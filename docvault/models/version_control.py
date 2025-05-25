"""Version control and update tracking for documents in DocVault."""

import difflib
import logging
import re
import sqlite3
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import requests
from bs4 import BeautifulSoup

from docvault import config

logger = logging.getLogger(__name__)


def extract_version_from_url(url: str) -> Optional[str]:
    """Extract version information from a URL.

    Args:
        url: The URL to analyze

    Returns:
        Version string if found, None otherwise
    """
    # Common version patterns in URLs
    version_patterns = [
        r"/v?(\d+\.\d+(?:\.\d+)?(?:\.\d+)?)",  # /v1.2.3 or /1.2.3
        r"/(\d+\.\d+(?:\.\d+)?(?:\.\d+)?)/",  # /1.2.3/
        r"version[=/](\d+\.\d+(?:\.\d+)?)",  # version=1.2.3 or version/1.2.3
        r"tag[=/]v?(\d+\.\d+(?:\.\d+)?)",  # tag=v1.2.3
    ]

    for pattern in version_patterns:
        match = re.search(pattern, url, re.IGNORECASE)
        if match:
            return match.group(1)

    return None


def check_for_updates(document_id: int) -> Dict[str, Any]:
    """Check if updates are available for a document.

    Args:
        document_id: ID of the document to check

    Returns:
        Dictionary with update information
    """
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row

    try:
        cursor = conn.cursor()

        # Get document information
        cursor.execute("SELECT * FROM documents WHERE id = ?", (document_id,))
        doc = cursor.fetchone()

        if not doc:
            return {"error": "Document not found"}

        # Get or create update check record
        cursor.execute(
            "SELECT * FROM update_checks WHERE document_id = ?", (document_id,)
        )
        check_record = cursor.fetchone()

        current_time = datetime.now()

        # Check if we need to perform an update check
        if check_record:
            last_checked = datetime.fromisoformat(check_record["last_checked"])
            update_frequency = doc.get("update_frequency", 7)  # days

            if current_time - last_checked < timedelta(days=update_frequency):
                return {
                    "document_id": document_id,
                    "needs_update": check_record["needs_update"],
                    "latest_available_version": check_record[
                        "latest_available_version"
                    ],
                    "last_checked": check_record["last_checked"],
                    "cached": True,
                }

        # Perform actual update check
        base_url = doc.get("base_url") or doc["url"]
        result = _perform_update_check(doc["url"], base_url)

        # Store/update the check result
        if check_record:
            cursor.execute(
                """
                UPDATE update_checks 
                SET last_checked = ?, latest_available_version = ?, 
                    needs_update = ?, check_error = ?
                WHERE document_id = ?
            """,
                (
                    current_time.isoformat(),
                    result.get("latest_version"),
                    result.get("needs_update", False),
                    result.get("error"),
                    document_id,
                ),
            )
        else:
            cursor.execute(
                """
                INSERT INTO update_checks 
                (document_id, last_checked, latest_available_version, 
                 needs_update, check_error)
                VALUES (?, ?, ?, ?, ?)
            """,
                (
                    document_id,
                    current_time.isoformat(),
                    result.get("latest_version"),
                    result.get("needs_update", False),
                    result.get("error"),
                ),
            )

        conn.commit()

        return {
            "document_id": document_id,
            "needs_update": result.get("needs_update", False),
            "latest_available_version": result.get("latest_version"),
            "current_version": doc.get("version"),
            "last_checked": current_time.isoformat(),
            "cached": False,
            "error": result.get("error"),
        }

    except Exception as e:
        logger.error(f"Error checking for updates: {e}")
        return {"error": str(e)}
    finally:
        conn.close()


def _perform_update_check(current_url: str, base_url: str) -> Dict[str, Any]:
    """Perform the actual update check by analyzing the website.

    Args:
        current_url: Current document URL
        base_url: Base URL for the documentation

    Returns:
        Dictionary with update check results
    """
    try:
        # Try to find version information in common locations

        # 1. Check for GitHub releases
        if "github.com" in base_url:
            return _check_github_releases(base_url)

        # 2. Check for documentation site patterns
        if any(
            pattern in base_url.lower()
            for pattern in ["docs.", "documentation.", "readthedocs"]
        ):
            return _check_docs_site_versions(base_url)

        # 3. Generic version detection
        return _check_generic_versions(current_url, base_url)

    except Exception as e:
        logger.warning(f"Update check failed for {current_url}: {e}")
        return {"error": str(e), "needs_update": False}


def _check_github_releases(base_url: str) -> Dict[str, Any]:
    """Check GitHub releases for latest version."""
    # Extract owner/repo from URL
    match = re.search(r"github\.com/([^/]+)/([^/]+)", base_url)
    if not match:
        return {"error": "Could not parse GitHub URL", "needs_update": False}

    owner, repo = match.groups()

    # Use GitHub API to get latest release
    api_url = f"https://api.github.com/repos/{owner}/{repo}/releases/latest"

    try:
        response = requests.get(api_url, timeout=10)
        if response.status_code == 200:
            release_data = response.json()
            latest_version = release_data.get("tag_name", "").lstrip("v")
            return {
                "latest_version": latest_version,
                "needs_update": True,  # Let the caller determine if it's actually newer
                "source": "github_releases",
            }
    except Exception as e:
        logger.warning(f"GitHub API check failed: {e}")

    return {"error": "Could not check GitHub releases", "needs_update": False}


def _check_docs_site_versions(base_url: str) -> Dict[str, Any]:
    """Check documentation site for version information."""
    try:
        response = requests.get(base_url, timeout=10)
        if response.status_code != 200:
            return {"error": f"HTTP {response.status_code}", "needs_update": False}

        soup = BeautifulSoup(response.content, "html.parser")

        # Look for version selectors or version information
        version_patterns = [
            "version-selector",
            "version-switch",
            "version-dropdown",
            "current-version",
        ]

        for pattern in version_patterns:
            elements = soup.find_all(attrs={"class": re.compile(pattern, re.I)})
            if elements:
                # Extract version numbers from these elements
                for element in elements:
                    text = element.get_text()
                    version_match = re.search(r"(\d+\.\d+(?:\.\d+)?)", text)
                    if version_match:
                        return {
                            "latest_version": version_match.group(1),
                            "needs_update": True,
                            "source": "docs_site",
                        }

        # Look in meta tags
        version_meta = soup.find("meta", attrs={"name": re.compile("version", re.I)})
        if version_meta and version_meta.get("content"):
            version_match = re.search(r"(\d+\.\d+(?:\.\d+)?)", version_meta["content"])
            if version_match:
                return {
                    "latest_version": version_match.group(1),
                    "needs_update": True,
                    "source": "meta_tag",
                }

    except Exception as e:
        logger.warning(f"Docs site check failed: {e}")

    return {"error": "No version information found", "needs_update": False}


def _check_generic_versions(current_url: str, base_url: str) -> Dict[str, Any]:
    """Generic version checking by analyzing URL patterns."""
    current_version = extract_version_from_url(current_url)

    if not current_version:
        return {"error": "No version found in URL", "needs_update": False}

    # Try to construct URLs for newer versions
    try:
        # Get the base pattern
        version_pattern = re.search(r"(\d+)\.(\d+)(?:\.(\d+))?", current_version)
        if not version_pattern:
            return {"error": "Invalid version format", "needs_update": False}

        major, minor, patch = version_pattern.groups()
        patch = patch or "0"

        # Try incrementing patch, minor, and major versions
        test_versions = [
            f"{major}.{minor}.{int(patch)+1}",
            f"{major}.{int(minor)+1}.0",
            f"{int(major)+1}.0.0",
        ]

        for test_version in test_versions:
            test_url = current_url.replace(current_version, test_version)

            try:
                response = requests.head(test_url, timeout=5)
                if response.status_code == 200:
                    return {
                        "latest_version": test_version,
                        "needs_update": True,
                        "source": "url_probing",
                    }
            except Exception:
                continue

    except Exception as e:
        logger.warning(f"Generic version check failed: {e}")

    return {"needs_update": False, "latest_version": current_version}


def compare_versions(doc_id: int, old_version: str, new_version: str) -> Dict[str, Any]:
    """Compare two versions of a document.

    Args:
        doc_id: Document ID
        old_version: Old version identifier
        new_version: New version identifier

    Returns:
        Dictionary with comparison results
    """
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row

    try:
        cursor = conn.cursor()

        # Get the two versions
        cursor.execute(
            """
            SELECT * FROM document_versions 
            WHERE base_document_id = ? AND version_string = ?
        """,
            (doc_id, old_version),
        )
        old_doc = cursor.fetchone()

        cursor.execute(
            """
            SELECT * FROM document_versions 
            WHERE base_document_id = ? AND version_string = ?
        """,
            (doc_id, new_version),
        )
        new_doc = cursor.fetchone()

        if not old_doc or not new_doc:
            return {"error": "One or both versions not found"}

        # Read the content of both versions
        try:
            with open(old_doc["markdown_path"], "r", encoding="utf-8") as f:
                old_content = f.read()
        except Exception:
            old_content = ""

        try:
            with open(new_doc["markdown_path"], "r", encoding="utf-8") as f:
                new_content = f.read()
        except Exception:
            new_content = ""

        # Generate diff
        diff = list(
            difflib.unified_diff(
                old_content.splitlines(keepends=True),
                new_content.splitlines(keepends=True),
                fromfile=f"Version {old_version}",
                tofile=f"Version {new_version}",
                n=3,
            )
        )

        # Calculate similarity
        similarity = difflib.SequenceMatcher(None, old_content, new_content).ratio()

        # Analyze changes
        added_lines = []
        removed_lines = []

        for line in diff:
            if line.startswith("+") and not line.startswith("+++"):
                added_lines.append(line[1:].strip())
            elif line.startswith("-") and not line.startswith("---"):
                removed_lines.append(line[1:].strip())

        # Store comparison in database
        cursor.execute(
            """
            INSERT OR REPLACE INTO version_comparisons
            (document_id, old_version_id, new_version_id, comparison_type,
             added_content, removed_content, similarity_score)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
            (
                doc_id,
                old_doc["id"],
                new_doc["id"],
                "content",
                "\n".join(added_lines[:50]),  # Limit stored content
                "\n".join(removed_lines[:50]),
                similarity,
            ),
        )

        conn.commit()

        return {
            "old_version": old_version,
            "new_version": new_version,
            "similarity_score": similarity,
            "added_lines_count": len(added_lines),
            "removed_lines_count": len(removed_lines),
            "diff": "".join(diff),
            "summary": _generate_change_summary(added_lines, removed_lines),
        }

    except Exception as e:
        logger.error(f"Error comparing versions: {e}")
        return {"error": str(e)}
    finally:
        conn.close()


def _generate_change_summary(added_lines: List[str], removed_lines: List[str]) -> str:
    """Generate a human-readable summary of changes."""
    summary_parts = []

    if added_lines:
        summary_parts.append(f"Added {len(added_lines)} lines")
    if removed_lines:
        summary_parts.append(f"Removed {len(removed_lines)} lines")

    # Look for specific types of changes
    added_functions = [
        line for line in added_lines if "def " in line or "function " in line
    ]
    removed_functions = [
        line for line in removed_lines if "def " in line or "function " in line
    ]

    if added_functions:
        summary_parts.append(f"Added {len(added_functions)} functions")
    if removed_functions:
        summary_parts.append(f"Removed {len(removed_functions)} functions")

    return (
        "; ".join(summary_parts) if summary_parts else "No significant changes detected"
    )


def get_documents_needing_updates() -> List[Dict[str, Any]]:
    """Get all documents that need updates.

    Returns:
        List of documents with available updates
    """
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row

    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT d.*, uc.latest_available_version, uc.last_checked
            FROM documents d
            JOIN update_checks uc ON d.id = uc.document_id
            WHERE uc.needs_update = 1 AND d.check_for_updates = 1
            ORDER BY uc.last_checked DESC
        """
        )

        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def get_version_history(document_id: int) -> List[Dict[str, Any]]:
    """Get version history for a document.

    Args:
        document_id: ID of the document

    Returns:
        List of versions ordered by creation date
    """
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row

    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT * FROM document_versions
            WHERE base_document_id = ?
            ORDER BY created_at DESC
        """,
            (document_id,),
        )

        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()
