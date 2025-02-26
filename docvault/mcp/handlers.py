import asyncio
from typing import Dict, Any

from docvault.core.scraper import scrape_url
from docvault.core.embeddings import search
from docvault.core.library_manager import lookup_library_docs
from docvault.core.storage import read_markdown, read_html
from docvault.db import operations

async def handle_scrape_document(params: Dict[str, Any]) -> Dict[str, Any]:
    """Handler for scrape_document tool"""
    url = params["url"]
    depth = params.get("depth", 1)
    
    try:
        result = await scrape_url(url, depth=depth)
        return {
            "success": True,
            "document_id": result["id"],
            "title": result["title"],
            "url": url
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

async def handle_search_documents(params: Dict[str, Any]) -> Dict[str, Any]:
    """Handler for search_documents tool"""
    query = params["query"]
    limit = params.get("limit", 5)
    
    try:
        results = await search(query, limit=limit)
        return {
            "success": True,
            "results": [
                {
                    "document_id": r["document_id"],
                    "segment_id": r["id"],
                    "title": r["title"],
                    "content": r["content"][:200] + "..." if len(r["content"]) > 200 else r["content"],
                    "score": r["score"]
                } for r in results
            ]
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

async def handle_read_document(params: Dict[str, Any]) -> Dict[str, Any]:
    """Handler for read_document tool"""
    document_id = params["document_id"]
    format = params.get("format", "markdown")
    
    try:
        document = operations.get_document(document_id)
        
        if not document:
            return {
                "success": False,
                "error": f"Document not found: {document_id}"
            }
        
        if format.lower() == "html":
            content = read_html(document["html_path"])
        else:
            content = read_markdown(document["markdown_path"])
        
        return {
            "success": True,
            "document_id": document_id,
            "title": document["title"],
            "url": document["url"],
            "format": format,
            "content": content
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

async def handle_lookup_library_docs(params: Dict[str, Any]) -> Dict[str, Any]:
    """Handler for lookup_library_docs tool"""
    library_name = params["library_name"]
    version = params.get("version", "latest")
    
    try:
        documents = await lookup_library_docs(library_name, version)
        
        if not documents:
            return {
                "success": False,
                "message": f"Could not find documentation for {library_name} {version}"
            }
        
        return {
            "success": True,
            "message": f"Documentation for {library_name} {version} is available",
            "document_count": len(documents),
            "documents": [
                {
                    "id": doc["id"],
                    "title": doc["title"],
                    "url": doc["url"]
                } for doc in documents
            ]
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

async def handle_list_documents(params: Dict[str, Any]) -> Dict[str, Any]:
    """Handler for list_documents tool"""
    filter_text = params.get("filter", "")
    limit = params.get("limit", 20)
    
    try:
        documents = operations.list_documents(
            limit=limit, 
            filter_text=filter_text
        )
        
        return {
            "success": True,
            "document_count": len(documents),
            "documents": [
                {
                    "id": doc["id"],
                    "title": doc["title"],
                    "url": doc["url"],
                    "scraped_at": doc["scraped_at"]
                } for doc in documents
            ]
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }
