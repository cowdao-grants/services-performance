"""CLI commands for report generation."""

import sys
from datetime import datetime
from pathlib import Path
from typing import Annotated, Literal, Optional, cast

import typer
from rich.console import Console

from cow_performance.baselines import BaselineManager
from cow_performance.reporting import ReportGenerator

app = typer.Typer(help="Generate performance reports")
console = Console()

# Default directory for saved reports
DEFAULT_REPORTS_DIR = Path(".cow-perf") / "reports"


@app.command("generate")
def generate_report(
    baseline_name: Annotated[
        str,
        typer.Argument(help="Name or ID of the baseline to report on"),
    ],
    format: Annotated[
        str,
        typer.Option("--format", "-f", help="Output format: text, markdown, json"),
    ] = "text",
    output: Annotated[
        Optional[Path],
        typer.Option("--output", "-o", help="Output file path"),
    ] = None,
    save: Annotated[
        bool,
        typer.Option("--save", "-s", help="Save report to .cow-perf/reports/"),
    ] = False,
    compare: Annotated[
        Optional[str],
        typer.Option("--compare", "-c", help="Baseline to compare against"),
    ] = None,
    export_csv: Annotated[
        bool,
        typer.Option("--export-csv", help="Export CSV files to .cow-perf/reports/csv/"),
    ] = False,
    no_color: Annotated[
        bool,
        typer.Option("--no-color", help="Disable colored output"),
    ] = False,
    baselines_dir: Annotated[
        Optional[Path],
        typer.Option("--baselines-dir", help="Baselines directory"),
    ] = None,
) -> None:
    """
    Generate a performance report from a saved baseline.

    Examples:

        # Generate text report to console
        cow-perf report generate my-baseline

        # Save report to .cow-perf/reports/
        cow-perf report generate my-baseline --save

        # Save markdown report
        cow-perf report generate my-baseline -f markdown --save

        # Save with CSV exports
        cow-perf report generate my-baseline --save --export-csv

        # Custom output location
        cow-perf report generate my-baseline -f markdown -o report.md

        # Compare against another baseline
        cow-perf report generate current-run -c previous-baseline --save
    """
    # Validate format
    valid_formats = ["text", "markdown", "json"]
    if format not in valid_formats:
        console.print(
            f"[bold red]Error:[/bold red] Invalid format '{format}'. "
            f"Valid formats: {', '.join(valid_formats)}"
        )
        raise typer.Exit(1)

    manager = BaselineManager(baselines_dir)
    generator = ReportGenerator()

    # Load baseline
    try:
        baseline = manager.load(baseline_name)
    except FileNotFoundError:
        console.print(f"[bold red]Error:[/bold red] Baseline not found: {baseline_name}")
        console.print("\n[yellow]Tip:[/yellow] List available baselines with: cow-perf baselines")
        raise typer.Exit(1) from None

    # Load comparison baseline if specified
    comparison = None
    if compare:
        try:
            compare_baseline = manager.load(compare)

            # Import and use comparison engine
            try:
                from cow_performance.comparison import ComparisonEngine
                from cow_performance.comparison.thresholds import load_thresholds

                engine = ComparisonEngine(thresholds=load_thresholds())
                comparison = engine.compare(compare_baseline, baseline)
            except ImportError:
                console.print(
                    "[yellow]Warning:[/yellow] Comparison module not available. "
                    "Generating report without comparison."
                )
        except FileNotFoundError:
            console.print(f"[yellow]Warning:[/yellow] Comparison baseline not found: {compare}")

    # Generate report
    report = generator.generate(baseline, comparison=comparison)

    # Format and output
    report_format = cast(Literal["text", "markdown", "json"], format)

    # Determine output path
    output_path = None
    if output:
        # User specified exact path
        output_path = output
    elif save:
        # Auto-generate filename in .cow-perf/reports/
        DEFAULT_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")

        # Add comparison suffix if comparing
        suffix = f"-vs-{compare}" if compare else ""

        # File extension based on format
        ext = {"text": "txt", "markdown": "md", "json": "json"}[report_format]
        filename = f"report-{baseline_name}{suffix}-{timestamp}.{ext}"
        output_path = DEFAULT_REPORTS_DIR / filename

    # Format the report
    use_colors = not no_color and output_path is None
    formatted = generator.format(report, format=report_format, use_colors=use_colors)

    # Save or display
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(formatted)
        console.print(f"\n[green]✓ Report saved to:[/green] {output_path}")

        # Also show a preview if it's text/markdown
        if report_format in ["text", "markdown"]:
            console.print("\n[dim]Preview (first 20 lines):[/dim]")
            preview_lines = formatted.split("\n")[:20]
            console.print("\n".join(preview_lines))
            if len(formatted.split("\n")) > 20:
                console.print("[dim]... (see file for full report)[/dim]")
    else:
        console.print(formatted)

    # Export CSV if requested
    if export_csv:
        csv_dir = DEFAULT_REPORTS_DIR / "csv" / baseline_name
        csv_dir.mkdir(parents=True, exist_ok=True)

        exported = generator.export_csv(report, csv_dir)
        console.print(f"\n[green]✓ CSV files exported to:[/green] {csv_dir}")
        for name, path in exported.items():
            console.print(f"  - {name}: {path.name}")

    # Exit with appropriate code based on verdict
    if report.summary:
        if report.summary.verdict.value == "failure":
            sys.exit(2)


@app.command("list-formats")
def list_formats() -> None:
    """List available report formats."""
    console.print("[bold]Available Report Formats:[/bold]")
    console.print("  text     - Plain text (terminal-friendly, default)")
    console.print("  markdown - Markdown (GitHub-friendly)")
    console.print("  json     - JSON (machine-readable)")
    console.print("")
    console.print("[bold]Additional Exports:[/bold]")
    console.print("  --export-csv <dir>  - Export metrics as CSV files")
