# CoW Performance Testing Suite

Comprehensive performance testing suite for the CoW Protocol Playground, enabling load testing, benchmarking, and regression detection using Anvil fork mode.

## Features

- **Load Generation**: Simulate realistic trading patterns with configurable strategies
- **Performance Benchmarking**: Measure order lifecycle, API performance, and resource utilization
- **Metrics & Visualization**: Prometheus exporters and Grafana dashboards
- **Regression Detection**: Statistical comparison against baselines
- **Fork Mode Testing**: Test against mainnet state using Anvil fork mode
- **Scenario Library**: Predefined scenarios from light to heavy loads
- **Flexible Configuration**: YAML-based scenarios with inheritance and composition

## Quick Start

### Prerequisites

- Python 3.11+
- Poetry **or** venv (choose your preferred dependency manager)
- Docker and Docker Compose
- Ethereum RPC URL (Alchemy, Infura, etc.)

### Setup (5 Steps)

1. **Clone and install**

   **Option A: Using Poetry** (recommended for development)
   ```bash
   git clone https://github.com/cowprotocol/cow-performance-testing-suite.git
   cd cow-performance-testing-suite
   poetry install

   # Activate the virtual environment (Poetry ≥ 2.0)
   poetry env activate
   # Note: `poetry shell` was removed in Poetry 2.0. If you have the shell plugin
   # installed you can still use it, otherwise use `poetry env activate` or run
   # commands via `poetry run <cmd>`.
   # With Poetry < 2.0: use `poetry shell` instead of `poetry env activate`.
   ```

   **Option B: Using venv** (standard Python virtual environment)
   ```bash
   git clone https://github.com/cowprotocol/cow-performance-testing-suite.git
   cd cow-performance-testing-suite
   python3 -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   pip install -e .
   ```

2. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env and set: ETH_RPC_URL=https://eth-mainnet.g.alchemy.com/v2/YOUR_KEY
   ```

3. **Start services**
   ```bash
   docker compose up -d
   ```
   > **Note**: First startup may show "unhealthy" errors while orderbook compiles
   > (takes 5-10 minutes). Check progress: `docker compose logs -f orderbook`

4. **Verify installation**
   ```bash
   cow-perf version
   ```

5. **Run your first test**

   > **Wallet funding required**: Trader wallets need ETH and tokens before orders can be submitted. The Quick Start scenario (`light-load.yml`) includes a `wallet:` block that handles this automatically via Anvil storage manipulation. See [Wallet Funding](docs/wallet-funding.md) for details.

   ```bash
   # Light 2-minute load test (wallet funding enabled in scenario config)
   cow-perf run --config configs/scenarios/predefined/light-load.yml
   ```

---

## Running Performance Tests

> **New to scenarios?** See the [Scenario User Guide](docs/scenario-user-guide.md) for a step-by-step tutorial.

### Available Test Scenarios

The suite includes 5 production-ready scenarios with automated validation:

| Scenario | Duration | Purpose | Success Criteria |
|----------|----------|---------|------------------|
| **regression-test** | 2 min | Fast CI/CD regression testing | ≥90% success, <15s P95 latency |
| **sustained-load** | 30 min | Long-term stability, memory leak detection | ≥80% success, <25s P95 latency |
| **large-orders** | 5 min | Edge case testing with whale trades (100+ ETH) | ≥70% success, <40s P95 latency |
| **high-frequency** | 3 min | Extreme stress test at 100 orders/sec | ≥60% success, <50s P95 latency |
| **limit-orders-only** | 10 min | Orderbook-focused testing (100% limit orders) | ≥75% success, <30s P95 latency |

### Run a Test

```bash
# Run a predefined scenario
cow-perf run --config configs/scenarios/predefined/light-load.yml

# Run with custom parameters
cow-perf run --traders 10 --duration 120

# Save results as baseline for comparison
cow-perf run --config configs/scenarios/predefined/light-load.yml \
  --save-baseline "v1.0" \
  --baseline-description "Production baseline"
```

---

## Reports & Baselines

Save baselines and generate comprehensive reports with regression detection.

### Quick Examples

```bash
# Run test and save as baseline
cow-perf run --config configs/scenarios/predefined/light-load.yml --save-baseline "v1.0"

# Generate report
cow-perf report generate v1.0

# Compare baselines (regression detection)
cow-perf report generate v2.0 --compare v1.0

# Export as markdown for PRs
cow-perf report generate v2.0 --compare v1.0 -f markdown --save

# List all saved baselines
cow-perf baselines --list

# Show baseline details
cow-perf baselines --show v1.0
```

### Comparison Reports

Comparison reports show:
- ✅ **Improvements**: Metrics that got better
- ⚠️ **Regressions**: Metrics that got worse (minor/major/critical)
- 📊 **Percent changes**: For all key metrics
- 🔧 **Recommendations**: Actionable insights

> **See:** [Reports & Baselines Guide](docs/reports.md) for detailed documentation.

---

## Monitoring & Visualization

Prometheus metrics export requires passing `--prometheus-port 9091` to the run command. To use the full monitoring stack with Grafana dashboards:

```bash
# Start Prometheus & Grafana
docker compose --profile monitoring up -d

# Run a test with Prometheus export enabled
cow-perf run --config configs/scenarios/predefined/light-load.yml \
  --prometheus-port 9091

# View dashboards
open http://localhost:3000  # Grafana (admin/admin)
open http://localhost:9090  # Prometheus
```

> **No data in Grafana?** Metrics only appear when `--prometheus-port 9091` is passed. Without this flag, no metrics are exported and Grafana panels will show "No data". The `$scenario` dashboard variable is populated from `cow_perf_orders_created_total` labels — it will be empty until at least one test has run with the flag enabled.

**Available dashboards:**
- **CoW Performance Overview** (`/d/cow-perf-overview`) - Real-time order lifecycle, latency, and submission rate metrics
- **API Performance** (`/d/cow-perf-api`) - Orderbook API response times and error rates
- **Resources** (`/d/cow-perf-resources`) - Container CPU and memory usage
- **Comparison** (`/d/cow-perf-comparison`) - Side-by-side metrics across test runs
- **Trader Activity** (`/d/cow-perf-traders`) - Per-trader submission and fill rates
- **Auction Activity** (`/d/cow-perf-auction`) - Auction frequency, orders per auction, filter reasons, solver winners, and order acceptance latency

> **See:** [CLI Reference](docs/cli.md#monitoring--visualization) for detailed setup.

---

## Creating Custom Scenarios

### Interactive Wizard (Recommended)

```bash
# Interactive mode
cow-perf config-init

# Quick start mode
cow-perf config-init --mode quick --output my-test.yml

# From template
cow-perf config-init --mode template --output spike-test.yml
```

### Manual YAML

```yaml
name: my-custom-test
description: Custom test scenario

num_traders: 10
duration: 120
trading_pattern: constant_rate
base_rate: 300.0  # orders per minute

# Order distribution
market_order_ratio: 0.6
limit_order_ratio: 0.4

# Success criteria
success_criteria:
  min_success_rate: 0.80
  max_p95_latency_seconds: 20.0
```

Then run:
```bash
cow-perf run --config my-custom-test.yml
```

> **See:** [Scenario User Guide](docs/scenario-user-guide.md) for complete tutorial.

---

## Documentation

| Topic | Document |
|-------|----------|
| **Getting Started** | |
| Scenario User Guide | [docs/scenario-user-guide.md](docs/scenario-user-guide.md) ⭐ **Start here!** |
| CLI Reference | [docs/cli.md](docs/cli.md) |
| **Configuration** | |
| Configuration Reference | [docs/configuration-reference.md](docs/configuration-reference.md) |
| Scenario Best Practices | [docs/scenario-best-practices.md](docs/scenario-best-practices.md) |
| **Reports & Operations** | |
| Reports & Baselines | [docs/reports.md](docs/reports.md) |
| Operations Guide | [docs/operations.md](docs/operations.md) |
| **Development** | |
| Development Guide | [docs/development.md](docs/development.md) |
| Architecture | [docs/architecture.md](docs/architecture.md) |
| **API Documentation** | |
| Order Generation API | [docs/order-generation.md](docs/order-generation.md) |
| Conditional Orders | [docs/conditional-orders.md](docs/conditional-orders.md) |
| User Simulation | [docs/user-simulation.md](docs/user-simulation.md) |
| **Features** | |
| Wallet Funding | [docs/wallet-funding.md](docs/wallet-funding.md) |
| Trading Patterns | [docs/trading-patterns.md](docs/trading-patterns.md) |
| Metrics Collection | [docs/metrics.md](docs/metrics.md) |
| Benchmarking | [docs/benchmarking.md](docs/benchmarking.md) |

---

## Project Structure

```
cow-performance-testing-suite/
├── src/cow_performance/         # Core library
│   ├── load_generation/         # Order generation and trader simulation
│   ├── metrics/                 # Metrics collection and aggregation
│   ├── benchmarking/            # Performance analysis
│   ├── cli/                     # CLI commands
│   └── scenarios/               # Test scenarios
├── tests/                       # Unit, integration, and E2E tests
├── configs/                     # Configuration and scenario files
│   └── scenarios/               # Predefined test scenarios
├── docs/                        # Documentation
└── docker/                      # Docker configuration
```

---

## Known Limitations

### Anvil Fork Mode - Event Synchronization Issue

**Issue:** In Anvil fork mode, the CoW Protocol services cannot detect settlement events due to missing `debug_traceTransaction` RPC support. This causes database fill rate metrics to show 0% even when settlements are executing successfully on-chain.

**Impact:**
- Fill rate metrics show 0% despite actual fills being 50–75%
- Order statuses remain "open" in the database even when filled on-chain

**Root Cause:** Anvil (Foundry's local node) doesn't implement `debug_traceTransaction`, which autopilot requires for event post-processing. This is a fundamental Anvil limitation, not a bug in CoW Protocol or this suite.

**Workaround:** Use the on-chain fill counts reported in the test summary output, which are derived directly from chain state rather than the database.

### Understanding Metrics Output

After a test run you will see several counts in the summary output:

| Term | Meaning |
|------|---------|
| `total_submitted` | Orders accepted by the CoW Protocol API (HTTP 201). These made it into the orderbook. |
| `total_tracked` | Orders the test suite monitored, including any that were rejected by the API before submission. |
| `orders_failed` | Orders that received an API error (4xx/5xx). These were never in the orderbook. |

> **Why do counts differ?** The API may reject orders (e.g. insufficient balance, invalid token pair). `orders_failed` counts those rejections. `total_submitted` is the count actually sent to the orderbook.

### Expected Fill Rates for Smoke Tests

In Anvil fork mode with default scenarios, partial fills are normal:

- **regression-test** (2 min): expect **50–75% fill rate** (database will show 0%; see Anvil limitation above)
- **quick-test** (30 sec): expect **10–50%** — short window, solver may not run every batch
- Fill rates vary run-to-run because Anvil mines blocks on-demand and solver scheduling is non-deterministic

> **For more reproducible results**, pin the fork block: set `ETH_BLOCKNUMBER=<block>` in `.env`. This ensures the same on-chain state across runs, reducing variance in order matching. See `docs/operations.md` for details.

## Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

### Development Workflow

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests and linting:

   **With Poetry:**
   ```bash
   poetry run pytest
   poetry run ruff check .
   poetry run mypy .
   poetry run black --check .
   ```

   **With venv:**
   ```bash
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   pytest
   ruff check .
   mypy .
   black --check .
   ```

5. Submit a pull request

---

## Roadmap

- [x] **Milestone 1**: Project Setup & Load Generation Framework
- [x] **Milestone 2**: User Simulation Module (TraderPool, Safe wallets, hooks)
- [x] **Milestone 3**: CLI Tool Interface
- [x] **Milestone 4**: Performance Benchmarking & Metrics
- [x] **Milestone 5**: Advanced Features & Documentation

---

## License

MIT License - see [LICENSE](LICENSE) for details.

## Support

- **Issues**: [GitHub Issues](https://github.com/cowprotocol/cow-performance-testing-suite/issues)
- **Discussions**: [GitHub Discussions](https://github.com/cowprotocol/cow-performance-testing-suite/discussions)

## Acknowledgments

Built with love by the CoW Protocol team for comprehensive performance testing of the CoW Protocol Playground.
