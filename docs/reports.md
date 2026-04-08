# Reports & Baselines

Comprehensive guide to saving baselines, generating reports, and detecting regressions.

## Overview

The CoW Performance Testing Suite provides powerful baseline management and reporting features:

- **Save baselines** from test runs for future comparison
- **Generate reports** in multiple formats (text, markdown, JSON)
- **Compare baselines** to detect regressions or improvements
- **Export CSV data** for custom analysis
- **Track multiple solvers** automatically

> **For conceptual understanding** of baselines, comparison, and regression detection, see [Performance Benchmarking Guide](benchmarking.md).

## Quick Start

```bash
# Run test and save as baseline
cow-perf run --config scenario.yml --save-baseline "v1.0"

# Generate report
cow-perf report generate v1.0

# Compare with another baseline
cow-perf report generate v2.0 --compare v1.0
```

---

## Saving Baselines

### Save During Test Run

The recommended approach is to save baselines during test execution using the `--save-baseline` flag:

```bash
# Basic baseline save
cow-perf run --config configs/scenarios/predefined/light-load.yml \
  --save-baseline "v1.0"

# With description and tags
cow-perf run --config configs/scenarios/predefined/light-load.yml \
  --save-baseline "v1.0" \
  --baseline-description "Production baseline before optimization" \
  --baseline-tags "production,release,pre-optimization"
```

**Benefits:**
- Single command execution
- Automatic timestamp and metadata capture
- No intermediate files to manage

**Storage Location:** `.cow-perf/baselines/{uuid}.json`

### Baseline Metadata

Each baseline includes:
- Test configuration (traders, duration, patterns)
- Order statistics (total, by type, success/failure)
- Performance metrics (latency percentiles, throughput)
- Resource utilization (CPU, memory, network)
- Timestamp and description
- Tags for organization

---

## Managing Baselines

### List All Baselines

```bash
# List all saved baselines
cow-perf baselines --list

# Output shows:
# - Baseline ID
# - Creation timestamp
# - Description
# - Tags
# - Key metrics summary
```

### Show Baseline Details

```bash
# Show detailed information
cow-perf baselines --show v1.0

# Output includes:
# - Full configuration
# - Complete metrics breakdown
# - Success criteria validation
# - Resource utilization
```

### Delete Baselines

```bash
# Delete specific baseline
cow-perf baselines --delete v1.0

# Confirmation prompt shown before deletion
```

---

## Generating Reports

### Report Formats

Generate reports in multiple formats for different use cases:

```bash
# Text report to console (default)
cow-perf report generate v1.0

# Save text report to file
cow-perf report generate v1.0 --save

# Markdown report (GitHub-friendly)
cow-perf report generate v1.0 -f markdown --save

# JSON report (machine-readable)
cow-perf report generate v1.0 -f json --save
```

**Output location:** `.cow-perf/reports/report-{baseline}-{timestamp}.{format}`

### Report Contents

Reports include:

1. **Executive Summary**
   - Test verdict (SUCCESS/WARNING/FAILURE)
   - Key metrics overview
   - Main findings

2. **Order Metrics**
   - Total orders created/submitted/filled
   - Success rate
   - Order type breakdown
   - Lifecycle latencies (P50, P90, P95, P99)

3. **API Performance**
   - Response times by endpoint
   - Request counts and error rates
   - API utilization

4. **Resource Utilization**
   - CPU usage (P95) per container
   - Memory usage (P95) per container
   - Network I/O
   - Solver-specific metrics

5. **Recommendations**
   - Actionable insights based on metrics
   - Performance improvement suggestions

### CSV Export

Export detailed metrics as CSV files for custom analysis:

```bash
# Generate report with CSV exports
cow-perf report generate v1.0 --save --export-csv

# Creates CSV files:
# - summary.csv - High-level metrics
# - latencies.csv - Latency percentiles
# - recommendations.csv - Improvement suggestions
```

**Output location:** `.cow-perf/reports/csv/{baseline}/`

---

## Baseline Comparison

### Compare Two Baselines

Compare baselines to detect regressions or improvements:

```bash
# Compare current against previous baseline
cow-perf report generate v2.0 --compare v1.0 --save

# With markdown format for PRs
cow-perf report generate v2.0 --compare v1.0 -f markdown --save
```

### Comparison Report

The comparison report shows:

**✅ Improvements:** Metrics that got better
```
- submission_latency_p95: -15.3% (improved from 12.5s to 10.6s)
- throughput: +22.1% (improved from 4.5/s to 5.5/s)
```

**⚠️ Regressions:** Metrics that got worse (with severity)
```
- fill_latency_p95: +45.2% (regressed from 8.2s to 11.9s) [MAJOR]
- error_rate: +10.0% (regressed from 5% to 5.5%) [MINOR]
```

**Severity Levels:**
- **MINOR**: <10% change or within acceptable threshold
- **MAJOR**: 10-25% change or significant impact
- **CRITICAL**: >25% change or test failure

**📊 Percent Changes:** For all key metrics

**🔧 Recommendations:** Actionable insights based on comparison

### Regression Detection in CI/CD

Use exit codes for automated failure detection:

```bash
# Run comparison in CI pipeline
cow-perf report generate current --compare baseline

# Exit codes:
# 0 = No regressions detected
# 2 = Performance regression detected
# 1 = Error (invalid arguments, missing files)
```

**Example GitHub Actions workflow:**
```yaml
- name: Run performance test
  run: |
    cow-perf run --config scenario.yml --save-baseline current

- name: Compare against baseline
  run: |
    cow-perf report generate current --compare baseline -f markdown --save

- name: Check for regressions
  run: |
    if [ $? -eq 2 ]; then
      echo "❌ Performance regression detected!"
      exit 1
    fi
```

---

## Multiple Solver Tracking

### Automatic Discovery

**All solver containers are automatically tracked** - no configuration needed!

The system uses pattern matching to discover containers:
- Any container with `solver` in its name is tracked
- Examples: `solver-baseline-1`, `solver-quasimodo-1`, `solver-custom-abc`
- Each solver gets separate resource metrics

**Supported patterns:**
- `solver-baseline-*` - Baseline solver instances
- `solver-quasimodo-*` - Quasimodo solver instances
- `solver-{any-type}-*` - Any custom solver type

### Example Report Output

```
Resource Utilization:
  Container              CPU(P95)  Memory(P95)
  -----------------------------------------------
  solver-baseline-1        38.8%       11.0%
  solver-baseline-2        43.8%       12.0%
  solver-baseline-3        48.8%       13.0%
  solver-quasimodo-1       35.2%       10.5%
  solver-quasimodo-2       41.1%       11.8%
```

### Comparison with Multiple Solvers

When comparing baselines, per-solver improvements/regressions are shown:

```
Improvements:
  - resource_solver-baseline-1_cpu: -51.5% (improved)
  - resource_solver-baseline-2_cpu: -9.1% (improved)
  - resource_solver-quasimodo-1_cpu: -12.3% (improved)

Regressions:
  - resource_solver-baseline-3_memory: +15.2% (regressed) [MINOR]
```

### Adding More Solvers

To add a new solver and have it automatically tracked:

1. **Add solver service to `docker-compose.yml`**:
   ```yaml
   solver-baseline-4:
     build:
       context: ./modules/services
       target: solvers
     command: ["baseline", "--config", "/baseline.toml"]
     volumes:
       - ./configs/baseline.toml:/baseline.toml:ro
     networks:
       - cownet
   ```

2. **Update autopilot and orderbook environment variables** in `docker-compose.yml`:
   ```yaml
   # Add new solver to DRIVERS, PRICE_ESTIMATION_DRIVERS, NATIVE_PRICE_ESTIMATORS
   - DRIVERS=solver-baseline-1|http://driver/solver-baseline-1|${SOLVER_ADDRESS},solver-baseline-4|http://driver/solver-baseline-4|${SOLVER_ADDRESS}
   ```

3. **Add solver configuration to `configs/driver.toml`**:
   ```toml
   [[solver]]
   name = "solver-baseline-4"
   endpoint = "http://solver-baseline-4"
   absolute-slippage = "40000000000000000"
   relative-slippage = "0.1"
   account = "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"
   ```

4. **Build and start containers**:
   ```bash
   docker compose build solver-baseline-4
   docker compose up -d
   ```

5. **Verify in reports** - the new solver appears automatically!

**No code changes needed** - the system discovers and tracks any container with `solver` in its name.

---

## Complete Workflow Example

### End-to-End Baseline Workflow

```bash
# 1. Run initial test and save baseline
cow-perf run --config configs/scenarios/predefined/medium-load.yml \
  --save-baseline "before-optimization" \
  --baseline-description "Performance before optimization work" \
  --baseline-tags "pre-optimization,baseline"

# 2. Make code changes, optimize, etc.

# 3. Run new test and save as new baseline
cow-perf run --config configs/scenarios/predefined/medium-load.yml \
  --save-baseline "after-optimization" \
  --baseline-description "Performance after optimization" \
  --baseline-tags "post-optimization,candidate"

# 4. Generate comparison report
cow-perf report generate after-optimization \
  --compare before-optimization \
  -f markdown \
  --save \
  --export-csv

# 5. View results
cat .cow-perf/reports/report-after-optimization-vs-before-optimization-*.md

# 6. Analyze CSV data (optional)
ls .cow-perf/reports/csv/after-optimization/
# summary.csv, latencies.csv, recommendations.csv
```

### Multi-Environment Comparison

```bash
# Test against local environment
export COW_API_BASE_URL=http://localhost:8080
cow-perf run --config scenario.yml --save-baseline "local" \
  --baseline-tags "environment:local"

# Test against staging
export COW_API_BASE_URL=https://staging-api.cow.fi
cow-perf run --config scenario.yml --save-baseline "staging" \
  --baseline-tags "environment:staging"

# Compare environments
cow-perf report generate staging --compare local -f markdown --save
```

---

## Data Directory Structure

All reports, baselines, and results are saved in `.cow-perf/`:

```
.cow-perf/
├── baselines/              # Saved performance baselines
│   ├── {uuid}.json         # Baseline data
│   └── README.md           # Documentation
├── reports/                # Generated reports
│   ├── report-*.txt        # Text reports
│   ├── report-*.md         # Markdown reports
│   ├── report-*.json       # JSON reports
│   └── csv/                # CSV exports
│       └── {baseline}/
│           ├── summary.csv
│           ├── latencies.csv
│           └── recommendations.csv
└── results/                # Raw test results
    └── {timestamp}.json    # Test execution data
```

See `.cow-perf/README.md` in your project directory for detailed documentation on the data structure.

---

## See Also

- [CLI Reference](cli.md) - Command options and examples
- [Benchmarking](benchmarking.md) - Performance analysis techniques
- [Scenario User Guide](scenario-user-guide.md) - Creating test scenarios
- [Configuration Reference](configuration-reference.md) - Full configuration schema
