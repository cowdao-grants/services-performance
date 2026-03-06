"""Integration tests for CLI functionality.

These tests verify the CLI commands work end-to-end without requiring
external services like RPC endpoints or APIs.
"""

import json
import tempfile
from collections.abc import Generator
from pathlib import Path

import pytest
import yaml  # type: ignore[import-untyped]
from typer.testing import CliRunner

from cow_performance.cli.main import app

runner = CliRunner()


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


class TestConfigCommand:
    """Integration tests for config command."""

    def test_save_config_template(self, temp_dir: Path) -> None:
        """Test saving configuration template to file."""
        output_path = temp_dir / "new-config.yml"

        result = runner.invoke(app, ["config", "--save-template", str(output_path)])

        assert result.exit_code == 0, f"Failed with stdout: {result.stdout}"
        assert output_path.exists()

        # Verify the template is valid YAML
        with open(output_path) as f:
            config_data = yaml.safe_load(f)
        assert "network" in config_data
        assert "api" in config_data

    def test_show_config_template(self) -> None:
        """Test showing configuration template."""
        result = runner.invoke(app, ["config", "--template"])

        assert result.exit_code == 0
        assert "Configuration Template" in result.stdout


class TestScenariosCommand:
    """Integration tests for scenarios command."""

    def test_create_scenario_template(self, temp_dir: Path) -> None:
        """Test creating scenario template."""
        scenario_path = temp_dir / "new-scenario.yml"

        result = runner.invoke(app, ["scenarios", "--create-template", str(scenario_path)])

        assert result.exit_code == 0
        assert scenario_path.exists()

        # Verify the template is valid YAML
        with open(scenario_path) as f:
            scenario_data = yaml.safe_load(f)
        assert "name" in scenario_data
        assert "trading_pattern" in scenario_data

    def test_list_scenarios_empty(self, temp_dir: Path) -> None:
        """Test listing scenarios when directory is empty."""
        result = runner.invoke(app, ["scenarios", "--dir", str(temp_dir)])

        assert result.exit_code == 0


class TestBaselinesCommand:
    """Integration tests for baselines command."""

    def test_list_baselines_empty(self, temp_dir: Path) -> None:
        """Test listing baselines when none exist."""
        result = runner.invoke(app, ["baselines", "--dir", str(temp_dir)])

        assert result.exit_code == 0
        assert "No baselines found" in result.stdout

    def test_save_from_file_deprecated(self, temp_dir: Path) -> None:
        """Test that saving from file is deprecated and returns error."""
        baselines_dir = temp_dir / "baselines"
        results_file = temp_dir / "results.json"

        # Create mock results file
        results_data = {
            "orchestration": {"num_traders": 5, "duration": 2},
            "orders": {"total_submitted": 10, "market_orders": 5},
            "performance": {"orders_per_second": 5.0},
        }
        with open(results_file, "w") as f:
            json.dump(results_data, f)

        # Save baseline - should fail with deprecation message
        save_arg = f"test-v1:{results_file}"
        result = runner.invoke(
            app,
            ["baselines", "--save", save_arg, "--dir", str(baselines_dir)],
        )

        # Now returns error since file-based save is deprecated
        assert result.exit_code == 1
        assert (
            "deprecated" in result.stdout.lower() or "no longer supported" in result.stdout.lower()
        )

    def test_show_baseline_not_found(self, temp_dir: Path) -> None:
        """Test showing a non-existent baseline."""
        baselines_dir = temp_dir / "baselines"
        baselines_dir.mkdir(parents=True, exist_ok=True)

        # Show baseline that doesn't exist
        result = runner.invoke(
            app, ["baselines", "--show", "nonexistent", "--dir", str(baselines_dir)]
        )

        assert result.exit_code == 2  # FileNotFoundError exit code
        assert "not found" in result.stdout.lower()

    def test_delete_baseline_not_found(self, temp_dir: Path) -> None:
        """Test deleting a non-existent baseline."""
        baselines_dir = temp_dir / "baselines"
        baselines_dir.mkdir(parents=True, exist_ok=True)

        # Delete baseline that doesn't exist
        result = runner.invoke(
            app,
            ["baselines", "--delete", "nonexistent", "--dir", str(baselines_dir)],
        )

        assert result.exit_code == 2  # FileNotFoundError exit code
        assert "not found" in result.stdout.lower()


class TestEndToEndWorkflow:
    """Integration tests for complete workflows."""

    def test_complete_config_and_scenario_workflow(self, temp_dir: Path) -> None:
        """Test complete workflow: create config, create scenario, validate."""
        # Step 1: Create config file
        config_path = temp_dir / "config.yml"
        result = runner.invoke(app, ["config", "--save-template", str(config_path)])
        assert result.exit_code == 0
        assert config_path.exists()

        # Step 2: Create scenario file
        scenario_path = temp_dir / "scenario.yml"
        result = runner.invoke(app, ["scenarios", "--create-template", str(scenario_path)])
        assert result.exit_code == 0
        assert scenario_path.exists()

        # Step 3: Validate scenario
        result = runner.invoke(app, ["scenarios", "--validate", str(scenario_path)])
        assert result.exit_code == 0

        # Note: Baseline saving from file is deprecated.
        # Baselines are now saved directly from test runs using
        # 'cow-perf run --save-baseline <name>' with a MetricsStore.
        # See COW-588 for details on the new baseline system.
