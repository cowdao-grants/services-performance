"""Project defaults loading and configuration precedence resolution.

This module handles loading project-level defaults from .cow-perf-defaults.yml
and merging multiple configuration layers with correct precedence.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


class DefaultsError(Exception):
    """Error loading or processing defaults."""

    pass


class DefaultsLoader:
    """Loads project defaults from .cow-perf-defaults.yml file."""

    DEFAULT_FILENAME = ".cow-perf-defaults.yml"

    def __init__(self, project_root: Path | None = None):
        """Initialize defaults loader.

        Args:
            project_root: Root directory of the project (default: current directory)
        """
        self.project_root = project_root or Path.cwd()

    def load_project_defaults(self) -> dict[str, Any] | None:
        """Load project defaults from .cow-perf-defaults.yml.

        Returns:
            Project defaults dictionary, or None if file doesn't exist

        Raises:
            DefaultsError: If defaults file exists but cannot be loaded
        """
        defaults_path = self.project_root / self.DEFAULT_FILENAME

        if not defaults_path.exists():
            return None

        try:
            with open(defaults_path) as f:
                defaults = yaml.safe_load(f)

            if defaults is None:
                # Empty file is valid - return empty dict
                return {}

            if not isinstance(defaults, dict):
                raise DefaultsError(
                    f"Project defaults must be a dictionary, got {type(defaults).__name__}"
                )

            return defaults

        except yaml.YAMLError as e:
            raise DefaultsError(f"Failed to parse project defaults file: {e}") from e
        except Exception as e:
            raise DefaultsError(f"Failed to load project defaults file: {e}") from e


class ConfigurationMerger:
    """Merges multiple configuration layers with correct precedence.

    Precedence order (lowest to highest):
    1. Built-in defaults (hardcoded in ScenarioConfig)
    2. Project defaults (.cow-perf-defaults.yml)
    3. Scenario file
    4. Profile overrides (applied separately)
    5. CLI arguments (applied separately)

    Merge rules:
    - Explicit values always override defaults
    - None/null in child doesn't clear parent value
    - Empty string in child does clear parent value
    - Lists are replaced, not merged
    - Dicts are deep-merged recursively
    """

    @staticmethod
    def merge(
        base: dict[str, Any],
        override: dict[str, Any],
        allow_none_clear: bool = False,
    ) -> dict[str, Any]:
        """Deep merge two configuration dictionaries.

        Args:
            base: Base configuration (lower priority)
            override: Override configuration (higher priority)
            allow_none_clear: If True, None in override clears base value

        Returns:
            Merged configuration dictionary
        """
        result: dict[str, Any] = base.copy()

        for key, value in override.items():
            if key not in result:
                # New key in override - just add it
                result[key] = value
            elif value is None and not allow_none_clear:
                # None in override doesn't clear base value (keep base)
                continue
            elif value == "" and isinstance(result[key], str):
                # Empty string in override clears base string value
                result[key] = value
            elif isinstance(value, dict) and isinstance(result[key], dict):
                # Both are dicts - deep merge
                result[key] = ConfigurationMerger.merge(result[key], value, allow_none_clear)
            else:
                # Override wins (primitives, lists, type changes)
                result[key] = value

        return result

    @staticmethod
    def merge_layers(*layers: dict[str, Any] | None) -> dict[str, Any]:
        """Merge multiple configuration layers in order.

        Args:
            *layers: Configuration dictionaries in order from lowest to highest priority.
                     None values are skipped.

        Returns:
            Merged configuration dictionary

        Example:
            >>> built_in = {"num_traders": 10, "duration": 60}
            >>> project = {"duration": 120, "tags": ["team"]}
            >>> scenario = {"name": "test", "num_traders": 20}
            >>> result = ConfigurationMerger.merge_layers(built_in, project, scenario)
            >>> # Result: {"num_traders": 20, "duration": 120, "tags": ["team"], "name": "test"}
        """
        # Filter out None layers
        valid_layers = [layer for layer in layers if layer is not None]

        if not valid_layers:
            return {}

        # Start with first layer
        result = valid_layers[0].copy()

        # Merge remaining layers
        for layer in valid_layers[1:]:
            result = ConfigurationMerger.merge(result, layer)

        return result


def load_with_defaults(
    scenario_config: dict[str, Any],
    project_root: Path | None = None,
) -> dict[str, Any]:
    """Load scenario configuration with project defaults merged in.

    This applies project defaults as a base layer under the scenario config,
    following the precedence hierarchy.

    Args:
        scenario_config: Scenario configuration dictionary
        project_root: Root directory of the project (default: current directory)

    Returns:
        Merged configuration with project defaults applied

    Raises:
        DefaultsError: If defaults file exists but cannot be loaded
    """
    # Load project defaults
    loader = DefaultsLoader(project_root=project_root)
    project_defaults = loader.load_project_defaults()

    # Merge with scenario config
    if project_defaults is None:
        # No project defaults file - return scenario as-is
        return scenario_config

    # Merge: project defaults (base) + scenario config (override)
    return ConfigurationMerger.merge(project_defaults, scenario_config)
