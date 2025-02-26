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

class WebScraper:
    """Web scraper for fetching documentation"""
    
    def __init__(self):
        self.visited_urls = set()
        self.logger = logging.getLogger(__name__)
    
    async def scrape_url(self, url: str, depth: int = 1, 
                        is_library_doc: bool = False, 
                        library_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Scrape a URL and store the content
        Returns document metadata
        """
        # Check if document already exists
        existing_doc = operations.get_document_by_url(url)
        if existing_doc:
            self.logger.info(f"Document already exists for URL: {url}")
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
        
        # Recursive scraping if depth > 1
        if depth > 1:
            await self._scrape_links(url, html_content, depth - 1, 
                                    is_library_doc, library_id)
        
        # Return document info
        return operations.get_document(document_id)
    
    async def _fetch_url(self, url: str) -> Optional[str]:
        """Fetch HTML content from URL"""
        if url in self.visited_urls:
            return None
        
        self.visited_urls.add(url)
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=30) as response:
                    if response.status == 200:
                        return await response.text()
                    else:
                        self.logger.warning(f"Failed to fetch URL: {url} (Status: {response.status})")
                        return None
        except Exception as e:
            self.logger.error(f"Error fetching URL {url}: {e}")
            return None
    
    async def _scrape_links(self, base_url: str, html_content: str, 
                           depth: int, is_library_doc: bool, 
                           library_id: Optional[int]) -> None:
        """Extract and scrape links from HTML content"""
        from bs4 import BeautifulSoup
        
        # Parse base URL
        parsed_base = urlparse(base_url)
        base_domain = parsed_base.netloc
        
        # Parse HTML to extract links
        soup = BeautifulSoup(html_content, 'html.parser')
        links = soup.find_all('a', href=True)
        
        # Filter and normalize links
        urls_to_scrape = []
        for link in links:
            href = link['href']
            
            # Skip fragment links, javascript, mailto, etc.
            if not href or href.startswith('#') or href.startswith('javascript:') or href.startswith('mailto:'):
                continue
            
            # Resolve relative URLs
            full_url = urljoin(base_url, href)
            parsed_url = urlparse(full_url)
            
            # Only scrape links from the same domain
            if parsed_url.netloc != base_domain:
                continue
            
            # Skip already visited URLs
            if full_url in self.visited_urls:
                continue
                
            # Add to scrape list
            urls_to_scrape.append(full_url)
        
        # Scrape links concurrently (limit concurrency)
        tasks = []
        for url in urls_to_scrape[:10]:  # Limit to prevent overloading
            task = asyncio.create_task(
                self.scrape_url(url, depth, is_library_doc, library_id)
            )
            tasks.append(task)
        
        # Wait for all tasks to complete
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

# Create singleton instance
scraper = WebScraper()

# Convenience function
async def scrape_url(url: str, depth: int = 1, 
                   is_library_doc: bool = False, 
                   library_id: Optional[int] = None) -> Dict[str, Any]:
    """Scrape a URL and store the content"""
    return await scraper.scrape_url(url, depth, is_library_doc, library_id)
