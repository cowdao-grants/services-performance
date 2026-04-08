# Limit Orders Only Scenario

**File:** `configs/scenarios/enhanced/limit-orders-only.yml`
**Version:** 1.0
**Tags:** edge-case, limit-orders, orderbook, medium

## Purpose

Edge case test with 100% limit orders and no market orders. This scenario validates orderbook behavior, limit order matching logic, price discovery mechanisms, and partial fill handling when orders may not match current market conditions.

## When to Use

- **Orderbook testing** - Validate limit order matching algorithms
- **Limit order matching validation** - Test fill conditions and priority
- **Price discovery testing** - Understand how limit orders affect pricing
- **Non-market order scenarios** - Test when liquidity doesn't immediately match
- **Partial fill testing** - Orders filling over multiple auctions
- **Order book depth analysis** - Understand limit order accumulation
- **Maker/taker dynamics** - Test passive liquidity provision

## Configuration Details

### Test Parameters

| Parameter | Value | Description |
|-----------|-------|-------------|
| Duration | 600 seconds (10 min) | Medium-length test for order accumulation |
| Traders | 15 | Moderate concurrency |
| Expected Orders | ~2,700 | Substantial orderbook depth |
| Trading Pattern | constant_rate | Consistent limit order submission |
| Base Rate | 270.0 orders/min | 4.5 orders/second aggregate |

**Note:** Limit order prices typically deviate -5% to +5% from current market price, so not all orders will fill immediately.

### Order Type Distribution

- **Market Orders:** 0%
- **Limit Orders:** 100%
- **TWAP Orders:** 0%
- **Stop-Loss Orders:** 0%
- **Good-After-Time Orders:** 0%

**Rationale:** Pure limit order testing isolates orderbook matching logic from market order execution.

### Resource Requirements

**Minimum:**
- Memory: 2.0 GB
- CPU Cores: 2

**Recommended:**
- Memory: 4.0 GB
- CPU Cores: 4

## Success Criteria

Relaxed thresholds due to the nature of limit orders:

| Metric | Threshold | Rationale |
|--------|-----------|-----------|
| Success Rate | ≥ 70% | Many limit orders won't fill if price doesn't reach limit |
| P95 Latency | ≤ 20 seconds | Limit orders may wait multiple auctions |
| Error Rate | ≤ 30% | Unfilled orders contribute to error rate |
| Throughput | ≥ 3.0 orders/sec | Lower throughput as many orders remain open |

**Note:** "Success" for limit orders means the order was accepted and properly tracked, even if it doesn't fill immediately.

## Expected Behavior

### Normal Operation

With properly functioning limit order matching:
- Success rate (filled): 70-78%
- Success rate (accepted): ~100%
- P95 latency: 12-18 seconds
- Error rate: 22-28% (mostly unfilled orders)
- Throughput: 3.2-4.0 orders/second
- Orders fill as market price crosses their limits
- Orderbook depth builds over time

### Order Fill Patterns

**Immediate Fill**
- Limit price at or better than current market
- Behaves similar to market order
- Latency: 8-12 seconds

**Delayed Fill**
- Limit price slightly off market
- Fills when price moves
- Latency: 15-30 seconds

**No Fill (Remains Open)**
- Limit price significantly off market
- Order stays in orderbook
- Eventually may expire or cancel

**Partial Fill**
- Large limit order
- Fills incrementally as price touches limit
- May take multiple auctions

## Usage Examples

### Command Line

```bash
# Run limit orders test
cow-perf run --config configs/scenarios/enhanced/limit-orders-only.yml

# Run with extended settlement wait to allow fills
cow-perf run \
  --config configs/scenarios/enhanced/limit-orders-only.yml \
  --settlement-wait 900

# Run with specific price deviation range
# (Note: Implementation-specific configuration)
cow-perf run \
  --config configs/scenarios/enhanced/limit-orders-only.yml \
  --limit-price-range -0.05:0.05
```

### Programmatic Usage

```python
from pathlib import Path
from cow_performance.cli.commands.scenarios import load_scenario_from_yaml

# Load scenario
scenario = load_scenario_from_yaml(
    Path('configs/scenarios/enhanced/limit-orders-only.yml')
)

# Run test
results = run_performance_test(scenario)

# Analyze limit order specific metrics
filled_orders = [o for o in results.orders if o.filled_amount > 0]
unfilled_orders = [o for o in results.orders if o.filled_amount == 0]

print(f"Fill rate: {len(filled_orders) / len(results.orders):.1%}")
print(f"Average time to fill: {mean([o.fill_time for o in filled_orders]):.1f}s")

# Analyze by price deviation
for deviation in [-0.05, -0.02, 0, 0.02, 0.05]:
    orders_at_deviation = [o for o in results.orders if abs(o.price_deviation - deviation) < 0.005]
    fill_rate = len([o for o in orders_at_deviation if o.filled]) / len(orders_at_deviation)
    print(f"Fill rate at {deviation:+.1%}: {fill_rate:.1%}")
```

## Interpreting Results

### Fill Rate Analysis

**By Price Deviation:**
```
Price Deviation | Expected Fill Rate
----------------|------------------
-5% (below)     | ~95% (very likely to fill)
-2% (below)     | ~85%
 0% (at market) | ~75%
+2% (above)     | ~60%
+5% (above)     | ~30% (unlikely to fill)
```

**By Time:**
- First 2 minutes: 40-50% of fills (in-market orders)
- Minutes 2-5: 20-30% of fills (price movement catches orders)
- Minutes 5-10: 10-20% of fills (larger price movements)
- After 10 minutes: Some orders still unfilled (extreme limits)

### Orderbook Depth

Track how many orders remain open at each price level:
```python
from collections import defaultdict

orderbook = defaultdict(list)
for order in open_orders:
    price_level = round(order.limit_price, 2)
    orderbook[price_level].append(order)

# Visualize depth
for price in sorted(orderbook.keys()):
    depth = sum(o.amount for o in orderbook[price])
    print(f"{price}: {'█' * int(depth/100)} {depth:.2f} ETH")
```

## Common Issues

**Very low fill rate (< 60%)**
- Price deviations too aggressive
- Market not moving enough
- Insufficient counterparty liquidity
- Orderbook not being swept

**All orders fill immediately (> 90%)**
- Price deviations too tight
- Orders effectively market orders
- Test not exercising limit order logic

**Orders never fill**
- Limit prices too far off market
- No price discovery happening
- Solvers not checking orderbook
- Matching algorithm not working

**High cancellation rate**
- Order expiry too short
- Traders cancelling unfilled orders
- System rejecting limit orders

## Advanced Analysis

### Price Impact on Fill Rate

```python
import matplotlib.pyplot as plt
import numpy as np

# Analyze fill rate by price deviation
deviations = np.linspace(-0.05, 0.05, 20)
fill_rates = []

for dev in deviations:
    orders_near_dev = [
        o for o in results.orders
        if abs(o.price_deviation - dev) < 0.005
    ]
    if orders_near_dev:
        filled = len([o for o in orders_near_dev if o.filled])
        fill_rates.append(filled / len(orders_near_dev))
    else:
        fill_rates.append(0)

plt.plot([d * 100 for d in deviations], [r * 100 for r in fill_rates])
plt.axvline(x=0, color='r', linestyle='--', label='Market Price')
plt.xlabel('Price Deviation from Market (%)')
plt.ylabel('Fill Rate (%)')
plt.title('Limit Order Fill Rate by Price')
plt.legend()
plt.show()
```

### Time to Fill Distribution

```python
# Understand how long limit orders take to fill
fill_times = [o.fill_time for o in filled_orders]

print(f"Median time to fill: {np.median(fill_times):.1f}s")
print(f"P90 time to fill: {np.percentile(fill_times, 90):.1f}s")

# Plot histogram
plt.hist(fill_times, bins=50)
plt.xlabel('Time to Fill (seconds)')
plt.ylabel('Number of Orders')
plt.title('Distribution of Fill Times for Limit Orders')
plt.show()
```

### Order Book Evolution

```python
# Track how orderbook depth changes over time
snapshots = []
for t in range(0, 600, 60):  # Every minute
    open_at_time = [o for o in results.orders if o.created_at <= t and (o.filled_at is None or o.filled_at > t)]
    total_volume = sum(o.amount for o in open_at_time)
    snapshots.append((t, total_volume, len(open_at_time)))

# Plot
times, volumes, counts = zip(*snapshots)
plt.plot(times, counts, label='Open Orders')
plt.xlabel('Time (seconds)')
plt.ylabel('Open Order Count')
plt.title('Orderbook Depth Over Time')
plt.show()
```

## Best Practices

1. **Use realistic price deviations** - Match actual trader behavior
2. **Allow sufficient settlement time** - Use `--settlement-wait 900` or more
3. **Monitor orderbook depth** - Track open order accumulation
4. **Analyze fill patterns** - Understand what price levels fill
5. **Test price movement scenarios** - Vary how much price moves
6. **Compare to market order baseline** - Understand limit order overhead
7. **Track partial fills** - Monitor how often orders fill incrementally
8. **Review matching algorithm** - Ensure fair order priority (price/time)

## Orderbook Metrics

### Key Metrics to Track

1. **Fill Rate by Price Level**
   - In-market orders (±1%): Should fill ~90%+
   - Near-market orders (±2%): Should fill ~70%+
   - Off-market orders (±5%): May fill <50%

2. **Time to Fill**
   - Fast (< 30s): In-market orders
   - Medium (30-120s): Near-market orders caught by price movement
   - Slow (> 120s): Off-market orders requiring significant movement

3. **Orderbook Depth**
   - Should grow steadily as unfilled orders accumulate
   - Should shrink as orders fill or expire
   - Peak depth depends on fill rate and order rate

4. **Matching Efficiency**
   - Are best-priced orders filling first?
   - Are older orders at same price filling first?
   - Are partial fills handled correctly?

## Related Scenarios

- **regression-test.yml** - Balanced market/limit order mix (baseline)
- **large-orders.yml** - Tests large limit orders with partial fills
- **sustained-load.yml** - Includes some limit orders in realistic mix

## Production Considerations

Lessons for production limit order support:

1. **Order Priority**
   - Implement price-time priority correctly
   - Handle equal-price orders fairly (FIFO)
   - Consider pro-rata allocation for large orders

2. **Orderbook Management**
   - Efficient data structure for depth queries
   - Fast insertion/deletion
   - Periodic cleanup of stale orders
   - Indexing for quick price level lookup

3. **Matching Algorithm**
   - O(log n) matching performance
   - Support partial fills
   - Handle minimum fill amounts
   - Respect price improvement rules

4. **Order Lifecycle**
   - Clear expiry handling
   - Cancellation support
   - Status updates (open, partial, filled)
   - Historical tracking

## Troubleshooting

**No orders filling**
- Check limit price generation
- Verify matching algorithm is running
- Ensure solvers see limit orders
- Review price movement in test

**All orders filling immediately**
- Limit prices too close to market
- Increase price deviation range
- Review order generation logic

**Orderbook grows without bound**
- Orders not expiring correctly
- Cancellation not working
- Fill logic not executing
- Database not cleaning up

**Unfair matching (wrong priority)**
- Review price-time priority implementation
- Check for race conditions
- Verify timestamp precision
- Test equal-price scenarios

## Version History

- **1.0** (Initial) - 100% limit orders test for orderbook validation
