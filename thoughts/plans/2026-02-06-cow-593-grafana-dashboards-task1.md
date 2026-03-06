# COW-593 Task 1: Grafana Dashboards Implementation Plan

## Overview

Create the essential Grafana dashboards for performance testing: **Performance Overview** and **API Performance**. These dashboards visualize metrics exposed by COW-591 Prometheus exporter, providing real-time visibility into test execution.

**Scope**: Task 1 only (2 points). Task 2 (Resources, Comparison, Trader Activity dashboards) is tracked separately in `thoughts/tasks/COW-593-remaining-dashboards.md`.

## Current State Analysis

**What exists:**
- Grafana service configured in `docker-compose.yml` (port 3000, monitoring profile)
- Datasource provisioning: `configs/grafana-datasource.yml` (Prometheus at http://prometheus:9090)
- Dashboard provisioning: `configs/grafana-dashboard.yml` (expects dashboards at `/etc/grafana/dashboards/`)
- **No dashboard JSON files exist** — the `configs/` directory has provisioning configs but no actual dashboards

**What COW-591 exposes (available metrics):**
- Order counters: `cow_perf_orders_created_total`, `cow_perf_orders_submitted_total`, `cow_perf_orders_filled_total`, `cow_perf_orders_failed_total`, `cow_perf_orders_expired_total`
- Order gauge: `cow_perf_orders_active`
- Latency histograms: `cow_perf_submission_latency_seconds`, `cow_perf_orderbook_latency_seconds`, `cow_perf_settlement_latency_seconds`, `cow_perf_order_lifecycle_seconds`
- Throughput gauges: `cow_perf_orders_per_second`, `cow_perf_target_rate`, `cow_perf_actual_rate`
- Test metadata: `cow_perf_test_info`, `cow_perf_test_start_timestamp`, `cow_perf_test_duration_seconds`, `cow_perf_num_traders`, `cow_perf_test_progress_percent`
- API metrics: `cow_perf_api_requests_total`, `cow_perf_api_response_time_seconds`, `cow_perf_api_errors_total`

**Key discovery:**
- Docker-compose sets `GF_DASHBOARDS_DEFAULT_HOME_DASHBOARD_PATH=/etc/grafana/dashboards/performance.json`
- The main dashboard file MUST be named `performance.json` to be the home dashboard

### Key Discoveries:

- `configs/grafana-dashboard.yml:14` - Provisioning expects dashboards at `/etc/grafana/dashboards`
- `docker-compose.yml:260` - Home dashboard path is `/etc/grafana/dashboards/performance.json`
- `docker-compose.yml:264-265` - Volume mounts for provisioning configs exist, but no dashboard volume mount
- `src/cow_performance/prometheus/metrics.py` - All metric definitions with labels

## Desired End State

After this plan is complete:
1. `configs/dashboards/` directory exists with dashboard JSON files
2. `performance.json` serves as the Overview dashboard and Grafana home
3. `api-performance.json` provides detailed API metrics visualization
4. Both dashboards auto-load when Grafana starts
5. Dashboard variables (`scenario`) allow filtering
6. All panels display data when a performance test is running with `--prometheus-port`

### Verification:

```bash
# 1. Start monitoring stack
docker compose --profile monitoring up -d

# 2. Run a test with Prometheus exporter
poetry run cow-perf run --scenario light-load --prometheus-port 9091

# 3. Open Grafana and verify dashboards display data
open http://localhost:3000
```

## What We're NOT Doing

- Task 2 dashboards (Resources, Comparison, Trader Activity) — separate task
- Alerting integration — COW-598 is deferred
- Dashboard links/navigation between dashboards — Task 2
- Documentation screenshots — human action after implementation

---

## Phase 1: Dashboard Infrastructure Setup

### Overview

Create the directory structure and update provisioning configuration so Grafana can load dashboard JSON files.

### Changes Required:

#### 1. Create Dashboard Directory

**Action**: Create `configs/dashboards/` directory

```bash
mkdir -p configs/dashboards
```

#### 2. Update Docker Compose Volume Mount

**File**: `docker-compose.yml`
**Changes**: Add volume mount for dashboards directory

The Grafana service needs a volume mount to access the dashboard JSON files. Currently only provisioning configs are mounted.

Add this volume mount to the grafana service volumes section:
```yaml
- ./configs/dashboards:/etc/grafana/dashboards:ro
```

#### 3. Verify Provisioning Config

**File**: `configs/grafana-dashboard.yml`
**Status**: Already correct — points to `/etc/grafana/dashboards`

No changes needed. The existing config will work once dashboards are in place.

### Success Criteria:

#### Automated Verification:

- [x] Directory exists: `ls configs/dashboards/`
- [x] Docker compose validates: `docker compose config --quiet`

#### Manual Verification:

- [ ] Grafana starts without errors: `docker compose --profile monitoring up -d grafana`
- [ ] No provisioning errors in logs: `docker compose logs grafana | grep -i error`

---

## Phase 2: Performance Overview Dashboard

### Overview

Create the main performance testing dashboard (`performance.json`) that serves as Grafana's home dashboard. This provides at-a-glance visibility into test execution.

### Changes Required:

#### 1. Create Performance Overview Dashboard

**File**: `configs/dashboards/performance.json`
**Changes**: Create new Grafana dashboard JSON

The dashboard should include these rows and panels:

**Row 1: Test Overview**
- Stat panel: Current scenario name (from `cow_perf_test_info`)
- Stat panel: Test duration / elapsed time
- Stat panel: Number of traders (`cow_perf_num_traders`)
- Gauge panel: Test progress percentage (`cow_perf_test_progress_percent`)

**Row 2: Order Submission Rate**
- Time series: Orders submitted per second (actual vs target rate)
  - Use `cow_perf_orders_per_second`, `cow_perf_target_rate`, `cow_perf_actual_rate`
- Time series: Cumulative orders over time
  - Use `cow_perf_orders_created_total`, `cow_perf_orders_submitted_total`
- Gauge: Submission rate achievement (actual/target × 100%)

**Row 3: Latency Distribution**
- Heatmap: Submission latency distribution
  - Use `cow_perf_submission_latency_seconds_bucket`
- Heatmap: Settlement latency distribution
  - Use `cow_perf_settlement_latency_seconds_bucket`
- Time series: P50, P90, P95, P99 latencies over time
  - Use histogram_quantile() on latency histograms

**Row 4: Order Status**
- Pie chart: Order status distribution (filled, failed, expired, active)
  - Use order counters and gauge
- Stat panel: Success rate percentage (filled / submitted × 100%)
  - Color thresholds: green >95%, yellow >90%, red <90%
- Stat panel: Total orders submitted (with sparkline)
- Stat panel: Total orders filled (with sparkline)

**Dashboard Variables:**
- `scenario`: Query variable from `label_values(cow_perf_orders_created_total, scenario)`

**Dashboard Settings:**
- Title: "CoW Performance Testing - Overview"
- UID: `cow-perf-overview`
- Tags: `["cow-protocol", "performance-testing"]`
- Refresh: 5s auto-refresh
- Time range: Last 15 minutes default

### Success Criteria:

#### Automated Verification:

- [x] File exists: `ls configs/dashboards/performance.json`
- [x] Valid JSON: `python -m json.tool configs/dashboards/performance.json > /dev/null`
- [x] Linting passes (no code changes to src/)

#### Manual Verification:

- [ ] Dashboard loads in Grafana without errors
- [ ] Dashboard is set as home dashboard
- [ ] All 4 rows visible with panels
- [ ] Scenario variable dropdown populated (when test running)
- [ ] Panels show data during active test

---

## Phase 3: API Performance Dashboard

### Overview

Create a detailed API performance dashboard (`api-performance.json`) for monitoring orderbook API interactions during performance tests.

### Changes Required:

#### 1. Create API Performance Dashboard

**File**: `configs/dashboards/api-performance.json`
**Changes**: Create new Grafana dashboard JSON

The dashboard should include these rows and panels:

**Row 1: API Response Times**
- Time series: API response time by endpoint
  - Use `cow_perf_api_response_time_seconds`
- Heatmap: Response time distribution
  - Use `cow_perf_api_response_time_seconds_bucket`
- Stat panels: P50, P95, P99 response times
  - Use histogram_quantile()

**Row 2: API Throughput**
- Time series: Requests per second by endpoint
  - Use rate() on `cow_perf_api_requests_total`
- Stat panel: Total requests
- Time series: Requests by HTTP method (GET, POST, etc.)

**Row 3: API Errors**
- Time series: Error rate over time
  - Use rate() on `cow_perf_api_errors_total`
- Pie chart: Errors by type (client_error, server_error, timeout, connection_error)
- Stat panel: Total errors
- Table: Error breakdown by endpoint and type

**Dashboard Variables:**
- `scenario`: Query variable (same as overview dashboard)
- `endpoint`: Query variable from `label_values(cow_perf_api_requests_total, endpoint)`
- `method`: Query variable from `label_values(cow_perf_api_requests_total, method)`

**Dashboard Settings:**
- Title: "CoW Performance Testing - API Performance"
- UID: `cow-perf-api`
- Tags: `["cow-protocol", "performance-testing", "api"]`
- Refresh: 5s auto-refresh
- Time range: Last 15 minutes default

### Success Criteria:

#### Automated Verification:

- [x] File exists: `ls configs/dashboards/api-performance.json`
- [x] Valid JSON: `python -m json.tool configs/dashboards/api-performance.json > /dev/null`

#### Manual Verification:

- [ ] Dashboard loads in Grafana without errors
- [ ] All 3 rows visible with panels
- [ ] Variables (scenario, endpoint, method) populated when test running
- [ ] Filtering by endpoint works correctly

---

## Testing Strategy

### Unit Tests:

No unit tests required — dashboard JSON files are configuration, not code.

### Integration Tests:

The dashboards will be validated through manual testing (see Human Testing Section below).

### Automated Validation:

```bash
# Validate JSON syntax
python -m json.tool configs/dashboards/performance.json > /dev/null
python -m json.tool configs/dashboards/api-performance.json > /dev/null

# Validate docker-compose
docker compose config --quiet
```

---

## Human Testing Section

After implementation is complete, follow these steps to verify the dashboards work correctly.

### Prerequisites

1. COW-591 Prometheus exporter must be working
2. Docker and Docker Compose installed
3. Poetry environment set up (`poetry install`)

### Step 1: Start the Monitoring Stack

```bash
# Start Grafana and Prometheus
docker compose --profile monitoring up -d

# Verify services are running
docker compose ps

# Expected output should show grafana and prometheus as "running" or "healthy"
```

### Step 2: Verify Grafana Loads

```bash
# Open Grafana in browser
open http://localhost:3000

# OR use curl to check
curl -s http://localhost:3000/api/health
# Expected: {"commit":"...","database":"ok","version":"..."}
```

**Check:**
- [ ] Grafana loads without login (anonymous access enabled)
- [ ] Home dashboard shows "CoW Performance Testing - Overview"
- [ ] No error banners or provisioning errors

### Step 3: Check Dashboard List

1. In Grafana, click the hamburger menu (☰) → Dashboards
2. Look for dashboards in the list

**Check:**
- [ ] "CoW Performance Testing - Overview" appears
- [ ] "CoW Performance Testing - API Performance" appears

### Step 4: Run a Performance Test with Prometheus

```bash
# In a new terminal, run a test with Prometheus exporter enabled
poetry run cow-perf run --scenario light-load --prometheus-port 9091

# The test should start and you should see output indicating Prometheus exporter started
```

**Check:**
- [ ] Test starts without Prometheus-related errors
- [ ] Log shows "Prometheus exporter started on port 9091" (or similar)

### Step 5: Verify Prometheus Scraping

```bash
# Check Prometheus is scraping the exporter
open http://localhost:9090/targets

# OR use curl
curl -s http://localhost:9090/api/v1/targets | grep cow-performance
```

**Check:**
- [ ] `cow-performance-test` job shows State: `UP`
- [ ] Last scrape is recent (within last 10 seconds)

### Step 6: Verify Overview Dashboard Data

1. Go back to Grafana (http://localhost:3000)
2. Open the Overview dashboard (should be home)
3. Set time range to "Last 5 minutes"

**Check:**
- [ ] Test Overview row shows scenario name, duration, traders
- [ ] Order Submission Rate row shows time series with data points
- [ ] Latency Distribution row shows heatmaps with color (if orders submitted)
- [ ] Order Status row shows pie chart and stats with values > 0

### Step 7: Verify API Performance Dashboard Data

1. In Grafana, go to Dashboards → "CoW Performance Testing - API Performance"
2. Set time range to "Last 5 minutes"

**Check:**
- [ ] API Response Times row shows response time data
- [ ] API Throughput row shows requests per second
- [ ] API Errors row shows error counts (may be 0 if no errors)
- [ ] Variables (endpoint, method) have options in dropdowns

### Step 8: Test Dashboard Variables

1. On either dashboard, look for variable dropdowns at the top
2. Click the `scenario` dropdown

**Check:**
- [ ] Dropdown shows the current scenario name (e.g., "light-load")
- [ ] Selecting different values (if multiple tests ran) filters data

### Step 9: Verify Dashboards Persist After Restart

```bash
# Restart Grafana
docker compose restart grafana

# Wait for it to come back up
sleep 10

# Open Grafana again
open http://localhost:3000
```

**Check:**
- [ ] Dashboards still exist after restart
- [ ] Home dashboard is still the Overview dashboard
- [ ] Historical data from before restart is still visible

### Step 10: Stop Test and Cleanup

```bash
# Stop the performance test (Ctrl+C in the test terminal)

# Optionally stop monitoring stack
docker compose --profile monitoring down
```

### Troubleshooting

**Dashboard shows "No data":**
- Ensure test is running with `--prometheus-port 9091`
- Check Prometheus targets: http://localhost:9090/targets
- Verify metrics exist: `curl http://localhost:9091/metrics | grep cow_perf`

**Dashboard has red error panels:**
- Check Grafana logs: `docker compose logs grafana`
- Verify Prometheus datasource: Grafana → Connections → Data sources → Prometheus → Test

**Variables empty:**
- Metrics may not have been scraped yet — wait 10-15 seconds
- Check that the test has actually submitted orders

---

## Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `configs/dashboards/` | Create | New directory for dashboard JSON files |
| `configs/dashboards/performance.json` | Create | Performance Overview dashboard (home) |
| `configs/dashboards/api-performance.json` | Create | API Performance dashboard |
| `docker-compose.yml` | Modify | Add volume mount for dashboards directory |

---

## References

- Original ticket: `thoughts/tickets/COW-593-grafana-dashboards.md`
- Task 2 (remaining dashboards): `thoughts/tasks/COW-593-remaining-dashboards.md`
- PoC patterns: `thoughts/research/poc-evaluation.md`
- Prometheus metrics: `src/cow_performance/prometheus/metrics.py`
- M3 validation: `thoughts/validations/m3-validation.md`
- Grafana provisioning docs: https://grafana.com/docs/grafana/latest/administration/provisioning/
