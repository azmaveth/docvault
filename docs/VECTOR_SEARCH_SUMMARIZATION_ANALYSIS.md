# Vector Search for Enhanced Document Summarization in DocVault

## Current State Analysis

### 1. Existing Infrastructure

DocVault already has a robust vector search infrastructure in place:

#### Vector Storage
- **Embeddings are generated** for each document segment during scraping (see `scraper.py:405`)
- **Embeddings are stored** in the `document_segments` table as BLOB data
- **Vector index exists** via sqlite-vec extension: `document_segments_vec` table
- **Embedding model**: Uses Ollama with configurable model (default from config)
- **Embedding dimensions**: 384 dimensions (float32) as seen in `embeddings.py:34`

#### Current Vector Search Usage
- **Search functionality**: Already implements semantic search in `embeddings.py:56-150`
- **Hybrid search**: Combines vector similarity with text matching
- **Score calculation**: Converts cosine distance to similarity score (0-1 range)
- **Fallback mechanism**: Falls back to text search if vector search fails

### 2. Current Summarization Approach

The current summarization in `summarizer.py` is pattern-based:
- Extracts functions, classes, parameters using regex patterns
- Identifies code examples and key concepts
- Creates structured summaries with overview, functions, classes, examples
- **Limitation**: Processes entire document linearly without considering relevance

## Proposed Enhancement: Vector-Based Summarization

### 1. Concept

Instead of processing the entire document linearly, use vector search to find the most relevant segments based on:
- **Query-based relevance**: When summarizing for a specific topic/query
- **Importance scoring**: Find segments most similar to key concept embeddings
- **Diversity sampling**: Select segments that cover different aspects of the documentation

### 2. Implementation Strategy

#### A. Query-Focused Summarization

```python
async def generate_query_focused_summary(
    document_id: int,
    query: str,
    max_segments: int = 10
) -> Dict[str, Any]:
    """Generate a summary focused on specific query terms"""
    
    # 1. Generate embedding for the query
    query_embedding = await generate_embeddings(query)
    
    # 2. Search for most relevant segments
    relevant_segments = search_segments(
        embedding=query_embedding,
        limit=max_segments,
        doc_filter={'document_id': document_id},
        min_score=0.7  # Higher threshold for relevance
    )
    
    # 3. Extract key information from relevant segments
    summary = {
        'query': query,
        'relevant_sections': [],
        'code_examples': [],
        'key_points': []
    }
    
    for segment in relevant_segments:
        # Process each relevant segment
        # Extract functions, examples, key points
        pass
    
    return summary
```

#### B. Concept-Based Summarization

```python
async def generate_concept_based_summary(
    document_id: int,
    concepts: List[str] = None
) -> Dict[str, Any]:
    """Generate summary based on important concepts"""
    
    if not concepts:
        # Default important concepts for documentation
        concepts = [
            "installation setup configuration",
            "main functions methods API",
            "examples usage code snippets",
            "error handling exceptions",
            "parameters arguments options",
            "return values outputs results"
        ]
    
    all_segments = []
    
    # Find segments for each concept
    for concept in concepts:
        concept_embedding = await generate_embeddings(concept)
        segments = search_segments(
            embedding=concept_embedding,
            limit=3,  # Top 3 for each concept
            doc_filter={'document_id': document_id},
            min_score=0.6
        )
        all_segments.extend(segments)
    
    # Deduplicate and process segments
    # ... rest of implementation
```

#### C. Multi-Stage Summarization

```python
async def generate_multi_stage_summary(
    document_id: int,
    stages: List[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Generate summary using multiple search stages"""
    
    if not stages:
        stages = [
            {'query': 'overview introduction getting started', 'weight': 1.0},
            {'query': 'main functions classes methods API', 'weight': 0.8},
            {'query': 'examples code usage', 'weight': 0.9},
            {'query': 'configuration options parameters', 'weight': 0.7},
        ]
    
    weighted_segments = {}
    
    for stage in stages:
        embedding = await generate_embeddings(stage['query'])
        segments = search_segments(
            embedding=embedding,
            limit=5,
            doc_filter={'document_id': document_id}
        )
        
        for segment in segments:
            seg_id = segment['id']
            if seg_id not in weighted_segments:
                weighted_segments[seg_id] = {
                    'segment': segment,
                    'total_score': 0
                }
            weighted_segments[seg_id]['total_score'] += (
                segment['score'] * stage['weight']
            )
    
    # Sort by weighted score and process top segments
    # ... rest of implementation
```

### 3. Integration Points

#### A. Enhance MCP Server's read_document

Modify the `read_document` function in `mcp/server.py` to support vector-based summarization:

```python
@server.tool()
async def read_document(
    document_id: int, 
    format: str = "markdown",
    mode: str = "summary",
    query: Optional[str] = None,  # NEW
    summary_type: str = "standard",  # NEW: standard, query_focused, concept_based
    chunk_size: int = 5000,
    chunk_number: int = 1
) -> types.CallToolResult:
    """Enhanced read_document with vector-based summarization options"""
    
    if mode == "summary":
        if summary_type == "query_focused" and query:
            # Use vector search to find relevant segments
            summary = await generate_query_focused_summary(document_id, query)
        elif summary_type == "concept_based":
            # Use predefined concepts to find important segments
            summary = await generate_concept_based_summary(document_id)
        else:
            # Fall back to existing pattern-based summarization
            summarizer = DocumentSummarizer()
            summary = summarizer.summarize(content, max_items=15)
```

#### B. Add New MCP Tool for Smart Summarization

```python
@server.tool()
async def summarize_document(
    document_id: int,
    focus: Optional[str] = None,
    concepts: Optional[List[str]] = None,
    max_length: int = 2000
) -> types.CallToolResult:
    """Generate intelligent summaries using vector search
    
    Args:
        document_id: Document to summarize
        focus: Optional query to focus the summary on
        concepts: Optional list of concepts to extract
        max_length: Maximum summary length
    """
    # Implementation using vector search
```

### 4. Benefits

1. **Relevance**: Summaries focus on what users are looking for
2. **Efficiency**: Only processes relevant segments instead of entire document
3. **Flexibility**: Can generate different summaries for different use cases
4. **Quality**: Leverages semantic understanding via embeddings
5. **Scalability**: Works well with large documents

### 5. Implementation Considerations

#### Performance
- Vector search is already optimized with sqlite-vec
- Can cache frequently requested summaries
- Parallel segment processing for multi-concept summaries

#### Fallback Strategy
- If vector search fails, fall back to pattern-based summarization
- Hybrid approach: combine vector-based and pattern-based results

#### Quality Metrics
- Track summary relevance scores
- Monitor user feedback on summary quality
- A/B test different summarization strategies

### 6. Next Steps

1. **Prototype Implementation**
   - Start with query-focused summarization
   - Test with existing documents
   - Measure performance and quality

2. **Enhanced Segment Storage**
   - Consider storing segment importance scores
   - Add segment type classifications (overview, example, API, etc.)

3. **UI/CLI Integration**
   - Add `--query` parameter to `dv read` command
   - Support different summary types in CLI

4. **Evaluation Framework**
   - Create test suite for summary quality
   - Benchmark against current approach

## Code Examples

### Example 1: Query-Focused Summary

```python
# User wants to know about error handling in a library
result = await read_document(
    document_id=5,
    mode="summary",
    summary_type="query_focused",
    query="error handling exceptions try catch"
)
# Returns summary with segments specifically about error handling
```

### Example 2: Concept-Based Summary

```python
# Generate a summary covering specific concepts
result = await summarize_document(
    document_id=10,
    concepts=["authentication", "authorization", "security"],
    max_length=3000
)
# Returns summary focused on security-related segments
```

### Example 3: Multi-Stage Summary

```python
# Generate comprehensive summary with weighted importance
summary = await generate_multi_stage_summary(
    document_id=15,
    stages=[
        {'query': 'getting started installation', 'weight': 1.0},
        {'query': 'core features functionality', 'weight': 0.9},
        {'query': 'advanced configuration', 'weight': 0.6}
    ]
)
# Returns balanced summary covering different aspects
```

## Conclusion

DocVault already has all the infrastructure needed for vector-based summarization:
- Embeddings are generated and stored for all segments
- Vector search is functional and tested
- The summarizer just needs to leverage these capabilities

The proposed enhancements would significantly improve summary quality and relevance while maintaining backward compatibility with the existing system.