# Scenario Configuration Reference

> Complete reference for all scenario configuration fields

**Last Updated:** 2026-03-11
**Schema Version:** 1.0

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

Scenario configuration files use YAML format and define all parameters for a performance test. All scenarios must include certain required fields, while others are optional.

### Minimal Configuration

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

### File Structure

```yaml
# Basic information
name: <string>
description: <string>
version: <string>
tags: [<string>, ...]

# Metadata (optional)
metadata:
  expected_orders: <int>
  expected_duration_seconds: <int>
  resources:
    min_memory_gb: <float>
    min_cpu_cores: <int>
    recommended_memory_gb: <float>
    recommended_cpu_cores: <int>

# Success criteria (optional)
success_criteria:
  min_success_rate: <float>
  max_p95_latency_seconds: <float>
  max_error_rate: <float>
  min_throughput_per_second: <float>

# Trader configuration
num_traders: <int>
duration: <int>
startup_interval: <float>

# Order type distribution
market_order_ratio: <float>
limit_order_ratio: <float>
twap_order_ratio: <float>
stop_loss_order_ratio: <float>
good_after_time_order_ratio: <float>

# Trading pattern
trading_pattern: <string>
base_rate: <float>

# Pattern-specific parameters (conditional)
burst_size: <int>
burst_interval: <float>
quiet_period: <float>
min_interval: <float>
max_interval: <float>
```

---

## Basic Fields

### `name` (Required)

**Type:** String
**Description:** Human-readable name for the scenario

**Guidelines:**
- Use descriptive names following conventions
- Format: `<type>-<characteristic>-<variant>`
- Examples: `smoke-basic-10traders`, `load-sustained-30min`

**Example:**
```yaml
name: "load-sustained-production-sim"
```

---

### `description` (Optional)

**Type:** String
**Default:** `""`
**Description:** Detailed description of the scenario's purpose

**Guidelines:**
- Explain what the scenario tests
- Include expected outcomes or goals
- Keep under 200 characters for display purposes

**Example:**
```yaml
description: "Production load simulation with 50 concurrent traders over 30 minutes to validate system stability"
```

---

### `version` (Optional)

**Type:** String
**Default:** `"1.0"`
**Description:** Scenario version for tracking changes

**Guidelines:**
- Use semantic versioning: `MAJOR.MINOR.PATCH`
- Increment when scenario parameters change significantly
- Useful for baseline comparisons

**Example:**
```yaml
version: "2.1"
```

---

### `tags` (Optional)

**Type:** List of strings
**Default:** `[]`
**Description:** Tags for categorizing and filtering scenarios

**Guidelines:**
- Use lowercase
- Use hyphens not underscores: `high-load` not `high_load`
- Common tags: `smoke`, `load`, `stress`, `regression`, `short`, `long`

**Example:**
```yaml
tags:
  - regression
  - ci
  - short
  - smoke
```

---

## Trader Configuration

### `num_traders` (Optional)

**Type:** Integer
**Default:** `10`
**Constraints:** ≥ 1
**Description:** Number of concurrent traders to simulate

**Guidelines:**
- Smoke tests: 5-10
- Standard load: 10-20
- Stress tests: 50-100+
- Consider available memory: ~50-100MB per trader

**Example:**
```yaml
num_traders: 20
```

---

### `duration` (Optional)

**Type:** Integer (seconds)
**Default:** `60`
**Constraints:** ≥ 1
**Description:** Total test duration in seconds

**Guidelines:**
- Minimum: 60s (allows for startup + steady state)
- Smoke: 60-120s
- Load: 300-900s (5-15 min)
- Stress: 900-1800s (15-30 min)
- Soak: 3600s+ (1+ hour)

**Example:**
```yaml
duration: 300  # 5 minutes
```

---

### `startup_interval` (Optional)

**Type:** Float (seconds)
**Default:** `0.1`
**Constraints:** ≥ 0.0
**Description:** Interval between starting each trader

**Guidelines:**
- Default (0.1s): Fast startup, suitable for most tests
- Increase (0.5-1.0s): Slower startup, reduces initial spike
- Use higher values if experiencing startup issues

**Example:**
```yaml
startup_interval: 0.5  # Slower, more gradual startup
```

---

## Order Type Distribution

All five ratios must sum to **exactly 1.0**. Each ratio represents the probability that a randomly generated order will be of that type.

### `market_order_ratio` (Optional)

**Type:** Float
**Default:** `0.4`
**Constraints:** 0.0 ≤ value ≤ 1.0
**Description:** Proportion of market orders

**Characteristics:**
- Simplest order type
- Immediate execution
- Highest throughput

**Example:**
```yaml
market_order_ratio: 0.6  # 60% market orders
```

---

### `limit_order_ratio` (Optional)

**Type:** Float
**Default:** `0.4`
**Constraints:** 0.0 ≤ value ≤ 1.0
**Description:** Proportion of limit orders

**Characteristics:**
- Order book participation
- Price-specific execution
- Moderate complexity

**Example:**
```yaml
limit_order_ratio: 0.3  # 30% limit orders
```

---

### `twap_order_ratio` (Optional)

**Type:** Float
**Default:** `0.1`
**Constraints:** 0.0 ≤ value ≤ 1.0
**Description:** Proportion of TWAP (Time-Weighted Average Price) orders

**Characteristics:**
- Conditional order type
- Scheduled execution
- Higher complexity

**Example:**
```yaml
twap_order_ratio: 0.1  # 10% TWAP orders
```

---

### `stop_loss_order_ratio` (Optional)

**Type:** Float
**Default:** `0.05`
**Constraints:** 0.0 ≤ value ≤ 1.0
**Description:** Proportion of stop-loss orders

**Characteristics:**
- Conditional order type
- Trigger-based execution
- Higher complexity

**Example:**
```yaml
stop_loss_order_ratio: 0.0  # No stop-loss orders
```

---

### `good_after_time_order_ratio` (Optional)

**Type:** Float
**Default:** `0.05`
**Constraints:** 0.0 ≤ value ≤ 1.0
**Description:** Proportion of good-after-time orders

**Characteristics:**
- Conditional order type
- Time-delayed execution
- Higher complexity

**Example:**
```yaml
good_after_time_order_ratio: 0.0  # No good-after-time orders
```

---

### Order Ratio Validation

**Rule:** All five ratios must sum to exactly 1.0 (within 0.001 tolerance for floating-point precision).

**Common Distributions:**

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

The trading pattern determines how traders submit orders over time.

### `trading_pattern` (Optional)

**Type:** String
**Default:** `"constant_rate"`
**Allowed Values:** `"constant_rate"`, `"burst"`, `"random_interval"`
**Description:** Pattern for order submission timing

**Example:**
```yaml
trading_pattern: "constant_rate"
```

---

### Constant Rate Pattern

Submit orders at a steady, predictable rate.

**Required Fields:**
- `base_rate`

**Optional Fields:** None

**Configuration:**
```yaml
trading_pattern: "constant_rate"
base_rate: 60.0  # 60 orders per minute per trader
```

**Use Cases:**
- Baseline testing
- Sustained load tests
- Predictable throughput validation

---

### `base_rate` (Required for constant_rate)

**Type:** Float
**Default:** `60.0`
**Constraints:** > 0.0
**Description:** Base trading rate in orders per minute per trader

**Guidelines:**
- Conservative: 30.0 (0.5 orders/sec per trader)
- Moderate: 60.0 (1 order/sec per trader)
- Aggressive: 300.0 (5 orders/sec per trader)

**Total System Load:**
```
total_orders_per_min = num_traders × base_rate
Example: 10 traders × 60 orders/min = 600 orders/min system-wide
```

**Example:**
```yaml
base_rate: 120.0  # 2 orders/sec per trader
```

---

### Burst Pattern

Submit orders in rapid bursts with quiet periods between.

**Required Fields:**
- `base_rate` (used as baseline between bursts)
- `burst_size`
- `burst_interval`
- `quiet_period`

**Configuration:**
```yaml
trading_pattern: "burst"
base_rate: 10.0       # Baseline rate between bursts
burst_size: 10        # Orders per burst
burst_interval: 0.1   # 0.1s between orders in burst
quiet_period: 5.0     # 5s between bursts
```

**Use Cases:**
- Spike testing
- Resilience validation
- Cache behavior testing

---

### `burst_size` (Required for burst pattern)

**Type:** Integer
**Default:** None
**Constraints:** ≥ 1
**Description:** Number of orders per burst

**Example:**
```yaml
burst_size: 20  # 20 orders per burst
```

---

### `burst_interval` (Required for burst pattern)

**Type:** Float (seconds)
**Default:** None
**Constraints:** > 0.0
**Description:** Time interval between orders within a burst

**Example:**
```yaml
burst_interval: 0.05  # 50ms between orders (very rapid)
```

---

### `quiet_period` (Required for burst pattern)

**Type:** Float (seconds)
**Default:** None
**Constraints:** > 0.0
**Description:** Quiet period between bursts

**Example:**
```yaml
quiet_period: 10.0  # 10s rest between bursts
```

---

### Random Interval Pattern

Submit orders at random intervals within a range.

**Required Fields:**
- `min_interval`
- `max_interval`

**Configuration:**
```yaml
trading_pattern: "random_interval"
min_interval: 0.5  # Minimum 0.5s between orders
max_interval: 3.0  # Maximum 3s between orders
```

**Use Cases:**
- Realistic user behavior simulation
- Variable load testing
- Unpredictable traffic patterns

---

### `min_interval` (Required for random_interval)

**Type:** Float (seconds)
**Default:** None
**Constraints:** ≥ 0.0
**Description:** Minimum interval between orders

**Example:**
```yaml
min_interval: 1.0  # At least 1s between orders
```

---

### `max_interval` (Required for random_interval)

**Type:** Float (seconds)
**Default:** None
**Constraints:** > 0.0, must be > `min_interval`
**Description:** Maximum interval between orders

**Example:**
```yaml
max_interval: 5.0  # At most 5s between orders
```

---

## Success Criteria

Optional automated validation thresholds for test results.

### `success_criteria` (Optional)

**Type:** Object
**Default:** None
**Description:** Criteria for automated pass/fail validation

**When to Use:**
- ✅ Regression tests (CI/CD gates)
- ✅ Production readiness validation
- ✅ SLA verification
- ❌ Exploratory testing
- ❌ Capacity finding

**Example:**
```yaml
success_criteria:
  min_success_rate: 0.95
  max_p95_latency_seconds: 10.0
  max_error_rate: 0.05
  min_throughput_per_second: 5.0
```

---

### `min_success_rate` (Optional)

**Type:** Float
**Default:** None
**Constraints:** 0.0 ≤ value ≤ 1.0
**Description:** Minimum required order success rate

**Guidelines:**
- Production SLA: 0.99+ (99%+)
- Standard testing: 0.95 (95%)
- Stress testing: 0.85-0.90 (85-90%)

**Example:**
```yaml
success_criteria:
  min_success_rate: 0.99  # Require 99% success
```

---

### `max_p95_latency_seconds` (Optional)

**Type:** Float (seconds)
**Default:** None
**Constraints:** > 0.0
**Description:** Maximum allowed 95th percentile latency

**Guidelines:**
- Interactive workloads: <2s
- Background processing: <10s
- Batch operations: <30s

**Example:**
```yaml
success_criteria:
  max_p95_latency_seconds: 5.0  # P95 must be under 5s
```

---

### `max_error_rate` (Optional)

**Type:** Float
**Default:** None
**Constraints:** 0.0 ≤ value ≤ 1.0
**Description:** Maximum allowed error rate

**Note:** Typically set as inverse of `min_success_rate`: `1.0 - min_success_rate`

**Example:**
```yaml
success_criteria:
  max_error_rate: 0.01  # Allow up to 1% errors
```

---

### `min_throughput_per_second` (Optional)

**Type:** Float
**Default:** None
**Constraints:** ≥ 0.0
**Description:** Minimum required throughput in orders per second

**Guidelines:**
- Based on business requirements
- Account for concurrent traders
- Consider system capacity

**Example:**
```yaml
success_criteria:
  min_throughput_per_second: 10.0  # At least 10 orders/sec
```

---

## Metadata

Optional metadata about expected outcomes and resource requirements.

### `metadata` (Optional)

**Type:** Object
**Default:** None
**Description:** Scenario metadata for documentation and resource planning

**Example:**
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

### `expected_orders` (Optional)

**Type:** Integer
**Default:** None
**Constraints:** ≥ 0
**Description:** Expected number of orders for planning purposes

**Calculation:**
```
expected_orders ≈ num_traders × (base_rate / 60) × duration
Example: 10 traders × (60/60) orders/sec × 60s = 600 orders
```

**Example:**
```yaml
metadata:
  expected_orders: 600
```

---

### `expected_duration_seconds` (Optional)

**Type:** Integer
**Default:** None
**Constraints:** ≥ 1
**Description:** Expected test duration (typically matches `duration`)

**Example:**
```yaml
metadata:
  expected_duration_seconds: 300
```

---

### `resources` (Optional)

**Type:** Object
**Default:** None
**Description:** Resource requirements for running the scenario

**Fields:**
- `min_memory_gb` (Float): Minimum memory in GB
- `min_cpu_cores` (Integer): Minimum CPU cores
- `recommended_memory_gb` (Float): Recommended memory in GB
- `recommended_cpu_cores` (Integer): Recommended CPU cores

**Example:**
```yaml
metadata:
  resources:
    min_memory_gb: 4.0
    min_cpu_cores: 2
    recommended_memory_gb: 8.0
    recommended_cpu_cores: 4
```

---

## Template Fields

When using templates, include these fields instead of full configuration.

### `template` (Template Mode)

**Type:** String
**Description:** Name of the template to use

**Available Templates:**
- `ramp-up` - Gradual load increase
- `spike` - Sudden load burst
- `sustained-load` - Constant load over time

**Example:**
```yaml
template: ramp-up
```

---

### `parameters` (Template Mode)

**Type:** Object
**Description:** Parameters to pass to the template

**Parameters vary by template.** See template documentation:

```bash
cow-perf scenarios --list-templates
```

**Example:**
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
# Basic information
name: "production-validation-smoke-test"
description: "Quick validation of production deployment with realistic load"
version: "2.0"
tags:
  - production
  - validation
  - smoke
  - short

# Metadata
metadata:
  expected_orders: 1200
  expected_duration_seconds: 120
  resources:
    min_memory_gb: 4.0
    min_cpu_cores: 2
    recommended_memory_gb: 8.0
    recommended_cpu_cores: 4

# Success criteria
success_criteria:
  min_success_rate: 0.99
  max_p95_latency_seconds: 5.0
  max_error_rate: 0.01
  min_throughput_per_second: 10.0

# Trader configuration
num_traders: 10
duration: 120
startup_interval: 0.1

# Order type distribution (sums to 1.0)
market_order_ratio: 0.5
limit_order_ratio: 0.4
twap_order_ratio: 0.1
stop_loss_order_ratio: 0.0
good_after_time_order_ratio: 0.0

# Trading pattern: constant rate
trading_pattern: "constant_rate"
base_rate: 60.0  # 1 order/sec per trader = 10 orders/sec total
```

---

## Validation

Validate your configuration before running:

```bash
# Validate syntax and schema
cow-perf scenarios --validate my-scenario.yml

# See all validation errors
cow-perf scenarios --validate my-scenario.yml --verbose
```

**Common Validation Errors:**

1. **Order ratios don't sum to 1.0**
   ```
   Error: Order ratios sum to 0.9, must equal 1.0
   ```

2. **Invalid trading pattern**
   ```
   Error: Trading pattern must be one of: constant_rate, burst, random_interval
   ```

3. **Missing required pattern parameters**
   ```
   Error: burst pattern requires burst_size, burst_interval, quiet_period
   ```

4. **Success criteria out of range**
   ```
   Error: min_success_rate must be between 0.0 and 1.0
   ```

---

## See Also

- [Best Practices Guide](scenario-best-practices.md) - Guidelines for effective scenarios
- [CLI Reference](cli.md) - Complete command documentation
- [Architecture](architecture.md) - System design and components

---

**Schema Version:** 1.0
**Last Updated:** 2026-03-11
