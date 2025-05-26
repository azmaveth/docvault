"""
Document caching and freshness management.

This module handles document staleness tracking, update checks,
and smart caching strategies.
"""

import logging
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Dict, List, Optional, Tuple

import aiohttp

from docvault.db.operations import get_connection


class StalenessStatus(Enum):
    """Document staleness levels."""

    FRESH = "fresh"
    STALE = "stale"
    OUTDATED = "outdated"


class CacheConfig:
    """Caching configuration."""

    def __init__(self):
        # Default staleness thresholds
        self.fresh_days = 7
        self.stale_days = 30
        self.auto_check = False
        self.check_on_read = True

    @property
    def fresh_threshold(self) -> timedelta:
        """Time before a document is considered stale."""
        return timedelta(days=self.fresh_days)

    @property
    def stale_threshold(self) -> timedelta:
        """Time before a document is considered outdated."""
        return timedelta(days=self.stale_days)


class CacheManager:
    """Manages document caching and freshness."""

    def __init__(self, config: Optional[CacheConfig] = None):
        self.config = config or CacheConfig()
        self.logger = logging.getLogger(__name__)

    def calculate_staleness(self, last_checked: datetime) -> StalenessStatus:
        """Calculate staleness status based on last check time."""
        if not last_checked:
            return StalenessStatus.OUTDATED

        # Ensure timezone awareness
        if last_checked.tzinfo is None:
            last_checked = last_checked.replace(tzinfo=timezone.utc)

        now = datetime.now(timezone.utc)
        age = now - last_checked

        if age < self.config.fresh_threshold:
            return StalenessStatus.FRESH
        elif age < self.config.stale_threshold:
            return StalenessStatus.STALE
        else:
            return StalenessStatus.OUTDATED

    def update_staleness_status(self, document_id: int) -> StalenessStatus:
        """Update and return the staleness status for a document."""
        with get_connection() as conn:
            cursor = conn.cursor()

            # Get document info
            cursor.execute(
                """
                SELECT last_checked, is_pinned 
                FROM documents 
                WHERE id = ?
            """,
                (document_id,),
            )

            row = cursor.fetchone()
            if not row:
                raise ValueError(f"Document {document_id} not found")

            last_checked, is_pinned = row

            # Pinned documents are always fresh
            if is_pinned:
                return StalenessStatus.FRESH

            # Parse datetime if it's a string
            if isinstance(last_checked, str):
                last_checked = datetime.fromisoformat(
                    last_checked.replace("Z", "+00:00")
                )

            status = self.calculate_staleness(last_checked)

            # Update status in database
            cursor.execute(
                """
                UPDATE documents 
                SET staleness_status = ? 
                WHERE id = ?
            """,
                (status.value, document_id),
            )

            conn.commit()
            return status

    def get_stale_documents(
        self, status: Optional[StalenessStatus] = None, limit: Optional[int] = None
    ) -> List[Dict]:
        """Get documents by staleness status."""
        with get_connection() as conn:
            cursor = conn.cursor()

            query = """
                SELECT id, url, title, version, last_checked, 
                       staleness_status, is_pinned
                FROM documents 
                WHERE is_pinned = FALSE
            """
            params = []

            if status:
                query += " AND staleness_status = ?"
                params.append(status.value)
            else:
                # Get all non-fresh documents
                query += " AND staleness_status IN ('stale', 'outdated')"

            query += " ORDER BY last_checked ASC"

            if limit:
                query += " LIMIT ?"
                params.append(limit)

            cursor.execute(query, params)

            documents = []
            for row in cursor.fetchall():
                documents.append(
                    {
                        "id": row[0],
                        "url": row[1],
                        "title": row[2],
                        "version": row[3],
                        "last_checked": row[4],
                        "staleness_status": row[5],
                        "is_pinned": row[6],
                    }
                )

            return documents

    async def check_for_updates(self, document_id: int) -> Tuple[bool, Optional[str]]:
        """
        Check if a document has updates available.

        Returns:
            (has_updates, reason): Whether updates are available and why
        """
        with get_connection() as conn:
            cursor = conn.cursor()

            # Get document info
            cursor.execute(
                """
                SELECT url, etag, content_hash, server_last_modified 
                FROM documents 
                WHERE id = ?
            """,
                (document_id,),
            )

            row = cursor.fetchone()
            if not row:
                return False, "Document not found"

            url, etag, content_hash, last_modified = row

            try:
                # Make HEAD request to check for changes
                async with aiohttp.ClientSession() as session:
                    headers = {}
                    if etag:
                        headers["If-None-Match"] = etag
                    if last_modified:
                        headers["If-Modified-Since"] = last_modified

                    async with session.head(
                        url, headers=headers, timeout=10
                    ) as response:
                        # 304 Not Modified means no updates
                        if response.status == 304:
                            self._mark_as_checked(document_id)
                            return False, "No changes detected (304 Not Modified)"

                        # Check new etag
                        new_etag = response.headers.get("ETag")
                        if new_etag and new_etag != etag:
                            return True, f"ETag changed: {etag} → {new_etag}"

                        # Check last modified
                        new_modified = response.headers.get("Last-Modified")
                        if new_modified and new_modified != last_modified:
                            return (
                                True,
                                f"Last-Modified changed: {last_modified} → {new_modified}",
                            )

                        # If no caching headers, we'll need to fetch and compare content
                        if response.status == 200 and not new_etag and not new_modified:
                            # For now, assume it might have changed
                            return (
                                True,
                                "No caching headers available, content may have changed",
                            )

                        self._mark_as_checked(document_id)
                        return False, "No changes detected"

            except aiohttp.ClientError as e:
                self.logger.warning(
                    f"Failed to check updates for document {document_id}: {e}"
                )
                return False, f"Check failed: {str(e)}"

    def _mark_as_checked(self, document_id: int):
        """Mark a document as recently checked."""
        with get_connection() as conn:
            cursor = conn.cursor()

            now = datetime.now(timezone.utc)
            cursor.execute(
                """
                UPDATE documents 
                SET last_checked = ?, staleness_status = ? 
                WHERE id = ?
            """,
                (now.isoformat(), StalenessStatus.FRESH.value, document_id),
            )

            conn.commit()

    def mark_as_updated(
        self,
        document_id: int,
        etag: Optional[str] = None,
        last_modified: Optional[str] = None,
        content_hash: Optional[str] = None,
    ):
        """Mark a document as updated with new metadata."""
        with get_connection() as conn:
            cursor = conn.cursor()

            now = datetime.now(timezone.utc)

            # Build update query dynamically
            updates = ["last_checked = ?", "staleness_status = ?", "updated_at = ?"]
            params = [now.isoformat(), StalenessStatus.FRESH.value, now.isoformat()]

            if etag is not None:
                updates.append("etag = ?")
                params.append(etag)

            if last_modified is not None:
                updates.append("server_last_modified = ?")
                params.append(last_modified)

            if content_hash is not None:
                updates.append("content_hash = ?")
                params.append(content_hash)

            params.append(document_id)

            query = f"UPDATE documents SET {', '.join(updates)} WHERE id = ?"
            cursor.execute(query, params)

            conn.commit()

    def pin_document(self, document_id: int, pinned: bool = True):
        """Pin or unpin a document to prevent staleness."""
        with get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                UPDATE documents 
                SET is_pinned = ? 
                WHERE id = ?
            """,
                (pinned, document_id),
            )

            conn.commit()

    def get_cache_statistics(self) -> Dict:
        """Get cache statistics."""
        with get_connection() as conn:
            cursor = conn.cursor()

            # Count documents by staleness
            cursor.execute(
                """
                SELECT staleness_status, COUNT(*) 
                FROM documents 
                WHERE is_pinned = FALSE 
                GROUP BY staleness_status
            """
            )

            status_counts = dict(cursor.fetchall())

            # Count pinned documents
            cursor.execute("SELECT COUNT(*) FROM documents WHERE is_pinned = TRUE")
            pinned_count = cursor.fetchone()[0]

            # Get average age
            cursor.execute(
                """
                SELECT AVG(julianday('now') - julianday(last_checked)) 
                FROM documents 
                WHERE last_checked IS NOT NULL
            """
            )

            avg_age_days = cursor.fetchone()[0] or 0

            return {
                "total_documents": sum(status_counts.values()) + pinned_count,
                "fresh": status_counts.get("fresh", 0),
                "stale": status_counts.get("stale", 0),
                "outdated": status_counts.get("outdated", 0),
                "pinned": pinned_count,
                "average_age_days": round(avg_age_days, 1),
                "thresholds": {
                    "fresh_days": self.config.fresh_days,
                    "stale_days": self.config.stale_days,
                },
            }


# Global cache manager instance
_cache_manager = None


def get_cache_manager() -> CacheManager:
    """Get or create the global cache manager instance."""
    global _cache_manager
    if _cache_manager is None:
        _cache_manager = CacheManager()
    return _cache_manager
