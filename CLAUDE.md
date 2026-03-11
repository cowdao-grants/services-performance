# CLAUDE.md

## What This Project Is

Performance testing suite for CoW Protocol. Generates load, captures metrics, and benchmarks solver performance in a forked Ethereum environment using Anvil.

**Tech**: Python 3.11+, Poetry, Docker Compose, Typer CLI, Web3.py

## Architecture

```
CLI (Typer) → Load Generation → CoW Protocol Services (Docker)
                             → Metrics Collection → Benchmarking
```

**Key paths**:
- `src/cow_performance/` - Core modules (load_generation, benchmarking, metrics, scenarios)
- `src/cow_performance/cli/` - CLI commands built with Typer
- `tests/` - Unit and integration tests
- `docker/` - Docker Compose configuration for CoW services
- `configs/` - Configuration files (baseline.toml, driver.toml, prometheus.yml)

## How to Verify Changes

```bash
poetry run pytest          # Run tests
poetry run ruff check .    # Lint
poetry run mypy .          # Type check
poetry run black --check . # Format check
```

## Docker Services

```bash
docker compose up -d       # Start CoW Protocol services
docker compose down        # Stop services
docker compose logs -f     # View logs
```

## Documentation Navigation

| What you need | Read this |
|---------------|-----------|
| Get started quickly | `README.md` |
| CLI commands and config | `docs/cli.md` |
| Development setup | `docs/development.md` |
| System architecture | `docs/architecture.md` |
| Order generation API | `docs/order-generation.md` |
| TWAP, Stop-Loss orders | `docs/conditional-orders.md` |
| Trader simulation | `docs/user-simulation.md` |
| Contributing | `CONTRIBUTING.md` |
| Utility scripts | `hack/CLAUDE.md` |
| Project scope and milestones | `thoughts/context/grant-proposal.md` |
| **Thoughts index (start here)** | `thoughts/INDEX.md` |

## Working Conventions

- **Check `thoughts/INDEX.md` first** before starting work - it catalogs all existing plans, research, and tickets
- Save analysis, plans, and reasoning to `thoughts/` directory
- Follow existing code patterns - the codebase is the source of truth for style
- Use Pydantic for data validation and configuration
- All async operations should use `asyncio` with proper concurrency patterns
- Type hints are required on all functions
- Google-style docstrings for documentation

## README.md Organization

The root README.md must follow a **chronological user journey** structure, prioritizing actionable content:

1. **Quick Start** - Installation, requirements, environment setup, and first test run
2. **Running Tests** - How to run performance tests, available scenarios (brief overview)
3. **Viewing Results** - Reports, baselines, comparison, regression detection
4. **Monitoring** - Prometheus, Grafana, dashboards (optional/advanced)
5. **Advanced Topics** - Detailed scenario management, custom scenarios, disk management
6. **Reference** - Documentation links, project structure, contributing, roadmap

**Key principles:**
- Early sections are action-oriented ("how to do X"), not reference material
- Detailed reference information belongs in later "Advanced" sections
- Users should be able to get started quickly without scrolling past extensive details
- Follow the natural workflow: install → run → view results → advanced usage
