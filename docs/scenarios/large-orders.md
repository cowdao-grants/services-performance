# Large Orders Scenario

**File:** `configs/scenarios/enhanced/large-orders.yml`
**Version:** 1.0
**Tags:** edge-case, large-orders, whale, short

## Purpose

Edge case test for handling very large order amounts (100+ ETH equivalent) from whale traders. This scenario validates that the system can handle high-value transactions with potentially complex routing requirements and liquidity constraints.

## When to Use

- **Whale trader testing** - Validate handling of large transactions
- **Liquidity constraint testing** - Test behavior when orders exceed available liquidity
- **Edge case validation** - Ensure system doesn't fail on large amounts
- **High-value transaction testing** - Verify correct handling of significant trades
- **MEV protection testing** - Validate that large orders have appropriate protections
- **Slippage testing** - Understand slippage behavior on large orders

## Configuration Details

### Test Parameters

| Parameter | Value | Description |
|-----------|-------|-------------|
| Duration | 300 seconds (5 min) | Short test focused on edge case |
| Traders | 10 | Moderate number of whale traders |
| Expected Orders | ~150 | Lower volume due to slower rate |
| Trading Pattern | constant_rate | Predictable submission pattern |
| Base Rate | 30.0 orders/min | 0.5 orders/second (slower for large orders) |

**Note:** Order amounts (100-500 ETH equivalent) must be configured separately in the test runner configuration.

### Order Type Distribution

- **Market Orders:** 80%
- **Limit Orders:** 20%
- **TWAP Orders:** 0%
- **Stop-Loss Orders:** 0%
- **Good-After-Time Orders:** 0%

**Rationale:** Large orders typically use market orders for immediate execution. Some limit orders test partial fill scenarios when liquidity is insufficient.

### Resource Requirements

**Minimum:**
- Memory: 2.0 GB
- CPU Cores: 2

**Recommended:**
- Memory: 4.0 GB
- CPU Cores: 4

## Success Criteria

The test uses relaxed thresholds due to liquidity constraints:

| Metric | Threshold | Rationale |
|--------|-----------|-----------|
| Success Rate | ≥ 85% | Lower due to liquidity constraints on large orders |
| P95 Latency | ≤ 20 seconds | Higher due to complex routing and split executions |
| Error Rate | ≤ 15% | Some failures expected when liquidity unavailable |
| Throughput | ≥ 0.4 orders/sec | Lower throughput acceptable for large orders |

**Note:** These relaxed criteria reflect the reality that large orders often face liquidity constraints and may need multiple auction rounds or partial fills.

## Expected Behavior

### Normal Operation

With healthy system performance and reasonable liquidity:
- Success rate: 85-92%
- P95 latency: 12-18 seconds
- Error rate: 8-12%
- Throughput: 0.45-0.55 orders/second
- Some orders may fill partially over multiple auctions
- Larger orders may take longer to settle

### Common Scenarios

**Full Fill**
- Order size within available liquidity
- Single auction settlement
- Latency: 8-12 seconds

**Partial Fill**
- Order size exceeds single solver capacity
- Multiple solvers participate
- Latency: 15-20 seconds

**No Fill (Failed)**
- Order size exceeds total available liquidity
- No solver can fulfill order
- Error: "Insufficient liquidity"

**Split Execution**
- Very large order split across multiple auctions
- Each part fills separately
- Total settlement time: 20-30 seconds

## Usage Examples

### Command Line

```bash
# Run large orders test
cow-perf run --config configs/scenarios/enhanced/large-orders.yml

# Run with extended settlement wait (recommended for large orders)
cow-perf run \
  --config configs/scenarios/enhanced/large-orders.yml \
  --settlement-wait 600

# Run with specific order size configuration
# (Note: Order size configuration depends on test runner implementation)
cow-perf run \
  --config configs/scenarios/enhanced/large-orders.yml \
  --min-order-size 100 \
  --max-order-size 500
```

### Programmatic Usage

```python
from pathlib import Path
from cow_performance.cli.commands.scenarios import load_scenario_from_yaml

# Load scenario
scenario = load_scenario_from_yaml(
    Path('configs/scenarios/enhanced/large-orders.yml')
)

# Configure order sizes (implementation-specific)
test_config = {
    'scenario': scenario,
    'order_amount_range': (100, 500),  # ETH equivalent
    'allow_partial_fills': True,
}

# Run test
results = run_performance_test(test_config)

# Analyze large order specific metrics
analyze_partial_fills(results)
analyze_settlement_paths(results)
analyze_slippage(results)
```

## Interpreting Results

### Success Metrics

**Success Rate: 85-92%**
- Excellent: Some orders require multiple auctions but eventually settle
- Good: Most fills complete, some partial fills
- Concerning: < 85% → Check liquidity or order sizes

**Failure Analysis**
- Expected failures: 8-15% due to liquidity constraints
- Unexpected failures: > 15% → System issues

### Latency Analysis

**P95 Latency: 12-18s**
- Quick fills (< 10s): Order within single solver capacity
- Normal fills (10-18s): Multiple solvers or auction rounds
- Slow fills (18-20s): Complex routing or partial fills
- Timeouts (> 20s): Liquidity issues or system problems

### Liquidity Impact

Large orders will reveal:
- **Available liquidity depth** - How large can orders get?
- **Solver capacity** - Can solvers handle whale trades?
- **Routing efficiency** - Are paths optimized for large amounts?
- **Slippage characteristics** - How much price impact occurs?

## Common Issues

**Very high failure rate (> 20%)**
- Insufficient liquidity in test environment
- Order sizes exceed realistic limits
- Solver configuration issues
- API rate limiting on large orders

**Excessive latency (> 25s)**
- Solvers struggling with routing
- Network congestion
- Database query slowdowns on large amounts
- Complex multi-hop paths

**Frequent partial fills**
- Normal for very large orders
- May indicate fragmented liquidity
- Solvers optimizing across multiple sources

**Orders timing out**
- Increase settlement wait time
- Check solver health
- Verify order sizes are realistic

## Advanced Analysis

### Partial Fill Rate

```python
# Analyze how often orders fill completely vs. partially
full_fills = len([o for o in orders if o.filled_amount == o.order_amount])
partial_fills = len([o for o in orders if 0 < o.filled_amount < o.order_amount])
no_fills = len([o for o in orders if o.filled_amount == 0])

print(f"Full fills: {full_fills / len(orders):.1%}")
print(f"Partial fills: {partial_fills / len(orders):.1%}")
print(f"Failed: {no_fills / len(orders):.1%}")
```

### Fill Amount Distribution

```python
# Understand what order sizes successfully fill
import matplotlib.pyplot as plt

successful_orders = [o for o in orders if o.filled_amount > 0]
plt.scatter(
    [o.order_amount for o in successful_orders],
    [o.filled_amount / o.order_amount for o in successful_orders]
)
plt.xlabel("Order Size (ETH)")
plt.ylabel("Fill Ratio")
plt.title("Fill Success by Order Size")
plt.show()
```

### Slippage Analysis

```python
# Calculate average slippage for large orders
for order in filled_orders:
    expected_price = order.limit_price
    actual_price = order.executed_price
    slippage = abs(actual_price - expected_price) / expected_price
    print(f"Order {order.id}: {slippage:.2%} slippage")
```

## Best Practices

1. **Start with realistic order sizes** - Don't exceed actual whale trader patterns
2. **Monitor liquidity depth** - Ensure test environment has sufficient liquidity
3. **Allow longer settlement time** - Use `--settlement-wait 600` or higher
4. **Analyze partial fills separately** - Track different fill patterns
5. **Test incrementally** - Start with smaller "large" orders, increase gradually
6. **Compare against mainnet** - Validate that test behavior matches production
7. **Monitor solver strategies** - Understand how solvers route large orders
8. **Track MEV protection** - Ensure large orders have appropriate safeguards

## Edge Cases to Test

### Extremely Large Orders

Test orders that exceed total available liquidity:
```python
# Order size > total liquidity
# Expected: Partial fill or failure with clear error
```

### Rapid Large Order Succession

Multiple whale traders submitting simultaneously:
```python
# Increase num_traders or decrease startup_interval
# Tests: Liquidity contention, solver coordination
```

### Market Impact

How large orders affect subsequent orders:
```python
# Submit sequence of large orders
# Measure: Price impact, liquidity depletion, recovery time
```

## Related Scenarios

- **high-frequency.yml** - Tests opposite extreme (many small orders)
- **limit-orders-only.yml** - Tests limit order handling (useful for large limit orders)
- **sustained-load.yml** - Tests normal load (opposite of edge case)

## Production Considerations

When deploying with whale trader support:

1. **Liquidity Management**
   - Ensure sufficient liquidity depth
   - Monitor liquidity provider capacity
   - Set up alerts for low liquidity

2. **MEV Protection**
   - Implement slippage limits
   - Use private orderflow if needed
   - Monitor for sandwich attacks

3. **Rate Limiting**
   - Consider separate limits for large orders
   - Implement value-based throttling
   - Monitor for abuse

4. **Monitoring**
   - Track large order success rate
   - Alert on unusual failure patterns
   - Monitor average fill times

## Troubleshooting

**All large orders fail**
- Check available liquidity in test environment
- Verify order sizes are reasonable
- Ensure solvers can handle large amounts

**Partial fills too common**
- May be expected behavior
- Check if liquidity is fragmented
- Review solver routing strategies

**Extreme latency on specific sizes**
- Identify problematic order size threshold
- Review solver computational complexity
- Check for database query inefficiencies

## Version History

- **1.0** (Initial) - Edge case testing for whale traders (100-500 ETH orders)
