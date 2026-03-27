"""Comparison engine for performance regression detection."""

from cow_performance.comparison.engine import ComparisonEngine
from cow_performance.comparison.models import (
    ComparisonResult,
    ComparisonVerdict,
    MetricComparison,
    MetricType,
    RegressionSeverity,
)
from cow_performance.comparison.reporter import RegressionReporter
from cow_performance.comparison.thresholds import (
    RELAXED_THRESHOLDS,
    STRICT_THRESHOLDS,
    MetricThresholds,
    RegressionThresholds,
    load_thresholds,
)

__all__ = [
    "ComparisonEngine",
    "ComparisonResult",
    "ComparisonVerdict",
    "MetricComparison",
    "MetricThresholds",
    "MetricType",
    "RegressionReporter",
    "RegressionSeverity",
    "RegressionThresholds",
    "RELAXED_THRESHOLDS",
    "STRICT_THRESHOLDS",
    "load_thresholds",
]
