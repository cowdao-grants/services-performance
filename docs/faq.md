# Frequently Asked Questions

Common questions about the CoW Performance Testing Suite.

---

## Getting Started

### Q: What are the minimum system requirements?

**A:** Minimum: 4 GB RAM, 2 CPU cores, 10 GB disk
Recommended: 8 GB RAM, 4 CPU cores, 20 GB disk

For heavy load tests (50+ traders), use 16 GB RAM and 8 CPU cores.

### Q: How do I install and run my first test?

**A:** See [First-Time User Workflow](workflows.md#first-time-user-workflow) for step-by-step instructions.

```bash
poetry install
docker compose up -d
poetry run cow-perf run --config configs/scenarios/predefined/smoke-test.yml
```

### Q: Which Python version do I need?

**A:** Python 3.11 or higher. Check with `python --version`.

### Q: Do I need Docker Desktop or can I use Docker Engine?

**A:** Both work. Docker Desktop is easier for beginners. Docker Engine + Docker Compose works on Linux servers.

---

## Test Execution

### Q: Why do I see 0% fill rate during tests?

**A:** This is normal in Anvil fork mode — the CoW Protocol database relies on `debug_traceTransaction` to detect settlement events, which Anvil does not implement. The actual on-chain fill rate is typically 50–75% for short tests. See [Known Limitations](../README.md#known-limitations) for details.

### Q: How long should my tests run?

**A:**
- Smoke tests: 2-5 minutes
- Load tests: 5-10 minutes
- Stress tests: 10-30 minutes
- Soak tests: 30+ minutes

Minimum 2 minutes for valid statistics.

### Q: How many traders should I use?

**A:**
- Smoke: 3-5 traders
- Light load: 10-15 traders
- Medium load: 20-30 traders
- Heavy load: 50+ traders

More traders = more load, but also more memory usage (~50-100 MB per trader).

### Q: What's a good target rate?

**A:** Start with 30 orders/minute per trader (0.5 orders/sec). Increase gradually based on system capacity.

---

## Results and Metrics

### Q: How do I know if my test succeeded?

**A:** Check the `verdict` field in the test report:
- **SUCCESS**: All success criteria met
- **WARNING**: Minor issues, close to thresholds
- **FAILURE**: Critical criteria failed

### Q: What's the difference between success rate and fill rate?

**A:**
- **Success rate**: Orders accepted by API / orders submitted
- **Fill rate**: Orders filled on-chain / orders submitted

Success rate measures API health, fill rate measures solver performance.

### Q: What's a good success rate?

**A:**
- Production: 99%+
- Standard load: 95%+
- Stress tests: 85-90%

Below 80% indicates serious issues.

### Q: What's an acceptable P95 latency?

**A:**
- Interactive: <2 seconds
- Background: <10 seconds
- Batch processing: <30 seconds

Depends on your use case.

### Q: Where are test results stored?

**A:** `.cow-perf/results/`

Latest result: `.cow-perf/results/latest-result.json`

### Q: How do I export results to CSV?

**A:**
```bash
poetry run cow-perf report generate my-baseline --export-csv
```

---

## Configuration

### Q: What's the difference between a scenario and a template?

**A:**
- **Scenario**: Complete test configuration (YAML file)
- **Template**: Reusable scenario with parameters

Templates are in `configs/scenarios/templates/`, scenarios use `template:` field to inherit.

### Q: Can I override scenario parameters from the command line?

**A:** Yes:

```bash
cow-perf run --config scenario.yml \
  --traders 20 \
  --duration 300
```

### Q: How do I create a custom scenario?

**A:** See [Custom Scenario Development Workflow](workflows.md#custom-scenario-development).

### Q: What trading pattern should I use?

**A:**
- **constant_rate**: Baseline, predictable load
- **poisson**: Most realistic, production estimates
- **ramp_up**: Find capacity limits
- **spike**: Test burst resilience
- **burst**: Short high-intensity bursts

See [Trading Patterns Guide](trading-patterns.md) for details.

### Q: Order ratios must sum to 1.0 - why?

**A:** They represent probabilities. Each generated order is randomly assigned a type based on these ratios, so they must sum to exactly 1.0.

---

## Baselines and Comparison

### Q: What's a baseline?

**A:** A saved test result used for comparison. Create with `--save-baseline`:

```bash
cow-perf run --config scenario.yml --save-baseline "v1.0"
```

### Q: How do I compare two test results?

**A:**
```bash
cow-perf report generate current --compare previous
```

### Q: What counts as a regression?

**A:** Configurable thresholds in `configs/thresholds.toml`:
- Success rate drops by >5%
- P95 latency increases by >20%
- Error rate increases by >2%

Adjust based on your requirements.

### Q: Can I use baselines in CI/CD?

**A:** Yes. Save a baseline and then generate a report to get an exit code:

```bash
cow-perf run --config scenario.yml --save-baseline "current"
cow-perf report generate current --compare previous
```

Exit code 0 = pass, 2 = FAILURE verdict (success rate <80% or critical latency).

---

## Docker Services

### Q: Which services are required?

**A:** Minimum:
- `chain` (Anvil)
- `orderbook`
- `autopilot`
- `driver`
- `solver-baseline-1`
- `db` (PostgreSQL)

Optional: `prometheus`, `grafana` (for monitoring)

### Q: How do I start all services?

**A:**
```bash
docker compose up -d
```

Wait 5-10 minutes for first startup (Rust compilation).

### Q: Why is orderbook showing "unhealthy"?

**A:** First startup compiles Rust code (5-10 minutes). Check logs:

```bash
docker compose logs -f orderbook | grep -i compiling
```

### Q: How do I check service status?

**A:**
```bash
docker compose ps
docker compose logs -f orderbook
```

### Q: How do I restart services?

**A:**
```bash
# Restart specific service
docker compose restart orderbook

# Restart all
docker compose restart

# Full reset
docker compose down -v
docker compose up -d
```

### Q: Services are using too much disk - what do I do?

**A:** See [Operations Guide](operations.md) for disk management:

```bash
docker system df  # Check usage
docker system prune -f  # Clean up
docker volume prune -f  # Remove unused volumes
```

---

## Monitoring

### Q: How do I access Grafana dashboards?

**A:**
```bash
docker compose up -d prometheus grafana
open http://localhost:3000
```

Default credentials: admin/admin

### Q: Where are Prometheus metrics?

**A:** `http://localhost:9091/metrics` during test runs.

Metrics are automatically exported when running tests.

### Q: Can I disable Prometheus export?

**A:**
```bash
cow-perf run --config scenario.yml --prometheus-port 0
```

---

## Troubleshooting

### Q: Orders are failing - what should I check?

**A:**
1. Wallet funding enabled? (`enable_wallet_funding: true`)
2. Services healthy? (`docker compose ps`)
3. Token balances sufficient?
4. Check logs: `docker compose logs orderbook`

See [Troubleshooting Guide](troubleshooting.md) for comprehensive diagnostics.

### Q: Test hangs or crashes - what do I do?

**A:**
1. Check resource usage: `docker stats`
2. Check for OOM kills in logs
3. Reduce load (fewer traders or lower rate)
4. Increase Docker memory limits

### Q: "Connection refused" errors?

**A:**
1. Check services running: `docker compose ps`
2. Restart services: `docker compose restart`
3. Check ports not in use: `lsof -i :8080`

### Q: How do I enable debug logging?

**A:**
```bash
cow-perf run --verbose --config scenario.yml
```

### Q: Where should I report bugs?

**A:** GitHub Issues: https://github.com/cowprotocol/services-performance/issues

Include: error message, logs, scenario file, system info.

---

## Performance Tuning

### Q: How do I improve test performance?

**A:**
1. Use simpler orders (market only)
2. Reduce num_traders or base_rate
3. Allocate more Docker resources
4. Use SSD for Docker storage

### Q: Tests are too slow - why?

**A:** Common causes:
- Underpowered hardware
- Database bottleneck (check `docker stats`)
- Too many complex orders (TWAP, stop-loss)
- Solver performance issues

### Q: How do I test at higher load?

**A:**
1. Increase Docker resources (CPU, memory)
2. Use more powerful hardware
3. Consider distributed testing (multiple machines)
4. Optimize scenario (simple orders, efficient patterns)

---

## Advanced Usage

### Q: Can I run tests in parallel?

**A:** Not recommended - services are shared. Run tests sequentially.

### Q: Can I use a remote orderbook?

**A:** Yes, configure `orderbook_url` in scenario:

```yaml
orderbook_url: "https://api.cow.fi"
```

Note: Can't use wallet funding with remote orderbook.

### Q: How do I test conditional orders (TWAP, stop-loss)?

**A:** Set order type ratios:

```yaml
twap_order_ratio: 0.3
stop_loss_order_ratio: 0.2
```

See [Conditional Orders Guide](conditional-orders.md).

### Q: Can I customize token pairs?

**A:** Yes, but requires code changes. Default pairs in `src/cow_performance/load_generation/`.

### Q: How do I integrate with CI/CD?

**A:** See [CI/CD Integration Workflow](workflows.md#cicd-integration-workflow).

---

## Best Practices

### Q: What's the recommended test workflow?

**A:**
1. Start with smoke test (quick validation)
2. Run load test (sustained performance)
3. Create baseline (for future comparison)
4. Run regularly in CI/CD

### Q: How often should I run tests?

**A:**
- Smoke: Every commit/PR
- Load: Daily or before releases
- Stress: Weekly or before major releases
- Soak: Monthly or before capacity changes

### Q: Should I commit baselines to git?

**A:** Yes - important baselines should be version-controlled:

```bash
cp .cow-perf/baselines/baseline.json baselines/production/v1.0.json
git add baselines/
git commit -m "chore: Added production baseline"
```

---

## See Also

- [Troubleshooting Guide](troubleshooting.md)
- [Workflows](workflows.md)
- [CLI Reference](cli.md)
- [Trading Patterns](trading-patterns.md)
- [Configuration Reference](configuration-reference.md)
