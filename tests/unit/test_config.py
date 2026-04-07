"""Unit tests for configuration system."""

import os
import tempfile
from pathlib import Path

import pytest
import yaml  # type: ignore[import-untyped]
from pytest import MonkeyPatch

from cow_performance.cli.config import (
    APIConfig,
    NetworkConfig,
    OutputConfig,
    PerformanceTestConfig,
    find_config_file,
    load_config,
    load_config_from_yaml,
    save_config_template,
)


class TestNetworkConfig:
    """Tests for NetworkConfig."""

    def test_default_values(self) -> None:
        """Test that default values are set correctly."""
        config = NetworkConfig()
        assert config.chain_id == 1
        assert config.rpc_url == "https://eth.llamarpc.com"
        assert config.settlement_contract == "0x9008D19f58AAbD9eD0D60971565AA8510560ab41"

    def test_custom_values(self) -> None:
        """Test that custom values can be set."""
        config = NetworkConfig(
            chain_id=100,
            rpc_url="https://rpc.gnosischain.com",
            settlement_contract="0x1234567890123456789012345678901234567890",
        )
        assert config.chain_id == 100
        assert config.rpc_url == "https://rpc.gnosischain.com"
        assert config.settlement_contract == "0x1234567890123456789012345678901234567890"

    def test_env_var_override(self, monkeypatch: MonkeyPatch) -> None:
        """Test that environment variables override defaults."""
        monkeypatch.setenv("COW_NETWORK_CHAIN_ID", "100")
        monkeypatch.setenv("COW_NETWORK_RPC_URL", "https://custom-rpc.com")

        config = NetworkConfig()
        assert config.chain_id == 100
        assert config.rpc_url == "https://custom-rpc.com"


class TestAPIConfig:
    """Tests for APIConfig."""

    def test_default_values(self) -> None:
        """Test that default values are set correctly."""
        config = APIConfig()
        assert config.base_url == "http://localhost:8080"
        assert config.timeout == 30
        assert config.max_retries == 3

    def test_custom_values(self) -> None:
        """Test that custom values can be set."""
        config = APIConfig(
            base_url="https://api.cow.fi",
            timeout=60,
            max_retries=5,
        )
        assert config.base_url == "https://api.cow.fi"
        assert config.timeout == 60
        assert config.max_retries == 5

    def test_env_var_override(self, monkeypatch: MonkeyPatch) -> None:
        """Test that environment variables override defaults."""
        monkeypatch.setenv("COW_API_BASE_URL", "https://custom-api.com")
        monkeypatch.setenv("COW_API_TIMEOUT", "120")

        config = APIConfig()
        assert config.base_url == "https://custom-api.com"
        assert config.timeout == 120


class TestOutputConfig:
    """Tests for OutputConfig."""

    def test_default_values(self) -> None:
        """Test that default values are set correctly."""
        config = OutputConfig()
        assert config.format == "json"
        assert config.verbose is False
        assert config.save_results is False
        assert config.results_dir == Path(".cow-perf") / "results"

    def test_custom_values(self) -> None:
        """Test that custom values can be set."""
        config = OutputConfig(
            format="table",
            verbose=True,
            save_results=True,
            results_dir=Path("/tmp/results"),
        )
        assert config.format == "table"
        assert config.verbose is True
        assert config.save_results is True
        assert config.results_dir == Path("/tmp/results")

    def test_invalid_format_raises_error(self) -> None:
        """Test that invalid format raises error."""
        with pytest.raises(ValueError, match="Output format must be one of"):
            OutputConfig(format="invalid")

    def test_valid_formats(self) -> None:
        """Test that all valid formats are accepted."""
        for fmt in ["json", "table", "csv", "prometheus"]:
            config = OutputConfig(format=fmt)
            assert config.format == fmt


class TestPerformanceTestConfig:
    """Tests for PerformanceTestConfig."""

    def test_default_values(self) -> None:
        """Test that default values are set correctly."""
        config = PerformanceTestConfig()
        assert config.default_trader_count == 10
        assert config.default_duration == 60
        assert config.default_startup_interval == 0.1
        assert config.market_order_ratio == 0.5
        assert config.limit_order_ratio == 0.5

    def test_nested_config_defaults(self) -> None:
        """Test that nested configs have correct defaults."""
        config = PerformanceTestConfig()
        assert isinstance(config.network, NetworkConfig)
        assert isinstance(config.api, APIConfig)
        assert isinstance(config.output, OutputConfig)

    def test_custom_values(self) -> None:
        """Test that custom values can be set."""
        config = PerformanceTestConfig(
            default_trader_count=20,
            default_duration=120,
            market_order_ratio=0.5,
            limit_order_ratio=0.5,
        )
        assert config.default_trader_count == 20
        assert config.default_duration == 120
        assert config.market_order_ratio == 0.5
        assert config.limit_order_ratio == 0.5

    def test_validate_ratio_sum_valid(self) -> None:
        """Test that valid ratio sum passes validation."""
        config = PerformanceTestConfig(
            market_order_ratio=0.6,
            limit_order_ratio=0.4,
        )
        config.validate_ratio_sum()  # Should not raise

    def test_validate_ratio_sum_invalid(self) -> None:
        """Test that invalid ratio sum raises error."""
        config = PerformanceTestConfig(
            market_order_ratio=0.5,
            limit_order_ratio=0.3,
        )
        with pytest.raises(ValueError, match="must sum to 1.0"):
            config.validate_ratio_sum()

    def test_ratio_bounds_validation(self) -> None:
        """Test that ratio bounds are validated."""
        with pytest.raises(ValueError):
            PerformanceTestConfig(market_order_ratio=-0.1)

        with pytest.raises(ValueError):
            PerformanceTestConfig(market_order_ratio=1.5)


class TestConfigFileOperations:
    """Tests for config file operations."""

    def test_save_config_template(self) -> None:
        """Test saving config template."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test-config.yml"
            save_config_template(output_path)

            assert output_path.exists()

            # Verify it's valid YAML
            with open(output_path) as f:
                config_data = yaml.safe_load(f)

            assert "network" in config_data
            assert "api" in config_data
            assert "output" in config_data

    def test_load_config_from_yaml(self) -> None:
        """Test loading config from YAML file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "test-config.yml"

            # Create test config
            config_data = {
                "default_trader_count": 20,
                "default_duration": 120,
                "network": {
                    "chain_id": 100,
                    "rpc_url": "https://test-rpc.com",
                },
                "api": {
                    "base_url": "https://test-api.com",
                },
            }

            with open(config_path, "w") as f:
                yaml.dump(config_data, f)

            # Load config
            loaded = load_config_from_yaml(config_path)

            assert loaded["default_trader_count"] == 20
            assert loaded["default_duration"] == 120
            assert loaded["network"]["chain_id"] == 100
            assert loaded["api"]["base_url"] == "https://test-api.com"

    def test_load_config_from_yaml_file_not_found(self) -> None:
        """Test that loading from non-existent file raises error."""
        with pytest.raises(FileNotFoundError):
            load_config_from_yaml(Path("/nonexistent/config.yml"))

    def test_load_config_with_yaml_file(self) -> None:
        """Test loading full config from YAML file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "test-config.yml"

            # Create test config with valid ratios
            config_data = {
                "default_trader_count": 20,
                "default_duration": 120,
                "market_order_ratio": 0.5,
                "limit_order_ratio": 0.5,
            }

            with open(config_path, "w") as f:
                yaml.dump(config_data, f)

            # Load config
            config = load_config(config_path)

            assert config.default_trader_count == 20
            assert config.default_duration == 120
            assert config.market_order_ratio == 0.5

    def test_load_config_no_file_uses_defaults(self) -> None:
        """Test that load_config uses defaults when no file is found."""
        config = load_config(None)
        assert config.default_trader_count == 10  # Default value

    def test_find_config_file_local(self) -> None:
        """Test finding config file in current directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Change to temp directory
            original_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)

                # Create local config
                local_config = Path(".cow-perf.yml")
                local_config.touch()

                found = find_config_file()
                assert found == local_config

            finally:
                os.chdir(original_cwd)

    def test_find_config_file_home(self, monkeypatch: MonkeyPatch) -> None:
        """Test finding config file in home directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Mock home directory
            monkeypatch.setattr(Path, "home", lambda: Path(tmpdir))

            # Change to a different directory
            original_cwd = os.getcwd()
            try:
                with tempfile.TemporaryDirectory() as workdir:
                    os.chdir(workdir)

                    # Create home config
                    home_config = Path(tmpdir) / ".cow-perf.yml"
                    home_config.touch()

                    found = find_config_file()
                    assert found == home_config

            finally:
                os.chdir(original_cwd)

    def test_find_config_file_not_found(self) -> None:
        """Test that find_config_file returns None when no config exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            original_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                found = find_config_file()
                assert found is None
            finally:
                os.chdir(original_cwd)


class TestConfigValidation:
    """Tests for configuration validation."""

    def test_invalid_ratio_sum_raises_error(self) -> None:
        """Test that invalid ratio sum is caught by load_config."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "test-config.yml"

            # Create invalid config (ratios don't sum to 1.0)
            config_data = {
                "market_order_ratio": 0.3,
                "limit_order_ratio": 0.3,
            }

            with open(config_path, "w") as f:
                yaml.dump(config_data, f)

            # Should raise ValueError
            with pytest.raises(ValueError, match="must sum to 1.0"):
                load_config(config_path)
