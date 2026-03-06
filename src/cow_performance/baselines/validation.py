"""Validation for baseline files."""

import logging
from typing import Any

from cow_performance.baselines.models import SCHEMA_VERSION

logger = logging.getLogger(__name__)


class BaselineValidationError(Exception):
    """Raised when baseline validation fails."""

    pass


REQUIRED_FIELDS = [
    "id",
    "name",
    "schema_version",
    "created_at",
]


def validate_baseline(data: dict[str, Any]) -> None:
    """
    Validate baseline data structure.

    Args:
        data: The baseline data dictionary to validate.

    Raises:
        BaselineValidationError: If validation fails.
    """
    # Check required fields
    missing_fields = [field for field in REQUIRED_FIELDS if field not in data]
    if missing_fields:
        raise BaselineValidationError(f"Missing required fields: {', '.join(missing_fields)}")

    # Validate schema version
    schema_version = data.get("schema_version")
    if schema_version is None:
        raise BaselineValidationError("Missing schema_version field")

    # Check major version compatibility
    try:
        file_major = int(schema_version.split(".")[0])
        current_major = int(SCHEMA_VERSION.split(".")[0])
    except (ValueError, IndexError, AttributeError) as e:
        raise BaselineValidationError(f"Invalid schema_version format: {schema_version}") from e

    if file_major > current_major:
        raise BaselineValidationError(
            f"Baseline schema version {schema_version} is newer than supported {SCHEMA_VERSION}. "
            "Please upgrade cow-performance to load this baseline."
        )

    # Validate id is a non-empty string
    baseline_id = data.get("id")
    if not baseline_id or not isinstance(baseline_id, str):
        raise BaselineValidationError("Invalid or missing 'id' field")

    # Validate name is a non-empty string
    name = data.get("name")
    if not name or not isinstance(name, str):
        raise BaselineValidationError("Invalid or missing 'name' field")

    # Validate created_at is a number
    created_at = data.get("created_at")
    if not isinstance(created_at, (int, float)):
        raise BaselineValidationError(f"Invalid 'created_at' field: {created_at}")

    # Validate tags is a list if present
    tags = data.get("tags")
    if tags is not None and not isinstance(tags, list):
        raise BaselineValidationError(f"Invalid 'tags' field: expected list, got {type(tags)}")

    logger.debug("Baseline validation passed: %s (schema %s)", baseline_id, schema_version)
