# Thoughts Directory Index

> **For AI Agents**: Start here to find relevant documentation without reprocessing existing work.

## Quick Reference

| Task | Start Here |
|------|------------|
| Understand project scope | [grant-proposal.md](context/grant-proposal.md) |
| Find a ticket's details | [tickets/](#tickets) |
| Find implementation approach | [plans/](#implementation-plans) |
| Check what's been researched | [research/](#research) |
| Review investigation reports | [reports/](#reports) |
| Find reusable prompts | [prompts/](#prompts) |
| Review code audits | [audits/](#audits) |

**Note:** `thoughts/private/` holds internal-only material (design decisions, testing guides, validations, etc.). It is in `.gitignore` and is **not committed**; this index does not list its contents in detail.

## Current Project Status

**Completed Milestones**: M2 (Performance Benchmarking)
**Active Work**: M4 (Scenario System & Configuration)
**Next Milestone**: M3 (Metrics & Visualization) - COW-591, COW-593, COW-598

> **For M3 developers**: Each completed M2 ticket (COW-588, COW-589, COW-590) includes an "Implementation Notes" section at the bottom documenting architectural decisions and deviations from the original scope. Review these before starting M3 to understand what was built vs. what was deferred.

### M2 - Performance Benchmarking (COMPLETE)

| Ticket | Status | Description |
|--------|--------|-------------|
| COW-587 | ✅ Done | Metrics Collection Framework (parent) |
| COW-609 | ✅ Done | Data Models & Storage |
| COW-610 | ✅ Done | Collection Lifecycle & API Monitoring |
| COW-611 | ✅ Done | Analysis & Aggregation |
| COW-588 | ✅ Done | Baseline Snapshot System |
| COW-589 | ✅ Done | Comparison Engine & Regression Detection |
| COW-590 | ✅ Done | Automated Reporting |
| COW-608 | ✅ Done | README Restructuring |

### M4 - Scenario System & Configuration (IN PROGRESS)

| Ticket | Status | Description |
|--------|--------|-------------|
| M4-Issue-14 | ✅ Done | Predefined Test Scenarios Library |
| M4-Issue-15 | ✅ Done | Enhanced Configuration Architecture |

**Recent Completion**: Configuration system with templates, interactive wizard (`cow-perf config-init`), and comprehensive documentation (user guide, configuration reference, best practices).

### M3 - Metrics & Visualization (QUEUED)

| Ticket | Status | Description |
|--------|--------|-------------|
| COW-591 | 🔲 Todo | Prometheus Exporters |
| COW-593 | 🔲 Todo | Grafana Dashboards |
| COW-598 | 🔲 Todo | Alerting Rules |

---

## Directory Structure

```
thoughts/
├── INDEX.md           # ← You are here
├── analysis/          # Deep-dive analysis documents
├── audits/            # Code quality and production readiness audits
├── bugfixes/          # Bug investigation and fix documentation
├── context/           # Project background, grants, scope
├── plans/             # Implementation plans for tickets
├── private/           # Internal-only (not committed; contents not listed here)
├── prompts/           # Reusable agent prompts
├── reports/           # Investigation reports and analysis
├── research/          # Research and investigation documents
└── tickets/           # Local copies of Linear tickets
```

---

## Tickets

Local copies of Linear tickets. **These are the source of truth** - do not update Linear directly unless explicitly asked.

| File | ID | Status | Milestone | Notes | Keywords |
|------|----|--------|-----------|-------|----------|
| [COW-587-metrics-collection-framework.md](tickets/COW-587-metrics-collection-framework.md) | COW-587 | ✅ Done | M2 | | metrics, collection, parent-ticket |
| [COW-588-baseline-snapshot-system.md](tickets/COW-588-baseline-snapshot-system.md) | COW-588 | ✅ Done | M2 | 📝 | baseline, snapshots, comparison |
| [COW-589-comparison-engine-regression-detection.md](tickets/COW-589-comparison-engine-regression-detection.md) | COW-589 | ✅ Done | M2 | 📝 | comparison, regression, statistics |
| [COW-590-automated-reporting.md](tickets/COW-590-automated-reporting.md) | COW-590 | ✅ Done | M2 | 📝 | reporting, formatters, CSV, recommendations |
| [COW-591-prometheus-exporters.md](tickets/COW-591-prometheus-exporters.md) | COW-591 | 🔲 Todo | M3 | | prometheus, metrics, exporters, monitoring |
| [COW-593-grafana-dashboards.md](tickets/COW-593-grafana-dashboards.md) | COW-593 | 🔲 Todo | M3 | | grafana, dashboards, visualization |
| [COW-598-alerting-rules.md](tickets/COW-598-alerting-rules.md) | COW-598 | 🔲 Todo | M3 | | alerting, prometheus, notifications |

> 📝 = Has "Implementation Notes" section with architectural decisions and deviations
| [COW-608-readme-restructuring.md](tickets/COW-608-readme-restructuring.md) | COW-608 | ✅ Done | - | | documentation, README |
| [COW-609-foundation-data-models-storage.md](tickets/COW-609-foundation-data-models-storage.md) | COW-609 | ✅ Done | M2 | | data-models, MetricsStore, export |
| [COW-610-collection-lifecycle-api-monitoring.md](tickets/COW-610-collection-lifecycle-api-monitoring.md) | COW-610 | ✅ Done | M2 | | lifecycle, API, resource-monitoring |
| [COW-611-analysis-aggregation-realtime.md](tickets/COW-611-analysis-aggregation-realtime.md) | COW-611 | ✅ Done | M2 | | aggregation, percentiles, streaming |

### Ticket Hierarchy

```
COW-587 (Metrics Collection Framework) ─ PARENT
├── COW-609 (Data Models & Storage)
├── COW-610 (Collection Lifecycle & API)
└── COW-611 (Analysis & Aggregation)

COW-588 (Baseline Snapshot System)
└── Depends on: COW-587
└── Blocks: COW-589

COW-589 (Comparison Engine & Regression Detection)
├── Depends on: COW-587, COW-588
└── Blocks: COW-590

COW-590 (Automated Reporting)
└── Depends on: COW-587, COW-588, COW-589 (optional)

COW-608 (README Restructuring) ─ Standalone

COW-591 (Prometheus Exporters)
├── Depends on: COW-587
└── Blocks: COW-593

COW-593 (Grafana Dashboards)
├── Depends on: COW-591
└── Blocks: COW-598

COW-598 (Alerting Rules)
└── Depends on: COW-591, COW-593
```

---

## Implementation Plans

Detailed implementation approaches for tickets. Read these before implementing to avoid duplicating work.

| File | Related Ticket | Status | Keywords |
|------|----------------|--------|----------|
| [2026-01-26-cli-tool-interface.md](plans/2026-01-26-cli-tool-interface.md) | M1-Issue-05 | ✅ Complete | CLI, Typer, commands, configuration |
| [2026-01-28-cow-587-validation-plan.md](plans/2026-01-28-cow-587-validation-plan.md) | COW-587 | ✅ Complete | validation, testing, component-status |
| [2026-01-28-cow-609-foundation-data-models-storage.md](plans/2026-01-28-cow-609-foundation-data-models-storage.md) | COW-609 | ✅ Complete | Pydantic, MetricsStore, OrderMetadata, JSON-export |
| [2026-01-28-cow-610-collection-lifecycle-api-monitoring.md](plans/2026-01-28-cow-610-collection-lifecycle-api-monitoring.md) | COW-610 | ✅ Complete | order-tracking, API-instrumentation, resource-monitoring |
| [2026-01-29-cow-611-analysis-aggregation-realtime.md](plans/2026-01-29-cow-611-analysis-aggregation-realtime.md) | COW-611 | ✅ Complete | MetricsAggregator, percentiles, real-time, CLI |
| [2026-02-02-cow-588-baseline-snapshot-system.md](plans/2026-02-02-cow-588-baseline-snapshot-system.md) | COW-588 | ✅ Complete | BaselineManager, git-info, UUID-index, serialization |
| [2026-02-03-cow-589-comparison-engine.md](plans/2026-02-03-cow-589-comparison-engine.md) | COW-589 | ✅ Complete | ComparisonEngine, regression, statistics, p-value, Cohen's-d |
| [2026-02-03-cow-590-automated-reporting.md](plans/2026-02-03-cow-590-automated-reporting.md) | COW-590 | ✅ Complete | ReportGenerator, formatters, CSV, recommendations, CLI |
| [2026-02-13-cow-598-alerting-rules.md](plans/2026-02-13-cow-598-alerting-rules.md) | COW-598 | 🔲 Ready | Prometheus alerts, alerting rules, thresholds, Grafana annotations |
| [m4-issue-14-predefined-scenarios-plan.md](plans/m4-issue-14-predefined-scenarios-plan.md) | M4-Issue-14 | 👀 In Review | scenarios, tags, metadata, success-criteria, CI/CD, documentation |
| [2026-03-10-m4-issue-15-configuration-architecture.md](plans/2026-03-10-m4-issue-15-configuration-architecture.md) | M4-Issue-15 | ✅ Complete | configuration-system, inheritance, templates, profiles, defaults, validation, config-generator, wizard |

---

## Research

Investigation and analysis documents created before implementation.

| File | Related Ticket | Keywords |
|------|----------------|----------|
| _(none currently)_ | — | — |

---

## Reports

Investigation reports and analysis of production issues, performance problems, and system behavior.

| File | Date | Summary | Keywords |
|------|------|---------|----------|
| [docker-disk-usage-investigation.md](reports/docker-disk-usage-investigation.md) | 2026-03-03 | Docker disk space investigation: Three root causes identified and fixed - 32GB Rust build artifacts (anonymous volumes), 28GB build cache/orphaned volumes (cleanup), 3.9GB Anvil state accumulation (--prune-history flag). Total: 54GB freed. | docker, disk-usage, rust, build-artifacts, volumes, orderbook, anvil, tmpfs, prune-history, optimization |
| [order-failure-analysis.md](reports/order-failure-analysis.md) | _(earlier)_ | Analysis of order failure patterns | orders, failures, analysis |

---

## Prompts

Reusable agent prompts for specific tasks. Use these instead of writing new prompts for similar tasks.

| File | Purpose | Target Area |
|------|---------|-------------|
| [m3-planning-agent.md](prompts/m3-planning-agent.md) | M3 planning & validation (claude-code): refine tasks, grant alignment, produce M3 validation doc | M3 (COW-591, COW-593, COW-598) |

---

## Validations

Milestone completion validations and delivery comments.

| File | Milestone | Summary |
|------|-----------|---------|
| [m2-validation-comments.md](m2-validation-comments.md) | M2 | Comments for Linear explaining implementation decisions and deviations |

---

## Audits

Code quality audits and their findings.

| File | Date | Summary |
|------|------|---------|
| _(none currently)_ | — | — |

---

## Context

Background documents providing project context.

| File | Purpose |
|------|---------|
| [grant-proposal.md](context/grant-proposal.md) | Project scope, milestones (M1-M4), budget (21,000 xDAI), success criteria |

---

## Document Clusters

Related documents grouped by feature/topic:

### Metrics Collection (COW-587)
```
tickets/COW-587-metrics-collection-framework.md  (Parent ticket)
├── tickets/COW-609-foundation-data-models-storage.md
│   └── plans/2026-01-28-cow-609-foundation-data-models-storage.md
├── tickets/COW-610-collection-lifecycle-api-monitoring.md
│   └── plans/2026-01-28-cow-610-collection-lifecycle-api-monitoring.md
├── tickets/COW-611-analysis-aggregation-realtime.md
│   └── plans/2026-01-29-cow-611-analysis-aggregation-realtime.md
└── plans/2026-01-28-cow-587-validation-plan.md
```

### Baseline Snapshot System (COW-588)
```
tickets/COW-588-baseline-snapshot-system.md
└── plans/2026-02-02-cow-588-baseline-snapshot-system.md
```

### Comparison Engine (COW-589)
```
tickets/COW-589-comparison-engine-regression-detection.md
└── plans/2026-02-03-cow-589-comparison-engine.md
```

### Automated Reporting (COW-590)
```
tickets/COW-590-automated-reporting.md
└── plans/2026-02-03-cow-590-automated-reporting.md
```

### Documentation (COW-608)
```
tickets/COW-608-readme-restructuring.md
```

### Prometheus Exporters (COW-591) — M3
```
tickets/COW-591-prometheus-exporters.md
```

### Grafana Dashboards (COW-593) — M3
```
tickets/COW-593-grafana-dashboards.md
```

### Alerting Rules (COW-598) — M3
```
tickets/COW-598-alerting-rules.md
└── plans/2026-02-13-cow-598-alerting-rules.md  (execution plan)
```

### Predefined Test Scenarios (M4-Issue-14) — M4
```
plans/m4-issue-14-predefined-scenarios-plan.md
└── Implementation:
    ├── configs/scenarios/enhanced/*.yml  (5 production scenarios)
    ├── src/cow_performance/scenarios/validation.py  (SuccessCriteriaValidator)
    └── docs/scenarios/*.md  (individual scenario documentation)
```

### Configuration Architecture (M4-Issue-15) — M4
```
plans/2026-03-10-m4-issue-15-configuration-architecture.md
└── Implementation (Phases 1-8):
    ├── Phase 1-5: Enhanced validation, defaults, inheritance, profiles, CLI
    ├── Phase 6: Templates
    │   ├── configs/templates/*.template.yml  (3 built-in templates)
    │   ├── src/cow_performance/scenarios/templates.py  (TemplateExpander)
    │   └── examples/scenarios/*.yml  (4 template examples)
    ├── Phase 7: Configuration Generator
    │   ├── src/cow_performance/scenarios/generator.py  (ConfigGenerator)
    │   ├── CLI: cow-perf config-init  (interactive wizard)
    │   └── tests/unit/test_generator.py  (20 tests)
    └── Phase 8: Documentation
        ├── docs/scenario-user-guide.md  (step-by-step tutorial)
        ├── docs/configuration-reference.md  (complete field reference)
        └── docs/scenario-best-practices.md  (guidelines and patterns)
```

---

## Keyword Index

Find documents by topic:

| Keyword | Documents |
|---------|-----------|
| `aggregation` | COW-611 ticket, COW-611 plan |
| `alerting` | COW-598 ticket |
| `alertmanager` | COW-598 ticket |
| `anvil` | docker-disk-usage-investigation report |
| `API` | COW-610 ticket, COW-610 plan |
| `baseline` | COW-588 ticket, COW-588 plan |
| `build-artifacts` | docker-disk-usage-investigation report |
| `BaselineManager` | COW-588 plan |
| `CLI` | 2026-01-26 plan |
| `Cohen's-d` | COW-589 plan |
| `comparison` | COW-589 ticket, COW-589 plan |
| `ComparisonEngine` | COW-589 plan |
| `config-generator` | M4-Issue-15 architecture (Phase 7) |
| `configuration-system` | M4-Issue-15 architecture |
| `CSV` | COW-590 plan |
| `dashboards` | COW-593 ticket |
| `defaults` | M4-Issue-15 architecture |
| `data-models` | COW-609 ticket, COW-609 plan |
| `disk-usage` | docker-disk-usage-investigation report |
| `docker` | docker-disk-usage-investigation report |
| `documentation` | COW-608 ticket |
| `export` | COW-609 plan |
| `formatters` | COW-590 plan |
| `git-info` | COW-588 plan |
| `grafana` | COW-593 ticket |
| `heatmaps` | COW-593 ticket |
| `histograms` | COW-591 ticket |
| `inheritance` | M4-Issue-15 architecture |
| `lifecycle` | COW-610 ticket, COW-610 plan |
| `metrics` | COW-587 ticket, COW-609/610/611, COW-591 ticket |
| `monitoring` | COW-591 ticket, COW-598 ticket |
| `notifications` | COW-598 ticket |
| `optimization` | docker-disk-usage-investigation report |
| `orderbook` | docker-disk-usage-investigation report |
| `p-value` | COW-589 plan |
| `profiles` | M4-Issue-15 architecture |
| `prune-history` | docker-disk-usage-investigation report |
| `prometheus` | COW-591 ticket, COW-598 ticket |
| `PrometheusExporter` | COW-591 ticket |
| `Pydantic` | COW-609 plan |
| `real-time` | COW-611 ticket, COW-611 plan |
| `recommendations` | COW-590 plan |
| `regression` | COW-589 ticket, COW-589 plan |
| `ReportGenerator` | COW-590 plan |
| `reporting` | COW-590 ticket, COW-590 plan |
| `rust` | docker-disk-usage-investigation report |
| `scenario-documentation` | M4-Issue-15 architecture (Phase 8), user-guide, config-reference, best-practices |
| `scenarios` | M4-Issue-14 plan, M4-Issue-15 architecture |
| `serialization` | COW-588 plan |
| `statistics` | COW-589 plan |
| `streaming` | COW-611 ticket, COW-611 plan |
| `success-criteria` | M4-Issue-14 plan |
| `TDD` | COW-587 validation plan |
| `templates` | M4-Issue-15 architecture (Phase 6) |
| `testing` | COW-587 validation plan |
| `user-guide` | M4-Issue-15 architecture (Phase 8), docs/scenario-user-guide.md |
| `wizard` | M4-Issue-15 architecture (Phase 7), cow-perf config-init |
| `tmpfs` | docker-disk-usage-investigation report |
| `Typer` | 2026-01-26 plan |
| `validation` | COW-587 validation plan |
| `visualization` | COW-593 ticket |
| `volumes` | docker-disk-usage-investigation report |

---

## Maintenance Notes

**Last Updated**: 2026-03-11 (completed M4-Issue-15 Phases 6-8: templates, config generator, and documentation; added 3 new docs files)

### How to Update This Index
1. When adding new files, add entries to the appropriate section
2. Update the "Current Project Status" table when ticket statuses change
3. Add new keywords to the Keyword Index
4. Update Document Clusters when creating related documents

### Naming Conventions
- **Tickets**: `{TICKET-ID}-{short-description}.md`
- **Plans**: `YYYY-MM-DD-{ticket-id}-{description}.md`
- **Research**: `{topic}-research.md`
- **Audits**: `{audit-type}-YYYY-MM-DD.md`
- **Prompts**: `{task-description}.md`
