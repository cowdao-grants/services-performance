# COW-589: 09 - Comparison Engine and Regression Detection

**Linear URL**: https://linear.app/bleu-builders/issue/COW-589/09-comparison-engine-and-regression-detection
**Status**: Todo
**Priority**: High
**Estimate**: 5 Points
**Milestone**: M2 — Performance Benchmarking
**Assignee**: jefferson@bleu.studio
**Git Branch**: `jefferson/cow-589-09-comparison-engine-and-regression-detection`

## Summary

Implement a sophisticated comparison engine that analyzes performance differences between test runs, detects regressions using statistical methods, and generates actionable reports highlighting performance changes.

## Background

This is one of the most complex components of the benchmarking system. The comparison engine must accurately identify meaningful performance changes while avoiding false positives from normal statistical variation.

**Prerequisites (from COW-587 and COW-588):**
- `PercentileStats` - Statistical summary with p50/p90/p95/p99 (`metrics/aggregator.py`)
- `OrderAggregateMetrics`, `APIAggregateMetrics`, `ResourceAggregateMetrics` - Aggregated metrics with `PercentileStats` fields
- `PerformanceBaseline` - Complete baseline snapshot containing the above aggregate types (COW-588)
- `BaselineManager` - Load/save baselines by name, ID, or git commit (COW-588)

## Deliverables

### 1. Comparison Data Model

**Subtasks:**

- [ ] Define `ComparisonResult` model:
  * Baseline and current run identifiers
  * Comparison timestamp
  * Overall verdict (improvement, regression, neutral)
  * Metric-by-metric comparisons
  * Statistical significance indicators
  * Severity ratings for regressions
- [ ] Define `MetricComparison` model:
  * Metric name and type
  * Baseline value vs current value
  * Absolute difference
  * Percentage change
  * Statistical significance (p-value)
  * Regression severity (critical, major, minor, none)

### 2. Statistical Comparison

**Subtasks:**

- [ ] Implement statistical comparison functions:
  - Mean comparison with confidence intervals
  - Percentile comparison (P50, P90, P95, P99)
  - Distribution comparison (Kolmogorov-Smirnov test)
  - Variance analysis
- [ ] Calculate statistical significance:
  - T-test for mean differences
  - Mann-Whitney U test for non-parametric data
  - Bootstrap resampling for robust estimates
- [ ] Determine effect size (Cohen's d)
- [ ] Handle small sample sizes appropriately

### 3. Regression Detection Algorithm

This is a non-trivial requirement that needs careful design.

**Subtasks:**

- [ ] Define regression thresholds for different metrics:
  - Latency metrics: % increase threshold (e.g., >10% = regression)
  - Throughput metrics: % decrease threshold (e.g., >5% = regression)
  - Error rate metrics: absolute increase threshold (e.g., >1% = critical)
  - Resource metrics: % increase threshold (e.g., >20% = major)
- [ ] Implement multi-level severity classification:
  - **Critical**: Severe performance degradation (>30% latency increase, >50% throughput decrease, or any error rate >5%)
  - **Major**: Significant degradation (>15% latency increase or >25% throughput decrease)
  - **Minor**: Noticeable degradation (>10% latency increase or >10% throughput decrease)
  - **None**: Within acceptable variation
- [ ] Require statistical significance for regression classification:
  - Only flag as regression if p-value < 0.05 AND threshold exceeded
  - Avoid false positives from random variation
- [ ] Implement composite score for overall verdict:
  - Weight different metrics by importance
  - Account for multiple simultaneous changes
- [ ] Support configurable thresholds per metric

### 4. Comparison Engine

**Subtasks:**

- [ ] Implement `ComparisonEngine` class
- [ ] Compare latency metrics:
  - Submission latency
  - Orderbook latency
  - Settlement latency
  - API response times
- [ ] Compare throughput metrics:
  - Orders per second
  - Peak throughput
- [ ] Compare success rates:
  - Order success rate
  - API success rate
- [ ] Compare resource utilization:
  - CPU usage
  - Memory usage
  - Network I/O
- [ ] Generate per-metric comparisons with context
- [ ] Identify which metrics regressed and by how much

### 5. Visualization-Ready Data

**Subtasks:**

- [ ] Generate comparison data suitable for plotting
- [ ] Create side-by-side metric tables
- [ ] Generate delta tables (absolute and percentage changes)
- [ ] Create histograms for distribution comparison
- [ ] Export comparison data in multiple formats (JSON, CSV, Markdown)

### 6. Regression Report Generation

**Subtasks:**

- [ ] Implement `RegressionReporter` class
- [ ] Generate comprehensive text reports:
  - Executive summary (overall verdict)
  - Critical regressions highlighted
  - Major regressions listed
  - Minor regressions listed
  - Improvements noted
- [ ] Generate Markdown reports for GitHub PRs
- [ ] Generate HTML reports (optional)
- [ ] Include visualizations in reports (ASCII charts, or image references)
- [ ] Provide actionable recommendations

### 7. Historical Trend Analysis

**Subtasks:**

- [ ] Compare against multiple baselines
- [ ] Identify performance trends over time
- [ ] Detect gradual performance degradation
- [ ] Support baseline-to-baseline comparison

### 8. Configurable Thresholds

**Subtasks:**

- [ ] Define `RegressionThresholds` configuration model
- [ ] Support per-metric threshold configuration
- [ ] Support environment-specific thresholds (dev vs prod)
- [ ] Implement threshold validation

## Implementation Details

### Directory Structure

```
src/cow_performance/comparison/
├── __init__.py
├── models.py       # ComparisonResult, MetricComparison
├── engine.py       # ComparisonEngine class
├── thresholds.py   # RegressionThresholds config
└── reporter.py     # RegressionReporter class
```

### Key Data Flow

```
PerformanceBaseline (COW-588)
    ├── order_metrics: OrderAggregateMetrics
    │       └── time_to_submit, time_to_fill, etc. (PercentileStats)
    ├── api_metrics: APIAggregateMetrics
    │       └── response_time_stats (PercentileStats)
    └── resource_metrics: dict[str, ResourceAggregateMetrics]

ComparisonEngine.compare(baseline, current) → ComparisonResult
    └── Extracts PercentileStats from both, computes deltas, classifies severity
```

### Core Models

```python
@dataclass
class MetricComparison:
    metric_name: str
    metric_type: str  # "latency", "throughput", "error_rate", "resource"
    baseline_value: float
    current_value: float
    absolute_diff: float
    percent_change: float
    statistical_significance: float  # p-value
    is_significant: bool
    regression_severity: Literal["critical", "major", "minor", "none"]
    is_improvement: bool
    context: str  # Human-readable explanation

@dataclass
class ComparisonResult:
    baseline_id: str
    current_id: str
    compared_at: datetime
    verdict: Literal["improvement", "regression", "neutral"]
    metric_comparisons: dict[str, MetricComparison]
    regressions: list[MetricComparison]  # Sorted by severity
    improvements: list[MetricComparison]
```

### Thresholds Configuration

```python
@dataclass
class MetricThresholds:
    minor: float    # e.g., 10% for latency
    major: float    # e.g., 15%
    critical: float # e.g., 30%

class RegressionThresholds(BaseModel):
    latency: MetricThresholds      # percent increase
    throughput: MetricThresholds   # percent decrease
    error_rate: MetricThresholds   # absolute percentage points
    resource: MetricThresholds     # percent increase
    significance_level: float = 0.05
```

## Acceptance Criteria

- [ ] Comparison engine accurately compares all metric types
- [ ] Statistical significance calculated correctly
- [ ] Regression detection identifies true regressions (validated manually)
- [ ] Severity classification matches expectations
- [ ] False positive rate is acceptably low (<5%)
- [ ] Comparison reports are clear and actionable
- [ ] Thresholds are configurable
- [ ] Supports multiple output formats
- [ ] Type hints throughout the codebase
- [ ] Comprehensive unit tests for all comparison logic
- [ ] Integration tests with realistic baselines

## Testing Requirements

### Unit Tests

* Test statistical comparison functions
* Test regression severity classification
* Test overall verdict determination
* Test report generation
* Use synthetic data with known properties

### Integration Tests

* Compare actual baseline pairs
* Verify regression detection with intentionally degraded metrics
* Test with edge cases (no baseline, identical runs, extreme differences)
* Validate report formatting

## Technical Notes

* Consider using `scipy` for statistical tests
* Use `numpy` for efficient numerical computations
* Implement proper handling of missing data
* Consider effect size in addition to statistical significance
* Use percentiles (P95) for latency rather than means (more robust)
* Document all statistical methods used
* Provide references for threshold choices
* Consider using Cohen's d for effect size
* Be careful with multiple hypothesis testing (consider Bonferroni correction)

## Performance Considerations

* Comparison should complete in <1 second for typical runs
* Optimize statistical calculations
* Cache intermediate results

## Related Issues

- **Depends on**: COW-587 (Metrics Collection Framework), COW-588 (Baseline Snapshot System)
- **Blocks**: COW-590 (Automated Reporting)
- **Related**: COW-605 (CLI Tool Interface)

---

## Implementation Notes (Post-Completion)

**Status**: ✅ Completed

### Architectural Decisions & Deviations from Original Scope

The implementation simplified the statistical approach while maintaining effectiveness:

1. **Welch's t-test only** - The original proposal specified multiple statistical tests (Kolmogorov-Smirnov, Mann-Whitney U, Bootstrap resampling). Only Welch's t-test was implemented because the aggregated percentile stats (p50/p90/p95/p99) don't provide raw samples needed for KS or bootstrap tests. Welch's t-test is robust to unequal variances and, combined with Cohen's d effect size, provides sufficient statistical rigor.

2. **Bonferroni correction deferred** - Multiple hypothesis testing correction was not implemented because the number of metrics compared is small and fixed, and overcorrection could cause excessive false negatives in practice.

3. **Historical trend analysis deferred** - Comparing against multiple baselines over time was moved to a future iteration. The core use case is A/B comparison (baseline vs current), and trend analysis would require different UX and storage considerations.

4. **Composite score replaced with severity classification** - Instead of weighting metrics into an overall score, the implementation uses clear severity classification (critical/major/minor) with simple verdict rules. This approach is more interpretable than a single number.

5. **P95 for latency comparison** - P95 values are used instead of means for latency comparison, which is more robust for performance metrics with long-tail distributions.

These decisions prioritize a practical, interpretable implementation over statistical complexity.
