"""Scenario inheritance and composition system.

This module provides functionality for scenarios to extend other scenarios using
the 'extends' keyword, enabling configuration reuse and composition.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


class InheritanceError(Exception):
    """Error during scenario inheritance resolution."""

    pass


class CircularDependencyError(InheritanceError):
    """Circular dependency detected in inheritance chain."""

    pass


class InheritanceResolver:
    """Resolves scenario inheritance chains and merges configurations."""

    def __init__(self, base_dir: Path | None = None):
        """Initialize inheritance resolver.

        Args:
            base_dir: Base directory for resolving relative paths (default: current directory)
        """
        self.base_dir = base_dir or Path.cwd()
        self.builtin_scenarios_dir = Path("configs/scenarios")

    def resolve(self, config: dict[str, Any], config_path: Path | None = None) -> dict[str, Any]:
        """Resolve inheritance for a configuration.

        Args:
            config: Configuration dictionary
            config_path: Path to the configuration file (for resolving relative extends)

        Returns:
            Merged configuration with inheritance resolved

        Raises:
            InheritanceError: If inheritance resolution fails
            CircularDependencyError: If circular dependency is detected
        """
        # Start resolution with empty visited set
        return self._resolve_recursive(config, config_path, set())

    def _resolve_recursive(
        self, config: dict[str, Any], config_path: Path | None, visited: set[str]
    ) -> dict[str, Any]:
        """Recursively resolve inheritance with circular dependency detection.

        Args:
            config: Configuration dictionary
            config_path: Path to the configuration file
            visited: Set of already visited config paths

        Returns:
            Merged configuration with inheritance resolved

        Raises:
            CircularDependencyError: If circular dependency is detected
        """
        # Track this config to detect circular dependencies
        if config_path:
            config_id = str(config_path.resolve())
            if config_id in visited:
                raise CircularDependencyError(
                    f"Circular dependency detected: {config_path} has already been visited\n"
                    f"Inheritance chain: {' -> '.join(visited)} -> {config_id}"
                )
            visited = visited | {config_id}  # Create new set with this path added

        # Check if this config extends another
        if "extends" not in config or config["extends"] is None:
            return config

        parent_ref = config["extends"]

        # Load parent configuration
        parent_config = self._load_parent(parent_ref, config_path)

        # Get parent path for tracking
        parent_path = self._get_parent_path(parent_ref, config_path)

        # Recursively resolve parent's inheritance
        parent_config = self._resolve_recursive(parent_config, parent_path, visited)

        # Merge parent and child configurations
        merged = self._deep_merge(parent_config, config)

        # Remove 'extends' from merged config (it's been resolved)
        merged.pop("extends", None)

        return merged

    def _load_parent(self, parent_ref: str, config_path: Path | None) -> dict[str, Any]:
        """Load parent scenario configuration.

        Args:
            parent_ref: Parent reference (can be relative path, builtin name, etc.)
            config_path: Path to child configuration file

        Returns:
            Parent configuration dictionary

        Raises:
            InheritanceError: If parent cannot be loaded
        """
        parent_path = self._resolve_parent_path(parent_ref, config_path)

        if not parent_path.exists():
            raise InheritanceError(
                f"Parent scenario not found: {parent_ref}\n"
                f"Resolved to: {parent_path}\n"
                f"Check that the file exists and the path is correct."
            )

        try:
            with open(parent_path) as f:
                parent_config = yaml.safe_load(f)

            if parent_config is None:
                raise InheritanceError(f"Parent scenario is empty: {parent_path}")

            if not isinstance(parent_config, dict):
                raise InheritanceError(
                    f"Parent scenario must be a dictionary, got {type(parent_config).__name__}"
                )

            return parent_config

        except yaml.YAMLError as e:
            raise InheritanceError(f"Failed to parse parent scenario {parent_path}: {e}") from e
        except Exception as e:
            raise InheritanceError(f"Failed to load parent scenario {parent_path}: {e}") from e

    def _resolve_parent_path(self, parent_ref: str, config_path: Path | None) -> Path:
        """Resolve parent reference to an absolute path.

        Supports:
        - Relative paths: ../base-scenario.yml, ./base.yml
        - Builtin scenarios: builtin:light-load
        - Absolute paths: /path/to/scenario.yml

        Args:
            parent_ref: Parent reference string
            config_path: Path to child configuration file

        Returns:
            Absolute path to parent scenario
        """
        # Handle builtin scenarios
        if parent_ref.startswith("builtin:"):
            scenario_name = parent_ref.replace("builtin:", "")
            # Try with .yml extension
            builtin_path = self.builtin_scenarios_dir / f"{scenario_name}.yml"
            if not builtin_path.exists():
                # Try enhanced subdirectory
                builtin_path = self.builtin_scenarios_dir / "enhanced" / f"{scenario_name}.yml"
            return builtin_path

        # Handle absolute paths
        parent_path = Path(parent_ref)
        if parent_path.is_absolute():
            return parent_path

        # Handle relative paths
        if config_path:
            # Relative to the child config's directory
            base_dir = config_path.parent
        else:
            # Relative to base directory
            base_dir = self.base_dir

        resolved = (base_dir / parent_ref).resolve()
        return resolved

    def _get_parent_path(self, parent_ref: str, config_path: Path | None) -> Path:
        """Get the path to use for the parent config in circular dependency tracking.

        Args:
            parent_ref: Parent reference string
            config_path: Path to child configuration file

        Returns:
            Path to parent configuration
        """
        return self._resolve_parent_path(parent_ref, config_path)

    def _deep_merge(self, base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
        """Deep merge two configuration dictionaries.

        Child (override) values take precedence over parent (base) values.

        Merge rules:
        - Primitives (str, int, float, bool): Child overrides parent
        - Lists: Child replaces parent entirely (no appending/merging)
        - Dicts: Deep merge recursively
        - None in child: Doesn't clear parent value (child must use explicit value)

        Args:
            base: Parent configuration
            override: Child configuration

        Returns:
            Merged configuration dictionary
        """
        result: dict[str, Any] = base.copy()

        for key, value in override.items():
            if key not in result:
                # New key in child - just add it
                result[key] = value
            elif value is None:
                # None in child doesn't override parent (use parent value)
                continue
            elif isinstance(value, dict) and isinstance(result[key], dict):
                # Both are dicts - deep merge
                result[key] = self._deep_merge(result[key], value)
            else:
                # Child overrides parent (primitives, lists, type changes)
                result[key] = value

        return result


def resolve_inheritance(
    config: dict[str, Any],
    config_path: Path | None = None,
    base_dir: Path | None = None,
) -> dict[str, Any]:
    """Convenience function to resolve inheritance for a configuration.

    Args:
        config: Configuration dictionary
        config_path: Path to the configuration file
        base_dir: Base directory for resolving paths

    Returns:
        Merged configuration with inheritance resolved

    Raises:
        InheritanceError: If inheritance resolution fails
        CircularDependencyError: If circular dependency is detected
    """
    resolver = InheritanceResolver(base_dir=base_dir)
    return resolver.resolve(config, config_path)
