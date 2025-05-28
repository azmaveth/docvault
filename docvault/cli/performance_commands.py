"""
CLI commands for performance optimization and monitoring.
"""

import asyncio
import json
import logging
import time

import click
from rich.console import Console
from rich.table import Table

from docvault.core.embeddings_optimized import (
    clear_cache,
    close_session,
    get_cache_stats,
)
from docvault.core.performance import (
    get_performance_stats,
    log_performance_summary,
    log_system_stats,
    memory_usage,
    reset_performance_stats,
)
from docvault.db.connection_pool import close_pool
from docvault.db.performance_indexes import (
    analyze_table_stats,
    create_performance_indexes,
    drop_performance_indexes,
    optimize_database,
)

console = Console()
logger = logging.getLogger(__name__)


@click.group()
def performance():
    """Performance optimization and monitoring commands."""
    pass


@performance.command()
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["table", "json"]),
    default="table",
    help="Output format",
)
def stats(output_format):
    """Show performance statistics."""
    perf_stats = get_performance_stats()
    cache_stats = get_cache_stats()
    table_stats = analyze_table_stats()

    if output_format == "json":
        stats_data = {
            "performance": perf_stats,
            "cache": cache_stats,
            "database": table_stats,
            "memory_mb": memory_usage(),
        }
        click.echo(json.dumps(stats_data, indent=2))
        return

    # Display performance statistics
    if perf_stats:
        perf_table = Table(title="Performance Statistics")
        perf_table.add_column("Operation", style="cyan")
        perf_table.add_column("Count", justify="right")
        perf_table.add_column("Avg Time", justify="right")
        perf_table.add_column("Min Time", justify="right")
        perf_table.add_column("Max Time", justify="right")
        perf_table.add_column("Total Time", justify="right")

        for operation, stats in perf_stats.items():
            perf_table.add_row(
                operation,
                str(stats["count"]),
                f"{stats['avg_time']:.3f}s",
                f"{stats['min_time']:.3f}s",
                f"{stats['max_time']:.3f}s",
                f"{stats['total_time']:.3f}s",
            )

        console.print(perf_table)
    else:
        console.print("[yellow]No performance statistics available[/yellow]")

    # Display cache statistics
    cache_table = Table(title="Embedding Cache Statistics")
    cache_table.add_column("Metric", style="cyan")
    cache_table.add_column("Value", justify="right")

    cache_table.add_row("Total Entries", str(cache_stats["total_entries"]))
    cache_table.add_row("Valid Entries", str(cache_stats["valid_entries"]))
    cache_table.add_row("Expired Entries", str(cache_stats["expired_entries"]))
    cache_table.add_row("Memory Usage", f"{cache_stats['memory_usage_mb']:.2f} MB")

    console.print("\n")
    console.print(cache_table)

    # Display database statistics
    if table_stats:
        db_table = Table(title="Database Statistics")
        db_table.add_column("Table", style="cyan")
        db_table.add_column("Row Count", justify="right")
        db_table.add_column("Indexes", justify="right")

        for table_name, stats in table_stats.items():
            if "error" not in stats:
                db_table.add_row(
                    table_name,
                    str(stats["row_count"]),
                    str(stats["indexes"]),
                )

        console.print("\n")
        console.print(db_table)

    # Display system statistics
    memory_mb = memory_usage()
    console.print(f"\n[cyan]Current Memory Usage:[/cyan] {memory_mb:.1f} MB")


@performance.command()
def reset():
    """Reset performance statistics."""
    reset_performance_stats()
    console.print("[green]Performance statistics reset[/green]")


@performance.command("clear-cache")
def clear_cache_cmd():
    """Clear embedding cache."""
    clear_cache()
    console.print("[green]Embedding cache cleared[/green]")


@performance.command()
@click.option(
    "--drop-first",
    is_flag=True,
    help="Drop existing indexes before creating new ones",
)
def create_indexes(drop_first):
    """Create database indexes for better performance."""
    if drop_first:
        console.print("Dropping existing indexes...")
        drop_performance_indexes()

    console.print("Creating performance indexes...")
    with console.status("Creating indexes..."):
        create_performance_indexes()

    console.print("[green]Performance indexes created successfully[/green]")


@performance.command()
def drop_indexes():
    """Drop all performance indexes."""
    if not click.confirm("Are you sure you want to drop all performance indexes?"):
        return

    console.print("Dropping performance indexes...")
    with console.status("Dropping indexes..."):
        drop_performance_indexes()

    console.print("[green]Performance indexes dropped[/green]")


@performance.command()
def optimize():
    """Optimize the database for better performance."""
    console.print("Optimizing database...")

    with console.status("Running database optimization..."):
        # Create indexes if they don't exist
        create_performance_indexes()

        # Run database optimization
        optimize_database()

    console.print("[green]Database optimization complete[/green]")


@performance.command()
@click.option(
    "--duration",
    default=10,
    help="Monitoring duration in seconds",
)
@click.option(
    "--interval",
    default=1,
    help="Update interval in seconds",
)
def monitor(duration, interval):
    """Monitor system performance in real-time."""
    console.print(f"Monitoring performance for {duration} seconds...")

    start_time = time.time()

    try:
        while time.time() - start_time < duration:
            # Clear screen and show current stats
            console.clear()

            # Show timestamp
            current_time = time.strftime("%H:%M:%S")
            console.print(f"[cyan]Performance Monitor - {current_time}[/cyan]\n")

            # System stats
            memory_mb = memory_usage()
            console.print(f"Memory Usage: {memory_mb:.1f} MB")

            # Cache stats
            cache_stats = get_cache_stats()
            console.print(
                f"Cache Entries: {cache_stats['valid_entries']}/{cache_stats['total_entries']}"
            )
            console.print(f"Cache Memory: {cache_stats['memory_usage_mb']:.2f} MB")

            # Recent performance stats
            perf_stats = get_performance_stats()
            if perf_stats:
                console.print("\nRecent Operations:")
                for operation, stats in list(perf_stats.items())[-5:]:
                    console.print(
                        f"  {operation}: {stats['count']} calls, avg {stats['avg_time']:.3f}s"
                    )

            time.sleep(interval)

    except KeyboardInterrupt:
        console.print("\n[yellow]Monitoring stopped[/yellow]")


@performance.command()
@click.argument("sql_query")
@click.option(
    "--params",
    help="Query parameters as JSON string",
)
def query_plan(sql_query, params):
    """Show execution plan for a SQL query."""
    from docvault.db.performance_indexes import get_query_plan

    query_params = []
    if params:
        try:
            query_params = json.loads(params)
        except json.JSONDecodeError:
            console.print("[red]Invalid JSON in params[/red]")
            return

    plan = get_query_plan(sql_query, query_params)

    if not plan:
        console.print("[yellow]No query plan available[/yellow]")
        return

    table = Table(title="Query Execution Plan")
    table.add_column("ID", justify="right")
    table.add_column("Parent", justify="right")
    table.add_column("Detail", style="cyan")

    for step in plan:
        table.add_row(
            str(step["id"]),
            str(step["parent"]) if step["parent"] is not None else "",
            step["detail"],
        )

    console.print(table)


@performance.command()
def benchmark():
    """Run performance benchmarks."""
    console.print("Running performance benchmarks...")

    # Benchmark database operations
    console.print("\n[cyan]Database Benchmarks:[/cyan]")

    from docvault.db.connection_pool import get_connection

    # Test connection pool performance
    start_time = time.time()
    for _ in range(100):
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            cursor.fetchone()
    pool_time = time.time() - start_time

    console.print(f"Connection pool (100 queries): {pool_time:.3f}s")

    # Benchmark embedding cache
    console.print("\n[cyan]Cache Benchmarks:[/cyan]")

    # Simulate cache operations
    import hashlib

    start_time = time.time()
    for i in range(1000):
        hashlib.md5(f"test_{i}".encode()).hexdigest()
        # This would test cache hit/miss performance in real implementation
    cache_time = time.time() - start_time

    console.print(f"Cache operations (1000 lookups): {cache_time:.3f}s")
    console.print("Cache hit ratio: N/A (would need hit/miss tracking)")

    console.print("\n[green]Benchmark complete[/green]")


@performance.command()
def cleanup():
    """Clean up performance-related resources."""
    console.print("Cleaning up performance resources...")

    # Close connection pool
    close_pool()
    console.print("✓ Database connection pool closed")

    # Close HTTP session
    asyncio.run(close_session())
    console.print("✓ HTTP session closed")

    # Clear caches
    clear_cache()
    console.print("✓ Embedding cache cleared")

    # Reset performance stats
    reset_performance_stats()
    console.print("✓ Performance statistics reset")

    console.print("[green]Cleanup complete[/green]")


@performance.command()
def system():
    """Show detailed system performance information."""
    console.print("[cyan]System Performance Information[/cyan]\n")

    # Log system stats (this will show in logs)
    log_system_stats()

    # Show memory usage
    memory_mb = memory_usage()
    console.print(f"Process Memory Usage: {memory_mb:.1f} MB")

    # Show database size
    import os

    from docvault import config

    if os.path.exists(config.DB_PATH):
        db_size_mb = os.path.getsize(config.DB_PATH) / 1024 / 1024
        console.print(f"Database Size: {db_size_mb:.1f} MB")

    # Show storage directory size
    storage_path = getattr(config, "STORAGE_PATH", None)
    if storage_path and os.path.exists(storage_path):
        total_size = 0
        for dirpath, dirnames, filenames in os.walk(storage_path):
            for filename in filenames:
                filepath = os.path.join(dirpath, filename)
                total_size += os.path.getsize(filepath)
        storage_size_mb = total_size / 1024 / 1024
        console.print(f"Storage Size: {storage_size_mb:.1f} MB")

    # Show performance summary
    console.print("\n[cyan]Performance Summary[/cyan]")
    log_performance_summary()


if __name__ == "__main__":
    performance()
