"""
SQL query logging for security auditing.
"""

import logging
import sqlite3
import time
from functools import wraps
from typing import Any, Optional, Tuple

logger = logging.getLogger("docvault.sql")


class QueryLogger:
    """Log SQL queries for security auditing."""

    def __init__(self, enabled: bool = True, log_params: bool = False):
        self.enabled = enabled
        self.log_params = log_params

    def log_query(
        self,
        query: str,
        params: Optional[Tuple[Any, ...]] = None,
        duration: Optional[float] = None,
    ):
        """Log a SQL query."""
        if not self.enabled:
            return

        # Clean up query for logging
        clean_query = " ".join(query.split())

        log_data = {
            "query": (
                clean_query[:200] + "..." if len(clean_query) > 200 else clean_query
            ),
            "param_count": len(params) if params else 0,
        }

        if self.log_params and params:
            # Only log parameter types, not values (for security)
            log_data["param_types"] = [type(p).__name__ for p in params[:5]]
            if len(params) > 5:
                log_data["param_types"].append(f"...{len(params)-5} more")

        if duration is not None:
            log_data["duration_ms"] = round(duration * 1000, 2)

        logger.debug("SQL Query: %s", log_data)


# Global query logger instance
query_logger = QueryLogger()


def log_queries(cursor_class: type) -> type:
    """Decorator to add query logging to a cursor class."""

    original_execute = cursor_class.execute
    original_executemany = cursor_class.executemany

    @wraps(original_execute)
    def logged_execute(self, query, parameters=None):
        start_time = time.time()
        try:
            result = original_execute(self, query, parameters)
            duration = time.time() - start_time
            query_logger.log_query(query, parameters, duration)
            return result
        except Exception as e:
            duration = time.time() - start_time
            query_logger.log_query(query, parameters, duration)
            logger.error("SQL Error: %s", str(e))
            raise

    @wraps(original_executemany)
    def logged_executemany(self, query, seq_of_parameters):
        start_time = time.time()
        try:
            result = original_executemany(self, query, seq_of_parameters)
            duration = time.time() - start_time
            query_logger.log_query(
                query, seq_of_parameters[0] if seq_of_parameters else None, duration
            )
            return result
        except Exception as e:
            duration = time.time() - start_time
            query_logger.log_query(query, None, duration)
            logger.error("SQL Error in executemany: %s", str(e))
            raise

    cursor_class.execute = logged_execute
    cursor_class.executemany = logged_executemany

    return cursor_class


def enable_query_logging(connection: sqlite3.Connection):
    """Enable query logging for a connection."""
    # Set row factory to get both row objects and logging
    connection.row_factory = sqlite3.Row

    # Add query logging to cursor
    cursor_class = type(connection.cursor())
    log_queries(cursor_class)

    return connection


def configure_sql_logging(
    enabled: bool = True, log_params: bool = False, log_file: Optional[str] = None
):
    """Configure SQL query logging."""
    query_logger.enabled = enabled
    query_logger.log_params = log_params

    if log_file:
        handler = logging.FileHandler(log_file)
        handler.setFormatter(
            logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        )
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)
