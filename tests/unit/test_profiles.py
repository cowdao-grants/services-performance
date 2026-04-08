"""Tests for profile-based configuration overrides."""

import pytest

from cow_performance.scenarios.profiles import (
    ProfileError,
    ProfileNotFoundError,
    ProfileSelector,
    apply_profile_if_requested,
)


class TestProfileSelector:
    """Test profile selection and application."""

    def test_has_profiles_true(self):
        """Test detecting profiles in config."""
        config = {
            "name": "test",
            "num_traders": 10,
            "profiles": {"dev": {"num_traders": 5}},
        }

        assert ProfileSelector.has_profiles(config) is True

    def test_has_profiles_false(self):
        """Test detecting no profiles in config."""
        config = {"name": "test", "num_traders": 10}

        assert ProfileSelector.has_profiles(config) is False

    def test_has_profiles_none(self):
        """Test profiles key with None value."""
        config = {"name": "test", "num_traders": 10, "profiles": None}

        assert ProfileSelector.has_profiles(config) is False

    def test_list_profiles(self):
        """Test listing available profiles."""
        config = {
            "name": "test",
            "profiles": {
                "dev": {"num_traders": 5},
                "staging": {"num_traders": 10},
                "production": {"num_traders": 50},
            },
        }

        profiles = ProfileSelector.list_profiles(config)

        assert set(profiles) == {"dev", "staging", "production"}

    def test_list_profiles_empty(self):
        """Test listing profiles when none exist."""
        config = {"name": "test", "num_traders": 10}

        profiles = ProfileSelector.list_profiles(config)

        assert profiles == []

    def test_list_profiles_invalid_type(self):
        """Test listing profiles when profiles is not a dict."""
        config = {"name": "test", "profiles": ["not", "a", "dict"]}

        profiles = ProfileSelector.list_profiles(config)

        assert profiles == []

    def test_apply_profile_simple(self):
        """Test applying a simple profile."""
        config = {
            "name": "test",
            "num_traders": 10,
            "duration": 60,
            "profiles": {
                "dev": {"num_traders": 5, "duration": 30},
            },
        }

        result = ProfileSelector.apply_profile(config, "dev")

        # Should have profile values + profiles removed
        assert result == {
            "name": "test",
            "num_traders": 5,  # From profile
            "duration": 30,  # From profile
        }

    def test_apply_profile_partial_override(self):
        """Test profile that only overrides some fields."""
        config = {
            "name": "test",
            "num_traders": 10,
            "duration": 60,
            "base_rate": 30,
            "profiles": {
                "staging": {"duration": 120},
            },
        }

        result = ProfileSelector.apply_profile(config, "staging")

        assert result == {
            "name": "test",
            "num_traders": 10,  # From base
            "duration": 120,  # From profile
            "base_rate": 30,  # From base
        }

    def test_apply_profile_nested_merge(self):
        """Test profile with nested structure merge."""
        config = {
            "name": "test",
            "metadata": {
                "expected_orders": 100,
                "resources": {"min_memory_gb": 4, "min_cpu_cores": 2},
            },
            "profiles": {
                "production": {
                    "metadata": {
                        "expected_orders": 1000,
                        "resources": {"min_memory_gb": 16},
                    }
                },
            },
        }

        result = ProfileSelector.apply_profile(config, "production")

        # Should deep merge nested structures
        assert result == {
            "name": "test",
            "metadata": {
                "expected_orders": 1000,  # From profile
                "resources": {
                    "min_memory_gb": 16,  # From profile
                    "min_cpu_cores": 2,  # From base
                },
            },
        }

    def test_apply_profile_new_fields(self):
        """Test profile that adds new fields."""
        config = {
            "name": "test",
            "num_traders": 10,
            "profiles": {
                "production": {
                    "num_traders": 50,
                    "tags": ["production", "critical"],
                    "api_url": "https://prod.example.com",
                },
            },
        }

        result = ProfileSelector.apply_profile(config, "production")

        assert result == {
            "name": "test",
            "num_traders": 50,
            "tags": ["production", "critical"],  # New field
            "api_url": "https://prod.example.com",  # New field
        }

    def test_apply_profile_empty_profile(self):
        """Test applying an empty profile."""
        config = {
            "name": "test",
            "num_traders": 10,
            "profiles": {"dev": None},
        }

        result = ProfileSelector.apply_profile(config, "dev")

        # Should just remove profiles section, no overrides
        assert result == {"name": "test", "num_traders": 10}

    def test_apply_profile_not_found(self):
        """Test error when requested profile doesn't exist."""
        config = {
            "name": "test",
            "profiles": {"dev": {"num_traders": 5}, "staging": {"num_traders": 10}},
        }

        with pytest.raises(ProfileNotFoundError) as exc_info:
            ProfileSelector.apply_profile(config, "production")

        error_msg = str(exc_info.value)
        assert "production" in error_msg.lower()
        assert "not found" in error_msg.lower()
        assert "dev" in error_msg  # Should list available profiles
        assert "staging" in error_msg

    def test_apply_profile_no_profiles_section(self):
        """Test error when trying to apply profile but no profiles defined."""
        config = {"name": "test", "num_traders": 10}

        with pytest.raises(ProfileError) as exc_info:
            ProfileSelector.apply_profile(config, "dev")

        assert "no profiles defined" in str(exc_info.value).lower()

    def test_apply_profile_invalid_profiles_type(self):
        """Test error when profiles section is not a dict."""
        config = {"name": "test", "profiles": ["not", "a", "dict"]}

        with pytest.raises(ProfileError) as exc_info:
            ProfileSelector.apply_profile(config, "dev")

        assert "must be a dictionary" in str(exc_info.value).lower()

    def test_apply_profile_invalid_profile_value_type(self):
        """Test error when profile value is not a dict."""
        config = {"name": "test", "profiles": {"dev": ["invalid", "type"]}}

        with pytest.raises(ProfileError) as exc_info:
            ProfileSelector.apply_profile(config, "dev")

        assert "must be a dictionary" in str(exc_info.value).lower()

    def test_apply_profile_list_replacement(self):
        """Test that lists in profiles replace base lists."""
        config = {
            "name": "test",
            "tags": ["base", "default"],
            "profiles": {
                "production": {"tags": ["production"]},
            },
        }

        result = ProfileSelector.apply_profile(config, "production")

        # Lists should be replaced, not merged
        assert result["tags"] == ["production"]


class TestApplyProfileIfRequested:
    """Test convenience function for conditional profile application."""

    def test_apply_profile_when_requested(self):
        """Test applying profile when profile name is provided."""
        config = {
            "name": "test",
            "num_traders": 10,
            "profiles": {"dev": {"num_traders": 5}},
        }

        result = apply_profile_if_requested(config, "dev")

        assert result == {"name": "test", "num_traders": 5}

    def test_no_profile_requested_with_profiles(self):
        """Test no profile application when None is passed but profiles exist."""
        config = {
            "name": "test",
            "num_traders": 10,
            "profiles": {"dev": {"num_traders": 5}},
        }

        result = apply_profile_if_requested(config, None)

        # Should just remove profiles section
        assert result == {"name": "test", "num_traders": 10}

    def test_no_profile_requested_no_profiles(self):
        """Test when no profile requested and no profiles exist."""
        config = {"name": "test", "num_traders": 10}

        result = apply_profile_if_requested(config, None)

        # Should return config unchanged
        assert result == {"name": "test", "num_traders": 10}

    def test_profile_not_found_error_propagates(self):
        """Test that ProfileNotFoundError is propagated."""
        config = {
            "name": "test",
            "profiles": {"dev": {"num_traders": 5}},
        }

        with pytest.raises(ProfileNotFoundError):
            apply_profile_if_requested(config, "nonexistent")


class TestMultipleProfiles:
    """Test scenarios with multiple profiles."""

    def test_multiple_profiles_selection(self):
        """Test selecting different profiles from same config."""
        config = {
            "name": "test",
            "num_traders": 10,
            "duration": 60,
            "profiles": {
                "dev": {"num_traders": 3, "duration": 30},
                "staging": {"num_traders": 10, "duration": 120},
                "production": {"num_traders": 50, "duration": 600},
            },
        }

        # Apply dev profile
        dev_result = ProfileSelector.apply_profile(config, "dev")
        assert dev_result["num_traders"] == 3
        assert dev_result["duration"] == 30

        # Apply staging profile (from original config)
        staging_result = ProfileSelector.apply_profile(config, "staging")
        assert staging_result["num_traders"] == 10
        assert staging_result["duration"] == 120

        # Apply production profile (from original config)
        prod_result = ProfileSelector.apply_profile(config, "production")
        assert prod_result["num_traders"] == 50
        assert prod_result["duration"] == 600

    def test_profile_independence(self):
        """Test that applying one profile doesn't affect others."""
        config = {
            "name": "test",
            "value": 10,
            "profiles": {
                "a": {"value": 20, "a_only": True},
                "b": {"value": 30, "b_only": True},
            },
        }

        result_a = ProfileSelector.apply_profile(config, "a")
        assert result_a == {"name": "test", "value": 20, "a_only": True}

        result_b = ProfileSelector.apply_profile(config, "b")
        assert result_b == {"name": "test", "value": 30, "b_only": True}

        # Verify original config unchanged
        assert config["profiles"]["a"] == {"value": 20, "a_only": True}
        assert config["profiles"]["b"] == {"value": 30, "b_only": True}
