"""Unit tests for baseline validation."""

import pytest

from cow_performance.baselines.models import SCHEMA_VERSION
from cow_performance.baselines.validation import (
    BaselineValidationError,
    validate_baseline,
)


class TestValidateBaseline:
    """Tests for validate_baseline function."""

    @pytest.fixture
    def valid_baseline_data(self) -> dict:  # type: ignore[type-arg]
        """Create valid baseline data."""
        return {
            "id": "test-uuid",
            "name": "test-baseline",
            "schema_version": SCHEMA_VERSION,
            "created_at": 1234567890.0,
        }

    def test_valid_baseline(self, valid_baseline_data: dict) -> None:  # type: ignore[type-arg]
        """Test validation passes for valid data."""
        # Should not raise
        validate_baseline(valid_baseline_data)

    def test_missing_id(self, valid_baseline_data: dict) -> None:  # type: ignore[type-arg]
        """Test validation fails for missing id."""
        del valid_baseline_data["id"]

        with pytest.raises(BaselineValidationError) as exc:
            validate_baseline(valid_baseline_data)

        assert "id" in str(exc.value)

    def test_missing_name(self, valid_baseline_data: dict) -> None:  # type: ignore[type-arg]
        """Test validation fails for missing name."""
        del valid_baseline_data["name"]

        with pytest.raises(BaselineValidationError) as exc:
            validate_baseline(valid_baseline_data)

        assert "name" in str(exc.value)

    def test_missing_schema_version(self, valid_baseline_data: dict) -> None:  # type: ignore[type-arg]
        """Test validation fails for missing schema_version."""
        del valid_baseline_data["schema_version"]

        with pytest.raises(BaselineValidationError) as exc:
            validate_baseline(valid_baseline_data)

        assert "schema_version" in str(exc.value)

    def test_missing_created_at(self, valid_baseline_data: dict) -> None:  # type: ignore[type-arg]
        """Test validation fails for missing created_at."""
        del valid_baseline_data["created_at"]

        with pytest.raises(BaselineValidationError) as exc:
            validate_baseline(valid_baseline_data)

        assert "created_at" in str(exc.value)

    def test_invalid_schema_version_format(self, valid_baseline_data: dict) -> None:  # type: ignore[type-arg]
        """Test validation fails for invalid schema version format."""
        valid_baseline_data["schema_version"] = "invalid"

        with pytest.raises(BaselineValidationError) as exc:
            validate_baseline(valid_baseline_data)

        assert "schema_version" in str(exc.value).lower()

    def test_newer_schema_version(self, valid_baseline_data: dict) -> None:  # type: ignore[type-arg]
        """Test validation fails for newer schema version."""
        valid_baseline_data["schema_version"] = "99.0"

        with pytest.raises(BaselineValidationError) as exc:
            validate_baseline(valid_baseline_data)

        assert "newer" in str(exc.value).lower()

    def test_empty_id(self, valid_baseline_data: dict) -> None:  # type: ignore[type-arg]
        """Test validation fails for empty id."""
        valid_baseline_data["id"] = ""

        with pytest.raises(BaselineValidationError) as exc:
            validate_baseline(valid_baseline_data)

        assert "id" in str(exc.value).lower()

    def test_empty_name(self, valid_baseline_data: dict) -> None:  # type: ignore[type-arg]
        """Test validation fails for empty name."""
        valid_baseline_data["name"] = ""

        with pytest.raises(BaselineValidationError) as exc:
            validate_baseline(valid_baseline_data)

        assert "name" in str(exc.value).lower()

    def test_invalid_created_at_type(self, valid_baseline_data: dict) -> None:  # type: ignore[type-arg]
        """Test validation fails for invalid created_at type."""
        valid_baseline_data["created_at"] = "not-a-number"

        with pytest.raises(BaselineValidationError) as exc:
            validate_baseline(valid_baseline_data)

        assert "created_at" in str(exc.value).lower()

    def test_invalid_tags_type(self, valid_baseline_data: dict) -> None:  # type: ignore[type-arg]
        """Test validation fails for invalid tags type."""
        valid_baseline_data["tags"] = "not-a-list"

        with pytest.raises(BaselineValidationError) as exc:
            validate_baseline(valid_baseline_data)

        assert "tags" in str(exc.value).lower()

    def test_older_schema_version_ok(self, valid_baseline_data: dict) -> None:  # type: ignore[type-arg]
        """Test validation passes for older compatible schema version."""
        valid_baseline_data["schema_version"] = "1.0"

        # Should not raise
        validate_baseline(valid_baseline_data)
