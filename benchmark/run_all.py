"""
Run all benchmarks and generate a comprehensive report.
"""
import sys
from rich.console import Console
from rich.table import Table

from benchmark.setup import setup_database, cleanup_database
from benchmark import large_resultset, concurrent, pool, batch_insert


def create_summary_table(all_results):
    """Create a summary table of all benchmark results"""
    console = Console()

    # Overall summary
    table = Table(title="Benchmark Summary", show_header=True, header_style="bold cyan")
    table.add_column("Test", style="yellow", width=30)
    table.add_column("Winner", style="green", width=15)
    table.add_column("asyncmy Rank", style="cyan", width=15)
    table.add_column("asyncmy vs Best", style="magenta", width=15)

    asyncmy_wins = 0
    total_tests = len(all_results)

    for test_name, results in all_results.items():
        winner = results[0][0]
        winner_time = results[0][1]

        # Find asyncmy's position
        asyncmy_rank = None
        asyncmy_time = None
        for idx, (name, time_val) in enumerate(results, 1):
            if name == "asyncmy":
                asyncmy_rank = idx
                asyncmy_time = time_val
                break

        if asyncmy_rank:
            if winner == "asyncmy":
                asyncmy_wins += 1
                rank_str = f"🏆 #{asyncmy_rank}"
                diff_str = "WINNER"
            else:
                rank_str = f"#{asyncmy_rank}/{len(results)}"
                diff_pct = ((asyncmy_time - winner_time) / winner_time * 100)
                diff_str = f"+{diff_pct:.1f}%"
        else:
            rank_str = "N/A"
            diff_str = "N/A"

        table.add_row(test_name, winner, rank_str, diff_str)

    console.print("\n")
    console.print(table)
    console.print(f"\n[bold]asyncmy wins: {asyncmy_wins}/{total_tests} tests[/bold]")
    console.print()

    return asyncmy_wins, total_tests


def main():
    console = Console()

    console.print("\n[bold cyan]" + "="*70 + "[/bold cyan]")
    console.print("[bold cyan]  asyncmy Performance Benchmark Suite (Complete Rewrite)[/bold cyan]")
    console.print("[bold cyan]" + "="*70 + "[/bold cyan]\n")

    # Setup database
    console.print("[yellow]Setting up database and test data...[/yellow]")
    try:
        setup_database()
    except Exception as e:
        console.print(f"[red]Error setting up database: {e}[/red]")
        console.print("[yellow]Make sure MySQL is running and accessible.[/yellow]")
        return 1

    all_results = {}

    try:
        # Run all benchmarks
        console.print("\n[bold green]Running benchmarks...[/bold green]")

        all_results["Large Result Set"] = large_resultset.run_benchmark()
        all_results["Concurrent Queries"] = concurrent.run_benchmark()
        all_results["Connection Pool"] = pool.run_benchmark()
        all_results["Batch Insert"] = batch_insert.run_benchmark()

        # Generate summary
        console.print("\n[bold cyan]" + "="*70 + "[/bold cyan]")
        console.print("[bold cyan]                         Final Summary[/bold cyan]")
        console.print("[bold cyan]" + "="*70 + "[/bold cyan]")

        asyncmy_wins, total_tests = create_summary_table(all_results)

        # Performance insights
        console.print("\n[bold yellow]Key Insights:[/bold yellow]")
        console.print("  • Large Result Set: Tests data processing & parsing efficiency")
        console.print("  • Concurrent Queries: Shows async advantage over sync libraries")
        console.print("  • Connection Pool: Tests connection management under load")
        console.print("  • Batch Insert: Tests bulk operation efficiency")

        if asyncmy_wins >= total_tests * 0.5:
            console.print(f"\n[bold green]✓ asyncmy performs excellently![/bold green]")
        else:
            console.print(f"\n[bold yellow]○ asyncmy shows competitive performance[/bold yellow]")

    finally:
        # Cleanup
        console.print("\n[yellow]Cleaning up...[/yellow]")
        cleanup_database()

    console.print("\n[bold green]Benchmark complete![/bold green]\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
