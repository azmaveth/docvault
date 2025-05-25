"""
Smart depth detection for documentation scraping.

This module provides intelligent depth control for the scraper,
analyzing URLs and content to determine optimal crawling depth.
"""

import re
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse


class DepthStrategy(Enum):
    """Available depth control strategies"""

    AUTO = "auto"  # Smart detection based on patterns and content
    CONSERVATIVE = "conservative"  # Only follow obvious documentation links
    AGGRESSIVE = "aggressive"  # Follow more links with filtering
    MANUAL = "manual"  # Use fixed depth (current behavior)


@dataclass
class LinkAnalysis:
    """Analysis result for a link"""

    url: str
    should_follow: bool
    priority: float  # 0.0 to 1.0
    reason: str
    suggested_depth: Optional[int] = None


class DepthAnalyzer:
    """Analyzes URLs and content to make intelligent depth decisions"""

    def __init__(self, strategy: DepthStrategy = DepthStrategy.AUTO):
        self.strategy = strategy

        # Documentation URL patterns (positive indicators)
        self.doc_patterns = [
            r"/docs?/",
            r"/api/",
            r"/reference/",
            r"/guide/",
            r"/manual/",
            r"/tutorial/",
            r"/documentation/",
            r"/resources/docs/",
            r"/developer/",
            r"/dev-?guide/",
            r"/learn/",
            r"/getting-?started/",
        ]

        # Non-documentation patterns (negative indicators)
        self.non_doc_patterns = [
            r"/blog/",
            r"/news/",
            r"/about/",
            r"/careers?/",
            r"/jobs?/",
            r"/pricing/",
            r"/contact/",
            r"/support/",
            r"/terms/",
            r"/privacy/",
            r"/legal/",
            r"/press/",
            r"/events?/",
            r"/community/",
            r"/forum/",
            r"/download/",
            r"/signin/",
            r"/login/",
            r"/register/",
            r"/account/",
        ]

        # File extensions to avoid
        self.skip_extensions = {
            ".pdf",
            ".zip",
            ".tar",
            ".gz",
            ".exe",
            ".dmg",
            ".pkg",
            ".jpg",
            ".jpeg",
            ".png",
            ".gif",
            ".svg",
            ".ico",
            ".mp3",
            ".mp4",
            ".avi",
            ".mov",
            ".doc",
            ".docx",
            ".xls",
            ".xlsx",
            ".ppt",
            ".pptx",
        }

        # Version patterns
        self.version_patterns = [
            r"/v\d+(?:\.\d+)*/",  # /v1/, /v2.0/, /v3.1.4/
            r"/\d+(?:\.\d+)*/",  # /1.0/, /2.5/
            r"/stable/",
            r"/latest/",
            r"/dev/",
            r"/master/",
        ]

        # Documentation content indicators
        self.doc_content_indicators = [
            r"<code[^>]*>",
            r"<pre[^>]*>",
            r"```[\w]*\n",
            r"class\s+\w+",
            r"function\s+\w+",
            r"def\s+\w+",
            r"@param\s+",
            r":param\s+",
            r"@returns?\s+",
            r":returns?:",
            r"import\s+",
            r"require\s*\(",
            r"#include\s*<",
        ]

    def analyze_url(self, url: str, base_url: str, current_depth: int) -> LinkAnalysis:
        """
        Analyze a URL to determine if it should be followed.

        Args:
            url: The URL to analyze
            base_url: The base URL being scraped
            current_depth: Current recursion depth

        Returns:
            LinkAnalysis with recommendation
        """
        # Parse URLs
        parsed_url = urlparse(url)
        parsed_base = urlparse(base_url)

        # Never follow external links
        if parsed_url.netloc != parsed_base.netloc:
            return LinkAnalysis(
                url=url, should_follow=False, priority=0.0, reason="External domain"
            )

        # Check file extension
        path_lower = parsed_url.path.lower()
        for ext in self.skip_extensions:
            if path_lower.endswith(ext):
                return LinkAnalysis(
                    url=url,
                    should_follow=False,
                    priority=0.0,
                    reason=f"Non-documentation file type: {ext}",
                )

        # Apply strategy-specific logic
        if self.strategy == DepthStrategy.MANUAL:
            # Current behavior - follow everything up to depth limit
            return LinkAnalysis(
                url=url,
                should_follow=current_depth > 0,
                priority=0.5,
                reason="Manual depth control",
            )

        # Analyze URL patterns
        doc_score = self._score_url_patterns(parsed_url.path)

        # Check if we're staying within the same version
        version_consistent = self._check_version_consistency(
            parsed_base.path, parsed_url.path
        )

        # Calculate relative depth
        base_parts = [p for p in parsed_base.path.split("/") if p]
        url_parts = [p for p in parsed_url.path.split("/") if p]
        # Only consider it a child if base has a path
        is_child = (
            len(base_parts) > 0
            and len(url_parts) > len(base_parts)
            and url_parts[: len(base_parts)] == base_parts
        )

        # Make decision based on strategy
        if self.strategy == DepthStrategy.CONSERVATIVE:
            # Only follow high-confidence documentation links
            should_follow = doc_score > 0.7 and version_consistent
            priority = doc_score if should_follow else 0.0
            reason = (
                "High-confidence documentation link"
                if should_follow
                else "Not clearly documentation"
            )

        elif self.strategy == DepthStrategy.AGGRESSIVE:
            # Follow unless clearly non-documentation
            should_follow = doc_score > -0.5 and current_depth > 0
            priority = max(0.1, (doc_score + 1) / 2)  # Normalize to 0.1-1.0
            reason = "Acceptable link" if should_follow else "Clearly non-documentation"

        else:  # AUTO strategy
            # Smart decision based on multiple factors
            if doc_score > 0.5:
                # Likely documentation
                should_follow = True
                priority = min(1.0, doc_score + (0.2 if is_child else 0))
                reason = "Documentation URL pattern"
            elif doc_score < -0.5:
                # Likely not documentation
                should_follow = False
                priority = 0.0
                reason = "Non-documentation URL pattern"
            else:
                # Uncertain - use additional heuristics
                if is_child and version_consistent:
                    should_follow = True
                    priority = 0.5
                    reason = "Child page in same section"
                else:
                    should_follow = (
                        current_depth > 1
                    )  # Be more selective at deeper levels
                    priority = 0.3
                    reason = "Uncertain - limited depth"

        # Suggest adaptive depth based on content
        suggested_depth = None
        if should_follow:
            if doc_score > 0.8:
                suggested_depth = 3  # Go deeper for clear documentation
            elif doc_score > 0.5:
                suggested_depth = 2
            else:
                suggested_depth = 1

        return LinkAnalysis(
            url=url,
            should_follow=should_follow,
            priority=priority,
            reason=reason,
            suggested_depth=suggested_depth,
        )

    def _score_url_patterns(self, path: str) -> float:
        """
        Score a URL path based on documentation patterns.

        Returns:
            Score from -1.0 (definitely not docs) to 1.0 (definitely docs)
        """
        path_lower = path.lower()
        score = 0.0

        # Check positive patterns
        for pattern in self.doc_patterns:
            if re.search(pattern, path_lower):
                score += 0.3

        # Check negative patterns
        for pattern in self.non_doc_patterns:
            if re.search(pattern, path_lower):
                score -= 0.5

        # Bonus for specific documentation indicators
        if "/api/" in path_lower and any(
            x in path_lower for x in ["reference", "docs", "v1", "v2"]
        ):
            score += 0.3

        # Penalize certain path structures
        if path_lower.count("/") > 6:  # Very deep paths often not documentation
            score -= 0.2

        return max(-1.0, min(1.0, score))

    def _check_version_consistency(self, base_path: str, url_path: str) -> bool:
        """Check if URL maintains version consistency with base"""
        base_version = self._extract_version(base_path)
        url_version = self._extract_version(url_path)

        # If no version in base, allow any
        if not base_version:
            return True

        # If version in base but not in URL, it's OK (inherits)
        if base_version and not url_version:
            return True

        # Both have versions - they should match
        return base_version == url_version

    def _extract_version(self, path: str) -> Optional[str]:
        """Extract version identifier from path"""
        for pattern in self.version_patterns:
            match = re.search(pattern, path)
            if match:
                return match.group(0)
        return None

    def analyze_content(self, content: str) -> Dict[str, float]:
        """
        Analyze page content to determine documentation quality.

        Args:
            content: HTML or text content of the page

        Returns:
            Dictionary with various scores
        """
        scores = {
            "code_density": 0.0,
            "api_indicators": 0.0,
            "navigation_ratio": 0.0,
            "overall": 0.0,
        }

        if not content:
            return scores

        content_lower = content.lower()
        content_length = len(content)

        # Calculate code density
        code_matches = 0
        for pattern in self.doc_content_indicators:
            matches = len(re.findall(pattern, content, re.IGNORECASE))
            code_matches += matches

        scores["code_density"] = min(1.0, code_matches / max(1, content_length / 1000))

        # Check for API documentation indicators
        api_keywords = [
            "parameter",
            "returns",
            "throws",
            "exception",
            "example",
            "usage",
            "syntax",
            "arguments",
            "options",
            "configuration",
        ]
        api_count = sum(1 for keyword in api_keywords if keyword in content_lower)
        scores["api_indicators"] = min(1.0, api_count / 5)

        # Calculate navigation ratio (too many links might indicate index page)
        link_count = len(re.findall(r"<a\s+[^>]*href=", content, re.IGNORECASE))
        text_length = len(re.sub(r"<[^>]+>", "", content))  # Rough text extraction
        if text_length > 0:
            scores["navigation_ratio"] = 1.0 - min(1.0, (link_count * 50) / text_length)

        # Overall score
        scores["overall"] = (
            scores["code_density"] * 0.4
            + scores["api_indicators"] * 0.3
            + scores["navigation_ratio"] * 0.3
        )

        return scores

    def should_continue_crawling(
        self, content_scores: Dict[str, float], current_depth: int
    ) -> Tuple[bool, int]:
        """
        Determine if crawling should continue based on content analysis.

        Args:
            content_scores: Scores from analyze_content()
            current_depth: Current recursion depth

        Returns:
            Tuple of (should_continue, suggested_depth_limit)
        """
        overall_score = content_scores.get("overall", 0.0)

        if self.strategy == DepthStrategy.MANUAL:
            return (True, current_depth)

        if self.strategy == DepthStrategy.CONSERVATIVE:
            # Only continue from high-quality documentation
            if overall_score < 0.6:
                return (False, 0)
            return (True, min(2, current_depth))

        if self.strategy == DepthStrategy.AGGRESSIVE:
            # Continue unless clearly not documentation
            if overall_score < 0.2:
                return (False, 0)
            return (True, current_depth)

        # AUTO strategy - adaptive depth based on content quality
        if overall_score > 0.7:
            # High quality documentation - go deeper
            return (True, max(3, current_depth))
        elif overall_score > 0.4:
            # Decent documentation - moderate depth
            return (True, min(2, current_depth))
        elif overall_score > 0.2:
            # Marginal - one more level only
            return (True, 1)
        else:
            # Low quality - stop here
            return (False, 0)

    def prioritize_links(
        self,
        links: List[str],
        base_url: str,
        current_depth: int,
        max_links: Optional[int] = None,
    ) -> List[str]:
        """
        Prioritize and filter a list of links for crawling.

        Args:
            links: List of URLs to prioritize
            base_url: The base URL being scraped
            current_depth: Current recursion depth
            max_links: Maximum number of links to return

        Returns:
            Prioritized and filtered list of URLs
        """
        # Analyze all links
        analyzed = []
        for link in links:
            analysis = self.analyze_url(link, base_url, current_depth)
            if analysis.should_follow:
                analyzed.append((link, analysis.priority))

        # Sort by priority (highest first)
        analyzed.sort(key=lambda x: x[1], reverse=True)

        # Apply max_links limit if specified
        if max_links and len(analyzed) > max_links:
            analyzed = analyzed[:max_links]

        return [link for link, _ in analyzed]
