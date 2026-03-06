# COW-590: 10 - Automated Reporting

**Linear URL**: https://linear.app/bleu-builders/issue/COW-590/10-automated-reporting
**Status**: Todo
**Priority**: High
**Estimate**: 3 Points
**Milestone**: M2 — Performance Benchmarking
**Assignee**: jefferson@bleu.studio
**Git Branch**: `jefferson/cow-590-10-automated-reporting`

## Summary

Implement automated report generation that produces comprehensive performance reports with summary statistics, detailed breakdowns, visualizations, and exportable data in multiple formats.

## Background

After performance tests complete, users need clear, actionable reports that summarize the results and highlight important findings. Reports should be suitable for both human consumption and programmatic analysis.

**Prerequisites (from COW-587, COW-588, COW-589):**
- `PercentileStats` - Statistical summary with p50/p90/p95/p99 (`metrics/aggregator.py`)
- `OrderAggregateMetrics`, `APIAggregateMetrics`, `ResourceAggregateMetrics` - Aggregated metrics
- `MetricsStore` - Contains all raw metrics for a test run
- `MetricsAggregator` - Computes summaries from `MetricsStore`
- `PerformanceBaseline` - Baseline snapshot (COW-588)
- `ComparisonResult` - Comparison output with regressions/improvements (COW-589)
- Export functions in `metrics/export.py` - JSON/CSV serialization already exists

## Deliverables

### 1. Report Data Model

**Subtasks:**

- [ ] Define `PerformanceReport` model:
  - Test run metadata
  - Executive summary
  - Detailed metrics sections
  - Comparison results (if baseline provided)
  - Recommendations
  - Export timestamp
- [ ] Define report sections structure
- [ ] Support report templates

### 2. Summary Statistics Generator

**Subtasks:**

- [ ] Generate executive summary:
  - Total orders submitted/filled
  - Overall success rate
  - Average throughput (orders/second)
  - Average settlement time
  - Error summary
- [ ] Calculate key performance indicators (KPIs)
- [ ] Identify notable events (spikes, drops, errors)
- [ ] Generate verdict (success, warning, failure)

### 3. Detailed Metrics Breakdown

**Subtasks:**

- [ ] Order lifecycle section:
  * Submission latency statistics
  * Orderbook latency statistics
  * Settlement latency statistics
  * Full lifecycle duration
  * Percentile tables (P50, P90, P95, P99)
- [ ] API performance section:
  * Per-endpoint response times
  * Request counts and rates
  * Success/error breakdown
  * Error types and frequencies
- [ ] Resource utilization section:
  * Per-container CPU usage
  * Per-container memory usage
  * Network I/O statistics
  * Resource usage over time
- [ ] Throughput analysis:
  * Actual vs target submission rate
  * Orders per second over time
  * Peak throughput achieved

### 4. Text Report Generation

**Subtasks:**

- [ ] Implement plain text report formatter
- [ ] Use tables for structured data (use `tabulate` library)
- [ ] Format percentiles and statistics clearly
- [ ] Include ASCII charts for trends (use `plotille` or similar)
- [ ] Support colored output for terminal display
- [ ] Generate concise summary for CLI output
- [ ] Generate detailed report for file output

### 5. Markdown Report Generation

**Subtasks:**

- [ ] Implement Markdown report formatter
- [ ] Use Markdown tables for data
- [ ] Include comparison sections
- [ ] Support embedding charts as images
- [ ] Generate GitHub-friendly format
- [ ] Include collapsible sections for details
- [ ] Add badges for status indicators

### 6. JSON Report Generation

**Subtasks:**

- [ ] Implement JSON report formatter
- [ ] Include all metrics in machine-readable format
- [ ] Support schema versioning
- [ ] Generate JSON Lines format for streaming
- [ ] Optimize for programmatic consumption

### 7. CSV Export

**Subtasks:**

- [ ] Export order-level metrics to CSV
- [ ] Export aggregated metrics to CSV
- [ ] Export time-series data to CSV
- [ ] Support custom column selection
- [ ] Generate multiple CSV files (orders.csv, metrics.csv, resources.csv)

### 8. HTML Report Generation (Optional)

**Subtasks:**

- [ ] Implement HTML report formatter with embedded CSS
- [ ] Include interactive charts (using Chart.js or similar)
- [ ] Support print-friendly styling
- [ ] Generate self-contained HTML file

### 9. Comparison Report Integration

**Subtasks:**

- [ ] Integrate `ComparisonResult` into reports
- [ ] Highlight regressions prominently
- [ ] Show side-by-side metric comparisons
- [ ] Include delta tables (absolute and percentage)
- [ ] Generate regression-focused summary

### 10. Recommendations Engine

**Subtasks:**

- [ ] Analyze metrics to generate recommendations:
  - High latency → investigate orderbook/solver performance
  - Low throughput → check rate limiting or resource constraints
  - High error rate → review error logs
  - High resource usage → consider optimization
- [ ] Provide actionable next steps
- [ ] Link to relevant documentation

## Implementation Details

### Directory Structure

```
src/cow_performance/reporting/
├── __init__.py
├── models.py           # PerformanceReport, ExecutiveSummary, Recommendation
├── generator.py        # ReportGenerator class
├── formatters/
│   ├── __init__.py
│   ├── text.py         # TextReportFormatter
│   ├── markdown.py     # MarkdownReportFormatter
│   ├── json.py         # JSONReportFormatter
│   └── html.py         # HTMLReportFormatter (optional)
└── recommendations.py  # RecommendationsEngine
```

### Key Data Flow

```
MetricsStore + ComparisonResult (optional)
    │
    ▼
ReportGenerator.generate(metrics_store, comparison, format)
    │
    ├── Uses MetricsAggregator.get_summary() for aggregated stats
    ├── Optionally includes ComparisonResult from COW-589
    ├── Generates recommendations based on thresholds
    │
    ▼
PerformanceReport → Formatter → text/markdown/json/html output
```

### Core Models

```python
@dataclass
class ExecutiveSummary:
    total_orders_submitted: int
    total_orders_filled: int
    success_rate: float
    average_throughput: float
    test_duration: int
    verdict: Literal["success", "warning", "failure"]
    key_findings: list[str]

@dataclass
class Recommendation:
    severity: Literal["critical", "warning", "info"]
    category: str  # "latency", "throughput", "reliability", "regression"
    title: str
    description: str
    action: str

@dataclass
class PerformanceReport:
    report_id: str
    generated_at: datetime
    summary: ExecutiveSummary
    order_metrics: OrderAggregateMetrics   # from COW-587
    api_metrics: APIAggregateMetrics       # from COW-587
    resource_metrics: dict[str, ResourceAggregateMetrics]
    comparison: ComparisonResult | None    # from COW-589
    recommendations: list[Recommendation]
```

### Formatter Interface

```python
class ReportFormatter(Protocol):
    def format(self, report: PerformanceReport) -> str:
        ...
```

> **Note**: Existing `metrics/export.py` already has `export_orders_to_csv()`, `export_api_metrics_to_csv()`, and `export_store_to_json()`. Reuse these where possible.

## Acceptance Criteria

- [ ] Reports include comprehensive metrics summary
- [ ] Multiple output formats supported (text, markdown, JSON, CSV)
- [ ] Reports are clear and easy to understand
- [ ] Comparison results integrated into reports
- [ ] Recommendations engine provides actionable insights
- [ ] CSV exports include all relevant data
- [ ] Reports can be generated from saved test runs
- [ ] Type hints throughout the codebase
- [ ] Unit tests for all formatters
- [ ] Integration tests generating actual reports

## Testing Requirements

### Unit Tests

* Test each formatter with sample data
* Test summary statistics calculations
* Test recommendations engine logic
* Test CSV export functionality

### Integration Tests

* Generate reports from actual test runs
* Validate report content completeness
* Test all output formats
* Verify CSV files are properly formatted

## Technical Notes

* Use `tabulate` for text tables
* Use `pandas` for CSV export (optional)
* Consider using `jinja2` for HTML templates
* Use `rich` for colored terminal output
* Keep formatters stateless for testability
* Support incremental report updates for long-running tests

## User Experience Considerations

* Default to concise output for CLI, detailed for files
* Use color coding for status indicators (green, yellow, red)
* Make recommendations actionable and specific
* Provide context for all metrics
* Include links to documentation where appropriate

## Related Issues

- **Depends on**: COW-587 (Metrics Collection Framework), COW-589 (Comparison Engine & Regression Detection)
- **Related**: COW-605 (CLI Tool Interface)
- **Related**: COW-591 (Prometheus Exporters - alternative metrics output)

---

## Implementation Notes (Post-Completion)

**Status**: ✅ Completed

### Architectural Decisions & Deviations from Original Scope

The implementation focused on practical output formats:

1. **HTML reports deferred** - HTML reports with Chart.js were not implemented. Text and Markdown cover all practical use cases (Markdown renders nicely on GitHub PRs, JSON enables programmatic consumption). HTML with embedded JS charts would significantly increase complexity for minimal additional value. This feature may be added in a future iteration if visual reporting becomes a priority.

2. **ASCII charts deferred** - The `plotille` library for ASCII charts in terminal output was not included. Simple tabular output is more practical for terminal use and avoids adding dependencies for marginal benefit.

3. **Standard CSV module instead of pandas** - Python's built-in `csv` module is used instead of pandas to avoid a heavy dependency. The CSV export needs are simple and don't require complex transforms.

4. **Collapsible sections in Markdown** - The `<details>` sections were implemented for the "All Metric Comparisons" section in comparison reports, while keeping executive summaries and recommendations always visible.

5. **Programmatic API focus** - Reports are generated from `PerformanceBaseline` objects via `ReportGenerator.generate()`. The CLI (`cow-perf report generate`) loads baselines by name and generates reports. This aligns with the framework-first approach of the grant.

These decisions prioritize practical, lightweight output over visual complexity.
