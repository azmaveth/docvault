import aiohttp
import asyncio
from typing import Dict, Any, List, Set, Optional
import re
import logging
from urllib.parse import urljoin, urlparse

from docvault.core.processor import html_to_markdown, extract_title, segment_markdown
from docvault.core.storage import save_html, save_markdown
from docvault.core.embeddings import generate_embeddings
from docvault.db import operations

# Get WebScraper instance
_scraper = None

def get_scraper():
    """Get or create a WebScraper instance"""
    global _scraper
    if _scraper is None:
        _scraper = WebScraper()
    return _scraper

class WebScraper:
    """Web scraper for fetching documentation"""
    
    def __init__(self):
        self.visited_urls = set()
        self.logger = logging.getLogger(__name__)
        # Stats tracking
        self.stats = {
            "pages_scraped": 0,
            "pages_skipped": 0,
            "segments_created": 0
        }
    
    async def scrape_url(self, url: str, depth: int = 1, 
                        is_library_doc: bool = False, 
                        library_id: Optional[int] = None,
                        max_links: Optional[int] = None,
                        strict_path: bool = True) -> Dict[str, Any]:
        """
        Scrape a URL and store the content
        Returns document metadata
        """
        # Check if document already exists
        existing_doc = operations.get_document_by_url(url)
        if existing_doc:
            self.stats["pages_skipped"] += 1
            self.logger.debug(f"Document already exists for URL: {url}")
            return existing_doc
        
        # Fetch HTML content
        html_content = await self._fetch_url(url)
        if not html_content:
            raise ValueError(f"Failed to fetch URL: {url}")
        
        # Extract title
        title = extract_title(html_content) or url
        
        # Convert to markdown
        markdown_content = html_to_markdown(html_content)
        
        # Save both formats
        html_path = save_html(html_content, url)
        markdown_path = save_markdown(markdown_content, url)
        
        # Add to database
        document_id = operations.add_document(
            url=url,
            title=title,
            html_path=html_path,
            markdown_path=markdown_path,
            library_id=library_id,
            is_library_doc=is_library_doc
        )
        
        # Update stats
        self.stats["pages_scraped"] += 1
        
        # Segment and embed content
        segments = segment_markdown(markdown_content)
        for i, (segment_type, content) in enumerate(segments):
            # Skip very short segments
            if len(content.strip()) < 10:
                continue
                
            # Generate embeddings
            embedding = await generate_embeddings(content)
            
            # Store segment with embedding
            operations.add_document_segment(
                document_id=document_id,
                content=content,
                embedding=embedding,
                segment_type=segment_type,
                position=i
            )
            
            # Update stats
            self.stats["segments_created"] += 1
        
        # Recursive scraping if depth > 1
        if depth > 1:
            await self._scrape_links(url, html_content, depth - 1, 
                                    is_library_doc, library_id, max_links, strict_path)
        
        # Return document info
        return operations.get_document(document_id)
    
    async def _fetch_url(self, url: str) -> Optional[str]:
        """Fetch HTML content from URL"""
        if url in self.visited_urls:
            return None
        
        self.visited_urls.add(url)
        
        # Skip fragment URLs (they reference parts of existing pages)
        if '#' in url:
            base_url = url.split('#')[0]
            if base_url in self.visited_urls:
                return None
        
        try:
            headers = {
                'User-Agent': 'DocVault/0.1.0 Documentation Indexer',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, timeout=30) as response:
                    if response.status == 200:
                        # Check content type to skip binary files
                        content_type = response.headers.get('Content-Type', '')
                        if 'text/html' not in content_type and \
                           'application/xhtml+xml' not in content_type and \
                           'application/xml' not in content_type and \
                           'text/plain' not in content_type:
                            self.logger.debug(f"Skipping non-text content: {url} (Content-Type: {content_type})")
                            return None
                            
                        try:
                            return await response.text()
                        except UnicodeDecodeError as e:
                            self.logger.debug(f"Unicode decode error for {url}: {e}")
                            return None
                    else:
                        if response.status != 404:  # Only log non-404 errors as debug
                            self.logger.debug(f"Failed to fetch URL: {url} (Status: {response.status})")
                        return None
        except asyncio.TimeoutError:
            self.logger.debug(f"Timeout fetching URL: {url}")
            return None
        except aiohttp.ClientError as e:
            self.logger.debug(f"Client error fetching URL {url}: {e}")
            return None
        except Exception as e:
            self.logger.debug(f"Error fetching URL {url}: {e}")
            return None
    
    async def _scrape_links(self, base_url: str, html_content: str, 
                           depth: int, is_library_doc: bool, 
                           library_id: Optional[int], 
                           max_links: Optional[int] = None,
                           strict_path: bool = True) -> None:
        """Extract and scrape links from HTML content"""
        from bs4 import BeautifulSoup
        
        # Parse base URL
        parsed_base = urlparse(base_url)
        base_domain = parsed_base.netloc
        
        # Get base path to restrict scraping to same hierarchy
        base_path_parts = [p for p in parsed_base.path.split('/') if p]
        # Keep at least the first part of the path to restrict to the project
        # For example, from /jido/readme.html, we'll only follow links starting with /jido/
        if len(base_path_parts) > 0:
            base_path_prefix = '/' + base_path_parts[0]
        else:
            base_path_prefix = '/'
        
        # Parse HTML to extract links
        soup = BeautifulSoup(html_content, 'html.parser')
        links = soup.find_all('a', href=True)
        
        # Filter and normalize links
        urls_to_scrape = []
        for link in links:
            href = link['href']
            
            # Skip empty, fragment, javascript, and mailto links
            if not href or href.startswith('#') or href.startswith('javascript:') or href.startswith('mailto:'):
                continue
                
            # Skip common binary file extensions that cause issues
            skip_extensions = ['.pdf', '.zip', '.epub', '.png', '.jpg', '.jpeg', '.gif', '.mp3', '.mp4', '.exe', '.dmg']
            if any(href.lower().endswith(ext) for ext in skip_extensions):
                continue
            
            # Resolve relative URLs
            full_url = urljoin(base_url, href)
            parsed_url = urlparse(full_url)
            
            # Skip fragment URLs that reference the same page
            if parsed_url.fragment and parsed_url._replace(fragment='').geturl() == base_url:
                continue
                
            # Only scrape links from the same domain
            if parsed_url.netloc != base_domain:
                continue
                
            # Only follow links within the same URL hierarchy if strict_path is enabled
            if strict_path and not parsed_url.path.startswith(base_path_prefix):
                self.logger.debug(f"Skipping link outside hierarchy: {full_url}")
                continue
            
            # Skip already visited URLs
            if full_url in self.visited_urls:
                self.stats["pages_skipped"] += 1
                continue
                
            # Add to scrape list
            urls_to_scrape.append(full_url)
        
        self.logger.info(f"Found {len(urls_to_scrape)} links to scrape at depth {depth}")
        
        # Limit number of URLs to scrape at deeper levels to prevent explosion
        if max_links is not None:
            max_urls = max_links
        else:
            max_urls = max(30, 100 // depth)
            
        if len(urls_to_scrape) > max_urls:
            self.logger.info(f"Limiting to {max_urls} URLs at depth {depth}")
            urls_to_scrape = urls_to_scrape[:max_urls]
        
        # Scrape links concurrently (limited concurrency)
        tasks = []
        for url in urls_to_scrape:
            # Log the URL being scraped
            self.logger.debug(f"Queuing: {url} (depth {depth})")
            task = asyncio.create_task(
                self.scrape_url(url, depth, is_library_doc, library_id, max_links, strict_path)
            )
            tasks.append(task)
        
        # Wait for all tasks to complete
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            # Log any exceptions (but only for non-404 errors)
            for i, result in enumerate(results):
                if isinstance(result, Exception) and not (
                    hasattr(result, 'status') and result.status == 404
                ):
                    self.logger.warning(f"Error scraping {urls_to_scrape[i]}: {result}")

# Create singleton instance
scraper = WebScraper()

# Convenience function
async def scrape_url(url: str, depth: int = 1, 
                   is_library_doc: bool = False, 
                   library_id: Optional[int] = None,
                   max_links: Optional[int] = None,
                   strict_path: bool = True) -> Dict[str, Any]:
    """Scrape a URL and store the content"""
    return await scraper.scrape_url(url, depth, is_library_doc, library_id, max_links, strict_path)
