"""OpenAPI/Swagger documentation extractor."""

import re
from typing import Any, Optional

from bs4 import BeautifulSoup, Tag

from .base import BaseExtractor


class OpenAPIExtractor(BaseExtractor):
    """Extractor specialized for OpenAPI/Swagger documentation."""

    def extract(self, soup: BeautifulSoup, url: str) -> dict[str, Any]:
        """Extract content from OpenAPI/Swagger documentation."""
        metadata = self.extract_metadata(soup)

        # Extract API specification
        api_spec = self._extract_api_spec(soup)
        if api_spec:
            metadata["api_spec"] = api_spec

        # Extract interactive elements
        interactive = self._extract_interactive_elements(soup)
        if interactive:
            metadata["interactive_elements"] = interactive

        # Extract authentication information
        auth_info = self._extract_auth_info(soup)
        if auth_info:
            metadata["authentication"] = auth_info

        # Extract endpoints
        endpoints = self._extract_endpoints(soup)
        if endpoints:
            metadata["endpoints"] = endpoints

        # Extract schemas/models
        schemas = self._extract_schemas(soup)
        if schemas:
            metadata["schemas"] = schemas

        # Extract main content
        content = self._extract_main_content(soup)

        # Extract code samples
        code_samples = self._extract_code_samples(soup)
        if code_samples:
            metadata["code_samples"] = code_samples

        return {"content": content, "metadata": metadata}

    def _extract_api_spec(self, soup: BeautifulSoup) -> dict[str, Any]:
        """Extract OpenAPI specification information."""
        spec_info = {}

        # Look for OpenAPI version in scripts or meta
        for script in soup.find_all("script"):
            text = script.string or ""
            if "openapi" in text.lower() or "swagger" in text.lower():
                # Try to extract version
                version_match = re.search(
                    r'["\']openapi["\']\s*:\s*["\']([^"\']+)["\']', text
                )
                if version_match:
                    spec_info["openapi_version"] = version_match.group(1)

                swagger_match = re.search(
                    r'["\']swagger["\']\s*:\s*["\']([^"\']+)["\']', text
                )
                if swagger_match:
                    spec_info["swagger_version"] = swagger_match.group(1)

        # Check for Swagger UI
        if soup.find(["div", "section"], id="swagger-ui"):
            spec_info["ui_type"] = "swagger-ui"

        # Check for ReDoc
        if soup.find(["div", "redoc"], id=["redoc", "redoc-container"]):
            spec_info["ui_type"] = "redoc"

        # Check for RapiDoc
        if soup.find("rapi-doc") or soup.find(["div"], class_="rapidoc"):
            spec_info["ui_type"] = "rapidoc"

        # Extract API title and version
        title_elem = soup.find(["h1", "h2"], class_=["api-title", "title"])
        if title_elem:
            spec_info["title"] = title_elem.get_text(strip=True)

        version_elem = soup.find(["span", "div"], class_=["version", "api-version"])
        if version_elem:
            spec_info["api_version"] = version_elem.get_text(strip=True)

        # Extract base URL
        base_url = self._extract_base_url(soup)
        if base_url:
            spec_info["base_url"] = base_url

        return spec_info

    def _extract_base_url(self, soup: BeautifulSoup) -> str | None:
        """Extract API base URL."""
        # Look for base URL in various places
        base_url_patterns = [
            (r'["\']basePath["\']\s*:\s*["\']([^"\']+)["\']', None),
            (r'["\']url["\']\s*:\s*["\']([^"\']+)["\']', lambda u: "http" in u),
            (
                r'["\']servers["\']\s*:\s*\[\s*\{\s*["\']url["\']\s*:\s*["\']([^"\']+)["\']',
                None,
            ),
        ]

        for script in soup.find_all("script"):
            text = script.string or ""
            for pattern, validator in base_url_patterns:
                match = re.search(pattern, text)
                if match:
                    url = match.group(1)
                    if validator is None or validator(url):
                        return url

        # Check for base URL in UI elements
        base_elem = soup.find(
            ["span", "div", "code"], class_=["base-url", "api-base-url"]
        )
        if base_elem:
            return base_elem.get_text(strip=True)

        return None

    def _extract_interactive_elements(self, soup: BeautifulSoup) -> dict[str, Any]:
        """Extract information about interactive API elements."""
        interactive = {}

        # Check for "Try it out" functionality
        try_it_out = soup.find(
            ["button", "a"], string=re.compile(r"try\s+it\s+out", re.I)
        )
        if try_it_out:
            interactive["try_it_out"] = True

        # Check for API key input
        api_key_input = soup.find(
            ["input", "button"], attrs={"name": re.compile(r"api[_-]?key", re.I)}
        )
        if api_key_input:
            interactive["api_key_input"] = True

        # Check for request/response examples
        if soup.find(
            ["div", "pre"],
            class_=re.compile(r"(request|response)[_-]?(example|sample)"),
        ):
            interactive["examples"] = True

        # Check for schema explorer
        if soup.find(
            ["div", "section"], class_=re.compile(r"schema[_-]?(explorer|viewer)")
        ):
            interactive["schema_explorer"] = True

        return interactive

    def _extract_auth_info(self, soup: BeautifulSoup) -> dict[str, Any]:
        """Extract authentication information."""
        auth_info = {}
        auth_methods = []

        # Look for authentication section
        auth_section = soup.find(
            ["section", "div"], class_=re.compile(r"auth|security", re.I)
        )
        if auth_section:
            # Extract auth method types
            for auth_type in ["bearer", "oauth2", "apikey", "basic", "jwt"]:
                if auth_type in auth_section.get_text().lower():
                    auth_methods.append(auth_type)

        # Look for authorization in scripts
        for script in soup.find_all("script"):
            text = script.string or ""
            if (
                "securityschemes" in text.lower()
                or "securitydefinitions" in text.lower()
            ):
                # Extract security schemes
                schemes_match = re.search(
                    r'["\']type["\']\s*:\s*["\']([^"\']+)["\']', text
                )
                if schemes_match:
                    auth_methods.append(schemes_match.group(1).lower())

        if auth_methods:
            auth_info["methods"] = list(set(auth_methods))

        # Look for OAuth scopes
        scopes_elem = soup.find(
            ["div", "ul"], class_=re.compile(r"scopes?|permissions?")
        )
        if scopes_elem:
            scopes = []
            for item in scopes_elem.find_all(["li", "span", "code"]):
                scope_text = item.get_text(strip=True)
                if scope_text and ":" in scope_text:
                    scopes.append(scope_text)

            if scopes:
                auth_info["scopes"] = scopes

        return auth_info

    def _extract_endpoints(self, soup: BeautifulSoup) -> list[dict[str, Any]]:
        """Extract API endpoints."""
        endpoints = []

        # Look for endpoint definitions
        endpoint_containers = soup.find_all(
            ["div", "section"], class_=re.compile(r"endpoint|operation|path", re.I)
        )

        for container in endpoint_containers:
            endpoint = {}

            # Extract HTTP method
            method_elem = container.find(
                ["span", "div"], class_=re.compile(r"(http[_-]?)?(method|verb)", re.I)
            )
            if method_elem:
                method = method_elem.get_text(strip=True).upper()
                if method in [
                    "GET",
                    "POST",
                    "PUT",
                    "DELETE",
                    "PATCH",
                    "HEAD",
                    "OPTIONS",
                ]:
                    endpoint["method"] = method

            # Extract path
            path_elem = container.find(
                ["span", "code"], class_=re.compile(r"(api[_-]?)?path|url", re.I)
            )
            if path_elem:
                endpoint["path"] = path_elem.get_text(strip=True)

            # Extract summary/description
            summary_elem = container.find(
                ["span", "p"], class_=re.compile(r"summary|description", re.I)
            )
            if summary_elem:
                endpoint["summary"] = summary_elem.get_text(strip=True)

            # Extract parameters
            params = self._extract_parameters(container)
            if params:
                endpoint["parameters"] = params

            # Extract response codes
            responses = self._extract_responses(container)
            if responses:
                endpoint["responses"] = responses

            if "method" in endpoint and "path" in endpoint:
                endpoints.append(endpoint)

        # Also try to extract from operation IDs
        operation_elems = soup.find_all(
            ["div", "span"], attrs={"data-operation-id": True}
        )
        for elem in operation_elems:
            endpoint = {
                "operation_id": elem.get("data-operation-id"),
                "method": elem.get("data-method", "").upper(),
                "path": elem.get("data-path", ""),
            }
            if endpoint["method"] and endpoint["path"]:
                endpoints.append(endpoint)

        return endpoints

    def _extract_parameters(self, container: Tag) -> list[dict[str, str]]:
        """Extract parameters from an endpoint container."""
        parameters = []

        # Look for parameter table
        param_table = container.find("table", class_=re.compile(r"param|argument"))
        if param_table:
            headers = [
                th.get_text(strip=True).lower() for th in param_table.find_all("th")
            ]

            for row in param_table.find_all("tr")[1:]:  # Skip header row
                cells = row.find_all(["td", "th"])
                if len(cells) >= 2:
                    param = {}
                    for i, cell in enumerate(cells):
                        if i < len(headers):
                            param[headers[i]] = cell.get_text(strip=True)

                    if "name" in param or "parameter" in param:
                        parameters.append(param)

        # Look for parameter list
        param_list = container.find(["ul", "dl"], class_=re.compile(r"param|argument"))
        if param_list:
            for item in param_list.find_all(["li", "dt"]):
                param_text = item.get_text(strip=True)
                if param_text:
                    # Try to parse parameter format: "name (type): description"
                    match = re.match(r"(\w+)\s*\(([^)]+)\)\s*:\s*(.+)", param_text)
                    if match:
                        parameters.append(
                            {
                                "name": match.group(1),
                                "type": match.group(2),
                                "description": match.group(3),
                            }
                        )

        return parameters

    def _extract_responses(self, container: Tag) -> dict[str, str]:
        """Extract response codes and descriptions."""
        responses = {}

        # Look for response section
        response_section = container.find(
            ["div", "section"], class_=re.compile(r"response")
        )
        if response_section:
            # Look for response codes
            for elem in response_section.find_all(["span", "code"]):
                text = elem.get_text(strip=True)
                # Match HTTP status codes
                if re.match(r"^\d{3}$", text):
                    # Get description
                    desc_elem = elem.find_next(["span", "p"])
                    if desc_elem:
                        responses[text] = desc_elem.get_text(strip=True)

        return responses

    def _extract_schemas(self, soup: BeautifulSoup) -> list[dict[str, Any]]:
        """Extract schema/model definitions."""
        schemas = []

        # Look for schema sections
        schema_sections = soup.find_all(
            ["div", "section"], class_=re.compile(r"(schema|model|definition)", re.I)
        )

        for section in schema_sections:
            schema = {}

            # Extract schema name
            name_elem = section.find(
                ["h3", "h4", "span"],
                class_=re.compile(r"(schema|model)[_-]?name", re.I),
            )
            if name_elem:
                schema["name"] = name_elem.get_text(strip=True)

            # Extract properties
            props = self._extract_schema_properties(section)
            if props:
                schema["properties"] = props

            # Extract example
            example_elem = section.find(
                ["pre", "code"], class_=re.compile(r"example|sample")
            )
            if example_elem:
                schema["example"] = example_elem.get_text(strip=True)

            if "name" in schema:
                schemas.append(schema)

        return schemas

    def _extract_schema_properties(self, section: Tag) -> list[dict[str, str]]:
        """Extract properties from a schema section."""
        properties = []

        # Look for property table
        prop_table = section.find("table", class_=re.compile(r"propert"))
        if prop_table:
            for row in prop_table.find_all("tr")[1:]:  # Skip header
                cells = row.find_all(["td", "th"])
                if len(cells) >= 2:
                    prop = {
                        "name": cells[0].get_text(strip=True),
                        "type": cells[1].get_text(strip=True) if len(cells) > 1 else "",
                        "description": (
                            cells[2].get_text(strip=True) if len(cells) > 2 else ""
                        ),
                    }
                    properties.append(prop)

        return properties

    def _extract_main_content(self, soup: BeautifulSoup) -> str:
        """Extract main content from OpenAPI documentation."""
        # Try different content containers
        content_selectors = [
            ("div", {"id": "swagger-ui"}),
            ("div", {"id": "redoc"}),
            ("div", {"class": "api-documentation"}),
            ("main", {"class": "content"}),
            ("div", {"role": "main"}),
        ]

        for tag, attrs in content_selectors:
            content_elem = soup.find(tag, attrs)
            if content_elem:
                return self._clean_content(content_elem)

        # Fallback to body
        body = soup.find("body")
        return self._clean_content(body) if body else ""

    def _extract_code_samples(self, soup: BeautifulSoup) -> list[dict[str, Any]]:
        """Extract code samples from API documentation."""
        code_samples = []

        # Look for code sample containers
        sample_containers = soup.find_all(
            ["div", "section"], class_=re.compile(r"code[_-]?sample|example[_-]?code")
        )

        for container in sample_containers:
            # Look for language tabs
            lang_tabs = container.find_all(
                ["button", "a"], class_=re.compile(r"lang|tab")
            )

            if lang_tabs:
                # Multi-language samples
                for tab in lang_tabs:
                    lang = tab.get_text(strip=True).lower()
                    # Find associated code block
                    code_id = tab.get("data-target") or tab.get("href", "").lstrip("#")
                    if code_id:
                        code_block = soup.find(id=code_id)
                    else:
                        code_block = tab.find_next("pre")

                    if code_block:
                        code_samples.append(
                            {"language": lang, "code": code_block.get_text(strip=True)}
                        )
            else:
                # Single language sample
                code_block = container.find("pre")
                if code_block:
                    sample = {"code": code_block.get_text(strip=True)}

                    # Try to detect language
                    lang_class = None
                    for cls in code_block.get("class", []):
                        if cls.startswith("language-"):
                            lang_class = cls.replace("language-", "")
                            break

                    if lang_class:
                        sample["language"] = lang_class

                    code_samples.append(sample)

        return code_samples
