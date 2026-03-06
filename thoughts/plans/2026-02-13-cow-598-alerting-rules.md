# COW-598: Alerting Rules Implementation Plan

## Overview

Implement Prometheus alerting rules for the CoW Performance Testing Suite. This plan delivers 7 core alerts that notify developers when performance degrades, error rates spike, or resource utilization exceeds thresholds during performance testing. Alert parameters are organized for easy modification with TODO references to COW-617 for future configurability.

**Ticket**: [COW-598-alerting-rules.md](../tickets/COW-598-alerting-rules.md)
**Grant Requirement**: M3 - Metrics & Visualization includes "Alerting rules"

---

## Current State Analysis

### What Already Exists

1. **Prometheus Configuration** (`configs/prometheus.yml:73-81`):
   - Alert rules section is commented out (`rule_files:` and `alerting:`)
   - Evaluation interval already set to 5s (suitable for alerting)
   - External labels configured (`monitor`, `environment`)

2. **All Required Metrics Exist** (`src/cow_performance/prometheus/metrics.py`):
   | Alert Category | Metrics Available |
   |----------------|-------------------|
   | Latency | `cow_perf_submission_latency_seconds_bucket` |
   | Error Rate | `cow_perf_orders_failed_total`, `cow_perf_orders_submitted_total` |
   | Throughput | `cow_perf_actual_rate`, `cow_perf_target_rate` |
   | Resources | `cow_perf_container_cpu_percent`, `cow_perf_container_memory_bytes` |
   | Test State | `cow_perf_test_progress_percent`, `cow_perf_orders_submitted_total` |

3. **Docker Infrastructure** (`docker-compose.yml:235-248`):
   - Prometheus service exists with volume mount at `/etc/prometheus/`
   - Currently only mounts `prometheus.yml`, not an alerts directory

4. **Grafana Dashboards** (`configs/dashboards/`):
   - 5 dashboards exist: performance, api-performance, comparison, resources, trader-activity
   - No alert annotations configured

### Key Discoveries

- Prometheus in Docker expects config at `/etc/prometheus/prometheus.yml`
- Volume mount pattern: `./configs/prometheus.yml:/etc/prometheus/prometheus.yml:ro`
- Need to mount alerts directory separately or extend the mount
- `cow_perf_container_memory_limit_bytes` metric does NOT exist - will use absolute threshold instead

---

## Desired End State

After this plan is complete:

1. A new `configs/prometheus/alerts/performance-testing.yml` file exists with:
   - Clear parameter documentation section at the top
   - TODO(COW-617) references for future configurability
   - 7 core alerting rules

2. Prometheus loads and evaluates the alert rules every 5 seconds

3. Alerts are visible in:
   - Prometheus UI at `/alerts`
   - Grafana dashboards via annotations

4. All alert parameters are easy to find and modify in one place

### Verification

```bash
# Start monitoring stack
docker compose --profile monitoring up -d

# Run a test to generate metrics
cow-perf run --prometheus-port 9091 --duration 120

# Check alerts in Prometheus UI
open http://localhost:9090/alerts

# Verify alert rules loaded
curl -s http://localhost:9090/api/v1/rules | jq '.data.groups[].name'
# Expected: "cow_performance_testing"
```

---

## What We're NOT Doing

1. **Alertmanager** - No notification channels (Slack, email, webhook)
2. **Full alert scope** - Only 7 core alerts, not the 15+ in the ticket
3. **Configurable thresholds** - Hardcoded with TODO(COW-617) for future work
4. **Alert testing framework** - Manual testing only
5. **Regression alerts** - `cow_perf_regression_detected` metric exists but regression alerts are lower priority

---

## Implementation Approach

1. **Create alerts directory structure** - New `configs/prometheus/alerts/` directory
2. **Parameter-first design** - All thresholds documented at top of file
3. **Mount alerts in Docker** - Update docker-compose volume mounts
4. **Enable rule loading in Prometheus** - Uncomment and configure `rule_files:`
5. **Add Grafana annotations** - Show firing alerts on dashboards

---

## Phase 1: Create Alert Rules Directory Structure

### Overview

Create the directory structure for Prometheus alert rules and the main alert rules file with parameter documentation.

### Changes Required

#### 1. Create Alerts Directory

```bash
mkdir -p configs/prometheus/alerts
```

#### 2. Create Alert Rules File

**File**: `configs/prometheus/alerts/performance-testing.yml`

```yaml
# =============================================================================
# CoW Performance Testing Suite - Prometheus Alert Rules
# =============================================================================
#
# This file defines alerting rules for the CoW Performance Testing Suite.
# Alerts are evaluated by Prometheus and can be viewed in the Prometheus UI
# or visualized in Grafana dashboards.
#
# =============================================================================
# ALERT PARAMETERS - Edit values here for easy customization
# =============================================================================
#
# TODO(COW-617): Move these thresholds to configurable TOML/env variables
#
# LATENCY THRESHOLDS (seconds):
#   submission_latency_warning_threshold: 5      # P95 > 5s triggers warning
#   submission_latency_critical_threshold: 10    # P95 > 10s triggers critical
#
# ERROR RATE THRESHOLDS (decimal, where 0.05 = 5%):
#   error_rate_critical_threshold: 0.05          # > 5% error rate
#
# THROUGHPUT THRESHOLDS (ratio, where 0.8 = 80%):
#   throughput_low_threshold: 0.8                # < 80% of target rate
#
# RESOURCE THRESHOLDS (percentage):
#   cpu_warning_threshold: 80                    # CPU > 80%
#   memory_critical_threshold: 95                # Memory > 95%
#
# ALERT DURATIONS (prevents flapping):
#   latency_warning_for: 2m
#   latency_critical_for: 1m
#   error_rate_for: 1m
#   throughput_for: 2m
#   cpu_for: 5m
#   memory_for: 2m
#   test_stalled_for: 1m
#
# =============================================================================

groups:
  - name: cow_performance_testing
    # Evaluation interval inherited from global config (5s)
    rules:
      # =========================================================================
      # LATENCY ALERTS
      # =========================================================================

      # High Submission Latency (Warning)
      # Triggers when P95 submission latency exceeds warning threshold
      - alert: HighSubmissionLatency
        expr: |
          histogram_quantile(0.95,
            sum(rate(cow_perf_submission_latency_seconds_bucket[1m])) by (le, scenario)
          ) > 5
        for: 2m
        labels:
          severity: warning
          component: cow-performance-testing
          category: latency
        annotations:
          summary: "High submission latency detected"
          description: "P95 submission latency is {{ $value | printf \"%.2f\" }}s (threshold: 5s) for scenario {{ $labels.scenario }}"
          runbook: "Check API logs, verify network connectivity, review recent code changes"

      # Critical Submission Latency (Critical)
      # Triggers when P95 submission latency exceeds critical threshold
      - alert: CriticalSubmissionLatency
        expr: |
          histogram_quantile(0.95,
            sum(rate(cow_perf_submission_latency_seconds_bucket[1m])) by (le, scenario)
          ) > 10
        for: 1m
        labels:
          severity: critical
          component: cow-performance-testing
          category: latency
        annotations:
          summary: "Critical submission latency - immediate attention required"
          description: "P95 submission latency is {{ $value | printf \"%.2f\" }}s (threshold: 10s) for scenario {{ $labels.scenario }}"
          runbook: "Immediate action: Check API health, container resources, database connections"

      # =========================================================================
      # ERROR RATE ALERTS
      # =========================================================================

      # High Error Rate (Critical)
      # Triggers when order failure rate exceeds threshold
      - alert: HighErrorRate
        expr: |
          (
            sum(rate(cow_perf_orders_failed_total[5m])) by (scenario)
            /
            sum(rate(cow_perf_orders_submitted_total[5m])) by (scenario)
          ) > 0.05
        for: 1m
        labels:
          severity: critical
          component: cow-performance-testing
          category: errors
        annotations:
          summary: "High error rate detected"
          description: "Error rate is {{ $value | humanizePercentage }} (threshold: 5%) for scenario {{ $labels.scenario }}"
          runbook: "Check order validation errors, API error responses, contract state"

      # =========================================================================
      # THROUGHPUT ALERTS
      # =========================================================================

      # Low Throughput (Warning)
      # Triggers when actual throughput falls below target
      - alert: LowThroughput
        expr: |
          (
            cow_perf_actual_rate
            /
            cow_perf_target_rate
          ) < 0.8
          and cow_perf_target_rate > 0
        for: 2m
        labels:
          severity: warning
          component: cow-performance-testing
          category: throughput
        annotations:
          summary: "Low throughput - not meeting target rate"
          description: "Actual throughput is {{ $value | humanizePercentage }} of target for scenario {{ $labels.scenario }}"
          runbook: "Check for bottlenecks: API rate limits, network latency, resource constraints"

      # =========================================================================
      # TEST EXECUTION ALERTS
      # =========================================================================

      # Test Stalled (Critical)
      # Triggers when no orders are being submitted during an active test
      - alert: TestStalled
        expr: |
          rate(cow_perf_orders_submitted_total[1m]) == 0
          and
          cow_perf_test_progress_percent > 0
          and
          cow_perf_test_progress_percent < 100
        for: 1m
        labels:
          severity: critical
          component: cow-performance-testing
          category: test-execution
        annotations:
          summary: "Performance test appears to be stalled"
          description: "No orders submitted in the last minute for scenario {{ $labels.scenario }} (progress: {{ $value }}%)"
          runbook: "Check test process, verify API connectivity, review error logs"

      # =========================================================================
      # RESOURCE ALERTS
      # =========================================================================

      # High CPU Usage (Warning)
      # Triggers when container CPU usage is high
      - alert: HighCPUUsage
        expr: |
          cow_perf_container_cpu_percent > 80
        for: 5m
        labels:
          severity: warning
          component: cow-performance-testing
          category: resources
        annotations:
          summary: "High CPU usage on {{ $labels.container }}"
          description: "CPU usage is {{ $value | printf \"%.1f\" }}% (threshold: 80%) on container {{ $labels.container }}"
          runbook: "Consider scaling resources, check for inefficient operations, review container limits"

      # Critical Memory Usage (Critical)
      # Triggers when container memory usage approaches limit
      # Note: Using absolute percentage since cow_perf_container_memory_limit_bytes not available
      - alert: CriticalMemoryUsage
        expr: |
          cow_perf_container_memory_percent > 95
        for: 2m
        labels:
          severity: critical
          component: cow-performance-testing
          category: resources
        annotations:
          summary: "Critical memory usage on {{ $labels.container }}"
          description: "Memory usage is {{ $value | printf \"%.1f\" }}% (threshold: 95%) on container {{ $labels.container }}"
          runbook: "Immediate action: Check for memory leaks, increase container memory limit, restart if necessary"
```

### Success Criteria

- [x] Directory `configs/prometheus/alerts/` exists
- [x] File `configs/prometheus/alerts/performance-testing.yml` exists with valid YAML syntax

---

## Phase 2: Update Prometheus Configuration

### Overview

Enable alert rule loading in Prometheus by uncommenting and configuring the `rule_files:` section.

### Changes Required

#### 1. Update Prometheus Config

**File**: `configs/prometheus.yml`

**Change**: Replace lines 73-81 (the commented alert section) with:

```yaml
# Alert rule files
rule_files:
  - "/etc/prometheus/alerts/*.yml"

# Note: Alertmanager not configured - alerts visible in Prometheus UI and Grafana only
# To enable Alertmanager notifications, uncomment below and add alertmanager service:
# alerting:
#   alertmanagers:
#     - static_configs:
#         - targets: ["alertmanager:9093"]
```

### Success Criteria

- [x] YAML syntax is valid: `python -c "import yaml; yaml.safe_load(open('configs/prometheus.yml'))"`

---

## Phase 3: Update Docker Compose Volume Mounts

### Overview

Update the Prometheus service in docker-compose.yml to mount the alerts directory.

### Changes Required

#### 1. Update Docker Compose

**File**: `docker-compose.yml`

**Change**: Update the prometheus service volumes section (around line 246-248):

From:
```yaml
    volumes:
      - ./configs/prometheus.yml:/etc/prometheus/prometheus.yml:ro
      - prometheus_data:/prometheus
```

To:
```yaml
    volumes:
      - ./configs/prometheus.yml:/etc/prometheus/prometheus.yml:ro
      - ./configs/prometheus/alerts:/etc/prometheus/alerts:ro
      - prometheus_data:/prometheus
```

### Success Criteria

- [x] Docker Compose syntax is valid: `docker compose config --quiet`

---

## Phase 4: Add Grafana Alert Annotations

### Overview

Update the Performance Overview dashboard to display alert annotations and an alerts status panel.

### Changes Required

#### 1. Update Performance Dashboard

**File**: `configs/dashboards/performance.json`

Add alert annotations to the dashboard. This requires adding an `annotations` section to the dashboard JSON.

**Change**: Add annotations configuration to show when alerts fire. Find the `"annotations"` section (or add it after `"templating"`) and update it:

```json
"annotations": {
  "list": [
    {
      "builtIn": 1,
      "datasource": {
        "type": "grafana",
        "uid": "-- Grafana --"
      },
      "enable": true,
      "hide": true,
      "iconColor": "rgba(0, 211, 255, 1)",
      "name": "Annotations & Alerts",
      "type": "dashboard"
    },
    {
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "enable": true,
      "expr": "ALERTS{alertstate=\"firing\", component=\"cow-performance-testing\"}",
      "iconColor": "red",
      "name": "Firing Alerts",
      "tagKeys": "alertname,severity",
      "titleFormat": "{{ alertname }}"
    }
  ]
}
```

### Success Criteria

- [x] Dashboard JSON is valid: `python -c "import json; json.load(open('configs/dashboards/performance.json'))"`

---

## Phase 5: Fix Memory Metric for Alert

### Overview

The alert rule uses `cow_perf_container_memory_percent` but this metric doesn't exist. We need to either:
1. Add the metric to the exporter, OR
2. Update the alert to use existing metrics

Based on review of `src/cow_performance/prometheus/metrics.py:200-225`, the available memory metric is `cow_perf_container_memory_bytes` (absolute bytes, not percentage).

### Changes Required

#### 1. Add Memory Percentage Metric

**File**: `src/cow_performance/prometheus/metrics.py`

**Change**: Add new gauge in `_init_resource_metrics()` method (around line 220):

```python
        self.container_memory_percent = Gauge(
            "cow_perf_container_memory_percent",
            "Container memory usage as percentage (0-100)",
            ["container"],
            registry=self.registry,
        )
```

#### 2. Update Exporter to Calculate Percentage

**File**: `src/cow_performance/prometheus/exporter.py`

**Change**: In the resource metrics update method, calculate and set the percentage. Find the `_update_resource_metrics` method and add:

```python
        # Calculate memory percentage if limit is known
        # Note: This requires container memory limit to be available
        # For now, we'll set this from Docker stats which provides percentage directly
        if hasattr(sample, 'memory_percent') and sample.memory_percent is not None:
            self._metrics.container_memory_percent.labels(
                container=sample.container_name
            ).set(sample.memory_percent)
```

**Alternative**: If ResourceSample doesn't have memory_percent, update the alert to use a fixed threshold in bytes:

```yaml
      - alert: CriticalMemoryUsage
        expr: |
          cow_perf_container_memory_bytes > 3.8e9
        # ... (3.8GB threshold, adjust based on container limits)
```

### Success Criteria

- [x] `poetry run mypy src/cow_performance/prometheus/` passes
- [x] Memory percentage metric is exposed at `/metrics` endpoint

---

## Phase 6: Documentation and Testing

### Overview

Document the alerting rules and provide manual testing instructions.

### Changes Required

#### 1. Update Ticket with Implementation Notes

**File**: `thoughts/tickets/COW-598-alerting-rules.md`

**Change**: Add implementation notes section at the end:

```markdown
---

## Implementation Notes (2026-02-13)

### Implemented Scope

**Approach**: Option A (Prometheus alerting rules + Grafana visualization)
**Alert Count**: 7 core alerts (reduced from 15+ in original scope)

### Alerts Implemented

| Alert | Severity | Condition | Duration |
|-------|----------|-----------|----------|
| HighSubmissionLatency | Warning | P95 > 5s | 2m |
| CriticalSubmissionLatency | Critical | P95 > 10s | 1m |
| HighErrorRate | Critical | Error rate > 5% | 1m |
| LowThroughput | Warning | Actual < 80% target | 2m |
| TestStalled | Critical | No orders for 1m during active test | 1m |
| HighCPUUsage | Warning | CPU > 80% | 5m |
| CriticalMemoryUsage | Critical | Memory > 95% | 2m |

### What Was NOT Implemented

- Alertmanager (no Slack/email/webhook notifications)
- Settlement latency alerts
- API error spike alerts
- Regression alerts
- Alert testing framework
- Configurable thresholds (see COW-617)

### Threshold Configuration

All thresholds are hardcoded in `configs/prometheus/alerts/performance-testing.yml`.
Parameters are documented at the top of the file for easy modification.

**TODO(COW-617)**: Move thresholds to configurable TOML/env variables.

### Files Created/Modified

- `configs/prometheus/alerts/performance-testing.yml` (NEW)
- `configs/prometheus.yml` (modified: enabled rule_files)
- `docker-compose.yml` (modified: added alerts volume mount)
- `configs/dashboards/performance.json` (modified: added alert annotations)
- `src/cow_performance/prometheus/metrics.py` (modified: added memory_percent gauge)
```

### Success Criteria

- [x] Ticket file updated with implementation notes

---

## Testing Strategy

### Manual Testing Steps

1. **Verify alert rules syntax**:
   ```bash
   # Use promtool if available, or start Prometheus and check logs
   docker run --rm -v $(pwd)/configs/prometheus:/etc/prometheus \
     prom/prometheus promtool check rules /etc/prometheus/alerts/performance-testing.yml
   ```

2. **Start monitoring stack**:
   ```bash
   docker compose --profile monitoring up -d
   ```

3. **Verify rules loaded in Prometheus**:
   ```bash
   # Check rules API
   curl -s http://localhost:9090/api/v1/rules | jq '.data.groups[].name'
   # Expected output: "cow_performance_testing"

   # Check alerts page
   open http://localhost:9090/alerts
   ```

4. **Run a test to generate metrics**:
   ```bash
   cow-perf run --prometheus-port 9091 --duration 120
   ```

5. **Trigger alerts manually (optional)**:
   ```bash
   # To test HighErrorRate, you could submit invalid orders
   # To test TestStalled, pause the test mid-execution
   # Alerts should appear in Prometheus UI within evaluation interval + for duration
   ```

6. **Verify Grafana annotations**:
   ```bash
   open http://localhost:3000
   # Navigate to Performance Overview dashboard
   # Firing alerts should appear as red annotations on graphs
   ```

### Automated Verification

```bash
# Format and lint
poetry run black src/ tests/
poetry run ruff check --fix src/ tests/

# Type check
poetry run mypy src/

# Run tests
poetry run pytest

# Validate YAML files
python -c "import yaml; yaml.safe_load(open('configs/prometheus.yml'))"
python -c "import yaml; yaml.safe_load(open('configs/prometheus/alerts/performance-testing.yml'))"

# Validate JSON
python -c "import json; json.load(open('configs/dashboards/performance.json'))"

# Validate Docker Compose
docker compose config --quiet
```

---

## Success Criteria Summary

### Automated Verification

- [x] `poetry run black src/ tests/` passes
- [x] `poetry run ruff check src/ tests/` passes
- [x] `poetry run mypy src/cow_performance/prometheus/` passes (pre-existing errors in other modules)
- [x] `poetry run pytest tests/unit/` passes (e2e tests require Docker services)
- [x] YAML syntax valid for all config files
- [x] JSON syntax valid for dashboard files
- [x] Docker Compose config valid

### Manual Verification

- [ ] Prometheus loads alert rules (visible at `/alerts`)
- [ ] Alert rules API returns `cow_performance_testing` group
- [ ] Running a test generates metrics that alerts can evaluate
- [ ] Grafana shows alert annotations on Performance dashboard
- [x] Alert parameters are clearly documented at top of rules file

---

## References

- Original ticket: [COW-598-alerting-rules.md](../tickets/COW-598-alerting-rules.md)
- Prometheus alerting docs: https://prometheus.io/docs/prometheus/latest/configuration/alerting_rules/
- Grafana annotations: https://grafana.com/docs/grafana/latest/dashboards/build-dashboards/annotate-visualizations/
- Related ticket for configurability: COW-617
