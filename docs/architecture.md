# Architecture Overview

This document outlines the architecture and design decisions for the CoW Performance Testing Suite.

## System Overview

The CoW Performance Testing Suite is designed as an independent, Python-based tool for comprehensive performance testing of the CoW Protocol Playground. The system operates primarily in **fork mode**, using Anvil to fork mainnet state for realistic testing.

## High-Level Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                       CLI Interface (Typer)                       │
│     run · scenarios · baselines · report · config · config-init · version   │
└──┬──────────┬──────────┬──────────────┬────────────┬────────────┘
   │          │          │              │            │
   ▼          ▼          ▼              ▼            ▼
┌──────────┐ ┌──────────────┐ ┌───────────┐ ┌──────────┐ ┌─────────────────────┐
│Scenarios │ │     Load     │ │ Baselines │ │Reporting │ │   Benchmarking      │
│          │ │  Generation  │ │           │ │          │ │ (Scaling/Complexity)│
└──────────┘ └──────┬───────┘ └─────┬─────┘ └────┬─────┘ └─────────────────────┘
                    │               │             │
                    ▼               ▼             │
             ┌──────────┐    ┌──────────────┐    │
             │   API    │    │  Comparison  │◀───┘
             │(Orderbook│    │    Engine    │
             │  Client) │    └──────┬───────┘
             └─────┬────┘           │
                   │         ┌──────▼──────┐
                   │         │  Reporting  │
                   │         └─────────────┘
                   ▼
   ┌──────────────────────────────────────┐
   │    CoW Protocol Services (Docker)    │
   │  ┌────────────┐  ┌─────────────┐   │
   │  │ Orderbook  │  │  Autopilot  │   │
   │  │    API     │  │   Driver    │   │
   │  └────────────┘  │   Solver    │   │
   │                  └─────────────┘   │
   └──────────────────┬──────────────────┘
                      ▼
           ┌──────────────────┐
           │  Anvil Fork Mode │
           │  (Mainnet State) │
           └──────────────────┘

Observability layer (runs in parallel during test execution):
┌──────────────────────┐  ┌──────────────────────┐  ┌────────────────────┐
│  metrics/            │  │  monitoring/         │  │  prometheus/       │
│  (MetricsStore,      │  │  (ResourceMonitor —  │  │  (Prometheus HTTP  │
│   aggregation,       │  │   Docker CPU/memory) │  │   exporter)        │
│   streaming)         │  └──────────────────────┘  └────────────────────┘
└──────────────────────┘
```

## Core Components

### 1. CLI Interface (`cli/`)

**Responsibility**: User interaction and command orchestration

**Design**:
- Built with Typer for rich CLI experience
- Commands: `run`, `scenarios`, `baselines`, `report`, `config`, `config-init`, `version`
- Handles argument parsing, validation, and progress display
- `run` transparently calls `scale_command` internally when `scaling.enabled` is set in config; `scale` is not a standalone CLI command

### 2. Load Generation (`load_generation/`)

**Responsibility**: Generate and submit orders to the orderbook

**Components**:
- **Order Factory** (`order_factory.py`): Creates CoW Protocol-compatible signed orders
  - Supports market and limit orders
  - Configurable token pairs and amounts
  - EIP-712 signing via `order_signer.py`
- **Trader Simulation** (`trader_simulator.py`, `trader_orchestrator.py`, `trader_account.py`): Manages concurrent test accounts
  - Account generation and wallet funding
  - Safe wallet support (`safe_wallet.py`)
  - Balance and approval tracking
- **Trading Patterns** (`trader_simulator.py`): Controls order submission timing via `TradingPattern` enum
  - `constant_rate`, `random_interval`, `burst`, `time_based`, `ramp_up`, `ramp_down`, `spike`, `poisson`
  - Configured declaratively through `TraderBehaviorConfig`
- **Order Tracking** (`order_tracker.py`): Monitors submitted order lifecycle states

**Key Design Decisions**:
- Asynchronous architecture using `asyncio` for concurrent operations
- Rate limiting to prevent overwhelming the system

### 3. API (`api/`)

**Responsibility**: HTTP communication with the CoW Protocol Orderbook API

**Components**:
- **OrderbookClient** (`orderbook_client.py`): Async client for order submission, status queries, and appData uploads
- **InstrumentedClient** (`instrumented_client.py`): Wraps `OrderbookClient` and records API latency and error metrics into `MetricsStore`

### 4. Metrics (`metrics/`)

**Responsibility**: In-process metrics collection and aggregation

**Components**:
- **MetricsStore** (`store.py`): Central in-memory store for order, API, and resource samples; supports registered callbacks for live consumers
- **MetricsAggregator** (`aggregator.py`): Computes percentile stats (P50/P90/P95/P99) over stored samples
- **MetricsEventStream** (`streaming.py`): Async iterator that streams `MetricEvent` objects in real time; `RollingMetricsSummary` maintains a sliding window for live dashboards
- **ExpirationChecker** (`expiration_checker.py`): Polls open orders and marks them expired when their deadline passes

**Key Design Decisions**:
- Thread-safe concurrent access via callbacks
- Efficient circular buffers for rolling windows
- Prometheus-compatible metric naming

### 5. Monitoring (`monitoring/`)

**Responsibility**: Docker container resource monitoring

**Components**:
- **ResourceMonitor** (`resource_monitor.py`): Polls Docker Engine API for CPU, memory, network, and I/O stats across CoW Protocol service containers (orderbook, autopilot, driver, solver, chain); writes `ResourceSample` objects into `MetricsStore`

### 6. Prometheus (`prometheus/`)

**Responsibility**: Expose metrics in Prometheus format over HTTP

**Components**:
- **PrometheusExporter** (`exporter.py`): HTTP server that serves `/metrics`; subscribes to `MetricsStore` callbacks and updates gauge/counter/histogram metrics defined in `metrics.py`

### 7. Baselines (`baselines/`)

**Responsibility**: Persist and retrieve performance snapshots

**Components**:
- **BaselineManager** (`manager.py`): CRUD operations over JSON baseline files; maintains an `index.json` for efficient listing
- **Models** (`models.py`): `PerformanceBaseline` and `BaselineMetadata` Pydantic models
- **Git Info** (`git_info.py`): Captures current git commit, branch, and dirty state as baseline metadata
- **Validation** (`validation.py`): Schema version checks and structural validation

### 8. Comparison (`comparison/`)

**Responsibility**: Statistical comparison between two baselines

**Components**:
- **ComparisonEngine** (`engine.py`): Compares aggregated metrics, calculates percent changes, and classifies regressions by severity
- **Statistics** (`statistics.py`): Percent-change calculation, effect-size interpretation, percentile comparison helpers
- **Thresholds** (`thresholds.py`): Configurable regression threshold definitions
- **Models** (`models.py`): `ComparisonResult` and `MetricComparison` data classes

### 9. Reporting (`reporting/`)

**Responsibility**: Format and export test results and comparison reports

**Components**:
- **ReportGenerator** (`generator.py`): Orchestrates summary generation, recommendations, and output formatting
- **Formatters** (`formatters/`): Text, Markdown, and JSON output formats
- **CSVExporter** (`csv_export.py`): Exports raw metrics as CSV
- **RecommendationsEngine** (`recommendations.py`): Generates actionable insights from results
- **Summary** (`summary.py`): Produces executive-summary statistics

### 10. Benchmarking (`benchmarking/`)

**Responsibility**: Scaling experiments and algorithmic complexity analysis

**Components**:
- **ComplexityAnalyzer** (`complexity.py`): Fits a power-law model (log-log regression) to (order-count, latency) measurement pairs and classifies the exponent into O(n), O(n log n), O(n²), etc.
- **DockerMemorySampler** (`memory_sampler.py`): Captures container RSS before and after each scaling phase to detect memory growth
- **ScalingReport** (`scaling_report.py`): Data models and text/JSON formatting for multi-phase scaling experiment results

The scaling experiment is triggered by setting `scaling.enabled = true` in the config and running `cow-perf run`; this causes `run` to invoke `scale_command` internally, which runs a doubling sequence of order counts and feeds results through these components to characterise system behaviour under increasing load.

### 11. Scenarios (`scenarios/`)

**Responsibility**: Test scenario configuration and validation

**Components**:
- **Scenario Loader / Validator** (`config_validation.py`, `validation.py`): Loads YAML files and validates against Pydantic models
- **Inheritance** (`inheritance.py`): Resolves `extends:` references between scenario files
- **Templates** (`templates.py`): Built-in scenario templates
- **Generator** (`generator.py`): Programmatic scenario creation
- **Profiles** (`profiles.py`): Named configuration presets

**Key Design Decisions**:
- Declarative scenario definitions with Pydantic validation
- Scenario reusability via inheritance and composition

## Data Flow

### Test Execution Flow

```
1. User runs CLI command
   ↓
2. Load scenario configuration
   ↓
3. Initialize components:
   - Trader pool (with automatic wallet funding if enabled)
   - Order factory
   - Metrics collector
   - Resource monitor
   ↓
3a. Fund Wallets (if enabled):
   - Transfer ETH from Anvil default account
   - Set token balances via storage slot manipulation
   - Approve tokens for VaultRelayer contract
   ↓
4. Execute submission strategy:
   - Generate orders
   - Sign with traders
   - Submit to orderbook API
   - Track order lifecycle
   ↓
5. Collect metrics:
   - Order states
   - API responses
   - Resource usage
   ↓
6. Generate reports:
   - Summary statistics
   - Comparison (if baseline)
   - Export formats (text, JSON, CSV)
   ↓
7. Save baseline (optional)
```

### Metrics Collection Flow

```
Order Creation
   ↓
Order Submission → API Metrics
   ↓
Orderbook Acceptance
   ↓
Order Filling → Settlement Metrics
   ↓
Settlement Completion
   ↓
Aggregation & Export → Prometheus
```


## Technology Stack

### Core Technologies
- **Python 3.11+**: Modern Python with type hints and async support
- **Typer**: CLI framework
- **Pydantic**: Data validation and settings management
- **aiohttp**: Async HTTP client
- **web3.py**: Ethereum interactions
- **eth-account**: Transaction signing

### Testing & Quality
- **pytest**: Testing framework
- **pytest-asyncio**: Async test support
- **black**: Code formatting
- **ruff**: Fast Python linter
- **mypy**: Static type checking

### DevOps
- **Poetry**: Dependency management
- **Docker**: Containerization
- **GitHub Actions**: CI/CD
- **pre-commit**: Git hooks

## Design Principles

### 1. Asynchronous First
All I/O operations (API calls, file operations) use async/await for maximum concurrency and throughput.

### 2. Type Safety
Comprehensive type hints throughout the codebase, enforced by mypy in strict mode.

### 3. Configuration over Code
Test scenarios are defined in YAML configuration files, not hardcoded in Python.

### 4. Separation of Concerns
Clear boundaries between load generation, metrics collection, benchmarking, and reporting.

### 5. Testability
Components are designed for easy unit testing with dependency injection and mocking.

### 6. Observability
Comprehensive logging, metrics export, and progress feedback for visibility into test execution.

## Fork Mode Architecture

### Environment Setup

```
┌──────────────────────────────────────────────────┐
│           Docker Compose Environment              │
│                                                   │
│  ┌─────────────┐     ┌──────────────┐           │
│  │   Anvil     │────▶│  Orderbook   │           │
│  │ (Fork Mode) │     │     API      │           │
│  └─────────────┘     └──────┬───────┘           │
│         ▲                    │                   │
│         │            ┌───────▼────────┐          │
│         │            │   Autopilot    │          │
│    Archive Node      │     Driver     │          │
│    (External)        │     Solver     │          │
│         │            └────────────────┘          │
│         │                                        │
│  ┌──────▼──────────────────────────────────┐   │
│  │   Performance Testing Suite Container    │   │
│  │   (runs cow-perf CLI)                    │   │
│  └──────────────────────────────────────────┘   │
│                                                   │
│  ┌──────────────┐     ┌──────────────┐          │
│  │  Prometheus  │────▶│   Grafana    │          │
│  └──────────────┘     └──────────────┘          │
└──────────────────────────────────────────────────┘
```

### Key Characteristics

- **Realistic State**: Tests against actual mainnet state at specific block
- **Deterministic**: Same fork point produces consistent results
- **Isolated**: No mainnet transactions, no gas costs
- **Fast**: Instant mining, no block delays

## Extension Points

### Custom Trading Patterns

Add a new value to `TradingPattern` in `trader_simulator.py`, add a corresponding `_<pattern>_loop` coroutine to `TraderSimulator`, and dispatch it in the `run()` method's `if/elif` chain. Configure it via `TraderBehaviorConfig` in YAML:

```yaml
trading_pattern: my_custom_pattern
```

There is no base class to subclass — patterns are enum values dispatched inside `TraderSimulator`.

### Custom Metrics

Register a callback on `MetricsStore` to receive live metric events:
```python
def my_callback(metric_type: str, metric: object) -> None:
    # handle order, api, or resource samples
    ...

metrics_store.register_callback(my_callback)
```

For Prometheus-style export, add new gauge/counter/histogram definitions to `prometheus/metrics.py` and update `PrometheusExporter` to populate them.

### Custom Scenarios

Create YAML scenario files in `configs/scenarios/`.

## Performance Considerations

### Scalability
- Supports up to 100 concurrent traders
- Throughput: 100+ orders/second (hardware dependent)
- Metrics overhead: <5% of CPU

### Resource Usage
- Memory: ~500MB base + ~10MB per concurrent trader
- CPU: Scales with order rate and number of traders
- Network: Depends on API response sizes

### Optimization Strategies
- Connection pooling
- Batch operations where possible
- Efficient data structures
- Lazy evaluation of derived metrics

## Future Enhancements

### Planned Features
- Historical trend analysis across many baseline runs
- Advanced statistical analysis (time series forecasting)
- Distributed load generation (multiple test runners)
- Custom reporter plugins

### Potential Improvements
- Parallel scenario execution
- Warm-up phases
- Think time simulation
- More sophisticated trader behaviors

## Security Considerations

- Test accounts use generated private keys (never use with real funds)
- Archive node URL may contain sensitive credentials (use environment variables)
- Baseline data may contain system information (review before sharing)
- Docker containers run with minimal privileges

## Maintenance

### Code Organization
- Keep modules focused and cohesive
- Maintain clear interfaces between components
- Document public APIs
- Write comprehensive tests

### Documentation
- Keep architecture docs in sync with code
- Document design decisions
- Provide examples for common use cases
- Maintain changelog

## References

- [CoW Protocol Documentation](https://docs.cow.fi/)
- [Anvil Documentation](https://book.getfoundry.sh/anvil/)
- [Performance Testing Best Practices](https://martinfowler.com/articles/practical-test-pyramid.html)
