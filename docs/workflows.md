# End-to-End Workflows

Common workflows for the CoW Performance Testing Suite.

---

## First-Time User Workflow

**Goal:** Run your first performance test.

```bash
# 1. Install
git clone https://github.com/cowprotocol/services-performance.git
cd services-performance
poetry install

# 2. Start services (wait 5-10 min for first startup)
docker compose up -d
docker compose ps  # All should show "healthy"

# 3. Run test
poetry run cow-perf run \
  --config configs/scenarios/predefined/smoke-test.yml \
  --num-traders 3 \
  --duration 120

# 4. View results
cat ~/.cow-perf/results/latest-result.json | jq .
```

**Next steps:** Try predefined scenarios, create custom scenarios, set up baselines.

---

## CI/CD Integration Workflow

**Goal:** Automated performance testing in CI/CD pipeline.

### GitHub Actions

`.github/workflows/performance.yml`:

```yaml
name: Performance Tests
on: [pull_request, push]

jobs:
  performance:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - uses: snok/install-poetry@v1

      - name: Install
        run: poetry install

      - name: Start services
        run: |
          docker compose up -d
          sleep 60

      - name: Run test
        run: |
          poetry run cow-perf run \
            --config configs/scenarios/ci/regression-test.yml \
            --compare-baseline baselines/main.json \
            --fail-on-regression

      - name: Upload results
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: performance-results
          path: ~/.cow-perf/results/
```

### CI Scenario

`configs/scenarios/ci/regression-test.yml`:

```yaml
name: "CI Regression Test"
tags: [ci, regression]

num_traders: 3
duration: 120

trading_pattern: "constant_rate"
base_rate: 30.0
market_order_ratio: 1.0

success_criteria:
  min_success_rate: 0.95
  max_p95_latency_seconds: 10.0
```

### Create Baseline

```bash
# On main branch
poetry run cow-perf run \
  --config configs/scenarios/ci/regression-test.yml \
  --save-baseline "main-$(git rev-parse --short HEAD)"

cp ~/.cow-perf/baselines/main-*.json baselines/main.json
git add baselines/main.json
git commit -m "chore: Updated CI baseline"
```

### Configure Thresholds

`configs/thresholds.toml`:

```toml
[ci]
success_rate_delta = -0.05
p95_latency_delta = 0.20
error_rate_delta = 0.02

[production]
success_rate_delta = -0.02
p95_latency_delta = 0.10
error_rate_delta = 0.01
```

Use: `export COW_PERF_THRESHOLD_PROFILE=ci`

---

## Performance Investigation Workflow

**Goal:** Diagnose performance issues.

### Reproduce

```bash
poetry run cow-perf run \
  --config configs/scenarios/predefined/sustained-load.yml \
  --duration 600

jq '.avg_order_latency_ms' ~/.cow-perf/results/latest-result.json
```

### Collect Metrics

```bash
# Fresh start
docker compose down -v
docker compose up -d

# Run with monitoring
poetry run cow-perf run \
  --config scenario.yml \
  --save-baseline "investigation"

# Open monitoring
open http://localhost:3000  # Grafana
open http://localhost:9091  # Prometheus
```

### Identify Bottlenecks

```bash
# Resource usage
docker stats

# Service logs
docker compose logs orderbook | grep -i error
docker compose logs autopilot | grep -i error
docker compose logs driver | grep -i error

# Database
docker exec -it $(docker ps -qf "name=db") psql -U postgres -d database

# Slow queries
SELECT query, mean_exec_time, calls
FROM pg_stat_statements
ORDER BY mean_exec_time DESC
LIMIT 10;
```

### Isolate Variables

```bash
# Reduce load
poetry run cow-perf run --config scenario.yml --num-traders 5

# Market orders only
poetry run cow-perf run --config scenario.yml --override "market_order_ratio=1.0"

# Lower rate
poetry run cow-perf run --config scenario.yml --override "base_rate=10.0"
```

### Document Findings

Create `thoughts/analysis/investigation-YYYY-MM-DD.md`:

```markdown
# Performance Investigation

## Issue
High latency observed (15s avg, expected <5s)

## Root Cause
Database connection pool exhaustion

## Evidence
- 95/100 connections in use
- Queue buildup in autopilot logs
- Normal latency restored with fewer traders

## Solution
Increased max_connections to 200 in docker-compose.yml

## Verification
4.1s avg latency after fix ✓
```

---

## Release Testing Workflow

**Goal:** Validate performance before release.

### Test Suite

```bash
# 1. Smoke test
poetry run cow-perf run \
  --config configs/scenarios/release/smoke-test.yml

# 2. Regression test
poetry run cow-perf run \
  --config configs/scenarios/release/regression.yml \
  --compare-baseline baselines/production.json \
  --fail-on-regression

# 3. Load test
poetry run cow-perf run \
  --config configs/scenarios/release/load-test.yml

# 4. Acceptance test
poetry run cow-perf run \
  --config configs/scenarios/release/acceptance.yml \
  --save-baseline "release-$(git describe --tags)"
```

### Acceptance Scenario

`configs/scenarios/release/acceptance.yml`:

```yaml
name: "Release Acceptance"
tags: [release, acceptance]

num_traders: 25
duration: 1800  # 30 minutes

trading_pattern: "poisson"
poisson_lambda: 60.0

market_order_ratio: 0.6
limit_order_ratio: 0.3
twap_order_ratio: 0.05
stop_loss_order_ratio: 0.05

success_criteria:
  min_success_rate: 0.98
  max_p95_latency_seconds: 8.0
  max_error_rate: 0.02
  min_fill_rate: 0.85
```

### Validate Results

```bash
# Check all passed
for result in ~/.cow-perf/results/2026-03-23*.json; do
  echo "$(basename $result): $(jq -r '.verdict' "$result")"
done

# Compare with previous release
poetry run cow-perf compare \
  baselines/release-v1.0.0.json \
  baselines/release-v1.1.0.json
```

### Update Baseline

```bash
cp ~/.cow-perf/baselines/release-v1.1.0.json baselines/production.json
git add baselines/production.json
git commit -m "chore: Updated baseline for v1.1.0"
```

---

## Custom Scenario Development

**Goal:** Create custom test scenario.

### Create Scenario

`configs/scenarios/custom/my-scenario.yml`:

```yaml
name: "My Custom Scenario"
description: "Test specific behavior"
tags: [custom]

# Inherit from template (optional)
extends: "configs/scenarios/templates/base.yml"

num_traders: 10
duration: 300

trading_pattern: "constant_rate"
base_rate: 30.0

market_order_ratio: 0.2
limit_order_ratio: 0.7
twap_order_ratio: 0.1

success_criteria:
  min_success_rate: 0.90
  max_p95_latency_seconds: 15.0
```

### Test Incrementally

```bash
# Validate
poetry run cow-perf scenarios --validate my-scenario.yml

# Short test
poetry run cow-perf run --config my-scenario.yml --duration 60

# Full test
poetry run cow-perf run --config my-scenario.yml

# Create baseline
poetry run cow-perf run \
  --config my-scenario.yml \
  --save-baseline "my-scenario" \
  --baseline-tags "custom"
```

### Parameterized Template

`configs/scenarios/templates/my-template.yml`:

```yaml
name: "${test_name}"
num_traders: ${traders}
duration: ${duration}
trading_pattern: "constant_rate"
base_rate: ${rate}
```

Use:

```yaml
# instance.yml
template: my-template
parameters:
  test_name: "Light Load"
  traders: 5
  duration: 120
  rate: 20.0
```

---

## Baseline Management

**Goal:** Manage performance baselines over time.

### Create Baseline

```bash
poetry run cow-perf run \
  --config scenario.yml \
  --save-baseline "baseline-name" \
  --baseline-tags "v1.0,production"

# Organize
mkdir -p baselines/{production,staging}
cp ~/.cow-perf/baselines/baseline-*.json baselines/production/v1.0.0.json

# Commit
git add baselines/
git commit -m "chore: Added production baseline"
```

### Compare Baselines

```bash
poetry run cow-perf compare \
  baselines/production/v1.0.0.json \
  baselines/production/v1.1.0.json

cat ~/.cow-perf/reports/comparison-*.json | jq .
```

### Track Over Time

`scripts/track-performance.sh`:

```bash
#!/bin/bash
BASELINE_DIR="baselines/production"
echo "Version,SuccessRate,AvgLatency,P95Latency" > trends.csv

for baseline in $BASELINE_DIR/*.json; do
  VERSION=$(basename $baseline .json)
  SUCCESS=$(jq -r '.success_rate' $baseline)
  AVG=$(jq -r '.avg_order_latency_ms' $baseline)
  P95=$(jq -r '.p95_latency_ms' $baseline)
  echo "$VERSION,$SUCCESS,$AVG,$P95" >> trends.csv
done
```

### Regression Detection

```bash
poetry run cow-perf run \
  --config scenario.yml \
  --compare-baseline baselines/production.json \
  --fail-on-regression

# Exit code 0 = pass, 1 = regression
```

### Cleanup

```bash
# Archive old baselines (90+ days)
mkdir -p baselines/archive/
find ~/.cow-perf/baselines/ -mtime +90 -exec mv {} baselines/archive/ \;
```

---

## Quick Reference

### Workflow Selection

| Goal | Workflow |
|------|----------|
| Getting started | First-Time User |
| CI/CD integration | CI/CD Integration |
| Debug issues | Performance Investigation |
| Validate release | Release Testing |
| Custom test | Custom Scenario Development |
| Track performance | Baseline Management |

### Common Commands

```bash
# First-time
poetry install && docker compose up -d
poetry run cow-perf run --config configs/scenarios/predefined/smoke-test.yml

# CI/CD
poetry run cow-perf run --config scenario.yml --compare-baseline baseline.json --fail-on-regression

# Investigation
docker stats
docker compose logs -f orderbook
poetry run cow-perf run --config test.yml --save-baseline "investigation"

# Release
poetry run cow-perf run --config acceptance.yml --save-baseline "release-v1.0"
poetry run cow-perf compare v1.0.json v1.1.json

# Custom
poetry run cow-perf scenarios --validate scenario.yml
poetry run cow-perf run --config scenario.yml --duration 60

# Baseline
poetry run cow-perf run --config scenario.yml --save-baseline "name" --baseline-tags "tag1,tag2"
```

---

## See Also

- [Scenario User Guide](scenario-user-guide.md)
- [CLI Reference](cli.md)
- [Benchmarking Guide](benchmarking.md)
- [Troubleshooting](troubleshooting.md)
