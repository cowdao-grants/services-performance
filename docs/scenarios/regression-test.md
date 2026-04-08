# Regression Test Scenario

**File:** `configs/scenarios/enhanced/regression-test.yml`
**Version:** 1.0
**Tags:** regression, ci-cd, short, quick, automated

## Purpose

Fast CI/CD regression test optimized for detecting performance degradation in automated pipelines. This scenario provides meaningful performance metrics in just 2 minutes, making it ideal for pull request validation and continuous integration workflows.

## When to Use

- **Continuous integration pipelines** - Run on every PR or commit
- **Pre-commit hooks** - Quick validation before pushing code
- **Pull request validation** - Ensure changes don't degrade performance
- **Quick smoke tests** - Fast verification that system is working
- **Development iteration** - Rapid feedback during feature development

## Configuration Details

### Test Parameters

| Parameter | Value | Description |
|-----------|-------|-------------|
| Duration | 120 seconds (2 min) | Fast but meaningful test duration |
| Traders | 10 | Moderate concurrency level |
| Expected Orders | ~600 | Total orders over test duration |
| Trading Pattern | constant_rate | Predictable, consistent load |
| Base Rate | 300.0 orders/min | 5 orders/second aggregate rate |

### Order Type Distribution

- **Market Orders:** 50%
- **Limit Orders:** 50%
- **TWAP Orders:** 0%
- **Stop-Loss Orders:** 0%
- **Good-After-Time Orders:** 0%

**Rationale:** Balanced mix of market and limit orders provides comprehensive testing without complexity of conditional orders.

### Resource Requirements

**Minimum:**
- Memory: 2.0 GB
- CPU Cores: 2

**Recommended:**
- Memory: 4.0 GB
- CPU Cores: 4

## Success Criteria

The test automatically validates results against these thresholds:

| Metric | Threshold | Rationale |
|--------|-----------|-----------|
| Success Rate | ≥ 90% | Allows for some liquidity issues while catching major problems |
| P95 Latency | ≤ 15 seconds | Reasonable latency for CI environment |
| Error Rate | ≤ 10% | Tolerates minor errors but catches systemic issues |
| Throughput | ≥ 4.0 orders/sec | Ensures system can handle expected load |

## Expected Behavior

### Normal Operation

With healthy system performance, you should see:
- Success rate: 93-98%
- P95 latency: 8-12 seconds
- Error rate: 2-5%
- Throughput: 4.5-5.5 orders/second
- Most orders settle within 1-2 auction rounds

### Performance Degradation Indicators

Watch for these warning signs:
- Success rate < 90% → Solver issues or liquidity problems
- P95 latency > 15s → System overload or network issues
- Error rate > 10% → API problems or validation failures
- Throughput < 4.0 orders/sec → Rate limiting or bottlenecks

## Usage Examples

### Command Line

```bash
# Run regression test with default config
cow-perf run --config configs/scenarios/enhanced/regression-test.yml

# Run and save as baseline
cow-perf run \
  --config configs/scenarios/enhanced/regression-test.yml \
  --save-baseline "pr-123" \
  --baseline-description "Performance before optimization"

# Run with custom settlement wait
cow-perf run \
  --config configs/scenarios/enhanced/regression-test.yml \
  --settlement-wait 180
```

### Programmatic Usage

```python
from pathlib import Path
from cow_performance.cli.commands.scenarios import load_scenario_from_yaml
from cow_performance.scenarios import SuccessCriteriaValidator

# Load scenario
scenario = load_scenario_from_yaml(
    Path('configs/scenarios/enhanced/regression-test.yml')
)

# Run test (implementation specific)
results = run_performance_test(scenario)

# Validate results
validator = SuccessCriteriaValidator(scenario.success_criteria)
validation = validator.validate_from_dict(results)

if not validation.passed:
    print(f"❌ Regression detected: {len(validation.failures)} failures")
    for failure in validation.failures:
        print(f"  - {failure.message}")
    exit(1)
else:
    print("✅ Performance within acceptable thresholds")
```

### CI/CD Integration

#### GitHub Actions

```yaml
name: Performance Regression Test

on: [pull_request]

jobs:
  regression-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2

      - name: Setup environment
        run: |
          # Setup steps...

      - name: Run regression test
        run: |
          cow-perf run \
            --config configs/scenarios/enhanced/regression-test.yml \
            --save-baseline "pr-${{ github.event.pull_request.number }}"

      - name: Check for regressions
        run: |
          # Compare against main branch baseline
          cow-perf compare \
            --baseline main \
            --current "pr-${{ github.event.pull_request.number }}"
```

## Interpreting Results

### Metrics to Monitor

1. **Success Rate** - Primary health indicator
   - > 95%: Excellent
   - 90-95%: Acceptable
   - < 90%: Investigation required

2. **P95 Latency** - Performance consistency
   - < 10s: Excellent
   - 10-15s: Acceptable
   - > 15s: Performance issue

3. **Error Rate** - System stability
   - < 5%: Excellent
   - 5-10%: Acceptable
   - > 10%: Stability issue

4. **Throughput** - System capacity
   - > 5 orders/s: Excellent
   - 4-5 orders/s: Acceptable
   - < 4 orders/s: Capacity issue

### Common Issues

**Low Success Rate**
- Check solver availability and health
- Verify liquidity on test tokens
- Review API error logs

**High Latency**
- Check network connectivity
- Monitor auction frequency
- Review solver processing time

**High Error Rate**
- Check API response codes
- Verify order validation
- Review authentication issues

**Low Throughput**
- Check rate limiting
- Monitor system resources
- Review trader orchestration

## Best Practices

1. **Run on every PR** - Catch regressions early
2. **Save baselines** - Track performance over time
3. **Set up alerts** - Get notified when thresholds are breached
4. **Compare to baseline** - Detect relative performance changes
5. **Run in consistent environment** - Use same hardware/network for comparisons
6. **Review trends** - Watch for gradual degradation over time

## Related Scenarios

- **sustained-load.yml** - For longer stability testing (30 min)
- **high-frequency.yml** - For extreme load testing (100 orders/sec)
- **large-orders.yml** - For whale trader edge cases

## Troubleshooting

**Test times out**
- Increase `duration` or reduce `num_traders`
- Check if services are running

**All orders fail**
- Verify API connectivity
- Check solver availability
- Ensure wallets have funds

**Inconsistent results**
- Run multiple times to establish baseline
- Check for external factors (network, solver load)
- Ensure consistent environment

## Version History

- **1.0** (Initial) - Fast 2-minute regression test optimized for CI/CD
