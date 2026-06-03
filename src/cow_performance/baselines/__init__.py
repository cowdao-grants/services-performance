"""Baseline snapshot system for performance testing."""

from cow_performance.baselines.git_info import get_git_info
from cow_performance.baselines.manager import BaselineManager
from cow_performance.baselines.models import (
    SCHEMA_VERSION,
    BaselineMetadata,
    PerformanceBaseline,
)
from cow_performance.baselines.validation import (
    BaselineValidationError,
    validate_baseline,
)

__all__ = [
    "SCHEMA_VERSION",
    "BaselineMetadata",
    "BaselineManager",
    "BaselineValidationError",
    "PerformanceBaseline",
    "get_git_info",
    "validate_baseline",
]
