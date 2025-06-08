import logging
import re
from typing import Any, Optional

import aiohttp

from docvault import config
from docvault.core.scraper import get_scraper
from docvault.db import operations

# Built-in mapping of library names to documentation URLs
LIBRARY_URL_PATTERNS = {
    # Data Science & Scientific Computing
    "pandas": "https://pandas.pydata.org/pandas-docs/version/{version}/",
    "numpy": "https://numpy.org/doc/{version}/",
    "scipy": "https://docs.scipy.org/doc/scipy/",
    "matplotlib": "https://matplotlib.org/stable/",
    "seaborn": "https://seaborn.pydata.org/",
    "plotly": "https://plotly.com/python/",
    "scikit-learn": "https://scikit-learn.org/stable/",
    "scikit-image": "https://scikit-image.org/docs/stable/",
    "statsmodels": "https://www.statsmodels.org/stable/",
    "sympy": "https://docs.sympy.org/latest/",
    
    # Machine Learning & AI
    "tensorflow": "https://www.tensorflow.org/versions/r{major}.{minor}/api_docs/python/tf",
    "pytorch": "https://pytorch.org/docs/{version}/",
    "torch": "https://pytorch.org/docs/{version}/",
    "keras": "https://keras.io/",
    "transformers": "https://huggingface.co/docs/transformers/",
    "openai": "https://platform.openai.com/docs/",
    
    # Web Development
    "django": "https://docs.djangoproject.com/en/{version}/",
    "flask": "https://flask.palletsprojects.com/en/{version}/",
    "fastapi": "https://fastapi.tiangolo.com/",
    "starlette": "https://www.starlette.io/",
    "pyramid": "https://docs.pylonsproject.org/projects/pyramid/",
    "tornado": "https://www.tornadoweb.org/en/stable/",
    "aiohttp": "https://docs.aiohttp.org/en/stable/",
    "celery": "https://docs.celeryproject.org/en/stable/",
    
    # HTTP & APIs
    "requests": "https://requests.readthedocs.io/en/{version}/",
    "httpx": "https://www.python-httpx.org/",
    "urllib3": "https://urllib3.readthedocs.io/en/stable/",
    
    # Database & ORM
    "sqlalchemy": "https://docs.sqlalchemy.org/en/{version}/",
    "django-orm": "https://docs.djangoproject.com/en/{version}/topics/db/",
    "peewee": "http://docs.peewee-orm.com/en/latest/",
    "pymongo": "https://pymongo.readthedocs.io/en/stable/",
    "redis": "https://redis-py.readthedocs.io/en/stable/",
    "psycopg2": "https://www.psycopg.org/docs/",
    
    # Testing
    "pytest": "https://docs.pytest.org/en/latest/",
    "unittest": "https://docs.python.org/3/library/unittest.html",
    "mock": "https://docs.python.org/3/library/unittest.mock.html",
    "nose2": "https://docs.nose2.io/en/latest/",
    "tox": "https://tox.readthedocs.io/en/latest/",
    "coverage": "https://coverage.readthedocs.io/en/latest/",
    
    # Utilities & Tools
    "click": "https://click.palletsprojects.org/en/{version}/",
    "rich": "https://rich.readthedocs.io/en/stable/",
    "typer": "https://typer.tiangolo.com/",
    "pydantic": "https://pydantic-docs.helpmanual.io/",
    "marshmallow": "https://marshmallow.readthedocs.io/en/stable/",
    "attrs": "https://www.attrs.org/en/stable/",
    "dataclasses": "https://docs.python.org/3/library/dataclasses.html",
    
    # Parsing & Processing
    "beautifulsoup4": "https://www.crummy.com/software/BeautifulSoup/bs4/doc/",
    "lxml": "https://lxml.de/",
    "pyparsing": "https://pyparsing-docs.readthedocs.io/en/latest/",
    "regex": "https://pypi.org/project/regex/",
    "jsonschema": "https://python-jsonschema.readthedocs.io/en/stable/",
    
    # Async & Concurrency
    "asyncio": "https://docs.python.org/3/library/asyncio.html",
    "trio": "https://trio.readthedocs.io/en/stable/",
    "twisted": "https://twistedmatrix.com/documents/current/",
    
    # Dev Tools & Deployment
    "docker": "https://docker-py.readthedocs.io/en/stable/",
    "fabric": "https://docs.fabfile.org/en/stable/",
    "ansible": "https://docs.ansible.com/ansible/latest/",
    "boto3": "https://boto3.amazonaws.com/v1/documentation/api/latest/",
    "kubernetes": "https://kubernetes.io/docs/reference/generated/kubernetes-api/v1.27/",
}


class LibraryManager:
    """Manager for library documentation"""

    # Map of programming languages to their documentation URL patterns
    LANGUAGE_PATTERNS = {
        "elixir": "https://hexdocs.pm/{library}/{version}",
        "rust": "https://docs.rs/{library}/{version}",
        "node": "https://www.npmjs.com/package/{library}/v/{version}",
        "ruby": "https://www.rubydoc.info/gems/{library}/{version}",
    }

    # Libraries known to be in specific languages
    LIBRARY_LANGUAGES = {
        # Elixir packages
        "jido": "elixir",
        "phoenix": "elixir",
        "ecto": "elixir",
        "ex_unit": "elixir",
        "plug": "elixir",
        "absinthe": "elixir",
        # Rust crates
        "tokio": "rust",
        "serde": "rust",
        "reqwest": "rust",
        "clap": "rust",
        "rocket": "rust",
        "rand": "rust",
        # Node.js packages
        "express": "node",
        "react": "node",
        "vue": "node",
        "lodash": "node",
        "axios": "node",
        # Ruby gems
        "rails": "ruby",
        "sinatra": "ruby",
        "devise": "ruby",
        "rspec": "ruby",
    }

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.url_patterns = LIBRARY_URL_PATTERNS

    async def get_library_docs(
        self, library_name: str, version: str = "latest"
    ) -> list[dict[str, Any]] | None:
        """Get documentation for a library, fetching it if necessary"""
        # Handle "latest" version lookup
        actual_version = version
        if version == "latest":
            # Try to get the latest known version from our database first
            latest_lib = operations.get_latest_library_version(library_name)
            if latest_lib and latest_lib.get("is_available"):
                self.logger.info(
                    f"Using latest known version {latest_lib['version']} for "
                    f"{library_name}"
                )
                documents = operations.get_library_documents(latest_lib["id"])
                if documents and isinstance(documents, list):
                    return documents
                return None

        # Check if we already have this library+version
        library = operations.get_library(library_name, version)
        if library and library.get("is_available"):
            documents = operations.get_library_documents(library["id"])
            if documents and isinstance(documents, list):
                return documents
            return None

        # If not, resolve the documentation URL
        doc_url = await self.resolve_doc_url(library_name, version)

        # If we can't find the URL and we're looking for latest version, try to
        # find the latest version
        if not doc_url and version == "latest":
            self.logger.info(
                f"Couldn't find latest version URL, trying to find latest "
                f"version for {library_name}"
            )

            # First, try to use Brave search to find the latest version
            latest_version = await self.find_latest_version_with_search(library_name)
            if latest_version and latest_version != "latest":
                self.logger.info(f"Found latest version via search: {latest_version}")
                actual_version = latest_version
                doc_url = await self.resolve_doc_url(library_name, latest_version)

            # If Brave search didn't work, try common version patterns
            if not doc_url:
                self.logger.info("Trying common version patterns")
                # Try to resolve a URL with a common stable version
                for fallback_version in [
                    "stable",
                    "1.0.0",
                    "1.0",
                    "0.1.0",
                    "main",
                    "master",
                ]:
                    self.logger.info(f"Trying fallback version: {fallback_version}")
                    doc_url = await self.resolve_doc_url(library_name, fallback_version)
                    if doc_url:
                        actual_version = fallback_version
                        self.logger.info(
                            f"Found URL for fallback version {fallback_version}"
                        )
                        break

        if not doc_url:
            return None

        # For "latest" version, try to determine the actual version number
        if version == "latest":
            actual_version = await self.determine_actual_version(library_name, doc_url)
            self.logger.info(f"Resolved 'latest' to actual version: {actual_version}")

            # If we couldn't determine the version, use a timestamp as a fallback
            if actual_version == "latest":
                from datetime import datetime

                timestamp = datetime.now().strftime("%Y.%m.%d")
                actual_version = f"{timestamp}-latest"

        # Store library info using the actual version
        library_id = operations.add_library(library_name, actual_version, doc_url)

        # Scrape the documentation with error suppression
        import logging

        # Temporarily set logging level to ERROR to suppress warning messages
        loggers = [
            logging.getLogger("docvault"),
            logging.getLogger("docvault.core.scraper"),
            logging.getLogger("docvault.core.library_manager"),
        ]
        original_levels = [logger.level for logger in loggers]
        for logger in loggers:
            logger.setLevel(logging.ERROR)

        try:
            scraper = get_scraper()
            document = await scraper.scrape_url(
                doc_url,
                depth=2,  # Scrape a bit deeper for library docs
                is_library_doc=True,
                library_id=library_id,
            )
        finally:
            # Restore original logging levels
            for logger, level in zip(loggers, original_levels):
                logger.setLevel(level)

        if document:
            # Update displayed version in the CLI
            try:
                # The title format is usually "Title — LibraryName vX.Y.Z"
                title = document.get("title", "")
                if " — " in title and " v" in title:
                    title_parts = title.split(" — ")
                    if len(title_parts) > 1:
                        lib_ver_part = title_parts[1].split(" ")
                        if len(lib_ver_part) > 1:
                            title_version = lib_ver_part[1].lstrip("v")
                            if version != title_version:
                                # Add resolved_version to show the user the correct
                                # version they asked for
                                document["resolved_version"] = actual_version
                else:
                    # If we can't parse the title, just set the resolved_version
                    document["resolved_version"] = actual_version
            except Exception:
                # If any error occurs, just set the resolved_version
                document["resolved_version"] = actual_version
            return [document]
        return None

    async def determine_actual_version(self, library_name: str, doc_url: str) -> str:
        """
        Try to determine the actual version number from documentation URL or content.
        """
        # Check if version is in URL
        import re

        # Common version patterns
        version_patterns = [
            r"v(\d+\.\d+\.\d+)",  # v1.2.3
            r"(\d+\.\d+\.\d+)",  # 1.2.3
            r"(\d+\.\d+\.\d+-\w+)",  # 1.2.3-rc1
            r"(\d+\.\d+)",  # 1.2
            r"version[/-](\d+\.\d+\.\d+)",  # version/1.2.3
        ]

        for pattern in version_patterns:
            match = re.search(pattern, doc_url)
            if match:
                return match.group(1)

        # If we can't determine the version, leave it as latest for now
        # In a more advanced implementation, we could scrape the page to find version
        # info
        return "latest"

    async def resolve_doc_url(self, library_name: str, version: str) -> str | None:
        """Resolve the documentation URL for a library"""
        # Check if we can connect to the URL using default patterns
        try:
            # Check built-in patterns
            if library_name in self.url_patterns:
                url = self.format_url_pattern(self.url_patterns[library_name], version)
                self.logger.debug(f"Checking hardcoded pattern URL: {url}")
                if await self.check_url_exists(url):
                    self.logger.info(f"Found working URL via hardcoded pattern: {url}")
                    return url
                else:
                    self.logger.warning(f"Hardcoded pattern URL failed: {url}")

            # Check if we know the language for this library
            if library_name in self.LIBRARY_LANGUAGES:
                language = self.LIBRARY_LANGUAGES[library_name]
                if language in self.LANGUAGE_PATTERNS:
                    pattern = self.LANGUAGE_PATTERNS[language]
                    url = pattern.replace("{library}", library_name).replace(
                        "{version}", version
                    )
                    if await self.check_url_exists(url):
                        return url

            # Try PyPI for Python libraries
            pypi_url = await self.get_pypi_doc_url(library_name, version)
            if pypi_url and await self.check_url_exists(pypi_url):
                return pypi_url

            # Last resort: search
            search_url = await self.search_doc_url(library_name, version)
            if search_url and await self.check_url_exists(search_url):
                return search_url

            return None
        except Exception as e:
            self.logger.error(f"Error resolving URL for {library_name} {version}: {e}")
            return None

    async def check_url_exists(self, url: str) -> bool:
        """Check if a URL exists and returns a valid response"""
        self.logger.debug(f"Checking if URL exists: {url}")
        try:
            async with aiohttp.ClientSession() as session:
                async with session.head(
                    url, allow_redirects=True, timeout=5
                ) as response:
                    return response.status < 400
        except Exception as e:
            self.logger.debug(f"URL check failed for {url}: {e}")
            return False

    def format_url_pattern(self, pattern: str, version: str) -> str:
        """Format URL pattern with version information"""
        # If pattern has no placeholders, return as-is
        if "{" not in pattern:
            return pattern
            
        if version == "latest" or version == "stable":
            version = "stable"
        else:
            # Handle version formatting for patterns that need major.minor
            if "{major}" in pattern and "{minor}" in pattern:
                parts = version.split(".")
                if len(parts) >= 2:
                    return pattern.format(
                        major=parts[0], minor=parts[1], version=version
                    )

        return pattern.format(version=version)

    async def get_pypi_doc_url(self, library_name: str, version: str) -> str | None:
        """Get documentation URL from PyPI metadata"""
        try:
            url = f"https://pypi.org/pypi/{library_name}/json"
            if version and version != "latest":
                url = f"https://pypi.org/pypi/{library_name}/{version}/json"

            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        return None

                    data = await response.json()
                    info = data.get("info", {})

                    # Check for documentation URL in metadata
                    project_urls = info.get("project_urls", {})
                    
                    # Try various common documentation URL keys
                    doc_keys = [
                        "Documentation", "Docs", "documentation", "docs",
                        "documentation_url", "doc_url", "Read the Docs",
                        "ReadTheDocs", "Manual", "User Guide", "API Reference"
                    ]
                    
                    doc_url = info.get("documentation_url")
                    if not doc_url and project_urls:
                        for key in doc_keys:
                            if key in project_urls:
                                doc_url = project_urls[key]
                                break
                                
                    if doc_url and doc_url.strip():
                        self.logger.info(f"Found documentation URL in PyPI metadata: {doc_url}")
                        return doc_url.strip()

                    # Fallback to homepage if it looks like documentation
                    homepage = info.get("home_page") or project_urls.get("Homepage")
                    if homepage and self._is_likely_documentation_url(
                        library_name, homepage
                    ):
                        self.logger.info(f"Using homepage as documentation URL: {homepage}")
                        return homepage
                        
                    # Try common documentation patterns based on package name
                    common_patterns = [
                        f"https://{library_name}.readthedocs.io/",
                        f"https://{library_name}.readthedocs.io/en/latest/",
                        f"https://{library_name}.readthedocs.io/en/stable/",
                        f"https://docs.{library_name}.org/",
                        f"https://{library_name}.org/docs/",
                        f"https://{library_name}.org/documentation/",
                        f"https://{library_name}.github.io/",
                    ]
                    
                    for pattern in common_patterns:
                        if await self.check_url_exists(pattern):
                            self.logger.info(f"Found documentation via pattern: {pattern}")
                            return pattern

            return None
        except Exception as e:
            self.logger.error(f"Error fetching PyPI metadata: {e}")
            return None

    async def find_latest_version_with_search(self, library_name: str) -> str | None:
        """Try to find the latest version of a library using Brave Search"""
        if not config.BRAVE_API_KEY:
            self.logger.warning("Brave API key not configured")
            return None

        query = f"{library_name} latest version release documentation"
        try:
            headers = {
                "Accept": "application/json",
                "X-Subscription-Token": config.BRAVE_API_KEY,
            }
            url = "https://api.search.brave.com/res/v1/web/search"
            params = {"q": query, "count": 5}

            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, params=params) as response:
                    if response.status != 200:
                        return None

                    data = await response.json()
                    results = data.get("web", {}).get("results", [])

                    # Common version patterns to extract from search results
                    version_patterns = [
                        # Version in title or description
                        r"(?:version|v)[:\s]+(\d+\.\d+(?:\.\d+)?(?:-\w+)?)",
                        r"(\d+\.\d+\.\d+(?:-\w+)?)",  # Standard semver
                        r"(\d+\.\d+(?:-\w+)?)",  # Major.minor
                        r"v(\d+\.\d+\.\d+(?:-\w+)?)",  # v1.2.3
                    ]

                    # Look through search results for version numbers
                    for result in results:
                        title = result.get("title", "")
                        description = result.get("description", "")
                        url = result.get("url", "")

                        # Check for version in these fields
                        for text in [title, description, url]:
                            for pattern in version_patterns:
                                match = re.search(pattern, text)
                                if match:
                                    return match.group(1)

            # If we couldn't find a version, return "latest"
            return "latest"
        except Exception as e:
            self.logger.error(f"Error searching for latest version: {e}")
            return "latest"

    async def search_doc_url(self, library_name: str, version: str) -> str | None:
        """Search for documentation URL using Brave Search"""
        if not config.BRAVE_API_KEY:
            self.logger.warning("Brave API key not configured")
            return None

        # Add the exact version to improve search accuracy
        query = f'{library_name} "version {version}" documentation official'
        try:
            headers = {
                "Accept": "application/json",
                "X-Subscription-Token": config.BRAVE_API_KEY,
            }
            url = "https://api.search.brave.com/res/v1/web/search"
            params = {"q": query, "count": 3}

            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, params=params) as response:
                    if response.status != 200:
                        return None

                    data = await response.json()
                    results = data.get("web", {}).get("results", [])

                    # Look for official documentation in results
                    for result in results:
                        url = result.get("url", "")
                        # Check if URL looks like documentation
                        if self._is_likely_documentation_url(library_name, url):
                            return url

                    # If no ideal match, return first result
                    if results:
                        return results[0].get("url")

            return None
        except Exception as e:
            self.logger.error(f"Error searching for documentation: {e}")
            return None

    def _is_likely_documentation_url(self, library_name: str, url: str) -> bool:
        """Check if a URL likely points to official documentation"""
        # Look for patterns that suggest official docs
        official_indicators = [
            f"{library_name}.org",
            f"{library_name}.io",
            f"{library_name}.readthedocs.io",
            "docs.",
            "documentation.",
            "reference.",
            "api.",
            "github.com/" + library_name,
            "pypi.org/project/" + library_name,
        ]

        url_lower = url.lower()
        library_lower = library_name.lower()

        # Check for language-specific documentation sites
        language_doc_patterns = {
            "hexdocs.pm/": "elixir",  # Elixir
            "docs.rs/": "rust",  # Rust
            "npmjs.com/package/": "node",  # Node.js
            "rubydoc.info/gems/": "ruby",  # Ruby
        }

        # Check if URL matches any of the language-specific patterns
        for pattern, lang in language_doc_patterns.items():
            if pattern in url_lower and library_lower in url_lower:
                # This looks like a language-specific documentation URL for this library
                return True

        # Fall back to general indicators
        return any(indicator.lower() in url_lower for indicator in official_indicators)

    def documentation_exists(self, library_name: str, version: str = "latest") -> bool:
        """
        Check if documentation for a library already exists in the database.

        Args:
            library_name: Name of the library
            version: Version of the library (default: "latest")

        Returns:
            bool: True if documentation exists, False otherwise
        """
        try:
            # Import here to avoid circular imports
            from docvault.db.operations import document_exists

            # Check if a document with this library name exists in the database
            doc_id = f"{library_name.lower()}:{version}"
            return document_exists(doc_id)

        except Exception as e:
            self.logger.error(
                f"Error checking if documentation exists for {library_name}: {e}"
            )
            return False


# Create singleton instance
library_manager = LibraryManager()


# Convenience function
async def lookup_library_docs(
    library_name: str, version: str = "latest"
) -> list[dict[str, Any]] | None:
    """Lookup and fetch documentation for a library"""
    return await library_manager.get_library_docs(library_name, version)
