# Contextual Processing Tips

## Issue: Stuck on Large Documents

When running `dv context process-all`, it may appear stuck on large documents like "Built-in Functions — Python 3.13.3 documentation" because:

1. This document has 79 segments to process
2. Each segment requires a call to your local Ollama model
3. With local models, each call can take 5-30 seconds depending on your hardware

## Workarounds

### 1. Process Smaller Documents First
Skip large documents and process smaller ones:

```bash
# Find smaller documents without context
sqlite3 ~/.docvault/docvault.db "SELECT d.id, d.title, COUNT(s.id) as segments FROM documents d JOIN document_segments s ON d.id = s.document_id LEFT JOIN (SELECT document_id FROM document_segments WHERE context_description IS NOT NULL GROUP BY document_id) ctx ON d.id = ctx.document_id WHERE ctx.document_id IS NULL GROUP BY d.id HAVING segments < 20 ORDER BY segments;"

# Process specific smaller documents
dv context process 211  # Handling Errors - FastAPI
dv context process 212  # Cookie Parameter Models
```

### 2. Process Documents One at a Time
Instead of `process-all`, process individual documents:

```bash
# Process a specific document
dv context process <document_id>

# You can monitor progress in the database
sqlite3 ~/.docvault/docvault.db "SELECT COUNT(*) as done, (SELECT COUNT(*) FROM document_segments WHERE document_id = 1) as total FROM document_segments WHERE document_id = 1 AND context_description IS NOT NULL;"
```

### 3. Skip Large Documents
Process all except the large ones:

```bash
# Process documents with less than 30 segments
for doc_id in $(sqlite3 ~/.docvault/docvault.db "SELECT d.id FROM documents d JOIN document_segments s ON d.id = s.document_id LEFT JOIN (SELECT document_id FROM document_segments WHERE context_description IS NOT NULL GROUP BY document_id) ctx ON d.id = ctx.document_id WHERE ctx.document_id IS NULL GROUP BY d.id HAVING COUNT(s.id) < 30"); do
    echo "Processing document $doc_id"
    dv context process $doc_id
done
```

### 4. Use Faster Models
If processing speed is important, consider:
- Using a smaller/faster Ollama model
- Using OpenAI API (much faster but requires API key and costs money)
- Using Claude Haiku via Anthropic API (fast and affordable)

### 5. Background Processing
Run processing in background with logging:

```bash
nohup dv context process-all > context_processing.log 2>&1 &
tail -f context_processing.log
```

## Performance Expectations

With local Ollama models:
- Small documents (< 10 segments): 1-5 minutes
- Medium documents (10-50 segments): 5-30 minutes  
- Large documents (50+ segments): 30+ minutes

Document 1 (Built-in Functions) with 79 segments could take 30-60 minutes to fully process.

## Checking Progress

Monitor processing progress:

```bash
# Overall status
dv context status

# Specific document progress
sqlite3 ~/.docvault/docvault.db "SELECT 'Processed:', COUNT(*), 'of', (SELECT COUNT(*) FROM document_segments WHERE document_id = 1), 'segments' FROM document_segments WHERE document_id = 1 AND context_description IS NOT NULL;"
```