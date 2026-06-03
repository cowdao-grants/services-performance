"""Unit tests for CLI commands."""

from typer.testing import CliRunner

from cow_performance.cli.main import app

runner = CliRunner()


class TestCLI:
    """Test CLI commands."""

    def test_version_command(self) -> None:
        """Test version command."""
        result = runner.invoke(app, ["version"])
        assert result.exit_code == 0
        assert "CoW Performance Testing Suite" in result.stdout
        assert "0.1.0" in result.stdout

    def test_scenarios_command_executes(self) -> None:
        """Test that scenarios command executes and shows directory info."""
        result = runner.invoke(app, ["scenarios"])
        assert result.exit_code == 0
        assert "Scenarios Directory" in result.stdout

    def test_baselines_command_executes(self) -> None:
        """Test that baselines command executes successfully."""
        result = runner.invoke(app, ["baselines"])
        assert result.exit_code == 0
        # Command should execute successfully and show either baselines or empty message
        assert result.stdout is not None

    def test_config_command_executes(self) -> None:
        """Test that config command runs without error."""
        result = runner.invoke(app, ["config", "--template"])
        assert result.exit_code == 0
