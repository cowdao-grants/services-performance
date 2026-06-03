"""Data models for performance comparison results."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum


class RegressionSeverity(StrEnum):
    """Severity level of a regression."""

    CRITICAL = "critical"  # >30% latency increase, >50% throughput decrease, error rate >5%
    MAJOR = "major"  # >15% latency increase, >25% throughput decrease
    MINOR = "minor"  # >10% latency increase, >10% throughput decrease
    NONE = "none"  # Within acceptable variation


class ComparisonVerdict(StrEnum):
    """Overall verdict for a comparison."""

    IMPROVEMENT = "improvement"  # Net positive change
    REGRESSION = "regression"  # Net negative change
    NEUTRAL = "neutral"  # No significant change


class MetricType(StrEnum):
    """Type of metric being compared."""

    LATENCY = "latency"  # Time-based metrics (lower is better)
    THROUGHPUT = "throughput"  # Rate metrics (higher is better)
    ERROR_RATE = "error_rate"  # Error percentages (lower is better)
    RESOURCE = "resource"  # CPU/memory usage (lower is better)


@dataclass
class MetricComparison:
    """Comparison result for a single metric."""

    # Identification
    metric_name: str
    metric_type: MetricType

    # Values
    baseline_value: float
    current_value: float

    # Differences
    absolute_diff: float
    percent_change: float  # Positive = increase, negative = decrease

    # Statistical analysis
    p_value: float | None = None  # Statistical significance (None if not calculable)
    effect_size: float | None = None  # Cohen's d (None if not calculable)
    is_significant: bool = False  # p_value < significance_level

    # Classification
    regression_severity: RegressionSeverity = RegressionSeverity.NONE
    is_regression: bool = False  # Is this a performance regression?
    is_improvement: bool = False  # Is this a performance improvement?

    # Context
    context: str = ""  # Human-readable explanation

    def __post_init__(self) -> None:
        """Calculate derived fields."""
        # Determine if this is a regression or improvement based on metric type
        if self.metric_type == MetricType.THROUGHPUT:
            # For throughput, decrease is bad
            self.is_regression = (
                self.is_significant
                and self.percent_change < 0
                and self.regression_severity != RegressionSeverity.NONE
            )
            self.is_improvement = self.is_significant and self.percent_change > 0
        else:
            # For latency, error_rate, resource: increase is bad
            self.is_regression = (
                self.is_significant
                and self.percent_change > 0
                and self.regression_severity != RegressionSeverity.NONE
            )
            self.is_improvement = self.is_significant and self.percent_change < 0


@dataclass
class ComparisonResult:
    """Complete comparison result between baseline and current run."""

    # Identification
    baseline_id: str
    baseline_name: str
    current_id: str
    current_name: str
    compared_at: datetime = field(default_factory=datetime.now)

    # Overall verdict
    verdict: ComparisonVerdict = ComparisonVerdict.NEUTRAL

    # Detailed comparisons
    metric_comparisons: dict[str, MetricComparison] = field(default_factory=dict)

    # Categorized results (sorted by severity)
    regressions: list[MetricComparison] = field(default_factory=list)
    improvements: list[MetricComparison] = field(default_factory=list)

    # Counts by severity
    critical_count: int = 0
    major_count: int = 0
    minor_count: int = 0

    # Summary statistics
    total_metrics_compared: int = 0
    significant_changes: int = 0

    def add_comparison(self, comparison: MetricComparison) -> None:
        """Add a metric comparison to the result."""
        self.metric_comparisons[comparison.metric_name] = comparison
        self.total_metrics_compared += 1

        if comparison.is_significant:
            self.significant_changes += 1

        if comparison.is_regression:
            self.regressions.append(comparison)
            if comparison.regression_severity == RegressionSeverity.CRITICAL:
                self.critical_count += 1
            elif comparison.regression_severity == RegressionSeverity.MAJOR:
                self.major_count += 1
            elif comparison.regression_severity == RegressionSeverity.MINOR:
                self.minor_count += 1

        if comparison.is_improvement:
            self.improvements.append(comparison)

    def calculate_verdict(self) -> None:
        """Calculate the overall verdict based on comparisons."""
        # Sort regressions by severity
        severity_order = {
            RegressionSeverity.CRITICAL: 0,
            RegressionSeverity.MAJOR: 1,
            RegressionSeverity.MINOR: 2,
            RegressionSeverity.NONE: 3,
        }
        self.regressions.sort(key=lambda x: severity_order[x.regression_severity])

        # Determine verdict
        if self.critical_count > 0 or self.major_count >= 2:
            self.verdict = ComparisonVerdict.REGRESSION
        elif self.major_count > 0 or self.minor_count >= 3:
            self.verdict = ComparisonVerdict.REGRESSION
        elif len(self.regressions) > len(self.improvements):
            self.verdict = ComparisonVerdict.REGRESSION
        elif len(self.improvements) > len(self.regressions):
            self.verdict = ComparisonVerdict.IMPROVEMENT
        else:
            self.verdict = ComparisonVerdict.NEUTRAL
