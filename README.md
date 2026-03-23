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
   poetry install && poetry shell
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
   ```bash
   # Quick 2-minute regression test
   cow-perf run --config configs/scenarios/predefined/enhanced/regression-test.yml
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
cow-perf run --config configs/scenarios/predefined/enhanced/regression-test.yml

# Run with custom parameters
cow-perf run --traders 10 --duration 120

# Save results as baseline for comparison
cow-perf run --config configs/scenarios/predefined/enhanced/regression-test.yml \
  --save-baseline "v1.0" \
  --baseline-description "Production baseline"
```

### Chain Reconciliation

In Anvil fork mode, database event synchronization is limited. The test suite automatically performs **chain reconciliation** after each test to verify actual on-chain fill rates and update the database.

> **See:** [Known Limitations](#known-limitations) for details on Anvil fork mode.

---

## Reports & Baselines

Save baselines and generate comprehensive reports with regression detection.

### Quick Examples

```bash
# Run test and save as baseline
cow-perf run --config scenario.yml --save-baseline "v1.0"

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

Prometheus metrics export is **enabled by default** (port 9091). To use the full monitoring stack with Grafana dashboards:

```bash
# Start Prometheus & Grafana
docker compose --profile monitoring up -d

# Run a test (metrics automatically exported)
cow-perf run --config scenario.yml

# View dashboards
open http://localhost:3000  # Grafana (admin/admin)
open http://localhost:9090  # Prometheus
```

**Available dashboards:**
- CoW Performance Overview - Real-time metrics during test runs
- Reconciliation Dashboard - Chain reconciliation and fill rate tracking

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

**Issue:** In Anvil fork mode, the CoW Protocol services cannot detect settlement events due to missing `debug_traceTransaction` RPC support. This causes database metrics to show 0% fill rate even when settlements are executing successfully on-chain.

**Solution:** The test suite automatically performs **chain reconciliation** after every test:

1. Queries the settlement contract for Trade events in the test block range
2. Matches events to submitted orders
3. Updates the database with accurate trade records
4. Updates Prometheus metrics with accurate on-chain data
5. Displays accurate fill rate comparison (database vs on-chain)

**Example Output:**
```
Chain Reconciliation:
  Database Reports:  0/8 filled (0.0%)
  On-Chain Reality:  6/8 filled (75.0%)

  ⚠️ Discrepancy: +75.0 percentage points
```

Chain reconciliation runs automatically on every test in fork mode to ensure accurate metrics.

**Long-term Solution:** A proper fix requires implementing a custom event indexer that works with Anvil's limitations. This is tracked in our internal issue tracker.

---

## Common Operations

### Disk Management

```bash
# Check Docker disk usage
docker system df

# Quick cleanup (preserves volumes)
docker compose down
docker system prune -f

# Deep cleanup (removes all data)
./hack/cleanup-docker.sh
```

> **See:** [Operations Guide](docs/operations.md) for detailed maintenance procedures.

### Service Management

```bash
# Start services
docker compose up -d

# Start with monitoring
docker compose --profile monitoring up -d

# Check service status
docker compose ps

# View logs
docker compose logs -f orderbook

# Restart a service
docker compose restart orderbook

# Stop services
docker compose down
```

### Verify Installation

```bash
# Check CLI version
cow-perf version

# Check Anvil is running
cast block-number --rpc-url http://localhost:8545

# Check orderbook API
curl http://localhost:8080/api/v1/version

# Check database
docker exec $(docker ps -qf "name=db") pg_isready -U postgres
```

---

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
