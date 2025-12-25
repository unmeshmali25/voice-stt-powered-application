"""
CLI entry point for the Agent Persona Generation System.

Usage:
    python -m app.simulation.cli generate --count 10
    python -m app.simulation.cli generate --count 10 --output custom.xlsx
    python -m app.simulation.cli generate --count 10 --preview-only
"""

import asyncio
import logging
import sys
from datetime import datetime
from pathlib import Path

import click
from rich.console import Console

from app.simulation.config import SimulationConfig
from app.simulation.exporters.excel_exporter import IncrementalPersonaExporter, PersonaExcelExporter
from app.simulation.exporters.preview_dashboard import (
    PersonaPreviewDashboard,
    show_cost_estimate,
    show_cost_summary,
)
from app.simulation.generators.persona_generator import PersonaGenerator

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

console = Console()


@click.group()
def cli():
    """Agent Persona Generation System.

    Generate realistic shopping personas for retail simulation using LLM.
    """
    pass


@cli.command()
@click.option(
    "--count",
    "-c",
    default=10,
    type=int,
    help="Number of personas to generate (default: 10)",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    help="Output Excel file path (default: data/personas/personas_YYYYMMDD_HHMMSS.xlsx)",
)
@click.option(
    "--append",
    "-a",
    type=click.Path(),
    help="Append to existing Excel file (overrides --output)",
)
@click.option(
    "--preview-only",
    is_flag=True,
    help="Show preview without saving to Excel",
)
@click.option(
    "--provider",
    "-p",
    type=click.Choice(["openrouter", "openai", "claude"], case_sensitive=False),
    help="LLM provider (default: from env or openrouter)",
)
@click.option(
    "--model",
    "-m",
    type=str,
    help="Override model name",
)
@click.option(
    "--temperature",
    "-t",
    type=float,
    help="LLM temperature (0.0-1.0, default: 0.8)",
)
@click.option(
    "--no-preview",
    is_flag=True,
    help="Skip preview dashboard (useful for automation)",
)
@click.option(
    "--yes",
    "-y",
    is_flag=True,
    help="Auto-confirm export (skip prompt)",
)
@click.option(
    "--incremental",
    is_flag=True,
    help="Save personas incrementally after each batch (cancel-safe)",
)
def generate(
    count: int,
    output: str,
    append: str,
    preview_only: bool,
    provider: str,
    model: str,
    temperature: float,
    no_preview: bool,
    yes: bool,
    incremental: bool,
):
    """Generate agent personas with LLM."""
    console.print()
    console.print("[bold cyan]Agent Persona Generation System[/bold cyan]")
    console.print("=" * 50)

    # Load and configure
    config = SimulationConfig()

    # Override from CLI
    if provider:
        config.llm_provider = provider
    if model:
        if config.llm_provider == "openrouter":
            config.fallback_models = [model]  # Use single model if specified
        elif config.llm_provider == "openai":
            config.openai_model = model
        elif config.llm_provider == "claude":
            config.claude_model = model
    if temperature is not None:
        config.llm_temperature = temperature

    # Validate config
    try:
        config.validate()
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        console.print()
        console.print(
            "Set the required API key in your environment:\n"
            "  [dim]export OPENROUTER_API_KEY=sk-or-...[/dim]\n"
            "  [dim]export OPENAI_API_KEY=sk-...[/dim]\n"
            "  [dim]export ANTHROPIC_API_KEY=sk-ant-...[/dim]"
        )
        sys.exit(1)

    # Determine mode and output path
    if append:
        output_path = Path(append)
        mode = "append"
        console.print(f"[dim]Mode: Append to existing file: {output_path}[/dim]")
    else:
        if output:
            output_path = Path(output)
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = config.output_dir / f"personas_{timestamp}.xlsx"
        mode = "create"
        console.print(f"[dim]Mode: Create new file: {output_path}[/dim]")

    # Show fallback models
    console.print(f"[dim]Fallback models: {' -> '.join(config.fallback_models)}[/dim]")

    # Show incremental mode message
    if incremental and mode == "append":
        console.print("[dim]Incremental mode: ON (saving after each batch)[/dim]")
    elif incremental and mode != "append":
        console.print("[yellow]Warning: --incremental only works with --append. Using standard mode.[/yellow]")
        incremental = False

    # Create generator
    generator = PersonaGenerator(config)

    # Generate personas
    console.print()
    start_time = datetime.now()

    try:
        if incremental and mode == "append":
            # Use incremental export with streaming generator
            with IncrementalPersonaExporter(output_path) as exporter:
                batch_count = [0]  # Use list to allow modification in closure

                def batch_callback(batch_personas):
                    batch_count[0] += len(batch_personas)
                    console.print(f"[dim]Saved batch of {len(batch_personas)} personas (total saved: {batch_count[0]})[/dim]")

                personas, cost_summary = asyncio.run(
                    generator.generate_batch_streaming(
                        count=count,
                        show_progress=True,
                        batch_callback=batch_callback,
                    )
                )
        else:
            # Standard generation (non-incremental)
            personas, cost_summary = asyncio.run(generator.generate_batch(count=count, show_progress=True))
    except Exception as e:
        console.print(f"[red]Error generating personas:[/red] {e}")
        sys.exit(1)

    duration = (datetime.now() - start_time).total_seconds()

    if not personas:
        console.print("[red]No personas were generated.[/red]")
        sys.exit(1)

    dashboard = PersonaPreviewDashboard()
    dashboard.show_generation_complete(len(personas), duration)

    # Show cost summary
    show_cost_summary(cost_summary, duration)

    if preview_only:
        if not no_preview:
            dashboard.show_preview_summary(personas)
        console.print("\n[dim]Preview mode: Excel export skipped.[/dim]")
        return

    # Show preview
    if not no_preview:
        dashboard.show_preview_summary(personas)

        if not yes and not dashboard.prompt_export_confirmation():
            dashboard.show_export_cancelled()
            return

    # Export to Excel (skip if incremental mode already saved)
    if not (incremental and mode == "append"):
        try:
            exporter = PersonaExcelExporter(personas)
            if mode == "append":
                exporter.append(output_path)
            else:
                exporter.export(output_path)
        except Exception as e:
            console.print(f"[red]Error exporting to Excel:[/red] {e}")
            sys.exit(1)

        dashboard.show_export_success(output_path, len(personas))

    # Save preview JSON
    if config.save_preview_json and mode == "create":
        preview_path = output_path.with_suffix(".json")
        dashboard.save_preview_json(personas, preview_path)


@cli.command()
@click.argument("filepath", type=click.Path(exists=True))
def validate(filepath: str):
    """Validate personas from Excel file."""
    console.print(f"[yellow]Validation command not yet implemented.[/yellow]")
    console.print(f"File: {filepath}")
    console.print()
    console.print("This will validate persona consistency and attribute ranges.")
    console.print("Coming soon!")


@cli.command()
def config_show():
    """Show current configuration."""
    config = SimulationConfig()

    console.print()
    console.print(Panel(f"[bold]LLM Provider:[/bold] {config.llm_provider}\n"
                       f"[bold]Model:[/bold] {config.model}\n"
                       f"[bold]Temperature:[/bold] {config.llm_temperature}\n"
                       f"[bold]Max Tokens:[/bold] {config.llm_max_tokens}\n"
                       f"[bold]Default Count:[/bold] {config.default_persona_count}\n"
                       f"[bold]Output Dir:[/bold] {config.output_dir}\n"
                       f"[bold]API Key Set:[/bold] {bool(config.llm_api_key)}",
                       title="[bold]Current Configuration[/bold]", border_style="blue"))


@cli.command()
def categories():
    """Show available product categories for personas."""
    from app.simulation.generators.prompts import AVAILABLE_CATEGORIES, US_REGIONS

    console.print()
    console.print(Panel("\n".join(f"  • {cat}" for cat in AVAILABLE_CATEGORIES),
                       title="[bold]Available Product Categories[/bold]", border_style="green"))
    console.print()
    console.print(Panel("\n".join(f"  • {region}" for region in US_REGIONS),
                       title="[bold]Available US Regions[/bold]", border_style="blue"))


if __name__ == "__main__":
    # Check for Python version
    if sys.version_info < (3, 10):
        console.print("[red]Error: Python 3.10 or higher required.[/red]")
        sys.exit(1)

    cli()
