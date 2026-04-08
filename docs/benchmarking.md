# Performance Benchmarking Guide

This guide explains the concepts behind performance benchmarking in the CoW Performance Testing Suite: baselines, comparison, regression detection, and reporting.

> **See also**: [Reports & Baselines Guide](reports.md) for command reference and workflows.

## Quick Start

```bash
# Run test and save as baseline
cow-perf run --config scenario.yml --save-baseline "v1.0"

# Generate report with comparison
cow-perf report generate v2.0 --compare v1.0
```

For detailed commands and options, see the [Reports & Baselines Guide](reports.md).

---

## Understanding Baselines

A **baseline** is a saved snapshot of performance metrics from a test run. Baselines enable you to:
- Track performance over time
- Detect regressions in new code
- Compare different configurations
- Establish performance expectations

### What's Included in a Baseline

Each baseline captures:

- **Order Metrics**: Success rates, submission/fill latencies (P50, P90, P95, P99)
- **API Metrics**: Response times, request rates, error rates
- **Resource Metrics**: CPU and memory usage per container
- **Throughput**: Orders per second (average and peak)
- **Test Configuration**: Traders, duration, scenario parameters
- **Git Information**: Commit hash and branch for reproducibility
- **Timestamp**: When the baseline was created

### Baseline Storage

Baselines are stored in `~/.cow-perf/baselines/` as JSON files with UUID identifiers. You reference them by name (e.g., "v1.0") and the system maintains an index mapping names to UUIDs.

> **Command Reference**: See [Reports Guide - Managing Baselines](reports.md#managing-baselines) for list/show/delete commands.

---

## Performance Comparison

The comparison engine detects performance **regressions** (worse) and **improvements** (better) between two baselines using statistical analysis.

### How Comparison Works

For each metric, the system calculates:

1. **Percentage Change**: How much the metric changed
   - Example: P95 latency went from 10s → 13s = +30% change

2. **Statistical Significance**: Whether the change is meaningful
   - Uses t-test with p-value < 0.05 threshold
   - Prevents false positives from random variance

3. **Effect Size**: Magnitude of the change
   - Cohen's d: small (0.2), medium (0.5), large (0.8)
   - Helps distinguish practical vs statistical significance

### Regression Severity Levels

Changes are categorized by severity:

| Severity | Latency Increase | Throughput Decrease | Error Rate Increase |
|----------|------------------|---------------------|---------------------|
| **CRITICAL** | >30% | >50% | >5 percentage points |
| **MAJOR** | >15% | >25% | >2 percentage points |
| **MINOR** | >10% | >10% | >1 percentage point |

### Comparison Verdicts

The overall comparison verdict:

- **Regression**: Critical issues detected or multiple major issues
- **Improvement**: Net positive change in metrics
- **Neutral**: No significant changes

> **Command Reference**: See [Reports Guide - Baseline Comparison](reports.md#baseline-comparison) for detailed examples.

---

## Understanding Reports

Reports provide comprehensive analysis of test results, with or without baseline comparison.

### Executive Summary

Every report includes an executive summary with:

- **Verdict**: SUCCESS, WARNING, or FAILURE
- **Key Metrics**: Orders submitted/filled, success rate, throughput
- **Latency Overview**: P95 values for submission, fill, and total lifecycle
- **Key Findings**: Important observations from the test

### Verdict Thresholds

| Verdict | Criteria |
|---------|----------|
| **SUCCESS** | Success rate ≥95%, latency within expectations |
| **WARNING** | Success rate 80-95% or elevated latency |
| **FAILURE** | Success rate <80% or critical latency issues |

### Report Sections

1. **Executive Summary**: High-level overview and verdict
2. **Order Metrics**: Detailed latency percentiles, success rates
3. **API Performance**: Response times by endpoint, error rates
4. **Resource Utilization**: CPU/memory per container (P95 values)
5. **Comparison Results**: Regressions and improvements (if comparing)
6. **Recommendations**: Actionable insights based on analysis

### Recommendations Engine

Reports include automated recommendations based on metric analysis:

| Category | Example Recommendation |
|----------|------------------------|
| **Latency** | "High fill latency detected (P95: 45s). Investigate solver performance." |
| **Throughput** | "Low throughput (2.1 orders/sec). Check rate limiting configuration." |
| **Reliability** | "Success rate below 95% (actual: 87%). Review error logs for patterns." |
| **Resource** | "Container CPU usage at 90%. Consider scaling or optimization." |
| **Regression** | "P95 latency increased 25% vs baseline (10s → 12.5s). [MAJOR]" |

### Report Formats

| Format | Use Case | Features |
|--------|----------|----------|
| **Text** | Terminal display, quick review | Colored output, tables |
| **Markdown** | GitHub PRs, documentation | Formatted tables, emoji indicators |
| **JSON** | Automation, data pipelines | Machine-readable, full metrics |
| **CSV** | Spreadsheets, detailed analysis | Multiple files (orders, API, resources) |

> **Command Reference**: See [Reports Guide - Generating Reports](reports.md#generating-reports) for format options and export commands.

---

## CI/CD Integration

### GitHub Actions Example

Use performance benchmarking in pull request workflows:

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
          cow-perf run --scenario configs/scenarios/predefined/enhanced/regression-test.yml \
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

### Exit Codes for Automation

The report command returns exit codes for CI/CD pipelines:

| Code | Meaning | Action |
|------|---------|--------|
| 0 | Success / No regressions | Continue pipeline |
| 1 | Error (invalid arguments, missing files) | Fail pipeline - fix command |
| 2 | Performance regression detected | Fail pipeline - investigate regression |

**Example CI check**:
```bash
cow-perf report generate current --compare baseline
if [ $? -eq 2 ]; then
  echo "❌ Performance regression detected!"
  exit 1
fi
```

---

## Best Practices

### 1. Consistent Test Conditions

- Run benchmarks on similar hardware/environment
- Use same Docker resources (CPU, memory limits)
- Minimize background processes
- Use consistent network conditions

### 2. Sufficient Test Duration

- Run tests long enough for meaningful statistics (5+ minutes minimum)
- Longer tests (10-30 minutes) provide more stable percentiles
- Short tests (<2 minutes) have higher variance

### 3. Baseline Naming Convention

Use descriptive names with context:
- **Good**: `v1.2.0-production`, `main-2024-03-23`, `pre-optimization`
- **Bad**: `test1`, `baseline`, `latest`

### 4. Baseline Tagging Strategy

- Save baselines after tagged releases (`v1.0`, `v2.0`)
- Save before major changes (`pre-refactor`, `before-optimization`)
- Keep main branch baseline up to date (`main-baseline`)

### 5. Regular Benchmarking

- Run regression tests on every pull request
- Create baselines for each release
- Schedule weekly benchmarks to track trends
- Compare staging vs production performance

### 6. Baseline Retention

- Keep release baselines indefinitely
- Archive old development baselines after 30 days
- Maintain at least 3-5 baselines for trend analysis

---

## Troubleshooting

### Common Issues

**"Baseline not found"**
- Check baseline name: `cow-perf baselines --list`
- Verify correct baselines directory
- Baselines stored in `~/.cow-perf/baselines/` by default

**"No metrics available"**
- Ensure test completed successfully
- Check that orders were submitted (not all failed)
- Verify scenario configuration is valid

**"Statistical comparison not available"**
- Need at least 2 samples per metric for statistical tests
- Very short tests may not generate enough data
- Increase test duration or order count

**"High variance in metrics"**
- Test duration too short
- Inconsistent load on system
- Background processes affecting performance
- Use longer tests or more stable environment

### Debug Mode

Enable verbose output for troubleshooting:

```bash
# Verbose report generation
cow-perf --verbose report generate my-baseline

# Show raw baseline data
cow-perf baselines --show my-baseline
```

---

## Statistical Background

### Why Statistical Significance Matters

Not all changes are meaningful. A 5% increase in latency might be:
- **Random variance** from test conditions
- **Real regression** from code changes

Statistical tests (t-test, p-value < 0.05) distinguish random fluctuations from real changes.

### Cohen's d Effect Size

Effect size measures practical significance:
- **d < 0.2**: Negligible effect (ignore even if statistically significant)
- **d = 0.5**: Medium effect (investigate)
- **d > 0.8**: Large effect (requires action)

### Why Percentiles, Not Averages

Percentiles (P50, P90, P95, P99) provide better insight than averages:
- P50 (median): Typical user experience
- P95: 95% of requests faster than this
- P99: Catches outliers and worst-case scenarios

Averages can hide problems - a few slow requests don't affect average much but ruin P99.

---

## See Also

- **[Reports & Baselines Guide](reports.md)** - Command reference and workflows
- **[CLI Reference](cli.md)** - All command-line options
- **[Scenario User Guide](scenario-user-guide.md)** - Creating test scenarios
- **[Metrics Collection](metrics.md)** - How metrics are captured
