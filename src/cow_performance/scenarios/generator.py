"""Interactive configuration generator for creating scenario YAML files.

This module provides an interactive CLI wizard to help users create
scenario configurations without manually writing YAML.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from rich.console import Console
from rich.prompt import Confirm, FloatPrompt, IntPrompt, Prompt

from .templates import TemplateExpander


class ConfigGenerator:
    """Interactive wizard for generating scenario configurations."""

    def __init__(self, console: Console | None = None):
        """Initialize the config generator.

        Args:
            console: Rich console for output (default: create new Console)
        """
        self.console = console or Console()
        self.template_expander = TemplateExpander()

    def generate(self, output_path: Path, mode: str = "interactive") -> dict[str, Any]:
        """Generate a scenario configuration.

        Args:
            output_path: Path where the config will be saved
            mode: Generation mode (quick, template, existing, advanced, interactive)

        Returns:
            Generated configuration dictionary

        Raises:
            ValueError: If mode is invalid
        """
        if mode == "interactive":
            return self._interactive_mode(output_path)
        elif mode == "quick":
            return self._quick_start_mode(output_path)
        elif mode == "template":
            return self._template_mode(output_path)
        elif mode == "existing":
            return self._copy_existing_mode(output_path)
        elif mode == "advanced":
            return self._advanced_mode(output_path)
        else:
            raise ValueError(f"Invalid mode: {mode}")

    def _interactive_mode(self, output_path: Path) -> dict[str, Any]:
        """Interactive mode: ask user which approach to use.

        Args:
            output_path: Path where config will be saved

        Returns:
            Generated configuration
        """
        self.console.print("\n[bold cyan]🎯 Create New Performance Test Scenario[/bold cyan]\n")

        choices = [
            "Quick start (minimal config)",
            "From template (ramp-up, spike, sustained)",
            "From existing scenario (customize a predefined one)",
            "Advanced (full configuration)",
        ]

        self.console.print("[bold]Choose a starting point:[/bold]")
        for i, choice in enumerate(choices, 1):
            self.console.print(f"  {i}. {choice}")

        selection = IntPrompt.ask(
            "\nYour choice",
            console=self.console,
            choices=["1", "2", "3", "4"],
            default=1,
        )

        if selection == 1:
            return self._quick_start_mode(output_path)
        elif selection == 2:
            return self._template_mode(output_path)
        elif selection == 3:
            return self._copy_existing_mode(output_path)
        else:
            return self._advanced_mode(output_path)

    def _quick_start_mode(self, output_path: Path) -> dict[str, Any]:
        """Quick start mode: minimal questions for simple config.

        Args:
            output_path: Path where config will be saved

        Returns:
            Generated configuration
        """
        self.console.print("\n[bold cyan]⚡ Quick Start Mode[/bold cyan]")
        self.console.print("Answer a few questions to create a basic load test.\n")

        # Basic info
        name = Prompt.ask(
            "Scenario name",
            console=self.console,
            default=output_path.stem.replace("-", " ").title(),
        )

        description = Prompt.ask(
            "Description (optional)",
            console=self.console,
            default=f"Performance test: {name}",
        )

        # Test parameters
        num_traders = IntPrompt.ask(
            "Number of concurrent traders",
            console=self.console,
            default=10,
        )

        duration = IntPrompt.ask(
            "Test duration (seconds)",
            console=self.console,
            default=60,
        )

        orders_per_minute = FloatPrompt.ask(
            "Target orders per minute (per trader)",
            console=self.console,
            default=60.0,
        )

        # Build config
        config = {
            "name": name,
            "description": description,
            "version": "1.0",
            "tags": ["quick-start", "test"],
            "num_traders": num_traders,
            "duration": duration,
            "startup_interval": 0.1,
            "trading_pattern": "constant_rate",
            "base_rate": orders_per_minute,
            "market_order_ratio": 0.6,
            "limit_order_ratio": 0.4,
            "twap_order_ratio": 0.0,
            "stop_loss_order_ratio": 0.0,
            "good_after_time_order_ratio": 0.0,
        }

        return config

    def _template_mode(self, output_path: Path) -> dict[str, Any]:
        """Template mode: generate from a template with parameters.

        Args:
            output_path: Path where config will be saved

        Returns:
            Generated configuration
        """
        self.console.print("\n[bold cyan]📋 Template Mode[/bold cyan]\n")

        # List available templates
        templates: list[tuple[str, str]] = []
        for template_dir in self.template_expander.template_dirs:
            if not template_dir.exists():
                continue

            for pattern in ["*.template.yml", "*.yml"]:
                for template_file in template_dir.glob(pattern):
                    template_name = template_file.stem
                    if template_name.endswith(".template"):
                        template_name = template_name[: -len(".template")]

                    if template_name not in [t[0] for t in templates]:
                        try:
                            template_data = self.template_expander.load_template(template_name)
                            metadata = template_data.get("template_metadata", {})
                            description = metadata.get("description", "No description")
                            templates.append((template_name, description))
                        except Exception:
                            pass

        if not templates:
            self.console.print("[yellow]No templates found. Using quick start mode.[/yellow]")
            return self._quick_start_mode(output_path)

        # Show templates
        self.console.print("[bold]Available Templates:[/bold]")
        for i, (name, desc) in enumerate(templates, 1):
            self.console.print(f"  {i}. [green]{name}[/green] - {desc}")

        # Select template
        choice = IntPrompt.ask(
            "\nSelect template",
            console=self.console,
            choices=[str(i) for i in range(1, len(templates) + 1)],
            default=1,
        )

        template_name, _ = templates[int(choice) - 1]

        # Load template metadata to get parameters
        template_data = self.template_expander.load_template(template_name)
        metadata = template_data.get("template_metadata", {})
        param_specs = metadata.get("parameters", [])

        self.console.print(f"\n[bold cyan]⚙️  Template Parameters: {template_name}[/bold cyan]\n")

        # Collect parameters
        parameters: dict[str, Any] = {}
        for param_spec in param_specs:
            param_name = param_spec.get("name")
            param_type = param_spec.get("type", "string")
            param_desc = param_spec.get("description", "")
            param_required = param_spec.get("required", False)
            param_default = param_spec.get("default")

            # Build prompt text
            prompt_text = param_name.replace("_", " ").title()
            if param_desc:
                prompt_text = f"{prompt_text} ({param_desc})"

            # Prompt based on type
            try:
                if param_type == "int":
                    if param_required and param_default is None:
                        int_value = IntPrompt.ask(prompt_text, console=self.console)
                    else:
                        default_int = int(param_default) if param_default is not None else 10
                        int_value = IntPrompt.ask(
                            prompt_text,
                            console=self.console,
                            default=default_int,
                        )
                    parameters[param_name] = int_value

                elif param_type == "float":
                    if param_required and param_default is None:
                        float_value = FloatPrompt.ask(prompt_text, console=self.console)
                    else:
                        default_float = float(param_default) if param_default is not None else 1.0
                        float_value = FloatPrompt.ask(
                            prompt_text,
                            console=self.console,
                            default=default_float,
                        )
                    parameters[param_name] = float_value

                else:  # string
                    if param_required and param_default is None:
                        str_value = Prompt.ask(prompt_text, console=self.console)
                    else:
                        default_str = str(param_default) if param_default is not None else ""
                        str_value = Prompt.ask(
                            prompt_text,
                            console=self.console,
                            default=default_str,
                        )
                    if str_value:  # Only add if not empty
                        parameters[param_name] = str_value

            except Exception as e:
                self.console.print(f"[yellow]Skipping parameter {param_name}: {e}[/yellow]")

        # Expand template
        try:
            expanded = self.template_expander.expand_template(template_name, parameters)
            return expanded
        except Exception as e:
            self.console.print(f"[red]Failed to expand template: {e}[/red]")
            self.console.print("[yellow]Falling back to quick start mode.[/yellow]")
            return self._quick_start_mode(output_path)

    def _copy_existing_mode(self, output_path: Path) -> dict[str, Any]:
        """Copy from existing mode: customize a predefined scenario.

        Args:
            output_path: Path where config will be saved

        Returns:
            Generated configuration
        """
        self.console.print("\n[bold cyan]📂 Copy From Existing Scenario[/bold cyan]\n")

        # Look for predefined scenarios
        scenarios_dir = Path("configs/scenarios")
        if not scenarios_dir.exists():
            self.console.print(
                "[yellow]No predefined scenarios found. Using quick start mode.[/yellow]"
            )
            return self._quick_start_mode(output_path)

        # Find scenario files
        scenario_files = list(scenarios_dir.rglob("*.yml")) + list(scenarios_dir.rglob("*.yaml"))

        if not scenario_files:
            self.console.print("[yellow]No scenario files found. Using quick start mode.[/yellow]")
            return self._quick_start_mode(output_path)

        # Show scenarios
        self.console.print("[bold]Available Scenarios:[/bold]")
        for i, scenario_file in enumerate(scenario_files[:10], 1):  # Limit to 10
            rel_path = scenario_file.relative_to(scenarios_dir)
            self.console.print(f"  {i}. {rel_path}")

        # Select scenario
        choice = IntPrompt.ask(
            "\nSelect scenario to copy",
            console=self.console,
            choices=[str(i) for i in range(1, min(len(scenario_files) + 1, 11))],
            default=1,
        )

        selected_file = scenario_files[int(choice) - 1]

        # Load the scenario
        with open(selected_file) as f:
            loaded_config = yaml.safe_load(f)

        if not isinstance(loaded_config, dict):
            self.console.print("[yellow]Invalid scenario format. Using quick start mode.[/yellow]")
            return self._quick_start_mode(output_path)

        config: dict[str, Any] = loaded_config

        # Ask for modifications
        self.console.print("\n[bold]Customize the scenario:[/bold]")

        new_name = Prompt.ask(
            "New scenario name",
            console=self.console,
            default=config.get("name", ""),
        )
        config["name"] = new_name

        modify_params = Confirm.ask(
            "Modify test parameters (traders, duration, rate)?",
            console=self.console,
            default=False,
        )

        if modify_params:
            config["num_traders"] = IntPrompt.ask(
                "Number of traders",
                console=self.console,
                default=config.get("num_traders", 10),
            )

            config["duration"] = IntPrompt.ask(
                "Duration (seconds)",
                console=self.console,
                default=config.get("duration", 60),
            )

            if "base_rate" in config:
                config["base_rate"] = FloatPrompt.ask(
                    "Base rate (orders/min)",
                    console=self.console,
                    default=config.get("base_rate", 60.0),
                )

        return config

    def _advanced_mode(self, output_path: Path) -> dict[str, Any]:
        """Advanced mode: full configuration wizard.

        Args:
            output_path: Path where config will be saved

        Returns:
            Generated configuration
        """
        self.console.print("\n[bold cyan]🔧 Advanced Configuration Mode[/bold cyan]\n")

        # Start with quick start
        config = self._quick_start_mode(output_path)

        # Add success criteria
        add_criteria = Confirm.ask(
            "\nAdd success criteria?",
            console=self.console,
            default=True,
        )

        if add_criteria:
            config["success_criteria"] = {
                "min_success_rate": FloatPrompt.ask(
                    "Minimum success rate (0-1)",
                    console=self.console,
                    default=0.90,
                ),
                "max_error_rate": FloatPrompt.ask(
                    "Maximum error rate (0-1)",
                    console=self.console,
                    default=0.10,
                ),
            }

        # Add metadata
        add_metadata = Confirm.ask(
            "Add metadata (resource requirements)?",
            console=self.console,
            default=False,
        )

        if add_metadata:
            config["metadata"] = {
                "expected_duration_seconds": config["duration"],
                "resources": {
                    "min_memory_gb": IntPrompt.ask(
                        "Minimum memory (GB)",
                        console=self.console,
                        default=4,
                    ),
                    "recommended_memory_gb": IntPrompt.ask(
                        "Recommended memory (GB)",
                        console=self.console,
                        default=8,
                    ),
                },
            }

        return config

    def save_config(self, config: dict[str, Any], output_path: Path) -> None:
        """Save configuration to YAML file with validation.

        Args:
            config: Configuration dictionary
            output_path: Path to save the file

        Raises:
            ValueError: If configuration is invalid
        """
        # Validate configuration before saving
        self.console.print("\n[dim]Validating configuration...[/dim]")
        try:
            from cow_performance.cli.commands.scenarios import ScenarioConfig

            # Try to parse with Pydantic
            scenario = ScenarioConfig(**config)

            # Run validation methods
            scenario.validate_ratios()
            scenario.validate_pattern_parameters()

            self.console.print("[dim green]✓ Configuration is valid[/dim green]")

        except Exception as e:
            self.console.print(f"[yellow]Warning: Configuration validation failed: {e}[/yellow]")
            self.console.print(
                "[yellow]Saving anyway. Please review and fix before running.[/yellow]"
            )

        # Ensure parent directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Write YAML with comments
        with open(output_path, "w") as f:
            f.write("# Performance Test Scenario Configuration\n")
            f.write("# Generated by cow-perf config init\n\n")
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)

        self.console.print(f"\n[bold green]✓[/bold green] Configuration saved: {output_path}")

    def display_next_steps(self, output_path: Path) -> None:
        """Display next steps for the user.

        Args:
            output_path: Path where config was saved
        """
        self.console.print("\n[bold cyan]Next Steps:[/bold cyan]")
        self.console.print(f"  • Review: [dim]cat {output_path}[/dim]")
        self.console.print(f"  • Validate: [dim]cow-perf scenarios --validate {output_path}[/dim]")
        self.console.print(f"  • Run: [dim]cow-perf run --config {output_path}[/dim]")
