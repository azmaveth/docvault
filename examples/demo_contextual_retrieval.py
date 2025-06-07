#!/usr/bin/env python3
"""
Demo of contextual retrieval feature in DocVault.

This script demonstrates how contextual retrieval improves search accuracy
by adding context to chunks before embedding them.
"""

import asyncio
import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from rich.console import Console
from rich.table import Table

from docvault.core.contextual_processor import ContextualChunkProcessor
from docvault.core.embeddings import generate_embeddings
from docvault.db import operations
from docvault.db.operations_contextual import (
    get_contextual_segments_stats,
    search_segments_contextual,
)

console = Console()


async def main():
    """Demo contextual retrieval functionality."""
    console.print("[bold]DocVault Contextual Retrieval Demo[/bold]\n")

    # Check if contextual retrieval is enabled
    with operations.get_connection() as conn:
        cursor = conn.execute(
            """
            SELECT value FROM config 
            WHERE key = 'contextual_retrieval_enabled'
        """
        )
        result = cursor.fetchone()
        enabled = result and result["value"] == "true"

    if not enabled:
        console.print("[yellow]Contextual retrieval is not enabled.[/yellow]")
        console.print("Enable it with: [cyan]dv context enable[/cyan]\n")
        return

    # Get statistics
    stats = get_contextual_segments_stats()

    console.print("[bold]Current Statistics:[/bold]")
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Total Segments", str(stats["total_segments"]))
    table.add_row("Segments with Context", str(stats["segments_with_context"]))
    table.add_row("Context Coverage", f"{stats['coverage_percentage']:.1f}%")
    table.add_row(
        "Documents with Context",
        f"{stats['documents_with_context']}/{stats['total_documents']}",
    )

    console.print(table)
    console.print()

    # Demo search comparison
    if stats["segments_with_context"] > 0:
        console.print("[bold]Search Comparison Demo[/bold]\n")

        # Example queries
        queries = [
            "error handling",
            "authentication",
            "database connection",
        ]

        for query in queries:
            console.print(f"\n[bold cyan]Query: '{query}'[/bold cyan]")

            # Generate embedding for the query
            embedding = await generate_embeddings(query)

            # Regular search
            console.print("\n[yellow]Regular Search:[/yellow]")
            regular_results = operations.search_segments(
                embedding=embedding,
                limit=3,
                text_query=query,
                min_score=0.0,
            )

            if regular_results:
                for i, result in enumerate(regular_results, 1):
                    console.print(
                        f"{i}. {result.get('title', 'Untitled')} - Score: {result.get('score', 0):.3f}"
                    )
                    console.print(
                        f"   Section: {result.get('section_title', 'Unknown')}"
                    )
                    console.print(f"   Content: {result.get('content', '')[:100]}...")
            else:
                console.print("   No results found")

            # Contextual search
            console.print("\n[green]Contextual Search:[/green]")
            contextual_results = search_segments_contextual(
                embedding=embedding,
                limit=3,
                text_query=query,
                min_score=0.0,
                use_contextual=True,
            )

            if contextual_results:
                for i, result in enumerate(contextual_results, 1):
                    ctx_indicator = " [ctx]" if result.get("is_contextual") else ""
                    console.print(
                        f"{i}. {result.get('title', 'Untitled')} - Score: {result.get('score', 0):.3f}{ctx_indicator}"
                    )
                    console.print(
                        f"   Section: {result.get('section_title', 'Unknown')}"
                    )
                    if result.get("context_description"):
                        console.print(
                            f"   Context: {result['context_description'][:100]}..."
                        )
                    console.print(f"   Content: {result.get('content', '')[:100]}...")
            else:
                console.print("   No results found")

            console.print("\n" + "─" * 60)

    else:
        console.print(
            "\n[yellow]No documents have been processed with contextual retrieval yet.[/yellow]"
        )
        console.print(
            "Process documents with: [cyan]dv context process <document_id>[/cyan]"
        )
        console.print("Or process all: [cyan]dv context process-all[/cyan]")


if __name__ == "__main__":
    asyncio.run(main())
