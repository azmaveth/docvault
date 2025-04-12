import aiohttp
import numpy as np
from typing import List, Dict, Any, Optional
import json
import logging

from docvault import config
from docvault.db import operations

async def generate_embeddings(text: str) -> bytes:
    """
    Generate embeddings for text using Ollama
    Returns binary embeddings (numpy array as bytes)
    """
    logger = logging.getLogger(__name__)
    
    # Format request for Ollama
    request_data = {
        "model": config.EMBEDDING_MODEL,
        "prompt": text
    }
    
    try:
        # Create a session for the request
        session = aiohttp.ClientSession()
        try:
            # Make the request
            resp = await session.post(
                f"{config.OLLAMA_URL}/api/embeddings",
                json=request_data,
                timeout=30
            )
            try:
                if resp.status != 200:
                    error_text = await resp.text()
                    logger.error(f"Embedding generation failed: {error_text}")
                    # Return empty embedding as fallback
                    return np.zeros(384, dtype=np.float32).tobytes()
                
                result = await resp.json()
                if "embedding" not in result:
                    logger.error(f"Embedding not found in response: {result}")
                    return np.zeros(384, dtype=np.float32).tobytes()
                
                # Convert to numpy array and then to bytes
                embedding = np.array(result["embedding"], dtype=np.float32)
                return embedding.tobytes()
            finally:
                # Close the response
                await resp.release()
        finally:
            # Close the session
            await session.close()
    except Exception as e:
        logger.error(f"Error generating embeddings: {e}")
        # Return empty embedding as fallback
        return np.zeros(384, dtype=np.float32).tobytes()

async def search(query: str, limit: int = 5, text_only: bool = False) -> List[Dict[str, Any]]:
    """
    Search for documents using semantic search
    Returns list of document segments with scores
    """
    logger = logging.getLogger(__name__)
    
    try:
        # Prepare search terms - main terms and alternative forms
        search_terms = query.lower().split()
        # Include stemmed/simplified versions of terms
        expanded_terms = []
        for term in search_terms:
            # Simple stemming: remove common suffixes
            if len(term) > 5:
                if term.endswith('ing'):
                    expanded_terms.append(term[:-3])
                elif term.endswith('ed'):
                    expanded_terms.append(term[:-2])
                elif term.endswith('s'):
                    expanded_terms.append(term[:-1])
                elif term.endswith('ly'):
                    expanded_terms.append(term[:-2])
        
        # Create expanded query
        expanded_query = " ".join(search_terms + expanded_terms)
        logger.info(f"Searching for: {query} (expanded: {expanded_query})")
        
        if text_only:
            # Skip embedding generation and use text search only
            logger.info("Using text-only search")
            results = operations.search_segments(None, limit, text_query=expanded_query)
        else:
            # Generate query embedding
            query_embedding = await generate_embeddings(query)
            logger.info(f"Generated embedding for query: {len(query_embedding)} bytes")
            
            # Search database with both embedding and text query
            results = operations.search_segments(query_embedding, limit, text_query=expanded_query)
        
        # Log results count
        logger.info(f"Found {len(results)} results")
        
        return results
    except Exception as e:
        logger.error(f"Error searching documents: {e}")
        return []
