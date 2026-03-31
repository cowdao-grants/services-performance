# CLI Reference

> Full reference for the `cow-perf` command-line tool.
>
> **See also**: [Development Guide](development.md) | [Architecture](architecture.md)

## Quick Start

```bash
# Show version
cow-perf version

# List scenarios
cow-perf scenarios

# Run a performance test
cow-perf run --config configs/scenarios/predefined/quick-test.yml
```

## Global Options

```bash
# Show version information
cow-perf version

# Get help for any command
cow-perf --help
cow-perf config --help
cow-perf scenarios --help
```

---

## Configuration Management

The configuration system uses YAML files and supports environment variable overrides with the `COW_` prefix.

### Show Configuration Template

Display the default configuration template to understand available options:

```bash
# Show configuration template in terminal
cow-perf config --template
```

### Save Configuration Template

Create a configuration file with default values:

```bash
# Save to default location (~/.cow-perf.yml)
cow-perf config --save-template ~/.cow-perf.yml

# Save to custom location
cow-perf config --save-template ./my-config.yml

# Save to project directory
cow-perf config --save-template .cow-perf.yml
```

### Configuration File Structure

```yaml
# Network settings
network:
  chain_id: 1  # 1=Mainnet, 100=Gnosis Chain
  rpc_url: "https://eth.llamarpc.com"
  settlement_contract: "0x9008D19f58AAbD9eD0D60971565AA8510560ab41"
  composable_cow_contract: "0xfdaFc9d1902f4e0b84f65F49f244b32b31013b74"

# API settings
api:
  base_url: "http://localhost:8080"
  timeout: 30
  max_retries: 3

# Output settings
output:
  format: "json"  # json, table, csv, prometheus
  verbose: false
  save_results: true
  results_dir: "~/.cow-perf/results"

# Wallet configuration for trader accounts
wallet:
  generate_count: 0       # Number of wallets to generate (0 = use default pool)
  private_keys: []        # List of private keys to use (optional)
  funding_enabled: false  # Enable automatic wallet funding (requires Anvil)
  eth_balance: 10.0       # ETH per wallet (when funding enabled)
  token_balances:         # Token amounts per wallet (when funding enabled)
    WETH: 10.0
    DAI: 10000.0
    USDC: 5000.0

# Default test parameters
default_trader_count: 10
default_duration: 60
default_startup_interval: 0.1

# Prometheus metrics export (enabled by default)
prometheus_port: 9091  # Port for metrics exporter (null or 0 to disable)

# Order type distribution (must sum to 1.0)
market_order_ratio: 0.4
limit_order_ratio: 0.4
twap_order_ratio: 0.1
stop_loss_order_ratio: 0.05
good_after_time_order_ratio: 0.05
```

### Load Configuration

```bash
# Load from specific file
cow-perf run --config ./my-config.yml --scenario light-load

# Config file search order:
# 1. --config flag (highest priority)
# 2. .cow-perf.yml in current directory
# 3. ~/.cow-perf.yml in home directory
# 4. Environment variables (COW_* prefix)
# 5. Default values (lowest priority)
```

### Environment Variable Overrides

Override configuration values using environment variables:

```bash
# Override network settings
export COW_NETWORK_CHAIN_ID=100
export COW_NETWORK_RPC_URL=https://rpc.gnosischain.com

# Override API settings
export COW_API_BASE_URL=http://localhost:8080
export COW_API_TIMEOUT=60

# Override output settings
export COW_OUTPUT_FORMAT=table
export COW_OUTPUT_VERBOSE=true

# Run with overrides
cow-perf run --scenario light-load
```

### Configuration Precedence

Configuration values are resolved in the following order (highest to lowest priority):

1. **Command-line flags**: `--traders 20`, `--duration 300`
2. **Environment variables**: `COW_API_BASE_URL=...`
3. **Scenario file**: Order ratios, trading patterns from scenario YAML
4. **Configuration file**: Settings from `--config` or auto-discovered `.cow-perf.yml`
5. **Default values**: Built-in defaults

Example:
```bash
# Config file says: trader_count=10
# Scenario file says: num_traders=20
# Command line says: --traders 30
# Result: 30 traders (command line wins)

# Config file says: base_url=http://localhost:8080
# Environment says: COW_API_BASE_URL=http://localhost:9000
# Result: http://localhost:9000 (environment wins over config file)
```

---

## Scenario Management

Scenarios define complete test configurations including trader count, duration, order distribution, and trading patterns.

### List Available Scenarios

```bash
# List scenarios in default directory (~/.cow-perf/scenarios)
cow-perf scenarios

# List scenarios in custom directory
cow-perf scenarios --dir ./scenarios

# Filter by tag (must match ALL tags specified)
cow-perf scenarios --tag production --tag smoke-test

# Search by name or description
cow-perf scenarios --search "high frequency"

# Simple view without metadata
cow-perf scenarios --simple

# List available scenario templates
cow-perf scenarios --list-templates
```

**Available Options:**
- `--dir` - Scenarios directory (default: ~/.cow-perf/scenarios)
- `--tag/-t` - Filter by tag (can specify multiple, must match ALL)
- `--search/-s` - Filter by name or description
- `--simple` - Show simple view without metadata
- `--list-templates` - List available scenario templates
- `--validate` - Validate a scenario file
- `--create-template` - Create a scenario template file

### Create Scenario Template

Generate a scenario template file:

```bash
# Create template in current directory
cow-perf scenarios --create-template my-scenario.yml

# Create in scenarios directory
cow-perf scenarios --create-template ~/.cow-perf/scenarios/custom-load.yml
```

### Interactive Configuration Wizard

The `cow-perf config-init` command provides an interactive wizard to create scenario configurations. This is recommended for new users or when you want guided configuration creation.

**Basic usage:**
```bash
# Interactive mode - choose your approach
cow-perf config-init

# Specify output file
cow-perf config-init --output my-test.yml

# Quick start mode (minimal questions)
cow-perf config-init --mode quick --output quick-test.yml

# Template mode (expand from built-in template)
cow-perf config-init --mode template --output spike-test.yml

# Copy existing mode (customize predefined scenario)
cow-perf config-init --mode existing --output custom-test.yml

# Advanced mode (full configuration wizard)
cow-perf config-init --mode advanced --output production-test.yml
```

**Available modes:**

| Mode | Description | Best For |
|------|-------------|----------|
| `interactive` | Let the wizard guide you (default) | First-time users |
| `quick` | Answer a few basic questions | Simple load tests |
| `template` | Select and customize a built-in template | Common test patterns |
| `existing` | Copy and modify a predefined scenario | Customizing known scenarios |
| `advanced` | Full configuration with all options | Production testing |

**Features:**
- Validates configuration before saving
- Shows helpful prompts with defaults
- Displays next steps after generation
- Supports all scenario features (success criteria, metadata, etc.)

**Example quick start session:**
```
$ cow-perf config-init --mode quick

⚡ Quick Start Mode
Answer a few questions to create a basic load test.

Scenario name [Scenario]: Load Test
Description (optional) [Performance test: Load Test]: Testing 10 traders
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

### Scenario File Structure

See [Configuration Reference](configuration-reference.md) for the complete field schema, descriptions, and examples.

### Validate Scenario

Check if a scenario file is valid:

```bash
# Validate scenario file
cow-perf scenarios --validate my-scenario.yml

# Output shows validation results and scenario details
```

### Trading Patterns

See [Configuration Reference: Trading Patterns](configuration-reference.md#trading-patterns) for all patterns, their parameters, and usage guidelines.

---

## Baseline Management

Baselines allow you to save performance test results and compare future runs for regression detection.

**For complete baseline management documentation**, see [Reports & Baselines Guide](reports.md#managing-baselines).

**Quick reference:**

```bash
# Save baseline during test run
cow-perf run --config scenario.yml --save-baseline v1.0

# List all baselines
cow-perf baselines --list

# Show baseline details
cow-perf baselines --show v1.0

# Delete baseline
cow-perf baselines --delete v1.0
```

---

## Running Performance Tests

Execute performance tests with configured scenarios:

```bash
# Run with predefined scenario
cow-perf run --scenario light-load

# Run with custom scenario file
cow-perf run --scenario ./my-scenario.yml

# Run with custom parameters
cow-perf run --traders 20 --duration 300

# Run and compare against baseline
cow-perf run --scenario medium-load --baseline v1.0

# Run with specific configuration
cow-perf run --config ./config.yml --scenario light-load
```

### Available Run Options

- `--config/-c` - Configuration file path
- `--scenario/-s` - Scenario name or file path
- `--traders/-t` - Number of concurrent traders
- `--duration/-d` - Test duration in seconds
- `--settlement-wait/-w` - Settlement wait time in seconds (default: 300)
- `--baseline/-B` - Baseline to compare against
- `--save-baseline/-b` - Save results as baseline with given name
- `--baseline-description` - Description for saved baseline
- `--baseline-tags` - Comma-separated tags for baseline (e.g. "production,v1.0")
- `--prometheus-port` - Port for Prometheus metrics exporter (default: 9091, 0 to disable)
- `--output-format` - Output format: json, table, csv, prometheus
- `--save-results` - Save results to file
- `--verbose/-v` - Enable verbose logging

### Real-Time Metrics Export

Prometheus metrics export is **enabled by default** on port 9091. During test execution, metrics are exposed at `http://localhost:9091/metrics` for Prometheus scraping.

```bash
# Run with default Prometheus export (port 9091)
cow-perf run --config configs/scenarios/predefined/light-load.yml

# Use a different port
cow-perf run --config configs/scenarios/predefined/light-load.yml --prometheus-port 9092

# Disable Prometheus export
cow-perf run --config configs/scenarios/predefined/light-load.yml --prometheus-port 0
```

**Using with Docker monitoring stack:**

```bash
# Start Prometheus and Grafana
docker compose --profile monitoring up -d

# Run test (metrics automatically available to Prometheus)
cow-perf run --config configs/scenarios/predefined/light-load.yml

# View dashboards at http://localhost:3000
```

---

## Output Formats

The CLI supports multiple output formats for different use cases:

```bash
# JSON output - for programmatic processing and APIs
cow-perf run --config my-test.yml --output-format json --save-results

# Table output - human-readable terminal display (default for console)
cow-perf run --config my-test.yml --output-format table

# CSV output - for spreadsheet analysis and data processing
cow-perf run --config my-test.yml --output-format csv --save-results

# Prometheus format - for metrics collection and monitoring
cow-perf run --config my-test.yml --output-format prometheus --save-results
```

You can also configure the output format in your YAML config file:

```yaml
output:
  format: "prometheus"  # json, table, csv, prometheus
  save_results: true
  results_dir: "./results"
```

### Prometheus Output Format

When using `--output-format prometheus`, the CLI generates metrics in Prometheus text exposition format, ready to be scraped or pushed to Prometheus.

**Example Prometheus output:**

```
# HELP cow_perf_orders_per_second CoW Protocol performance test metric
# TYPE cow_perf_orders_per_second gauge
cow_perf_orders_per_second 0.6969890196125873

# HELP cow_perf_avg_order_latency_ms CoW Protocol performance test metric
# TYPE cow_perf_avg_order_latency_ms gauge
cow_perf_avg_order_latency_ms 1434.742832183838

# HELP cow_perf_orders_total CoW Protocol performance test metric
# TYPE cow_perf_orders_total gauge
cow_perf_orders_total 5.0
```

**Available Prometheus metrics:**

Performance metrics:
- `cow_perf_orders_per_second` - Throughput (orders/sec)
- `cow_perf_avg_order_latency_ms` - Average order latency

Order type metrics:
- `cow_perf_orders_total` - Total orders submitted
- `cow_perf_orders_market` - Market orders count
- `cow_perf_orders_limit` - Limit orders count
- `cow_perf_orders_twap` - TWAP orders count
- `cow_perf_orders_stop_loss` - Stop-loss orders count
- `cow_perf_orders_good_after_time` - Good-after-time orders count

Orchestration metrics:
- `cow_perf_duration_seconds` - Test duration
- `cow_perf_traders_active` - Number of active traders
- `cow_perf_traders_total` - Total number of traders

### Prometheus Integration

**1. Push to Prometheus Pushgateway** (recommended for batch jobs):

```bash
# Run test and save Prometheus metrics
cow-perf run --config test.yml --output-format prometheus --save-results

# Push to Pushgateway
cat results/perf-test-*.txt | \
  curl --data-binary @- http://pushgateway:9091/metrics/job/cow_perf_test
```

**2. Node Exporter textfile collector**:

```bash
# Configure output directory to node exporter's textfile directory
cow-perf run --config test.yml --output-format prometheus \
  --output-file /var/lib/node_exporter/textfile_collector/cow_perf.prom
```

**3. Custom HTTP endpoint** (requires additional service):

```bash
# Save to directory served by HTTP
cow-perf run --config test.yml --output-format prometheus \
  --output-file /var/www/metrics/cow_perf.txt
```

**Example Prometheus scrape config:**

```yaml
scrape_configs:
  - job_name: 'cow_performance'
    honor_labels: true
    static_configs:
      - targets: ['pushgateway:9091']
```

---

## Docker Usage

### Service URLs

Once the environment is running, the following services are available:

| Service | URL | Description |
|---------|-----|-------------|
| Anvil RPC | http://localhost:8545 | Forked Ethereum node |
| Orderbook API | http://localhost:8080 | CoW Protocol orderbook |
| Driver | http://localhost:9000 | Driver service |
| Baseline Solver | http://localhost:9001 | AMM-based solver |
| PostgreSQL | localhost:5432 | Database |
| Prometheus | http://localhost:9090 | Metrics (with monitoring profile) |
| Grafana | http://localhost:3000 | Dashboards (with monitoring profile) |

### Common Docker Commands

```bash
# Start core services
docker compose up -d

# Start with monitoring (Prometheus & Grafana)
docker compose --profile monitoring up -d

# View logs
docker compose logs -f

# Check service status
docker compose ps

# Stop services
docker compose down

# Stop and remove volumes (fresh start)
docker compose down -v

# View resource usage
docker stats

# Restart a specific service
docker compose restart orderbook
```

### Building Custom Image

```bash
# Build the Docker image
docker build -t cow-performance-testing-suite -f docker/Dockerfile .

# Run in Docker
docker run cow-performance-testing-suite --help

# Run a scenario
docker run -v $(pwd)/configs:/app/configs \
  cow-performance-testing-suite run --scenario light-load
```

### Verifying the Environment

```bash
# Check if Anvil is running
cast block-number --rpc-url http://localhost:8545

# Check orderbook API
curl http://localhost:8080/api/v1/version

# Check all services status
docker compose ps

# Check database
docker exec $(docker ps -qf "name=db") pg_isready -U postgres
```

### Troubleshooting

#### Services failing to start

```bash
# Check logs
docker compose logs orderbook
docker compose logs autopilot
docker compose logs driver

# Restart a specific service
docker compose restart orderbook

# Rebuild and restart
docker compose up -d --build orderbook
```

#### Database connection issues

```bash
# Check database is running
docker compose ps db

# Check database logs
docker compose logs db

# Reset database
docker compose down -v
docker compose up -d
```

#### Anvil fork issues

Make sure your `ETH_RPC_URL` in `.env` is:
- A valid Ethereum mainnet RPC URL
- Has sufficient rate limits
- Supports `eth_blockNumber` and archive state queries

#### Out of memory

Increase Docker memory limit to at least 8GB:
- Docker Desktop -> Settings -> Resources -> Memory

---

## Report Commands

Generate performance reports from saved baselines with comprehensive metrics analysis.

**For complete report generation documentation**, see [Reports & Baselines Guide](reports.md#generating-reports).

**Quick reference:**

```bash
# Generate text report
cow-perf report generate my-baseline

# Generate markdown report with comparison
cow-perf report generate v2.0 --compare v1.0 -f markdown --save

# Export metrics as CSV
cow-perf report generate my-baseline --export-csv ./csv/
```

**Exit codes:** 0 = Success, 1 = Error, 2 = Performance regression detected

---


## Example Workflows

### Setup New Project

```bash
# 1. Create configuration file
cow-perf config --save-template .cow-perf.yml

# 2. Edit configuration as needed
vim .cow-perf.yml

# 3. Create scenarios directory
mkdir -p scenarios

# 4. Create test scenario
cow-perf scenarios --create-template scenarios/my-test.yml

# 5. Edit scenario
vim scenarios/my-test.yml

# 6. Validate scenario
cow-perf scenarios --validate scenarios/my-test.yml

# 7. Run test
cow-perf run --scenario scenarios/my-test.yml
```

### Baseline Comparison Workflow

```bash
# 1. Run initial test and save as baseline
cow-perf run --scenario load-test --save-baseline v1.0 \
  --baseline-description "Initial baseline before changes"

# 2. Make changes to system
# ... deploy updates, configuration changes, etc.

# 3. Run test again and compare
cow-perf run --scenario load-test --baseline v1.0

# 4. View baseline details
cow-perf baselines --show v1.0
```

### Multi-Environment Testing

```bash
# Test against local environment and save baseline
export COW_API_BASE_URL=http://localhost:8080
cow-perf run --scenario load-test --save-baseline local \
  --baseline-tags "environment:local"

# Test against staging and save baseline
export COW_API_BASE_URL=https://staging-api.cow.fi
cow-perf run --scenario load-test --save-baseline staging \
  --baseline-tags "environment:staging"

# Test against production (read-only)
export COW_API_BASE_URL=https://api.cow.fi
cow-perf run --scenario read-only-test --save-baseline prod \
  --baseline-tags "environment:production,read-only"

# Compare results
cow-perf baselines --show local
cow-perf baselines --show staging
cow-perf baselines --show prod
```
