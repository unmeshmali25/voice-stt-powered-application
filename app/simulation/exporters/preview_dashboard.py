"""
Rich CLI dashboard for persona generation preview.

Displays generation progress, statistics, and persona previews.
"""

import json
from collections import Counter
from pathlib import Path
from typing import List, Optional

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from app.simulation.models.persona import AgentPersona

console = Console()


class PersonaPreviewDashboard:
    """
    Rich-based CLI dashboard for persona generation preview.

    Usage:
        dashboard = PersonaPreviewDashboard()
        dashboard.show_preview_summary(personas)
        if dashboard.prompt_export_confirmation():
            # proceed with export
    """

    def show_generation_progress(
        self,
        current: int,
        total: int,
        agent_id: str = "",
    ) -> None:
        """
        Show a progress indicator during generation.

        Args:
            current: Current number of personas generated
            total: Total number to generate
            agent_id: ID of the most recently generated agent
        """
        console.print(
            f"[cyan]Generating personas...[/cyan] [{current}/{total}] {agent_id}",
            end="\r",
        )

    def show_generation_complete(self, total: int, duration: float) -> None:
        """Show completion message with timing."""
        console.print(f"\n[green]✓[/green] Generated {total} personas in {duration:.1f}s")

    def show_preview_summary(self, personas: List[AgentPersona]) -> None:
        """
        Display summary of generated personas.

        Args:
            personas: List of generated personas
        """
        console.print()
        console.print(Panel(self._format_statistics(personas), title="[bold]Generation Statistics[/bold]", border_style="blue"))

        console.print()

        # Show preview table
        table = Table(title="[bold cyan]Generated Personas Preview[/bold cyan]", show_header=True, header_style="bold magenta")
        table.add_column("Agent ID", style="cyan", width=12)
        table.add_column("Age", justify="right", style="white", width=6)
        table.add_column("Gender", style="white", width=10)
        table.add_column("Income", style="green", width=10)
        table.add_column("Price Sens", justify="right", style="yellow", width=10)
        table.add_column("Brand Loyalty", justify="right", style="yellow", width=12)
        table.add_column("Coupon Affin", justify="right", style="blue", width=12)
        table.add_column("Categories", style="white", width=25)

        # Show first 10 or all if fewer
        preview_count = min(10, len(personas))
        for persona in personas[:preview_count]:
            categories = ", ".join(persona.shopping_preferences.preferred_categories[:2])
            if len(persona.shopping_preferences.preferred_categories) > 2:
                categories += f" +{len(persona.shopping_preferences.preferred_categories) - 2}"

            table.add_row(
                persona.agent_id,
                str(persona.demographics.age),
                persona.demographics.gender,
                persona.demographics.income_bracket,
                f"{persona.behavioral_traits.price_sensitivity:.2f}",
                f"{persona.behavioral_traits.brand_loyalty:.2f}",
                f"{persona.coupon_behavior.coupon_affinity:.2f}",
                categories,
            )

        console.print(table)

        if len(personas) > preview_count:
            console.print(f"[dim]... and {len(personas) - preview_count} more personas[/dim]")

    def _format_statistics(self, personas: List[AgentPersona]) -> str:
        """Format persona statistics for display."""
        if not personas:
            return "No personas generated"

        # Calculate statistics
        ages = [p.demographics.age for p in personas]
        incomes = [p.demographics.income_bracket for p in personas]
        income_counts = Counter(incomes)

        price_sens = [p.behavioral_traits.price_sensitivity for p in personas]
        brand_loyal = [p.behavioral_traits.brand_loyalty for p in personas]
        coupon_affin = [p.coupon_behavior.coupon_affinity for p in personas]

        # Get all categories
        all_categories = []
        for p in personas:
            all_categories.extend(p.shopping_preferences.preferred_categories)
        category_counts = Counter(all_categories).most_common(5)

        # Format output
        lines = [
            f"[bold]Total Personas:[/bold] {len(personas)}",
            f"",
            f"[bold]Age:[/bold] {min(ages):.0f} - {max(ages):.0f} (avg: {sum(ages)/len(ages):.1f})",
            f"[bold]Income:[/bold] {', '.join(f'{k}={v}' for k, v in sorted(income_counts.items()))}",
            f"",
            f"[bold]Avg Behavioral Scores:[/bold]",
            f"  Price Sensitivity: {sum(price_sens)/len(price_sens):.2f}",
            f"  Brand Loyalty:     {sum(brand_loyal)/len(brand_loyal):.2f}",
            f"  Coupon Affinity:   {sum(coupon_affin)/len(coupon_affin):.2f}",
            f"",
            f"[bold]Top Categories:[/bold] {', '.join(f'{cat}({count})' for cat, count in category_counts)}",
        ]

        return "\n".join(lines)

    def prompt_export_confirmation(self) -> bool:
        """
        Ask user if they want to export to Excel.

        Returns:
            True if user confirms export, False otherwise
        """
        console.print()
        response = console.input("[bold yellow]Export to Excel?[/bold yellow] [Y/n]: ")
        return response.lower() in ("", "y", "yes")

    def show_export_success(self, filepath: Path, persona_count: int) -> None:
        """Show export success message."""
        console.print()
        console.print(
            Panel(
                f"[green]✓[/green] Successfully exported [bold]{persona_count}[/bold] personas to:\n\n[bold cyan]{filepath}[/bold cyan]",
                title="[bold green]Export Complete[/bold green]",
                border_style="green",
            )
        )

    def show_export_cancelled(self) -> None:
        """Show export cancelled message."""
        console.print()
        console.print("[yellow]Export cancelled.[/yellow]")

    def save_preview_json(self, personas: List[AgentPersona], filepath: Path) -> None:
        """
        Save preview data to JSON file.

        Args:
            personas: List of personas to save
            filepath: Path to save JSON file
        """
        filepath.parent.mkdir(parents=True, exist_ok=True)

        preview_data = {
            "count": len(personas),
            "generated_at": personas[0].generated_at if personas else None,
            "generation_model": personas[0].generation_model if personas else None,
            "statistics": {
                "age_range": [p.demographics.age for p in personas],
                "income_distribution": [p.demographics.income_bracket for p in personas],
                "avg_price_sensitivity": sum(p.behavioral_traits.price_sensitivity for p in personas) / len(personas) if personas else 0,
                "avg_brand_loyalty": sum(p.behavioral_traits.brand_loyalty for p in personas) / len(personas) if personas else 0,
                "avg_coupon_affinity": sum(p.coupon_behavior.coupon_affinity for p in personas) / len(personas) if personas else 0,
            },
            "personas": [p.to_dict() for p in personas],
        }

        with open(filepath, "w") as f:
            json.dump(preview_data, f, indent=2)

        console.print(f"[dim]Preview JSON saved to: {filepath}[/dim]")


def show_cost_estimate(provider: str, model: str, num_personas: int, estimated_cost: float) -> None:
    """Show LLM cost estimate."""
    console.print()
    console.print(
        Panel(
            f"[bold]Provider:[/bold] {provider}\n[bold]Model:[/bold] {model}\n[bold]Personas:[/bold] {num_personas}\n[bold]Estimated Cost:[/bold] [yellow]${estimated_cost:.2f} USD[/yellow]",
            title="[bold cyan]LLM Generation Estimate[/bold cyan]",
            border_style="cyan",
        )
    )


def show_cost_summary(cost_summary: dict, total_duration: float) -> None:
    """
    Display actual cost and time tracking from generation.

    Args:
        cost_summary: Dict with total_cost_usd, total_tokens, total_time_seconds, avg_cost_per_persona,
                     avg_time_per_persona, per_persona_details
        total_duration: Total wall-clock time for generation in seconds
    """
    console.print()
    console.print(
        Panel(
            f"[bold]Total Cost:[/bold] [yellow]${cost_summary['total_cost_usd']:.4f} USD[/yellow]\n"
            f"[bold]Total Tokens:[/bold] {cost_summary['total_tokens']:,}\n"
            f"[bold]Total Time:[/bold] {total_duration:.1f}s ({cost_summary['total_time_seconds']:.1f}s API time)\n"
            f"[bold]Avg Cost/Persona:[/bold] ${cost_summary['avg_cost_per_persona']:.4f}\n"
            f"[bold]Avg Time/Persona:[/bold] {cost_summary['avg_time_per_persona']:.1f}s",
            title="[bold cyan]Generation Cost & Time Summary[/bold cyan]",
            border_style="green",
        )
    )

    # Show per-persona breakdown
    if cost_summary.get("per_persona_details"):
        table = Table(title="[bold]Per-Persona Details[/bold]")
        table.add_column("Agent ID", style="cyan", width=12)
        table.add_column("Model", style="white", width=25)
        table.add_column("Tokens", justify="right", style="white", width=10)
        table.add_column("Cost (USD)", justify="right", style="yellow", width=12)
        table.add_column("Time (s)", justify="right", style="white", width=10)

        for detail in cost_summary["per_persona_details"]:
            # Shorten model name for display
            model_name = detail["model"].split("/")[-1][:25]
            table.add_row(
                detail["agent_id"],
                model_name,
                f"{detail['total_tokens']:,}",
                f"${detail['cost_usd']:.4f}",
                f"{detail['time_seconds']:.1f}",
            )

        console.print(table)
