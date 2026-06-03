# Trading Patterns Guide

This document explains the different order submission patterns available in the CoW Performance Testing Suite. These patterns control the timing and rate of order submissions during tests.

**See also**: [Configuration Reference](configuration-reference.md#trading-patterns) for parameter details.

## Overview

The CoW Performance Testing Suite supports multiple order submission patterns to simulate realistic user behavior and test the orderbook under various load conditions. Each pattern serves specific testing purposes and mimics different real-world scenarios.

## Implementation

All patterns are implemented in `TraderSimulator`:
- Source: `src/cow_performance/load_generation/trader_simulator.py`
- Pattern enum: `TradingPattern` (StrEnum) — top of file
- Pattern logic: `_constant_rate_loop`, `_random_interval_loop`, `_burst_pattern_loop`, `_time_based_loop`, `_ramp_up_loop`, `_ramp_down_loop`, `_spike_loop`, `_poisson_loop`

## Available Patterns

### 1. CONSTANT_RATE

**Description:** Submits orders at a steady, predictable rate.

**Use Case:**
- Baseline performance testing
- Establishing consistent load
- Testing sustained throughput capacity
- Comparing performance across different configurations

**Configuration Example:**

```yaml
trading_pattern: "constant_rate"
base_rate: 30.0  # 30 orders per minute (0.5 orders/sec)
```

**Behavior:**
- Orders submitted at fixed intervals
- Interval = 60 seconds / base_rate
- Example: 30 orders/min = 1 order every 2 seconds
- Most predictable pattern for controlled testing

**When to Use:**
- Initial smoke tests
- Establishing baseline metrics
- Testing specific throughput levels
- Regression testing against previous baselines

---

### 2. RANDOM_INTERVAL

**Description:** Submits orders at random intervals within a configurable range.

**Use Case:**
- Simulating realistic human trading behavior
- Testing orderbook under unpredictable load
- Avoiding artificial patterns in submissions
- Load variance testing

**Configuration Example:**

```yaml
trading_pattern: "random_interval"
min_interval: 5.0   # Minimum 5 seconds between orders
max_interval: 30.0  # Maximum 30 seconds between orders
```

**Behavior:**
- Each order submission waits a random duration between min_interval and max_interval
- Uses uniform distribution (all intervals equally likely)
- Example: min=5s, max=30s → orders submitted every 5-30 seconds randomly
- Average rate: 1 / ((min_interval + max_interval) / 2)

**When to Use:**
- Testing real-world user behavior patterns
- Avoiding resonance with orderbook operations
- Load tests requiring natural variance
- Capacity finding with unpredictable load

**Pattern Selection Guidelines:**

| Interval Range | Orders/Minute (avg) | Use Case |
|----------------|---------------------|----------|
| 2-10s | 5-30 | High variance, aggressive testing |
| 5-30s | 2-12 | Moderate variance, realistic behavior |
| 10-60s | 1-6 | Low frequency, background trading |

**Complete Example:**

```yaml
name: "realistic-user-behavior"
description: "Simulates natural user trading with random intervals"

num_traders: 15
duration: 600  # 10 minutes

trading_pattern: "random_interval"
min_interval: 10.0
max_interval: 45.0  # Average ~27.5s = ~2.2 orders/min per trader

market_order_ratio: 0.6
limit_order_ratio: 0.4
```

**Implementation:** `trader_simulator.py`: `_random_interval_loop`

---

### 3. TIME_BASED

**Description:** Adjusts order submission rate based on time of day, with higher activity during configured hours.

**Use Case:**
- Simulating business hours trading patterns
- Testing daily load variations
- Capacity planning for peak hours
- Modeling real-world usage patterns with time zones

**Configuration Example:**

```yaml
trading_pattern: "time_based"
base_rate: 30.0           # Orders/minute during normal hours
active_hours: [9, 10, 11, 12, 13, 14, 15, 16]  # 9 AM - 4 PM (UTC)
active_multiplier: 2.0    # 2x rate during active hours
```

**Behavior:**
- During active_hours: interval = base_interval / active_multiplier (faster submissions)
- Outside active_hours: interval = base_interval (normal rate)
- Example: base_rate=30/min, multiplier=2.0 → 60 orders/min during active hours
- Uses local system time (time.localtime().tm_hour)

**When to Use:**
- Testing production-like daily patterns
- Capacity planning for peak trading hours
- Geographic time zone simulation
- Stress testing during business hours only

**Pattern Configuration Guidelines:**

| Scenario | Base Rate | Active Hours | Multiplier | Peak Load |
|----------|-----------|--------------|------------|-----------|
| Light load | 20/min | 8-16 (8 hours) | 2.0 | 40/min during peak |
| Moderate load | 40/min | 9-17 (8 hours) | 3.0 | 120/min during peak |
| Heavy load | 60/min | 10-14 (4 hours) | 5.0 | 300/min during peak |

**Complete Example:**

```yaml
name: "business-hours-simulation"
description: "Higher trading volume during market hours (UTC)"

num_traders: 20
duration: 86400  # 24 hours for full daily cycle

trading_pattern: "time_based"
base_rate: 20.0              # 20 orders/min baseline
active_hours: [13, 14, 15, 16, 17, 18, 19, 20]  # 1 PM - 8 PM UTC (US trading)
active_multiplier: 4.0       # 80 orders/min during US market hours

market_order_ratio: 0.7
limit_order_ratio: 0.3
```

**Important Notes:**
- Uses UTC/local system time - ensure test environment time zone is correct
- For 24-hour tests, consider multiple active hour ranges
- Active hours use 24-hour format (0-23)

**Implementation:** `trader_simulator.py`: `_time_based_loop`

---

### 4. BURST

**Description:** Submits rapid bursts of orders followed by quiet periods, creating cyclical load spikes.

**Use Case:**
- Testing resilience to sudden load spikes
- Simulating batch trading bots
- Queue backlog and recovery testing
- Finding breaking points under burst load

**Configuration Example:**

```yaml
trading_pattern: "burst"
base_rate: 10.0        # Not used (placeholder for compatibility)
burst_size: 10         # 10 orders per burst
burst_interval: 0.5    # 0.5 seconds between orders in burst
quiet_period: 30.0     # 30 seconds rest between bursts
```

**Behavior:**
- Submits burst_size orders with burst_interval seconds between each
- After completing burst, waits quiet_period seconds
- Then repeats: burst → quiet → burst → quiet
- Peak instantaneous load: 1 / burst_interval orders/second during burst
- Average load: burst_size / (burst_size * burst_interval + quiet_period)

**When to Use:**
- Resilience and recovery testing
- Simulating algorithmic trading bots
- Testing rate limiting and backpressure
- Queue overflow scenarios

**Pattern Configuration Guidelines:**

| Burst Type | burst_size | burst_interval | quiet_period | Peak Rate | Avg Rate |
|------------|-----------|----------------|--------------|-----------|----------|
| Gentle | 5 | 2.0s | 60.0s | 0.5/s | ~0.14/s |
| Moderate | 10 | 1.0s | 30.0s | 1.0/s | ~0.25/s |
| Aggressive | 20 | 0.5s | 20.0s | 2.0/s | ~0.67/s |
| Extreme | 50 | 0.1s | 10.0s | 10.0/s | ~3.3/s |

**Complete Example:**

```yaml
name: "burst-resilience-test"
description: "Tests recovery from sudden order bursts"

num_traders: 5
duration: 300  # 5 minutes

trading_pattern: "burst"
base_rate: 60.0        # Ignored for burst pattern
burst_size: 15         # 15 orders per burst
burst_interval: 0.2    # 5 orders/second during burst
quiet_period: 20.0     # 20 seconds between bursts

# Use simple orders for burst testing
market_order_ratio: 1.0
limit_order_ratio: 0.0

success_criteria:
  min_success_rate: 0.80  # Allow some failures during bursts
  max_p95_latency_seconds: 30.0
```

**Burst Calculation Example:**
```
burst_size: 15 orders
burst_interval: 0.2s
quiet_period: 20.0s

Time per cycle: (15 × 0.2s) + 20.0s = 3s + 20s = 23s
Orders per cycle: 15
Average rate: 15 / 23 ≈ 0.65 orders/second
Peak rate: 1 / 0.2 = 5 orders/second (during burst only)
```

**Implementation:** `trader_simulator.py`: `_burst_pattern_loop`

---

### 5. RAMP_UP

**Description:** Gradually increases submission rate from a low starting rate to a target rate.

**Use Case:**
- Load testing to find capacity limits
- Simulating gradual user growth
- Warming up the system before peak load
- Identifying performance degradation thresholds

**Configuration Example:**

```yaml
trading_pattern: "ramp_up"
ramp_start_rate: 6.0     # Start at 6 orders/min
ramp_target_rate: 60.0   # End at 60 orders/min
ramp_duration: 300.0     # Ramp over 5 minutes
ramp_curve: "linear"     # or "exponential"
```

**Behavior:**

**Linear Curve:**
- Rate increases steadily at constant pace
- Formula: `current_rate = start_rate + (target_rate - start_rate) * progress`
- Example: 6→60 orders/min over 5 minutes
  - At 0s: 6 orders/min
  - At 150s (50%): 33 orders/min
  - At 300s (100%): 60 orders/min

**Exponential Curve:**
- Rate increases slowly at first, then rapidly
- Formula: `current_rate = start_rate * (target_rate / start_rate) ^ progress`
- Good for finding breaking points quickly
- Example: 6→60 orders/min over 5 minutes
  - At 0s: 6 orders/min
  - At 150s (50%): ~15 orders/min
  - At 225s (75%): ~30 orders/min
  - At 300s (100%): 60 orders/min

**When to Use:**
- Capacity planning: "How much load can the system handle?"
- Finding performance cliffs: "At what load does latency spike?"
- Testing autoscaling behavior
- Simulating organic traffic growth

---

### 6. RAMP_DOWN

**Description:** Gradually decreases submission rate from a high rate to a lower rate.

**Use Case:**
- Testing cooldown behavior
- Observing system recovery after high load
- Testing resource cleanup
- Simulating peak hours ending

**Configuration Example:**

```yaml
trading_pattern: "ramp_down"
ramp_start_rate: 60.0    # Start at 60 orders/min
ramp_target_rate: 6.0    # End at 6 orders/min
ramp_duration: 300.0     # Ramp down over 5 minutes
ramp_curve: "exponential"
```

**Behavior:**
- Inverse of RAMP_UP
- Linear: steady decrease
- Exponential: rapid decrease early, then gradual
- After ramp_duration, maintains target_rate

**When to Use:**
- Testing graceful load reduction
- Observing cache behavior during cooldown
- Testing resource deallocation
- Measuring recovery time after stress

---

### 7. SPIKE

**Description:** Simulates sudden traffic spikes with recovery periods between bursts.

**Use Case:**
- Testing resilience to sudden load increases
- Simulating market events (news, price movements)
- Testing rate limiting effectiveness
- Observing burst handling and recovery

**Configuration Example:**

```yaml
trading_pattern: "spike"
spike_normal_rate: 10.0      # Normal: 10 orders/min
spike_burst_rate: 100.0      # Spike: 100 orders/min (10x!)
spike_duration: 15.0         # Each spike lasts 15 seconds
spike_recovery_time: 45.0    # 45 seconds between spikes
```

**Behavior:**
1. **Normal Period:** Submits at `spike_normal_rate` for `spike_recovery_time` seconds
2. **Burst Period:** Submits at `spike_burst_rate` for `spike_duration` seconds
3. **Repeat:** Cycles between normal and burst

**Example Timeline:**
```
0-45s:   Normal rate (10 orders/min)
45-60s:  Burst rate (100 orders/min)  <- SPIKE!
60-105s: Normal rate (10 orders/min)
105-120s: Burst rate (100 orders/min) <- SPIKE!
...
```

**When to Use:**
- Stress testing burst capacity
- Testing rate limiting under bursts
- Simulating market volatility events
- Testing system recovery between spikes

---

### 8. POISSON

**Description:** Submits orders following a Poisson distribution for statistically realistic random intervals.

**Use Case:**
- Most realistic simulation of real user behavior
- Production load estimation
- Capacity planning with realistic traffic
- Testing under natural traffic patterns

**Configuration Example:**

```yaml
trading_pattern: "poisson"
poisson_lambda: 30.0  # Average 30 orders per minute
```

**Behavior:**
- Intervals follow exponential distribution (Poisson process property)
- Lambda (λ) parameter = average events per minute
- More realistic than uniform random intervals
- Natural clustering and gaps in submissions

**Why Poisson?**
1. **Real users don't submit at fixed intervals:** Poisson captures natural randomness
2. **Independent events:** One user submitting doesn't affect others
3. **Memoryless property:** Past doesn't influence future (realistic for users)
4. **Industry standard:** Used for modeling HTTP requests, API calls, etc.

**Statistical Properties:**
- Mean interval: `1 / (lambda / 60)` seconds
- Example: lambda=30/min → mean interval = 2 seconds
- But intervals vary: some short, some long
- Variance equals mean (Poisson property)

**When to Use:**
- Production capacity planning
- Realistic load testing
- Estimating real-world performance
- Benchmarking with natural traffic patterns

---

## Rate Limiting

All patterns support global and per-trader rate limiting to prevent overwhelming the API.

### Global Rate Limiting

Limits total submission rate across all traders.

```yaml
enable_global_rate_limit: true
max_orders_global_per_second: 10.0  # Max 10 orders/sec total
rate_limit_burst_allowance: 1.5     # Allow 50% bursts
```

**Token Bucket Algorithm:**
- Bucket capacity: `max_rate * burst_allowance`
- Refill rate: `max_rate` tokens per second
- Each submission consumes 1 token
- If bucket empty, wait until token available

### Per-Trader Rate Limiting

Limits submission rate per individual trader.

```yaml
enable_per_trader_rate_limit: true
max_orders_per_trader_per_second: 2.0  # Max 2 orders/sec per trader
```

**Use Cases:**
- Simulating user-level rate limits
- Preventing single trader from dominating
- Testing fairness across traders

---

## Pattern Comparison Matrix

| Pattern | Predictability | Realism | Use Case | Load Profile |
|---------|---------------|---------|----------|--------------|
| CONSTANT_RATE | High | Low | Baseline testing | Flat |
| RANDOM_INTERVAL | Medium | Medium | Realistic variance | Variable |
| TIME_BASED | Medium | High | Daily patterns | Time-dependent |
| BURST | Low | Medium | Bot simulation | Cyclical spikes |
| RAMP_UP | Medium | Medium | Capacity finding | Increasing |
| RAMP_DOWN | Medium | Medium | Recovery testing | Decreasing |
| SPIKE | Low | Medium | Burst resilience | Spiky |
| POISSON | Low | High | Production estimation | Random |

---

## Configuration Best Practices

### 1. Start Simple

Begin with CONSTANT_RATE to establish baseline:

```yaml
# smoke-test.yml
trading_pattern: "constant_rate"
base_rate: 30.0
default_trader_count: 3
default_duration: 120
```

### 2. Test Capacity with Ramps

Use RAMP_UP to find limits:

```yaml
# capacity-test.yml
trading_pattern: "ramp_up"
ramp_start_rate: 1.0
ramp_target_rate: 120.0
ramp_duration: 300.0
ramp_curve: "exponential"  # Finds breaking point faster
```

### 3. Test Resilience with Spikes

Verify burst handling:

```yaml
# spike-test.yml
trading_pattern: "spike"
spike_normal_rate: 10.0
spike_burst_rate: 100.0
spike_duration: 15.0
spike_recovery_time: 60.0
enable_global_rate_limit: true
max_orders_global_per_second: 20.0
```

### 4. Estimate Production with Poisson

Most realistic simulation:

```yaml
# production-estimate.yml
trading_pattern: "poisson"
poisson_lambda: 60.0
default_trader_count: 20
default_duration: 600  # 10 minutes
```

---

## Example Scenarios

### Scenario 1: Light Load (Smoke Test)

**Purpose:** Verify system health, catch obvious regressions

```yaml
default_trader_count: 3
default_duration: 120
trading_pattern: "constant_rate"
base_rate: 30.0
```

**Expected:** ~60 orders in 2 minutes, all successful

---

### Scenario 2: Medium Load (Standard Benchmark)

**Purpose:** Standard performance benchmark

```yaml
default_trader_count: 10
default_duration: 300
trading_pattern: "poisson"
poisson_lambda: 60.0
enable_global_rate_limit: true
max_orders_global_per_second: 15.0
```

**Expected:** ~300 orders in 5 minutes, low latency

---

### Scenario 3: Heavy Load (Stress Test)

**Purpose:** Push system to limits

```yaml
default_trader_count: 25
default_duration: 600
trading_pattern: "constant_rate"
base_rate: 120.0
enable_global_rate_limit: true
max_orders_global_per_second: 40.0
```

**Expected:** ~3000 orders in 10 minutes, measure degradation

---

### Scenario 4: Spike Stress

**Purpose:** Test burst resilience

```yaml
default_trader_count: 10
default_duration: 180
trading_pattern: "spike"
spike_normal_rate: 10.0
spike_burst_rate: 100.0
spike_duration: 15.0
spike_recovery_time: 45.0
```

**Expected:** System handles spikes, recovers quickly

---

### Scenario 5: Capacity Finding

**Purpose:** Find performance limits

```yaml
default_trader_count: 10
default_duration: 300
trading_pattern: "ramp_up"
ramp_start_rate: 1.0
ramp_target_rate: 120.0
ramp_duration: 240.0
ramp_curve: "exponential"
```

**Expected:** Identify rate where latency/errors spike

---

## Measuring Success

For each pattern, measure:

1. **Throughput:** Orders submitted per second
2. **Success Rate:** Percentage of orders accepted
3. **Latency:** Time from submission to acceptance
4. **Rate Limit Hits:** How often rate limiting triggered
5. **Error Rate:** Failed submissions

Example metrics output:

```json
{
  "total_submitted": 232,
  "orders_failed": 0,
  "avg_order_latency_ms": 5395.24,
  "rate_limiting": {
    "global_hits": 12,
    "per_trader_hits": 3
  }
}
```

---

## Advanced Tips

### Combining Patterns

For complex scenarios, run multiple tests sequentially:

```bash
# Warm up
cow-perf run --config ramp-up-warmup.yml --duration 60

# Peak load
cow-perf run --config spike-stress.yml --duration 180

# Cool down
cow-perf run --config ramp-down-cooldown.yml --duration 60
```

### Adjusting for Network Latency

If testing remote orderbook, increase rates to account for latency:

```yaml
# Local: 30 orders/min might be enough
# Remote: Use 60 orders/min for similar server load
poisson_lambda: 60.0
```

### Reproducibility

For reproducible tests with random patterns (POISSON), use:

```python
# In code, set random seed
np.random.seed(42)
random.seed(42)
```

---

## Troubleshooting

### Problem: All orders failing

**Check:**
- Wallet funding enabled in config
- Anvil running in fork mode
- Token balances sufficient
- API URL correct

### Problem: Rate limiting too aggressive

**Solution:**
- Increase `max_orders_global_per_second`
- Increase `rate_limit_burst_allowance`
- Reduce `base_rate` or pattern rates

### Problem: POISSON rate doesn't match expected

**Explanation:**
- Poisson has natural variance
- Short tests have higher variance
- Run longer tests (10+ minutes) for stable rates
- Allow 20-30% tolerance for short tests

### Problem: RAMP_UP doesn't reach target rate

**Check:**
- Test duration > ramp_duration
- After ramp completes, rate should stabilize at target
- Use longer ramp_duration for smoother progression

---

## References

- [Poisson Process (Wikipedia)](https://en.wikipedia.org/wiki/Poisson_point_process)
- [Token Bucket Algorithm](https://en.wikipedia.org/wiki/Token_bucket)
- [Load Testing Best Practices](https://en.wikipedia.org/wiki/Load_testing)

---

## Quick Reference

```yaml
# CONSTANT_RATE
trading_pattern: "constant_rate"
base_rate: 30.0

# RANDOM_INTERVAL
trading_pattern: "random_interval"
min_interval: 5.0
max_interval: 30.0

# TIME_BASED
trading_pattern: "time_based"
base_rate: 30.0
active_hours: [9, 10, 11, 12, 13, 14, 15, 16]
active_multiplier: 2.0

# BURST
trading_pattern: "burst"
base_rate: 60.0
burst_size: 10
burst_interval: 0.5
quiet_period: 30.0

# RAMP_UP
trading_pattern: "ramp_up"
ramp_start_rate: 6.0
ramp_target_rate: 60.0
ramp_duration: 300.0
ramp_curve: "linear"  # or "exponential"

# RAMP_DOWN
trading_pattern: "ramp_down"
ramp_start_rate: 60.0
ramp_target_rate: 6.0
ramp_duration: 300.0
ramp_curve: "exponential"

# SPIKE
trading_pattern: "spike"
spike_normal_rate: 10.0
spike_burst_rate: 100.0
spike_duration: 15.0
spike_recovery_time: 60.0

# POISSON
trading_pattern: "poisson"
poisson_lambda: 30.0
```
