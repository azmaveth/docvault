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
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{config.OLLAMA_URL}/api/embeddings",
                json=request_data,
                timeout=30
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"Embedding generation failed: {error_text}")
                    # Return empty embedding as fallback
                    return np.zeros(384, dtype=np.float32).tobytes()
                
                result = await response.json()
                if "embedding" not in result:
                    logger.error(f"Embedding not found in response: {result}")
                    return np.zeros(384, dtype=np.float32).tobytes()
                
                # Convert to numpy array and then to bytes
                embedding = np.array(result["embedding"], dtype=np.float32)
                return embedding.tobytes()
                
    except Exception as e:
        logger.error(f"Error generating embeddings: {e}")
        # Return empty embedding as fallback
        return np.zeros(384, dtype=np.float32).tobytes()

async def search(query: str, limit: int = 5) -> List[Dict[str, Any]]:
    """
    Search for documents using semantic search
    Returns list of document segments with scores
    """
    logger = logging.getLogger(__name__)
    
    try:
        # Generate query embedding
        query_embedding = await generate_embeddings(query)
        
        # Search database
        results = operations.search_segments(query_embedding, limit)
        
        return results
    except Exception as e:
        logger.error(f"Error searching documents: {e}")
        return []
