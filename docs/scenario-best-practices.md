# Scenario Best Practices Guide

> Guidelines for creating effective performance test scenarios

## Table of Contents

- [Choosing a Creation Method](#choosing-a-creation-method)
- [Scenario Naming Conventions](#scenario-naming-conventions)
- [Selecting the Right Template](#selecting-the-right-template)
- [Configuring Test Parameters](#configuring-test-parameters)
- [Order Type Distribution](#order-type-distribution)
- [Success Criteria Guidelines](#success-criteria-guidelines)
- [Tagging Strategies](#tagging-strategies)
- [Common Patterns](#common-patterns)
- [Troubleshooting](#troubleshooting)

---

## Choosing a Creation Method

The suite offers multiple ways to create scenarios. Choose based on your needs:

### Use Interactive Wizard (`config-init`) When:
- ✅ You're new to the tool
- ✅ You want guided configuration with validation
- ✅ You need to create a scenario quickly (<2 minutes)
- ✅ You're unsure about available options

```bash
cow-perf config-init --mode quick
```

### Use Templates When:
- ✅ You need a common test pattern (ramp-up, spike, sustained load)
- ✅ You want consistent test structure across scenarios
- ✅ You're testing standard performance characteristics

```yaml
template: ramp-up
parameters:
  num_traders: 10
  duration: 300
  target_rate: 100.0
```

### Use Manual YAML When:
- ✅ You need precise control over all parameters
- ✅ You're creating complex, custom test patterns
- ✅ You're familiar with the schema

### Copy Existing Scenarios When:
- ✅ You want to modify a predefined scenario slightly
- ✅ You're creating variants for comparison
- ✅ You need consistency with previous tests

---

## Scenario Naming Conventions

**General Format:** `<type>-<characteristic>-<variant>`

### Recommended Patterns:

**Test Type Prefixes:**
- `smoke-` - Quick validation tests (1-2 min)
- `load-` - Standard load tests (5-15 min)
- `stress-` - High-load stress tests (15-30 min)
- `soak-` - Long-duration stability tests (30+ min)
- `spike-` - Sudden load burst tests
- `regression-` - CI/CD regression tests

**Examples:**
```yaml
# Good
name: "smoke-basic-10traders"
name: "load-sustained-30min"
name: "stress-high-frequency-100traders"
name: "regression-quick-ci"

# Avoid
name: "test1"              # Not descriptive
name: "my_awesome_test"    # Informal
name: "LoadTestHighTraders123"  # Inconsistent casing
```

**File Naming:**
- Use kebab-case: `smoke-basic-10traders.yml`
- Match scenario name to filename when possible
- Group related scenarios in subdirectories

---

## Selecting the Right Template

### Ramp-Up Template

**Use When:**
- Finding system breaking points
- Testing auto-scaling behavior
- Identifying gradual degradation patterns
- Capacity planning

**Key Parameters:**
```yaml
template: ramp-up
parameters:
  num_traders: 10
  duration: 300        # 5 minutes
  start_rate: 5.0      # Start low
  target_rate: 100.0   # End high
```

**Best For:**
- Initial system assessment
- Gradual load increase testing
- Finding maximum sustainable load

### Spike Template

**Use When:**
- Testing resilience to sudden traffic bursts
- Validating auto-scaling responsiveness
- Testing cache warming behavior
- Simulating flash sales or events

**Key Parameters:**
```yaml
template: spike
parameters:
  num_traders: 20
  duration: 180
  normal_rate: 10.0    # Baseline
  spike_rate: 200.0    # Burst level
  spike_duration: 30   # How long the spike lasts
```

**Best For:**
- Resilience testing
- Auto-scaling validation
- Recovery time measurement

### Sustained-Load Template

**Use When:**
- Testing long-term stability
- Looking for memory leaks
- Validating resource management
- Baseline performance measurement

**Key Parameters:**
```yaml
template: sustained-load
parameters:
  num_traders: 15
  duration: 1800       # 30 minutes
  orders_per_minute: 60.0
```

**Best For:**
- Stability testing
- Memory leak detection
- Endurance testing
- Production load simulation

---

## Configuring Test Parameters

### Trader Count (`num_traders`)

**Guidelines:**

| Scenario Type | Trader Count | Rationale |
|--------------|--------------|-----------|
| Smoke test | 5-10 | Quick validation, low resource usage |
| Standard load | 10-20 | Realistic concurrent users |
| Stress test | 50-100+ | Push system limits |
| Regression | 5 | Fast CI/CD execution |

**Considerations:**
- More traders = more system load AND longer startup time
- Each trader maintains state (wallet, orders)
- Consider memory constraints on test machine

### Duration (`duration`)

**Guidelines:**

| Test Type | Duration | Purpose |
|-----------|----------|---------|
| Smoke | 60-120s | Quick validation |
| Load | 300-900s (5-15 min) | Standard performance |
| Stress | 900-1800s (15-30 min) | Extended high load |
| Soak | 3600s+ (1+ hour) | Stability/leaks |

**Rule of Thumb:**
- Minimum: 60s (allows for startup + steady state)
- CI/CD: Keep under 300s for fast feedback
- Production simulation: Match peak traffic periods

### Order Rate (`base_rate`, `orders_per_minute`)

**Starting Points:**

```yaml
# Conservative (safe starting point)
base_rate: 30.0  # 30 orders/min per trader

# Moderate (typical usage)
base_rate: 60.0  # 1 order/sec per trader

# Aggressive (stress testing)
base_rate: 300.0  # 5 orders/sec per trader
```

**Calculation:**
```
Total system load = num_traders × base_rate
Example: 10 traders × 60 orders/min = 600 orders/min system-wide
```

---

## Order Type Distribution

All ratios must sum to **exactly 1.0**.

### Recommended Distributions

**Balanced (realistic usage):**
```yaml
market_order_ratio: 0.4
limit_order_ratio: 0.4
twap_order_ratio: 0.1
stop_loss_order_ratio: 0.05
good_after_time_order_ratio: 0.05
```

**High-throughput (maximum load):**
```yaml
market_order_ratio: 0.7  # Market orders are fastest
limit_order_ratio: 0.3
twap_order_ratio: 0.0
stop_loss_order_ratio: 0.0
good_after_time_order_ratio: 0.0
```

**Conditional-heavy (complex orders):**
```yaml
market_order_ratio: 0.2
limit_order_ratio: 0.2
twap_order_ratio: 0.3
stop_loss_order_ratio: 0.2
good_after_time_order_ratio: 0.1
```

**Single-type (testing specific functionality):**
```yaml
# Limit orders only
market_order_ratio: 0.0
limit_order_ratio: 1.0
twap_order_ratio: 0.0
stop_loss_order_ratio: 0.0
good_after_time_order_ratio: 0.0
```

---

## Success Criteria Guidelines

### When to Use Success Criteria

**Always use for:**
- ✅ Regression tests (CI/CD gates)
- ✅ Production readiness validation
- ✅ SLA verification
- ✅ Automated pass/fail decisions

**Optional for:**
- Exploratory testing
- Capacity finding
- One-off investigations

### Recommended Thresholds

**Conservative (production-grade):**
```yaml
success_criteria:
  min_success_rate: 0.99        # 99% success
  max_error_rate: 0.01          # 1% errors
  max_p95_latency_seconds: 5.0  # 5s P95
  min_throughput_per_second: 10.0
```

**Moderate (development/staging):**
```yaml
success_criteria:
  min_success_rate: 0.95        # 95% success
  max_error_rate: 0.05          # 5% errors
  max_p95_latency_seconds: 10.0 # 10s P95
  min_throughput_per_second: 5.0
```

**Lenient (stress testing - expect some failures):**
```yaml
success_criteria:
  min_success_rate: 0.85        # 85% success
  max_error_rate: 0.15          # 15% errors
  max_p95_latency_seconds: 20.0 # 20s P95
```

### Criteria Selection Guide

**Success Rate:**
- Production SLA: 0.99+ (99%+)
- Standard testing: 0.95 (95%)
- Stress testing: 0.85-0.90 (85-90%)

**Error Rate:**
- Inverse of success rate: `1.0 - min_success_rate`
- Account for transient failures
- Consider retry logic in your application

**Latency (P95):**
- Interactive workloads: <2s
- Background processing: <10s
- Batch operations: <30s

**Throughput:**
- Set based on business requirements
- Consider: orders per second needed to meet SLA
- Account for concurrent traders

---

## Tagging Strategies

Tags help organize, filter, and search scenarios.

### Standard Tags

**Environment:**
- `dev`, `staging`, `production`
- `local`, `ci`

**Test Type:**
- `smoke`, `load`, `stress`, `soak`
- `regression`, `performance`, `capacity`

**Characteristics:**
- `short` (<5 min), `medium` (5-15 min), `long` (>15 min)
- `low-load`, `high-load`
- `edge-case`

**Purpose:**
- `baseline`, `comparison`
- `bug-reproduction`
- `feature-validation`

### Example Tag Sets

```yaml
# CI/CD regression test
tags:
  - regression
  - ci
  - short
  - smoke

# Production capacity test
tags:
  - production
  - capacity
  - stress
  - long

# Bug investigation
tags:
  - dev
  - bug-COW-123
  - edge-case
```

### Tag Naming Rules

1. Use lowercase
2. Use hyphens, not underscores: `high-load` not `high_load`
3. Be specific but concise
4. Use consistent vocabulary across scenarios

---

## Common Patterns

### Pattern 1: Progressive Load Testing

Run a series of tests with increasing load:

```bash
# Scenario 1: Baseline
cow-perf run --config load-baseline-10traders.yml --save-baseline baseline-10

# Scenario 2: Double the load
cow-perf run --config load-baseline-20traders.yml --save-baseline baseline-20

# Scenario 3: Quadruple the load
cow-perf run --config load-baseline-40traders.yml --save-baseline baseline-40

# Compare
cow-perf report compare baseline-10 baseline-40
```

### Pattern 2: Before/After Feature Comparison

```bash
# Before feature deployment
cow-perf run --config regression-suite.yml --save-baseline before-feature-x

# Deploy feature

# After feature deployment
cow-perf run --config regression-suite.yml --save-baseline after-feature-x

# Compare for regressions
cow-perf report compare before-feature-x after-feature-x
```

### Pattern 3: Multi-Environment Validation

```yaml
# production-simulation.yml
name: "Production Load Simulation"
tags: [production, validation]
num_traders: 50
duration: 1800  # 30 min

success_criteria:
  min_success_rate: 0.99
  max_p95_latency_seconds: 5.0
```

Run on staging, then production (with lower load):

```bash
# Staging (full load)
cow-perf run --config production-simulation.yml

# Production (10% sample)
cow-perf run --config production-simulation.yml --traders 5
```

### Pattern 4: Spike Recovery Testing

```yaml
# spike-recovery.yml
template: spike
parameters:
  num_traders: 30
  duration: 300
  normal_rate: 20.0
  spike_rate: 200.0
  spike_duration: 30

# Measure: How long until system returns to normal?
success_criteria:
  min_success_rate: 0.90  # Lenient during spike
  max_p95_latency_seconds: 15.0
```

---

## Troubleshooting

### Problem: Tests failing validation

**Symptoms:**
```
Error: Order ratios sum to 0.9, must equal 1.0
```

**Solution:**
```yaml
# Ensure ratios sum to exactly 1.0
market_order_ratio: 0.6
limit_order_ratio: 0.4
twap_order_ratio: 0.0       # Include all 5 types
stop_loss_order_ratio: 0.0
good_after_time_order_ratio: 0.0
```

### Problem: Scenario too slow

**Symptoms:**
- Long test duration
- High startup time
- Resource exhaustion

**Solutions:**

1. **Reduce trader count:**
   ```yaml
   num_traders: 5  # Down from 50
   ```

2. **Shorten duration:**
   ```yaml
   duration: 120  # Down from 1800
   ```

3. **Adjust startup interval:**
   ```yaml
   startup_interval: 0.5  # Slower startup (default: 0.1)
   ```

### Problem: Inconsistent results

**Symptoms:**
- Large variance between runs
- Success criteria sometimes pass, sometimes fail

**Solutions:**

1. **Increase test duration** (more samples):
   ```yaml
   duration: 300  # Up from 60
   ```

2. **Use consistent test environment**
3. **Check for external factors** (other processes, network)
4. **Run multiple iterations and compare baselines**

### Problem: Template not found

**Symptoms:**
```
Error: Template 'my-template' not found
```

**Solutions:**

1. **Check available templates:**
   ```bash
   cow-perf scenarios --list-templates
   ```

2. **Use correct template name:**
   ```yaml
   template: ramp-up  # Not: ramp_up or rampup
   ```

3. **Check template directories:**
   - Built-in: `configs/scenarios/templates/`
   - Custom: `~/.cow-perf/templates/`

### Problem: Success criteria too strict

**Symptoms:**
- Tests always fail
- Minor variations cause failure

**Solutions:**

1. **Run without criteria first** to establish baseline
2. **Use percentile-based thresholds** instead of absolutes
3. **Account for variance:**
   ```yaml
   success_criteria:
     min_success_rate: 0.95  # Not 0.99 for development
     max_p95_latency_seconds: 10.0  # Add buffer
   ```

---

## Quick Reference

### Configuration Checklist

Before running a scenario, verify:

- [ ] Scenario name is descriptive and follows conventions
- [ ] Tags are lowercase and use hyphens
- [ ] Order ratios sum to exactly 1.0
- [ ] Duration is appropriate for test type (≥60s)
- [ ] Trader count matches available resources
- [ ] Success criteria (if present) are realistic
- [ ] Template parameters are all provided (if using template)
- [ ] Trading pattern matches test goals

### Validation Commands

```bash
# Validate scenario file
cow-perf scenarios --validate my-scenario.yml

# List all scenarios with metadata
cow-perf scenarios

# List templates
cow-perf scenarios --list-templates

# Test scenario (dry run - no actual orders)
cow-perf run --config my-scenario.yml --dry-run
```

---

## Additional Resources

- [CLI Reference](cli.md) - Complete command documentation
- [Architecture](architecture.md) - System design and components
- [Development Guide](development.md) - Contributing and extending

---

**Last Updated:** 2026-03-11
