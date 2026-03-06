# COW-590: Automated Reporting Implementation Plan

## Overview

Implement automated report generation that produces comprehensive performance reports with summary statistics, detailed breakdowns, visualizations, and exportable data in multiple formats (text, Markdown, JSON, CSV). This is the final ticket in M2 (Performance Benchmarking), building upon COW-587 (Metrics Collection), COW-588 (Baseline Snapshot System), and COW-589 (Comparison Engine).

## Current State Analysis

### What Exists (from COW-587, COW-588, COW-589)

**Metrics Infrastructure (`src/cow_performance/metrics/`):**
- `MetricsStore` - Central storage for all metrics during a test run
- `OrderMetadata` - Individual order tracking with timestamps
- `APIMetrics` - API call tracking
- `ResourceMetrics` - Container resource tracking

**Aggregation Models (`metrics/aggregator.py` - from COW-587 plan):**
- `PercentileStats` - Statistical summary with p50/p90/p95/p99
- `OrderAggregateMetrics` - Order lifecycle stats
- `APIAggregateMetrics` - API response time stats
- `ResourceAggregateMetrics` - CPU/memory usage stats
- `MetricsAggregator` - Computes summaries from `MetricsStore`

**Baseline System (`src/cow_performance/baselines/`):**
- `PerformanceBaseline` - Complete baseline snapshot with all metrics
- `BaselineManager` - CRUD operations for baselines
- Serialization functions for all metric types

**Comparison Engine (`src/cow_performance/comparison/` - implemented in COW-589):**
- `ComparisonResult` - Comparison output with regressions/improvements
- `ComparisonEngine` - Compares two baselines using statistical methods
- `RegressionReporter` - Basic text/markdown/JSON reports for comparisons
- `RegressionSeverity` - Critical/major/minor classification
- `MetricComparison` - Single metric comparison with significance
- `RegressionThresholds` - Configurable thresholds for severity classification

**Existing Export (`metrics/export.py` - referenced in tickets):**
- `export_orders_to_csv()` - Order-level CSV export
- `export_api_metrics_to_csv()` - API metrics CSV export
- `export_store_to_json()` - Full store JSON export

### Key Data Structures

```python
# Inputs for Report Generation:
MetricsStore                    # Raw metrics from a test run
  ├── orders: dict[str, OrderMetadata]
  ├── api_metrics: list[APIMetrics]
  └── resource_metrics: dict[str, list[ResourceMetrics]]

PerformanceBaseline             # Aggregated snapshot (from COW-588)
  ├── order_metrics: OrderAggregateMetrics
  ├── api_metrics: APIAggregateMetrics
  ├── resource_metrics: dict[str, ResourceAggregateMetrics]
  └── orders_per_second, peak_orders_per_second

ComparisonResult                # Optional comparison (from COW-589)
  ├── regressions: list[MetricComparison]
  ├── improvements: list[MetricComparison]
  └── verdict: ComparisonVerdict
```

## Desired End State

After this plan is complete:

1. **Report Data Model** (`reporting/models.py`):
   - `PerformanceReport` - Complete report structure
   - `ExecutiveSummary` - High-level summary with KPIs and verdict
   - `Recommendation` - Actionable suggestion with severity

2. **Summary Statistics Generator** (`reporting/summary.py`):
   - Generate executive summary from metrics
   - Calculate KPIs (throughput, success rate, latency)
   - Determine verdict (success/warning/failure)
   - Identify notable events

3. **Report Generator** (`reporting/generator.py`):
   - `ReportGenerator` class orchestrates report creation
   - Integrates metrics, comparison results, and recommendations

4. **Formatters** (`reporting/formatters/`):
   - `TextReportFormatter` - Terminal-friendly output with colors
   - `MarkdownReportFormatter` - GitHub-friendly format
   - `JSONReportFormatter` - Machine-readable output
   - `CSVExporter` - Tabular data export

5. **Recommendations Engine** (`reporting/recommendations.py`):
   - Analyze metrics to generate actionable recommendations
   - Categorize by severity and category

6. **CLI Integration** (`cli/commands/report.py`):
   - `cow-perf report` command for generating reports
   - Integration with `cow-perf run` for automatic reporting

7. **End-User Documentation** (`docs/`):
   - `docs/benchmarking.md` - Comprehensive benchmarking guide
   - Updated `docs/cli.md` - Report command documentation
   - `docs/examples/sample-report.md` - Example report output

### Verification

```bash
# All tests pass
poetry run pytest tests/unit/test_reporting_*.py -v

# Type checking
poetry run mypy src/cow_performance/reporting/

# Linting
poetry run ruff check src/cow_performance/reporting/

# Full workflow
poetry run black src/ tests/ && poetry run ruff check --fix src/ tests/ && poetry run mypy src/
```

## What We're NOT Doing

- **No HTML reports with interactive charts**: Text and Markdown only (HTML is marked as optional in ticket)
- **No Prometheus exporters**: That's COW-591
- **No PDF generation**: Not in scope
- **No historical trend analysis**: Single run or single comparison only
- **No automatic email/Slack notifications**: Out of scope

## Integration with COW-589

COW-589's `RegressionReporter` generates reports specifically for `ComparisonResult` objects. COW-590's reporting module complements this by:

1. **`ReportGenerator`** - Generates comprehensive reports for a single `PerformanceBaseline` (test run), with optional `ComparisonResult` integration
2. **`RecommendationsEngine`** - Analyzes both standalone baselines AND comparison results to generate actionable recommendations
3. **Reusing COW-589 comparison data** - When a comparison is provided, the report includes regression/improvement details from `ComparisonResult`

The two modules work together:
- `RegressionReporter` (COW-589): Focused comparison reports
- `ReportGenerator` (COW-590): Full performance reports with optional comparison section

## Implementation Approach

We'll implement in 7 phases, each resulting in a working, testable increment:

1. **Phase 1**: Report data models (`PerformanceReport`, `ExecutiveSummary`, `Recommendation`)
2. **Phase 2**: Summary statistics generator
3. **Phase 3**: Recommendations engine
4. **Phase 4**: Report formatters (text, markdown, JSON)
5. **Phase 5**: CSV export
6. **Phase 6**: CLI integration
7. **Phase 7**: End-user documentation (M2 completion)

> **Note**: This is the final ticket in M2 (Performance Benchmarking). Phase 7 adds user-facing documentation to complete the milestone.

---

## Phase 1: Report Data Models

### Overview

Define the core data models for reports following codebase patterns (dataclasses).

### Changes Required

#### 1. Create Module Structure

**File**: `src/cow_performance/reporting/__init__.py`

```python
"""Automated reporting for performance test results."""

from cow_performance.reporting.generator import ReportGenerator
from cow_performance.reporting.models import (
    ExecutiveSummary,
    PerformanceReport,
    Recommendation,
    ReportVerdict,
)
from cow_performance.reporting.recommendations import RecommendationsEngine

__all__ = [
    "ExecutiveSummary",
    "PerformanceReport",
    "Recommendation",
    "RecommendationsEngine",
    "ReportGenerator",
    "ReportVerdict",
]
```

#### 2. Define Data Models

**File**: `src/cow_performance/reporting/models.py`

```python
"""Data models for performance reports."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from cow_performance.baselines.models import PerformanceBaseline


class ReportVerdict(str, Enum):
    """Overall verdict for a performance test."""

    SUCCESS = "success"  # All metrics within acceptable thresholds
    WARNING = "warning"  # Some minor issues, but generally acceptable
    FAILURE = "failure"  # Critical issues detected


class RecommendationSeverity(str, Enum):
    """Severity level for recommendations."""

    CRITICAL = "critical"  # Immediate action required
    WARNING = "warning"  # Should be addressed soon
    INFO = "info"  # Informational suggestion


class RecommendationCategory(str, Enum):
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
        return any(
            r.severity == RecommendationSeverity.CRITICAL
            for r in self.recommendations
        )

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
```

### Success Criteria

#### Automated Verification

- [ ] `poetry run pytest tests/unit/test_reporting_models.py -v`
- [ ] `poetry run mypy src/cow_performance/reporting/models.py`
- [ ] `poetry run ruff check src/cow_performance/reporting/models.py`

#### Manual Verification

- [ ] Models can be instantiated with required fields
- [ ] Enums provide clear value options
- [ ] Helper methods work correctly

---

## Phase 2: Summary Statistics Generator

### Overview

Implement functions to generate executive summaries from metrics data.

### Changes Required

#### 1. Create Summary Module

**File**: `src/cow_performance/reporting/summary.py`

```python
"""Summary statistics generation for performance reports."""

import logging
from datetime import datetime

from cow_performance.baselines.models import PerformanceBaseline
from cow_performance.reporting.models import ExecutiveSummary, ReportVerdict

logger = logging.getLogger(__name__)

# Verdict thresholds
SUCCESS_RATE_WARNING_THRESHOLD = 0.95  # Below 95% = warning
SUCCESS_RATE_FAILURE_THRESHOLD = 0.80  # Below 80% = failure
LATENCY_WARNING_MULTIPLIER = 2.0  # 2x expected = warning
LATENCY_FAILURE_MULTIPLIER = 5.0  # 5x expected = failure
EXPECTED_FILL_LATENCY_MS = 5000.0  # Expected P95 fill latency


def generate_executive_summary(
    baseline: PerformanceBaseline,
    test_name: str | None = None,
) -> ExecutiveSummary:
    """
    Generate an executive summary from a performance baseline.

    Args:
        baseline: The performance baseline containing aggregated metrics
        test_name: Optional test name override

    Returns:
        ExecutiveSummary with key metrics and verdict
    """
    # Extract order metrics
    order_metrics = baseline.order_metrics
    api_metrics = baseline.api_metrics

    # Calculate timestamps
    test_start = datetime.fromtimestamp(baseline.created_at - baseline.duration_seconds)
    test_end = datetime.fromtimestamp(baseline.created_at)

    # Extract order counts
    if order_metrics:
        total_submitted = order_metrics.orders_submitted
        total_filled = order_metrics.orders_filled
        total_failed = order_metrics.orders_failed
        success_rate = order_metrics.success_rate
        submission_latency_p95 = order_metrics.time_to_submit.p95 * 1000  # to ms
        fill_latency_p95 = order_metrics.time_to_fill.p95 * 1000  # to ms
        lifecycle_latency_p95 = order_metrics.total_lifecycle.p95 * 1000  # to ms
    else:
        total_submitted = 0
        total_filled = 0
        total_failed = 0
        success_rate = 0.0
        submission_latency_p95 = 0.0
        fill_latency_p95 = 0.0
        lifecycle_latency_p95 = 0.0

    # Extract API metrics
    if api_metrics:
        total_api_requests = api_metrics.total_requests
        api_success_rate = api_metrics.success_rate
        api_response_p95 = api_metrics.response_time.p95
    else:
        total_api_requests = 0
        api_success_rate = 0.0
        api_response_p95 = 0.0

    # Determine verdict
    verdict, verdict_reason, findings = _determine_verdict(
        success_rate=success_rate,
        fill_latency_p95_ms=fill_latency_p95,
        api_success_rate=api_success_rate,
        total_failed=total_failed,
    )

    return ExecutiveSummary(
        test_name=test_name or baseline.name,
        test_duration_seconds=baseline.duration_seconds,
        test_start_time=test_start,
        test_end_time=test_end,
        total_orders_submitted=total_submitted,
        total_orders_filled=total_filled,
        total_orders_failed=total_failed,
        success_rate=success_rate,
        average_throughput=baseline.orders_per_second,
        peak_throughput=baseline.peak_orders_per_second,
        submission_latency_p95_ms=submission_latency_p95,
        fill_latency_p95_ms=fill_latency_p95,
        total_lifecycle_p95_ms=lifecycle_latency_p95,
        total_api_requests=total_api_requests,
        api_success_rate=api_success_rate,
        api_response_time_p95_ms=api_response_p95,
        verdict=verdict,
        verdict_reason=verdict_reason,
        key_findings=findings,
    )


def _determine_verdict(
    success_rate: float,
    fill_latency_p95_ms: float,
    api_success_rate: float,
    total_failed: int,
) -> tuple[ReportVerdict, str, list[str]]:
    """
    Determine the overall verdict based on metrics.

    Returns:
        Tuple of (verdict, reason, list of key findings)
    """
    findings: list[str] = []
    issues: list[str] = []

    # Check success rate
    if success_rate >= SUCCESS_RATE_WARNING_THRESHOLD:
        findings.append(f"Order success rate is excellent ({success_rate:.1%})")
    elif success_rate >= SUCCESS_RATE_FAILURE_THRESHOLD:
        issues.append(f"Order success rate is below target ({success_rate:.1%})")
        findings.append(f"Order success rate needs attention ({success_rate:.1%})")
    else:
        issues.append(f"Critical: Order success rate is very low ({success_rate:.1%})")
        findings.append(f"Order success rate is critically low ({success_rate:.1%})")

    # Check latency
    if fill_latency_p95_ms > 0:
        if fill_latency_p95_ms <= EXPECTED_FILL_LATENCY_MS:
            findings.append(f"Fill latency is within expectations (P95: {fill_latency_p95_ms:.0f}ms)")
        elif fill_latency_p95_ms <= EXPECTED_FILL_LATENCY_MS * LATENCY_WARNING_MULTIPLIER:
            findings.append(f"Fill latency is elevated (P95: {fill_latency_p95_ms:.0f}ms)")
        else:
            issues.append(f"Fill latency is very high (P95: {fill_latency_p95_ms:.0f}ms)")
            findings.append(f"Fill latency is critically high (P95: {fill_latency_p95_ms:.0f}ms)")

    # Check API success rate
    if api_success_rate < 0.99:
        issues.append(f"API success rate is below 99% ({api_success_rate:.1%})")
        findings.append(f"API experiencing some failures ({api_success_rate:.1%} success)")

    # Check failed orders
    if total_failed > 0:
        findings.append(f"{total_failed} orders failed during the test")

    # Determine final verdict
    critical_issues = [i for i in issues if "Critical" in i]
    if critical_issues:
        return (
            ReportVerdict.FAILURE,
            critical_issues[0],
            findings,
        )
    elif issues:
        return (
            ReportVerdict.WARNING,
            issues[0],
            findings,
        )
    else:
        return (
            ReportVerdict.SUCCESS,
            "All metrics within acceptable thresholds",
            findings,
        )


def format_duration(seconds: float) -> str:
    """Format duration in human-readable form."""
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f}m"
    else:
        hours = seconds / 3600
        return f"{hours:.1f}h"


def format_rate(rate: float) -> str:
    """Format rate as percentage."""
    return f"{rate * 100:.1f}%"


def format_latency(ms: float) -> str:
    """Format latency in appropriate units."""
    if ms < 1:
        return f"{ms * 1000:.0f}μs"
    elif ms < 1000:
        return f"{ms:.1f}ms"
    else:
        return f"{ms / 1000:.2f}s"
```

### Success Criteria

#### Automated Verification

- [ ] `poetry run pytest tests/unit/test_reporting_summary.py -v`
- [ ] `poetry run mypy src/cow_performance/reporting/summary.py`

#### Manual Verification

- [ ] Summary correctly extracts metrics from baseline
- [ ] Verdict determination is logical
- [ ] Key findings are informative

---

## Phase 3: Recommendations Engine

### Overview

Implement analysis logic to generate actionable recommendations based on metrics.

### Changes Required

#### 1. Create Recommendations Module

**File**: `src/cow_performance/reporting/recommendations.py`

```python
"""Recommendations engine for performance analysis."""

import logging

from cow_performance.baselines.models import PerformanceBaseline
from cow_performance.reporting.models import (
    Recommendation,
    RecommendationCategory,
    RecommendationSeverity,
)

logger = logging.getLogger(__name__)

# Thresholds for recommendations
LATENCY_THRESHOLDS = {
    "submission_p95_warning_ms": 500,
    "submission_p95_critical_ms": 2000,
    "fill_p95_warning_ms": 5000,
    "fill_p95_critical_ms": 15000,
}

THROUGHPUT_THRESHOLDS = {
    "min_orders_per_second": 0.5,
    "warning_utilization": 0.5,  # 50% of target
}

RELIABILITY_THRESHOLDS = {
    "success_rate_warning": 0.95,
    "success_rate_critical": 0.80,
    "api_success_rate_warning": 0.99,
}

RESOURCE_THRESHOLDS = {
    "cpu_warning_percent": 70,
    "cpu_critical_percent": 90,
    "memory_warning_percent": 70,
    "memory_critical_percent": 90,
}


class RecommendationsEngine:
    """
    Analyzes metrics and generates actionable recommendations.

    Example:
        engine = RecommendationsEngine()
        recommendations = engine.analyze(baseline)
        for rec in recommendations:
            print(f"[{rec.severity}] {rec.title}: {rec.action}")
    """

    def __init__(
        self,
        latency_thresholds: dict | None = None,
        throughput_thresholds: dict | None = None,
        reliability_thresholds: dict | None = None,
        resource_thresholds: dict | None = None,
    ):
        """
        Initialize the recommendations engine.

        Args:
            latency_thresholds: Custom latency thresholds
            throughput_thresholds: Custom throughput thresholds
            reliability_thresholds: Custom reliability thresholds
            resource_thresholds: Custom resource thresholds
        """
        self._latency = latency_thresholds or LATENCY_THRESHOLDS
        self._throughput = throughput_thresholds or THROUGHPUT_THRESHOLDS
        self._reliability = reliability_thresholds or RELIABILITY_THRESHOLDS
        self._resource = resource_thresholds or RESOURCE_THRESHOLDS

    def analyze(self, baseline: PerformanceBaseline) -> list[Recommendation]:
        """
        Analyze a baseline and generate recommendations.

        Args:
            baseline: The performance baseline to analyze

        Returns:
            List of recommendations sorted by severity
        """
        recommendations: list[Recommendation] = []

        # Analyze order metrics
        if baseline.order_metrics:
            recommendations.extend(self._analyze_latency(baseline))
            recommendations.extend(self._analyze_reliability(baseline))

        # Analyze API metrics
        if baseline.api_metrics:
            recommendations.extend(self._analyze_api_performance(baseline))

        # Analyze throughput
        recommendations.extend(self._analyze_throughput(baseline))

        # Analyze resource utilization
        if baseline.resource_metrics:
            recommendations.extend(self._analyze_resources(baseline))

        # Sort by severity (critical first)
        severity_order = {
            RecommendationSeverity.CRITICAL: 0,
            RecommendationSeverity.WARNING: 1,
            RecommendationSeverity.INFO: 2,
        }
        recommendations.sort(key=lambda r: severity_order[r.severity])

        return recommendations

    def _analyze_latency(self, baseline: PerformanceBaseline) -> list[Recommendation]:
        """Analyze latency metrics and generate recommendations."""
        recommendations: list[Recommendation] = []
        om = baseline.order_metrics
        if not om:
            return recommendations

        # Check submission latency
        submission_p95_ms = om.time_to_submit.p95 * 1000
        if submission_p95_ms > self._latency["submission_p95_critical_ms"]:
            recommendations.append(Recommendation(
                severity=RecommendationSeverity.CRITICAL,
                category=RecommendationCategory.LATENCY,
                title="Critical submission latency",
                description=(
                    f"Order submission P95 latency is {submission_p95_ms:.0f}ms, "
                    f"exceeding the critical threshold of {self._latency['submission_p95_critical_ms']}ms."
                ),
                action="Investigate API endpoint performance and network connectivity.",
                metric_name="time_to_submit_p95",
                metric_value=submission_p95_ms,
                threshold=self._latency["submission_p95_critical_ms"],
            ))
        elif submission_p95_ms > self._latency["submission_p95_warning_ms"]:
            recommendations.append(Recommendation(
                severity=RecommendationSeverity.WARNING,
                category=RecommendationCategory.LATENCY,
                title="Elevated submission latency",
                description=(
                    f"Order submission P95 latency is {submission_p95_ms:.0f}ms, "
                    f"above the warning threshold of {self._latency['submission_p95_warning_ms']}ms."
                ),
                action="Monitor API response times and consider rate limiting adjustments.",
                metric_name="time_to_submit_p95",
                metric_value=submission_p95_ms,
                threshold=self._latency["submission_p95_warning_ms"],
            ))

        # Check fill latency
        fill_p95_ms = om.time_to_fill.p95 * 1000
        if fill_p95_ms > self._latency["fill_p95_critical_ms"]:
            recommendations.append(Recommendation(
                severity=RecommendationSeverity.CRITICAL,
                category=RecommendationCategory.LATENCY,
                title="Critical fill latency",
                description=(
                    f"Order fill P95 latency is {fill_p95_ms:.0f}ms, "
                    f"exceeding the critical threshold of {self._latency['fill_p95_critical_ms']}ms."
                ),
                action=(
                    "Investigate solver performance, orderbook indexing, "
                    "and settlement transaction processing."
                ),
                metric_name="time_to_fill_p95",
                metric_value=fill_p95_ms,
                threshold=self._latency["fill_p95_critical_ms"],
            ))
        elif fill_p95_ms > self._latency["fill_p95_warning_ms"]:
            recommendations.append(Recommendation(
                severity=RecommendationSeverity.WARNING,
                category=RecommendationCategory.LATENCY,
                title="Elevated fill latency",
                description=(
                    f"Order fill P95 latency is {fill_p95_ms:.0f}ms, "
                    f"above the warning threshold of {self._latency['fill_p95_warning_ms']}ms."
                ),
                action="Review solver configuration and market liquidity.",
                metric_name="time_to_fill_p95",
                metric_value=fill_p95_ms,
                threshold=self._latency["fill_p95_warning_ms"],
            ))

        return recommendations

    def _analyze_reliability(self, baseline: PerformanceBaseline) -> list[Recommendation]:
        """Analyze reliability metrics."""
        recommendations: list[Recommendation] = []
        om = baseline.order_metrics
        if not om:
            return recommendations

        success_rate = om.success_rate
        if success_rate < self._reliability["success_rate_critical"]:
            recommendations.append(Recommendation(
                severity=RecommendationSeverity.CRITICAL,
                category=RecommendationCategory.RELIABILITY,
                title="Critical order failure rate",
                description=(
                    f"Order success rate is {success_rate:.1%}, "
                    f"below the critical threshold of {self._reliability['success_rate_critical']:.0%}."
                ),
                action=(
                    "Investigate order rejection reasons. Check error logs for "
                    "insufficient funds, invalid orders, or API errors."
                ),
                metric_name="success_rate",
                metric_value=success_rate,
                threshold=self._reliability["success_rate_critical"],
            ))
        elif success_rate < self._reliability["success_rate_warning"]:
            recommendations.append(Recommendation(
                severity=RecommendationSeverity.WARNING,
                category=RecommendationCategory.RELIABILITY,
                title="Elevated order failure rate",
                description=(
                    f"Order success rate is {success_rate:.1%}, "
                    f"below the target of {self._reliability['success_rate_warning']:.0%}."
                ),
                action="Review failed orders to identify common failure patterns.",
                metric_name="success_rate",
                metric_value=success_rate,
                threshold=self._reliability["success_rate_warning"],
            ))

        return recommendations

    def _analyze_api_performance(self, baseline: PerformanceBaseline) -> list[Recommendation]:
        """Analyze API performance metrics."""
        recommendations: list[Recommendation] = []
        am = baseline.api_metrics
        if not am:
            return recommendations

        if am.success_rate < self._reliability["api_success_rate_warning"]:
            recommendations.append(Recommendation(
                severity=RecommendationSeverity.WARNING,
                category=RecommendationCategory.RELIABILITY,
                title="API experiencing failures",
                description=(
                    f"API success rate is {am.success_rate:.1%}, "
                    f"below the expected {self._reliability['api_success_rate_warning']:.0%}."
                ),
                action=(
                    "Check API error responses and status codes. "
                    "Review rate limiting and connection pooling settings."
                ),
                metric_name="api_success_rate",
                metric_value=am.success_rate,
                threshold=self._reliability["api_success_rate_warning"],
            ))

        return recommendations

    def _analyze_throughput(self, baseline: PerformanceBaseline) -> list[Recommendation]:
        """Analyze throughput metrics."""
        recommendations: list[Recommendation] = []

        if baseline.orders_per_second < self._throughput["min_orders_per_second"]:
            recommendations.append(Recommendation(
                severity=RecommendationSeverity.WARNING,
                category=RecommendationCategory.THROUGHPUT,
                title="Low throughput detected",
                description=(
                    f"Average throughput is {baseline.orders_per_second:.2f} orders/second, "
                    f"below the minimum expected of {self._throughput['min_orders_per_second']} orders/second."
                ),
                action=(
                    "Check rate limiting configuration, network latency, "
                    "and trader concurrency settings."
                ),
                metric_name="orders_per_second",
                metric_value=baseline.orders_per_second,
                threshold=self._throughput["min_orders_per_second"],
            ))

        return recommendations

    def _analyze_resources(self, baseline: PerformanceBaseline) -> list[Recommendation]:
        """Analyze resource utilization metrics."""
        recommendations: list[Recommendation] = []

        for container_name, metrics in baseline.resource_metrics.items():
            # Check CPU
            cpu_p95 = metrics.cpu_percent.p95
            if cpu_p95 > self._resource["cpu_critical_percent"]:
                recommendations.append(Recommendation(
                    severity=RecommendationSeverity.CRITICAL,
                    category=RecommendationCategory.RESOURCE,
                    title=f"Critical CPU usage on {container_name}",
                    description=(
                        f"Container '{container_name}' CPU usage P95 is {cpu_p95:.1f}%, "
                        f"exceeding the critical threshold of {self._resource['cpu_critical_percent']}%."
                    ),
                    action=(
                        "Consider scaling horizontally or optimizing "
                        "the container's workload."
                    ),
                    metric_name=f"{container_name}_cpu_p95",
                    metric_value=cpu_p95,
                    threshold=self._resource["cpu_critical_percent"],
                ))
            elif cpu_p95 > self._resource["cpu_warning_percent"]:
                recommendations.append(Recommendation(
                    severity=RecommendationSeverity.WARNING,
                    category=RecommendationCategory.RESOURCE,
                    title=f"High CPU usage on {container_name}",
                    description=(
                        f"Container '{container_name}' CPU usage P95 is {cpu_p95:.1f}%."
                    ),
                    action="Monitor CPU usage trends and consider optimization.",
                    metric_name=f"{container_name}_cpu_p95",
                    metric_value=cpu_p95,
                    threshold=self._resource["cpu_warning_percent"],
                ))

            # Check memory
            mem_p95 = metrics.memory_percent.p95
            if mem_p95 > self._resource["memory_critical_percent"]:
                recommendations.append(Recommendation(
                    severity=RecommendationSeverity.CRITICAL,
                    category=RecommendationCategory.RESOURCE,
                    title=f"Critical memory usage on {container_name}",
                    description=(
                        f"Container '{container_name}' memory usage P95 is {mem_p95:.1f}%, "
                        f"exceeding the critical threshold of {self._resource['memory_critical_percent']}%."
                    ),
                    action=(
                        "Investigate memory leaks or increase memory limits. "
                        "Consider restarting the container."
                    ),
                    metric_name=f"{container_name}_memory_p95",
                    metric_value=mem_p95,
                    threshold=self._resource["memory_critical_percent"],
                ))
            elif mem_p95 > self._resource["memory_warning_percent"]:
                recommendations.append(Recommendation(
                    severity=RecommendationSeverity.WARNING,
                    category=RecommendationCategory.RESOURCE,
                    title=f"High memory usage on {container_name}",
                    description=(
                        f"Container '{container_name}' memory usage P95 is {mem_p95:.1f}%."
                    ),
                    action="Monitor memory usage trends and review allocation.",
                    metric_name=f"{container_name}_memory_p95",
                    metric_value=mem_p95,
                    threshold=self._resource["memory_warning_percent"],
                ))

        return recommendations

    def analyze_comparison(self, comparison: "ComparisonResult") -> list[Recommendation]:
        """
        Generate recommendations from a comparison result.

        Args:
            comparison: ComparisonResult from COW-589

        Returns:
            List of regression-related recommendations
        """
        recommendations: list[Recommendation] = []

        # Import here to avoid circular dependency
        try:
            from cow_performance.comparison.models import RegressionSeverity
        except ImportError:
            logger.warning("Comparison module not available")
            return recommendations

        for regression in comparison.regressions:
            if regression.regression_severity == RegressionSeverity.CRITICAL:
                severity = RecommendationSeverity.CRITICAL
            elif regression.regression_severity == RegressionSeverity.MAJOR:
                severity = RecommendationSeverity.WARNING
            else:
                severity = RecommendationSeverity.INFO

            recommendations.append(Recommendation(
                severity=severity,
                category=RecommendationCategory.REGRESSION,
                title=f"Regression detected: {regression.metric_name}",
                description=regression.context,
                action=(
                    "Review recent changes that may have impacted this metric. "
                    "Consider reverting or optimizing the affected code."
                ),
                metric_name=regression.metric_name,
                metric_value=regression.current_value,
                threshold=regression.baseline_value,
            ))

        return recommendations


# Type hint for ComparisonResult (from COW-589)
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cow_performance.comparison.models import ComparisonResult
```

### Success Criteria

#### Automated Verification

- [ ] `poetry run pytest tests/unit/test_reporting_recommendations.py -v`
- [ ] `poetry run mypy src/cow_performance/reporting/recommendations.py`

#### Manual Verification

- [ ] Recommendations are generated for metrics exceeding thresholds
- [ ] Severity classification is appropriate
- [ ] Recommendations include actionable guidance

---

## Phase 4: Report Formatters

### Overview

Implement formatters for text, Markdown, and JSON output.

### Changes Required

#### 1. Create Formatter Base

**File**: `src/cow_performance/reporting/formatters/__init__.py`

```python
"""Report formatters for different output formats."""

from cow_performance.reporting.formatters.json_formatter import JSONReportFormatter
from cow_performance.reporting.formatters.markdown import MarkdownReportFormatter
from cow_performance.reporting.formatters.text import TextReportFormatter

__all__ = [
    "JSONReportFormatter",
    "MarkdownReportFormatter",
    "TextReportFormatter",
]
```

#### 2. Text Formatter

**File**: `src/cow_performance/reporting/formatters/text.py`

```python
"""Plain text report formatter with optional color support."""

from datetime import datetime

from cow_performance.reporting.models import (
    ExecutiveSummary,
    PerformanceReport,
    Recommendation,
    RecommendationSeverity,
    ReportVerdict,
)
from cow_performance.reporting.summary import format_duration, format_latency, format_rate


class TextReportFormatter:
    """
    Formats performance reports as plain text.

    Supports optional ANSI color codes for terminal output.
    """

    def __init__(self, use_colors: bool = True):
        """
        Initialize the formatter.

        Args:
            use_colors: Whether to use ANSI color codes
        """
        self._use_colors = use_colors

    def format(self, report: PerformanceReport) -> str:
        """
        Format a complete performance report.

        Args:
            report: The report to format

        Returns:
            Formatted text string
        """
        lines: list[str] = []

        # Header
        lines.append(self._header("PERFORMANCE REPORT"))
        lines.append("")
        lines.append(f"Generated: {report.generated_at.strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"Report ID: {report.report_id}")
        if report.git_commit:
            lines.append(f"Git: {report.git_branch or 'detached'}@{report.git_commit[:8]}")
        lines.append("")

        # Executive Summary
        if report.summary:
            lines.extend(self._format_summary(report.summary))
            lines.append("")

        # Detailed Metrics
        if report.baseline:
            lines.extend(self._format_metrics(report.baseline))
            lines.append("")

        # Comparison Results
        if report.comparison:
            lines.extend(self._format_comparison(report.comparison))
            lines.append("")

        # Recommendations
        if report.recommendations:
            lines.extend(self._format_recommendations(report.recommendations))
            lines.append("")

        # Footer
        lines.append(self._divider())

        return "\n".join(lines)

    def _header(self, text: str) -> str:
        """Format a major header."""
        divider = "=" * 70
        return f"{divider}\n{text:^70}\n{divider}"

    def _subheader(self, text: str) -> str:
        """Format a section header."""
        return f"\n{'-' * 70}\n{text}\n{'-' * 70}"

    def _divider(self) -> str:
        """Return a divider line."""
        return "=" * 70

    def _color(self, text: str, color: str) -> str:
        """Apply ANSI color if colors are enabled."""
        if not self._use_colors:
            return text

        colors = {
            "red": "\033[91m",
            "green": "\033[92m",
            "yellow": "\033[93m",
            "blue": "\033[94m",
            "bold": "\033[1m",
            "reset": "\033[0m",
        }

        return f"{colors.get(color, '')}{text}{colors['reset']}"

    def _verdict_str(self, verdict: ReportVerdict) -> str:
        """Format verdict with appropriate color."""
        if verdict == ReportVerdict.SUCCESS:
            return self._color("[SUCCESS]", "green")
        elif verdict == ReportVerdict.WARNING:
            return self._color("[WARNING]", "yellow")
        else:
            return self._color("[FAILURE]", "red")

    def _format_summary(self, summary: ExecutiveSummary) -> list[str]:
        """Format the executive summary section."""
        lines = [self._subheader("EXECUTIVE SUMMARY")]

        # Verdict
        lines.append(f"\nVerdict: {self._verdict_str(summary.verdict)}")
        lines.append(f"Reason:  {summary.verdict_reason}")
        lines.append("")

        # Test info
        lines.append(f"Test:     {summary.test_name}")
        lines.append(f"Duration: {format_duration(summary.test_duration_seconds)}")
        lines.append(f"Period:   {summary.test_start_time.strftime('%H:%M:%S')} - "
                    f"{summary.test_end_time.strftime('%H:%M:%S')}")
        lines.append("")

        # Order metrics table
        lines.append("Order Metrics:")
        lines.append(f"  Submitted:     {summary.total_orders_submitted:,}")
        lines.append(f"  Filled:        {summary.total_orders_filled:,}")
        lines.append(f"  Failed:        {summary.total_orders_failed:,}")
        lines.append(f"  Success Rate:  {format_rate(summary.success_rate)}")
        lines.append("")

        # Throughput
        lines.append("Throughput:")
        lines.append(f"  Average: {summary.average_throughput:.2f} orders/sec")
        lines.append(f"  Peak:    {summary.peak_throughput:.2f} orders/sec")
        lines.append("")

        # Latency
        lines.append("Latency (P95):")
        lines.append(f"  Submission:  {format_latency(summary.submission_latency_p95_ms)}")
        lines.append(f"  Fill:        {format_latency(summary.fill_latency_p95_ms)}")
        lines.append(f"  Lifecycle:   {format_latency(summary.total_lifecycle_p95_ms)}")
        lines.append("")

        # API metrics
        lines.append("API Performance:")
        lines.append(f"  Requests:      {summary.total_api_requests:,}")
        lines.append(f"  Success Rate:  {format_rate(summary.api_success_rate)}")
        lines.append(f"  Response P95:  {format_latency(summary.api_response_time_p95_ms)}")

        # Key findings
        if summary.key_findings:
            lines.append("")
            lines.append("Key Findings:")
            for finding in summary.key_findings:
                lines.append(f"  * {finding}")

        return lines

    def _format_metrics(self, baseline: "PerformanceBaseline") -> list[str]:
        """Format detailed metrics."""
        lines = [self._subheader("DETAILED METRICS")]

        # Order metrics percentiles
        if baseline.order_metrics:
            om = baseline.order_metrics
            lines.append("\nOrder Lifecycle Latencies:")
            lines.append("  Metric            P50       P90       P95       P99")
            lines.append("  " + "-" * 56)

            for name, stats in [
                ("Time to Submit", om.time_to_submit),
                ("Time to Accept", om.time_to_accept),
                ("Time to Fill", om.time_to_fill),
                ("Total Lifecycle", om.total_lifecycle),
            ]:
                if stats.count > 0:
                    lines.append(
                        f"  {name:16} "
                        f"{format_latency(stats.p50 * 1000):>8}  "
                        f"{format_latency(stats.p90 * 1000):>8}  "
                        f"{format_latency(stats.p95 * 1000):>8}  "
                        f"{format_latency(stats.p99 * 1000):>8}"
                    )

        # Resource metrics
        if baseline.resource_metrics:
            lines.append("\nResource Utilization:")
            lines.append("  Container         CPU(P95)  Memory(P95)")
            lines.append("  " + "-" * 42)

            for name, metrics in baseline.resource_metrics.items():
                lines.append(
                    f"  {name:16} "
                    f"{metrics.cpu_percent.p95:>7.1f}%  "
                    f"{metrics.memory_percent.p95:>9.1f}%"
                )

        return lines

    def _format_comparison(self, comparison: "ComparisonResult") -> list[str]:
        """Format comparison results."""
        lines = [self._subheader("COMPARISON RESULTS")]

        lines.append(f"\nBaseline: {comparison.baseline_name}")
        lines.append(f"Current:  {comparison.current_name}")
        lines.append(f"Verdict:  {comparison.verdict.value.upper()}")
        lines.append("")

        # Regressions
        if comparison.regressions:
            lines.append(f"Regressions ({len(comparison.regressions)}):")
            for reg in comparison.regressions:
                severity = f"[{reg.regression_severity.value.upper()}]"
                lines.append(f"  {severity:10} {reg.metric_name}: {reg.context}")

        # Improvements
        if comparison.improvements:
            lines.append(f"\nImprovements ({len(comparison.improvements)}):")
            for imp in comparison.improvements:
                lines.append(f"  {imp.metric_name}: {imp.context}")

        return lines

    def _format_recommendations(self, recommendations: list[Recommendation]) -> list[str]:
        """Format recommendations section."""
        lines = [self._subheader("RECOMMENDATIONS")]

        for rec in recommendations:
            if rec.severity == RecommendationSeverity.CRITICAL:
                severity_str = self._color("[CRITICAL]", "red")
            elif rec.severity == RecommendationSeverity.WARNING:
                severity_str = self._color("[WARNING]", "yellow")
            else:
                severity_str = "[INFO]"

            lines.append(f"\n{severity_str} {rec.title}")
            lines.append(f"  Category: {rec.category.value}")
            lines.append(f"  {rec.description}")
            lines.append(f"  Action: {rec.action}")

        return lines


# Import for type hints
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cow_performance.baselines.models import PerformanceBaseline
    from cow_performance.comparison.models import ComparisonResult
```

#### 3. Markdown Formatter

**File**: `src/cow_performance/reporting/formatters/markdown.py`

```python
"""Markdown report formatter for GitHub-friendly output."""

from cow_performance.reporting.models import (
    ExecutiveSummary,
    PerformanceReport,
    Recommendation,
    RecommendationSeverity,
    ReportVerdict,
)
from cow_performance.reporting.summary import format_duration, format_latency, format_rate


class MarkdownReportFormatter:
    """
    Formats performance reports as Markdown.

    Designed for GitHub PRs and documentation.
    """

    def format(self, report: PerformanceReport) -> str:
        """
        Format a complete performance report as Markdown.

        Args:
            report: The report to format

        Returns:
            Markdown formatted string
        """
        lines: list[str] = []

        # Header with verdict badge
        verdict_emoji = self._verdict_emoji(report.summary.verdict if report.summary else None)
        lines.append(f"# {verdict_emoji} Performance Report")
        lines.append("")

        # Metadata table
        lines.append("| Property | Value |")
        lines.append("|----------|-------|")
        lines.append(f"| Generated | {report.generated_at.strftime('%Y-%m-%d %H:%M:%S')} |")
        lines.append(f"| Report ID | `{report.report_id}` |")
        if report.git_commit:
            lines.append(f"| Git | `{report.git_branch or 'detached'}@{report.git_commit[:8]}` |")
        if report.scenario_name:
            lines.append(f"| Scenario | `{report.scenario_name}` |")
        lines.append("")

        # Executive Summary
        if report.summary:
            lines.extend(self._format_summary(report.summary))
            lines.append("")

        # Detailed Metrics
        if report.baseline:
            lines.extend(self._format_metrics(report.baseline))
            lines.append("")

        # Comparison Results
        if report.comparison:
            lines.extend(self._format_comparison(report.comparison))
            lines.append("")

        # Recommendations
        if report.recommendations:
            lines.extend(self._format_recommendations(report.recommendations))
            lines.append("")

        # Footer
        lines.append("---")
        lines.append("*Generated by CoW Performance Testing Suite*")

        return "\n".join(lines)

    def _verdict_emoji(self, verdict: ReportVerdict | None) -> str:
        """Get emoji for verdict."""
        if verdict is None:
            return "📊"
        mapping = {
            ReportVerdict.SUCCESS: "✅",
            ReportVerdict.WARNING: "⚠️",
            ReportVerdict.FAILURE: "❌",
        }
        return mapping.get(verdict, "📊")

    def _severity_emoji(self, severity: RecommendationSeverity) -> str:
        """Get emoji for severity."""
        mapping = {
            RecommendationSeverity.CRITICAL: "🔴",
            RecommendationSeverity.WARNING: "🟠",
            RecommendationSeverity.INFO: "🔵",
        }
        return mapping.get(severity, "⚪")

    def _format_summary(self, summary: ExecutiveSummary) -> list[str]:
        """Format executive summary as Markdown."""
        lines = ["## Executive Summary", ""]

        # Verdict badge
        verdict_badge = self._verdict_emoji(summary.verdict)
        lines.append(f"**Verdict:** {verdict_badge} **{summary.verdict.value.upper()}**")
        lines.append(f"> {summary.verdict_reason}")
        lines.append("")

        # Test info
        lines.append(f"**Test:** {summary.test_name}")
        lines.append(f"**Duration:** {format_duration(summary.test_duration_seconds)}")
        lines.append("")

        # Metrics summary table
        lines.append("### Key Metrics")
        lines.append("")
        lines.append("| Metric | Value |")
        lines.append("|--------|-------|")
        lines.append(f"| Orders Submitted | {summary.total_orders_submitted:,} |")
        lines.append(f"| Orders Filled | {summary.total_orders_filled:,} |")
        lines.append(f"| Success Rate | {format_rate(summary.success_rate)} |")
        lines.append(f"| Avg Throughput | {summary.average_throughput:.2f} orders/sec |")
        lines.append(f"| Fill Latency (P95) | {format_latency(summary.fill_latency_p95_ms)} |")
        lines.append(f"| API Success Rate | {format_rate(summary.api_success_rate)} |")
        lines.append("")

        # Key findings
        if summary.key_findings:
            lines.append("### Key Findings")
            lines.append("")
            for finding in summary.key_findings:
                lines.append(f"- {finding}")
            lines.append("")

        return lines

    def _format_metrics(self, baseline: "PerformanceBaseline") -> list[str]:
        """Format detailed metrics as Markdown."""
        lines = ["## Detailed Metrics", ""]

        # Order latencies table
        if baseline.order_metrics:
            om = baseline.order_metrics
            lines.append("### Order Lifecycle Latencies")
            lines.append("")
            lines.append("| Stage | P50 | P90 | P95 | P99 |")
            lines.append("|-------|-----|-----|-----|-----|")

            for name, stats in [
                ("Submit", om.time_to_submit),
                ("Accept", om.time_to_accept),
                ("Fill", om.time_to_fill),
                ("Total", om.total_lifecycle),
            ]:
                if stats.count > 0:
                    lines.append(
                        f"| {name} | "
                        f"{format_latency(stats.p50 * 1000)} | "
                        f"{format_latency(stats.p90 * 1000)} | "
                        f"{format_latency(stats.p95 * 1000)} | "
                        f"{format_latency(stats.p99 * 1000)} |"
                    )
            lines.append("")

        # Resource metrics
        if baseline.resource_metrics:
            lines.append("### Resource Utilization")
            lines.append("")
            lines.append("| Container | CPU (P95) | Memory (P95) |")
            lines.append("|-----------|-----------|--------------|")

            for name, metrics in baseline.resource_metrics.items():
                lines.append(
                    f"| {name} | {metrics.cpu_percent.p95:.1f}% | "
                    f"{metrics.memory_percent.p95:.1f}% |"
                )
            lines.append("")

        return lines

    def _format_comparison(self, comparison: "ComparisonResult") -> list[str]:
        """Format comparison results as Markdown."""
        lines = ["## Comparison Results", ""]

        lines.append(f"**Baseline:** `{comparison.baseline_name}`")
        lines.append(f"**Current:** `{comparison.current_name}`")
        lines.append(f"**Verdict:** {comparison.verdict.value.upper()}")
        lines.append("")

        # Regressions table
        if comparison.regressions:
            lines.append("### Regressions")
            lines.append("")
            lines.append("| Severity | Metric | Change |")
            lines.append("|----------|--------|--------|")
            for reg in comparison.regressions:
                severity = f"{reg.regression_severity.value}"
                change = f"{reg.percent_change * 100:+.1f}%"
                lines.append(f"| {severity} | `{reg.metric_name}` | {change} |")
            lines.append("")

        # Improvements table
        if comparison.improvements:
            lines.append("### Improvements")
            lines.append("")
            lines.append("| Metric | Change |")
            lines.append("|--------|--------|")
            for imp in comparison.improvements:
                change = f"{imp.percent_change * 100:+.1f}%"
                lines.append(f"| `{imp.metric_name}` | {change} |")
            lines.append("")

        return lines

    def _format_recommendations(self, recommendations: list[Recommendation]) -> list[str]:
        """Format recommendations as Markdown."""
        lines = ["## Recommendations", ""]

        for rec in recommendations:
            emoji = self._severity_emoji(rec.severity)
            lines.append(f"### {emoji} {rec.title}")
            lines.append("")
            lines.append(f"**Category:** {rec.category.value}")
            lines.append("")
            lines.append(rec.description)
            lines.append("")
            lines.append(f"**Action:** {rec.action}")
            lines.append("")

        return lines


# Import for type hints
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cow_performance.baselines.models import PerformanceBaseline
    from cow_performance.comparison.models import ComparisonResult
```

#### 4. JSON Formatter

**File**: `src/cow_performance/reporting/formatters/json_formatter.py`

```python
"""JSON report formatter for machine-readable output."""

import json
from datetime import datetime
from typing import Any

from cow_performance.reporting.models import (
    ExecutiveSummary,
    PerformanceReport,
    Recommendation,
)


class JSONReportFormatter:
    """
    Formats performance reports as JSON.

    Designed for programmatic consumption and data pipelines.
    """

    def __init__(self, indent: int = 2):
        """
        Initialize the formatter.

        Args:
            indent: JSON indentation level (0 for compact)
        """
        self._indent = indent if indent > 0 else None

    def format(self, report: PerformanceReport) -> str:
        """
        Format a complete performance report as JSON.

        Args:
            report: The report to format

        Returns:
            JSON formatted string
        """
        data = self._report_to_dict(report)
        return json.dumps(data, indent=self._indent, default=self._json_serializer)

    def _json_serializer(self, obj: Any) -> Any:
        """Custom JSON serializer for non-standard types."""
        if isinstance(obj, datetime):
            return obj.isoformat()
        if hasattr(obj, "value"):  # Enum
            return obj.value
        if hasattr(obj, "__dict__"):
            return obj.__dict__
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

    def _report_to_dict(self, report: PerformanceReport) -> dict[str, Any]:
        """Convert report to dictionary."""
        data: dict[str, Any] = {
            "report_id": report.report_id,
            "generated_at": report.generated_at.isoformat(),
            "report_version": report.report_version,
            "test_name": report.test_name,
            "scenario_name": report.scenario_name,
            "git_commit": report.git_commit,
            "git_branch": report.git_branch,
        }

        if report.summary:
            data["summary"] = self._summary_to_dict(report.summary)

        if report.baseline:
            data["baseline"] = self._baseline_to_dict(report.baseline)

        if report.comparison:
            data["comparison"] = self._comparison_to_dict(report.comparison)

        if report.recommendations:
            data["recommendations"] = [
                self._recommendation_to_dict(r) for r in report.recommendations
            ]

        data["data_files"] = report.data_files

        return data

    def _summary_to_dict(self, summary: ExecutiveSummary) -> dict[str, Any]:
        """Convert executive summary to dictionary."""
        return {
            "test_name": summary.test_name,
            "test_duration_seconds": summary.test_duration_seconds,
            "test_start_time": summary.test_start_time.isoformat(),
            "test_end_time": summary.test_end_time.isoformat(),
            "total_orders_submitted": summary.total_orders_submitted,
            "total_orders_filled": summary.total_orders_filled,
            "total_orders_failed": summary.total_orders_failed,
            "success_rate": summary.success_rate,
            "average_throughput": summary.average_throughput,
            "peak_throughput": summary.peak_throughput,
            "submission_latency_p95_ms": summary.submission_latency_p95_ms,
            "fill_latency_p95_ms": summary.fill_latency_p95_ms,
            "total_lifecycle_p95_ms": summary.total_lifecycle_p95_ms,
            "total_api_requests": summary.total_api_requests,
            "api_success_rate": summary.api_success_rate,
            "api_response_time_p95_ms": summary.api_response_time_p95_ms,
            "verdict": summary.verdict.value,
            "verdict_reason": summary.verdict_reason,
            "key_findings": summary.key_findings,
        }

    def _baseline_to_dict(self, baseline: "PerformanceBaseline") -> dict[str, Any]:
        """Convert baseline to dictionary (reuse existing serialization)."""
        from cow_performance.baselines.models import baseline_to_dict
        return baseline_to_dict(baseline)

    def _comparison_to_dict(self, comparison: "ComparisonResult") -> dict[str, Any]:
        """Convert comparison result to dictionary."""
        return {
            "baseline_id": comparison.baseline_id,
            "baseline_name": comparison.baseline_name,
            "current_id": comparison.current_id,
            "current_name": comparison.current_name,
            "compared_at": comparison.compared_at.isoformat(),
            "verdict": comparison.verdict.value,
            "total_metrics_compared": comparison.total_metrics_compared,
            "significant_changes": comparison.significant_changes,
            "regressions_count": len(comparison.regressions),
            "improvements_count": len(comparison.improvements),
            "critical_count": comparison.critical_count,
            "major_count": comparison.major_count,
            "minor_count": comparison.minor_count,
        }

    def _recommendation_to_dict(self, rec: Recommendation) -> dict[str, Any]:
        """Convert recommendation to dictionary."""
        return {
            "severity": rec.severity.value,
            "category": rec.category.value,
            "title": rec.title,
            "description": rec.description,
            "action": rec.action,
            "metric_name": rec.metric_name,
            "metric_value": rec.metric_value,
            "threshold": rec.threshold,
        }


# Import for type hints
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cow_performance.baselines.models import PerformanceBaseline
    from cow_performance.comparison.models import ComparisonResult
```

### Success Criteria

#### Automated Verification

- [ ] `poetry run pytest tests/unit/test_reporting_formatters.py -v`
- [ ] `poetry run mypy src/cow_performance/reporting/formatters/`

#### Manual Verification

- [ ] Text report is readable in terminal
- [ ] Markdown report renders correctly on GitHub
- [ ] JSON report is valid and parseable

---

## Phase 5: CSV Export

### Overview

Implement CSV export functionality for tabular data.

### Changes Required

#### 1. Create CSV Exporter

**File**: `src/cow_performance/reporting/csv_export.py`

```python
"""CSV export for performance metrics."""

import csv
import io
from pathlib import Path

from cow_performance.baselines.models import PerformanceBaseline
from cow_performance.reporting.models import PerformanceReport


class CSVExporter:
    """
    Exports performance metrics to CSV files.

    Generates multiple CSV files for different data types:
    - summary.csv: Executive summary metrics
    - latencies.csv: Latency percentiles by stage
    - resources.csv: Resource utilization by container
    - recommendations.csv: All recommendations
    """

    def export_to_directory(
        self,
        report: PerformanceReport,
        output_dir: Path,
    ) -> dict[str, Path]:
        """
        Export all CSV files to a directory.

        Args:
            report: The performance report to export
            output_dir: Directory to write CSV files

        Returns:
            Dictionary mapping file type to file path
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        exported_files: dict[str, Path] = {}

        # Export summary
        if report.summary:
            summary_path = output_dir / "summary.csv"
            self._export_summary(report.summary, summary_path)
            exported_files["summary"] = summary_path

        # Export latencies
        if report.baseline and report.baseline.order_metrics:
            latencies_path = output_dir / "latencies.csv"
            self._export_latencies(report.baseline, latencies_path)
            exported_files["latencies"] = latencies_path

        # Export resources
        if report.baseline and report.baseline.resource_metrics:
            resources_path = output_dir / "resources.csv"
            self._export_resources(report.baseline, resources_path)
            exported_files["resources"] = resources_path

        # Export recommendations
        if report.recommendations:
            recs_path = output_dir / "recommendations.csv"
            self._export_recommendations(report.recommendations, recs_path)
            exported_files["recommendations"] = recs_path

        return exported_files

    def export_summary_to_string(self, report: PerformanceReport) -> str:
        """Export summary as CSV string."""
        if not report.summary:
            return ""

        output = io.StringIO()
        self._export_summary(report.summary, output)
        return output.getvalue()

    def _export_summary(
        self,
        summary: "ExecutiveSummary",
        output: Path | io.StringIO,
    ) -> None:
        """Export executive summary to CSV."""
        rows = [
            ("metric", "value"),
            ("test_name", summary.test_name),
            ("test_duration_seconds", summary.test_duration_seconds),
            ("total_orders_submitted", summary.total_orders_submitted),
            ("total_orders_filled", summary.total_orders_filled),
            ("total_orders_failed", summary.total_orders_failed),
            ("success_rate", summary.success_rate),
            ("average_throughput", summary.average_throughput),
            ("peak_throughput", summary.peak_throughput),
            ("submission_latency_p95_ms", summary.submission_latency_p95_ms),
            ("fill_latency_p95_ms", summary.fill_latency_p95_ms),
            ("total_lifecycle_p95_ms", summary.total_lifecycle_p95_ms),
            ("total_api_requests", summary.total_api_requests),
            ("api_success_rate", summary.api_success_rate),
            ("api_response_time_p95_ms", summary.api_response_time_p95_ms),
            ("verdict", summary.verdict.value),
        ]

        self._write_rows(output, rows)

    def _export_latencies(
        self,
        baseline: PerformanceBaseline,
        output: Path | io.StringIO,
    ) -> None:
        """Export latency percentiles to CSV."""
        om = baseline.order_metrics
        if not om:
            return

        header = ("stage", "count", "min", "max", "mean", "p50", "p90", "p95", "p99", "std_dev")
        rows = [header]

        for name, stats in [
            ("time_to_submit", om.time_to_submit),
            ("time_to_accept", om.time_to_accept),
            ("time_to_fill", om.time_to_fill),
            ("total_lifecycle", om.total_lifecycle),
        ]:
            if stats.count > 0:
                rows.append((
                    name,
                    stats.count,
                    stats.min * 1000,  # Convert to ms
                    stats.max * 1000,
                    stats.mean * 1000,
                    stats.p50 * 1000,
                    stats.p90 * 1000,
                    stats.p95 * 1000,
                    stats.p99 * 1000,
                    stats.std_dev * 1000,
                ))

        self._write_rows(output, rows)

    def _export_resources(
        self,
        baseline: PerformanceBaseline,
        output: Path | io.StringIO,
    ) -> None:
        """Export resource utilization to CSV."""
        header = (
            "container", "sample_count",
            "cpu_mean", "cpu_p50", "cpu_p95", "cpu_max",
            "memory_mean", "memory_p50", "memory_p95", "memory_max",
        )
        rows = [header]

        for name, metrics in baseline.resource_metrics.items():
            rows.append((
                name,
                metrics.sample_count,
                metrics.cpu_percent.mean,
                metrics.cpu_percent.p50,
                metrics.cpu_percent.p95,
                metrics.cpu_percent.max,
                metrics.memory_percent.mean,
                metrics.memory_percent.p50,
                metrics.memory_percent.p95,
                metrics.memory_percent.max,
            ))

        self._write_rows(output, rows)

    def _export_recommendations(
        self,
        recommendations: list["Recommendation"],
        output: Path | io.StringIO,
    ) -> None:
        """Export recommendations to CSV."""
        header = ("severity", "category", "title", "description", "action", "metric_name")
        rows = [header]

        for rec in recommendations:
            rows.append((
                rec.severity.value,
                rec.category.value,
                rec.title,
                rec.description,
                rec.action,
                rec.metric_name or "",
            ))

        self._write_rows(output, rows)

    def _write_rows(
        self,
        output: Path | io.StringIO,
        rows: list[tuple],
    ) -> None:
        """Write rows to CSV output."""
        if isinstance(output, Path):
            with open(output, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerows(rows)
        else:
            writer = csv.writer(output)
            writer.writerows(rows)


# Import for type hints
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cow_performance.reporting.models import ExecutiveSummary, Recommendation
```

### Success Criteria

#### Automated Verification

- [ ] `poetry run pytest tests/unit/test_reporting_csv.py -v`
- [ ] `poetry run mypy src/cow_performance/reporting/csv_export.py`

#### Manual Verification

- [ ] CSV files are valid and can be opened in Excel/Google Sheets
- [ ] All expected data columns are present

---

## Phase 6: Report Generator and CLI Integration

### Overview

Implement the main `ReportGenerator` class and integrate with the CLI.

### Changes Required

#### 1. Create Report Generator

**File**: `src/cow_performance/reporting/generator.py`

```python
"""Report generator orchestrating report creation."""

import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Literal

from cow_performance.baselines.models import PerformanceBaseline
from cow_performance.reporting.csv_export import CSVExporter
from cow_performance.reporting.formatters import (
    JSONReportFormatter,
    MarkdownReportFormatter,
    TextReportFormatter,
)
from cow_performance.reporting.models import PerformanceReport
from cow_performance.reporting.recommendations import RecommendationsEngine
from cow_performance.reporting.summary import generate_executive_summary

logger = logging.getLogger(__name__)

ReportFormat = Literal["text", "markdown", "json"]


class ReportGenerator:
    """
    Generates comprehensive performance reports.

    Orchestrates summary generation, recommendations, and formatting.

    Example:
        generator = ReportGenerator()
        report = generator.generate(baseline)
        print(generator.format(report, "markdown"))
    """

    def __init__(
        self,
        recommendations_engine: RecommendationsEngine | None = None,
    ):
        """
        Initialize the report generator.

        Args:
            recommendations_engine: Optional custom recommendations engine
        """
        self._recommendations_engine = recommendations_engine or RecommendationsEngine()
        self._text_formatter = TextReportFormatter()
        self._markdown_formatter = MarkdownReportFormatter()
        self._json_formatter = JSONReportFormatter()
        self._csv_exporter = CSVExporter()

    def generate(
        self,
        baseline: PerformanceBaseline,
        comparison: "ComparisonResult | None" = None,
        test_name: str | None = None,
    ) -> PerformanceReport:
        """
        Generate a complete performance report.

        Args:
            baseline: The performance baseline (aggregated metrics)
            comparison: Optional comparison result from COW-589
            test_name: Optional test name override

        Returns:
            Complete PerformanceReport
        """
        report_id = str(uuid.uuid4())

        # Generate executive summary
        summary = generate_executive_summary(baseline, test_name)

        # Generate recommendations
        recommendations = self._recommendations_engine.analyze(baseline)

        # Add comparison-based recommendations
        if comparison:
            recommendations.extend(
                self._recommendations_engine.analyze_comparison(comparison)
            )

        # Create report
        report = PerformanceReport(
            report_id=report_id,
            generated_at=datetime.now(),
            test_name=test_name or baseline.name,
            scenario_name=baseline.scenario_name,
            git_commit=baseline.git_commit,
            git_branch=baseline.git_branch,
            summary=summary,
            baseline=baseline,
            comparison=comparison,
            recommendations=recommendations,
        )

        logger.info(
            "Generated report %s with verdict %s and %d recommendations",
            report_id,
            summary.verdict.value,
            len(recommendations),
        )

        return report

    def format(
        self,
        report: PerformanceReport,
        format: ReportFormat = "text",
        use_colors: bool = True,
    ) -> str:
        """
        Format a report in the specified format.

        Args:
            report: The report to format
            format: Output format ("text", "markdown", or "json")
            use_colors: Whether to use ANSI colors (text format only)

        Returns:
            Formatted report string
        """
        if format == "text":
            formatter = TextReportFormatter(use_colors=use_colors)
            return formatter.format(report)
        elif format == "markdown":
            return self._markdown_formatter.format(report)
        elif format == "json":
            return self._json_formatter.format(report)
        else:
            raise ValueError(f"Unknown format: {format}")

    def export_csv(
        self,
        report: PerformanceReport,
        output_dir: Path,
    ) -> dict[str, Path]:
        """
        Export report data as CSV files.

        Args:
            report: The report to export
            output_dir: Directory for CSV files

        Returns:
            Dictionary mapping file type to file path
        """
        return self._csv_exporter.export_to_directory(report, output_dir)

    def save_report(
        self,
        report: PerformanceReport,
        output_path: Path,
        format: ReportFormat = "markdown",
    ) -> None:
        """
        Save a formatted report to a file.

        Args:
            report: The report to save
            output_path: Output file path
            format: Output format
        """
        content = self.format(report, format, use_colors=False)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content)
        logger.info("Saved report to %s", output_path)


# Import for type hints
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cow_performance.comparison.models import ComparisonResult
```

#### 2. Create CLI Command

**File**: `src/cow_performance/cli/commands/report.py`

```python
"""CLI commands for report generation."""

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from cow_performance.baselines import BaselineManager
from cow_performance.reporting import ReportGenerator

app = typer.Typer(help="Generate performance reports")
console = Console()


@app.command("generate")
def generate_report(
    baseline_name: Annotated[
        str,
        typer.Argument(help="Name or ID of the baseline to report on"),
    ],
    format: Annotated[
        str,
        typer.Option("--format", "-f", help="Output format: text, markdown, json"),
    ] = "text",
    output: Annotated[
        Path | None,
        typer.Option("--output", "-o", help="Output file path"),
    ] = None,
    compare: Annotated[
        str | None,
        typer.Option("--compare", "-c", help="Baseline to compare against"),
    ] = None,
    export_csv: Annotated[
        Path | None,
        typer.Option("--export-csv", help="Directory for CSV exports"),
    ] = None,
    no_color: Annotated[
        bool,
        typer.Option("--no-color", help="Disable colored output"),
    ] = False,
    baselines_dir: Annotated[
        Path | None,
        typer.Option("--baselines-dir", help="Baselines directory"),
    ] = None,
) -> None:
    """
    Generate a performance report from a saved baseline.

    Examples:

        # Generate text report to console
        cow-perf report generate my-baseline

        # Generate markdown report to file
        cow-perf report generate my-baseline -f markdown -o report.md

        # Compare against another baseline
        cow-perf report generate current-run -c previous-baseline

        # Export CSV files
        cow-perf report generate my-baseline --export-csv ./csv_output/
    """
    manager = BaselineManager(baselines_dir)
    generator = ReportGenerator()

    # Load baseline
    try:
        baseline = manager.load(baseline_name)
    except FileNotFoundError:
        console.print(f"[bold red]Error:[/bold red] Baseline not found: {baseline_name}")
        raise typer.Exit(1)

    # Load comparison baseline if specified
    comparison = None
    if compare:
        try:
            compare_baseline = manager.load(compare)

            # Try to import comparison engine
            try:
                from cow_performance.comparison import ComparisonEngine
                engine = ComparisonEngine()
                comparison = engine.compare(compare_baseline, baseline)
            except ImportError:
                console.print(
                    "[yellow]Warning:[/yellow] Comparison module not available. "
                    "Generating report without comparison."
                )
        except FileNotFoundError:
            console.print(f"[yellow]Warning:[/yellow] Comparison baseline not found: {compare}")

    # Generate report
    report = generator.generate(baseline, comparison=comparison)

    # Format and output
    use_colors = not no_color and output is None
    formatted = generator.format(report, format=format, use_colors=use_colors)

    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(formatted)
        console.print(f"[green]Report saved to:[/green] {output}")
    else:
        console.print(formatted)

    # Export CSV if requested
    if export_csv:
        exported = generator.export_csv(report, export_csv)
        console.print(f"\n[green]CSV files exported to:[/green] {export_csv}")
        for name, path in exported.items():
            console.print(f"  - {name}: {path.name}")


@app.command("list-formats")
def list_formats() -> None:
    """List available report formats."""
    console.print("[bold]Available Report Formats:[/bold]")
    console.print("  text     - Plain text (terminal-friendly, default)")
    console.print("  markdown - Markdown (GitHub-friendly)")
    console.print("  json     - JSON (machine-readable)")
    console.print("")
    console.print("[bold]Additional Exports:[/bold]")
    console.print("  --export-csv <dir>  - Export metrics as CSV files")
```

#### 3. Update Main CLI

**File**: Update `src/cow_performance/cli/main.py` to include report command.

Add import and register the report app:

```python
# Add to imports
from cow_performance.cli.commands.report import app as report_app

# Add to the main app registration
app.add_typer(report_app, name="report")
```

### Success Criteria

#### Automated Verification

- [ ] `poetry run pytest tests/unit/test_reporting_generator.py -v`
- [ ] `poetry run pytest tests/integration/test_reporting_integration.py -v`
- [ ] `poetry run mypy src/cow_performance/reporting/`

#### Manual Verification

- [ ] `cow-perf report generate <baseline>` works
- [ ] `cow-perf report generate <baseline> -f markdown -o report.md` creates file
- [ ] `cow-perf report generate <baseline> --export-csv ./csv/` creates CSV files

---

## Phase 7: End-User Documentation

### Overview

Create comprehensive end-user documentation for the M2 Performance Benchmarking features. This documentation targets users who want to use the performance testing suite to benchmark CoW Protocol performance.

### Changes Required

#### 1. Create Benchmarking Guide

**File**: `docs/benchmarking.md`

```markdown
# Performance Benchmarking Guide

This guide explains how to use the CoW Performance Testing Suite to benchmark performance, save baselines, compare test runs, and generate reports.

## Quick Start

### Running a Performance Test

```bash
# Run a test scenario
cow-perf run --scenario configs/scenarios/basic-load.yml

# Run and save results as a baseline
cow-perf run --scenario configs/scenarios/basic-load.yml --save-baseline my-baseline
```

### Comparing Performance

```bash
# Compare two baselines
cow-perf baselines compare baseline-v1 baseline-v2

# Generate a comparison report
cow-perf report generate current-run --compare previous-baseline
```

### Generating Reports

```bash
# Text report to console
cow-perf report generate my-baseline

# Markdown report to file
cow-perf report generate my-baseline -f markdown -o report.md

# JSON report for automation
cow-perf report generate my-baseline -f json -o report.json

# Export CSV files
cow-perf report generate my-baseline --export-csv ./csv_output/
```

## Understanding Baselines

A baseline is a saved snapshot of performance metrics from a test run. Baselines include:

- **Order Metrics**: Success rates, submission/fill latencies (P50, P90, P95, P99)
- **API Metrics**: Response times, request rates, error rates
- **Resource Metrics**: CPU and memory usage per container
- **Throughput**: Orders per second (average and peak)
- **Git Information**: Commit hash and branch for reproducibility

### Managing Baselines

```bash
# List all saved baselines
cow-perf baselines list

# Show baseline details
cow-perf baselines show my-baseline

# Delete a baseline
cow-perf baselines delete old-baseline

# Tag baselines for organization
cow-perf baselines tag my-baseline release-v1.0
```

## Performance Comparison

The comparison engine detects performance regressions and improvements between two baselines using statistical analysis.

### Regression Detection

Metrics are compared using:
- **Percentage Change**: How much the metric changed
- **Statistical Significance**: Whether the change is meaningful (p-value < 0.05)
- **Effect Size**: Magnitude of the change (Cohen's d)

### Severity Levels

| Severity | Latency Increase | Throughput Decrease | Error Rate Increase |
|----------|------------------|---------------------|---------------------|
| Critical | >30% | >50% | >5 percentage points |
| Major | >15% | >25% | >2 percentage points |
| Minor | >10% | >10% | >1 percentage point |

### Comparison Verdicts

- **Regression**: Critical issues detected or multiple major issues
- **Improvement**: Net positive change in metrics
- **Neutral**: No significant changes

## Understanding Reports

### Executive Summary

The executive summary provides a quick assessment:
- **Verdict**: SUCCESS, WARNING, or FAILURE
- **Key Metrics**: Orders submitted/filled, success rate, throughput
- **Latency Overview**: P95 values for submission, fill, and total lifecycle
- **Key Findings**: Important observations from the test

### Recommendations

Reports include actionable recommendations based on metric analysis:

| Category | Example Recommendation |
|----------|------------------------|
| Latency | "High fill latency detected. Investigate solver performance." |
| Throughput | "Low throughput. Check rate limiting configuration." |
| Reliability | "Success rate below 95%. Review error logs." |
| Resource | "Container CPU usage at 90%. Consider scaling." |
| Regression | "P95 latency increased 25% vs baseline." |

### Report Formats

| Format | Use Case |
|--------|----------|
| Text | Terminal display, quick review |
| Markdown | GitHub PRs, documentation |
| JSON | Automation, data pipelines |
| CSV | Spreadsheets, detailed analysis |

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Performance Benchmarks

on:
  pull_request:
    branches: [main]

jobs:
  benchmark:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Start services
        run: docker compose up -d

      - name: Run benchmark
        run: |
          cow-perf run --scenario configs/scenarios/ci-benchmark.yml \
            --save-baseline pr-${{ github.event.number }}

      - name: Compare with main
        run: |
          cow-perf report generate pr-${{ github.event.number }} \
            --compare main-baseline \
            -f markdown \
            -o benchmark-report.md

      - name: Post report to PR
        uses: actions/github-script@v7
        with:
          script: |
            const fs = require('fs');
            const report = fs.readFileSync('benchmark-report.md', 'utf8');
            github.rest.issues.createComment({
              issue_number: context.issue.number,
              owner: context.repo.owner,
              repo: context.repo.repo,
              body: report
            });
```

### Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success / No regressions |
| 1 | Error (invalid arguments, missing files) |
| 2 | Performance regression detected |

Use exit codes for CI gating:

```bash
cow-perf report generate current --compare baseline --strict
# Returns exit code 2 if regressions detected
```

## Troubleshooting

### Common Issues

**"Baseline not found"**
- Check baseline name with `cow-perf baselines list`
- Baselines are stored in `~/.cow-perf/baselines/` by default

**"No metrics available"**
- Ensure the test completed successfully
- Check that orders were actually submitted during the test

**"Statistical comparison not available"**
- Need at least 2 samples per metric for statistical tests
- Very short tests may not generate enough data

### Debug Mode

```bash
# Verbose output for debugging
cow-perf --verbose report generate my-baseline

# Show raw metrics
cow-perf baselines show my-baseline --raw
```

## Best Practices

1. **Consistent Test Conditions**: Run benchmarks on similar hardware/load
2. **Sufficient Duration**: Run tests long enough for meaningful statistics (5+ minutes)
3. **Baseline Naming**: Use descriptive names with dates/versions
4. **Git Tags**: Save baselines after tagged releases for comparison
5. **Regular Benchmarking**: Run benchmarks on PRs to catch regressions early
```

#### 2. Update CLI Documentation

**File**: Update `docs/cli.md` to add report commands

Add the following section to `docs/cli.md`:

```markdown
## Report Commands

### Generate Report

Generate a performance report from a saved baseline.

```bash
cow-perf report generate <baseline-name> [OPTIONS]
```

**Options:**
| Option | Description |
|--------|-------------|
| `-f, --format` | Output format: text, markdown, json (default: text) |
| `-o, --output` | Output file path |
| `-c, --compare` | Baseline to compare against |
| `--export-csv` | Directory for CSV exports |
| `--no-color` | Disable colored output |

**Examples:**

```bash
# Text report to console
cow-perf report generate my-baseline

# Markdown report for GitHub
cow-perf report generate my-baseline -f markdown -o report.md

# Compare against another baseline
cow-perf report generate current-run --compare previous-baseline

# Export metrics as CSV
cow-perf report generate my-baseline --export-csv ./csv/
```

### List Report Formats

Show available report formats.

```bash
cow-perf report list-formats
```
```

#### 3. Add Report Examples

**File**: `docs/examples/sample-report.md`

Create a sample report showing what users can expect:

```markdown
# Sample Performance Report

This is an example of a Markdown performance report generated by the suite.

---

# ✅ Performance Report

| Property | Value |
|----------|-------|
| Generated | 2026-02-03 14:30:00 |
| Report ID | `a1b2c3d4-e5f6-7890-abcd-ef1234567890` |
| Git | `main@abc123de` |
| Scenario | `basic-load` |

## Executive Summary

**Verdict:** ✅ **SUCCESS**
> All metrics within acceptable thresholds

**Test:** basic-load-test
**Duration:** 5.0m

### Key Metrics

| Metric | Value |
|--------|-------|
| Orders Submitted | 500 |
| Orders Filled | 485 |
| Success Rate | 97.0% |
| Avg Throughput | 1.67 orders/sec |
| Fill Latency (P95) | 2.5s |
| API Success Rate | 99.5% |

### Key Findings

- Order success rate is excellent (97.0%)
- Fill latency is within expectations (P95: 2500ms)
- 15 orders failed during the test

## Detailed Metrics

### Order Lifecycle Latencies

| Stage | P50 | P90 | P95 | P99 |
|-------|-----|-----|-----|-----|
| Submit | 45ms | 85ms | 100ms | 150ms |
| Accept | 200ms | 400ms | 500ms | 750ms |
| Fill | 1.2s | 2.1s | 2.5s | 4.0s |
| Total | 1.5s | 2.6s | 3.1s | 4.9s |

### Resource Utilization

| Container | CPU (P95) | Memory (P95) |
|-----------|-----------|--------------|
| orderbook | 45.2% | 52.3% |
| solver | 38.1% | 41.5% |
| driver | 25.3% | 35.2% |

## Recommendations

### 🔵 Order failure rate within tolerance

**Category:** reliability

15 orders failed (3% failure rate), which is within acceptable limits for production testing.

**Action:** Review failed orders to identify any patterns that could be optimized.

---

*Generated by CoW Performance Testing Suite*
```

### Success Criteria

#### Automated Verification

- [ ] Documentation files are valid Markdown
- [ ] All code examples are syntactically correct
- [ ] Links between documentation files work

#### Manual Verification

- [ ] New user can follow the guide to run their first benchmark
- [ ] CLI examples are accurate and work as documented
- [ ] Sample report matches actual output format
- [ ] CI/CD integration example is functional

---

## Testing Strategy

### Unit Tests

Create comprehensive tests for each module:

**File**: `tests/unit/test_reporting_models.py`

```python
"""Unit tests for reporting data models."""

import pytest
from datetime import datetime

from cow_performance.reporting.models import (
    ExecutiveSummary,
    PerformanceReport,
    Recommendation,
    RecommendationCategory,
    RecommendationSeverity,
    ReportVerdict,
)


class TestReportVerdict:
    """Tests for ReportVerdict enum."""

    def test_verdict_values(self):
        """Test verdict enum values."""
        assert ReportVerdict.SUCCESS.value == "success"
        assert ReportVerdict.WARNING.value == "warning"
        assert ReportVerdict.FAILURE.value == "failure"


class TestRecommendation:
    """Tests for Recommendation dataclass."""

    def test_recommendation_creation(self):
        """Test creating a recommendation."""
        rec = Recommendation(
            severity=RecommendationSeverity.WARNING,
            category=RecommendationCategory.LATENCY,
            title="High latency detected",
            description="P95 latency exceeds threshold",
            action="Investigate API performance",
        )

        assert rec.severity == RecommendationSeverity.WARNING
        assert rec.category == RecommendationCategory.LATENCY
        assert rec.metric_name is None


class TestPerformanceReport:
    """Tests for PerformanceReport dataclass."""

    def test_has_critical_issues(self):
        """Test critical issue detection."""
        report = PerformanceReport(report_id="test")
        assert not report.has_critical_issues()

        report.recommendations.append(Recommendation(
            severity=RecommendationSeverity.CRITICAL,
            category=RecommendationCategory.RELIABILITY,
            title="Critical",
            description="Test",
            action="Test",
        ))
        assert report.has_critical_issues()

    def test_get_recommendations_by_severity(self):
        """Test filtering recommendations by severity."""
        report = PerformanceReport(report_id="test")
        report.recommendations = [
            Recommendation(
                severity=RecommendationSeverity.CRITICAL,
                category=RecommendationCategory.RELIABILITY,
                title="Critical 1", description="", action=""
            ),
            Recommendation(
                severity=RecommendationSeverity.WARNING,
                category=RecommendationCategory.LATENCY,
                title="Warning 1", description="", action=""
            ),
        ]

        critical = report.get_recommendations_by_severity(RecommendationSeverity.CRITICAL)
        assert len(critical) == 1
        assert critical[0].title == "Critical 1"
```

**File**: `tests/unit/test_reporting_summary.py`

```python
"""Unit tests for summary generation."""

import pytest
from datetime import datetime

from cow_performance.baselines.models import PerformanceBaseline
from cow_performance.metrics.aggregator import (
    OrderAggregateMetrics,
    PercentileStats,
)
from cow_performance.reporting.models import ReportVerdict
from cow_performance.reporting.summary import (
    generate_executive_summary,
    format_duration,
    format_latency,
)


class TestGenerateExecutiveSummary:
    """Tests for generate_executive_summary function."""

    @pytest.fixture
    def good_baseline(self):
        """Create a baseline with good metrics."""
        return PerformanceBaseline(
            id="test",
            name="good-test",
            created_at=datetime.now().timestamp(),
            duration_seconds=300,
            order_metrics=OrderAggregateMetrics(
                total_orders=100,
                orders_submitted=100,
                orders_filled=98,
                orders_failed=2,
                success_rate=0.98,
                time_to_submit=PercentileStats(count=100, p95=0.1),
                time_to_fill=PercentileStats(count=98, p95=2.0),
                total_lifecycle=PercentileStats(count=98, p95=2.5),
            ),
            orders_per_second=5.0,
            peak_orders_per_second=8.0,
        )

    def test_generates_summary_from_baseline(self, good_baseline):
        """Test that summary is generated correctly."""
        summary = generate_executive_summary(good_baseline)

        assert summary.test_name == "good-test"
        assert summary.total_orders_submitted == 100
        assert summary.total_orders_filled == 98
        assert summary.success_rate == 0.98
        assert summary.verdict == ReportVerdict.SUCCESS

    def test_verdict_warning_for_low_success_rate(self, good_baseline):
        """Test warning verdict for moderate issues."""
        good_baseline.order_metrics.success_rate = 0.90
        summary = generate_executive_summary(good_baseline)
        assert summary.verdict == ReportVerdict.WARNING


class TestFormatFunctions:
    """Tests for formatting utility functions."""

    def test_format_duration_seconds(self):
        """Test duration formatting in seconds."""
        assert format_duration(30) == "30.0s"

    def test_format_duration_minutes(self):
        """Test duration formatting in minutes."""
        assert format_duration(150) == "2.5m"

    def test_format_latency_ms(self):
        """Test latency formatting in milliseconds."""
        assert format_latency(100) == "100.0ms"

    def test_format_latency_seconds(self):
        """Test latency formatting in seconds."""
        assert format_latency(2500) == "2.50s"
```

### Integration Tests

**File**: `tests/integration/test_reporting_integration.py`

```python
"""Integration tests for full reporting workflow."""

import pytest
from pathlib import Path

from cow_performance.baselines.models import PerformanceBaseline
from cow_performance.metrics.aggregator import (
    APIAggregateMetrics,
    OrderAggregateMetrics,
    PercentileStats,
    ResourceAggregateMetrics,
)
from cow_performance.reporting import ReportGenerator
from cow_performance.reporting.models import ReportVerdict


class TestReportingIntegration:
    """Integration tests for complete reporting workflow."""

    @pytest.fixture
    def sample_baseline(self):
        """Create a realistic sample baseline."""
        return PerformanceBaseline(
            id="integration-test-baseline",
            name="Integration Test",
            scenario_name="test-scenario",
            duration_seconds=300,
            git_commit="abc123def456",
            git_branch="main",
            order_metrics=OrderAggregateMetrics(
                total_orders=500,
                orders_submitted=500,
                orders_filled=480,
                orders_failed=20,
                success_rate=0.96,
                time_to_submit=PercentileStats(
                    count=500, mean=0.05, p50=0.04, p90=0.08, p95=0.1, p99=0.15
                ),
                time_to_fill=PercentileStats(
                    count=480, mean=1.5, p50=1.2, p90=2.5, p95=3.0, p99=4.5
                ),
                total_lifecycle=PercentileStats(
                    count=480, mean=2.0, p50=1.5, p90=3.0, p95=4.0, p99=6.0
                ),
            ),
            api_metrics=APIAggregateMetrics(
                total_requests=2000,
                successful_requests=1980,
                failed_requests=20,
                success_rate=0.99,
                response_time=PercentileStats(count=2000, mean=50, p95=120),
                requests_per_second=6.67,
            ),
            resource_metrics={
                "orderbook": ResourceAggregateMetrics(
                    container_name="orderbook",
                    sample_count=60,
                    cpu_percent=PercentileStats(count=60, mean=25, p95=45),
                    memory_percent=PercentileStats(count=60, mean=40, p95=55),
                ),
            },
            orders_per_second=1.6,
            peak_orders_per_second=2.5,
        )

    def test_full_report_generation(self, sample_baseline):
        """Test generating a complete report."""
        generator = ReportGenerator()
        report = generator.generate(sample_baseline)

        assert report.summary is not None
        assert report.summary.verdict == ReportVerdict.SUCCESS
        assert report.baseline == sample_baseline
        assert len(report.recommendations) >= 0

    def test_text_format_output(self, sample_baseline):
        """Test text format output."""
        generator = ReportGenerator()
        report = generator.generate(sample_baseline)
        text_output = generator.format(report, "text", use_colors=False)

        assert "PERFORMANCE REPORT" in text_output
        assert "Integration Test" in text_output
        assert "EXECUTIVE SUMMARY" in text_output

    def test_markdown_format_output(self, sample_baseline):
        """Test markdown format output."""
        generator = ReportGenerator()
        report = generator.generate(sample_baseline)
        md_output = generator.format(report, "markdown")

        assert "# " in md_output  # Has headers
        assert "| " in md_output  # Has tables
        assert "Integration Test" in md_output

    def test_json_format_output(self, sample_baseline):
        """Test JSON format output."""
        import json

        generator = ReportGenerator()
        report = generator.generate(sample_baseline)
        json_output = generator.format(report, "json")

        # Should be valid JSON
        data = json.loads(json_output)
        assert data["test_name"] == "Integration Test"
        assert "summary" in data
        assert "recommendations" in data

    def test_csv_export(self, sample_baseline, tmp_path):
        """Test CSV export functionality."""
        generator = ReportGenerator()
        report = generator.generate(sample_baseline)
        exported = generator.export_csv(report, tmp_path)

        assert "summary" in exported
        assert "latencies" in exported
        assert "resources" in exported

        # Verify files exist and are non-empty
        for file_type, path in exported.items():
            assert path.exists()
            assert path.stat().st_size > 0
```

---

## Manual Testing Steps

1. **Generate a baseline from a test run:**
   ```bash
   cow-perf run --scenario configs/scenarios/test-funded-scenario.yml --save-baseline test-run
   ```

2. **Generate reports in different formats:**
   ```bash
   # Text report to console
   cow-perf report generate test-run

   # Markdown report to file
   cow-perf report generate test-run -f markdown -o report.md

   # JSON report
   cow-perf report generate test-run -f json -o report.json
   ```

3. **Compare baselines (once COW-589 is implemented):**
   ```bash
   cow-perf report generate current-run -c previous-baseline
   ```

4. **Export CSV files:**
   ```bash
   cow-perf report generate test-run --export-csv ./csv_output/
   ls -la ./csv_output/
   ```

5. **Verify reports:**
   - Check text report is readable in terminal
   - Check Markdown renders correctly on GitHub
   - Check JSON is valid with `jq . report.json`
   - Check CSV files can be opened in Excel/Google Sheets

---

## Performance Considerations

- Report generation should complete in <2 seconds for typical baselines
- JSON formatter uses compact output when file size matters
- CSV export streams data to avoid memory issues with large datasets
- Formatters are stateless for better testability

---

## Migration Notes

- No migration needed - this is new functionality
- Reporting module is independent of existing code
- Integrates with COW-589 comparison module (now implemented)
- This completes M2 (Performance Benchmarking) milestone

---

## References

- Original ticket: `thoughts/tickets/COW-590-automated-reporting.md`
- Depends on: `thoughts/plans/2026-02-02-cow-588-baseline-snapshot-system.md` (COW-588 - implemented)
- Integrates with: `thoughts/plans/2026-02-03-cow-589-comparison-engine.md` (COW-589 - implemented)
- Implementation: `src/cow_performance/comparison/` (COW-589 code)
- tabulate library: https://pypi.org/project/tabulate/
- rich library: https://rich.readthedocs.io/
