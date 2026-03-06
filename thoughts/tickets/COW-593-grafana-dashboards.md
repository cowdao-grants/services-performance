# COW-593: 12 - Grafana Dashboards

**Linear URL**: https://linear.app/bleu-builders/issue/COW-593/12-grafana-dashboards
**Status**: Todo
**Priority**: High
**Estimate**: 2 Points
**Milestone**: M3 — Metrics & Visualization
**Git Branch**: `jefferson/cow-593-12-grafana-dashboards`

## Summary

Create comprehensive Grafana dashboards for performance testing that leverage existing CoW Protocol dashboards from the PoC and extend them with performance testing-specific metrics including order throughput, latency distributions, trader activity, and comparison views.

## Background

The PoC already has two Grafana dashboards that provide excellent starting points:

* `latency_dashboard.json`: Autopilot, driver, and solver latency metrics
* `main_dashboard.json`: API throughput, orders, database, and RPC metrics

We'll adapt these dashboards for performance testing context and add new performance-testing-specific panels.

## Deliverables

### 1. Dashboard Infrastructure Setup

**Subtasks:**

- [ ] Review existing dashboards: `latency_dashboard.json` and `main_dashboard.json`
- [ ] Adapt dashboard provisioning for performance testing suite
- [ ] Create `grafana/provisioning/` directory structure
- [ ] Set up datasource configuration for Prometheus
- [ ] Configure dashboard auto-loading
- [ ] Document dashboard organization

### 2. Adapt Existing CoW Protocol Dashboards

**Leverage existing dashboards as foundation:**

**From** `latency_dashboard.json` - Keep and adapt:

- [ ] Auction overhead panels (autopilot, driver preprocessing)
- [ ] Runloop timing heatmaps
- [ ] Driver settle time heatmaps
- [ ] Solver compute time heatmaps
- [ ] Current block delay tracking
- [ ] **Adaptation**: Add performance test context (test scenario label, trader count)

**From** `main_dashboard.json` - Keep and adapt:

- [ ] API throughput and response times
- [ ] API response status codes
- [ ] Orders in auction tracking
- [ ] Database query performance
- [ ] RPC call metrics
- [ ] **Adaptation**: Filter by performance test run ID

**Subtasks:**

- [ ] Copy existing dashboard JSON files to `grafana/dashboards/`
- [ ] Add test run ID and scenario filters to all panels
- [ ] Update panel queries to include performance test labels
- [ ] Test existing panels with performance test metrics

### 3. New Performance Testing Dashboard

Create a dedicated dashboard for performance test overview:

**Overview Row:**

- [ ] Stat panel: Current test scenario
- [ ] Stat panel: Test duration (elapsed/total)
- [ ] Stat panel: Active traders count
- [ ] Stat panel: Target vs actual submission rate

**Summary Stats Row:**

- [ ] Stat panel: Total orders submitted (with sparkline)
- [ ] Stat panel: Total orders filled (with sparkline)
- [ ] Stat panel: Success rate percentage (color-coded: green >95%, yellow >90%, red <90%)
- [ ] Stat panel: Current throughput (orders/second)

**Order Submission Row:**

- [ ] Time series: Orders submitted per second (actual vs target)
- [ ] Time series: Cumulative orders over time
- [ ] Time series: Orders by status (created, submitted, accepted, filled)
- [ ] Gauge: Submission rate achievement (actual/target × 100%)

**Order Lifecycle Row (leveraging existing patterns):**

- [ ] Heatmap: Submission latency distribution (based on existing heatmap style)
- [ ] Heatmap: Orderbook acceptance latency
- [ ] Heatmap: Settlement latency (adapt from driver settle time panel)
- [ ] Time series: P50, P90, P95, P99 latencies over time

**Order Status Row:**

- [ ] Pie chart: Order status distribution (filled, expired, cancelled, failed, active)
- [ ] Time series: Order status over time (stacked area chart)
- [ ] Stat panel: Failed orders count
- [ ] Table: Top error messages

**Trader Activity Row:**

- [ ] Time series: Active traders over time
- [ ] Stat panel: Orders per trader (average)
- [ ] Bar chart: Top traders by volume
- [ ] Heatmap: Trader activity over time

### 4. API Performance Dashboard

Extend the existing API panels with performance test context:

**API Response Times Row (extend main_dashboard):**

- [ ] Adapt existing "API Response Time" panel with test filters
- [ ] Adapt existing "Api Responses 95th Percentile" panel
- [ ] Add per-endpoint breakdown specific to order submission
- [ ] Add heatmap for request duration distribution

**API Throughput Row (extend main_dashboard):**

- [ ] Adapt existing "API throughput" panel
- [ ] Adapt existing "API Requests" panel
- [ ] Add performance test specific request rate tracking
- [ ] Add concurrent request counter

**API Errors Row (extend main_dashboard):**

- [ ] Adapt existing "API Response Status" panel
- [ ] Adapt existing "API 500 Response Status" panel
- [ ] Add error rate time series
- [ ] Add error type breakdown table

### 5. Resource Utilization Dashboard

**CPU Usage Row:**

- [ ] Time series: CPU usage per container (orderbook, autopilot, driver, solver, anvil)
- [ ] Gauge: Current CPU usage per service
- [ ] Stat panel: Peak CPU usage during test

**Memory Usage Row:**

- [ ] Time series: Memory usage per container
- [ ] Gauge: Current memory percentage per service
- [ ] Stat panel: Peak memory usage
- [ ] Warning: Memory approaching limits

**Network I/O Row:**

- [ ] Time series: Network bytes sent/received per container
- [ ] Stat panel: Total network I/O
- [ ] Time series: Network throughput rate

**Container Health Row:**

- [ ] Stat panels: Container status (running/stopped/error)
- [ ] Time series: Container restarts
- [ ] Table: Container resource limits

### 6. Comparison Dashboard

**Comparison Overview Row:**

- [ ] Stat panel: Baseline name
- [ ] Stat panel: Overall verdict (improvement/regression/neutral)
- [ ] Stat panel: Number of regressions detected
- [ ] Stat panel: Regression severity (critical/major/minor)

**Latency Comparison Row:**

- [ ] Bar gauge: Submission latency (baseline vs current, with delta %)
- [ ] Bar gauge: Settlement latency (baseline vs current, with delta %)
- [ ] Time series: Latency comparison over time
- [ ] Stat panels: Percentage changes

**Throughput Comparison Row:**

- [ ] Bar gauge: Orders per second (baseline vs current)
- [ ] Stat panel: Throughput delta (absolute and percentage)
- [ ] Time series: Throughput trend comparison

**Regression Details Row:**

- [ ] Table: List of detected regressions with severity and metrics
- [ ] Stat panels: Count by severity (critical, major, minor)
- [ ] Heatmap: Regression distribution over time

### 7. Dashboard Variables (extend existing)

Existing variables to keep and adapt:

- [ ] `network` variable (from latency_dashboard)
- [ ] `datasource` variable (from both dashboards)
- [ ] `driver` variable (from latency_dashboard)
- [ ] `db_operation` variable (from main_dashboard)

New variables for performance testing:

- [ ] `test_run_id` - Filter by specific test run
- [ ] `scenario` - Filter by test scenario name
- [ ] `trader_address` - Filter by specific trader (optional)
- [ ] `baseline_id` - Select baseline for comparison

### 8. Dashboard Organization

**Subtasks:**

- [ ] Create dashboard folder structure:

  ```
  grafana/dashboards/
  ├── cow-protocol/              # Adapted from PoC
  │   ├── latency-dashboard.json
  │   └── main-dashboard.json
  └── performance-testing/       # New dashboards
      ├── overview.json
      ├── api-performance.json
      ├── resources.json
      ├── comparison.json
      └── trader-activity.json
  ```
- [ ] Configure dashboard provisioning
- [ ] Set up dashboard links for easy navigation
- [ ] Create dashboard tags for organization

### 9. Dashboard Documentation

**Subtasks:**

- [ ] Document each dashboard's purpose
- [ ] Explain key panels and what to look for
- [ ] Provide screenshots
- [ ] Create troubleshooting section
- [ ] Document variable usage

## Implementation Details

### Adapted Dashboard Example

```json
{
  "dashboard": {
    "title": "CoW Performance Testing - Overview",
    "tags": ["cow-protocol", "performance-testing"],
    "templating": {
      "list": [
        {
          "name": "test_run_id",
          "type": "query",
          "datasource": "Prometheus",
          "query": "label_values(cow_perf_orders_created_total, test_run_id)",
          "refresh": 1
        },
        {
          "name": "scenario",
          "type": "query",
          "datasource": "Prometheus",
          "query": "label_values(cow_perf_orders_created_total{test_run_id=\"$test_run_id\"}, scenario)",
          "refresh": 1
        }
      ]
    },
    "panels": [
      {
        "title": "Orders Per Second",
        "type": "timeseries",
        "targets": [
          {
            "expr": "rate(cow_perf_orders_submitted_total{test_run_id=\"$test_run_id\",scenario=\"$scenario\"}[1m])",
            "legendFormat": "Actual Rate"
          },
          {
            "expr": "cow_perf_target_rate{test_run_id=\"$test_run_id\",scenario=\"$scenario\"}",
            "legendFormat": "Target Rate"
          }
        ]
      }
    ]
  }
}
```

### Leveraging Existing Heatmap Panels

Adapt the existing heatmap pattern from `latency_dashboard.json`:

```json
{
  "title": "Order Submission Latency",
  "type": "heatmap",
  "datasource": "Prometheus",
  "targets": [
    {
      "expr": "sum(rate(cow_perf_submission_latency_seconds_bucket{scenario=\"$scenario\"}[$__rate_interval])) by (le)",
      "format": "heatmap"
    }
  ],
  "options": {
    "calculate": false,
    "color": {
      "scheme": "Oranges",
      "exponent": 0.5
    },
    "yAxis": {
      "unit": "s"
    }
  }
}
```

## Acceptance Criteria

- [ ] Existing CoW Protocol dashboards adapted for performance testing
- [ ] New performance testing overview dashboard created
- [ ] All dashboard variables working correctly
- [ ] Panels display data from performance tests
- [ ] Heatmaps show latency distributions
- [ ] Comparison dashboard shows baseline deltas
- [ ] Resource monitoring panels track all containers
- [ ] Dashboard navigation (links) working
- [ ] Dashboards auto-load on Grafana startup
- [ ] Dashboard documentation complete
- [ ] Screenshots captured for docs

## Testing Requirements

### Manual Testing

* Start fork mode environment
* Run performance test
* Verify all dashboards display data correctly
* Test all dashboard variables
* Verify heatmaps render correctly
* Test comparison view with baseline
* Check panel interactions (zoom, legend, tooltips)

### Integration Testing

* Automated test that verifies dashboards load
* Verify all Prometheus queries return data
* Test dashboard provisioning

## Technical Notes

* Reuse existing dashboard patterns from PoC (especially heatmaps)
* Maintain consistent color schemes with existing dashboards
* Follow Grafana best practices from existing dashboards
* Use existing panel configurations as templates
* Keep test-specific metrics clearly labeled
* Add `test_run_id` label to all performance test metrics
* Use dashboard variables for filtering
* Consider dashboard performance with many panels
* Test with different time ranges

## Existing Dashboard Insights

**From latency_dashboard.json:**

* Excellent heatmap usage for latency distribution
* Good use of variables for filtering (network, driver, stages)
* Organized by sections (Autopilot, Driver, Solver)
* Focuses on timing and overhead metrics

**From main_dashboard.json:**

* Comprehensive API monitoring
* Good database performance tracking
* Excellent RPC and external API monitoring
* Rich set of operational metrics

**Adaptation Strategy:**

* Keep all relevant CoW Protocol metrics
* Add performance test context (test_run_id, scenario, etc.)
* Add new panels for trader activity and test progress
* Maintain existing dashboard quality and patterns

## Directory Structure

```
grafana/
├── provisioning/
│   ├── datasources/
│   │   └── prometheus.yml
│   └── dashboards/
│       ├── dashboards.yml
│       └── performance-testing.yml
└── dashboards/
    ├── cow-protocol/              # From PoC, adapted
    │   ├── latency-metrics.json   # Based on latency_dashboard.json
    │   └── system-metrics.json    # Based on main_dashboard.json
    └── performance-testing/       # New dashboards
        ├── overview.json
        ├── api-performance.json
        ├── resources.json
        ├── comparison.json
        └── trader-activity.json
```

## Related Issues

* Depends on: m3-issue-11-prometheus-exporters
* Related: m1-issue-02-fork-mode-environment-setup (Grafana configured in docker-compose)
* Related: m5-issue-19-comprehensive-documentation (dashboard usage guide)
* Related: Existing PoC dashboards in `/playground/performance-test-suite/`

---

## Planning Notes (M3 Planning — 2026-02-05)

### Current State Analysis

**What already exists:**

1. **Grafana service configured** (`docker-compose.yml`):
   - Grafana on port 3000 with `profile: monitoring`
   - Datasource provisioning: `configs/grafana-datasource.yml` (points to Prometheus)
   - Dashboard provisioning: `configs/grafana-dashboard.yml` (configured but **no dashboards exist**)

2. **No dashboard JSON files** - The `configs/` directory has provisioning config but no actual dashboard files.

3. **PoC dashboards don't exist locally** - The ticket references `latency_dashboard.json` and `main_dashboard.json` from CoW Protocol's monitoring. These are **external references** for design inspiration, not files to copy.

### Adjustments & Clarifications

1. **PoC Reference Available**: The PoC dashboards ARE available as a reference via **PR #17 on bleu/cowprotocol-services**. The PR adds ~4k lines, so direct file reads aren't practical. Use targeted searches:
   - Search for metric names (e.g., `cow_perf_`, `gp_v2_autopilot_runloop`, `driver_auction_preprocessing`)
   - Search for panel types (heatmap, timeseries, stat)
   - Reference dashboard patterns (heatmap color schemes, bucket configurations)

   **Access strategy**: See [thoughts/research/poc-evaluation.md](../research/poc-evaluation.md) for complete PoC analysis (metrics, dashboards, architecture). For additional reference patterns, see [thoughts/tasks/COW-593-poc-reference.md](../tasks/COW-593-poc-reference.md).

2. **Full dashboard scope maintained**: All dashboards listed in this ticket are grant deliverables:
   - Performance Testing Overview
   - API Performance
   - Resource Utilization
   - Comparison Dashboard
   - Trader Activity

   **Implementation split** (for manageable delivery):
   - **Task 1 (COW-593)**: Essential dashboards (~2 points) — Overview, API Performance
   - **Task 2 (local)**: Remaining dashboards (~3 points) — Resources, Comparison, Trader Activity

   See `thoughts/tasks/COW-593-remaining-dashboards.md` for Task 2 details.

3. **Directory structure** (maintains original plan):
   ```
   configs/
   ├── grafana-datasource.yml     # exists
   ├── grafana-dashboard.yml      # exists, update path
   └── dashboards/
       ├── performance-overview.json   # Task 1
       ├── api-performance.json        # Task 1
       ├── resources.json              # Task 2
       ├── comparison.json             # Task 2
       └── trader-activity.json        # Task 2
   ```

4. **Variable strategy**:
   - `test_run_id` - Essential for filtering
   - `scenario` - Essential for filtering
   - `baseline_id` - For comparison dashboard
   - Keep others as needed per dashboard

5. **Dashboard panel structure** (per original ticket specification):

   **Overview Dashboard** (Task 1):
   - Row 1: Test overview stats (scenario, duration, traders, verdict)
   - Row 2: Order submission rate (time series + gauge)
   - Row 3: Latency heatmaps (submission, settlement)
   - Row 4: Order status (pie chart, success rate)

   **API Performance Dashboard** (Task 1):
   - Adapt patterns from PoC's API monitoring panels
   - Response times, throughput, error rates by endpoint

   **Resources, Comparison, Trader Activity** (Task 2):
   - See `thoughts/tasks/COW-593-remaining-dashboards.md`

### Dependencies

- **Requires COW-591 complete**: Dashboard queries depend on Prometheus metrics being exposed
- **Grafana provisioning**: Update `configs/grafana-dashboard.yml` to point to `configs/dashboards/`

### Recommended Implementation Order

1. Create `configs/dashboards/` directory
2. Update `configs/grafana-dashboard.yml` provisioning path
3. Create `configs/dashboards/performance-testing.json` with core panels
4. Test with `docker compose --profile monitoring up -d`
5. Iterate on panel queries and layout
6. Add documentation screenshots to `docs/`

### Acceptance Criteria (Full Scope, Split Delivery)

**Task 1 — COW-593 (this ticket, ~2 points)**:
- [ ] Performance Overview dashboard functional
- [ ] API Performance dashboard functional
- [ ] Order submission rate visualization
- [ ] Latency distribution visualization (heatmap)
- [ ] Test metadata display (scenario, duration, traders)
- [ ] Dashboard variables working (test_run_id, scenario)
- [ ] Dashboards auto-load on Grafana startup
- [ ] Dashboard loads correctly with Prometheus datasource

**Task 2 — `thoughts/tasks/COW-593-remaining-dashboards.md` (~3 points)**:
- [ ] Resources dashboard (CPU, memory, network per container)
- [ ] Comparison dashboard (baseline vs current, regression indicators)
- [ ] Trader Activity dashboard (per-trader stats, activity heatmap)
- [ ] Dashboard links and navigation between dashboards
- [ ] Complete documentation with screenshots

**Note**: Both tasks must be completed for full COW-593 delivery. Task 2 is tracked locally and should be completed immediately after Task 1.

### Human Actions Required

- After COW-591 and COW-593 are implemented, manual testing is required:
  1. Start monitoring stack: `docker compose --profile monitoring up -d`
  2. Run a performance test with Prometheus exporter enabled
  3. Open Grafana at http://localhost:3000
  4. Verify dashboard displays data correctly
  5. Take screenshots for documentation
