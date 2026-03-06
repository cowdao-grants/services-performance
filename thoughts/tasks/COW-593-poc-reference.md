# COW-593: PoC Reference Guide

> **Purpose**: Document how to extract dashboard patterns and metrics from the PoC for COW-593 implementation.
>
> **Created**: 2026-02-05 (M3 Planning Revision)
> **Parent Ticket**: [COW-593-grafana-dashboards.md](../tickets/COW-593-grafana-dashboards.md)
> **PoC Analysis**: [poc-evaluation.md](../research/poc-evaluation.md) — Complete evaluation of PoC including metrics, dashboards, and architecture

---

## Quick Reference

For detailed PoC analysis (already completed), see **[poc-evaluation.md](../research/poc-evaluation.md)**, which covers:
- All Prometheus metrics exposed by the PoC
- Grafana provisioning structure
- Architecture and Docker integration
- Patterns to adopt in our implementation
- Key differences between K6 and our Python approach

---

## PoC Location

**PR #17** on `bleu/cowprotocol-services`: [https://github.com/bleu/cowprotocol-services/pull/17](https://github.com/bleu/cowprotocol-services/pull/17)

- Title: "Luizhatem/poc performance testing suite"
- Additions: ~4,834 lines
- Files: 83

**Key paths in the PR**:
```
playground/performance-test-suite/
├── grafana/provisioning/
│   ├── dashboards/dashboard.yml
│   └── datasources/datasource.yml
├── prometheus/prometheus.yml
├── src/
│   ├── load-test.ts
│   ├── order-generator.ts
│   └── scenarios.ts
└── README.md
```

---

## How to Access PoC Content

### Option A: Clone the Branch Locally

```bash
# Clone the repo with the PoC branch
git clone --single-branch --branch Luizhatem/poc-performance-testing-suite \
    https://github.com/bleu/cowprotocol-services.git /tmp/cow-poc

# Navigate to performance test suite
cd /tmp/cow-poc/playground/performance-test-suite
```

### Option B: Use GitHub API for Targeted Searches

```bash
# Get specific file content
gh api repos/bleu/cowprotocol-services/contents/playground/performance-test-suite/prometheus/prometheus.yml \
    --jq '.content' | base64 -d

# Search for patterns in PR files
gh api repos/bleu/cowprotocol-services/pulls/17/files \
    --jq '.[] | select(.filename | test("grafana")) | .patch'
```

### Option C: Run a Search Agent

Use Claude Code's Task tool with the `Explore` subagent to search the PoC repo for specific patterns.

---

## Metrics Referenced in Ticket

The ticket mentions these dashboards from CoW Protocol monitoring:

### `latency_dashboard.json` Metrics
These metrics are from CoW Protocol's autopilot/driver/solver services:

| Metric Pattern | Description | Use in Our Dashboard |
|----------------|-------------|----------------------|
| `*auction_overhead_time` | Auction processing overhead | Adapt for order processing latency |
| `*auction_overhead_count` | Auction overhead counter | Reference for counter patterns |
| `gp_v2_autopilot_runloop_*` | Autopilot runloop timing | Panel layout inspiration |
| `driver_auction_preprocessing_*` | Driver preprocessing | Heatmap pattern reference |
| `driver_remaining_solve_time_*` | Solver time remaining | Gauge pattern reference |

### `main_dashboard.json` Metrics
From CoW Protocol's API/orderbook services:

| Metric Pattern | Description | Use in Our Dashboard |
|----------------|-------------|----------------------|
| API throughput | Requests per second | `cow_perf_api_requests_total` rate |
| API response times | Latency distribution | `cow_perf_api_response_time_seconds` histogram |
| API status codes | Response status breakdown | `cow_perf_api_requests_total{status}` |
| Orders in auction | Active orders | `cow_perf_orders_active` |
| Database queries | DB performance | Reference only (not in our scope) |
| RPC metrics | External calls | Reference only (not in our scope) |

---

## PoC Prometheus Configuration

From the PR's `prometheus/prometheus.yml`:

```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s
  external_labels:
    cluster: 'cow-protocol-perf-test'
    environment: 'local'

scrape_configs:
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']

  - job_name: 'k6'
    static_configs:
      - targets: ['k6:6565']
    scrape_interval: 5s

  # CoW Protocol Services (commented out, available if needed)
  # - job_name: 'orderbook' -> targets: ['orderbook:8080']
  # - job_name: 'autopilot' -> targets: ['autopilot:9589']
  # - job_name: 'driver' -> targets: ['driver:9590']
```

**Key takeaways**:
- PoC uses K6 for load testing (we use Python)
- 5s scrape interval for K6 metrics (good for real-time)
- 15s default interval (we can use 5-10s for performance testing)

---

## Dashboard Design Patterns to Adopt

Based on CoW Protocol's existing dashboards:

### Heatmap Configuration
```json
{
  "type": "heatmap",
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

### Time Series with Target Line
```json
{
  "type": "timeseries",
  "targets": [
    {
      "expr": "rate(cow_perf_orders_submitted_total[1m])",
      "legendFormat": "Actual Rate"
    },
    {
      "expr": "cow_perf_target_rate",
      "legendFormat": "Target Rate"
    }
  ],
  "fieldConfig": {
    "defaults": {
      "custom": {
        "lineStyle": {
          "fill": "solid"
        }
      }
    }
  }
}
```

### Stat Panel with Color Thresholds
```json
{
  "type": "stat",
  "options": {
    "colorMode": "value",
    "graphMode": "area"
  },
  "fieldConfig": {
    "defaults": {
      "thresholds": {
        "mode": "absolute",
        "steps": [
          {"color": "green", "value": null},
          {"color": "yellow", "value": 90},
          {"color": "red", "value": 95}
        ]
      }
    }
  }
}
```

---

## Recommended Search Queries

When exploring the PoC for specific patterns:

```bash
# Find all metric names used
gh api repos/bleu/cowprotocol-services/pulls/17/files --jq '.[] | .patch' | grep -oE '[a-z_]+_total|[a-z_]+_seconds|[a-z_]+_bytes'

# Find Grafana panel types
gh api repos/bleu/cowprotocol-services/pulls/17/files --jq '.[] | select(.filename | test("grafana")) | .patch' | grep -oE '"type":\s*"[^"]+"'

# Find histogram bucket configurations
gh api repos/bleu/cowprotocol-services/pulls/17/files --jq '.[] | .patch' | grep -i bucket
```

---

## Notes

- The PoC is TypeScript/K6-based; our implementation is Python-based
- Dashboard JSON patterns are portable regardless of the test framework
- Focus on panel layouts, color schemes, and query patterns from the PoC
- Our `cow_perf_*` metrics will have similar semantics but different names
