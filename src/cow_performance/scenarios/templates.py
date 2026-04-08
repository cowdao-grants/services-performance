"""Template-based scenario generation with parameterization.

This module provides functionality for creating scenarios from templates,
allowing quick generation of common patterns like ramp-up, spike, and sustained load tests.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml


class TemplateError(Exception):
    """Error during template processing."""

    pass


class TemplateNotFoundError(TemplateError):
    """Template file not found."""

    pass


class ParameterError(TemplateError):
    """Error with template parameters."""

    pass


class TemplateExpander:
    """Expands parameterized templates into full scenario configurations.

    Templates use ${param_name} syntax for parameters, with optional defaults
    using ${param_name:-default} syntax.
    """

    # Pattern to match ${VAR} or ${VAR:-default}
    PARAM_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(:-([^}]*))?\}")

    def __init__(self, template_dirs: list[Path] | None = None):
        """Initialize template expander.

        Args:
            template_dirs: List of directories to search for templates
                          (default: [configs/scenarios/templates/, .cow-perf/templates/])
        """
        if template_dirs is None:
            self.template_dirs = [
                Path("configs/scenarios/templates"),
                Path(".cow-perf/templates"),
            ]
        else:
            self.template_dirs = template_dirs

    def find_template(self, template_name: str) -> Path | None:
        """Find a template file by name.

        Args:
            template_name: Template name (without .yml extension)

        Returns:
            Path to template file, or None if not found
        """
        # Try with .template.yml extension first, then .yml
        for template_dir in self.template_dirs:
            # Try .template.yml
            template_path = template_dir / f"{template_name}.template.yml"
            if template_path.exists():
                return template_path

            # Try .yml
            template_path = template_dir / f"{template_name}.yml"
            if template_path.exists():
                return template_path

        return None

    def load_template(self, template_name: str) -> dict[str, Any]:
        """Load a template file.

        Args:
            template_name: Template name (without extension)

        Returns:
            Template configuration dictionary

        Raises:
            TemplateNotFoundError: If template file doesn't exist
            TemplateError: If template file is invalid
        """
        template_path = self.find_template(template_name)

        if template_path is None:
            searched = ", ".join(str(d) for d in self.template_dirs)
            raise TemplateNotFoundError(
                f"Template '{template_name}' not found.\n" f"Searched directories: {searched}"
            )

        try:
            with open(template_path) as f:
                template = yaml.safe_load(f)

            if template is None:
                raise TemplateError(f"Template file is empty: {template_path}")

            if not isinstance(template, dict):
                raise TemplateError(f"Template must be a dictionary, got {type(template).__name__}")

            return template

        except yaml.YAMLError as e:
            raise TemplateError(f"Failed to parse template {template_path}: {e}") from e
        except Exception as e:
            raise TemplateError(f"Failed to load template {template_path}: {e}") from e

    def expand_string(self, text: str, parameters: dict[str, Any]) -> str:
        """Expand parameters in a string.

        Args:
            text: String with parameter references
            parameters: Dictionary of parameter values

        Returns:
            String with parameters expanded

        Raises:
            ParameterError: If required parameter is missing
        """

        def replace_param(match: re.Match) -> str:
            param_name = match.group(1)
            has_default = match.group(2) is not None
            default_value = match.group(3) if has_default else None

            # Check if parameter is provided
            if param_name in parameters:
                value = parameters[param_name]
                return str(value)

            # Use default if provided
            if has_default:
                return default_value if default_value is not None else ""

            # Required parameter missing
            raise ParameterError(
                f"Required parameter '${{{param_name}}}' not provided.\n"
                f"Available parameters: {', '.join(parameters.keys())}"
            )

        return self.PARAM_PATTERN.sub(replace_param, text)

    def expand_dict(self, config: dict[str, Any], parameters: dict[str, Any]) -> dict[str, Any]:
        """Recursively expand parameters in a dictionary.

        Args:
            config: Configuration dictionary with parameters
            parameters: Dictionary of parameter values

        Returns:
            Configuration with parameters expanded

        Raises:
            ParameterError: If required parameter is missing
        """
        result: dict[str, Any] = {}

        for key, value in config.items():
            # Expand parameter in key if it's a string
            if isinstance(key, str):
                key = self.expand_string(key, parameters)

            # Expand value based on type
            if isinstance(value, str):
                result[key] = self.expand_string(value, parameters)
            elif isinstance(value, dict):
                result[key] = self.expand_dict(value, parameters)
            elif isinstance(value, list):
                result[key] = self.expand_list(value, parameters)
            else:
                # Numbers, booleans, None - keep as is
                result[key] = value

        return result

    def expand_list(self, items: list[Any], parameters: dict[str, Any]) -> list[Any]:
        """Recursively expand parameters in a list.

        Args:
            items: List with potential parameters
            parameters: Dictionary of parameter values

        Returns:
            List with parameters expanded

        Raises:
            ParameterError: If required parameter is missing
        """
        result: list[Any] = []

        for item in items:
            if isinstance(item, str):
                result.append(self.expand_string(item, parameters))
            elif isinstance(item, dict):
                result.append(self.expand_dict(item, parameters))
            elif isinstance(item, list):
                result.append(self.expand_list(item, parameters))
            else:
                result.append(item)

        return result

    def expand_template(
        self,
        template_name: str,
        parameters: dict[str, Any],
    ) -> dict[str, Any]:
        """Expand a template with given parameters.

        Args:
            template_name: Template name (without extension)
            parameters: Dictionary of parameter values

        Returns:
            Fully expanded configuration dictionary

        Raises:
            TemplateNotFoundError: If template doesn't exist
            ParameterError: If required parameter is missing
            TemplateError: If template is invalid
        """
        # Load template
        template = self.load_template(template_name)

        # Remove template_metadata section if present (metadata only, not expanded)
        template_body = {k: v for k, v in template.items() if k != "template_metadata"}

        # Expand parameters in template body
        expanded = self.expand_dict(template_body, parameters)

        return expanded


def expand_template(
    template_name: str,
    parameters: dict[str, Any],
    template_dirs: list[Path] | None = None,
) -> dict[str, Any]:
    """Convenience function to expand a template.

    Args:
        template_name: Template name (without extension)
        parameters: Dictionary of parameter values
        template_dirs: Optional list of directories to search for templates

    Returns:
        Fully expanded configuration dictionary

    Raises:
        TemplateNotFoundError: If template doesn't exist
        ParameterError: If required parameter is missing
        TemplateError: If template is invalid
    """
    expander = TemplateExpander(template_dirs=template_dirs)
    return expander.expand_template(template_name, parameters)
