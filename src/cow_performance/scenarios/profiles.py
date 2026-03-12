"""Profile-based configuration overrides for environment-specific settings.

This module provides functionality for defining and applying configuration profiles
within scenario files, allowing different settings for dev/staging/production.
"""

from __future__ import annotations

from typing import Any


class ProfileError(Exception):
    """Error during profile selection or application."""

    pass


class ProfileNotFoundError(ProfileError):
    """Requested profile does not exist."""

    pass


class ProfileSelector:
    """Selects and applies profile-based configuration overrides.

    Profiles allow environment-specific overrides within a single scenario file:

    Example:
        ```yaml
        name: "My Test"
        num_traders: 10
        duration: 60

        profiles:
          dev:
            duration: 30
            num_traders: 5
          staging:
            duration: 120
          production:
            duration: 600
            num_traders: 50
        ```

        When `--profile staging` is used, the staging profile overrides are applied.
    """

    @staticmethod
    def has_profiles(config: dict[str, Any]) -> bool:
        """Check if configuration has profiles defined.

        Args:
            config: Configuration dictionary

        Returns:
            True if profiles are defined, False otherwise
        """
        return "profiles" in config and config["profiles"] is not None

    @staticmethod
    def list_profiles(config: dict[str, Any]) -> list[str]:
        """List available profile names in configuration.

        Args:
            config: Configuration dictionary

        Returns:
            List of profile names, empty if no profiles defined
        """
        if not ProfileSelector.has_profiles(config):
            return []

        profiles = config["profiles"]
        if not isinstance(profiles, dict):
            return []

        return list(profiles.keys())

    @staticmethod
    def apply_profile(
        config: dict[str, Any],
        profile_name: str,
    ) -> dict[str, Any]:
        """Apply a profile to the configuration.

        This extracts the specified profile from the profiles section and merges
        it with the base configuration. The profiles section is removed from the
        result.

        Args:
            config: Configuration dictionary with profiles section
            profile_name: Name of profile to apply

        Returns:
            Configuration with profile applied and profiles section removed

        Raises:
            ProfileNotFoundError: If requested profile doesn't exist
            ProfileError: If profiles section is malformed
        """
        # Check if profiles exist
        if not ProfileSelector.has_profiles(config):
            raise ProfileError(
                f"Cannot apply profile '{profile_name}': No profiles defined in configuration"
            )

        profiles = config["profiles"]

        # Validate profiles section is a dict
        if not isinstance(profiles, dict):
            raise ProfileError(
                f"Profiles section must be a dictionary, got {type(profiles).__name__}"
            )

        # Check if requested profile exists
        if profile_name not in profiles:
            available = ", ".join(profiles.keys()) if profiles else "none"
            raise ProfileNotFoundError(
                f"Profile '{profile_name}' not found.\n" f"Available profiles: {available}"
            )

        # Get profile overrides
        profile_overrides = profiles[profile_name]

        if profile_overrides is None:
            # Empty profile is valid - no overrides
            profile_overrides = {}

        if not isinstance(profile_overrides, dict):
            raise ProfileError(
                f"Profile '{profile_name}' must be a dictionary, "
                f"got {type(profile_overrides).__name__}"
            )

        # Create base config without profiles section
        base_config = {k: v for k, v in config.items() if k != "profiles"}

        # Merge profile overrides into base
        # Import here to avoid circular dependency
        from cow_performance.scenarios.defaults import ConfigurationMerger

        result = ConfigurationMerger.merge(base_config, profile_overrides)

        return result


def apply_profile_if_requested(
    config: dict[str, Any],
    profile_name: str | None,
) -> dict[str, Any]:
    """Apply profile to configuration if profile name is provided.

    Convenience function that applies profile only if profile_name is not None.
    If no profile is requested but profiles exist, they are simply removed.

    Args:
        config: Configuration dictionary
        profile_name: Optional profile name to apply

    Returns:
        Configuration with profile applied (if requested) and profiles removed

    Raises:
        ProfileNotFoundError: If requested profile doesn't exist
        ProfileError: If profiles section is malformed
    """
    # If no profile requested
    if profile_name is None:
        # Just remove profiles section if it exists
        if "profiles" in config:
            return {k: v for k, v in config.items() if k != "profiles"}
        return config

    # Apply the requested profile
    return ProfileSelector.apply_profile(config, profile_name)
