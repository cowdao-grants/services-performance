"""
End-to-end tests for the CLI run command.

These tests verify that the CLI can successfully orchestrate multiple traders
and submit orders to the orderbook API.
"""

import json
import subprocess
import tempfile
from pathlib import Path

import pytest

from tests.e2e.conftest import ORDERBOOK_API_URL


class TestCLIRun:
    """E2E tests for the CLI run command."""

    @pytest.mark.e2e
    def test_cli_run_dry_run_mode(self) -> None:
        """Test CLI run command in dry-run mode (no API submission)."""
        # Run with minimal parameters in dry-run mode (no API submission)
        result = subprocess.run(
            [
                ".venv/bin/cow-perf",
                "run",
                "--traders",
                "2",
                "--duration",
                "3",
                "--dry-run",
                "--verbose",
                "--format",
                "json",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

        # Check command succeeded
        assert result.returncode == 0, f"Command failed: {result.stderr}"

        # Parse output to find JSON results (may be multi-line or have Rich/ANSI prefix)
        json_output = None
        stdout = result.stdout
        start = stdout.find("{")
        if start != -1:
            depth = 0
            end = -1
            for i in range(start, len(stdout)):
                if stdout[i] == "{":
                    depth += 1
                elif stdout[i] == "}":
                    depth -= 1
                    if depth == 0:
                        end = i + 1
                        break
            if end != -1:
                try:
                    json_output = json.loads(stdout[start:end])
                except json.JSONDecodeError:
                    pass

        # Verify we got metrics
        assert json_output is not None, "No JSON output found"
        assert "orchestration" in json_output
        assert "orders" in json_output
        assert "performance" in json_output

        # Verify orchestration config
        assert json_output["orchestration"]["num_traders"] == 2
        assert json_output["orchestration"]["duration"] == 3

        # Verify orders were generated
        assert json_output["orders"]["total_submitted"] > 0

    @pytest.mark.e2e
    def test_cli_run_with_config_file(self) -> None:
        """Test CLI run command with custom config file."""
        # Create temporary config file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as config_file:
            config_content = f"""
network:
  chain_id: 1
  rpc_url: "http://localhost:8545"
  settlement_contract: "0x9008D19f58AAbD9eD0D60971565AA8510560ab41"
  composable_cow_contract: "0xfdaFc9d1902f4e0b84f65F49f244b32b31013b74"

api:
  base_url: "{ORDERBOOK_API_URL}"
  timeout: 30
  max_retries: 3

output:
  format: "json"
  verbose: false
  save_results: false

default_trader_count: 2
default_duration: 3

market_order_ratio: 1.0
limit_order_ratio: 0.0
twap_order_ratio: 0.0
stop_loss_order_ratio: 0.0
good_after_time_order_ratio: 0.0
"""
            config_file.write(config_content)
            config_path = config_file.name

        try:
            # Run with config file in dry-run mode
            result = subprocess.run(
                [
                    ".venv/bin/cow-perf",
                    "run",
                    "--config",
                    config_path,
                    "--format",
                    "json",
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )

            # Check command succeeded
            assert result.returncode == 0, f"Command failed: {result.stderr}"

            # Verify output contains expected data
            assert "Test Results:" in result.stdout or "{" in result.stdout

        finally:
            # Clean up config file
            Path(config_path).unlink()

    @pytest.mark.e2e
    def test_cli_run_with_results_save(self) -> None:
        """Test CLI run command with results saving."""
        with tempfile.TemporaryDirectory() as tmpdir:
            results_file = Path(tmpdir) / "results.json"

            # Run and save results (--output = file path, --format = display/save format)
            result = subprocess.run(
                [
                    ".venv/bin/cow-perf",
                    "run",
                    "--traders",
                    "2",
                    "--duration",
                    "3",
                    "--settlement-wait",
                    "0",
                    "--format",
                    "json",
                    "--output",
                    str(results_file),
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )

            # Check command succeeded
            assert result.returncode == 0, f"Command failed: {result.stderr}"

            # Verify results file was created
            assert results_file.exists(), "Results file was not created"

            # Verify results file contains valid JSON
            with open(results_file) as f:
                results = json.load(f)
                assert "orchestration" in results
                assert "orders" in results
                assert "performance" in results

    @pytest.mark.e2e
    def test_cli_run_table_output(self) -> None:
        """Test CLI run command with table output format."""
        result = subprocess.run(
            [
                ".venv/bin/cow-perf",
                "run",
                "--traders",
                "2",
                "--duration",
                "3",
                "--settlement-wait",
                "0",
                "--format",
                "table",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

        # Check command succeeded
        assert result.returncode == 0, f"Command failed: {result.stderr}"

        # Verify table output contains expected headers
        assert "Test Results:" in result.stdout
        # Table format uses Rich library, so we look for key metrics
        assert "traders" in result.stdout.lower() or "Traders" in result.stdout

    @pytest.mark.e2e
    @pytest.mark.skip(reason="Requires running orderbook API")
    def test_cli_run_with_real_api_submission(self) -> None:
        """Test CLI run command with real order submission to API.

        This test requires:
        - Running docker-compose environment
        - Orderbook API at localhost:8080
        - Funded trader accounts with token approvals
        """
        # Create config that points to local API
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as config_file:
            config_content = f"""
network:
  chain_id: 1
  rpc_url: "http://localhost:8545"
  settlement_contract: "0x9008D19f58AAbD9eD0D60971565AA8510560ab41"

api:
  base_url: "{ORDERBOOK_API_URL}"
  timeout: 30
  max_retries: 3

output:
  format: "json"

default_trader_count: 1
default_duration: 5

market_order_ratio: 1.0
limit_order_ratio: 0.0
twap_order_ratio: 0.0
stop_loss_order_ratio: 0.0
good_after_time_order_ratio: 0.0
"""
            config_file.write(config_content)
            config_path = config_file.name

        try:
            # Run with real API (not dry-run)
            result = subprocess.run(
                [
                    ".venv/bin/cow-perf",
                    "run",
                    "--config",
                    config_path,
                    "--verbose",
                    "--format",
                    "json",
                ],
                capture_output=True,
                text=True,
                timeout=60,
            )

            # Note: This will likely fail because traders won't have funded accounts
            # or token approvals. This test is more for documentation of how it
            # would work in a fully set up environment.

            # Check if API connection was attempted
            assert "Orderbook API" in result.stdout or "API" in result.stdout

        finally:
            # Clean up config file
            Path(config_path).unlink()
