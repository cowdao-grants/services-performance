"""Configurable thresholds for regression detection."""

from dataclasses import dataclass, field
from typing import Any

from cow_performance.comparison.models import MetricType, RegressionSeverity


@dataclass
class MetricThresholds:
    """
    Thresholds for a specific metric type.

    All values are percentages (0.10 = 10%).
    For latency/resource/error_rate: increase beyond threshold = regression.
    For throughput: decrease beyond threshold = regression.
    """

    minor: float = 0.10  # 10% - Minor regression threshold
    major: float = 0.15  # 15% - Major regression threshold
    critical: float = 0.30  # 30% - Critical regression threshold

    def classify_severity(
        self,
        percent_change: float,
        metric_type: MetricType,
    ) -> RegressionSeverity:
        """
        Classify regression severity based on percent change.

        Args:
            percent_change: The percentage change (positive = increase)
            metric_type: The type of metric (affects direction interpretation)

        Returns:
            RegressionSeverity classification
        """
        # For throughput, we care about decreases (negative change)
        # For others, we care about increases (positive change)
        if metric_type == MetricType.THROUGHPUT:
            change = -percent_change  # Flip sign: decrease becomes positive
        else:
            change = percent_change

        # Classify based on magnitude
        if change >= self.critical:
            return RegressionSeverity.CRITICAL
        elif change >= self.major:
            return RegressionSeverity.MAJOR
        elif change >= self.minor:
            return RegressionSeverity.MINOR
        else:
            return RegressionSeverity.NONE


@dataclass
class RegressionThresholds:
    """
    Complete threshold configuration for regression detection.

    Provides sensible defaults that can be customized per-environment
    or per-metric type.
    """

    # Per-metric-type thresholds
    latency: MetricThresholds = field(
        default_factory=lambda: MetricThresholds(
            minor=0.10,  # 10% latency increase = minor
            major=0.15,  # 15% latency increase = major
            critical=0.30,  # 30% latency increase = critical
        )
    )

    throughput: MetricThresholds = field(
        default_factory=lambda: MetricThresholds(
            minor=0.10,  # 10% throughput decrease = minor
            major=0.25,  # 25% throughput decrease = major
            critical=0.50,  # 50% throughput decrease = critical
        )
    )

    error_rate: MetricThresholds = field(
        default_factory=lambda: MetricThresholds(
            minor=0.01,  # 1 percentage point increase = minor
            major=0.02,  # 2 percentage points = major
            critical=0.05,  # 5 percentage points = critical
        )
    )

    resource: MetricThresholds = field(
        default_factory=lambda: MetricThresholds(
            minor=0.10,  # 10% resource increase = minor
            major=0.20,  # 20% resource increase = major
            critical=0.50,  # 50% resource increase = critical
        )
    )

    # Statistical significance level (p-value threshold)
    significance_level: float = 0.05

    # Minimum effect size (Cohen's d) to consider meaningful
    min_effect_size: float = 0.2  # Small effect

    def get_thresholds_for_type(self, metric_type: MetricType) -> MetricThresholds:
        """Get thresholds for a specific metric type."""
        mapping = {
            MetricType.LATENCY: self.latency,
            MetricType.THROUGHPUT: self.throughput,
            MetricType.ERROR_RATE: self.error_rate,
            MetricType.RESOURCE: self.resource,
        }
        return mapping[metric_type]

    def classify_severity(
        self,
        percent_change: float,
        metric_type: MetricType,
    ) -> RegressionSeverity:
        """
        Classify regression severity for a metric.

        Args:
            percent_change: The percentage change (positive = increase)
            metric_type: The type of metric

        Returns:
            RegressionSeverity classification
        """
        thresholds = self.get_thresholds_for_type(metric_type)
        return thresholds.classify_severity(percent_change, metric_type)

    def to_dict(self) -> dict[str, Any]:
        """Serialize thresholds to dict."""
        return {
            "latency": {
                "minor": self.latency.minor,
                "major": self.latency.major,
                "critical": self.latency.critical,
            },
            "throughput": {
                "minor": self.throughput.minor,
                "major": self.throughput.major,
                "critical": self.throughput.critical,
            },
            "error_rate": {
                "minor": self.error_rate.minor,
                "major": self.error_rate.major,
                "critical": self.error_rate.critical,
            },
            "resource": {
                "minor": self.resource.minor,
                "major": self.resource.major,
                "critical": self.resource.critical,
            },
            "significance_level": self.significance_level,
            "min_effect_size": self.min_effect_size,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RegressionThresholds":
        """Deserialize thresholds from dict."""
        return cls(
            latency=MetricThresholds(**data.get("latency", {})),
            throughput=MetricThresholds(**data.get("throughput", {})),
            error_rate=MetricThresholds(**data.get("error_rate", {})),
            resource=MetricThresholds(**data.get("resource", {})),
            significance_level=data.get("significance_level", 0.05),
            min_effect_size=data.get("min_effect_size", 0.2),
        )


# Pre-configured threshold profiles
STRICT_THRESHOLDS = RegressionThresholds(
    latency=MetricThresholds(minor=0.05, major=0.10, critical=0.20),
    throughput=MetricThresholds(minor=0.05, major=0.15, critical=0.30),
    error_rate=MetricThresholds(minor=0.005, major=0.01, critical=0.02),
    resource=MetricThresholds(minor=0.05, major=0.15, critical=0.30),
    significance_level=0.01,
)

RELAXED_THRESHOLDS = RegressionThresholds(
    latency=MetricThresholds(minor=0.20, major=0.30, critical=0.50),
    throughput=MetricThresholds(minor=0.20, major=0.40, critical=0.70),
    error_rate=MetricThresholds(minor=0.02, major=0.05, critical=0.10),
    resource=MetricThresholds(minor=0.20, major=0.40, critical=0.70),
    significance_level=0.10,
)
