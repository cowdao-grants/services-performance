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
- Poetry (for dependency management)
- Docker and Docker Compose
- Ethereum RPC URL (Alchemy, Infura, etc.)

### Setup (5 Steps)

1. **Clone and install**
   ```bash
   git clone https://github.com/cowprotocol/cow-performance-testing-suite.git
   cd cow-performance-testing-suite
   poetry install && poetry shell
   ```

   Alternative without Poetry:
   ```bash
   python3 -m venv .venv && source .venv/bin/activate && pip install -e .
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
   cow-perf run --config configs/scenarios/enhanced/regression-test.yml
   ```

## Running Performance Tests

> **New to scenarios?** See the [Scenario User Guide](docs/scenario-user-guide.md) for a step-by-step tutorial on creating and using test scenarios.

### Available Test Scenarios

The suite includes 5 production-ready scenarios with automated validation:

| Scenario | Duration | Purpose | Success Criteria |
|----------|----------|---------|------------------|
| **regression-test** | 2 min | Fast CI/CD regression testing | ≥90% success, <15s P95 latency |
| **sustained-load** | 30 min | Long-term stability, memory leak detection | ≥80% success, <25s P95 latency |
| **large-orders** | 5 min | Edge case testing with whale trades (100+ ETH) | ≥70% success, <40s P95 latency |
| **high-frequency** | 3 min | Extreme stress test at 100 orders/sec | ≥60% success, <50s P95 latency |
| **limit-orders-only** | 10 min | Orderbook-focused testing (100% limit orders) | ≥75% success, <30s P95 latency |

**See detailed docs:** [Regression Test](docs/scenarios/regression-test.md) · [Sustained Load](docs/scenarios/sustained-load.md) · [Large Orders](docs/scenarios/large-orders.md) · [High Frequency](docs/scenarios/high-frequency.md) · [Limit Orders Only](docs/scenarios/limit-orders-only.md)

### Running a Test

**Basic usage:**
```bash
# Run a predefined scenario
cow-perf run --config configs/scenarios/enhanced/regression-test.yml

# Run with custom parameters
cow-perf run --traders 10 --duration 120 --settlement-wait 300
```

**Save results for later analysis:**
```bash
# Save as baseline for comparison
cow-perf run --config configs/scenarios/enhanced/regression-test.yml \
  --save-baseline "v1.0-regression" \
  --baseline-description "CI/CD regression baseline"
```

### Choosing the Right Scenario

| Your Goal | Use This Scenario | Why |
|-----------|-------------------|-----|
| Quick verification | **regression-test** | Fast (2 min), catches regressions |
| CI/CD pipeline | **regression-test** | Reliable, automated validation |
| Pre-release check | **sustained-load** | Detects memory leaks, stability issues |
| Stress testing | **high-frequency** | Finds breaking points, rate limits |
| Edge cases | **large-orders** | Tests extreme order sizes |
| Orderbook testing | **limit-orders-only** | Tests matching engine |

## Reports & Baselines

Save performance baselines and generate comprehensive reports with regression detection.

### Save Baseline After Test

Run a test and automatically save the results as a baseline for future comparisons:

```bash
# Run test and save as baseline
cow-perf run --config configs/scenarios/light-load.yml \
  --save-baseline "v1.0" \
  --baseline-description "Production baseline" \
  --baseline-tags "production,release"
```

**Saved to**: `.cow-perf/baselines/{uuid}.json`

### Generate Reports

Generate performance reports from saved baselines in multiple formats:

```bash
# Text report to console (default)
cow-perf report generate v1.0

# Save report to file (.cow-perf/reports/)
cow-perf report generate v1.0 --save

# Markdown report (GitHub-friendly)
cow-perf report generate v1.0 -f markdown --save

# JSON report (machine-readable)
cow-perf report generate v1.0 -f json --save

# With CSV exports
cow-perf report generate v1.0 --save --export-csv
```

**Saved to**:
- Reports: `.cow-perf/reports/report-{baseline}-{timestamp}.{format}`
- CSV files: `.cow-perf/reports/csv/{baseline}/summary.csv`, `latencies.csv`, `recommendations.csv`

### Compare Baselines (Regression Detection)

Compare two baselines to detect performance regressions or improvements:

```bash
# Compare current against previous baseline
cow-perf report generate v2.0 --compare v1.0 --save

# With markdown format for GitHub PRs
cow-perf report generate v2.0 --compare v1.0 -f markdown --save
```

The comparison report shows:
- ✅ **Improvements**: Metrics that got better
- ⚠️ **Regressions**: Metrics that got worse (with severity: minor/major/critical)
- 📊 **Percent changes**: For all key metrics
- 🔧 **Recommendations**: Actionable insights based on the comparison

### Manage Baselines

```bash
# List all saved baselines
cow-perf baselines --list

# Show detailed baseline info
cow-perf baselines --show v1.0

# Delete old baseline
cow-perf baselines --delete old-baseline
```

### Multiple Solver Tracking

**All solver containers are automatically tracked** - no configuration needed!

The system uses pattern matching to discover containers:
- Any container with `solver` in its name is tracked (e.g., `solver-baseline-1`, `solver-quasimodo-1`)
- Each solver gets separate resource metrics (CPU, memory, network I/O)
- Reports show per-solver performance

**Supported solver types**:
- `solver-baseline-*` - Baseline solver instances
- `solver-quasimodo-*` - Quasimodo solver instances
- `solver-{any-type}-*` - Any other solver type

**Adding more solvers**:

Follow these steps to add a new solver (e.g., adding a 4th baseline solver or a new quasimodo solver):

1. **Add solver service to `docker-compose.yml`**:
   ```yaml
   # For a 4th baseline solver:
   solver-baseline-4:
     build:
       context: ./modules/services
       target: solvers
     command: ["baseline", "--config", "/baseline.toml"]
     volumes:
       - ./configs/baseline.toml:/baseline.toml:ro
     networks:
       - cownet

   # OR for a quasimodo solver:
   solver-quasimodo-1:
     build:
       context: ./modules/services
       target: solvers
     command: ["quasimodo", "--config", "/quasimodo.toml"]
     volumes:
       - ./configs/quasimodo.toml:/quasimodo.toml:ro
     networks:
       - cownet
   ```

2. **Update autopilot environment variables** in `docker-compose.yml`:
   ```yaml
   # Add new solver to the DRIVERS list:
   - DRIVERS=solver-baseline-1|http://driver/solver-baseline-1|${SOLVER_ADDRESS},solver-baseline-2|http://driver/solver-baseline-2|${SOLVER_ADDRESS},solver-baseline-3|http://driver/solver-baseline-3|${SOLVER_ADDRESS},solver-baseline-4|http://driver/solver-baseline-4|${SOLVER_ADDRESS}

   # Add to PRICE_ESTIMATION_DRIVERS:
   - PRICE_ESTIMATION_DRIVERS=solver-baseline-1|http://driver/solver-baseline-1,solver-baseline-2|http://driver/solver-baseline-2,solver-baseline-3|http://driver/solver-baseline-3,solver-baseline-4|http://driver/solver-baseline-4

   # Add to NATIVE_PRICE_ESTIMATORS:
   - NATIVE_PRICE_ESTIMATORS=solver-baseline-1|http://driver/solver-baseline-1,solver-baseline-2|http://driver/solver-baseline-2,solver-baseline-3|http://driver/solver-baseline-3,solver-baseline-4|http://driver/solver-baseline-4
   ```

3. **Update orderbook environment variables** in `docker-compose.yml`:
   ```yaml
   # Add new solver to these same lists (same format as autopilot)
   - DRIVERS=...
   - PRICE_ESTIMATION_DRIVERS=...
   - NATIVE_PRICE_ESTIMATORS=...
   ```

4. **Add solver configuration to `configs/driver.toml`**:
   ```toml
   [[solver]]
   name = "solver-baseline-4"
   endpoint = "http://solver-baseline-4"
   absolute-slippage = "40000000000000000"
   relative-slippage = "0.1"
   account = "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"
   ```

5. **Build and start containers**:
   ```bash
   # Build new solver image (first time only)
   docker compose build solver-baseline-4

   # Start all services
   docker compose up -d

   # Verify solver is running
   docker compose ps | grep solver-baseline-4

   # Check solver logs
   docker compose logs -f solver-baseline-4
   ```

6. **Verify driver can reach the solver**:
   ```bash
   # Check driver logs for successful solver mounting
   docker compose logs driver | grep "mounting solver"
   # Should show: mounting solver solver=solver-baseline-4 path="/solver-baseline-4"
   ```

7. **Run a test to verify**:
   ```bash
   cow-perf run --config configs/scenarios/light-load.yml --duration 30
   ```

8. **Check report** - the new solver will automatically appear in resource metrics!

The system will automatically discover and track any container with `solver` in its name - no code changes needed!

**Example report output**:
```
Resource Utilization:
  Container              CPU(P95)  Memory(P95)
  -----------------------------------------------
  solver-baseline-1        38.8%       11.0%
  solver-baseline-2        43.8%       12.0%
  solver-baseline-3        48.8%       13.0%
  solver-quasimodo-1       35.2%       10.5%
  solver-quasimodo-2       41.1%       11.8%
```

When comparing baselines, per-solver improvements/regressions are shown:
```
Improvements:
  - resource_solver-baseline-1_cpu: -51.5% (improved)
  - resource_solver-baseline-2_cpu: -9.1% (improved)
  - resource_solver-quasimodo-1_cpu: -12.3% (improved)
```

### Complete Workflow Example

```bash
# 1. Run initial test and save baseline
cow-perf run --config configs/scenarios/medium-load.yml \
  --save-baseline "before-optimization" \
  --baseline-description "Performance before optimization work"

# 2. Make code changes, run new test
cow-perf run --config configs/scenarios/medium-load.yml \
  --save-baseline "after-optimization" \
  --baseline-description "Performance after optimization"

# 3. Generate comparison report
cow-perf report generate after-optimization \
  --compare before-optimization \
  -f markdown \
  --save \
  --export-csv

# 4. View results
cat .cow-perf/reports/report-after-optimization-vs-before-optimization-*.md
```

All files are saved in your project directory under `.cow-perf/`:
```
.cow-perf/
├── baselines/              # Saved performance baselines
├── reports/                # Generated reports
│   ├── report-*.txt
│   ├── report-*.md
│   ├── report-*.json
│   └── csv/               # CSV exports
│       └── {baseline}/
│           ├── summary.csv
│           ├── latencies.csv
│           └── recommendations.csv
└── results/               # Raw test results
```

See `.cow-perf/README.md` for detailed documentation on the data directory structure.

## Monitoring & Visualization

Prometheus metrics export is **enabled by default** (port 9091). To use the full monitoring stack:

1. **Start Prometheus & Grafana**
   ```bash
   docker compose --profile monitoring up -d
   ```

2. **Run a test** (metrics export automatically on port 9091)
   ```bash
   cow-perf run --config configs/scenarios/light-load.yml
   ```

3. **View dashboards** at http://localhost:3000 (default: admin/admin)
   - Performance Overview
   - API Performance
   - Resources
   - Comparison
   - Trader Activity

4. **Disable metrics export** (if needed)
   ```bash
   cow-perf run --config configs/scenarios/light-load.yml --prometheus-port 0
   ```

For detailed setup and troubleshooting, see [Development Guide](docs/development.md).

## Advanced: Scenario Management

### Discovering Scenarios

**List all available scenarios:**
```bash
# Show all scenarios with full metadata
cow-perf scenarios --dir configs/scenarios

# Simple view (basic info only)
cow-perf scenarios --dir configs/scenarios --simple
```

**Filter by tags:**
```bash
# Find regression tests
cow-perf scenarios --tag regression

# Find short-duration tests
cow-perf scenarios --tag short

# Multiple tags (AND logic) - find edge-case tests that are short
cow-perf scenarios --tag edge-case --tag short
```

**Search by text:**
```bash
# Search in name, description, or tags (case-insensitive)
cow-perf scenarios --search "stability"
cow-perf scenarios --search "whale"
cow-perf scenarios --search "ci-cd"
```

### Validating Scenarios

Before running a test, validate the scenario configuration:

```bash
cow-perf scenarios --validate configs/scenarios/enhanced/regression-test.yml
```

This displays:
- ✓ Configuration is valid
- Basic properties (name, traders, duration, pattern)
- Scenario metadata (expected orders, resource requirements)
- Success criteria thresholds
- Order type distribution

### Success Criteria Validation

Each scenario includes automated success criteria for pass/fail validation:

**Four key metrics:**
1. **Min Success Rate** - Minimum percentage of orders that must fill successfully
2. **Max P95 Latency** - Maximum acceptable 95th percentile latency
3. **Max Error Rate** - Maximum percentage of orders that can fail
4. **Min Throughput** - Minimum orders processed per second

**Example: Regression Test Criteria**
```yaml
success_criteria:
  min_success_rate: 0.90        # ≥90% orders must succeed
  max_p95_latency_seconds: 15.0 # P95 latency must be ≤15s
  max_error_rate: 0.10          # ≤10% orders can fail
  min_throughput_per_second: 4.0 # Must process ≥4 orders/sec
```

**Programmatic validation:**
```python
from pathlib import Path
from cow_performance.cli.commands.scenarios import load_scenario_from_yaml
from cow_performance.scenarios import SuccessCriteriaValidator

# Load scenario
scenario = load_scenario_from_yaml(
    Path('configs/scenarios/enhanced/regression-test.yml')
)

# Validate test results against criteria
validator = SuccessCriteriaValidator(scenario.success_criteria)
validation = validator.validate(
    success_rate=0.95,
    p95_latency_seconds=12.0,
    error_rate=0.05,
    throughput_per_second=5.0
)

if validation.passed:
    print(f"✅ All {validation.total_checks} criteria passed!")
else:
    print(f"❌ {len(validation.failures)} criteria failed:")
    for failure in validation.failures:
        print(f"  - {failure.criterion}: {failure.message}")
```

### Using Scenario Templates

Templates provide a quick way to create scenarios for common test patterns without writing full YAML configurations. The suite includes built-in templates for the most common testing patterns.

**List available templates:**
```bash
cow-perf scenarios --list-templates
```

**Built-in templates:**
- **`ramp-up`** - Gradually increase load to find breaking points and test scaling behavior
- **`spike`** - Sudden load burst to test resilience and recovery
- **`sustained-load`** - Maintain constant load for extended periods to test stability

**Create a scenario from a template:**

```yaml
# quick-load-test.yml
template: ramp-up
parameters:
  test_name: "Quick Ramp-Up Test"
  num_traders: 5
  duration: 300  # 5 minutes
  start_rate: 5.0  # Start at 5 orders/min per trader
  target_rate: 50.0  # Ramp up to 50 orders/min per trader
  ramp_curve: "linear"
```

Run the template-based scenario:
```bash
cow-perf run --config quick-load-test.yml
```

**Customize templates with additional settings:**

You can override template defaults or add extra configuration:

```yaml
template: spike
parameters:
  test_name: "Custom Spike Test"
  num_traders: 10
  duration: 180
  normal_rate: 10.0
  spike_rate: 100.0

# Override template defaults
tags:
  - custom
  - high-priority

# Custom order distribution
twap_order_ratio: 0.2  # Enable TWAP orders

# Custom success criteria
success_criteria:
  min_success_rate: 0.95
  max_p95_latency_seconds: 10.0
```

**See template examples:**
Check the `examples/scenarios/` directory for complete template usage examples.

### Interactive Configuration Wizard

> **📖 Full guide:** [Scenario User Guide](docs/scenario-user-guide.md) - Complete tutorial with examples and workflows

The `cow-perf config-init` command provides an interactive wizard to create scenario configurations without manually writing YAML. This is the easiest way to create custom scenarios, especially for new users.

**Quick start (interactive mode):**
```bash
# Let the wizard guide you through available options
cow-perf config-init

# Or specify output file
cow-perf config-init --output my-test.yml
```

The wizard will present four creation approaches:
1. **Quick start** - Answer a few basic questions for a simple test
2. **From template** - Select and customize a built-in template
3. **From existing** - Copy and modify a predefined scenario
4. **Advanced** - Full configuration with success criteria and metadata

**Mode shortcuts:**

Skip the selection prompt by specifying a mode directly:

```bash
# Quick start: minimal questions
cow-perf config-init --mode quick --output quick-test.yml

# Template-based: expand from a template
cow-perf config-init --mode template --output spike-test.yml

# Copy existing: customize a predefined scenario
cow-perf config-init --mode existing --output custom-test.yml

# Advanced: full configuration wizard
cow-perf config-init --mode advanced --output production-test.yml
```

**After generation:**

The wizard automatically validates your configuration and shows next steps:
```bash
# Review the generated file
cat my-test.yml

# Validate the scenario
cow-perf scenarios --validate my-test.yml

# Run the test
cow-perf run --config my-test.yml
```

**Example session:**
```
$ cow-perf config-init --mode quick

⚡ Quick Start Mode
Answer a few questions to create a basic load test.

Scenario name: My First Load Test
Description (optional): Testing order submission with 10 traders
Number of concurrent traders [10]: 10
Test duration (seconds) [60]: 120
Target orders per minute (per trader) [60.0]: 30.0

Validating configuration...
✓ Configuration is valid

✓ Configuration saved: scenario.yml

Next Steps:
  • Review: cat scenario.yml
  • Validate: cow-perf scenarios --validate scenario.yml
  • Run: cow-perf run --config scenario.yml
```

### Creating Custom Scenarios Manually

Create your own scenario YAML file:

```yaml
name: my-custom-test
description: Custom test scenario
version: "1.0"
tags: [custom, testing]

# Metadata (optional but recommended)
metadata:
  expected_orders: 300
  expected_duration_seconds: 60
  resource_requirements:
    min_memory_gb: 2.0
    min_cpu_cores: 2
    recommended_memory_gb: 4.0
    recommended_cpu_cores: 4

# Success criteria (optional)
success_criteria:
  min_success_rate: 0.80
  max_p95_latency_seconds: 20.0
  max_error_rate: 0.20
  min_throughput_per_second: 3.0

# Test configuration
num_traders: 10
duration: 60
trading_pattern: constant_rate
base_rate: 300.0  # orders per minute

# Order distribution
market_order_ratio: 0.6
limit_order_ratio: 0.4
```

Then validate and run:
```bash
cow-perf scenarios --validate my-custom-test.yml
cow-perf run --config my-custom-test.yml
```

## Disk Management

The Docker environment is optimized to prevent excessive disk usage, but monitoring is still recommended:

### Built-in Protections

- **Chain container (Anvil)**: Uses `--prune-history` flag to keep state in process memory only (no disk accumulation)
- **Container logs**: Limited to 10MB per file, max 3 files (30MB total per service)
- **Prometheus data**: Retention limited to 7 days and 1GB
- **Rust build artifacts**: Stored in Docker volumes (not on host disk)

### Monitoring Disk Usage

```bash
# Check Docker disk usage
docker system df

# Monitor specific container disk usage
docker stats --no-stream
```

### Cleanup Options

**Quick cleanup** (recommended for regular use):
```bash
# Stop containers (preserves images and volumes)
docker compose down

# Remove stopped containers and unused images
docker system prune -f
```

**Deep cleanup** (if disk space is critical):
```bash
# Use the automated cleanup script
./hack/cleanup-docker.sh

# Or manual cleanup with volumes (⚠️  data loss)
docker compose down -v
docker system prune -a -f --volumes
```

**After cleanup**, restart services:
```bash
docker compose up -d
```

> **Note**: First startup after cleanup may be slower due to image rebuilding and database migrations.

## Documentation

| Topic | Document |
|-------|----------|
| **Getting Started** | |
| Scenario User Guide | [docs/scenario-user-guide.md](docs/scenario-user-guide.md) ⭐ **Start here!** |
| CLI Reference | [docs/cli.md](docs/cli.md) |
| **Configuration** | |
| Configuration Reference | [docs/configuration-reference.md](docs/configuration-reference.md) |
| Scenario Best Practices | [docs/scenario-best-practices.md](docs/scenario-best-practices.md) |
| **Development** | |
| Development Guide | [docs/development.md](docs/development.md) |
| Architecture | [docs/architecture.md](docs/architecture.md) |
| **API Documentation** | |
| Order Generation API | [docs/order-generation.md](docs/order-generation.md) |
| Conditional Orders | [docs/conditional-orders.md](docs/conditional-orders.md) |
| User Simulation | [docs/user-simulation.md](docs/user-simulation.md) |
| **Scenario Documentation** | |
| Regression Test | [docs/scenarios/regression-test.md](docs/scenarios/regression-test.md) |
| Sustained Load | [docs/scenarios/sustained-load.md](docs/scenarios/sustained-load.md) |
| Large Orders | [docs/scenarios/large-orders.md](docs/scenarios/large-orders.md) |
| High Frequency | [docs/scenarios/high-frequency.md](docs/scenarios/high-frequency.md) |
| Limit Orders Only | [docs/scenarios/limit-orders-only.md](docs/scenarios/limit-orders-only.md) |

## Project Structure

```
cow-performance-testing-suite/
├── src/cow_performance/     # Core modules
│   ├── cli/                 # CLI commands (Typer)
│   ├── load_generation/     # Order generation, traders, Safe wallets
│   ├── benchmarking/        # Performance analysis
│   ├── metrics/             # Metrics collection
│   └── scenarios/           # Test scenarios
├── tests/                   # Unit, integration, and E2E tests
├── configs/                 # Configuration and scenario files
├── docs/                    # Documentation
└── docker/                  # Docker configuration
```

## Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

### Development Workflow

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests and linting: `poetry run pytest && poetry run ruff check . && poetry run mypy .`
5. Submit a pull request

## Roadmap

- [x] **Milestone 1**: Project Setup & Load Generation Framework
- [ ] **Milestone 2**: User Simulation Module (TraderPool, Safe wallets, hooks)
- [ ] **Milestone 3**: CLI Tool Interface
- [ ] **Milestone 4**: Performance Benchmarking & Metrics
- [ ] **Milestone 5**: Advanced Features & Documentation

## License

MIT License - see [LICENSE](LICENSE) for details.

## Support

- **Issues**: [GitHub Issues](https://github.com/cowprotocol/cow-performance-testing-suite/issues)
- **Discussions**: [GitHub Discussions](https://github.com/cowprotocol/cow-performance-testing-suite/discussions)

## Acknowledgments

Built with love by the CoW Protocol team for comprehensive performance testing of the CoW Protocol Playground.
