# High-Frequency Trading Scenario

**File:** `configs/scenarios/enhanced/high-frequency.yml`
**Version:** 1.0
**Tags:** edge-case, high-frequency, stress, short

## Purpose

Extreme stress test with very high order submission rate (100 orders/second). This scenario validates system behavior under peak load conditions, tests rate limiting mechanisms, identifies bottlenecks, and ensures graceful degradation under pressure.

## When to Use

- **Stress testing** - Find system breaking points
- **Rate limiting validation** - Verify throttling works correctly
- **Peak load testing** - Understand maximum capacity
- **HFT simulation** - Test high-frequency trading scenarios
- **Bottleneck identification** - Find performance constraints
- **Denial of service protection** - Validate system doesn't crash under extreme load
- **Queue management testing** - Verify request queuing behaves correctly

## Configuration Details

### Test Parameters

| Parameter | Value | Description |
|-----------|-------|-------------|
| Duration | 180 seconds (3 min) | Short burst of extreme load |
| Traders | 100 | Very high concurrency |
| Expected Orders | ~18,000 | Massive volume in short time |
| Trading Pattern | constant_rate | Sustained high rate |
| Base Rate | 6000.0 orders/min | 100 orders/second aggregate |
| Startup Interval | 0.01 seconds | Nearly instant trader startup |

**Note:** Order amounts (0.01-0.1 ETH equivalent) kept small to focus on throughput rather than value.

### Order Type Distribution

- **Market Orders:** 100%
- **Limit Orders:** 0%
- **TWAP Orders:** 0%
- **Stop-Loss Orders:** 0%
- **Good-After-Time Orders:** 0%

**Rationale:** Market orders only minimize processing overhead to focus stress test on submission/handling capacity.

### Resource Requirements

**Minimum:**
- Memory: 8.0 GB
- CPU Cores: 8

**Recommended:**
- Memory: 16.0 GB
- CPU Cores: 16

**Note:** This scenario requires significantly more resources than others due to extreme concurrency and throughput.

## Success Criteria

Relaxed thresholds reflecting extreme stress conditions:

| Metric | Threshold | Rationale |
|--------|-----------|-----------|
| Success Rate | ≥ 80% | System can handle high load without total failure |
| P95 Latency | ≤ 30 seconds | Acceptable degradation under extreme pressure |
| Error Rate | ≤ 20% | Some failures expected at this load level |
| Throughput | ≥ 80 orders/sec | Must sustain most of the target rate |

**Note:** Success means the system survives extreme load and processes most orders, even if some fail or experience delays.

## Expected Behavior

### Normal Operation Under Stress

With appropriate rate limiting and queue management:
- Success rate: 82-88%
- P95 latency: 15-25 seconds
- Error rate: 12-18%
- Throughput: 85-95 orders/second
- Rate limiting kicks in appropriately
- System remains responsive
- No crashes or deadlocks

### System Behavior Patterns

**Graceful Degradation**
- Rate limiting activates at defined threshold
- Queue builds up but doesn't overflow
- Oldest/newest requests handled appropriately
- Error messages are clear (e.g., "Rate limit exceeded")

**Resource Saturation**
- CPU approaches maximum capacity
- Memory usage spikes but stabilizes
- Network bandwidth near limit
- Connection pool at max size

**Recovery**
- After test ends, system processes queued requests
- Resources return to normal levels
- No persistent degradation

## Usage Examples

### Command Line

```bash
# Run high-frequency test (ensure sufficient resources!)
cow-perf run --config configs/scenarios/enhanced/high-frequency.yml

# Run with very long settlement wait to clear queue
cow-perf run \
  --config configs/scenarios/enhanced/high-frequency.yml \
  --settlement-wait 900

# Run with resource monitoring
cow-perf run \
  --config configs/scenarios/enhanced/high-frequency.yml \
  --prometheus-port 9091 &

# In separate terminal, monitor resources
watch -n 1 'docker stats'
```

### Stress Test Series

```bash
# Incremental stress testing to find limits
for rate in 50 75 100 125 150; do
  echo "Testing at ${rate} orders/sec..."

  # Modify base_rate in config file
  # (or use parameter override if implemented)

  cow-perf run --config modified-high-freq.yml \
    --save-baseline "stress-${rate}ops"

  sleep 300  # Cool-down period
done

# Analyze results to find breaking point
```

## Interpreting Results

### Success Indicators

Even under extreme load, look for:

**System Survives**
- No crashes or restarts
- Services remain responsive
- Graceful error handling

**Predictable Failures**
- Clear error messages (rate limit, timeout, etc.)
- Consistent failure patterns
- No cascading failures

**Resource Management**
- Memory doesn't leak
- CPU returns to normal after test
- Connections properly closed

### Failure Indicators

**System Breaks**
- Services crash or become unresponsive
- Database connections exhausted
- Out of memory errors

**Cascading Failures**
- One failure triggers others
- System doesn't recover after load stops
- Corruption or inconsistent state

**Unpredictable Behavior**
- Random errors without clear cause
- Performance varies wildly
- Intermittent connection issues

## Common Issues

**Very low success rate (< 70%)**
- Rate limits too aggressive
- Insufficient system resources
- Database bottleneck
- Network saturation

**Service crashes during test**
- Out of memory
- Connection pool exhausted
- Unhandled exception in hot path
- Resource leak under load

**Extreme latency (> 60s)**
- Queue overflow
- Database query slowdown
- Network congestion
- Solver overload

**System doesn't recover after test**
- Resource leak
- Connection leak
- Memory not freed
- Background tasks stuck

## Advanced Analysis

### Throughput Over Time

```python
import matplotlib.pyplot as plt

# Plot throughput in 1-second buckets
timestamps = [o.timestamp for o in orders]
buckets = create_time_buckets(timestamps, bucket_size=1.0)

plt.plot(buckets.keys(), buckets.values())
plt.axhline(y=100, color='r', linestyle='--', label='Target Rate')
plt.xlabel('Time (seconds)')
plt.ylabel('Orders/second')
plt.title('Throughput Under High-Frequency Load')
plt.legend()
plt.show()

# Expected: May peak above 100 ops/s, then stabilize around 85-95 ops/s
```

### Latency Distribution

```python
import numpy as np

latencies = [o.latency for o in orders]

print(f"P50: {np.percentile(latencies, 50):.1f}s")
print(f"P75: {np.percentile(latencies, 75):.1f}s")
print(f"P90: {np.percentile(latencies, 90):.1f}s")
print(f"P95: {np.percentile(latencies, 95):.1f}s")
print(f"P99: {np.percentile(latencies, 99):.1f}s")
print(f"Max: {max(latencies):.1f}s")

# Expected distribution: Long tail due to queuing
```

### Resource Usage Correlation

```python
# Correlate throughput with resource usage
import pandas as pd

df = pd.DataFrame({
    'throughput': throughput_samples,
    'cpu_usage': cpu_samples,
    'memory_usage': memory_samples,
})

print(df.corr())

# Find bottleneck: Which resource correlates most with throughput drops?
```

## Best Practices

1. **Ensure adequate resources** - Don't run on underpowered hardware
2. **Monitor during test** - Watch CPU, memory, network in real-time
3. **Allow recovery time** - Use long `--settlement-wait` (900s+)
4. **Test incrementally** - Start at lower rates, increase gradually
5. **Isolate test environment** - Don't run on shared infrastructure
6. **Compare against baseline** - Understand normal capacity first
7. **Monitor logs** - Watch for errors, warnings, rate limit messages
8. **Cool down between runs** - Allow system to fully reset

## Rate Limiting Validation

### Test Rate Limit Effectiveness

```bash
# Test that rate limiting actually works
# Expected: Error rate increases, but system survives

# Check rate limit headers in responses
curl -v http://api/orders | grep -i rate-limit

# Monitor rate limit metrics
curl http://localhost:9091/metrics | grep rate_limit
```

### Analyze Rate Limit Behavior

```python
# Verify rate limiting is fair and consistent
for trader in traders:
    accepted = len([o for o in trader.orders if o.status == 'accepted'])
    rejected = len([o for o in trader.orders if o.status == 'rate_limited'])

    print(f"Trader {trader.id}: {accepted} accepted, {rejected} rate-limited")

# Expected: Fairly even distribution across traders
```

## Related Scenarios

- **sustained-load.yml** - Moderate sustained load (opposite extreme)
- **regression-test.yml** - Normal load baseline
- **large-orders.yml** - Tests value instead of volume

## Production Considerations

Lessons from this test for production deployment:

1. **Rate Limiting**
   - Implement per-IP rate limits
   - Consider per-wallet limits
   - Use token bucket or leaky bucket algorithm
   - Return clear error messages

2. **Queue Management**
   - Bounded queues with overflow handling
   - Priority queuing for important requests
   - Queue monitoring and alerts
   - Graceful degradation under load

3. **Resource Management**
   - Connection pooling with limits
   - Memory limits and monitoring
   - CPU throttling if needed
   - Automatic scaling based on load

4. **Monitoring**
   - Real-time throughput tracking
   - Queue depth monitoring
   - Error rate alerts
   - Resource usage dashboards

## Troubleshooting

**Cannot achieve target throughput**
- Check available CPU cores
- Review database connection pool size
- Monitor network bandwidth
- Check for lock contention

**Random connection failures**
- Connection pool exhausted
- Increase max connections
- Review connection timeout settings
- Check for connection leaks

**Memory usage spikes and crashes**
- Too many concurrent requests
- Reduce num_traders or base_rate
- Increase memory allocation
- Review object lifecycle

**Uneven trader performance**
- Check thread scheduling
- Review random number generation
- Verify fair resource allocation
- Monitor GIL contention (Python)

## Version History

- **1.0** (Initial) - Extreme stress test at 100 orders/second with 100 concurrent traders
