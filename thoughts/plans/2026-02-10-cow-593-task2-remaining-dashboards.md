# COW-593 Task 2: Remaining Dashboards Implementation Plan

## Overview

Implement the three remaining dashboards for COW-593 that complete the Grafana visualization suite:

1. **Resource Utilization Dashboard** (`resources.json`) — Container CPU, memory, network monitoring
2. **Comparison Dashboard** (`comparison.json`) — Baseline vs current test comparison with regression indicators
3. **Trader Activity Dashboard** (`trader-activity.json`) — Per-trader statistics and activity patterns

All three dashboards are grant deliverables required for COW-593 completion.

## Current State Analysis

### What Exists

1. **Two dashboards already implemented** (Task 1):
   - `configs/dashboards/performance.json` — Overview dashboard with 20 panels
   - `configs/dashboards/api-performance.json` — API Performance dashboard with 14 panels

2. **Dashboard provisioning configured**:
   - `configs/grafana-dashboard.yml` — Points to `configs/dashboards/`
   - `configs/grafana-datasource.yml` — Prometheus datasource configured

3. **All required metrics available** (COW-591 Phase 2 complete):
   - Resource metrics: `cow_perf_container_cpu_percent`, `cow_perf_container_memory_bytes`, `cow_perf_container_network_rx_bytes`, `cow_perf_container_network_tx_bytes`
   - Comparison metrics: `cow_perf_baseline_comparison_percent`, `cow_perf_regression_detected`, `cow_perf_regressions_total`
   - Trader metrics: `cow_perf_trader_orders_submitted`, `cow_perf_trader_orders_filled`, `cow_perf_traders_active`

### Key Discoveries

- **Trader metrics use `trader_index`** (0, 1, 2...) not `trader_address` for cardinality management (`metrics.py:227-249`)
- **Comparison metrics are "push" metrics** — populated explicitly via `record_comparison_result()` after a comparison runs
- **Existing dashboards use consistent patterns**: `schemaVersion: 38`, `pluginVersion: "10.0.0"`, `refresh: "5s"`, tags `["cow-protocol", "performance-testing"]`
- **Variable pattern**: `{scenario=~\"$scenario\"}` regex match for filtering
- **Panel IDs**: Start at 1 per dashboard (not global), use sequential numbering
- **Navigation links**: API dashboard has link back to Overview using URL `/d/cow-perf-overview`

## Desired End State

After this plan is complete:

1. Three new dashboard JSON files exist in `configs/dashboards/`:
   - `resources.json` — Resource Utilization Dashboard
   - `comparison.json` — Comparison Dashboard
   - `trader-activity.json` — Trader Activity Dashboard

2. All dashboards:
   - Follow existing panel patterns and conventions
   - Have working variables for filtering
   - Include navigation links to other dashboards
   - Auto-load when Grafana starts with the monitoring profile

3. Dashboard navigation is complete:
   - All 5 dashboards link to each other
   - Existing dashboards (performance.json, api-performance.json) updated with full navigation

### Verification

- All dashboards load without errors in Grafana
- Panels display data when metrics are available
- Variables filter data correctly
- Navigation links work between all dashboards

## What We're NOT Doing

- **Not implementing alerting** — That's COW-598
- **Not modifying Prometheus exporter** — Metrics already exist
- **Not adding new metrics** — Using existing COW-591 Phase 2 metrics
- **Not changing provisioning configuration** — Already set up for `configs/dashboards/`
- **Not creating documentation** — Will be done after all dashboards are tested

---

## Implementation Approach

**Strategy**: Create each dashboard following the exact patterns from existing dashboards (`performance.json`, `api-performance.json`), ensuring:
- Consistent JSON structure
- Proper gridPos layout (24-unit grid width)
- Standard panel configurations
- Working variable queries

**Order**:
1. Resources Dashboard (simplest, clearest metric mapping)
2. Trader Activity Dashboard (moderate complexity, per-trader breakdown)
3. Comparison Dashboard (most complex, requires baseline selection)
4. Navigation Links Update (cross-dashboard navigation)

---

## Phase 1: Resource Utilization Dashboard

### Overview

Create `configs/dashboards/resources.json` with CPU, memory, and network monitoring for all containers.

### Dashboard Metadata

```json
{
  "title": "CoW Performance Testing - Resources",
  "uid": "cow-perf-resources",
  "tags": ["cow-protocol", "performance-testing", "resources"],
  "refresh": "5s",
  "schemaVersion": 38
}
```

### Variables

| Name | Label | Query | Multi |
|------|-------|-------|-------|
| `scenario` | Scenario | `label_values(cow_perf_orders_created_total, scenario)` | false |
| `container` | Container | `label_values(cow_perf_container_cpu_percent, container)` | true |

### Panel Layout

**Row 1: CPU Usage (y: 0)**

| Panel | Type | GridPos | Query |
|-------|------|---------|-------|
| Row: CPU Usage | row | h:1, w:24, x:0, y:0 | - |
| CPU by Container | timeseries | h:8, w:12, x:0, y:1 | `cow_perf_container_cpu_percent{container=~"$container"}` |
| Current CPU | gauge | h:8, w:6, x:12, y:1 | `cow_perf_container_cpu_percent{container=~"$container"}` (per container) |
| Peak CPU | stat | h:4, w:6, x:18, y:1 | `max_over_time(cow_perf_container_cpu_percent{container=~"$container"}[1h])` |
| Avg CPU | stat | h:4, w:6, x:18, y:5 | `avg_over_time(cow_perf_container_cpu_percent{container=~"$container"}[$__range])` |

**Row 2: Memory Usage (y: 9)**

| Panel | Type | GridPos | Query |
|-------|------|---------|-------|
| Row: Memory Usage | row | h:1, w:24, x:0, y:9 | - |
| Memory by Container | timeseries | h:8, w:12, x:0, y:10 | `cow_perf_container_memory_bytes{container=~"$container"}` |
| Current Memory | gauge | h:8, w:6, x:12, y:10 | `cow_perf_container_memory_bytes{container=~"$container"}` (per container) |
| Peak Memory | stat | h:4, w:6, x:18, y:10 | `max_over_time(cow_perf_container_memory_bytes{container=~"$container"}[1h])` |
| Avg Memory | stat | h:4, w:6, x:18, y:14 | `avg_over_time(cow_perf_container_memory_bytes{container=~"$container"}[$__range])` |

**Row 3: Network I/O (y: 18)**

| Panel | Type | GridPos | Query |
|-------|------|---------|-------|
| Row: Network I/O | row | h:1, w:24, x:0, y:18 | - |
| Network RX | timeseries | h:8, w:12, x:0, y:19 | `rate(cow_perf_container_network_rx_bytes{container=~"$container"}[1m])` |
| Network TX | timeseries | h:8, w:12, x:12, y:19 | `rate(cow_perf_container_network_tx_bytes{container=~"$container"}[1m])` |

**Row 4: Resource Summary (y: 27)**

| Panel | Type | GridPos | Query |
|-------|------|---------|-------|
| Row: Summary | row | h:1, w:24, x:0, y:27 | - |
| Total RX | stat | h:4, w:6, x:0, y:28 | `sum(cow_perf_container_network_rx_bytes{container=~"$container"})` |
| Total TX | stat | h:4, w:6, x:6, y:28 | `sum(cow_perf_container_network_tx_bytes{container=~"$container"})` |
| Resource Table | table | h:8, w:12, x:12, y:28 | All metrics by container |

### Key Panel Configurations

**CPU Timeseries**:
```json
{
  "fieldConfig": {
    "defaults": {
      "unit": "percent",
      "max": 100,
      "min": 0
    }
  }
}
```

**Memory Timeseries**:
```json
{
  "fieldConfig": {
    "defaults": {
      "unit": "bytes"
    }
  }
}
```

**Network Rate**:
```json
{
  "fieldConfig": {
    "defaults": {
      "unit": "Bps"
    }
  }
}
```

**CPU/Memory Thresholds** (gauge panels):
```json
{
  "thresholds": {
    "mode": "percentage",
    "steps": [
      { "color": "green", "value": null },
      { "color": "yellow", "value": 70 },
      { "color": "red", "value": 90 }
    ]
  }
}
```

### Navigation Links

```json
{
  "links": [
    {
      "title": "Overview",
      "url": "/d/cow-perf-overview",
      "includeVars": true,
      "keepTime": true
    },
    {
      "title": "API Performance",
      "url": "/d/cow-perf-api",
      "includeVars": true,
      "keepTime": true
    }
  ]
}
```

### Success Criteria

#### Automated Verification

- [x] JSON is valid: `python -m json.tool configs/dashboards/resources.json`
- [x] Linting passes: `poetry run ruff check .`
- [x] File exists at correct path

#### Manual Verification

- [ ] Dashboard loads in Grafana at `/d/cow-perf-resources`
- [ ] Container variable populates with container names
- [ ] CPU, memory, network panels display data during a test run
- [ ] Gauge thresholds show correct colors
- [ ] Navigation links work

---

## Phase 2: Trader Activity Dashboard

### Overview

Create `configs/dashboards/trader-activity.json` with per-trader statistics and activity patterns.

### Dashboard Metadata

```json
{
  "title": "CoW Performance Testing - Trader Activity",
  "uid": "cow-perf-traders",
  "tags": ["cow-protocol", "performance-testing", "traders"],
  "refresh": "5s",
  "schemaVersion": 38
}
```

### Variables

| Name | Label | Query | Multi |
|------|-------|-------|-------|
| `scenario` | Scenario | `label_values(cow_perf_orders_created_total, scenario)` | false |
| `top_n` | Top N | Custom: 5, 10, 20, 50 | false |

### Panel Layout

**Row 1: Trader Overview (y: 0)**

| Panel | Type | GridPos | Query |
|-------|------|---------|-------|
| Row: Overview | row | h:1, w:24, x:0, y:0 | - |
| Active Traders | stat | h:4, w:6, x:0, y:1 | `cow_perf_traders_active` |
| Total Traders | stat | h:4, w:6, x:6, y:1 | `cow_perf_num_traders{scenario=~"$scenario"}` |
| Avg Orders/Trader | stat | h:4, w:6, x:12, y:1 | `sum(cow_perf_trader_orders_submitted) / cow_perf_num_traders{scenario=~"$scenario"}` |
| Fill Rate | stat | h:4, w:6, x:18, y:1 | `sum(cow_perf_trader_orders_filled) / sum(cow_perf_trader_orders_submitted) * 100` |

**Row 2: Top Traders (y: 5)**

| Panel | Type | GridPos | Query |
|-------|------|---------|-------|
| Row: Top Traders | row | h:1, w:24, x:0, y:5 | - |
| Orders Submitted (Bar) | timeseries (bars) | h:8, w:12, x:0, y:6 | `topk($top_n, cow_perf_trader_orders_submitted)` |
| Orders Filled (Bar) | timeseries (bars) | h:8, w:12, x:12, y:6 | `topk($top_n, cow_perf_trader_orders_filled)` |

**Row 3: Trader Activity Over Time (y: 14)**

| Panel | Type | GridPos | Query |
|-------|------|---------|-------|
| Row: Activity | row | h:1, w:24, x:0, y:14 | - |
| Active Traders Over Time | timeseries | h:8, w:12, x:0, y:15 | `cow_perf_traders_active` |
| Submission Rate by Trader | timeseries | h:8, w:12, x:12, y:15 | `topk($top_n, rate(cow_perf_trader_orders_submitted[1m]))` |

**Row 4: Trader Distribution (y: 23)**

| Panel | Type | GridPos | Query |
|-------|------|---------|-------|
| Row: Distribution | row | h:1, w:24, x:0, y:23 | - |
| Order Distribution | piechart | h:8, w:8, x:0, y:24 | `topk($top_n, cow_perf_trader_orders_submitted)` |
| Success Rate by Trader | table | h:8, w:16, x:8, y:24 | Submitted, Filled, Rate % by trader_index |

### Key Panel Configurations

**Bar Chart for Top Traders**:
```json
{
  "fieldConfig": {
    "defaults": {
      "custom": {
        "drawStyle": "bars",
        "fillOpacity": 80,
        "stacking": { "mode": "none" }
      }
    }
  }
}
```

**Top N Variable**:
```json
{
  "name": "top_n",
  "type": "custom",
  "query": "5,10,20,50",
  "current": { "text": "10", "value": "10" }
}
```

**Trader Table Transformations**:
```json
{
  "transformations": [
    {
      "id": "organize",
      "options": {
        "renameByName": {
          "trader_index": "Trader",
          "Value #A": "Submitted",
          "Value #B": "Filled",
          "Value #C": "Success %"
        }
      }
    }
  ]
}
```

### Navigation Links

Same pattern as Resources dashboard, linking to Overview, API, and Resources.

### Success Criteria

#### Automated Verification

- [x] JSON is valid: `python -m json.tool configs/dashboards/trader-activity.json`
- [x] File exists at correct path

#### Manual Verification

- [ ] Dashboard loads in Grafana at `/d/cow-perf-traders`
- [ ] Top N variable allows selection
- [ ] Bar charts show top traders correctly
- [ ] Trader table shows all columns
- [ ] Pie chart shows distribution

---

## Phase 3: Comparison Dashboard

### Overview

Create `configs/dashboards/comparison.json` for baseline vs current test comparison with regression indicators.

### Dashboard Metadata

```json
{
  "title": "CoW Performance Testing - Comparison",
  "uid": "cow-perf-comparison",
  "tags": ["cow-protocol", "performance-testing", "comparison"],
  "refresh": "5s",
  "schemaVersion": 38
}
```

### Variables

| Name | Label | Query | Multi |
|------|-------|-------|-------|
| `scenario` | Scenario | `label_values(cow_perf_orders_created_total, scenario)` | false |
| `baseline_id` | Baseline | `label_values(cow_perf_baseline_comparison_percent, baseline_id)` | false |

### Panel Layout

**Row 1: Comparison Overview (y: 0)**

| Panel | Type | GridPos | Query |
|-------|------|---------|-------|
| Row: Overview | row | h:1, w:24, x:0, y:0 | - |
| Baseline ID | stat | h:4, w:6, x:0, y:1 | `cow_perf_test_info{baseline_id=~".+"}` (extract baseline label) |
| Overall Verdict | stat | h:4, w:6, x:6, y:1 | Based on regression count (color-coded) |
| Total Regressions | stat | h:4, w:6, x:12, y:1 | `sum(cow_perf_regressions_total)` |
| Critical Count | stat | h:4, w:6, x:18, y:1 | `cow_perf_regression_detected{severity="critical"}` |

**Row 2: Latency Comparison (y: 5)**

| Panel | Type | GridPos | Query |
|-------|------|---------|-------|
| Row: Latency | row | h:1, w:24, x:0, y:5 | - |
| Submission Latency Delta | stat | h:4, w:6, x:0, y:6 | `cow_perf_baseline_comparison_percent{metric="submission_latency_p95"}` |
| Settlement Latency Delta | stat | h:4, w:6, x:6, y:6 | `cow_perf_baseline_comparison_percent{metric="settlement_latency_p95"}` |
| Comparison Over Time | timeseries | h:8, w:12, x:12, y:6 | Multiple `cow_perf_baseline_comparison_percent` by metric |

**Row 3: Throughput Comparison (y: 14)**

| Panel | Type | GridPos | Query |
|-------|------|---------|-------|
| Row: Throughput | row | h:1, w:24, x:0, y:14 | - |
| Orders/Second Delta | stat | h:4, w:6, x:0, y:15 | `cow_perf_baseline_comparison_percent{metric="orders_per_second"}` |
| Success Rate Delta | stat | h:4, w:6, x:6, y:15 | `cow_perf_baseline_comparison_percent{metric="success_rate"}` |
| Throughput Trend | timeseries | h:8, w:12, x:12, y:15 | Actual rate comparison |

**Row 4: Regression Details (y: 23)**

| Panel | Type | GridPos | Query |
|-------|------|---------|-------|
| Row: Regressions | row | h:1, w:24, x:0, y:23 | - |
| Critical Regressions | stat | h:4, w:4, x:0, y:24 | `cow_perf_regression_detected{severity="critical"}` |
| Major Regressions | stat | h:4, w:4, x:4, y:24 | `cow_perf_regression_detected{severity="major"}` |
| Minor Regressions | stat | h:4, w:4, x:8, y:24 | `cow_perf_regression_detected{severity="minor"}` |
| Regression Table | table | h:8, w:12, x:12, y:24 | All comparison metrics with deltas |

### Key Panel Configurations

**Delta Stat Panel** (positive = worse for latency):
```json
{
  "fieldConfig": {
    "defaults": {
      "unit": "percent",
      "thresholds": {
        "mode": "absolute",
        "steps": [
          { "color": "green", "value": null },
          { "color": "yellow", "value": 5 },
          { "color": "red", "value": 15 }
        ]
      }
    }
  },
  "options": {
    "graphMode": "none"
  }
}
```

**Delta Stat Panel** (positive = better for throughput):
```json
{
  "fieldConfig": {
    "defaults": {
      "unit": "percent",
      "thresholds": {
        "mode": "absolute",
        "steps": [
          { "color": "red", "value": null },
          { "color": "yellow", "value": -5 },
          { "color": "green", "value": 0 }
        ]
      }
    }
  }
}
```

**Regression Severity Colors**:
- Critical: `red`
- Major: `orange`
- Minor: `yellow`

**Value Mappings for Verdict**:
```json
{
  "mappings": [
    { "type": "value", "options": { "0": { "text": "No Regressions", "color": "green" } } },
    { "type": "range", "options": { "from": 1, "to": 5, "result": { "text": "Minor Issues", "color": "yellow" } } },
    { "type": "range", "options": { "from": 6, "to": 999, "result": { "text": "Regressions Detected", "color": "red" } } }
  ]
}
```

### Important Note

The comparison dashboard will only show data when a baseline comparison has been run via the CLI (`cow-perf compare`). When no comparison data exists, panels will show "No data" which is expected behavior.

### Success Criteria

#### Automated Verification

- [x] JSON is valid: `python -m json.tool configs/dashboards/comparison.json`
- [x] File exists at correct path

#### Manual Verification

- [ ] Dashboard loads in Grafana at `/d/cow-perf-comparison`
- [ ] Baseline variable populates after a comparison is run
- [ ] Delta panels show correct % change
- [ ] Color coding reflects regression severity
- [ ] Table shows all metrics with comparison data

---

## Phase 4: Dashboard Navigation Links

### Overview

Update all 5 dashboards to include consistent navigation links to each other.

### Link Configuration

Each dashboard should have links to all other dashboards:

```json
{
  "links": [
    {
      "asDropdown": false,
      "icon": "dashboard",
      "includeVars": true,
      "keepTime": true,
      "tags": [],
      "targetBlank": false,
      "title": "Overview",
      "tooltip": "Go to Overview Dashboard",
      "type": "link",
      "url": "/d/cow-perf-overview"
    },
    {
      "asDropdown": false,
      "icon": "dashboard",
      "includeVars": true,
      "keepTime": true,
      "tags": [],
      "targetBlank": false,
      "title": "API",
      "tooltip": "Go to API Performance Dashboard",
      "type": "link",
      "url": "/d/cow-perf-api"
    },
    {
      "asDropdown": false,
      "icon": "dashboard",
      "includeVars": true,
      "keepTime": true,
      "tags": [],
      "targetBlank": false,
      "title": "Resources",
      "tooltip": "Go to Resources Dashboard",
      "type": "link",
      "url": "/d/cow-perf-resources"
    },
    {
      "asDropdown": false,
      "icon": "dashboard",
      "includeVars": true,
      "keepTime": true,
      "tags": [],
      "targetBlank": false,
      "title": "Comparison",
      "tooltip": "Go to Comparison Dashboard",
      "type": "link",
      "url": "/d/cow-perf-comparison"
    },
    {
      "asDropdown": false,
      "icon": "dashboard",
      "includeVars": true,
      "keepTime": true,
      "tags": [],
      "targetBlank": false,
      "title": "Traders",
      "tooltip": "Go to Trader Activity Dashboard",
      "type": "link",
      "url": "/d/cow-perf-traders"
    }
  ]
}
```

### Files to Update

1. `configs/dashboards/performance.json` — Add full links array (currently empty)
2. `configs/dashboards/api-performance.json` — Update links array (currently only has Overview link)
3. `configs/dashboards/resources.json` — Include links on creation
4. `configs/dashboards/comparison.json` — Include links on creation
5. `configs/dashboards/trader-activity.json` — Include links on creation

### Success Criteria

#### Automated Verification

- [x] All 5 dashboard JSON files are valid
- [x] Each dashboard has 4 links (excluding self to avoid redundancy)

#### Manual Verification

- [ ] Navigation links appear in dashboard header
- [ ] Clicking links navigates to correct dashboard
- [ ] Variables are preserved across navigation
- [ ] Time range is preserved across navigation

---

## Testing Strategy

### Unit Tests

No unit tests needed — dashboards are JSON configuration files.

### Integration Tests

Dashboard JSON validation is covered by Grafana's provisioning system. If JSON is invalid, Grafana will fail to load.

### Manual Testing Steps

1. **Start the monitoring stack**:
   ```bash
   docker compose --profile monitoring up -d
   ```

2. **Run a performance test** (to generate metrics):
   ```bash
   poetry run cow-perf test --scenario medium_load --prometheus-port 9091
   ```

3. **Verify dashboards in Grafana** (http://localhost:3000):
   - Navigate to each dashboard
   - Verify panels show data
   - Test variable selection
   - Test navigation links

4. **Run a comparison** (for Comparison dashboard):
   ```bash
   poetry run cow-perf baseline save --name test-baseline
   poetry run cow-perf test --scenario medium_load
   poetry run cow-perf compare --baseline test-baseline
   ```
   - Verify Comparison dashboard shows delta values

5. **Take screenshots** for documentation (after manual verification passes)

---

## Files to Create/Modify

### New Files

```
configs/dashboards/
├── resources.json           # NEW (Phase 1)
├── comparison.json          # NEW (Phase 3)
└── trader-activity.json     # NEW (Phase 2)
```

### Modified Files

```
configs/dashboards/
├── performance.json         # UPDATE: Add navigation links (Phase 4)
└── api-performance.json     # UPDATE: Expand navigation links (Phase 4)

thoughts/
├── INDEX.md                 # UPDATE: Add this plan
└── tasks/COW-593-remaining-dashboards.md  # UPDATE: Mark items complete as implemented
```

---

## References

- Parent ticket: `thoughts/tickets/COW-593-grafana-dashboards.md`
- Task 2 specification: `thoughts/tasks/COW-593-remaining-dashboards.md`
- PoC patterns: `thoughts/research/poc-evaluation.md`
- Task 1 plan: `thoughts/plans/2026-02-06-cow-593-grafana-dashboards-task1.md`
- Existing dashboards: `configs/dashboards/performance.json`, `configs/dashboards/api-performance.json`
- Metrics implementation: `src/cow_performance/prometheus/metrics.py`
