"""Tests for NextJSExtractor using real MCP specification site."""

import asyncio

import aiohttp
import pytest
from bs4 import BeautifulSoup

from docvault.core.doc_type_detector import DocType, DocTypeDetector
from docvault.core.extractors.nextjs import NextJSExtractor


@pytest.mark.asyncio
async def test_nextjs_detection_mcp_site():
    """Test that MCP specification site is detected as Next.js."""
    url = "https://modelcontextprotocol.io/specification/2025-03-26"

    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            html_content = await response.text()

    detector = DocTypeDetector()
    doc_type, confidence = detector.detect(url, html_content)

    # Should detect as Next.js with reasonable confidence
    assert doc_type == DocType.NEXTJS
    assert confidence > 0.5


@pytest.mark.asyncio
async def test_nextjs_extractor_mcp_site():
    """Test NextJSExtractor with MCP specification site."""
    url = "https://modelcontextprotocol.io/specification/2025-03-26"

    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            html_content = await response.text()

    soup = BeautifulSoup(html_content, "html.parser")
    extractor = NextJSExtractor()

    result = extractor.extract(soup, url)

    # Check that we got meaningful content
    assert result is not None
    assert "content" in result
    assert "metadata" in result

    content = result["content"]
    metadata = result["metadata"]

    # Content should be longer than what GenericExtractor produces (>5k)
    assert len(content) > 5000, f"Expected >5k chars, got {len(content)}"

    # Should contain key MCP specification content
    assert "Model Context Protocol" in content
    assert "specification" in content.lower()

    # Metadata should indicate successful extraction
    assert metadata.get("extraction_method") == "next_data"

    # Should have extracted table of contents
    assert "table_of_contents" in metadata
    assert len(metadata["table_of_contents"]) > 0

    print(f"✅ Extracted {len(content)} characters")
    print(f"📋 Table of contents: {len(metadata['table_of_contents'])} items")
    print(f"🎯 Extraction method: {metadata['extraction_method']}")


@pytest.mark.asyncio
async def test_nextjs_extractor_vs_generic():
    """Compare NextJSExtractor vs GenericExtractor on MCP site."""
    from docvault.core.extractors.generic import GenericExtractor

    url = "https://modelcontextprotocol.io/specification/2025-03-26"

    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            html_content = await response.text()

    soup = BeautifulSoup(html_content, "html.parser")

    # Extract with both extractors
    nextjs_extractor = NextJSExtractor()
    generic_extractor = GenericExtractor()

    nextjs_result = nextjs_extractor.extract(soup, url)
    generic_result = generic_extractor.extract(soup, url)

    nextjs_content = nextjs_result["content"]
    generic_content = generic_result["content"]

    # NextJS extractor should get more content
    assert len(nextjs_content) > len(
        generic_content
    ), f"NextJS: {len(nextjs_content)}, Generic: {len(generic_content)}"

    print(f"📊 NextJS extractor: {len(nextjs_content)} chars")
    print(f"📊 Generic extractor: {len(generic_content)} chars")
    print(
        f"📈 Improvement: {len(nextjs_content) / len(generic_content):.1f}x more "
        f"content"
    )


def test_nextjs_text_extraction():
    """Test text extraction from compiled MDX."""
    extractor = NextJSExtractor()

    # Sample compiled MDX-like JavaScript
    compiled_source = """
    "use strict";
    const _jsx = arguments[0].jsx;
    function _createMdxContent(props) {
        return _jsx("div", {
            children: [
                _jsx("h1", { children: "Introduction" }),
                _jsx("p", { children: "This is a test document with some content." }),
                _jsx("pre", {
                    children: _jsx("code", { children: "console.log('hello');" })
                })
            ]
        });
    }
    """

    result = extractor._extract_text_from_compiled_mdx(compiled_source)

    assert "Introduction" in result
    assert "test document" in result

    print(f"📝 Extracted text: {result}")


def test_content_string_filtering():
    """Test content string filtering logic."""
    extractor = NextJSExtractor()

    # Test cases: (input, should_be_content)
    test_cases = [
        ("This is a valid content string.", True),
        ("Model Context Protocol specification", True),
        ("_internal_var", False),
        ("function foo() {}", False),
        ("const x = 5", False),
        ("import React from 'react'", False),
        ("CONSTANT_VALUE", False),
        ("foo(bar)", False),
        ("http://example.com", False),
        ("Tiny", False),  # Too short (4 chars)
        ("Short", True),  # Title-like (5 chars, starts with capital)
        ("NoSpacesHere", True),  # Title-like (starts with capital, alphanumeric)
        ("Good content with punctuation!", True),
        ("Another sentence with proper structure.", True),
    ]

    for text, expected in test_cases:
        result = extractor._is_content_string(text)
        assert (
            result == expected
        ), f"Failed for '{text}': expected {expected}, got {result}"

    print("✅ All content filtering tests passed")


if __name__ == "__main__":
    # Run the tests
    asyncio.run(test_nextjs_detection_mcp_site())
    asyncio.run(test_nextjs_extractor_mcp_site())
    asyncio.run(test_nextjs_extractor_vs_generic())
    test_nextjs_text_extraction()
    test_content_string_filtering()
    print("🎉 All tests completed!")
