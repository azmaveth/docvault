import aiohttp
import logging
from typing import Dict, Any, List, Optional
import re
import json

from docvault import config
from docvault.db import operations
from docvault.core.scraper import scrape_url

# Built-in mapping of library names to documentation URLs
LIBRARY_URL_PATTERNS = {
    "pandas": "https://pandas.pydata.org/pandas-docs/version/{version}/",
    "numpy": "https://numpy.org/doc/{version}/",
    "tensorflow": "https://www.tensorflow.org/versions/r{major}.{minor}/api_docs/python/tf",
    "pytorch": "https://pytorch.org/docs/{version}/",
    "django": "https://docs.djangoproject.com/en/{version}/",
    "flask": "https://flask.palletsprojects.com/en/{version}/",
    "requests": "https://requests.readthedocs.io/en/{version}/",
    "beautifulsoup4": "https://www.crummy.com/software/BeautifulSoup/bs4/doc/",
    "matplotlib": "https://matplotlib.org/stable/",
    "scikit-learn": "https://scikit-learn.org/stable/",
    "sqlalchemy": "https://docs.sqlalchemy.org/en/{version}/",
    "fastapi": "https://fastapi.tiangolo.com/",
}

class LibraryManager:
    """Manager for library documentation"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.url_patterns = LIBRARY_URL_PATTERNS
    
    async def get_library_docs(self, library_name: str, version: str = "latest") -> Optional[List[Dict[str, Any]]]:
        """Get documentation for a library, fetching it if necessary"""
        # Check if we already have this library+version
        library = operations.get_library(library_name, version)
        if library and library["is_available"]:
            return operations.get_library_documents(library["id"])
            
        # If not, resolve the documentation URL
        doc_url = await self.resolve_doc_url(library_name, version)
        if not doc_url:
            return None
            
        # Store library info
        library_id = operations.add_library(library_name, version, doc_url)
        
        # Scrape the documentation
        document = await scrape_url(
            doc_url, 
            depth=2,  # Scrape a bit deeper for library docs
            is_library_doc=True, 
            library_id=library_id
        )
        
        if document:
            return [document]
        return None
    
    async def resolve_doc_url(self, library_name: str, version: str) -> Optional[str]:
        """Resolve the documentation URL for a library"""
        # Check built-in patterns
        if library_name in self.url_patterns:
            return self.format_url_pattern(
                self.url_patterns[library_name], 
                version
            )
            
        # Try PyPI for Python libraries
        pypi_url = await self.get_pypi_doc_url(library_name, version)
        if pypi_url:
            return pypi_url
            
        # Last resort: search
        return await self.search_doc_url(library_name, version)
    
    def format_url_pattern(self, pattern: str, version: str) -> str:
        """Format URL pattern with version information"""
        if version == "latest" or version == "stable":
            version = "stable"
        else:
            # Handle version formatting for patterns that need major.minor
            if "{major}" in pattern and "{minor}" in pattern:
                parts = version.split(".")
                if len(parts) >= 2:
                    return pattern.format(
                        major=parts[0], 
                        minor=parts[1],
                        version=version
                    )
        
        return pattern.format(version=version)
    
    async def get_pypi_doc_url(self, library_name: str, version: str) -> Optional[str]:
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
                    doc_url = info.get("documentation_url") or info.get("project_urls", {}).get("Documentation")
                    if doc_url:
                        return doc_url
                        
                    # Fallback to homepage
                    homepage = info.get("home_page") or info.get("project_urls", {}).get("Homepage")
                    if homepage and self._is_likely_documentation_url(library_name, homepage):
                        return homepage
                        
            return None
        except Exception as e:
            self.logger.error(f"Error fetching PyPI metadata: {e}")
            return None
    
    async def search_doc_url(self, library_name: str, version: str) -> Optional[str]:
        """Search for documentation URL using Brave Search"""
        if not config.BRAVE_SEARCH_API_KEY:
            self.logger.warning("Brave Search API key not configured")
            return None
            
        query = f"{library_name} {version} documentation official"
        try:
            headers = {
                "Accept": "application/json",
                "X-Subscription-Token": config.BRAVE_SEARCH_API_KEY
            }
            url = "https://api.search.brave.com/res/v1/web/search"
            params = {
                "q": query,
                "count": 3
            }
            
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
            "pypi.org/project/" + library_name
        ]
        
        url_lower = url.lower()
        return any(indicator.lower() in url_lower for indicator in official_indicators)

# Create singleton instance
library_manager = LibraryManager()

# Convenience function
async def lookup_library_docs(library_name: str, version: str = "latest") -> Optional[List[Dict[str, Any]]]:
    """Lookup and fetch documentation for a library"""
    return await library_manager.get_library_docs(library_name, version)
