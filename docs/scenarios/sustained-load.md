# Sustained Load Scenario

**File:** `configs/scenarios/enhanced/sustained-load.yml`
**Version:** 1.0
**Tags:** sustained, stability, long, endurance

## Purpose

Extended 30-minute test designed to validate system stability under continuous load. This scenario is critical for detecting memory leaks, resource exhaustion, gradual performance degradation, and other issues that only manifest over longer time periods.

## When to Use

- **Production readiness testing** - Validate system before releases
- **Memory leak detection** - Identify resource leaks over time
- **Long-term stability validation** - Ensure system doesn't degrade
- **Load testing before releases** - Stress test with realistic duration
- **Soak testing** - Verify sustained performance under load
- **Capacity planning** - Understand long-term resource usage

## Configuration Details

### Test Parameters

| Parameter | Value | Description |
|-----------|-------|-------------|
| Duration | 1800 seconds (30 min) | Extended duration for stability testing |
| Traders | 25 | Higher concurrency than regression test |
| Expected Orders | ~18,000 | High volume over test duration |
| Trading Pattern | constant_rate | Consistent load for stability observation |
| Base Rate | 600.0 orders/min | 10 orders/second aggregate rate |

### Order Type Distribution

- **Market Orders:** 45%
- **Limit Orders:** 45%
- **TWAP Orders:** 5%
- **Stop-Loss Orders:** 3%
- **Good-After-Time Orders:** 2%

**Rationale:** Realistic mix including conditional orders to test all code paths over extended period.

### Resource Requirements

**Minimum:**
- Memory: 4.0 GB
- CPU Cores: 4

**Recommended:**
- Memory: 8.0 GB
- CPU Cores: 8

**Note:** Higher resource requirements reflect longer duration and larger state accumulation.

## Success Criteria

The test automatically validates results against these thresholds:

| Metric | Threshold | Rationale |
|--------|-----------|-----------|
| Success Rate | ≥ 95% | Higher threshold for production readiness |
| P95 Latency | ≤ 10 seconds | Stricter latency requirement |
| Error Rate | ≤ 5% | Lower error tolerance for stability |
| Throughput | ≥ 9.0 orders/sec | Must sustain high throughput |

## Expected Behavior

### Normal Operation

With healthy system performance, you should see:
- Success rate: 96-99%
- P95 latency: 6-9 seconds
- Error rate: 1-3%
- Throughput: 9.5-10.5 orders/second
- Stable memory usage over entire test
- No degradation in later vs. earlier periods

### Performance Degradation Indicators

Watch for these warning signs:

**Memory Issues:**
- Increasing memory usage over time → Memory leak
- Out of memory errors → Insufficient resources

**Performance Degradation:**
- Latency increasing over time → Resource exhaustion
- Throughput declining over time → Bottleneck accumulation
- Success rate dropping in later periods → State corruption

**System Instability:**
- Error rate increasing over time → System instability
- Service crashes or restarts → Resource exhaustion
- Connection timeouts → Network saturation

## Usage Examples

### Command Line

```bash
# Run sustained load test
cow-perf run --config configs/scenarios/enhanced/sustained-load.yml

# Run with extended settlement wait (recommended for long tests)
cow-perf run \
  --config configs/scenarios/enhanced/sustained-load.yml \
  --settlement-wait 600

# Run and save as baseline for production readiness
cow-perf run \
  --config configs/scenarios/enhanced/sustained-load.yml \
  --save-baseline "v2.0-stability" \
  --baseline-description "30-min stability test before v2.0 release"

# Run with Prometheus monitoring
cow-perf run \
  --config configs/scenarios/enhanced/sustained-load.yml \
  --prometheus-port 9091
```

### Monitoring During Test

```bash
# In separate terminal, monitor resource usage
watch -n 5 'docker stats'

# Monitor memory specifically
watch -n 10 'ps aux | grep cow-perf'

# Monitor Prometheus metrics (if enabled)
curl http://localhost:9091/metrics | grep cow_performance
```

## Interpreting Results

### Time-Series Analysis

The key to sustained load testing is analyzing trends over time, not just final metrics.

**Plot these metrics over time:**
1. Memory usage (should be stable or grow slowly)
2. Latency (should remain consistent)
3. Success rate (should not trend downward)
4. Throughput (should remain constant)
5. Error rate (should stay consistently low)

### Baseline Comparison

Compare metrics between different time periods within the same test:

```python
# Pseudo-code for analysis
first_10_min = results[0:600]
middle_10_min = results[600:1200]
last_10_min = results[1200:1800]

# Performance should be similar across all periods
assert abs(first_10_min.success_rate - last_10_min.success_rate) < 0.05
assert last_10_min.p95_latency < 1.2 * first_10_min.p95_latency  # Allow 20% degradation max
```

### Memory Leak Detection

**Indicators of memory leaks:**
- Linear memory growth throughout test
- Memory doesn't plateau or stabilize
- Memory usage >> expected based on state size
- System slowdown in later periods

**Analysis approach:**
1. Record memory at start, middle, end
2. Calculate growth rate
3. Extrapolate to longer durations
4. Determine if growth is bounded

## Best Practices

1. **Run before major releases** - Validate stability before production
2. **Monitor resource usage** - Watch memory, CPU, network during test
3. **Compare time periods** - Ensure consistent performance throughout
4. **Establish baselines** - Track stability metrics over releases
5. **Run in production-like environment** - Match deployment configuration
6. **Allow for settlement** - Use longer `--settlement-wait` (600s recommended)
7. **Monitor logs** - Watch for errors, warnings, anomalies
8. **Run overnight** - Schedule for off-hours to avoid interference

## Metrics to Monitor

### During Test

| Metric | Tool | What to Watch |
|--------|------|---------------|
| Memory Usage | `docker stats` | Should plateau, not grow linearly |
| CPU Usage | `docker stats` | Should be steady, not increasing |
| Network I/O | `docker stats` | Should be consistent |
| Disk I/O | `iostat` | Should not be bottleneck |
| Connection Count | `netstat` | Should be stable |

### After Test

| Metric | Analysis | Healthy Range |
|--------|----------|---------------|
| Success Rate | Mean ± std dev | 96-99% ± 1% |
| P95 Latency | Trend over time | < 10s, flat trend |
| Error Rate | Mean ± std dev | 1-3% ± 1% |
| Throughput | Mean | 9.5-10.5 orders/s |

## Common Issues

**Memory continuously increasing**
- Check for unreleased resources (connections, file handles)
- Review order tracker cleanup
- Monitor metrics storage

**Performance degrades over time**
- Check for state accumulation
- Review caching strategy
- Monitor database query performance

**High error rate in later periods**
- Check for connection pool exhaustion
- Review retry logic
- Monitor API rate limits

**Service crashes mid-test**
- Increase memory allocation
- Review error handling
- Check for race conditions

## Production Readiness Checklist

Before releasing to production, this scenario should demonstrate:

- [ ] Success rate > 95% sustained over 30 minutes
- [ ] P95 latency < 10 seconds consistently
- [ ] No memory leaks (memory plateaus)
- [ ] No performance degradation over time
- [ ] Error rate < 5% consistently
- [ ] No service crashes or restarts
- [ ] Resource usage within acceptable limits
- [ ] All 18,000+ orders processed
- [ ] Conditional orders work correctly

## Related Scenarios

- **regression-test.yml** - Quick 2-minute smoke test for CI/CD
- **high-frequency.yml** - Short burst of extreme load
- **large-orders.yml** - Edge case testing with large order sizes

## Advanced Analysis

### Performance Percentiles Over Time

```python
# Analyze latency distribution changes over test duration
import numpy as np

early_latencies = get_latencies(0, 600)   # First 10 min
late_latencies = get_latencies(1200, 1800)  # Last 10 min

print(f"P50 change: {np.percentile(late_latencies, 50) / np.percentile(early_latencies, 50)}")
print(f"P95 change: {np.percentile(late_latencies, 95) / np.percentile(early_latencies, 95)}")
print(f"P99 change: {np.percentile(late_latencies, 99) / np.percentile(early_latencies, 99)}")

# Should all be close to 1.0 (no change)
```

### Memory Growth Rate

```python
# Calculate memory growth rate
memory_samples = [(t, get_memory_usage(t)) for t in range(0, 1800, 60)]
slope = calculate_linear_regression_slope(memory_samples)

# Acceptable: < 1 MB/minute growth
# Warning: 1-5 MB/minute
# Critical: > 5 MB/minute
```

## Troubleshooting

**Test doesn't complete**
- Increase timeout settings
- Check for deadlocks
- Review service health

**Intermittent failures**
- Check for rate limiting
- Review connection timeouts
- Monitor network stability

**Results inconsistent between runs**
- Ensure consistent environment
- Check for external interference
- Review random seed handling

## Version History

- **1.0** (Initial) - 30-minute stability test with realistic order mix
