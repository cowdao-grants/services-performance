# COW-588: 08 - Baseline Snapshot System

**Linear URL**: https://linear.app/bleu-builders/issue/COW-588/08-baseline-snapshot-system
**Status**: In Progress
**Priority**: High
**Estimate**: 3 Points
**Milestone**: M2 — Performance Benchmarking
**Assignee**: jefferson@bleu.studio
**Git Branch**: `jefferson/cow-588-08-baseline-snapshot-system`

## Summary

Implement a system for capturing, storing, and managing performance baselines that enable comparison of test runs over time and detection of performance regressions.

## Background

Performance baselines serve as reference points for evaluating changes to the system. The baseline system must store comprehensive metrics along with metadata about the test conditions and code version.

**Prerequisites (DONE in COW-587):**
- `PercentileStats` - Statistical summary with p50/p90/p95/p99 (`metrics/aggregator.py`)
- `OrderAggregateMetrics`, `APIAggregateMetrics`, `ResourceAggregateMetrics` - Aggregated metrics
- `MetricsAggregator.get_summary()` - Returns comprehensive summary dict
- `MetricsStore` - Thread-safe storage of all raw metrics
- Basic `save_baseline()`, `load_baseline()`, `list_baselines()` functions (`cli/commands/baselines.py`)

## Deliverables

### 1. Baseline Data Model

**Subtasks:**

- [ ] Define `PerformanceBaseline` dataclass in `src/cow_performance/baselines/models.py`:
  - Identification: `id` (UUID), `name`, `description`, `tags`, `created_at`
  - Git info: `git_commit`, `git_branch`, `git_repo`, `has_uncommitted_changes`
  - Test config: `scenario_name`, `duration_seconds`, `num_traders`, `test_config` dict
  - Environment: `python_version`, `platform`, `dependencies` dict
  - Metrics: embed `OrderAggregateMetrics`, `APIAggregateMetrics`, `ResourceAggregateMetrics`
- [ ] Define `BaselineMetadata` dataclass for index entries (lightweight summary)
- [ ] Add `schema_version` field for forward compatibility
- [ ] Implement `to_dict()` and `from_dict()` methods for JSON serialization

> **Note**: Reuse `PercentileStats` from `metrics/aggregator.py` - do NOT create a separate `LatencyStats` class.

### 2. BaselineManager Class

**Subtasks:**

- [ ] Create `BaselineManager` class in `src/cow_performance/baselines/manager.py`
- [ ] Implement `save(name, metrics_store, config, description, tags)` method:
  - Use `MetricsAggregator` to compute summary from `MetricsStore`
  - Extract git info via `get_git_info()`
  - Capture environment info (Python version, platform, dependencies)
  - Write baseline JSON file
  - Update index
- [ ] Implement `load(identifier)` method - load by name, ID, or git commit
- [ ] Implement `list(tags, branch)` method with filtering
- [ ] Implement `delete(identifier)` method
- [ ] Implement private methods: `_update_index()`, `_load_index()`, `_find_baseline()`

### 3. Index Management

**Subtasks:**

- [ ] Create `index.json` in baselines directory
- [ ] Store `BaselineMetadata` entries (id, name, tags, git_branch, git_commit, created_at)
- [ ] Implement efficient lookup by name, ID, git commit, tag
- [ ] Handle index corruption gracefully (rebuild from files)

### 4. Git Integration

**Subtasks:**

- [ ] Create `get_git_info()` function in `src/cow_performance/baselines/git_info.py`
- [ ] Use `GitPython` library to extract:
  - Current commit hash
  - Branch name
  - Repository URL (from origin remote)
  - Whether working directory is dirty
- [ ] Return empty dict gracefully when not in a git repo
- [ ] Log warning if uncommitted changes detected

### 5. Validation

**Subtasks:**

- [ ] Validate baseline JSON structure on load
- [ ] Check `schema_version` compatibility
- [ ] Provide clear error messages for invalid/corrupted files
- [ ] Validate required fields present

### 6. CLI Integration

**Subtasks:**

- [ ] Update `cli/commands/baselines.py` to use `BaselineManager`
- [ ] Enhance `show_baseline_command` to display git info and tags
- [ ] Add `--tag` filter to `list_baselines_command`
- [ ] Keep backward compatibility with existing baseline files

## Implementation Details

### Directory Structure

```
src/cow_performance/baselines/
├── __init__.py
├── models.py       # PerformanceBaseline, BaselineMetadata
├── manager.py      # BaselineManager class
├── git_info.py     # get_git_info() function
└── validation.py   # validate_baseline() function

tests/baselines/
├── __init__.py
├── test_models.py
├── test_manager.py
├── test_git_info.py
└── test_validation.py
```

### Storage Structure

```
.cow-perf/
└── baselines/
    ├── index.json              # Catalog of all baselines
    ├── {uuid-1}.json           # Full baseline data
    ├── {uuid-2}.json
    └── ...
```

### Data Models

```python
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any
from cow_performance.metrics.aggregator import (
    PercentileStats,
    OrderAggregateMetrics,
    APIAggregateMetrics,
    ResourceAggregateMetrics,
)

SCHEMA_VERSION = "1.0"

@dataclass
class PerformanceBaseline:
    """Complete baseline snapshot with all metrics and metadata."""

    # Identification
    id: str  # UUID
    name: str
    description: str = ""
    tags: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    schema_version: str = SCHEMA_VERSION

    # Git Information
    git_commit: str | None = None
    git_branch: str | None = None
    git_repo: str | None = None
    has_uncommitted_changes: bool = False

    # Test Configuration
    scenario_name: str = ""
    duration_seconds: int = 0
    num_traders: int = 0
    test_config: dict[str, Any] = field(default_factory=dict)

    # Environment
    python_version: str = ""
    platform: str = ""
    dependencies: dict[str, str] = field(default_factory=dict)

    # Aggregated Metrics (from MetricsAggregator)
    order_metrics: OrderAggregateMetrics | None = None
    api_metrics: APIAggregateMetrics | None = None
    resource_metrics: dict[str, ResourceAggregateMetrics] = field(default_factory=dict)

    # Throughput
    orders_per_second: float = 0.0
    peak_orders_per_second: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for JSON storage."""
        ...

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PerformanceBaseline":
        """Deserialize from dictionary."""
        ...


@dataclass
class BaselineMetadata:
    """Lightweight baseline info for index entries."""

    id: str
    name: str
    tags: list[str]
    git_commit: str | None
    git_branch: str | None
    created_at: datetime
    orders_per_second: float  # Key metric for quick comparison
```

### BaselineManager Interface

```python
class BaselineManager:
    def __init__(self, baselines_dir: Path | None = None):
        """Initialize manager with baselines directory."""

    def save(
        self,
        name: str,
        metrics_store: MetricsStore,
        config: dict[str, Any] | None = None,
        description: str = "",
        tags: list[str] | None = None,
    ) -> PerformanceBaseline:
        """Capture and save a performance baseline from current metrics."""

    def load(self, identifier: str) -> PerformanceBaseline:
        """Load baseline by name, ID, or git commit hash."""

    def list(
        self,
        tags: list[str] | None = None,
        branch: str | None = None,
    ) -> list[BaselineMetadata]:
        """List all baselines with optional filtering."""

    def delete(self, identifier: str) -> None:
        """Delete a baseline by name or ID."""
```

## Testing Requirements

### Unit Tests

- Model serialization/deserialization roundtrips
- Git info extraction (mock git operations)
- Index management (add, remove, lookup)
- Validation logic for corrupted/invalid files

### Integration Tests

- Save baseline from populated `MetricsStore`, then load it back
- Verify git info captured correctly in a real git repo
- Test in non-git environment (graceful handling)
- Test index rebuild from baseline files

### Key Fixtures Needed

- `tmp_baselines_dir` - isolated directory for tests
- `mock_metrics_store` - `MetricsStore` with sample data
- `tmp_git_repo` - temporary git repo with commits

## Acceptance Criteria

- [ ] `PerformanceBaseline` dataclass defined with all fields
- [ ] Baselines can be saved from `MetricsStore` with `BaselineManager.save()`
- [ ] Baselines include git information automatically
- [ ] Baselines stored as human-readable JSON with schema version
- [ ] Baselines can be loaded by name, ID, or git commit hash
- [ ] Baseline listing and filtering by tag/branch working
- [ ] Index file (`index.json`) tracks all baselines
- [ ] Git integration working (handles non-git environments gracefully)
- [ ] Validation prevents loading corrupted files
- [ ] CLI commands updated to use `BaselineManager`
- [ ] Type hints throughout
- [ ] All TDD tests passing

## Technical Notes

- Reuse `PercentileStats` from `metrics/aggregator.py` (don't create `LatencyStats`)
- Use `GitPython` for git operations
- Use `uuid.uuid4()` for baseline IDs
- Store baselines in `.cow-perf/baselines/` (project-local, add to `.gitignore`)
- JSON storage for human readability
- Include `schema_version` for future compatibility
- The existing functions in `cli/commands/baselines.py` should be updated to use `BaselineManager`

## Related Issues

- **Depends on**: COW-587 (Metrics Collection Framework) - DONE
- **Blocks**: COW-589 (Comparison Engine & Regression Detection)
- **Related**: COW-605 (CLI Tool Interface)

---

## Implementation Notes (Post-Completion)

**Status**: ✅ Completed

### Architectural Decisions & Deviations from Original Scope

The implementation adjusted several aspects from the original proposal:

1. **Environment tracking simplified** - The `python_version`, `platform`, and `dependencies` fields exist in the dataclass but are not actively populated. This was a deliberate choice to focus on metrics comparison rather than cross-environment reproducibility, which wasn't needed for local performance testing.

2. **File locking deferred** - The original proposal included file locking to prevent corruption. This was not implemented because the tool is designed for single-user local use, and the index auto-rebuild mechanism provides sufficient corruption recovery.

3. **Baseline expiration/archival deferred** - The expiration feature was moved to a future iteration. Manual deletion via CLI is sufficient for the current use case, and disk space constraints are minimal for JSON files.

4. **Git diff storage deferred** - Storing git diffs for uncommitted changes was not implemented. The `has_uncommitted_changes` flag provides sufficient warning without the storage overhead of full diffs.

5. **CLI `--save-baseline` flag not implemented** - Baselines are saved programmatically via `BaselineManager.save(metrics_store)`. The CLI is for library/framework use, not end-user tooling. This aligns with the grant scope (performance testing framework, not CLI tool).

These decisions prioritize a lean, working implementation that can be extended later if needed.
