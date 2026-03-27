"""Configurable thresholds for regression detection."""

import os
from dataclasses import dataclass, field
from pathlib import Path
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

    # Minimum absolute change in rate metrics (e.g. error_rate) to count as significant
    # (e.g. 0.01 = 1 percentage point absolute difference required)
    rate_significance: float = 0.01

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
            "statistics": {
                "significance_level": self.significance_level,
                "min_effect_size": self.min_effect_size,
                "rate_significance": self.rate_significance,
            },
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RegressionThresholds":
        """Deserialize thresholds from dict."""
        stats = data.get("statistics", {})
        # Support both flat (legacy) and nested (TOML) formats
        return cls(
            latency=MetricThresholds(**data.get("latency", {})),
            throughput=MetricThresholds(**data.get("throughput", {})),
            error_rate=MetricThresholds(**data.get("error_rate", {})),
            resource=MetricThresholds(**data.get("resource", {})),
            significance_level=stats.get(
                "significance_level", data.get("significance_level", 0.05)
            ),
            min_effect_size=stats.get("min_effect_size", data.get("min_effect_size", 0.2)),
            rate_significance=stats.get("rate_significance", data.get("rate_significance", 0.01)),
        )

    @classmethod
    def from_toml(cls, path: str | Path) -> "RegressionThresholds":
        """Load thresholds from a TOML file.

        Args:
            path: Path to the TOML configuration file

        Returns:
            RegressionThresholds loaded from file

        Raises:
            FileNotFoundError: If the file does not exist
            ValueError: If the file cannot be parsed
        """
        import tomllib

        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Threshold config not found: {path}")

        try:
            with open(path, "rb") as f:
                data = tomllib.load(f)
        except Exception as e:
            raise ValueError(f"Failed to parse threshold config {path}: {e}") from e

        return cls.from_dict(data)


# Pre-configured threshold profiles
STRICT_THRESHOLDS = RegressionThresholds(
    latency=MetricThresholds(minor=0.05, major=0.10, critical=0.20),
    throughput=MetricThresholds(minor=0.05, major=0.15, critical=0.30),
    error_rate=MetricThresholds(minor=0.005, major=0.01, critical=0.02),
    resource=MetricThresholds(minor=0.05, major=0.15, critical=0.30),
    significance_level=0.01,
    rate_significance=0.005,
)

RELAXED_THRESHOLDS = RegressionThresholds(
    latency=MetricThresholds(minor=0.20, major=0.30, critical=0.50),
    throughput=MetricThresholds(minor=0.20, major=0.40, critical=0.70),
    error_rate=MetricThresholds(minor=0.02, major=0.05, critical=0.10),
    resource=MetricThresholds(minor=0.20, major=0.40, critical=0.70),
    significance_level=0.10,
    rate_significance=0.02,
)

# Named profiles for env var selection
_PROFILES: dict[str, RegressionThresholds] = {
    "default": RegressionThresholds(),
    "strict": STRICT_THRESHOLDS,
    "relaxed": RELAXED_THRESHOLDS,
}


def load_thresholds(toml_path: str | Path | None = None) -> RegressionThresholds:
    """Load thresholds from a TOML file or env-var profile selection.

    Resolution order:
    1. ``toml_path`` argument (explicit file)
    2. ``COW_PERF_THRESHOLD_FILE`` env var (path to a TOML file)
    3. ``COW_PERF_THRESHOLD_PROFILE`` env var (``strict`` | ``relaxed`` | ``default``)
    4. Built-in defaults

    Args:
        toml_path: Optional explicit path to a TOML threshold config file.

    Returns:
        RegressionThresholds to use for comparison.

    Raises:
        FileNotFoundError: If a configured file path does not exist.
        ValueError: If an unknown profile name is given.
    """
    if toml_path is not None:
        return RegressionThresholds.from_toml(toml_path)

    file_env = os.environ.get("COW_PERF_THRESHOLD_FILE")
    if file_env:
        return RegressionThresholds.from_toml(file_env)

    profile_env = os.environ.get("COW_PERF_THRESHOLD_PROFILE", "").lower().strip()
    if profile_env:
        if profile_env not in _PROFILES:
            valid = ", ".join(_PROFILES)
            raise ValueError(f"Unknown threshold profile '{profile_env}'. Valid options: {valid}")
        return _PROFILES[profile_env]

    return RegressionThresholds()
