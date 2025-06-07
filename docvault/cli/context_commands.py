"""
CLI commands for managing contextual retrieval.
"""

import asyncio
from typing import Optional

import click
from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn
from rich.table import Table

from docvault import config
from docvault.core.contextual_processor import ContextualChunkProcessor
from docvault.db import operations
from docvault.utils.console import console


@click.group(name="context")
def context_group():
    """Manage contextual retrieval features."""
    pass


@context_group.command(name="enable")
def enable_contextual_retrieval():
    """Enable contextual retrieval for new documents."""
    with operations.get_connection() as conn:
        conn.execute(
            """
            UPDATE config
            SET value = 'true'
            WHERE key = 'contextual_retrieval_enabled'
        """
        )
        conn.commit()

    console.print("[green]✓[/green] Contextual retrieval enabled")
    console.print("New documents will be processed with contextual augmentation")


@context_group.command(name="disable")
def disable_contextual_retrieval():
    """Disable contextual retrieval."""
    with operations.get_connection() as conn:
        conn.execute(
            """
            UPDATE config
            SET value = 'false'
            WHERE key = 'contextual_retrieval_enabled'
        """
        )
        conn.commit()

    console.print("[yellow]✓[/yellow] Contextual retrieval disabled")


@context_group.command(name="status")
def show_status():
    """Show contextual retrieval status and statistics."""
    with operations.get_connection() as conn:
        # Get config status
        cursor = conn.execute(
            """
            SELECT value FROM config
            WHERE key = 'contextual_retrieval_enabled'
        """
        )
        result = cursor.fetchone()
        enabled = result["value"] == "true" if result else False

        # Get provider info
        cursor = conn.execute(
            """
            SELECT key, value FROM config
            WHERE key IN ('context_llm_provider', 'context_llm_model')
        """
        )
        config_items = {row["key"]: row["value"] for row in cursor.fetchall()}

        # Get statistics
        cursor = conn.execute(
            """
            SELECT
                COUNT(DISTINCT document_id) as docs_with_context,
                COUNT(*) as segments_with_context,
                COUNT(DISTINCT context_model) as models_used
            FROM document_segments
            WHERE context_description IS NOT NULL
        """
        )
        stats = cursor.fetchone()

        # Get total counts
        cursor = conn.execute(
            """
            SELECT
                COUNT(DISTINCT d.id) as total_docs,
                COUNT(*) as total_segments
            FROM documents d
            JOIN document_segments s ON d.id = s.document_id
        """
        )
        totals = cursor.fetchone()

    # Display status
    console.print("\n[bold]Contextual Retrieval Status[/bold]")
    console.print(f"Enabled: {'[green]Yes[/green]' if enabled else '[red]No[/red]'}")
    console.print(f"Provider: {config_items.get('context_llm_provider', 'ollama')}")
    console.print(f"Model: {config_items.get('context_llm_model', 'llama2')}")

    console.print("\n[bold]Statistics[/bold]")
    console.print(
        f"Documents with context: {stats['docs_with_context']}/{totals['total_docs']}"
    )
    console.print(
        f"Segments with context: {stats['segments_with_context']}/"
        f"{totals['total_segments']}"
    )

    if stats["segments_with_context"] > 0:
        percentage = (stats["segments_with_context"] / totals["total_segments"]) * 100
        console.print(f"Coverage: {percentage:.1f}%")


@context_group.command(name="process")
@click.argument("document_id", type=int)
@click.option("--regenerate", "-r", is_flag=True, help="Regenerate existing contexts")
@click.option("--chunk-size", default=5000, help="Chunk size in characters")
@click.option("--strategy", default="hybrid", help="Chunking strategy")
def process_document(
    document_id: int, regenerate: bool, chunk_size: int, strategy: str
):
    """Process a document with contextual augmentation."""
    # Check if document exists
    doc = operations.get_document(document_id)
    if not doc:
        console.error(f"Document with ID {document_id} not found")
        return

    console.print(f"\n[bold]Processing document:[/bold] {doc['title']}")

    # Run async processing
    async def run_processing():
        processor = ContextualChunkProcessor()

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("Generating contexts...", total=None)

            try:
                result = await processor.process_document(
                    document_id,
                    regenerate=regenerate,
                    chunk_size=chunk_size,
                    chunking_strategy=strategy,
                )

                progress.update(task, completed=100)

                if result["status"] == "success":
                    console.print("\n[green]✓[/green] Processing complete!")
                    console.print(
                        f"  Segments processed: {result['segments_processed']}"
                    )
                    console.print(
                        f"  Contexts generated: {result['contexts_generated']}"
                    )
                    console.print(
                        f"  Embeddings updated: {result['embeddings_updated']}"
                    )
                    if result.get("metadata_embeddings"):
                        console.print(
                            f"  Metadata embeddings: {result['metadata_embeddings']}"
                        )
                    console.print(f"  Duration: {result['duration_seconds']:.1f}s")
                else:
                    console.print(
                        f"\n[yellow]![/yellow] Processing skipped: "
                        f"{result.get('reason', 'Unknown')}"
                    )

            except Exception as e:
                console.error(f"Error processing document: {e}")

    asyncio.run(run_processing())


@context_group.command(name="process-all")
@click.option("--regenerate", "-r", is_flag=True, help="Regenerate existing contexts")
@click.option("--limit", "-l", type=int, help="Limit number of documents to process")
def process_all_documents(regenerate: bool, limit: int | None):
    """Process all documents with contextual augmentation."""
    # Get documents to process
    with operations.get_connection() as conn:
        query = """
            SELECT DISTINCT d.id, d.title
            FROM documents d
        """

        if not regenerate:
            query += """
                LEFT JOIN document_segments s ON d.id = s.document_id
                WHERE s.context_description IS NULL
            """

        query += " ORDER BY d.id"

        if limit:
            query += f" LIMIT {limit}"

        cursor = conn.execute(query)
        documents = cursor.fetchall()

    if not documents:
        console.print("No documents need processing")
        return

    console.print(f"\n[bold]Processing {len(documents)} documents[/bold]")

    # Process documents
    async def run_batch_processing():
        processor = ContextualChunkProcessor()

        success_count = 0
        error_count = 0

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("{task.completed}/{task.total}"),
            console=console,
        ) as progress:
            task = progress.add_task("Processing documents...", total=len(documents))

            for doc in documents:
                progress.update(task, description=f"Processing: {doc['title'][:50]}...")

                try:
                    result = await processor.process_document(
                        doc["id"], regenerate=regenerate
                    )

                    if result["status"] == "success":
                        success_count += 1
                    else:
                        error_count += 1

                except Exception as e:
                    error_count += 1
                    console.print(f"[red]Error processing {doc['title']}: {e}[/red]")

                progress.advance(task)

        console.print("\n[bold]Processing complete![/bold]")
        console.print(f"  Successful: {success_count}")
        console.print(f"  Failed: {error_count}")

    asyncio.run(run_batch_processing())


@context_group.command(name="similar")
@click.argument("segment_id", type=int)
@click.option("--limit", "-l", default=10, help="Number of results")
@click.option("--role", "-r", help="Filter by semantic role")
def find_similar_segments(segment_id: int, limit: int, role: str | None):
    """Find segments with similar metadata/context."""

    async def find_similar():
        processor = ContextualChunkProcessor()

        results = await processor.find_similar_by_metadata(
            segment_id, limit=limit, filter_role=role
        )

        if not results:
            console.print("No similar segments found")
            return

        # Create results table
        table = Table(title=f"Segments Similar to #{segment_id}")
        table.add_column("ID", style="cyan")
        table.add_column("Document", style="blue")
        table.add_column("Section", style="green")
        table.add_column("Role", style="yellow")
        table.add_column("Similarity", style="magenta")

        for result in results:
            # Get document title
            doc = operations.get_document(result["document_id"])
            doc_title = (
                doc["title"][:30] + "..." if len(doc["title"]) > 30 else doc["title"]
            )

            table.add_row(
                str(result["segment_id"]),
                doc_title,
                result["section_title"][:40],
                result["metadata"].get("semantic_role", "general"),
                f"{result['similarity_score']:.3f}",
            )

        console.print(table)

    asyncio.run(find_similar())


@context_group.command(name="config")
@click.option("--provider", help="LLM provider (ollama, openai, anthropic)")
@click.option("--model", help="Model name")
@click.option("--batch-size", type=int, help="Batch size for processing")
@click.option("--max-tokens", type=int, help="Max tokens for context")
def configure(
    provider: str | None,
    model: str | None,
    batch_size: int | None,
    max_tokens: int | None,
):
    """Configure contextual retrieval settings."""
    updates = []

    with operations.get_connection() as conn:
        if provider:
            conn.execute(
                """
                UPDATE config SET value = ?
                WHERE key = 'context_llm_provider'
            """,
                (provider,),
            )
            updates.append(f"Provider: {provider}")

        if model:
            conn.execute(
                """
                UPDATE config SET value = ?
                WHERE key = 'context_llm_model'
            """,
                (model,),
            )
            updates.append(f"Model: {model}")

        if batch_size:
            conn.execute(
                """
                UPDATE config SET value = ?
                WHERE key = 'context_batch_size'
            """,
                (str(batch_size),),
            )
            updates.append(f"Batch size: {batch_size}")

        if max_tokens:
            conn.execute(
                """
                UPDATE config SET value = ?
                WHERE key = 'context_max_tokens'
            """,
                (str(max_tokens),),
            )
            updates.append(f"Max tokens: {max_tokens}")

        conn.commit()

    if updates:
        console.print("[green]✓[/green] Configuration updated:")
        for update in updates:
            console.print(f"  {update}")
    else:
        console.print("No configuration changes made")
        console.print("\nAvailable options:")
        console.print("  --provider: ollama, openai, anthropic")
        console.print("  --model: Model name for the provider")
        console.print("  --batch-size: Number of chunks to process together")
        console.print("  --max-tokens: Maximum tokens for context description")
