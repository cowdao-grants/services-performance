"""Tests for project defaults loading and configuration precedence."""


import pytest
import yaml

from cow_performance.scenarios.defaults import (
    ConfigurationMerger,
    DefaultsError,
    DefaultsLoader,
    load_with_defaults,
)


class TestDefaultsLoader:
    """Test project defaults loading."""

    def test_load_project_defaults_file_exists(self, tmp_path):
        """Test loading existing project defaults file."""
        defaults_file = tmp_path / ".cow-perf-defaults.yml"
        defaults_file.write_text(
            yaml.dump(
                {
                    "num_traders": 20,
                    "duration": 120,
                    "tags": ["default"],
                }
            )
        )

        loader = DefaultsLoader(project_root=tmp_path)
        result = loader.load_project_defaults()

        assert result == {
            "num_traders": 20,
            "duration": 120,
            "tags": ["default"],
        }

    def test_load_project_defaults_file_not_exists(self, tmp_path):
        """Test loading when defaults file doesn't exist."""
        loader = DefaultsLoader(project_root=tmp_path)
        result = loader.load_project_defaults()

        assert result is None

    def test_load_project_defaults_empty_file(self, tmp_path):
        """Test loading empty defaults file."""
        defaults_file = tmp_path / ".cow-perf-defaults.yml"
        defaults_file.write_text("")

        loader = DefaultsLoader(project_root=tmp_path)
        result = loader.load_project_defaults()

        assert result == {}

    def test_load_project_defaults_invalid_yaml(self, tmp_path):
        """Test error on invalid YAML syntax."""
        defaults_file = tmp_path / ".cow-perf-defaults.yml"
        defaults_file.write_text("invalid: yaml: syntax: error:")

        loader = DefaultsLoader(project_root=tmp_path)

        with pytest.raises(DefaultsError) as exc_info:
            loader.load_project_defaults()

        assert "parse" in str(exc_info.value).lower()

    def test_load_project_defaults_not_dict(self, tmp_path):
        """Test error when defaults file contains non-dict."""
        defaults_file = tmp_path / ".cow-perf-defaults.yml"
        defaults_file.write_text("- item1\n- item2\n")  # YAML list

        loader = DefaultsLoader(project_root=tmp_path)

        with pytest.raises(DefaultsError) as exc_info:
            loader.load_project_defaults()

        assert "must be a dictionary" in str(exc_info.value)

    def test_load_project_defaults_nested_structure(self, tmp_path):
        """Test loading defaults with nested structure."""
        defaults_file = tmp_path / ".cow-perf-defaults.yml"
        defaults_file.write_text(
            yaml.dump(
                {
                    "num_traders": 20,
                    "metadata": {
                        "expected_orders": 100,
                        "resources": {"min_memory_gb": 8},
                    },
                    "tags": ["default", "team"],
                }
            )
        )

        loader = DefaultsLoader(project_root=tmp_path)
        result = loader.load_project_defaults()

        assert result["metadata"]["expected_orders"] == 100
        assert result["metadata"]["resources"]["min_memory_gb"] == 8


class TestConfigurationMerger:
    """Test configuration merging logic."""

    def test_merge_simple_override(self):
        """Test simple override of base values."""
        base = {"num_traders": 10, "duration": 60}
        override = {"num_traders": 20}

        result = ConfigurationMerger.merge(base, override)

        assert result == {"num_traders": 20, "duration": 60}

    def test_merge_new_keys_added(self):
        """Test that new keys in override are added."""
        base = {"num_traders": 10}
        override = {"duration": 60, "name": "test"}

        result = ConfigurationMerger.merge(base, override)

        assert result == {"num_traders": 10, "duration": 60, "name": "test"}

    def test_merge_none_doesnt_clear_by_default(self):
        """Test that None in override doesn't clear base value."""
        base = {"num_traders": 10, "duration": 60}
        override = {"num_traders": 20, "duration": None}

        result = ConfigurationMerger.merge(base, override)

        # duration should keep base value (60) since override has None
        assert result == {"num_traders": 20, "duration": 60}

    def test_merge_none_clears_with_flag(self):
        """Test that None in override clears base value when flag is set."""
        base = {"num_traders": 10, "duration": 60}
        override = {"num_traders": 20, "duration": None}

        result = ConfigurationMerger.merge(base, override, allow_none_clear=True)

        # duration should be cleared (None)
        assert result == {"num_traders": 20, "duration": None}

    def test_merge_empty_string_clears(self):
        """Test that empty string in override clears base string value."""
        base = {"name": "base", "description": "Base description"}
        override = {"description": ""}

        result = ConfigurationMerger.merge(base, override)

        assert result == {"name": "base", "description": ""}

    def test_merge_nested_dicts(self):
        """Test deep merge of nested dictionaries."""
        base = {
            "metadata": {
                "expected_orders": 100,
                "expected_duration_seconds": 60,
                "resources": {"min_memory_gb": 4},
            }
        }
        override = {
            "metadata": {
                "expected_orders": 200,
                "resources": {"min_cpu_cores": 2},
            }
        }

        result = ConfigurationMerger.merge(base, override)

        assert result == {
            "metadata": {
                "expected_orders": 200,  # Overridden
                "expected_duration_seconds": 60,  # Inherited
                "resources": {
                    "min_memory_gb": 4,  # Inherited
                    "min_cpu_cores": 2,  # Added
                },
            }
        }

    def test_merge_lists_replaced_not_merged(self):
        """Test that lists are replaced, not merged."""
        base = {"tags": ["base", "parent"]}
        override = {"tags": ["child"]}

        result = ConfigurationMerger.merge(base, override)

        assert result == {"tags": ["child"]}

    def test_merge_complex_structure(self):
        """Test complex nested structure merge."""
        base = {
            "name": "base",
            "num_traders": 10,
            "metadata": {
                "expected_orders": 100,
                "resources": {"min_memory_gb": 4, "min_cpu_cores": 2},
            },
            "tags": ["base"],
        }

        override = {
            "name": "child",
            "duration": 120,
            "metadata": {
                "expected_orders": 200,
                "resources": {"min_memory_gb": 8},
                "new_field": "value",
            },
            "tags": ["child", "test"],
        }

        result = ConfigurationMerger.merge(base, override)

        assert result == {
            "name": "child",
            "num_traders": 10,
            "duration": 120,
            "metadata": {
                "expected_orders": 200,
                "resources": {"min_memory_gb": 8, "min_cpu_cores": 2},
                "new_field": "value",
            },
            "tags": ["child", "test"],
        }


class TestMergeLayers:
    """Test merging multiple configuration layers."""

    def test_merge_layers_single_layer(self):
        """Test merging with single layer."""
        layer1 = {"num_traders": 10, "duration": 60}

        result = ConfigurationMerger.merge_layers(layer1)

        assert result == {"num_traders": 10, "duration": 60}

    def test_merge_layers_two_layers(self):
        """Test merging two layers."""
        layer1 = {"num_traders": 10, "duration": 60}
        layer2 = {"num_traders": 20, "name": "test"}

        result = ConfigurationMerger.merge_layers(layer1, layer2)

        assert result == {"num_traders": 20, "duration": 60, "name": "test"}

    def test_merge_layers_three_layers(self):
        """Test merging three layers (built-in, project, scenario)."""
        built_in = {"num_traders": 10, "duration": 60, "base_rate": 30}
        project = {"duration": 120, "tags": ["team"]}
        scenario = {"name": "test", "num_traders": 20}

        result = ConfigurationMerger.merge_layers(built_in, project, scenario)

        assert result == {
            "num_traders": 20,  # From scenario (highest)
            "duration": 120,  # From project
            "base_rate": 30,  # From built-in
            "tags": ["team"],  # From project
            "name": "test",  # From scenario
        }

    def test_merge_layers_with_none(self):
        """Test merging layers with None values (skipped)."""
        layer1 = {"num_traders": 10, "duration": 60}
        layer2 = None
        layer3 = {"num_traders": 20}

        result = ConfigurationMerger.merge_layers(layer1, layer2, layer3)

        assert result == {"num_traders": 20, "duration": 60}

    def test_merge_layers_all_none(self):
        """Test merging with all None layers."""
        result = ConfigurationMerger.merge_layers(None, None, None)

        assert result == {}

    def test_merge_layers_complex_nested(self):
        """Test merging layers with complex nested structures."""
        layer1 = {
            "num_traders": 10,
            "metadata": {
                "expected_orders": 100,
                "resources": {"min_memory_gb": 4},
            },
        }
        layer2 = {
            "duration": 120,
            "metadata": {
                "expected_orders": 150,
                "resources": {"min_cpu_cores": 2},
            },
        }
        layer3 = {
            "name": "test",
            "metadata": {
                "expected_orders": 200,
            },
        }

        result = ConfigurationMerger.merge_layers(layer1, layer2, layer3)

        assert result == {
            "num_traders": 10,
            "duration": 120,
            "name": "test",
            "metadata": {
                "expected_orders": 200,  # From layer3 (highest)
                "resources": {
                    "min_memory_gb": 4,  # From layer1
                    "min_cpu_cores": 2,  # From layer2
                },
            },
        }


class TestLoadWithDefaults:
    """Test load_with_defaults convenience function."""

    def test_load_with_defaults_no_file(self, tmp_path):
        """Test loading when no defaults file exists."""
        scenario = {"name": "test", "num_traders": 20}

        result = load_with_defaults(scenario, project_root=tmp_path)

        # Should return scenario unchanged
        assert result == {"name": "test", "num_traders": 20}

    def test_load_with_defaults_with_file(self, tmp_path):
        """Test loading with defaults file present."""
        # Create defaults file
        defaults_file = tmp_path / ".cow-perf-defaults.yml"
        defaults_file.write_text(
            yaml.dump(
                {
                    "duration": 120,
                    "tags": ["default"],
                    "num_traders": 10,
                }
            )
        )

        scenario = {"name": "test", "num_traders": 20}

        result = load_with_defaults(scenario, project_root=tmp_path)

        # Should merge defaults with scenario (scenario wins conflicts)
        assert result == {
            "name": "test",
            "num_traders": 20,  # From scenario (overrides default)
            "duration": 120,  # From defaults
            "tags": ["default"],  # From defaults
        }

    def test_load_with_defaults_nested_merge(self, tmp_path):
        """Test loading with nested structure merge."""
        # Create defaults file with nested structure
        defaults_file = tmp_path / ".cow-perf-defaults.yml"
        defaults_file.write_text(
            yaml.dump(
                {
                    "num_traders": 10,
                    "metadata": {
                        "expected_orders": 100,
                        "resources": {"min_memory_gb": 4, "min_cpu_cores": 2},
                    },
                }
            )
        )

        scenario = {
            "name": "test",
            "num_traders": 20,
            "metadata": {
                "expected_orders": 200,
            },
        }

        result = load_with_defaults(scenario, project_root=tmp_path)

        # Should deep merge nested structures
        assert result == {
            "name": "test",
            "num_traders": 20,
            "metadata": {
                "expected_orders": 200,  # From scenario
                "resources": {  # From defaults
                    "min_memory_gb": 4,
                    "min_cpu_cores": 2,
                },
            },
        }

    def test_load_with_defaults_empty_file(self, tmp_path):
        """Test loading with empty defaults file."""
        # Create empty defaults file
        defaults_file = tmp_path / ".cow-perf-defaults.yml"
        defaults_file.write_text("")

        scenario = {"name": "test", "num_traders": 20}

        result = load_with_defaults(scenario, project_root=tmp_path)

        # Should return scenario unchanged (empty defaults)
        assert result == {"name": "test", "num_traders": 20}
