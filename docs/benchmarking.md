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
cow-perf baselines

# Show baseline details
cow-perf baselines --show my-baseline

# Delete a baseline
cow-perf baselines --delete old-baseline
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

### Verdict Thresholds

| Verdict | Criteria |
|---------|----------|
| SUCCESS | Success rate ≥95%, latency within expectations |
| WARNING | Success rate 80-95% or elevated latency |
| FAILURE | Success rate <80% or critical latency issues |

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

## Troubleshooting

### Common Issues

**"Baseline not found"**
- Check baseline name with `cow-perf baselines`
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
cow-perf baselines --show my-baseline
```

## Best Practices

1. **Consistent Test Conditions**: Run benchmarks on similar hardware/load
2. **Sufficient Duration**: Run tests long enough for meaningful statistics (5+ minutes)
3. **Baseline Naming**: Use descriptive names with dates/versions
4. **Git Tags**: Save baselines after tagged releases for comparison
5. **Regular Benchmarking**: Run benchmarks on PRs to catch regressions early
