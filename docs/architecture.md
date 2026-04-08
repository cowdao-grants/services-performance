# Architecture Overview

This document outlines the architecture and design decisions for the CoW Performance Testing Suite.

## System Overview

The CoW Performance Testing Suite is designed as an independent, Python-based tool for comprehensive performance testing of the CoW Protocol Playground. The system operates primarily in **fork mode**, using Anvil to fork mainnet state for realistic testing.

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      CLI Interface (Typer)                       │
│                    cow-perf [command] [options]                  │
└───────────────────────────┬─────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
        ▼                   ▼                   ▼
┌───────────────┐  ┌────────────────┐  ┌──────────────────┐
│   Scenario    │  │  Benchmarking  │  │     Metrics      │
│  Management   │  │   & Reporting  │  │   & Monitoring   │
└───────┬───────┘  └────────┬───────┘  └────────┬─────────┘
        │                   │                    │
        └───────────────────┼────────────────────┘
                            ▼
                ┌─────────────────────┐
                │  Load Generation    │
                │  - Order Factory    │
                │  - Trader Pool      │
                │  - Strategies       │
                └──────────┬──────────┘
                           │
                           ▼
        ┌──────────────────────────────────────┐
        │    CoW Protocol Services (Docker)     │
        │  ┌────────────┐  ┌─────────────┐    │
        │  │ Orderbook  │  │  Autopilot  │    │
        │  │    API     │  │   Driver    │    │
        │  └────────────┘  │   Solver    │    │
        │                  └─────────────┘    │
        └──────────────────┬───────────────────┘
                           │
                           ▼
                ┌──────────────────┐
                │  Anvil Fork Mode │
                │  (Mainnet State) │
                └──────────────────┘
```

## Core Components

### 1. CLI Interface (`cli/`)

**Responsibility**: User interaction and command orchestration

**Design**:
- Built with Typer for rich CLI experience
- Commands: `run`, `scenarios`, `baselines`, `config`
- Handles argument parsing and validation
- Provides progress feedback and results display

**Key Classes**:
- `PerformanceTestCLI`: Main CLI application
- Command handlers for each subcommand

### 2. Load Generation (`load_generation/`)

**Responsibility**: Generate and submit orders to the orderbook

**Components**:
- **Order Factory**: Creates CoW Protocol compatible orders
  - Supports market and limit orders
  - Configurable token pairs and amounts
  - EIP-712 signing
- **Trader Pool**: Manages test accounts
  - Account generation and funding
  - Signing operations
  - Balance tracking
- **Submission Strategies**: Control order submission patterns
  - Constant rate
  - Burst patterns
  - Ramp-up/ramp-down
  - Spike patterns
  - Poisson distribution

**Key Design Decisions**:
- Asynchronous architecture using `asyncio` for concurrent operations
- Connection pooling for API requests
- Rate limiting to prevent overwhelming the system

### 3. Benchmarking (`benchmarking/`)

**Responsibility**: Performance measurement and analysis

**Components**:
- **Metrics Collector**: Captures performance data
  - Order lifecycle tracking
  - API response times
  - Resource utilization
- **Baseline Manager**: Stores and retrieves performance baselines
  - Git-integrated versioning
  - JSON storage format
  - Metadata tracking
- **Comparison Engine**: Analyzes performance changes
  - Statistical comparison
  - Regression detection
  - Severity classification

**Key Design Decisions**:
- In-memory metrics storage with periodic export
- Percentile-based analysis (P50, P90, P95, P99)
- Statistical significance testing for regressions

### 4. Metrics (`metrics/`)

**Responsibility**: Metrics collection, aggregation, and export

**Components**:
- **Order Lifecycle Tracker**: Monitors orders from creation to settlement
- **API Metrics**: Tracks API performance
- **Resource Monitor**: Monitors Docker container resources
- **Prometheus Exporter**: Exposes metrics in Prometheus format

**Key Design Decisions**:
- Real-time metrics updates
- Thread-safe concurrent access
- Efficient data structures (circular buffers)
- Prometheus-compatible metric naming

### 5. Scenarios (`scenarios/`)

**Responsibility**: Test scenario configuration and execution

**Components**:
- **Scenario Loader**: Loads and validates scenario configurations
- **Scenario Executor**: Orchestrates test execution
- **Configuration System**: Flexible YAML-based configuration
  - Template support
  - Inheritance/composition
  - Environment variable substitution

**Key Design Decisions**:
- Declarative scenario definitions
- Validation with Pydantic
- Scenario reusability and composition

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

### Chain Reconciliation Flow

```
Test Completion
  ↓
Query On-Chain Trade Events
  ↓
Extract Filled Orders (from event logs)
  ↓
Query Database for Same Orders
  ↓
Compare: Database vs On-Chain Status
  ↓
Update Database with Correct Statuses
  ↓
Update Prometheus Metrics
  ↓
Report Discrepancies (if any)
```

**Purpose**: Resolve event sync issues in Anvil fork mode where `eth_getLogs` doesn't return events from transactions in the same block.

**Implementation**: `src/cow_performance/chain_reconciliation.py`

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

### Custom Submission Strategies

Implement `SubmissionStrategy` interface:
```python
class CustomStrategy(SubmissionStrategy):
    async def generate_submission_times(self, duration: int):
        # Your implementation
        pass
```

### Custom Metrics

Add to `MetricsCollector`:
```python
def collect_custom_metric(self, name: str, value: float):
    self.custom_metrics[name] = value
```

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
- Historical trend analysis
- Advanced statistical analysis (time series forecasting)
- Distributed load generation (multiple test runners)
- Real-time dashboard updates
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
