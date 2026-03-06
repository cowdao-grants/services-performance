# COW-589: Comparison Engine and Regression Detection Implementation Plan

## Overview

Implement a sophisticated comparison engine that analyzes performance differences between test runs, detects regressions using statistical methods, and generates actionable reports highlighting performance changes. This is the third ticket in M2 (Performance Benchmarking), building upon COW-587 (Metrics Collection) and COW-588 (Baseline Snapshot System).

## Current State Analysis

### What Exists (from COW-587 and COW-588)

**Baseline System (`src/cow_performance/baselines/`):**
- `PerformanceBaseline` dataclass with aggregated metrics
- `BaselineManager` for CRUD operations (load, save, list, delete)
- Git info capture with `GitInfo` dataclass
- Validation with `BaselineValidationError`

**Metrics Models (from COW-611 plan, imports in `baselines/models.py`):**
- `PercentileStats` - Statistical summary with p50/p90/p95/p99
- `OrderAggregateMetrics` - Order lifecycle stats with timing percentiles
- `APIAggregateMetrics` - API response time stats
- `ResourceAggregateMetrics` - CPU/memory usage stats

**Dependencies Available (`pyproject.toml`):**
- `numpy = "^2.0.0"` - Array operations and basic statistics
- `scipy = "^1.14.0"` - Statistical tests (t-test, Mann-Whitney U)

### Key Data Structures to Compare

```python
# From PerformanceBaseline:
order_metrics: OrderAggregateMetrics | None
  ├── success_rate: float
  ├── failure_rate: float
  ├── time_to_submit: PercentileStats (p50, p90, p95, p99)
  ├── time_to_accept: PercentileStats
  ├── time_to_fill: PercentileStats
  └── total_lifecycle: PercentileStats

api_metrics: APIAggregateMetrics | None
  ├── success_rate: float
  ├── response_time: PercentileStats
  └── requests_per_second: float

resource_metrics: dict[str, ResourceAggregateMetrics]
  └── [container_name]:
      ├── cpu_percent: PercentileStats
      ├── memory_percent: PercentileStats
      └── memory_bytes: PercentileStats

orders_per_second: float
peak_orders_per_second: float
```

## Desired End State

After this plan is complete:

1. **Comparison Data Models** (`comparison/models.py`):
   - `MetricComparison` - Single metric comparison with significance and severity
   - `ComparisonResult` - Full comparison between baseline and current run
   - `RegressionSeverity` enum (critical, major, minor, none)
   - `ComparisonVerdict` enum (improvement, regression, neutral)

2. **Thresholds Configuration** (`comparison/thresholds.py`):
   - `MetricThresholds` - Per-metric threshold configuration
   - `RegressionThresholds` - Complete threshold settings with defaults

3. **Statistical Functions** (`comparison/statistics.py`):
   - Percentage change calculation
   - Statistical significance (p-value via t-test / Mann-Whitney U)
   - Effect size calculation (Cohen's d)
   - Severity classification based on thresholds

4. **Comparison Engine** (`comparison/engine.py`):
   - `ComparisonEngine` class
   - Compare latency metrics (all PercentileStats fields)
   - Compare rates (success_rate, failure_rate)
   - Compare throughput metrics
   - Compare resource utilization
   - Generate overall verdict

5. **Regression Reporter** (`comparison/reporter.py`):
   - `RegressionReporter` class
   - Text report generation
   - Markdown report generation (for GitHub PRs)
   - JSON export

6. **Unit Tests** for all components with >90% coverage

### Verification

```bash
# All tests pass
poetry run pytest tests/unit/test_comparison_*.py -v

# Type checking
poetry run mypy src/cow_performance/comparison/

# Linting
poetry run ruff check src/cow_performance/comparison/

# Full workflow
poetry run black src/ tests/ && poetry run ruff check --fix src/ tests/ && poetry run mypy src/
```

## What We're NOT Doing

- **No raw metrics comparison**: We compare aggregated `PercentileStats`, not individual data points
- **No historical trend analysis**: Single baseline-to-current comparison only
- **No HTML reports**: Markdown and text only (HTML is COW-590)
- **No CLI integration**: That comes in COW-590 (Automated Reporting)
- **No automatic threshold tuning**: Thresholds are static configuration
- **No Bonferroni correction**: Simple p-value threshold without multiple testing adjustment

## Implementation Approach

We'll implement in 5 phases, each resulting in a working, testable increment:

1. **Phase 1**: Data models (`MetricComparison`, `ComparisonResult`, enums)
2. **Phase 2**: Thresholds configuration (`RegressionThresholds`)
3. **Phase 3**: Statistical functions (significance, effect size)
4. **Phase 4**: Comparison engine (`ComparisonEngine`)
5. **Phase 5**: Reporter (`RegressionReporter`)

---

## Phase 1: Comparison Data Models

### Overview

Define the core data models for comparison results following codebase patterns (dataclasses).

### Changes Required

#### 1. Create Module Structure

**File**: `src/cow_performance/comparison/__init__.py`

```python
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
    MetricThresholds,
    RegressionThresholds,
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
]
```

#### 2. Define Data Models

**File**: `src/cow_performance/comparison/models.py`

```python
"""Data models for performance comparison results."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class RegressionSeverity(str, Enum):
    """Severity level of a regression."""

    CRITICAL = "critical"  # >30% latency increase, >50% throughput decrease, error rate >5%
    MAJOR = "major"  # >15% latency increase, >25% throughput decrease
    MINOR = "minor"  # >10% latency increase, >10% throughput decrease
    NONE = "none"  # Within acceptable variation


class ComparisonVerdict(str, Enum):
    """Overall verdict for a comparison."""

    IMPROVEMENT = "improvement"  # Net positive change
    REGRESSION = "regression"  # Net negative change
    NEUTRAL = "neutral"  # No significant change


class MetricType(str, Enum):
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
```

### Success Criteria

#### Automated Verification

- [x] `poetry run pytest tests/unit/test_comparison_models.py -v`
- [x] `poetry run mypy src/cow_performance/comparison/models.py`
- [x] `poetry run ruff check src/cow_performance/comparison/models.py`

#### Manual Verification

- [x] MetricComparison correctly identifies regressions vs improvements
- [x] ComparisonResult verdict calculation is logical

---

## Phase 2: Thresholds Configuration

### Overview

Define configurable thresholds for regression detection, allowing per-metric customization.

### Changes Required

#### 1. Create Thresholds Module

**File**: `src/cow_performance/comparison/thresholds.py`

```python
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
```

### Success Criteria

#### Automated Verification

- [x] `poetry run pytest tests/unit/test_comparison_thresholds.py -v`
- [x] `poetry run mypy src/cow_performance/comparison/thresholds.py`

#### Manual Verification

- [x] Default thresholds match ticket specifications
- [x] Severity classification works correctly for all metric types

---

## Phase 3: Statistical Functions

### Overview

Implement statistical comparison functions using scipy for significance testing and effect size calculation.

### Changes Required

#### 1. Create Statistics Module

**File**: `src/cow_performance/comparison/statistics.py`

```python
"""Statistical functions for performance comparison."""

import math
from dataclasses import dataclass

import numpy as np
from scipy import stats


@dataclass
class StatisticalResult:
    """Result of statistical comparison."""

    p_value: float | None
    effect_size: float | None  # Cohen's d
    is_significant: bool
    test_used: str  # Name of the statistical test used


def calculate_percent_change(
    baseline_value: float,
    current_value: float,
) -> float:
    """
    Calculate percentage change between baseline and current.

    Args:
        baseline_value: The baseline (reference) value
        current_value: The current (test) value

    Returns:
        Percentage change as a decimal (0.10 = 10% increase)
        Positive = increase, negative = decrease
    """
    if baseline_value == 0:
        if current_value == 0:
            return 0.0
        # Infinite change from zero - return large value
        return float("inf") if current_value > 0 else float("-inf")

    return (current_value - baseline_value) / abs(baseline_value)


def calculate_cohens_d(
    baseline_mean: float,
    current_mean: float,
    baseline_std: float,
    current_std: float,
    baseline_n: int,
    current_n: int,
) -> float | None:
    """
    Calculate Cohen's d effect size.

    Uses pooled standard deviation for two independent samples.

    Args:
        baseline_mean: Mean of baseline sample
        current_mean: Mean of current sample
        baseline_std: Standard deviation of baseline
        current_std: Standard deviation of current
        baseline_n: Sample size of baseline
        current_n: Sample size of current

    Returns:
        Cohen's d value, or None if calculation not possible
    """
    if baseline_n < 2 or current_n < 2:
        return None

    # Calculate pooled standard deviation
    pooled_variance = (
        ((baseline_n - 1) * baseline_std**2 + (current_n - 1) * current_std**2)
        / (baseline_n + current_n - 2)
    )

    if pooled_variance <= 0:
        return None

    pooled_std = math.sqrt(pooled_variance)

    if pooled_std == 0:
        return None

    return (current_mean - baseline_mean) / pooled_std


def welchs_t_test(
    baseline_mean: float,
    current_mean: float,
    baseline_std: float,
    current_std: float,
    baseline_n: int,
    current_n: int,
) -> tuple[float, float] | None:
    """
    Perform Welch's t-test for unequal variances.

    Args:
        baseline_mean: Mean of baseline sample
        current_mean: Mean of current sample
        baseline_std: Standard deviation of baseline
        current_std: Standard deviation of current
        baseline_n: Sample size of baseline
        current_n: Sample size of current

    Returns:
        Tuple of (t-statistic, p-value) or None if not calculable
    """
    if baseline_n < 2 or current_n < 2:
        return None

    if baseline_std == 0 and current_std == 0:
        # No variance in either sample
        if baseline_mean == current_mean:
            return (0.0, 1.0)  # No difference
        return None

    # Calculate standard error
    se_baseline = baseline_std**2 / baseline_n
    se_current = current_std**2 / current_n
    se_diff = math.sqrt(se_baseline + se_current)

    if se_diff == 0:
        return None

    # Calculate t-statistic
    t_stat = (current_mean - baseline_mean) / se_diff

    # Calculate degrees of freedom (Welch-Satterthwaite)
    numerator = (se_baseline + se_current) ** 2
    denominator = (se_baseline**2 / (baseline_n - 1)) + (se_current**2 / (current_n - 1))

    if denominator == 0:
        return None

    df = numerator / denominator

    # Calculate two-tailed p-value
    p_value = 2 * stats.t.sf(abs(t_stat), df)

    return (t_stat, p_value)


def compare_percentile_stats(
    baseline_mean: float,
    baseline_std: float,
    baseline_count: int,
    current_mean: float,
    current_std: float,
    current_count: int,
    significance_level: float = 0.05,
) -> StatisticalResult:
    """
    Compare two samples using statistical tests.

    Uses Welch's t-test (robust to unequal variances).
    Falls back to simple comparison if sample sizes are too small.

    Args:
        baseline_mean: Mean of baseline
        baseline_std: Std dev of baseline
        baseline_count: Sample size of baseline
        current_mean: Mean of current
        current_std: Std dev of current
        current_count: Sample size of current
        significance_level: P-value threshold for significance

    Returns:
        StatisticalResult with p-value, effect size, and significance
    """
    # Calculate effect size
    effect_size = calculate_cohens_d(
        baseline_mean,
        current_mean,
        baseline_std,
        current_std,
        baseline_count,
        current_count,
    )

    # Try t-test
    t_test_result = welchs_t_test(
        baseline_mean,
        current_mean,
        baseline_std,
        current_std,
        baseline_count,
        current_count,
    )

    if t_test_result is not None:
        _, p_value = t_test_result
        return StatisticalResult(
            p_value=p_value,
            effect_size=effect_size,
            is_significant=p_value < significance_level,
            test_used="Welch's t-test",
        )

    # Fallback: no statistical test possible
    # Consider significant if there's a meaningful effect size
    is_significant = effect_size is not None and abs(effect_size) >= 0.5

    return StatisticalResult(
        p_value=None,
        effect_size=effect_size,
        is_significant=is_significant,
        test_used="effect_size_only",
    )


def interpret_effect_size(cohens_d: float | None) -> str:
    """
    Interpret Cohen's d effect size.

    Args:
        cohens_d: Cohen's d value

    Returns:
        Human-readable interpretation
    """
    if cohens_d is None:
        return "unknown"

    d = abs(cohens_d)
    if d < 0.2:
        return "negligible"
    elif d < 0.5:
        return "small"
    elif d < 0.8:
        return "medium"
    else:
        return "large"


def format_percent_change(percent_change: float) -> str:
    """
    Format percentage change for display.

    Args:
        percent_change: Decimal percentage (0.10 = 10%)

    Returns:
        Formatted string like "+10.0%" or "-5.2%"
    """
    if math.isinf(percent_change):
        return "∞%" if percent_change > 0 else "-∞%"

    sign = "+" if percent_change >= 0 else ""
    return f"{sign}{percent_change * 100:.1f}%"
```

### Success Criteria

#### Automated Verification

- [x] `poetry run pytest tests/unit/test_comparison_statistics.py -v`
- [x] `poetry run mypy src/cow_performance/comparison/statistics.py`

#### Manual Verification

- [x] Percent change calculation handles edge cases (zero baseline)
- [x] Cohen's d matches expected values for known data
- [x] T-test produces valid p-values

---

## Phase 4: Comparison Engine

### Overview

Implement the core `ComparisonEngine` class that compares two baselines and produces a `ComparisonResult`.

### Changes Required

#### 1. Create Engine Module

**File**: `src/cow_performance/comparison/engine.py`

```python
"""Comparison engine for performance baselines."""

import logging
from datetime import datetime

from cow_performance.baselines.models import PerformanceBaseline
from cow_performance.comparison.models import (
    ComparisonResult,
    MetricComparison,
    MetricType,
)
from cow_performance.comparison.statistics import (
    calculate_percent_change,
    compare_percentile_stats,
    format_percent_change,
    interpret_effect_size,
)
from cow_performance.comparison.thresholds import RegressionThresholds
from cow_performance.metrics.aggregator import PercentileStats

logger = logging.getLogger(__name__)


class ComparisonEngine:
    """
    Engine for comparing performance baselines.

    Compares aggregated metrics between a baseline and current run,
    calculates statistical significance, and classifies regressions.

    Example:
        engine = ComparisonEngine()
        result = engine.compare(baseline, current)
        if result.verdict == ComparisonVerdict.REGRESSION:
            print(f"Found {result.critical_count} critical regressions")
    """

    def __init__(
        self,
        thresholds: RegressionThresholds | None = None,
    ):
        """
        Initialize the comparison engine.

        Args:
            thresholds: Optional threshold configuration.
                       Uses default thresholds if not specified.
        """
        self._thresholds = thresholds or RegressionThresholds()

    @property
    def thresholds(self) -> RegressionThresholds:
        """Get the current threshold configuration."""
        return self._thresholds

    def compare(
        self,
        baseline: PerformanceBaseline,
        current: PerformanceBaseline,
    ) -> ComparisonResult:
        """
        Compare two baselines and generate a comparison result.

        Args:
            baseline: The reference baseline
            current: The current run to compare

        Returns:
            ComparisonResult with detailed metric comparisons
        """
        result = ComparisonResult(
            baseline_id=baseline.id,
            baseline_name=baseline.name,
            current_id=current.id,
            current_name=current.name,
            compared_at=datetime.now(),
        )

        # Compare order metrics
        if baseline.order_metrics and current.order_metrics:
            self._compare_order_metrics(
                baseline.order_metrics,
                current.order_metrics,
                result,
            )

        # Compare API metrics
        if baseline.api_metrics and current.api_metrics:
            self._compare_api_metrics(
                baseline.api_metrics,
                current.api_metrics,
                result,
            )

        # Compare throughput metrics
        self._compare_throughput(baseline, current, result)

        # Compare resource metrics
        self._compare_resource_metrics(
            baseline.resource_metrics,
            current.resource_metrics,
            result,
        )

        # Calculate overall verdict
        result.calculate_verdict()

        logger.info(
            "Comparison complete: %s vs %s - verdict: %s, "
            "%d critical, %d major, %d minor regressions",
            baseline.name,
            current.name,
            result.verdict.value,
            result.critical_count,
            result.major_count,
            result.minor_count,
        )

        return result

    def _compare_percentile_stats(
        self,
        metric_name: str,
        metric_type: MetricType,
        baseline_stats: PercentileStats,
        current_stats: PercentileStats,
    ) -> MetricComparison:
        """
        Compare two PercentileStats objects.

        Args:
            metric_name: Name for this metric
            metric_type: Type of metric (latency, throughput, etc.)
            baseline_stats: Baseline statistics
            current_stats: Current statistics

        Returns:
            MetricComparison for this metric
        """
        # Calculate percent change using p95 (more robust than mean for latency)
        baseline_value = baseline_stats.p95
        current_value = current_stats.p95
        percent_change = calculate_percent_change(baseline_value, current_value)

        # Statistical comparison using mean and std
        stat_result = compare_percentile_stats(
            baseline_mean=baseline_stats.mean,
            baseline_std=baseline_stats.std_dev,
            baseline_count=baseline_stats.count,
            current_mean=current_stats.mean,
            current_std=current_stats.std_dev,
            current_count=current_stats.count,
            significance_level=self._thresholds.significance_level,
        )

        # Classify severity
        severity = self._thresholds.classify_severity(percent_change, metric_type)

        # Generate context
        context = self._generate_context(
            metric_name,
            metric_type,
            percent_change,
            stat_result.is_significant,
            severity.value,
            stat_result.effect_size,
        )

        return MetricComparison(
            metric_name=metric_name,
            metric_type=metric_type,
            baseline_value=baseline_value,
            current_value=current_value,
            absolute_diff=current_value - baseline_value,
            percent_change=percent_change,
            p_value=stat_result.p_value,
            effect_size=stat_result.effect_size,
            is_significant=stat_result.is_significant,
            regression_severity=severity,
            context=context,
        )

    def _compare_rate(
        self,
        metric_name: str,
        metric_type: MetricType,
        baseline_value: float,
        current_value: float,
    ) -> MetricComparison:
        """
        Compare simple rate metrics (success_rate, failure_rate).

        Args:
            metric_name: Name for this metric
            metric_type: Type of metric
            baseline_value: Baseline rate
            current_value: Current rate

        Returns:
            MetricComparison for this metric
        """
        percent_change = calculate_percent_change(baseline_value, current_value)

        # For rates, we use absolute difference for significance
        # (e.g., going from 0.95 to 0.93 is a 2 percentage point drop)
        absolute_diff = current_value - baseline_value

        # Simple significance check for rates
        # Consider significant if change is > 1 percentage point
        is_significant = abs(absolute_diff) > 0.01

        # Classify severity
        severity = self._thresholds.classify_severity(percent_change, metric_type)

        # Generate context
        context = self._generate_rate_context(
            metric_name,
            metric_type,
            baseline_value,
            current_value,
            absolute_diff,
        )

        return MetricComparison(
            metric_name=metric_name,
            metric_type=metric_type,
            baseline_value=baseline_value,
            current_value=current_value,
            absolute_diff=absolute_diff,
            percent_change=percent_change,
            is_significant=is_significant,
            regression_severity=severity,
            context=context,
        )

    def _compare_order_metrics(
        self,
        baseline: "OrderAggregateMetrics",
        current: "OrderAggregateMetrics",
        result: ComparisonResult,
    ) -> None:
        """Compare order lifecycle metrics."""
        # Compare success rate
        result.add_comparison(
            self._compare_rate(
                "order_success_rate",
                MetricType.ERROR_RATE,  # Lower failure is better
                baseline.success_rate,
                current.success_rate,
            )
        )

        # Compare latency metrics
        latency_metrics = [
            ("time_to_submit", baseline.time_to_submit, current.time_to_submit),
            ("time_to_accept", baseline.time_to_accept, current.time_to_accept),
            ("time_to_fill", baseline.time_to_fill, current.time_to_fill),
            ("total_lifecycle", baseline.total_lifecycle, current.total_lifecycle),
        ]

        for name, baseline_stats, current_stats in latency_metrics:
            if baseline_stats.count > 0 and current_stats.count > 0:
                result.add_comparison(
                    self._compare_percentile_stats(
                        f"order_{name}",
                        MetricType.LATENCY,
                        baseline_stats,
                        current_stats,
                    )
                )

    def _compare_api_metrics(
        self,
        baseline: "APIAggregateMetrics",
        current: "APIAggregateMetrics",
        result: ComparisonResult,
    ) -> None:
        """Compare API metrics."""
        # Compare success rate
        result.add_comparison(
            self._compare_rate(
                "api_success_rate",
                MetricType.ERROR_RATE,
                baseline.success_rate,
                current.success_rate,
            )
        )

        # Compare response time
        if baseline.response_time.count > 0 and current.response_time.count > 0:
            result.add_comparison(
                self._compare_percentile_stats(
                    "api_response_time",
                    MetricType.LATENCY,
                    baseline.response_time,
                    current.response_time,
                )
            )

        # Compare throughput
        result.add_comparison(
            self._compare_rate(
                "api_requests_per_second",
                MetricType.THROUGHPUT,
                baseline.requests_per_second,
                current.requests_per_second,
            )
        )

    def _compare_throughput(
        self,
        baseline: PerformanceBaseline,
        current: PerformanceBaseline,
        result: ComparisonResult,
    ) -> None:
        """Compare throughput metrics."""
        result.add_comparison(
            self._compare_rate(
                "orders_per_second",
                MetricType.THROUGHPUT,
                baseline.orders_per_second,
                current.orders_per_second,
            )
        )

        result.add_comparison(
            self._compare_rate(
                "peak_orders_per_second",
                MetricType.THROUGHPUT,
                baseline.peak_orders_per_second,
                current.peak_orders_per_second,
            )
        )

    def _compare_resource_metrics(
        self,
        baseline_resources: dict[str, "ResourceAggregateMetrics"],
        current_resources: dict[str, "ResourceAggregateMetrics"],
        result: ComparisonResult,
    ) -> None:
        """Compare resource utilization metrics."""
        # Find common containers
        common_containers = set(baseline_resources.keys()) & set(current_resources.keys())

        for container in common_containers:
            baseline = baseline_resources[container]
            current = current_resources[container]

            if baseline.sample_count > 0 and current.sample_count > 0:
                # Compare CPU usage
                result.add_comparison(
                    self._compare_percentile_stats(
                        f"resource_{container}_cpu",
                        MetricType.RESOURCE,
                        baseline.cpu_percent,
                        current.cpu_percent,
                    )
                )

                # Compare memory usage
                result.add_comparison(
                    self._compare_percentile_stats(
                        f"resource_{container}_memory",
                        MetricType.RESOURCE,
                        baseline.memory_percent,
                        current.memory_percent,
                    )
                )

    def _generate_context(
        self,
        metric_name: str,
        metric_type: MetricType,
        percent_change: float,
        is_significant: bool,
        severity: str,
        effect_size: float | None,
    ) -> str:
        """Generate human-readable context for a comparison."""
        change_str = format_percent_change(percent_change)
        effect_str = interpret_effect_size(effect_size)

        if not is_significant:
            return f"{metric_name}: {change_str} (not statistically significant)"

        direction = "increased" if percent_change > 0 else "decreased"

        if metric_type == MetricType.THROUGHPUT:
            good_bad = "improved" if percent_change > 0 else "degraded"
        else:
            good_bad = "degraded" if percent_change > 0 else "improved"

        return (
            f"{metric_name}: {change_str} ({direction}, {good_bad}), "
            f"severity={severity}, effect size={effect_str}"
        )

    def _generate_rate_context(
        self,
        metric_name: str,
        metric_type: MetricType,
        baseline_value: float,
        current_value: float,
        absolute_diff: float,
    ) -> str:
        """Generate context for rate metric comparison."""
        baseline_pct = baseline_value * 100
        current_pct = current_value * 100
        diff_pct = absolute_diff * 100

        if metric_type == MetricType.ERROR_RATE:
            # For error rates, lower is better
            if metric_name.endswith("success_rate"):
                good_bad = "improved" if absolute_diff > 0 else "degraded"
            else:
                good_bad = "degraded" if absolute_diff > 0 else "improved"
        elif metric_type == MetricType.THROUGHPUT:
            good_bad = "improved" if absolute_diff > 0 else "degraded"
        else:
            good_bad = "changed"

        sign = "+" if absolute_diff >= 0 else ""
        return (
            f"{metric_name}: {baseline_pct:.1f}% → {current_pct:.1f}% "
            f"({sign}{diff_pct:.1f} pp, {good_bad})"
        )


# Import types for type hints
from cow_performance.metrics.aggregator import (  # noqa: E402
    APIAggregateMetrics,
    OrderAggregateMetrics,
    ResourceAggregateMetrics,
)
```

### Success Criteria

#### Automated Verification

- [x] `poetry run pytest tests/unit/test_comparison_engine.py -v`
- [x] `poetry run mypy src/cow_performance/comparison/engine.py`

#### Manual Verification

- [x] Compare two real baselines and verify logical results
- [x] Regressions are correctly identified for latency increases
- [x] Improvements are correctly identified for latency decreases
- [x] Throughput handled correctly (decrease = regression)

---

## Phase 5: Regression Reporter

### Overview

Implement report generation in text and Markdown formats for displaying comparison results.

### Changes Required

#### 1. Create Reporter Module

**File**: `src/cow_performance/comparison/reporter.py`

```python
"""Report generation for comparison results."""

import json
from datetime import datetime
from typing import Any

from cow_performance.comparison.models import (
    ComparisonResult,
    ComparisonVerdict,
    MetricComparison,
    RegressionSeverity,
)
from cow_performance.comparison.statistics import format_percent_change


class RegressionReporter:
    """
    Generates reports from comparison results.

    Supports multiple output formats: text, markdown, JSON.

    Example:
        reporter = RegressionReporter()
        text_report = reporter.generate_text_report(comparison_result)
        md_report = reporter.generate_markdown_report(comparison_result)
    """

    def __init__(self) -> None:
        """Initialize the reporter."""
        pass

    def generate_text_report(self, result: ComparisonResult) -> str:
        """
        Generate a plain text report.

        Args:
            result: The comparison result to report

        Returns:
            Formatted text report
        """
        lines: list[str] = []

        # Header
        lines.append("=" * 70)
        lines.append("PERFORMANCE COMPARISON REPORT")
        lines.append("=" * 70)
        lines.append("")

        # Summary
        lines.append(f"Baseline:  {result.baseline_name} ({result.baseline_id[:8]})")
        lines.append(f"Current:   {result.current_name} ({result.current_id[:8]})")
        lines.append(f"Compared:  {result.compared_at.strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")

        # Verdict
        verdict_symbol = self._get_verdict_symbol(result.verdict)
        lines.append(f"VERDICT: {verdict_symbol} {result.verdict.value.upper()}")
        lines.append("")

        # Summary counts
        lines.append(f"Total metrics compared: {result.total_metrics_compared}")
        lines.append(f"Significant changes:    {result.significant_changes}")
        lines.append(f"Regressions:            {len(result.regressions)}")
        lines.append(f"  - Critical: {result.critical_count}")
        lines.append(f"  - Major:    {result.major_count}")
        lines.append(f"  - Minor:    {result.minor_count}")
        lines.append(f"Improvements:           {len(result.improvements)}")
        lines.append("")

        # Critical regressions (if any)
        if result.critical_count > 0:
            lines.append("-" * 70)
            lines.append("CRITICAL REGRESSIONS")
            lines.append("-" * 70)
            for comparison in result.regressions:
                if comparison.regression_severity == RegressionSeverity.CRITICAL:
                    lines.append(self._format_comparison_text(comparison))
            lines.append("")

        # Major regressions (if any)
        if result.major_count > 0:
            lines.append("-" * 70)
            lines.append("MAJOR REGRESSIONS")
            lines.append("-" * 70)
            for comparison in result.regressions:
                if comparison.regression_severity == RegressionSeverity.MAJOR:
                    lines.append(self._format_comparison_text(comparison))
            lines.append("")

        # Minor regressions (if any)
        if result.minor_count > 0:
            lines.append("-" * 70)
            lines.append("MINOR REGRESSIONS")
            lines.append("-" * 70)
            for comparison in result.regressions:
                if comparison.regression_severity == RegressionSeverity.MINOR:
                    lines.append(self._format_comparison_text(comparison))
            lines.append("")

        # Improvements (if any)
        if result.improvements:
            lines.append("-" * 70)
            lines.append("IMPROVEMENTS")
            lines.append("-" * 70)
            for comparison in result.improvements:
                lines.append(self._format_comparison_text(comparison))
            lines.append("")

        # Footer
        lines.append("=" * 70)

        return "\n".join(lines)

    def generate_markdown_report(self, result: ComparisonResult) -> str:
        """
        Generate a Markdown report suitable for GitHub PRs.

        Args:
            result: The comparison result to report

        Returns:
            Formatted Markdown report
        """
        lines: list[str] = []

        # Header with verdict badge
        verdict_emoji = self._get_verdict_emoji(result.verdict)
        lines.append(f"## {verdict_emoji} Performance Comparison Report")
        lines.append("")

        # Summary table
        lines.append("| Property | Value |")
        lines.append("|----------|-------|")
        lines.append(f"| Baseline | `{result.baseline_name}` ({result.baseline_id[:8]}) |")
        lines.append(f"| Current | `{result.current_name}` ({result.current_id[:8]}) |")
        lines.append(f"| Compared | {result.compared_at.strftime('%Y-%m-%d %H:%M:%S')} |")
        lines.append(f"| **Verdict** | **{result.verdict.value.upper()}** |")
        lines.append("")

        # Summary stats
        lines.append("### Summary")
        lines.append("")
        lines.append(f"- **Total metrics compared:** {result.total_metrics_compared}")
        lines.append(f"- **Significant changes:** {result.significant_changes}")
        lines.append(f"- **Regressions:** {len(result.regressions)} "
                    f"({result.critical_count} critical, "
                    f"{result.major_count} major, "
                    f"{result.minor_count} minor)")
        lines.append(f"- **Improvements:** {len(result.improvements)}")
        lines.append("")

        # Regressions section
        if result.regressions:
            lines.append("### Regressions")
            lines.append("")
            lines.append(self._generate_comparison_table_md(result.regressions))
            lines.append("")

        # Improvements section
        if result.improvements:
            lines.append("### Improvements")
            lines.append("")
            lines.append(self._generate_comparison_table_md(result.improvements))
            lines.append("")

        # Detailed metrics (collapsible)
        lines.append("<details>")
        lines.append("<summary>All Metric Comparisons</summary>")
        lines.append("")
        lines.append(self._generate_all_metrics_table_md(result))
        lines.append("")
        lines.append("</details>")
        lines.append("")

        return "\n".join(lines)

    def generate_json_report(self, result: ComparisonResult) -> str:
        """
        Generate a JSON report.

        Args:
            result: The comparison result to report

        Returns:
            JSON string
        """
        data = self._result_to_dict(result)
        return json.dumps(data, indent=2, default=str)

    def _get_verdict_symbol(self, verdict: ComparisonVerdict) -> str:
        """Get ASCII symbol for verdict."""
        mapping = {
            ComparisonVerdict.IMPROVEMENT: "[+]",
            ComparisonVerdict.REGRESSION: "[!]",
            ComparisonVerdict.NEUTRAL: "[=]",
        }
        return mapping[verdict]

    def _get_verdict_emoji(self, verdict: ComparisonVerdict) -> str:
        """Get emoji for verdict."""
        mapping = {
            ComparisonVerdict.IMPROVEMENT: "✅",
            ComparisonVerdict.REGRESSION: "⚠️",
            ComparisonVerdict.NEUTRAL: "➡️",
        }
        return mapping[verdict]

    def _get_severity_emoji(self, severity: RegressionSeverity) -> str:
        """Get emoji for severity level."""
        mapping = {
            RegressionSeverity.CRITICAL: "🔴",
            RegressionSeverity.MAJOR: "🟠",
            RegressionSeverity.MINOR: "🟡",
            RegressionSeverity.NONE: "⚪",
        }
        return mapping[severity]

    def _format_comparison_text(self, comparison: MetricComparison) -> str:
        """Format a single comparison for text output."""
        change_str = format_percent_change(comparison.percent_change)
        return (
            f"  {comparison.metric_name}:\n"
            f"    Baseline: {comparison.baseline_value:.4f}\n"
            f"    Current:  {comparison.current_value:.4f}\n"
            f"    Change:   {change_str}\n"
            f"    {comparison.context}"
        )

    def _generate_comparison_table_md(
        self,
        comparisons: list[MetricComparison],
    ) -> str:
        """Generate a Markdown table for comparisons."""
        lines = [
            "| Severity | Metric | Baseline | Current | Change |",
            "|----------|--------|----------|---------|--------|",
        ]

        for c in comparisons:
            severity_emoji = self._get_severity_emoji(c.regression_severity)
            change_str = format_percent_change(c.percent_change)
            lines.append(
                f"| {severity_emoji} {c.regression_severity.value} | "
                f"`{c.metric_name}` | "
                f"{c.baseline_value:.4f} | "
                f"{c.current_value:.4f} | "
                f"{change_str} |"
            )

        return "\n".join(lines)

    def _generate_all_metrics_table_md(self, result: ComparisonResult) -> str:
        """Generate table with all metrics."""
        lines = [
            "| Metric | Type | Baseline | Current | Change | Significant |",
            "|--------|------|----------|---------|--------|-------------|",
        ]

        for name, c in sorted(result.metric_comparisons.items()):
            change_str = format_percent_change(c.percent_change)
            sig_str = "✓" if c.is_significant else "-"
            lines.append(
                f"| `{name}` | {c.metric_type.value} | "
                f"{c.baseline_value:.4f} | {c.current_value:.4f} | "
                f"{change_str} | {sig_str} |"
            )

        return "\n".join(lines)

    def _result_to_dict(self, result: ComparisonResult) -> dict[str, Any]:
        """Convert ComparisonResult to dict for JSON serialization."""
        return {
            "baseline_id": result.baseline_id,
            "baseline_name": result.baseline_name,
            "current_id": result.current_id,
            "current_name": result.current_name,
            "compared_at": result.compared_at.isoformat(),
            "verdict": result.verdict.value,
            "summary": {
                "total_metrics_compared": result.total_metrics_compared,
                "significant_changes": result.significant_changes,
                "regressions": len(result.regressions),
                "critical_count": result.critical_count,
                "major_count": result.major_count,
                "minor_count": result.minor_count,
                "improvements": len(result.improvements),
            },
            "regressions": [
                self._comparison_to_dict(c) for c in result.regressions
            ],
            "improvements": [
                self._comparison_to_dict(c) for c in result.improvements
            ],
            "all_comparisons": {
                name: self._comparison_to_dict(c)
                for name, c in result.metric_comparisons.items()
            },
        }

    def _comparison_to_dict(self, c: MetricComparison) -> dict[str, Any]:
        """Convert MetricComparison to dict."""
        return {
            "metric_name": c.metric_name,
            "metric_type": c.metric_type.value,
            "baseline_value": c.baseline_value,
            "current_value": c.current_value,
            "absolute_diff": c.absolute_diff,
            "percent_change": c.percent_change,
            "p_value": c.p_value,
            "effect_size": c.effect_size,
            "is_significant": c.is_significant,
            "regression_severity": c.regression_severity.value,
            "is_regression": c.is_regression,
            "is_improvement": c.is_improvement,
            "context": c.context,
        }
```

### Success Criteria

#### Automated Verification

- [x] `poetry run pytest tests/unit/test_comparison_reporter.py -v`
- [x] `poetry run mypy src/cow_performance/comparison/reporter.py`

#### Manual Verification

- [x] Text report is readable and well-formatted
- [x] Markdown report renders correctly on GitHub
- [x] JSON report contains all necessary data

---

## Testing Strategy

### Unit Tests

Create comprehensive tests for each module:

**File**: `tests/unit/test_comparison_models.py`

```python
"""Unit tests for comparison data models."""

import pytest

from cow_performance.comparison.models import (
    ComparisonResult,
    ComparisonVerdict,
    MetricComparison,
    MetricType,
    RegressionSeverity,
)


class TestMetricComparison:
    """Tests for MetricComparison dataclass."""

    def test_latency_increase_is_regression(self):
        """Latency increase should be marked as regression."""
        comparison = MetricComparison(
            metric_name="time_to_fill",
            metric_type=MetricType.LATENCY,
            baseline_value=0.1,
            current_value=0.15,
            absolute_diff=0.05,
            percent_change=0.50,
            is_significant=True,
            regression_severity=RegressionSeverity.CRITICAL,
        )
        assert comparison.is_regression is True
        assert comparison.is_improvement is False

    def test_latency_decrease_is_improvement(self):
        """Latency decrease should be marked as improvement."""
        comparison = MetricComparison(
            metric_name="time_to_fill",
            metric_type=MetricType.LATENCY,
            baseline_value=0.15,
            current_value=0.1,
            absolute_diff=-0.05,
            percent_change=-0.33,
            is_significant=True,
            regression_severity=RegressionSeverity.NONE,
        )
        assert comparison.is_regression is False
        assert comparison.is_improvement is True

    def test_throughput_decrease_is_regression(self):
        """Throughput decrease should be marked as regression."""
        comparison = MetricComparison(
            metric_name="orders_per_second",
            metric_type=MetricType.THROUGHPUT,
            baseline_value=10.0,
            current_value=5.0,
            absolute_diff=-5.0,
            percent_change=-0.50,
            is_significant=True,
            regression_severity=RegressionSeverity.CRITICAL,
        )
        assert comparison.is_regression is True
        assert comparison.is_improvement is False

    def test_not_significant_not_regression(self):
        """Non-significant change should not be marked as regression."""
        comparison = MetricComparison(
            metric_name="time_to_fill",
            metric_type=MetricType.LATENCY,
            baseline_value=0.1,
            current_value=0.12,
            absolute_diff=0.02,
            percent_change=0.20,
            is_significant=False,
            regression_severity=RegressionSeverity.MINOR,
        )
        assert comparison.is_regression is False


class TestComparisonResult:
    """Tests for ComparisonResult dataclass."""

    def test_add_comparison(self):
        """Test adding comparisons updates counts correctly."""
        result = ComparisonResult(
            baseline_id="baseline-1",
            baseline_name="baseline",
            current_id="current-1",
            current_name="current",
        )

        # Add a critical regression
        result.add_comparison(MetricComparison(
            metric_name="latency",
            metric_type=MetricType.LATENCY,
            baseline_value=0.1,
            current_value=0.2,
            absolute_diff=0.1,
            percent_change=1.0,
            is_significant=True,
            regression_severity=RegressionSeverity.CRITICAL,
        ))

        assert result.total_metrics_compared == 1
        assert result.significant_changes == 1
        assert result.critical_count == 1
        assert len(result.regressions) == 1

    def test_verdict_calculation_regression(self):
        """Test verdict is regression when critical issues exist."""
        result = ComparisonResult(
            baseline_id="b1",
            baseline_name="base",
            current_id="c1",
            current_name="curr",
        )

        result.add_comparison(MetricComparison(
            metric_name="latency",
            metric_type=MetricType.LATENCY,
            baseline_value=0.1,
            current_value=0.2,
            absolute_diff=0.1,
            percent_change=1.0,
            is_significant=True,
            regression_severity=RegressionSeverity.CRITICAL,
        ))

        result.calculate_verdict()
        assert result.verdict == ComparisonVerdict.REGRESSION

    def test_verdict_calculation_improvement(self):
        """Test verdict is improvement when more improvements than regressions."""
        result = ComparisonResult(
            baseline_id="b1",
            baseline_name="base",
            current_id="c1",
            current_name="curr",
        )

        # Add improvement
        comp = MetricComparison(
            metric_name="latency",
            metric_type=MetricType.LATENCY,
            baseline_value=0.2,
            current_value=0.1,
            absolute_diff=-0.1,
            percent_change=-0.5,
            is_significant=True,
            regression_severity=RegressionSeverity.NONE,
        )
        result.add_comparison(comp)

        result.calculate_verdict()
        assert result.verdict == ComparisonVerdict.IMPROVEMENT
```

**File**: `tests/unit/test_comparison_thresholds.py`

```python
"""Unit tests for threshold configuration."""

import pytest

from cow_performance.comparison.models import MetricType, RegressionSeverity
from cow_performance.comparison.thresholds import (
    MetricThresholds,
    RegressionThresholds,
    STRICT_THRESHOLDS,
    RELAXED_THRESHOLDS,
)


class TestMetricThresholds:
    """Tests for MetricThresholds."""

    def test_classify_latency_increase(self):
        """Test latency increase classification."""
        thresholds = MetricThresholds(minor=0.10, major=0.15, critical=0.30)

        assert thresholds.classify_severity(0.05, MetricType.LATENCY) == RegressionSeverity.NONE
        assert thresholds.classify_severity(0.10, MetricType.LATENCY) == RegressionSeverity.MINOR
        assert thresholds.classify_severity(0.15, MetricType.LATENCY) == RegressionSeverity.MAJOR
        assert thresholds.classify_severity(0.30, MetricType.LATENCY) == RegressionSeverity.CRITICAL

    def test_classify_throughput_decrease(self):
        """Test throughput decrease classification (inverted)."""
        thresholds = MetricThresholds(minor=0.10, major=0.25, critical=0.50)

        # Negative change = decrease, which is bad for throughput
        assert thresholds.classify_severity(-0.05, MetricType.THROUGHPUT) == RegressionSeverity.NONE
        assert thresholds.classify_severity(-0.10, MetricType.THROUGHPUT) == RegressionSeverity.MINOR
        assert thresholds.classify_severity(-0.25, MetricType.THROUGHPUT) == RegressionSeverity.MAJOR
        assert thresholds.classify_severity(-0.50, MetricType.THROUGHPUT) == RegressionSeverity.CRITICAL


class TestRegressionThresholds:
    """Tests for RegressionThresholds."""

    def test_default_thresholds(self):
        """Test default threshold values."""
        thresholds = RegressionThresholds()

        assert thresholds.latency.minor == 0.10
        assert thresholds.throughput.major == 0.25
        assert thresholds.significance_level == 0.05

    def test_strict_thresholds(self):
        """Test strict threshold profile."""
        assert STRICT_THRESHOLDS.latency.minor == 0.05
        assert STRICT_THRESHOLDS.significance_level == 0.01

    def test_serialization_roundtrip(self):
        """Test thresholds can be serialized and deserialized."""
        thresholds = RegressionThresholds()
        data = thresholds.to_dict()
        restored = RegressionThresholds.from_dict(data)

        assert restored.latency.minor == thresholds.latency.minor
        assert restored.significance_level == thresholds.significance_level
```

**File**: `tests/unit/test_comparison_statistics.py`

```python
"""Unit tests for statistical functions."""

import math

import pytest

from cow_performance.comparison.statistics import (
    calculate_cohens_d,
    calculate_percent_change,
    compare_percentile_stats,
    format_percent_change,
    welchs_t_test,
)


class TestPercentChange:
    """Tests for percent change calculation."""

    def test_positive_change(self):
        """Test positive percent change."""
        assert calculate_percent_change(100, 110) == pytest.approx(0.10)

    def test_negative_change(self):
        """Test negative percent change."""
        assert calculate_percent_change(100, 90) == pytest.approx(-0.10)

    def test_zero_baseline(self):
        """Test with zero baseline."""
        result = calculate_percent_change(0, 10)
        assert math.isinf(result)

    def test_both_zero(self):
        """Test with both zero."""
        assert calculate_percent_change(0, 0) == 0.0


class TestCohensD:
    """Tests for Cohen's d effect size."""

    def test_large_effect(self):
        """Test detection of large effect size."""
        # Large difference: 100 vs 200 with std of 50
        d = calculate_cohens_d(100, 200, 50, 50, 30, 30)
        assert d is not None
        assert abs(d) > 0.8  # Large effect

    def test_small_sample_returns_none(self):
        """Test that small samples return None."""
        d = calculate_cohens_d(100, 200, 50, 50, 1, 1)
        assert d is None


class TestWelchsTTest:
    """Tests for Welch's t-test."""

    def test_significant_difference(self):
        """Test detection of significant difference."""
        result = welchs_t_test(100, 150, 20, 20, 30, 30)
        assert result is not None
        t_stat, p_value = result
        assert p_value < 0.05  # Should be significant

    def test_no_difference(self):
        """Test no difference returns high p-value."""
        result = welchs_t_test(100, 100, 20, 20, 30, 30)
        assert result is not None
        t_stat, p_value = result
        assert p_value > 0.05


class TestFormatPercentChange:
    """Tests for percent change formatting."""

    def test_positive(self):
        """Test positive change formatting."""
        assert format_percent_change(0.10) == "+10.0%"

    def test_negative(self):
        """Test negative change formatting."""
        assert format_percent_change(-0.05) == "-5.0%"

    def test_infinity(self):
        """Test infinity formatting."""
        assert format_percent_change(float("inf")) == "∞%"
```

**File**: `tests/unit/test_comparison_engine.py`

```python
"""Unit tests for ComparisonEngine."""

import pytest

from cow_performance.baselines.models import PerformanceBaseline
from cow_performance.comparison.engine import ComparisonEngine
from cow_performance.comparison.models import ComparisonVerdict, RegressionSeverity
from cow_performance.metrics.aggregator import (
    APIAggregateMetrics,
    OrderAggregateMetrics,
    PercentileStats,
)


class TestComparisonEngine:
    """Tests for ComparisonEngine."""

    @pytest.fixture
    def baseline(self):
        """Create a sample baseline."""
        return PerformanceBaseline(
            id="baseline-1",
            name="test-baseline",
            order_metrics=OrderAggregateMetrics(
                total_orders=100,
                orders_filled=90,
                success_rate=0.90,
                time_to_fill=PercentileStats(
                    count=90, mean=0.1, std_dev=0.02, p50=0.095, p90=0.12, p95=0.13, p99=0.15
                ),
            ),
            api_metrics=APIAggregateMetrics(
                total_requests=500,
                success_rate=0.95,
                response_time=PercentileStats(
                    count=500, mean=50, std_dev=10, p50=48, p90=60, p95=65, p99=80
                ),
                requests_per_second=10.0,
            ),
            orders_per_second=5.0,
            peak_orders_per_second=8.0,
        )

    @pytest.fixture
    def current_regression(self, baseline):
        """Create a current run with regressions."""
        return PerformanceBaseline(
            id="current-1",
            name="test-current",
            order_metrics=OrderAggregateMetrics(
                total_orders=100,
                orders_filled=80,
                success_rate=0.80,  # 10pp drop
                time_to_fill=PercentileStats(
                    count=80, mean=0.15, std_dev=0.03, p50=0.14, p90=0.18, p95=0.20, p99=0.25
                ),  # 50% latency increase
            ),
            api_metrics=APIAggregateMetrics(
                total_requests=400,
                success_rate=0.90,
                response_time=PercentileStats(
                    count=400, mean=75, std_dev=15, p50=72, p90=90, p95=100, p99=120
                ),  # 50% latency increase
                requests_per_second=8.0,
            ),
            orders_per_second=3.0,  # 40% drop
            peak_orders_per_second=5.0,
        )

    def test_compare_detects_regressions(self, baseline, current_regression):
        """Test that comparison detects regressions."""
        engine = ComparisonEngine()
        result = engine.compare(baseline, current_regression)

        assert result.verdict == ComparisonVerdict.REGRESSION
        assert result.critical_count > 0 or result.major_count > 0
        assert len(result.regressions) > 0

    def test_compare_with_identical_baselines(self, baseline):
        """Test comparison of identical baselines."""
        engine = ComparisonEngine()
        result = engine.compare(baseline, baseline)

        assert result.verdict == ComparisonVerdict.NEUTRAL
        assert result.critical_count == 0
        assert result.major_count == 0

    def test_compare_with_custom_thresholds(self, baseline, current_regression):
        """Test comparison with custom thresholds."""
        from cow_performance.comparison.thresholds import RELAXED_THRESHOLDS

        engine = ComparisonEngine(thresholds=RELAXED_THRESHOLDS)
        result = engine.compare(baseline, current_regression)

        # With relaxed thresholds, some regressions may be classified as less severe
        assert result is not None
```

**File**: `tests/unit/test_comparison_reporter.py`

```python
"""Unit tests for RegressionReporter."""

import json
from datetime import datetime

import pytest

from cow_performance.comparison.models import (
    ComparisonResult,
    ComparisonVerdict,
    MetricComparison,
    MetricType,
    RegressionSeverity,
)
from cow_performance.comparison.reporter import RegressionReporter


class TestRegressionReporter:
    """Tests for RegressionReporter."""

    @pytest.fixture
    def sample_result(self):
        """Create a sample comparison result."""
        result = ComparisonResult(
            baseline_id="baseline-123",
            baseline_name="release-v1.0",
            current_id="current-456",
            current_name="pr-feature-x",
            compared_at=datetime(2025, 1, 15, 10, 30, 0),
        )

        # Add a critical regression
        result.add_comparison(MetricComparison(
            metric_name="time_to_fill_p95",
            metric_type=MetricType.LATENCY,
            baseline_value=0.10,
            current_value=0.15,
            absolute_diff=0.05,
            percent_change=0.50,
            p_value=0.001,
            is_significant=True,
            regression_severity=RegressionSeverity.CRITICAL,
            context="50% latency increase",
        ))

        # Add an improvement
        result.add_comparison(MetricComparison(
            metric_name="orders_per_second",
            metric_type=MetricType.THROUGHPUT,
            baseline_value=5.0,
            current_value=6.0,
            absolute_diff=1.0,
            percent_change=0.20,
            is_significant=True,
            regression_severity=RegressionSeverity.NONE,
            context="20% throughput improvement",
        ))

        result.calculate_verdict()
        return result

    def test_text_report_generation(self, sample_result):
        """Test text report generation."""
        reporter = RegressionReporter()
        report = reporter.generate_text_report(sample_result)

        assert "PERFORMANCE COMPARISON REPORT" in report
        assert "release-v1.0" in report
        assert "CRITICAL REGRESSIONS" in report
        assert "time_to_fill_p95" in report

    def test_markdown_report_generation(self, sample_result):
        """Test Markdown report generation."""
        reporter = RegressionReporter()
        report = reporter.generate_markdown_report(sample_result)

        assert "## " in report  # Has headers
        assert "| Baseline |" in report  # Has tables
        assert "`release-v1.0`" in report
        assert "⚠️" in report or "✅" in report  # Has emoji

    def test_json_report_generation(self, sample_result):
        """Test JSON report generation."""
        reporter = RegressionReporter()
        report = reporter.generate_json_report(sample_result)

        # Should be valid JSON
        data = json.loads(report)

        assert data["baseline_name"] == "release-v1.0"
        assert data["verdict"] == "regression"
        assert len(data["regressions"]) == 1
        assert len(data["improvements"]) == 1
```

### Integration Tests

**File**: `tests/integration/test_comparison_integration.py`

```python
"""Integration tests for comparison engine."""

import pytest

from cow_performance.baselines.models import PerformanceBaseline
from cow_performance.comparison import ComparisonEngine, RegressionReporter
from cow_performance.metrics.aggregator import (
    OrderAggregateMetrics,
    PercentileStats,
)


class TestComparisonIntegration:
    """Integration tests for full comparison workflow."""

    def test_full_comparison_workflow(self):
        """Test complete comparison from baselines to report."""
        # Create baselines
        baseline = PerformanceBaseline(
            id="b1",
            name="baseline",
            order_metrics=OrderAggregateMetrics(
                total_orders=100,
                orders_filled=95,
                success_rate=0.95,
                time_to_fill=PercentileStats(
                    count=95, mean=0.1, std_dev=0.02, p95=0.13
                ),
            ),
            orders_per_second=5.0,
            peak_orders_per_second=8.0,
        )

        current = PerformanceBaseline(
            id="c1",
            name="current",
            order_metrics=OrderAggregateMetrics(
                total_orders=100,
                orders_filled=90,
                success_rate=0.90,
                time_to_fill=PercentileStats(
                    count=90, mean=0.12, std_dev=0.03, p95=0.16
                ),
            ),
            orders_per_second=4.5,
            peak_orders_per_second=7.0,
        )

        # Compare
        engine = ComparisonEngine()
        result = engine.compare(baseline, current)

        # Generate reports
        reporter = RegressionReporter()
        text_report = reporter.generate_text_report(result)
        md_report = reporter.generate_markdown_report(result)
        json_report = reporter.generate_json_report(result)

        # Verify reports contain expected content
        assert "baseline" in text_report
        assert "current" in md_report
        assert '"verdict"' in json_report
```

### Manual Testing Steps

1. **Create test baselines:**
   ```bash
   # Run a test and save baseline
   poetry run cow-perf run --scenario configs/scenarios/test-funded-scenario.yml --save-baseline baseline-v1

   # Make changes, run again
   poetry run cow-perf run --scenario configs/scenarios/test-funded-scenario.yml --save-baseline baseline-v2
   ```

2. **Test comparison (once CLI is integrated in COW-590):**
   ```bash
   # Compare baselines
   poetry run cow-perf compare baseline-v1 baseline-v2
   ```

3. **Verify reports:**
   - Check text report is readable
   - Check Markdown renders correctly in a Markdown viewer
   - Check JSON is valid and complete

---

## Performance Considerations

- **Comparison should complete in <1 second** for typical baselines
- Use numpy for efficient numerical operations
- Avoid repeated calculations by caching intermediate results
- PercentileStats comparison uses p95 values (no raw data needed)

---

## Migration Notes

- No migration needed - this is new functionality
- Comparison module is independent and doesn't modify existing code
- CLI integration will come in COW-590

---

## References

- Original ticket: `thoughts/tickets/COW-589-comparison-engine-regression-detection.md`
- Depends on: `thoughts/plans/2026-02-02-cow-588-baseline-snapshot-system.md` (COW-588)
- Depends on: `thoughts/plans/2026-01-29-cow-611-analysis-aggregation-realtime.md` (COW-611 for PercentileStats)
- Blocks: `thoughts/tickets/COW-590-automated-reporting.md` (COW-590)
- scipy t-test docs: https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.ttest_ind.html
- Cohen's d interpretation: https://en.wikipedia.org/wiki/Effect_size#Cohen's_d
