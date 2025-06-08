# Setting OpenAI API Key for Contextual Retrieval

Since the credential system is having issues, you can set the API key directly in the database.

## Method 1: Direct SQL (Recommended)

```bash
# Replace 'sk-your-actual-api-key' with your real OpenAI API key
sqlite3 ~/.docvault/docvault.db "INSERT OR REPLACE INTO config (key, value) VALUES ('openai_api_key', 'sk-your-actual-api-key');"
```

## Method 2: Fix Credential System

If you want to fix the credential system, try:

```bash
# Backup existing credential files
mv ~/.docvault/.credentials.enc ~/.docvault/.credentials.enc.backup
mv ~/.docvault/.credentials.key ~/.docvault/.credentials.key.backup

# Try setting credential again (will create new key)
dv credentials set openai_api_key --category api_keys
```

## Method 3: Configure to Use OpenAI

After setting the API key, configure DocVault to use OpenAI:

```bash
# Configure to use OpenAI
dv context config --provider openai --model gpt-3.5-turbo

# Verify configuration
dv context status
```

## Verify API Key is Set

```bash
# Check if API key is stored (will show partial key)
sqlite3 ~/.docvault/docvault.db "SELECT key, SUBSTR(value, 1, 7) || '...' as partial_value FROM config WHERE key = 'openai_api_key';"
```

## Benefits of OpenAI over Ollama

- **Speed**: 10-100x faster processing
- **Quality**: Generally better context descriptions
- **No local resources**: Doesn't use your CPU/GPU
- **Cost**: About $0.01-0.10 per document depending on size

## Processing with OpenAI

Once configured:

```bash
# Process a single document
dv context process 211

# Process all (much faster than Ollama)
dv context process-all
```

With OpenAI, processing all 200+ documents might take 10-30 minutes instead of many hours with Ollama.