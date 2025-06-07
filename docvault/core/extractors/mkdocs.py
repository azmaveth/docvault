"""MkDocs documentation extractor."""

from typing import Any, Dict, List

from bs4 import BeautifulSoup, Tag

from .base import BaseExtractor


class MkDocsExtractor(BaseExtractor):
    """Extractor specialized for MkDocs documentation."""

    def extract(self, soup: BeautifulSoup, url: str) -> dict[str, Any]:
        """Extract content from MkDocs documentation."""
        metadata = self.extract_metadata(soup)

        # Extract navigation structure
        nav_structure = self._extract_navigation(soup)
        if nav_structure:
            metadata["navigation"] = nav_structure

        # Extract search index if available
        search_index = self._extract_search_index(soup)
        if search_index:
            metadata["search_index"] = search_index

        # Extract theme information
        theme_info = self._extract_theme_info(soup)
        if theme_info:
            metadata["theme"] = theme_info

        # Extract page metadata
        page_meta = self._extract_page_metadata(soup)
        if page_meta:
            metadata.update(page_meta)

        # Extract main content
        content = self._extract_main_content(soup)

        # Extract code examples with language detection
        code_examples = self._extract_code_examples(soup)
        if code_examples:
            metadata["code_examples"] = code_examples

        # Extract admonitions (notes, warnings, etc.)
        admonitions = self._extract_admonitions(soup)
        if admonitions:
            metadata["admonitions"] = admonitions

        return {"content": content, "metadata": metadata}

    def _extract_navigation(self, soup: BeautifulSoup) -> list[dict[str, Any]]:
        """Extract MkDocs navigation structure."""
        nav_items = []

        # Look for navigation in sidebar
        nav_element = soup.find(["nav", "div"], class_=["md-nav", "md-sidebar"])
        if nav_element:
            nav_items = self._parse_nav_tree(nav_element)

        # Also check for breadcrumbs
        breadcrumbs = soup.find(["nav", "ol"], class_=["md-breadcrumb", "breadcrumb"])
        if breadcrumbs:
            nav_items.append(
                {
                    "type": "breadcrumbs",
                    "items": [
                        item.get_text(strip=True)
                        for item in breadcrumbs.find_all(["li", "a"])
                    ],
                }
            )

        return nav_items

    def _parse_nav_tree(self, nav_element: Tag) -> list[dict[str, Any]]:
        """Parse navigation tree recursively."""
        items = []

        # Find the ul element first
        ul_element = nav_element.find("ul")
        if ul_element:
            nav_element = ul_element

        for item in nav_element.find_all(["li"], recursive=False):
            nav_item = {}

            # Get link and text
            link = item.find("a")
            if link:
                nav_item["title"] = link.get_text(strip=True)
                nav_item["url"] = link.get("href", "")

            # Check for sub-navigation
            sub_nav = item.find(["ul", "nav"])
            if sub_nav:
                nav_item["children"] = self._parse_nav_tree(sub_nav)

            if nav_item:
                items.append(nav_item)

        return items

    def _extract_search_index(self, soup: BeautifulSoup) -> dict[str, Any]:
        """Extract search index information."""
        search_info = {}

        # Look for search configuration
        search_script = soup.find(
            "script", string=lambda t: t and "search_index.json" in t
        )
        if search_script:
            search_info["has_search"] = True
            search_info["search_type"] = "mkdocs-search"

        # Check for algolia search
        algolia_script = soup.find(
            "script", string=lambda t: t and "algolia" in t.lower() if t else False
        )
        if algolia_script:
            search_info["has_search"] = True
            search_info["search_type"] = "algolia"

        return search_info

    def _extract_theme_info(self, soup: BeautifulSoup) -> dict[str, str]:
        """Extract MkDocs theme information."""
        theme_info = {}

        # Check for Material theme
        if soup.find(class_=["md-header", "md-container"]):
            theme_info["name"] = "material"

            # Extract Material theme features
            features = []
            if soup.find(class_="md-search"):
                features.append("search")
            if soup.find(class_="md-tabs"):
                features.append("tabs")
            if soup.find(class_="md-sidebar--secondary"):
                features.append("toc")

            if features:
                theme_info["features"] = features

        # Check for ReadTheDocs theme
        elif soup.find(class_=["rst-content", "wy-nav-side"]):
            theme_info["name"] = "readthedocs"

        # Check for default MkDocs theme
        elif soup.find(class_=["navbar", "bs-sidebar"]):
            theme_info["name"] = "mkdocs"

        return theme_info

    def _extract_page_metadata(self, soup: BeautifulSoup) -> dict[str, Any]:
        """Extract page-level metadata."""
        metadata = {}

        # Extract from meta tags
        for meta in soup.find_all("meta"):
            name = meta.get("name", "") or meta.get("property", "")
            content = meta.get("content", "")

            if name and content:
                if name in ["description", "keywords", "author"]:
                    metadata[f"page_{name}"] = content
                elif name.startswith("mkdocs:"):
                    metadata[name.replace("mkdocs:", "mkdocs_")] = content

        # Extract edit URL if available
        edit_link = soup.find("a", class_=["md-content__button", "edit-page"])
        if edit_link:
            metadata["edit_url"] = edit_link.get("href", "")

        # Extract last updated date
        date_elem = soup.find(
            ["span", "time"], class_=["md-source__date", "git-revision-date"]
        )
        if date_elem:
            metadata["last_updated"] = date_elem.get_text(strip=True)

        return metadata

    def _extract_main_content(self, soup: BeautifulSoup) -> str:
        """Extract main content from MkDocs page."""
        # Try different content containers
        content_selectors = [
            ("article", {"class": "md-content__inner"}),
            ("div", {"class": "md-content"}),
            ("main", {"class": "md-main"}),
            ("div", {"role": "main"}),
            ("div", {"class": "rst-content"}),
            ("div", {"class": "bs-docs-section"}),
        ]

        for tag, attrs in content_selectors:
            content_elem = soup.find(tag, attrs)
            if content_elem:
                return self._clean_content(content_elem)

        # Fallback to body
        body = soup.find("body")
        return self._clean_content(body) if body else ""

    def _extract_code_examples(self, soup: BeautifulSoup) -> list[dict[str, str]]:
        """Extract code examples with language information."""
        code_examples = []

        # Look for code blocks with language
        for code_block in soup.find_all(
            ["pre", "div"], class_=["highlight", "codehilite"]
        ):
            example = {}

            # Try to detect language
            lang_class = None
            for cls in code_block.get("class", []):
                if cls.startswith("language-"):
                    lang_class = cls.replace("language-", "")
                    break

            # Check for language in child elements
            if not lang_class:
                lang_elem = code_block.find(
                    class_=lambda c: c
                    and any(
                        c.startswith(p) for p in ["language-", "lang-", "highlight-"]
                    )
                )
                if lang_elem:
                    for cls in lang_elem.get("class", []):
                        if cls.startswith(("language-", "lang-", "highlight-")):
                            lang_class = cls.split("-", 1)[1]
                            break

            # Extract code
            code_elem = code_block.find("code")
            if code_elem:
                example["code"] = code_elem.get_text(strip=True)
                if lang_class:
                    example["language"] = lang_class

                # Check for title/filename
                title_elem = code_block.find_previous(
                    ["div", "span"], class_=["filename", "code-title"]
                )
                if title_elem:
                    example["title"] = title_elem.get_text(strip=True)

                code_examples.append(example)

        return code_examples

    def _extract_admonitions(self, soup: BeautifulSoup) -> list[dict[str, str]]:
        """Extract admonitions (notes, warnings, tips, etc.)."""
        admonitions = []

        # Material for MkDocs admonitions
        for admonition in soup.find_all("div", class_="admonition"):
            adm_type = None
            adm_classes = admonition.get("class", [])

            # Find admonition type from classes
            for cls in adm_classes:
                if cls != "admonition":
                    adm_type = cls
                    break

            # Get title and content
            title_elem = admonition.find(["p", "div"], class_="admonition-title")
            title = (
                title_elem.get_text(strip=True) if title_elem else adm_type or "Note"
            )

            # Remove title from content
            if title_elem:
                title_elem.decompose()

            content = admonition.get_text(strip=True)

            admonitions.append(
                {"type": adm_type or "note", "title": title, "content": content}
            )

        # Also check for Bootstrap-style alerts
        for alert in soup.find_all("div", class_=lambda c: c and "alert" in c):
            alert_type = "info"
            for cls in alert.get("class", []):
                if cls.startswith("alert-"):
                    alert_type = cls.replace("alert-", "")
                    break

            admonitions.append(
                {"type": alert_type, "content": alert.get_text(strip=True)}
            )

        return admonitions
