"""Tests for scenario configuration and management."""

from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
import yaml

from cow_performance.cli.commands.scenarios import (
    ResourceRequirements,
    ScenarioConfig,
    ScenarioMetadata,
    SuccessCriteria,
    load_scenario_from_yaml,
    save_scenario_to_yaml,
)


class TestResourceRequirements:
    """Test ResourceRequirements model."""

    def test_default_values(self):
        """Test default values are None."""
        resources = ResourceRequirements()
        assert resources.min_memory_gb is None
        assert resources.min_cpu_cores is None
        assert resources.recommended_memory_gb is None
        assert resources.recommended_cpu_cores is None

    def test_valid_requirements(self):
        """Test valid resource requirements."""
        resources = ResourceRequirements(
            min_memory_gb=4.0,
            min_cpu_cores=2,
            recommended_memory_gb=8.0,
            recommended_cpu_cores=4,
        )
        assert resources.min_memory_gb == 4.0
        assert resources.min_cpu_cores == 2
        assert resources.recommended_memory_gb == 8.0
        assert resources.recommended_cpu_cores == 4

    def test_invalid_memory(self):
        """Test negative memory is rejected."""
        with pytest.raises(ValueError):
            ResourceRequirements(min_memory_gb=-1.0)

    def test_invalid_cpu(self):
        """Test zero/negative CPU cores rejected."""
        with pytest.raises(ValueError):
            ResourceRequirements(min_cpu_cores=0)


class TestScenarioMetadata:
    """Test ScenarioMetadata model."""

    def test_default_values(self):
        """Test default values are None."""
        metadata = ScenarioMetadata()
        assert metadata.expected_orders is None
        assert metadata.expected_duration_seconds is None
        assert metadata.resources is None

    def test_valid_metadata(self):
        """Test valid metadata."""
        resources = ResourceRequirements(min_memory_gb=4.0, min_cpu_cores=2)
        metadata = ScenarioMetadata(
            expected_orders=3000,
            expected_duration_seconds=600,
            resources=resources,
        )
        assert metadata.expected_orders == 3000
        assert metadata.expected_duration_seconds == 600
        assert metadata.resources.min_memory_gb == 4.0

    def test_invalid_expected_orders(self):
        """Test negative expected orders rejected."""
        with pytest.raises(ValueError):
            ScenarioMetadata(expected_orders=-1)


class TestSuccessCriteria:
    """Test SuccessCriteria model."""

    def test_default_values(self):
        """Test default values are None."""
        criteria = SuccessCriteria()
        assert criteria.min_success_rate is None
        assert criteria.max_p95_latency_seconds is None
        assert criteria.max_error_rate is None
        assert criteria.min_throughput_per_second is None

    def test_valid_criteria(self):
        """Test valid success criteria."""
        criteria = SuccessCriteria(
            min_success_rate=0.95,
            max_p95_latency_seconds=10.0,
            max_error_rate=0.05,
            min_throughput_per_second=5.0,
        )
        assert criteria.min_success_rate == 0.95
        assert criteria.max_p95_latency_seconds == 10.0
        assert criteria.max_error_rate == 0.05
        assert criteria.min_throughput_per_second == 5.0

    def test_invalid_success_rate(self):
        """Test success rate must be 0-1."""
        with pytest.raises(ValueError):
            SuccessCriteria(min_success_rate=1.5)

        with pytest.raises(ValueError):
            SuccessCriteria(min_success_rate=-0.1)

    def test_invalid_latency(self):
        """Test latency must be positive."""
        with pytest.raises(ValueError):
            SuccessCriteria(max_p95_latency_seconds=0.0)


class TestScenarioConfig:
    """Test ScenarioConfig model."""

    def test_minimal_scenario(self):
        """Test scenario with only required fields."""
        scenario = ScenarioConfig(name="test-scenario")
        assert scenario.name == "test-scenario"
        assert scenario.description == ""
        assert scenario.version == "1.0"
        assert scenario.tags == []
        assert scenario.metadata is None
        assert scenario.success_criteria is None

    def test_scenario_with_all_fields(self):
        """Test scenario with all optional fields."""
        resources = ResourceRequirements(min_memory_gb=4.0, min_cpu_cores=2)
        metadata = ScenarioMetadata(expected_orders=3000, resources=resources)
        criteria = SuccessCriteria(
            min_success_rate=0.95,
            max_p95_latency_seconds=10.0,
        )

        scenario = ScenarioConfig(
            name="complete-scenario",
            description="A complete test scenario",
            version="2.0",
            tags=["stress", "baseline"],
            metadata=metadata,
            success_criteria=criteria,
            num_traders=20,
            duration=600,
        )

        assert scenario.name == "complete-scenario"
        assert scenario.version == "2.0"
        assert "stress" in scenario.tags
        assert scenario.metadata.expected_orders == 3000
        assert scenario.success_criteria.min_success_rate == 0.95

    def test_validate_ratios_valid(self):
        """Test ratio validation with valid ratios."""
        scenario = ScenarioConfig(
            name="test",
            market_order_ratio=0.4,
            limit_order_ratio=0.4,
            twap_order_ratio=0.1,
            stop_loss_order_ratio=0.05,
            good_after_time_order_ratio=0.05,
        )
        # Should not raise
        scenario.validate_ratios()

    def test_validate_ratios_invalid(self):
        """Test ratio validation with invalid ratios."""
        scenario = ScenarioConfig(
            name="test",
            market_order_ratio=0.5,
            limit_order_ratio=0.5,
            twap_order_ratio=0.1,
            stop_loss_order_ratio=0.05,
            good_after_time_order_ratio=0.05,
        )
        with pytest.raises(ValueError, match="must sum to 1.0"):
            scenario.validate_ratios()


class TestScenarioYAMLOperations:
    """Test YAML loading and saving operations."""

    def test_load_minimal_scenario(self):
        """Test loading a minimal scenario from YAML."""
        yaml_content = """
name: test-scenario
description: A test scenario
num_traders: 10
duration: 60
"""
        with TemporaryDirectory() as tmpdir:
            scenario_path = Path(tmpdir) / "test.yml"
            scenario_path.write_text(yaml_content)

            scenario = load_scenario_from_yaml(scenario_path)
            assert scenario.name == "test-scenario"
            assert scenario.num_traders == 10
            assert scenario.duration == 60

    def test_load_scenario_with_new_fields(self):
        """Test loading a scenario with tags, metadata, and success criteria."""
        yaml_content = """
name: enhanced-scenario
description: Enhanced test scenario
version: "2.0"
tags:
  - stress
  - baseline
  - medium-load

metadata:
  expected_orders: 3000
  expected_duration_seconds: 600
  resources:
    min_memory_gb: 4.0
    min_cpu_cores: 2

success_criteria:
  min_success_rate: 0.95
  max_p95_latency_seconds: 10.0
  max_error_rate: 0.05

num_traders: 20
duration: 600
trading_pattern: constant_rate
base_rate: 300.0
market_order_ratio: 0.7
limit_order_ratio: 0.3
twap_order_ratio: 0.0
stop_loss_order_ratio: 0.0
good_after_time_order_ratio: 0.0
"""
        with TemporaryDirectory() as tmpdir:
            scenario_path = Path(tmpdir) / "enhanced.yml"
            scenario_path.write_text(yaml_content)

            scenario = load_scenario_from_yaml(scenario_path)
            assert scenario.name == "enhanced-scenario"
            assert scenario.version == "2.0"
            assert "stress" in scenario.tags
            assert "baseline" in scenario.tags
            assert scenario.metadata is not None
            assert scenario.metadata.expected_orders == 3000
            assert scenario.metadata.resources.min_memory_gb == 4.0
            assert scenario.success_criteria is not None
            assert scenario.success_criteria.min_success_rate == 0.95

    def test_backward_compatibility(self):
        """Test loading old scenario format without new fields."""
        # Old format scenario (before tags/metadata/success_criteria)
        yaml_content = """
name: old-scenario
description: Old format scenario
num_traders: 5
duration: 120
trading_pattern: constant_rate
base_rate: 60.0
market_order_ratio: 0.5
limit_order_ratio: 0.5
twap_order_ratio: 0.0
stop_loss_order_ratio: 0.0
good_after_time_order_ratio: 0.0
"""
        with TemporaryDirectory() as tmpdir:
            scenario_path = Path(tmpdir) / "old.yml"
            scenario_path.write_text(yaml_content)

            scenario = load_scenario_from_yaml(scenario_path)
            assert scenario.name == "old-scenario"
            assert scenario.num_traders == 5
            # New fields should have defaults
            assert scenario.version == "1.0"
            assert scenario.tags == []
            assert scenario.metadata is None
            assert scenario.success_criteria is None

    def test_save_and_load_roundtrip(self):
        """Test saving and loading a scenario preserves data."""
        resources = ResourceRequirements(min_memory_gb=4.0, min_cpu_cores=2)
        metadata = ScenarioMetadata(expected_orders=3000, resources=resources)
        criteria = SuccessCriteria(
            min_success_rate=0.95,
            max_p95_latency_seconds=10.0,
        )

        original = ScenarioConfig(
            name="roundtrip-test",
            description="Test roundtrip",
            version="1.5",
            tags=["test", "roundtrip"],
            metadata=metadata,
            success_criteria=criteria,
            num_traders=15,
            duration=300,
        )

        with TemporaryDirectory() as tmpdir:
            scenario_path = Path(tmpdir) / "roundtrip.yml"
            save_scenario_to_yaml(original, scenario_path)

            loaded = load_scenario_from_yaml(scenario_path)
            assert loaded.name == original.name
            assert loaded.version == original.version
            assert loaded.tags == original.tags
            assert loaded.metadata.expected_orders == original.metadata.expected_orders
            assert (
                loaded.success_criteria.min_success_rate
                == original.success_criteria.min_success_rate
            )

    def test_load_nonexistent_file(self):
        """Test loading a nonexistent file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            load_scenario_from_yaml(Path("/nonexistent/scenario.yml"))

    def test_load_empty_file(self):
        """Test loading an empty file raises ValueError."""
        with TemporaryDirectory() as tmpdir:
            scenario_path = Path(tmpdir) / "empty.yml"
            scenario_path.write_text("")

            with pytest.raises(ValueError, match="empty"):
                load_scenario_from_yaml(scenario_path)

    def test_load_invalid_yaml(self):
        """Test loading invalid YAML raises error."""
        with TemporaryDirectory() as tmpdir:
            scenario_path = Path(tmpdir) / "invalid.yml"
            scenario_path.write_text("{ invalid yaml:")

            with pytest.raises(yaml.YAMLError):
                load_scenario_from_yaml(scenario_path)
