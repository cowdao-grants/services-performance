"""Data models for performance reports."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any

from cow_performance.baselines.models import PerformanceBaseline


class ReportVerdict(StrEnum):
    """Overall verdict for a performance test."""

    SUCCESS = "success"  # All metrics within acceptable thresholds
    WARNING = "warning"  # Some minor issues, but generally acceptable
    FAILURE = "failure"  # Critical issues detected


class RecommendationSeverity(StrEnum):
    """Severity level for recommendations."""

    CRITICAL = "critical"  # Immediate action required
    WARNING = "warning"  # Should be addressed soon
    INFO = "info"  # Informational suggestion


class RecommendationCategory(StrEnum):
    """Category of recommendation."""

    LATENCY = "latency"
    THROUGHPUT = "throughput"
    RELIABILITY = "reliability"
    RESOURCE = "resource"
    REGRESSION = "regression"


@dataclass
class Recommendation:
    """Actionable recommendation based on metrics analysis."""

    severity: RecommendationSeverity
    category: RecommendationCategory
    title: str
    description: str
    action: str
    metric_name: str | None = None  # Related metric, if applicable
    metric_value: float | None = None  # Current value of the metric
    threshold: float | None = None  # Threshold that was exceeded


@dataclass
class ExecutiveSummary:
    """High-level summary for quick assessment."""

    # Test identification
    test_name: str
    test_duration_seconds: float
    test_start_time: datetime
    test_end_time: datetime

    # Order metrics
    total_orders_submitted: int
    total_orders_filled: int
    total_orders_failed: int
    success_rate: float  # 0.0 to 1.0

    # Throughput
    average_throughput: float  # orders/second
    peak_throughput: float  # orders/second

    # Latency (P95 values in milliseconds)
    submission_latency_p95_ms: float
    fill_latency_p95_ms: float
    total_lifecycle_p95_ms: float

    # API performance
    total_api_requests: int
    api_success_rate: float
    api_response_time_p95_ms: float

    # Verdict
    verdict: ReportVerdict
    verdict_reason: str

    # Key findings (bullet points)
    key_findings: list[str] = field(default_factory=list)


@dataclass
class PerformanceReport:
    """Complete performance report."""

    # Identification
    report_id: str
    generated_at: datetime = field(default_factory=datetime.now)
    report_version: str = "1.0"

    # Test metadata
    test_name: str = ""
    scenario_name: str = ""
    git_commit: str | None = None
    git_branch: str | None = None

    # Summary
    summary: ExecutiveSummary | None = None

    # Detailed metrics (from baseline)
    baseline: PerformanceBaseline | None = None

    # Comparison results (optional, from COW-589)
    comparison: Any | None = None  # ComparisonResult when available

    # Recommendations
    recommendations: list[Recommendation] = field(default_factory=list)

    # Raw data paths (for reference)
    data_files: dict[str, str] = field(default_factory=dict)

    def has_critical_issues(self) -> bool:
        """Check if report contains critical issues."""
        return any(r.severity == RecommendationSeverity.CRITICAL for r in self.recommendations)

    def get_recommendations_by_severity(
        self, severity: RecommendationSeverity
    ) -> list[Recommendation]:
        """Get recommendations filtered by severity."""
        return [r for r in self.recommendations if r.severity == severity]

    def get_recommendations_by_category(
        self, category: RecommendationCategory
    ) -> list[Recommendation]:
        """Get recommendations filtered by category."""
        return [r for r in self.recommendations if r.category == category]
