"""Tests for scenario inheritance resolution."""


import pytest
import yaml

from cow_performance.scenarios.inheritance import (
    CircularDependencyError,
    InheritanceError,
    InheritanceResolver,
    resolve_inheritance,
)


class TestDeepMerge:
    """Test deep merge logic."""

    def test_merge_primitives_child_wins(self):
        """Test that child primitives override parent."""
        resolver = InheritanceResolver()

        base = {"num_traders": 10, "duration": 60, "name": "base"}
        override = {"num_traders": 20, "duration": 120}

        result = resolver._deep_merge(base, override)

        assert result == {"num_traders": 20, "duration": 120, "name": "base"}

    def test_merge_new_keys_added(self):
        """Test that new keys in child are added."""
        resolver = InheritanceResolver()

        base = {"num_traders": 10}
        override = {"duration": 60, "name": "test"}

        result = resolver._deep_merge(base, override)

        assert result == {"num_traders": 10, "duration": 60, "name": "test"}

    def test_merge_nested_dicts(self):
        """Test deep merge of nested dictionaries."""
        resolver = InheritanceResolver()

        base = {"metadata": {"expected_orders": 100, "expected_duration_seconds": 60}}
        override = {"metadata": {"expected_orders": 200}}

        result = resolver._deep_merge(base, override)

        assert result == {"metadata": {"expected_orders": 200, "expected_duration_seconds": 60}}

    def test_merge_lists_replaced_not_merged(self):
        """Test that lists are replaced, not merged."""
        resolver = InheritanceResolver()

        base = {"tags": ["base", "parent"]}
        override = {"tags": ["child"]}

        result = resolver._deep_merge(base, override)

        assert result == {"tags": ["child"]}

    def test_merge_none_doesnt_override(self):
        """Test that None in child doesn't override parent value."""
        resolver = InheritanceResolver()

        base = {"num_traders": 10, "duration": 60}
        override = {"num_traders": 20, "duration": None}

        result = resolver._deep_merge(base, override)

        # duration should keep parent value (60) since child has None
        assert result == {"num_traders": 20, "duration": 60}

    def test_merge_complex_nested_structure(self):
        """Test complex nested structure merge."""
        resolver = InheritanceResolver()

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

        result = resolver._deep_merge(base, override)

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


class TestInheritanceResolution:
    """Test inheritance resolution."""

    def test_no_inheritance(self):
        """Test config without inheritance passes through unchanged."""
        resolver = InheritanceResolver()

        config = {"name": "test", "num_traders": 10}

        result = resolver.resolve(config)

        assert result == {"name": "test", "num_traders": 10}

    def test_simple_inheritance(self, tmp_path):
        """Test simple parent-child inheritance."""
        # Create parent scenario
        parent = tmp_path / "parent.yml"
        parent.write_text(
            yaml.dump(
                {
                    "name": "parent",
                    "num_traders": 10,
                    "duration": 60,
                    "market_order_ratio": 0.7,
                    "limit_order_ratio": 0.3,
                }
            )
        )

        # Create child scenario
        child_config = {
            "extends": str(parent),
            "name": "child",
            "num_traders": 20,
        }

        resolver = InheritanceResolver()
        result = resolver.resolve(child_config)

        # Should merge parent and child
        assert result == {
            "name": "child",
            "num_traders": 20,
            "duration": 60,
            "market_order_ratio": 0.7,
            "limit_order_ratio": 0.3,
        }
        # 'extends' should be removed
        assert "extends" not in result

    def test_multi_level_inheritance(self, tmp_path):
        """Test multi-level inheritance chain (grandchild → child → parent)."""
        # Create grandparent
        grandparent = tmp_path / "grandparent.yml"
        grandparent.write_text(
            yaml.dump({"name": "grandparent", "num_traders": 5, "duration": 30, "base_rate": 30})
        )

        # Create parent extending grandparent
        parent = tmp_path / "parent.yml"
        parent.write_text(
            yaml.dump(
                {"extends": str(grandparent), "name": "parent", "num_traders": 10, "duration": 60}
            )
        )

        # Create child extending parent
        child_config = {"extends": str(parent), "name": "child", "num_traders": 20}

        resolver = InheritanceResolver()
        result = resolver.resolve(child_config)

        # Should have values from all three levels
        assert result == {
            "name": "child",
            "num_traders": 20,  # From child
            "duration": 60,  # From parent
            "base_rate": 30,  # From grandparent
        }

    def test_relative_path_extends(self, tmp_path):
        """Test extends with relative path."""
        # Create subdirectory structure
        base_dir = tmp_path / "scenarios"
        base_dir.mkdir()
        shared_dir = base_dir / "shared"
        shared_dir.mkdir()

        # Create parent in shared directory
        parent = shared_dir / "base.yml"
        parent.write_text(yaml.dump({"name": "base", "num_traders": 10}))

        # Create child with relative path
        child = base_dir / "child.yml"
        child.write_text(yaml.dump({"extends": "shared/base.yml", "name": "child"}))

        # Load child config
        with open(child) as f:
            child_config = yaml.safe_load(f)

        resolver = InheritanceResolver()
        result = resolver.resolve(child_config, child)

        assert result == {"name": "child", "num_traders": 10}

    def test_parent_not_found(self):
        """Test error when parent scenario doesn't exist."""
        resolver = InheritanceResolver()

        config = {"extends": "/nonexistent/parent.yml", "name": "child"}

        with pytest.raises(InheritanceError) as exc_info:
            resolver.resolve(config)

        assert "not found" in str(exc_info.value).lower()

    def test_circular_dependency_direct(self, tmp_path):
        """Test detection of direct circular dependency."""
        # Create scenario that extends itself
        scenario = tmp_path / "circular.yml"
        scenario.write_text(yaml.dump({"extends": str(scenario), "name": "circular"}))

        with open(scenario) as f:
            config = yaml.safe_load(f)

        resolver = InheritanceResolver()

        with pytest.raises(CircularDependencyError) as exc_info:
            resolver.resolve(config, scenario)

        assert "circular dependency" in str(exc_info.value).lower()

    def test_circular_dependency_indirect(self, tmp_path):
        """Test detection of indirect circular dependency."""
        # Create A extends B, B extends A
        scenario_a = tmp_path / "a.yml"
        scenario_b = tmp_path / "b.yml"

        scenario_a.write_text(yaml.dump({"extends": str(scenario_b), "name": "a"}))
        scenario_b.write_text(yaml.dump({"extends": str(scenario_a), "name": "b"}))

        with open(scenario_a) as f:
            config = yaml.safe_load(f)

        resolver = InheritanceResolver()

        with pytest.raises(CircularDependencyError) as exc_info:
            resolver.resolve(config, scenario_a)

        assert "circular dependency" in str(exc_info.value).lower()

    def test_builtin_scenario_reference(self, tmp_path, monkeypatch):
        """Test extending a builtin scenario."""
        # Mock the builtin scenarios directory
        builtin_dir = tmp_path / "configs" / "scenarios"
        builtin_dir.mkdir(parents=True)

        # Create a builtin scenario
        builtin = builtin_dir / "light-load.yml"
        builtin.write_text(yaml.dump({"name": "light-load", "num_traders": 3, "duration": 120}))

        # Create child extending builtin
        child_config = {"extends": "builtin:light-load", "name": "custom", "num_traders": 5}

        resolver = InheritanceResolver(base_dir=tmp_path)
        resolver.builtin_scenarios_dir = builtin_dir

        result = resolver.resolve(child_config)

        assert result == {"name": "custom", "num_traders": 5, "duration": 120}

    def test_nested_dict_partial_override(self, tmp_path):
        """Test that nested dict fields are merged, not replaced."""
        parent = tmp_path / "parent.yml"
        parent.write_text(
            yaml.dump(
                {
                    "name": "parent",
                    "metadata": {
                        "expected_orders": 100,
                        "expected_duration_seconds": 60,
                        "resources": {"min_memory_gb": 4, "min_cpu_cores": 2},
                    },
                }
            )
        )

        child_config = {
            "extends": str(parent),
            "name": "child",
            "metadata": {"expected_orders": 200},  # Only override one field
        }

        resolver = InheritanceResolver()
        result = resolver.resolve(child_config)

        # Should have merged metadata, not replaced
        assert result["metadata"] == {
            "expected_orders": 200,  # Overridden
            "expected_duration_seconds": 60,  # Inherited
            "resources": {"min_memory_gb": 4, "min_cpu_cores": 2},  # Inherited
        }


class TestConvenienceFunction:
    """Test convenience function for inheritance resolution."""

    def test_resolve_inheritance_function(self, tmp_path):
        """Test resolve_inheritance convenience function."""
        parent = tmp_path / "parent.yml"
        parent.write_text(yaml.dump({"name": "parent", "num_traders": 10}))

        child_config = {"extends": str(parent), "name": "child"}

        result = resolve_inheritance(child_config, base_dir=tmp_path)

        assert result == {"name": "child", "num_traders": 10}


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_empty_parent_scenario(self, tmp_path):
        """Test error when parent scenario is empty."""
        parent = tmp_path / "empty.yml"
        parent.write_text("")

        child_config = {"extends": str(parent), "name": "child"}

        resolver = InheritanceResolver()

        with pytest.raises(InheritanceError) as exc_info:
            resolver.resolve(child_config)

        assert "empty" in str(exc_info.value).lower()

    def test_invalid_yaml_parent(self, tmp_path):
        """Test error when parent has invalid YAML."""
        parent = tmp_path / "invalid.yml"
        parent.write_text("invalid: yaml: syntax: error:")

        child_config = {"extends": str(parent), "name": "child"}

        resolver = InheritanceResolver()

        with pytest.raises(InheritanceError) as exc_info:
            resolver.resolve(child_config)

        assert "parse" in str(exc_info.value).lower()

    def test_extends_none(self):
        """Test that extends: null is treated as no inheritance."""
        resolver = InheritanceResolver()

        config = {"extends": None, "name": "test", "num_traders": 10}

        result = resolver.resolve(config)

        assert result == {"extends": None, "name": "test", "num_traders": 10}

    def test_multiple_resolution_calls_independent(self, tmp_path):
        """Test that multiple resolve() calls are independent."""
        parent = tmp_path / "parent.yml"
        parent.write_text(yaml.dump({"name": "parent", "num_traders": 10}))

        resolver = InheritanceResolver()

        # First resolution
        config1 = {"extends": str(parent), "name": "child1"}
        result1 = resolver.resolve(config1)

        # Second resolution should not be affected by first
        config2 = {"extends": str(parent), "name": "child2", "duration": 120}
        result2 = resolver.resolve(config2)

        assert result1 == {"name": "child1", "num_traders": 10}
        assert result2 == {"name": "child2", "num_traders": 10, "duration": 120}
