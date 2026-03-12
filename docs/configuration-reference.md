# Scenario Configuration Reference

> Complete reference for all scenario configuration fields

**Schema Version:** 1.0 | **Last Updated:** 2026-03-11

## Table of Contents

- [Overview](#overview)
- [Basic Fields](#basic-fields)
- [Trader Configuration](#trader-configuration)
- [Order Type Distribution](#order-type-distribution)
- [Trading Patterns](#trading-patterns)
- [Success Criteria](#success-criteria)
- [Metadata](#metadata)
- [Template Fields](#template-fields)
- [Complete Example](#complete-example)

---

## Overview

Scenario configuration files use YAML format and define all parameters for a performance test.

**Minimal configuration:**
```yaml
name: "my-test"
num_traders: 10
duration: 60
trading_pattern: "constant_rate"
base_rate: 60.0

# Order ratios (must sum to 1.0)
market_order_ratio: 0.6
limit_order_ratio: 0.4
twap_order_ratio: 0.0
stop_loss_order_ratio: 0.0
good_after_time_order_ratio: 0.0
```

---

## Basic Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `name` | String | **Required** | Human-readable scenario name. Format: `<type>-<characteristic>-<variant>` (e.g. `smoke-basic-10traders`) |
| `description` | String | `""` | Scenario purpose. Keep under 200 characters |
| `version` | String | `"1.0"` | Semantic version for tracking changes. Increment when parameters change significantly |
| `tags` | List[String] | `[]` | Lowercase, hyphen-separated tags for filtering (e.g. `smoke`, `load`, `stress`, `regression`, `ci`) |

---

## Trader Configuration

| Field | Type | Default | Constraints | Description |
|-------|------|---------|-------------|-------------|
| `num_traders` | Integer | `10` | ≥ 1 | Concurrent traders to simulate. Smoke: 5–10, load: 10–20, stress: 50–100+. ~50–100 MB per trader |
| `duration` | Integer (s) | `60` | ≥ 1 | Test duration. Smoke: 60–120s, load: 300–900s, stress: 900–1800s, soak: 3600s+ |
| `startup_interval` | Float (s) | `0.1` | ≥ 0.0 | Delay between starting each trader. Increase to 0.5–1.0s to reduce initial spike |

---

## Order Type Distribution

All five ratios must sum to **exactly 1.0** (±0.001 tolerance). Each ratio is the probability a generated order will be of that type.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `market_order_ratio` | Float | `0.4` | Market orders — simplest type, immediate execution, highest throughput |
| `limit_order_ratio` | Float | `0.4` | Limit orders — price-specific execution, moderate complexity |
| `twap_order_ratio` | Float | `0.1` | TWAP orders — conditional, scheduled execution, higher complexity |
| `stop_loss_order_ratio` | Float | `0.05` | Stop-loss orders — conditional, trigger-based execution, higher complexity |
| `good_after_time_order_ratio` | Float | `0.05` | Good-after-time orders — conditional, time-delayed execution, higher complexity |

**Common distributions:**

```yaml
# Balanced (default)
market_order_ratio: 0.4
limit_order_ratio: 0.4
twap_order_ratio: 0.1
stop_loss_order_ratio: 0.05
good_after_time_order_ratio: 0.05

# High-throughput (simple orders only)
market_order_ratio: 0.7
limit_order_ratio: 0.3
twap_order_ratio: 0.0
stop_loss_order_ratio: 0.0
good_after_time_order_ratio: 0.0

# Conditional-heavy
market_order_ratio: 0.2
limit_order_ratio: 0.2
twap_order_ratio: 0.3
stop_loss_order_ratio: 0.2
good_after_time_order_ratio: 0.1
```

---

## Trading Patterns

The `trading_pattern` field (default: `"constant_rate"`) controls order submission timing. Each pattern requires specific additional fields.

### `constant_rate`

Steady, predictable order rate. Use for baseline and sustained load tests.

| Field | Type | Default | Constraints | Description |
|-------|------|---------|-------------|-------------|
| `base_rate` | Float | `60.0` | > 0.0 | Orders per minute per trader. Total load = `num_traders × base_rate` |

```yaml
trading_pattern: "constant_rate"
base_rate: 60.0  # 10 traders × 60 = 600 orders/min system-wide
```

Rate guidelines: conservative 30.0, moderate 60.0, aggressive 300.0 orders/min/trader.

### `burst`

Rapid bursts with quiet periods. Use for spike and resilience testing.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `base_rate` | Float | > 0.0 | Baseline rate between bursts |
| `burst_size` | Integer | ≥ 1 | Orders per burst |
| `burst_interval` | Float (s) | > 0.0 | Time between orders within a burst |
| `quiet_period` | Float (s) | > 0.0 | Rest period between bursts |

```yaml
trading_pattern: "burst"
base_rate: 10.0
burst_size: 10
burst_interval: 0.1
quiet_period: 5.0
```

### `random_interval`

Random intervals between orders. Use for realistic user behavior simulation.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `min_interval` | Float (s) | ≥ 0.0 | Minimum interval between orders |
| `max_interval` | Float (s) | > `min_interval` | Maximum interval between orders |

```yaml
trading_pattern: "random_interval"
min_interval: 0.5
max_interval: 3.0
```

---

## Success Criteria

Optional automated pass/fail thresholds. Use for regression/CI gates and SLA verification. Omit for exploratory or capacity-finding tests.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `min_success_rate` | Float | 0.0–1.0 | Minimum order success rate. Production: 0.99+, standard: 0.95, stress: 0.85–0.90 |
| `max_p95_latency_seconds` | Float | > 0.0 | Max P95 latency. Interactive: <2s, background: <10s, batch: <30s |
| `max_error_rate` | Float | 0.0–1.0 | Max error rate. Typically `1.0 - min_success_rate` |
| `min_throughput_per_second` | Float | ≥ 0.0 | Minimum orders/sec throughput |

```yaml
success_criteria:
  min_success_rate: 0.95
  max_p95_latency_seconds: 10.0
  max_error_rate: 0.05
  min_throughput_per_second: 5.0
```

---

## Metadata

Optional documentation and resource planning fields.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `expected_orders` | Integer | ≥ 0 | Expected order count. ≈ `num_traders × (base_rate/60) × duration` |
| `expected_duration_seconds` | Integer | ≥ 1 | Expected duration (typically matches `duration`) |
| `resources.min_memory_gb` | Float | — | Minimum memory in GB |
| `resources.min_cpu_cores` | Integer | — | Minimum CPU cores |
| `resources.recommended_memory_gb` | Float | — | Recommended memory in GB |
| `resources.recommended_cpu_cores` | Integer | — | Recommended CPU cores |

```yaml
metadata:
  expected_orders: 300
  expected_duration_seconds: 60
  resources:
    min_memory_gb: 2.0
    min_cpu_cores: 2
    recommended_memory_gb: 4.0
    recommended_cpu_cores: 4
```

---

## Template Fields

Use these fields instead of full configuration when basing a scenario on a built-in template.

| Field | Type | Description |
|-------|------|-------------|
| `template` | String | Template name: `ramp-up`, `spike`, or `sustained-load` |
| `parameters` | Object | Template-specific parameters (run `cow-perf scenarios --list-templates` to see all) |

```yaml
template: sustained-load
parameters:
  test_name: "My Sustained Test"
  num_traders: 15
  duration: 600
  orders_per_minute: 30.0
```

---

## Complete Example

```yaml
name: "production-validation-smoke-test"
description: "Quick validation of production deployment with realistic load"
version: "2.0"
tags:
  - production
  - validation
  - smoke
  - short

metadata:
  expected_orders: 1200
  expected_duration_seconds: 120
  resources:
    min_memory_gb: 4.0
    min_cpu_cores: 2
    recommended_memory_gb: 8.0
    recommended_cpu_cores: 4

success_criteria:
  min_success_rate: 0.99
  max_p95_latency_seconds: 5.0
  max_error_rate: 0.01
  min_throughput_per_second: 10.0

num_traders: 10
duration: 120
startup_interval: 0.1

market_order_ratio: 0.5
limit_order_ratio: 0.4
twap_order_ratio: 0.1
stop_loss_order_ratio: 0.0
good_after_time_order_ratio: 0.0

trading_pattern: "constant_rate"
base_rate: 60.0  # 1 order/sec per trader = 10 orders/sec total
```

---

## Validation

```bash
cow-perf scenarios --validate my-scenario.yml
cow-perf scenarios --validate my-scenario.yml --verbose
```

**Common errors:**

| Error | Cause |
|-------|-------|
| `Order ratios sum to 0.9, must equal 1.0` | Five order ratios don't sum to 1.0 |
| `Trading pattern must be one of: constant_rate, burst, random_interval` | Invalid `trading_pattern` value |
| `burst pattern requires burst_size, burst_interval, quiet_period` | Missing fields for selected pattern |
| `min_success_rate must be between 0.0 and 1.0` | Success criteria value out of range |

---

## See Also

- [Best Practices Guide](scenario-best-practices.md)
- [CLI Reference](cli.md)
- [Architecture](architecture.md)
