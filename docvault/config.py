import os
import pathlib

try:
    from dotenv import load_dotenv
except ImportError:

    def load_dotenv(*args, **kwargs):
        return


# Default paths
HOME_DIR = pathlib.Path.home()
DEFAULT_BASE_DIR = HOME_DIR / ".docvault"
DEFAULT_BASE_DIR.mkdir(exist_ok=True)
CONFIG_DIR = DEFAULT_BASE_DIR  # Alias for compatibility

# Load .env file if it exists (first check current directory, then ~/.docvault)
load_dotenv()
# Look for .env file in the user's docvault directory
docvault_env = DEFAULT_BASE_DIR / ".env"
if docvault_env.exists():
    load_dotenv(docvault_env)

# Also check for .env in the package directory (useful for development)
package_dir = pathlib.Path(__file__).parent.parent
if (package_dir / ".env").exists():
    load_dotenv(package_dir / ".env")

# Database
DB_PATH = os.getenv("DOCVAULT_DB_PATH", str(DEFAULT_BASE_DIR / "docvault.db"))
USE_CONNECTION_POOL = os.getenv("USE_CONNECTION_POOL", "false").lower() == "true"
DB_POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "5"))

# API Keys
BRAVE_API_KEY = os.getenv("BRAVE_API_KEY", "")
# GitHub
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")

# Embedding
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "nomic-embed-text")

# Storage
STORAGE_PATH = pathlib.Path(
    os.getenv("STORAGE_PATH", str(DEFAULT_BASE_DIR / "storage"))
)
HTML_PATH = STORAGE_PATH / "html"
MARKDOWN_PATH = STORAGE_PATH / "markdown"

# Logging
LOG_DIR = pathlib.Path(os.getenv("LOG_DIR", str(DEFAULT_BASE_DIR / "logs")))
LOG_FILE = LOG_DIR / os.getenv("LOG_FILE", "docvault.log")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Server
# For stdio/AI mode (legacy)
SERVER_HOST = os.getenv("SERVER_HOST", "127.0.0.1")
SERVER_PORT = int(os.getenv("SERVER_PORT", "8000"))

# For SSE/web mode (Uvicorn/FastMCP)
HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "8000"))
SERVER_WORKERS = int(os.getenv("SERVER_WORKERS", "4"))

# Ensure directories exist
STORAGE_PATH.mkdir(parents=True, exist_ok=True)
HTML_PATH.mkdir(parents=True, exist_ok=True)
MARKDOWN_PATH.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)

# Security Configuration
# URL validation settings
URL_ALLOWED_DOMAINS = os.getenv("URL_ALLOWED_DOMAINS", "").strip()
URL_ALLOWED_DOMAINS = (
    [d.strip() for d in URL_ALLOWED_DOMAINS.split(",") if d.strip()]
    if URL_ALLOWED_DOMAINS
    else None
)

URL_BLOCKED_DOMAINS = os.getenv("URL_BLOCKED_DOMAINS", "").strip()
URL_BLOCKED_DOMAINS = (
    [d.strip() for d in URL_BLOCKED_DOMAINS.split(",") if d.strip()]
    if URL_BLOCKED_DOMAINS
    else None
)

# Request settings
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "30"))  # seconds
MAX_RESPONSE_SIZE = int(
    os.getenv("MAX_RESPONSE_SIZE", str(10 * 1024 * 1024))
)  # 10MB default
MAX_SCRAPING_DEPTH = int(
    os.getenv("MAX_SCRAPING_DEPTH", "3")
)  # More conservative default
MAX_PAGES_PER_DOMAIN = int(os.getenv("MAX_PAGES_PER_DOMAIN", "50"))  # Reduced from 100

# Proxy settings
HTTP_PROXY = os.getenv("HTTP_PROXY", "")
HTTPS_PROXY = os.getenv("HTTPS_PROXY", "")
NO_PROXY = os.getenv("NO_PROXY", "")

# Rate limiting settings - more conservative defaults
RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "30"))  # Reduced from 60
RATE_LIMIT_PER_HOUR = int(os.getenv("RATE_LIMIT_PER_HOUR", "500"))  # Reduced from 1000
RATE_LIMIT_BURST_SIZE = int(os.getenv("RATE_LIMIT_BURST_SIZE", "5"))  # Reduced from 10
GLOBAL_RATE_LIMIT_PER_MINUTE = int(
    os.getenv("GLOBAL_RATE_LIMIT_PER_MINUTE", "150")
)  # Reduced from 300
GLOBAL_RATE_LIMIT_PER_HOUR = int(
    os.getenv("GLOBAL_RATE_LIMIT_PER_HOUR", "2500")
)  # Reduced from 5000

# Resource limits - more conservative
MAX_CONCURRENT_REQUESTS = int(
    os.getenv("MAX_CONCURRENT_REQUESTS", "5")
)  # Reduced from 10
MAX_MEMORY_MB = int(os.getenv("MAX_MEMORY_MB", "1024"))
MAX_PROCESSING_TIME_SECONDS = int(os.getenv("MAX_PROCESSING_TIME_SECONDS", "300"))


# Helper function for getting config values from database
def get(key: str, default: str | None = None) -> str | None:
    """Get a configuration value from the database.
    
    Args:
        key: The configuration key
        default: Default value if key not found
        
    Returns:
        The configuration value or default
    """
    try:
        from docvault.db import operations
        
        with operations.get_connection() as conn:
            cursor = conn.execute(
                "SELECT value FROM config WHERE key = ?",
                (key,)
            )
            result = cursor.fetchone()
            return result["value"] if result else default
    except Exception:
        return default
