"""
Database connection pool for improved performance.
"""

import sqlite3
import threading
from contextlib import contextmanager
from queue import Empty, Full, Queue
from typing import Generator, Optional

from docvault import config


class ConnectionPool:
    """Thread-safe SQLite connection pool."""

    def __init__(self, max_connections: int = 10, timeout: int = 30):
        self.max_connections = max_connections
        self.timeout = timeout
        self._pool = Queue(maxsize=max_connections)
        self._created_connections = 0
        self._lock = threading.Lock()

    def _create_connection(self) -> sqlite3.Connection:
        """Create a new database connection."""
        import datetime

        # Register adapter for datetime objects
        sqlite3.register_adapter(datetime.datetime, lambda dt: dt.isoformat())

        conn = sqlite3.connect(config.DB_PATH, check_same_thread=False)
        conn.row_factory = sqlite3.Row

        # Enable WAL mode for better concurrency
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")  # 5 second timeout for locks
        conn.execute("PRAGMA synchronous=NORMAL")  # Better performance with WAL

        # Enable loading extensions if sqlite-vec is available
        try:
            import sqlite_vec

            conn.enable_load_extension(True)
            sqlite_vec.load(conn)
        except ImportError:
            pass
        except Exception:
            pass

        # Enable query logging for security auditing
        if getattr(config, "SQL_LOGGING", False):
            from docvault.db.sql_logging import enable_query_logging

            enable_query_logging(conn)

        return conn

    def get_connection(self) -> sqlite3.Connection:
        """Get a connection from the pool."""
        try:
            # Try to get an existing connection
            return self._pool.get_nowait()
        except Empty:
            # Create new connection if under limit
            with self._lock:
                if self._created_connections < self.max_connections:
                    conn = self._create_connection()
                    self._created_connections += 1
                    return conn

            # Wait for available connection
            try:
                return self._pool.get(timeout=self.timeout)
            except Empty:
                raise RuntimeError("Connection pool timeout")

    def return_connection(self, conn: sqlite3.Connection):
        """Return a connection to the pool."""
        try:
            self._pool.put_nowait(conn)
        except Full:
            # Pool is full, close the connection
            conn.close()
            with self._lock:
                self._created_connections -= 1

    @contextmanager
    def connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Context manager for getting and returning connections."""
        conn = self.get_connection()
        try:
            yield conn
        finally:
            self.return_connection(conn)

    def close_all(self):
        """Close all connections in the pool."""
        while not self._pool.empty():
            try:
                conn = self._pool.get_nowait()
                conn.close()
            except Empty:
                break
        self._created_connections = 0


# Global connection pool instance
_pool: Optional[ConnectionPool] = None
_pool_lock = threading.Lock()


def get_pool() -> ConnectionPool:
    """Get the global connection pool instance."""
    global _pool
    if _pool is None:
        with _pool_lock:
            if _pool is None:
                from docvault import config

                pool_size = getattr(config, "DB_POOL_SIZE", 5)
                _pool = ConnectionPool(max_connections=pool_size)
    return _pool


@contextmanager
def get_connection() -> Generator[sqlite3.Connection, None, None]:
    """Get a database connection from the pool."""
    pool = get_pool()
    with pool.connection() as conn:
        yield conn


def close_pool():
    """Close the global connection pool."""
    global _pool
    if _pool is not None:
        _pool.close_all()
        _pool = None
