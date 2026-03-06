# COW-593 Task 2: Remaining Dashboards

> **Purpose**: Track the remaining dashboards for COW-593 that will be implemented after the essential dashboards (Task 1).
>
> **Created**: 2026-02-05 (M3 Planning Revision)
> **Parent Ticket**: [COW-593-grafana-dashboards.md](../tickets/COW-593-grafana-dashboards.md)
> **Depends on**: COW-593 Task 1 (Overview + API Performance dashboards)
> **Estimate**: ~3 points
> **PoC Analysis**: [poc-evaluation.md](../research/poc-evaluation.md) — Dashboard panel types and Grafana provisioning patterns

---

## Summary

This task covers the remaining dashboards from COW-593 that are not included in Task 1:

1. **Resource Utilization Dashboard** — Container CPU, memory, network monitoring
2. **Comparison Dashboard** — Baseline vs current test comparison
3. **Trader Activity Dashboard** — Per-trader statistics and activity patterns

All three dashboards are grant deliverables and must be completed for COW-593 to be considered done.

---

## 1. Resource Utilization Dashboard

**File**: `configs/dashboards/resources.json`

### Required Panels

#### CPU Usage Row
- [ ] Time series: CPU usage per container (orderbook, autopilot, driver, solver, anvil)
  - Query: `cow_perf_container_cpu_percent{container=~"$container"}`
- [ ] Gauge: Current CPU usage per service
- [ ] Stat panel: Peak CPU usage during test
  - Query: `max_over_time(cow_perf_container_cpu_percent[1h])`

#### Memory Usage Row
- [ ] Time series: Memory usage per container
  - Query: `cow_perf_container_memory_bytes{container=~"$container"}`
- [ ] Gauge: Current memory percentage per service
- [ ] Stat panel: Peak memory usage
- [ ] Alert annotation: Memory approaching limits (>80%)

#### Network I/O Row
- [ ] Time series: Network bytes sent/received per container
  - Query: `rate(cow_perf_container_network_rx_bytes[1m])`, `rate(cow_perf_container_network_tx_bytes[1m])`
- [ ] Stat panel: Total network I/O
- [ ] Time series: Network throughput rate

#### Container Health Row
- [ ] Stat panels: Container status (running/stopped/error)
- [ ] Time series: Container restarts (if available)
- [ ] Table: Container resource limits

### Variables
- `container` - Multi-select for container filtering

---

## 2. Comparison Dashboard

**File**: `configs/dashboards/comparison.json`

### Required Panels

#### Comparison Overview Row
- [ ] Stat panel: Baseline name
  - Query: `cow_perf_test_info{baseline_id=~".+"}`
- [ ] Stat panel: Overall verdict (improvement/regression/neutral)
  - Color-coded: green=improvement, yellow=neutral, red=regression
- [ ] Stat panel: Number of regressions detected
  - Query: `sum(cow_perf_regression_detected)`
- [ ] Stat panel: Regression severity (critical/major/minor)

#### Latency Comparison Row
- [ ] Bar gauge: Submission latency (baseline vs current, with delta %)
  - Query comparison between baseline and current test_run_id
- [ ] Bar gauge: Settlement latency (baseline vs current, with delta %)
- [ ] Time series: Latency comparison over time
- [ ] Stat panels: Percentage changes per metric

#### Throughput Comparison Row
- [ ] Bar gauge: Orders per second (baseline vs current)
  - Query: `cow_perf_orders_per_second` for both runs
- [ ] Stat panel: Throughput delta (absolute and percentage)
  - Query: `cow_perf_baseline_comparison_percent{metric="throughput"}`
- [ ] Time series: Throughput trend comparison

#### Regression Details Row
- [ ] Table: List of detected regressions with severity and metrics
  - Columns: Metric, Baseline Value, Current Value, Change %, Severity
- [ ] Stat panels: Count by severity (critical, major, minor)
  - Query: `sum(cow_perf_regression_detected{severity="critical"})`

### Variables
- `test_run_id` - Current test run
- `baseline_id` - Baseline to compare against

### Implementation Note
This dashboard requires baseline comparison metrics from COW-591 Phase 2:
- `cow_perf_baseline_comparison_percent`
- `cow_perf_regression_detected`
- `cow_perf_regressions_total`

If those metrics aren't available, the comparison dashboard can show "No baseline data" placeholder.

---

## 3. Trader Activity Dashboard

**File**: `configs/dashboards/trader-activity.json`

### Required Panels

#### Trader Overview Row
- [ ] Stat panel: Total active traders
  - Query: `cow_perf_traders_active`
- [ ] Stat panel: Average orders per trader
  - Query: `sum(cow_perf_orders_submitted_total) / cow_perf_num_traders`
- [ ] Time series: Active traders over time
  - Query: `cow_perf_traders_active`

#### Top Traders Row
- [ ] Bar chart: Top 10 traders by orders submitted
  - Query: `topk(10, cow_perf_trader_orders_submitted)`
- [ ] Bar chart: Top 10 traders by orders filled
  - Query: `topk(10, cow_perf_trader_orders_filled)`
- [ ] Table: Trader success rates
  - Columns: Trader Address, Submitted, Filled, Success Rate %

#### Trader Activity Patterns Row
- [ ] Heatmap: Trader activity over time
  - Query: `sum(rate(cow_perf_trader_orders_submitted[1m])) by (trader_address)`
  - May need to limit to top N traders for readability
- [ ] Time series: Orders by trader over time (top 5)

#### Trader Distribution Row
- [ ] Pie chart: Distribution of orders across traders
- [ ] Histogram: Orders per trader distribution

### Variables
- `trader_address` - Optional filter for specific trader
- `top_n` - Number of top traders to show (default: 10)

### Implementation Note
This dashboard requires per-trader metrics from COW-591 Phase 2:
- `cow_perf_trader_orders_submitted{trader_address}`
- `cow_perf_trader_orders_filled{trader_address}`
- `cow_perf_traders_active`

Cardinality management is important - see COW-591 implementation phases for strategies.

---

## 4. Dashboard Navigation

After all dashboards are created, add navigation links:

- [ ] Add dashboard links in each dashboard header
- [ ] Create consistent navigation pattern:
  - Overview → API → Resources → Comparison → Traders
- [ ] Add "Back to Overview" link in all secondary dashboards

---

## Acceptance Criteria

- [ ] Resources dashboard shows CPU, memory, network for all containers
- [ ] Comparison dashboard shows baseline vs current with clear indicators
- [ ] Trader Activity dashboard shows per-trader statistics
- [ ] All dashboards have working variables
- [ ] Dashboard navigation links work
- [ ] Documentation includes screenshots of each dashboard
- [ ] All panels render without errors when metrics are available

---

## Implementation Order

1. **Resources Dashboard** — Depends only on COW-591 Phase 2 resource metrics
2. **Trader Activity Dashboard** — Depends only on COW-591 Phase 2 per-trader metrics
3. **Comparison Dashboard** — Depends on COW-591 Phase 2 baseline metrics
4. **Dashboard Navigation** — After all dashboards exist

---

## Files to Create

```
configs/dashboards/
├── resources.json           # NEW (this task)
├── comparison.json          # NEW (this task)
└── trader-activity.json     # NEW (this task)
```

---

## Notes

- This task should be started immediately after COW-593 Task 1 is complete
- All three dashboards are grant deliverables — not optional
- The split into Task 1 and Task 2 is for manageable delivery, not scope reduction
- If COW-591 Phase 2 metrics aren't available, dashboards should show appropriate placeholders
