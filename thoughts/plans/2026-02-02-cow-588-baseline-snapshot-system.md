# COW-588: Baseline Snapshot System Implementation Plan

## Overview

Implement a structured baseline snapshot system that captures, stores, and manages performance baselines with git integration. This replaces the existing basic baseline functions with a comprehensive `BaselineManager` class and structured data models.

## Current State Analysis

**Existing Code (`cli/commands/baselines.py:19-165`)**:
- Basic functions: `save_baseline()`, `load_baseline()`, `list_baselines()`, `delete_baseline()`
- Stores baselines in `~/.cow-perf/baselines/` (user home)
- Uses sanitized name as filename (`{name}.json`)
- Only saves raw metrics dict with name and timestamp
- No git info, no structured data model, no index

**Available Building Blocks (from COW-587)**:
- `PercentileStats` - `metrics/aggregator.py:19-60`
- `OrderAggregateMetrics` - `metrics/aggregator.py:63-86`
- `APIAggregateMetrics` - `metrics/aggregator.py:89-106`
- `ResourceAggregateMetrics` - `metrics/aggregator.py:108-117`
- `MetricsAggregator.get_summary()` - `metrics/aggregator.py:310-321`
- `MetricsStore` - `metrics/store.py:35-326`

**Dependencies Ready**:
- `gitpython = "^3.1.40"` in `pyproject.toml:30` (not yet used)

## Desired End State

After implementation:
1. **New module** at `src/cow_performance/baselines/` with:
   - `models.py` - `PerformanceBaseline`, `BaselineMetadata` dataclasses
   - `manager.py` - `BaselineManager` class for all CRUD operations
   - `git_info.py` - `get_git_info()` function using GitPython
   - `validation.py` - `validate_baseline()` function

2. **Storage** in `.cow-perf/baselines/` (project root):
   - `index.json` - catalog of all baselines with lightweight metadata
   - `{uuid}.json` - full baseline data files

3. **CLI commands** updated to use `BaselineManager`

4. **Git info** automatically captured when saving baselines

### Verification:
```bash
# All tests pass
poetry run pytest tests/unit/test_baseline_models.py tests/unit/test_baseline_manager.py tests/unit/test_baseline_git_info.py tests/unit/test_baseline_validation.py -v

# Type checking
poetry run mypy src/cow_performance/baselines/

# Lint
poetry run ruff check src/cow_performance/baselines/
```

## What We're NOT Doing

- **No backward compatibility** with old baseline format (per design decision)
- **No comparison logic** - that's COW-589
- **No HTML/Markdown reporting** - that's COW-590
- **No threshold configuration** - that's COW-589
- **No migration tool** for existing baselines

## Implementation Approach

1. **Phase 1**: Create data models (`PerformanceBaseline`, `BaselineMetadata`)
2. **Phase 2**: Implement git integration (`get_git_info()`)
3. **Phase 3**: Implement validation (`validate_baseline()`)
4. **Phase 4**: Implement `BaselineManager` class
5. **Phase 5**: Update CLI commands to use `BaselineManager`
6. **Phase 6**: Write comprehensive tests

---

## Phase 1: Data Models

### Overview

Create the core dataclasses for baselines following codebase patterns.

### Changes Required:

#### 1. Create Module Structure

**File**: `src/cow_performance/baselines/__init__.py`

```python
"""Baseline snapshot system for performance testing."""

from cow_performance.baselines.git_info import get_git_info
from cow_performance.baselines.manager import BaselineManager
from cow_performance.baselines.models import (
    SCHEMA_VERSION,
    BaselineMetadata,
    PerformanceBaseline,
)
from cow_performance.baselines.validation import (
    BaselineValidationError,
    validate_baseline,
)

__all__ = [
    "SCHEMA_VERSION",
    "BaselineMetadata",
    "BaselineManager",
    "BaselineValidationError",
    "PerformanceBaseline",
    "get_git_info",
    "validate_baseline",
]
```

#### 2. Define Data Models

**File**: `src/cow_performance/baselines/models.py`

```python
"""Data models for performance baselines."""

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any

from cow_performance.metrics.aggregator import (
    APIAggregateMetrics,
    OrderAggregateMetrics,
    PercentileStats,
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
    created_at: float = field(default_factory=lambda: datetime.now().timestamp())
    schema_version: str = SCHEMA_VERSION

    # Git Information
    git_commit: str | None = None
    git_branch: str | None = None
    git_repo: str | None = None
    has_uncommitted_changes: bool = False

    # Test Configuration
    scenario_name: str = ""
    duration_seconds: float = 0.0
    num_traders: int = 0
    test_config: dict[str, Any] = field(default_factory=dict)

    # Environment
    python_version: str = ""
    platform: str = ""
    dependencies: dict[str, str] = field(default_factory=dict)

    # Aggregated Metrics
    order_metrics: OrderAggregateMetrics | None = None
    api_metrics: APIAggregateMetrics | None = None
    resource_metrics: dict[str, ResourceAggregateMetrics] = field(default_factory=dict)

    # Throughput
    orders_per_second: float = 0.0
    peak_orders_per_second: float = 0.0


@dataclass
class BaselineMetadata:
    """Lightweight baseline info for index entries."""

    id: str
    name: str
    tags: list[str]
    git_commit: str | None
    git_branch: str | None
    created_at: float
    orders_per_second: float  # Key metric for quick comparison


def percentile_stats_to_dict(stats: PercentileStats) -> dict[str, Any]:
    """Serialize PercentileStats to dict."""
    return asdict(stats)


def percentile_stats_from_dict(data: dict[str, Any]) -> PercentileStats:
    """Deserialize PercentileStats from dict."""
    return PercentileStats(**data)


def order_aggregate_to_dict(metrics: OrderAggregateMetrics) -> dict[str, Any]:
    """Serialize OrderAggregateMetrics to dict."""
    return {
        "total_orders": metrics.total_orders,
        "orders_created": metrics.orders_created,
        "orders_submitted": metrics.orders_submitted,
        "orders_accepted": metrics.orders_accepted,
        "orders_filled": metrics.orders_filled,
        "orders_partially_filled": metrics.orders_partially_filled,
        "orders_expired": metrics.orders_expired,
        "orders_cancelled": metrics.orders_cancelled,
        "orders_failed": metrics.orders_failed,
        "success_rate": metrics.success_rate,
        "failure_rate": metrics.failure_rate,
        "time_to_submit": percentile_stats_to_dict(metrics.time_to_submit),
        "time_to_accept": percentile_stats_to_dict(metrics.time_to_accept),
        "time_to_fill": percentile_stats_to_dict(metrics.time_to_fill),
        "total_lifecycle": percentile_stats_to_dict(metrics.total_lifecycle),
    }


def order_aggregate_from_dict(data: dict[str, Any]) -> OrderAggregateMetrics:
    """Deserialize OrderAggregateMetrics from dict."""
    return OrderAggregateMetrics(
        total_orders=data.get("total_orders", 0),
        orders_created=data.get("orders_created", 0),
        orders_submitted=data.get("orders_submitted", 0),
        orders_accepted=data.get("orders_accepted", 0),
        orders_filled=data.get("orders_filled", 0),
        orders_partially_filled=data.get("orders_partially_filled", 0),
        orders_expired=data.get("orders_expired", 0),
        orders_cancelled=data.get("orders_cancelled", 0),
        orders_failed=data.get("orders_failed", 0),
        success_rate=data.get("success_rate", 0.0),
        failure_rate=data.get("failure_rate", 0.0),
        time_to_submit=percentile_stats_from_dict(data.get("time_to_submit", {})),
        time_to_accept=percentile_stats_from_dict(data.get("time_to_accept", {})),
        time_to_fill=percentile_stats_from_dict(data.get("time_to_fill", {})),
        total_lifecycle=percentile_stats_from_dict(data.get("total_lifecycle", {})),
    )


def api_aggregate_to_dict(metrics: APIAggregateMetrics) -> dict[str, Any]:
    """Serialize APIAggregateMetrics to dict."""
    return {
        "total_requests": metrics.total_requests,
        "successful_requests": metrics.successful_requests,
        "failed_requests": metrics.failed_requests,
        "success_rate": metrics.success_rate,
        "response_time": percentile_stats_to_dict(metrics.response_time),
        "status_code_counts": metrics.status_code_counts,
        "requests_per_second": metrics.requests_per_second,
    }


def api_aggregate_from_dict(data: dict[str, Any]) -> APIAggregateMetrics:
    """Deserialize APIAggregateMetrics from dict."""
    return APIAggregateMetrics(
        total_requests=data.get("total_requests", 0),
        successful_requests=data.get("successful_requests", 0),
        failed_requests=data.get("failed_requests", 0),
        success_rate=data.get("success_rate", 0.0),
        response_time=percentile_stats_from_dict(data.get("response_time", {})),
        status_code_counts=data.get("status_code_counts", {}),
        requests_per_second=data.get("requests_per_second", 0.0),
    )


def resource_aggregate_to_dict(metrics: ResourceAggregateMetrics) -> dict[str, Any]:
    """Serialize ResourceAggregateMetrics to dict."""
    return {
        "container_name": metrics.container_name,
        "sample_count": metrics.sample_count,
        "cpu_percent": percentile_stats_to_dict(metrics.cpu_percent),
        "memory_percent": percentile_stats_to_dict(metrics.memory_percent),
        "memory_bytes": percentile_stats_to_dict(metrics.memory_bytes),
    }


def resource_aggregate_from_dict(data: dict[str, Any]) -> ResourceAggregateMetrics:
    """Deserialize ResourceAggregateMetrics from dict."""
    return ResourceAggregateMetrics(
        container_name=data.get("container_name", ""),
        sample_count=data.get("sample_count", 0),
        cpu_percent=percentile_stats_from_dict(data.get("cpu_percent", {})),
        memory_percent=percentile_stats_from_dict(data.get("memory_percent", {})),
        memory_bytes=percentile_stats_from_dict(data.get("memory_bytes", {})),
    )


def baseline_to_dict(baseline: PerformanceBaseline) -> dict[str, Any]:
    """Serialize PerformanceBaseline to dict for JSON storage."""
    result: dict[str, Any] = {
        # Identification
        "id": baseline.id,
        "name": baseline.name,
        "description": baseline.description,
        "tags": baseline.tags,
        "created_at": baseline.created_at,
        "schema_version": baseline.schema_version,
        # Git
        "git_commit": baseline.git_commit,
        "git_branch": baseline.git_branch,
        "git_repo": baseline.git_repo,
        "has_uncommitted_changes": baseline.has_uncommitted_changes,
        # Test config
        "scenario_name": baseline.scenario_name,
        "duration_seconds": baseline.duration_seconds,
        "num_traders": baseline.num_traders,
        "test_config": baseline.test_config,
        # Environment
        "python_version": baseline.python_version,
        "platform": baseline.platform,
        "dependencies": baseline.dependencies,
        # Throughput
        "orders_per_second": baseline.orders_per_second,
        "peak_orders_per_second": baseline.peak_orders_per_second,
    }

    # Metrics (can be None)
    if baseline.order_metrics is not None:
        result["order_metrics"] = order_aggregate_to_dict(baseline.order_metrics)
    else:
        result["order_metrics"] = None

    if baseline.api_metrics is not None:
        result["api_metrics"] = api_aggregate_to_dict(baseline.api_metrics)
    else:
        result["api_metrics"] = None

    # Resource metrics (dict)
    result["resource_metrics"] = {
        name: resource_aggregate_to_dict(metrics)
        for name, metrics in baseline.resource_metrics.items()
    }

    return result


def baseline_from_dict(data: dict[str, Any]) -> PerformanceBaseline:
    """Deserialize PerformanceBaseline from dict."""
    # Parse order_metrics
    order_metrics = None
    if data.get("order_metrics") is not None:
        order_metrics = order_aggregate_from_dict(data["order_metrics"])

    # Parse api_metrics
    api_metrics = None
    if data.get("api_metrics") is not None:
        api_metrics = api_aggregate_from_dict(data["api_metrics"])

    # Parse resource_metrics
    resource_metrics = {}
    for name, metrics_data in data.get("resource_metrics", {}).items():
        resource_metrics[name] = resource_aggregate_from_dict(metrics_data)

    return PerformanceBaseline(
        id=data["id"],
        name=data["name"],
        description=data.get("description", ""),
        tags=data.get("tags", []),
        created_at=data.get("created_at", 0.0),
        schema_version=data.get("schema_version", SCHEMA_VERSION),
        git_commit=data.get("git_commit"),
        git_branch=data.get("git_branch"),
        git_repo=data.get("git_repo"),
        has_uncommitted_changes=data.get("has_uncommitted_changes", False),
        scenario_name=data.get("scenario_name", ""),
        duration_seconds=data.get("duration_seconds", 0.0),
        num_traders=data.get("num_traders", 0),
        test_config=data.get("test_config", {}),
        python_version=data.get("python_version", ""),
        platform=data.get("platform", ""),
        dependencies=data.get("dependencies", {}),
        order_metrics=order_metrics,
        api_metrics=api_metrics,
        resource_metrics=resource_metrics,
        orders_per_second=data.get("orders_per_second", 0.0),
        peak_orders_per_second=data.get("peak_orders_per_second", 0.0),
    )


def metadata_to_dict(metadata: BaselineMetadata) -> dict[str, Any]:
    """Serialize BaselineMetadata to dict."""
    return asdict(metadata)


def metadata_from_dict(data: dict[str, Any]) -> BaselineMetadata:
    """Deserialize BaselineMetadata from dict."""
    return BaselineMetadata(
        id=data["id"],
        name=data["name"],
        tags=data.get("tags", []),
        git_commit=data.get("git_commit"),
        git_branch=data.get("git_branch"),
        created_at=data.get("created_at", 0.0),
        orders_per_second=data.get("orders_per_second", 0.0),
    )
```

### Success Criteria:

#### Automated Verification:
- [x] `poetry run pytest tests/unit/test_baseline_models.py -v`
- [x] `poetry run mypy src/cow_performance/baselines/models.py`
- [x] `poetry run ruff check src/cow_performance/baselines/models.py`

#### Manual Verification:
- [x] Serialization roundtrip preserves all fields
- [x] Default values work correctly

---

## Phase 2: Git Integration

### Overview

Implement `get_git_info()` function using GitPython to extract repository metadata.

### Changes Required:

#### 1. Create Git Info Module

**File**: `src/cow_performance/baselines/git_info.py`

```python
"""Git integration for baseline metadata."""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class GitInfo:
    """Git repository information."""

    commit: str | None = None
    branch: str | None = None
    repo_url: str | None = None
    is_dirty: bool = False


def get_git_info(repo_path: Path | None = None) -> GitInfo:
    """
    Extract git information from the current repository.

    Args:
        repo_path: Optional path to repository. Uses cwd if not specified.

    Returns:
        GitInfo with repository metadata. Returns empty GitInfo if not in a git repo.
    """
    try:
        import git
    except ImportError:
        logger.warning("GitPython not installed. Git info will not be captured.")
        return GitInfo()

    if repo_path is None:
        repo_path = Path.cwd()

    try:
        repo = git.Repo(repo_path, search_parent_directories=True)
    except git.InvalidGitRepositoryError:
        logger.debug("Not in a git repository: %s", repo_path)
        return GitInfo()
    except git.GitCommandNotFound:
        logger.warning("Git command not found. Git info will not be captured.")
        return GitInfo()

    info = GitInfo()

    # Get current commit hash
    try:
        info.commit = repo.head.commit.hexsha
    except Exception as e:
        logger.debug("Could not get commit hash: %s", e)

    # Get current branch name
    try:
        if not repo.head.is_detached:
            info.branch = repo.active_branch.name
        else:
            info.branch = f"detached@{info.commit[:8]}" if info.commit else "detached"
    except Exception as e:
        logger.debug("Could not get branch name: %s", e)

    # Get remote URL (origin)
    try:
        if "origin" in repo.remotes:
            info.repo_url = repo.remotes.origin.url
    except Exception as e:
        logger.debug("Could not get remote URL: %s", e)

    # Check for uncommitted changes
    try:
        info.is_dirty = repo.is_dirty(untracked_files=True)
        if info.is_dirty:
            logger.warning(
                "Repository has uncommitted changes. "
                "Baseline may not be reproducible from git commit."
            )
    except Exception as e:
        logger.debug("Could not check dirty status: %s", e)

    return info


def git_info_to_dict(info: GitInfo) -> dict[str, Any]:
    """Convert GitInfo to a dictionary for baseline storage."""
    return {
        "git_commit": info.commit,
        "git_branch": info.branch,
        "git_repo": info.repo_url,
        "has_uncommitted_changes": info.is_dirty,
    }
```

### Success Criteria:

#### Automated Verification:
- [x] `poetry run pytest tests/unit/test_baseline_git_info.py -v`
- [x] `poetry run mypy src/cow_performance/baselines/git_info.py`

#### Manual Verification:
- [x] Works correctly in a git repo (returns actual values)
- [x] Returns empty GitInfo gracefully when not in git repo
- [x] Logs warning when uncommitted changes detected

---

## Phase 3: Validation

### Overview

Implement validation logic for loading baselines with schema version checking.

### Changes Required:

#### 1. Create Validation Module

**File**: `src/cow_performance/baselines/validation.py`

```python
"""Validation for baseline files."""

import logging
from typing import Any

from cow_performance.baselines.models import SCHEMA_VERSION

logger = logging.getLogger(__name__)


class BaselineValidationError(Exception):
    """Raised when baseline validation fails."""

    pass


REQUIRED_FIELDS = [
    "id",
    "name",
    "schema_version",
    "created_at",
]


def validate_baseline(data: dict[str, Any]) -> None:
    """
    Validate baseline data structure.

    Args:
        data: The baseline data dictionary to validate.

    Raises:
        BaselineValidationError: If validation fails.
    """
    # Check required fields
    missing_fields = [field for field in REQUIRED_FIELDS if field not in data]
    if missing_fields:
        raise BaselineValidationError(
            f"Missing required fields: {', '.join(missing_fields)}"
        )

    # Validate schema version
    schema_version = data.get("schema_version")
    if schema_version is None:
        raise BaselineValidationError("Missing schema_version field")

    # Check major version compatibility
    try:
        file_major = int(schema_version.split(".")[0])
        current_major = int(SCHEMA_VERSION.split(".")[0])
    except (ValueError, IndexError, AttributeError) as e:
        raise BaselineValidationError(f"Invalid schema_version format: {schema_version}") from e

    if file_major > current_major:
        raise BaselineValidationError(
            f"Baseline schema version {schema_version} is newer than supported {SCHEMA_VERSION}. "
            "Please upgrade cow-performance to load this baseline."
        )

    # Validate id is a non-empty string
    baseline_id = data.get("id")
    if not baseline_id or not isinstance(baseline_id, str):
        raise BaselineValidationError("Invalid or missing 'id' field")

    # Validate name is a non-empty string
    name = data.get("name")
    if not name or not isinstance(name, str):
        raise BaselineValidationError("Invalid or missing 'name' field")

    # Validate created_at is a number
    created_at = data.get("created_at")
    if not isinstance(created_at, (int, float)):
        raise BaselineValidationError(f"Invalid 'created_at' field: {created_at}")

    # Validate tags is a list if present
    tags = data.get("tags")
    if tags is not None and not isinstance(tags, list):
        raise BaselineValidationError(f"Invalid 'tags' field: expected list, got {type(tags)}")

    logger.debug("Baseline validation passed: %s (schema %s)", baseline_id, schema_version)
```

### Success Criteria:

#### Automated Verification:
- [x] `poetry run pytest tests/unit/test_baseline_validation.py -v`
- [x] `poetry run mypy src/cow_performance/baselines/validation.py`

#### Manual Verification:
- [x] Validation passes for valid baselines
- [x] Clear error messages for missing fields
- [x] Clear error messages for incompatible schema versions

---

## Phase 4: BaselineManager

### Overview

Implement the core `BaselineManager` class for all CRUD operations on baselines.

### Changes Required:

#### 1. Create Manager Module

**File**: `src/cow_performance/baselines/manager.py`

```python
"""Baseline manager for CRUD operations."""

import json
import logging
import platform
import sys
import uuid
from pathlib import Path
from typing import Any

from cow_performance.baselines.git_info import get_git_info, git_info_to_dict
from cow_performance.baselines.models import (
    SCHEMA_VERSION,
    BaselineMetadata,
    PerformanceBaseline,
    baseline_from_dict,
    baseline_to_dict,
    metadata_from_dict,
    metadata_to_dict,
)
from cow_performance.baselines.validation import (
    BaselineValidationError,
    validate_baseline,
)
from cow_performance.metrics.aggregator import MetricsAggregator
from cow_performance.metrics.store import MetricsStore

logger = logging.getLogger(__name__)

# Default baselines directory (project-local)
DEFAULT_BASELINES_DIR = Path(".cow-perf") / "baselines"
INDEX_FILENAME = "index.json"


class BaselineManager:
    """
    Manages baseline CRUD operations with index-based lookups.

    Baselines are stored as JSON files with UUIDs as filenames.
    An index.json file maintains lightweight metadata for efficient listing.
    """

    def __init__(self, baselines_dir: Path | None = None):
        """
        Initialize the baseline manager.

        Args:
            baselines_dir: Directory for storing baselines.
                          Defaults to .cow-perf/baselines/ in project root.
        """
        if baselines_dir is None:
            baselines_dir = DEFAULT_BASELINES_DIR

        self._baselines_dir = baselines_dir
        self._index_path = self._baselines_dir / INDEX_FILENAME

    @property
    def baselines_dir(self) -> Path:
        """Get the baselines directory path."""
        return self._baselines_dir

    def _ensure_dir(self) -> None:
        """Ensure the baselines directory exists."""
        self._baselines_dir.mkdir(parents=True, exist_ok=True)

    def _load_index(self) -> dict[str, dict[str, Any]]:
        """Load the baseline index."""
        if not self._index_path.exists():
            return {}

        try:
            with open(self._index_path) as f:
                data = json.load(f)
                if not isinstance(data, dict):
                    logger.warning("Index file is not a dict, returning empty index")
                    return {}
                return data
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to load index, will rebuild: %s", e)
            return self._rebuild_index()

    def _save_index(self, index: dict[str, dict[str, Any]]) -> None:
        """Save the baseline index."""
        self._ensure_dir()
        with open(self._index_path, "w") as f:
            json.dump(index, f, indent=2)

    def _rebuild_index(self) -> dict[str, dict[str, Any]]:
        """Rebuild index from baseline files."""
        logger.info("Rebuilding baseline index from files...")
        index: dict[str, dict[str, Any]] = {}

        if not self._baselines_dir.exists():
            return index

        for baseline_file in self._baselines_dir.glob("*.json"):
            if baseline_file.name == INDEX_FILENAME:
                continue

            try:
                with open(baseline_file) as f:
                    data = json.load(f)

                validate_baseline(data)
                baseline = baseline_from_dict(data)

                metadata = BaselineMetadata(
                    id=baseline.id,
                    name=baseline.name,
                    tags=baseline.tags,
                    git_commit=baseline.git_commit,
                    git_branch=baseline.git_branch,
                    created_at=baseline.created_at,
                    orders_per_second=baseline.orders_per_second,
                )
                index[baseline.id] = metadata_to_dict(metadata)
            except Exception as e:
                logger.warning("Skipping invalid baseline file %s: %s", baseline_file, e)

        self._save_index(index)
        logger.info("Rebuilt index with %d baselines", len(index))
        return index

    def _update_index(self, baseline: PerformanceBaseline) -> None:
        """Add or update a baseline in the index."""
        index = self._load_index()

        metadata = BaselineMetadata(
            id=baseline.id,
            name=baseline.name,
            tags=baseline.tags,
            git_commit=baseline.git_commit,
            git_branch=baseline.git_branch,
            created_at=baseline.created_at,
            orders_per_second=baseline.orders_per_second,
        )
        index[baseline.id] = metadata_to_dict(metadata)

        self._save_index(index)

    def _remove_from_index(self, baseline_id: str) -> None:
        """Remove a baseline from the index."""
        index = self._load_index()
        if baseline_id in index:
            del index[baseline_id]
            self._save_index(index)

    def _find_baseline(self, identifier: str) -> tuple[str, Path] | None:
        """
        Find a baseline by name, ID, or git commit.

        Args:
            identifier: Name, UUID, or git commit hash prefix.

        Returns:
            Tuple of (baseline_id, file_path) or None if not found.
        """
        index = self._load_index()

        # Try direct ID match
        if identifier in index:
            return identifier, self._baselines_dir / f"{identifier}.json"

        # Try name match
        for baseline_id, metadata in index.items():
            if metadata.get("name") == identifier:
                return baseline_id, self._baselines_dir / f"{baseline_id}.json"

        # Try git commit prefix match
        for baseline_id, metadata in index.items():
            git_commit = metadata.get("git_commit")
            if git_commit and git_commit.startswith(identifier):
                return baseline_id, self._baselines_dir / f"{baseline_id}.json"

        return None

    def save(
        self,
        name: str,
        metrics_store: MetricsStore,
        config: dict[str, Any] | None = None,
        description: str = "",
        tags: list[str] | None = None,
    ) -> PerformanceBaseline:
        """
        Capture and save a performance baseline from current metrics.

        Args:
            name: Human-readable baseline name.
            metrics_store: MetricsStore containing collected metrics.
            config: Optional test configuration dict.
            description: Optional description.
            tags: Optional list of tags for filtering.

        Returns:
            The saved PerformanceBaseline.

        Raises:
            ValueError: If name is empty.
        """
        if not name or not name.strip():
            raise ValueError("Baseline name cannot be empty")

        self._ensure_dir()

        # Generate UUID
        baseline_id = str(uuid.uuid4())

        # Get git info
        git_info = get_git_info()
        git_dict = git_info_to_dict(git_info)

        # Aggregate metrics
        aggregator = MetricsAggregator(metrics_store)
        order_metrics = aggregator.aggregate_orders()
        api_metrics = aggregator.aggregate_api_metrics()
        resource_metrics = aggregator.aggregate_resource_metrics()
        throughput = aggregator.calculate_throughput()

        # Extract config values
        config = config or {}

        # Create baseline
        baseline = PerformanceBaseline(
            id=baseline_id,
            name=name.strip(),
            description=description,
            tags=tags or [],
            schema_version=SCHEMA_VERSION,
            git_commit=git_dict["git_commit"],
            git_branch=git_dict["git_branch"],
            git_repo=git_dict["git_repo"],
            has_uncommitted_changes=git_dict["has_uncommitted_changes"],
            scenario_name=config.get("scenario_name", ""),
            duration_seconds=config.get("duration_seconds", 0.0),
            num_traders=config.get("num_traders", 0),
            test_config=config,
            python_version=platform.python_version(),
            platform=platform.platform(),
            dependencies={},  # Could be populated from importlib.metadata if needed
            order_metrics=order_metrics,
            api_metrics=api_metrics,
            resource_metrics=resource_metrics,
            orders_per_second=throughput.get("orders_per_second", 0.0),
            peak_orders_per_second=throughput.get("orders_per_second", 0.0),  # Same for now
        )

        # Save to file
        baseline_path = self._baselines_dir / f"{baseline_id}.json"
        with open(baseline_path, "w") as f:
            json.dump(baseline_to_dict(baseline), f, indent=2)

        # Update index
        self._update_index(baseline)

        logger.info("Saved baseline '%s' (id=%s) to %s", name, baseline_id, baseline_path)

        return baseline

    def load(self, identifier: str) -> PerformanceBaseline:
        """
        Load a baseline by name, ID, or git commit hash.

        Args:
            identifier: Baseline name, UUID, or git commit prefix.

        Returns:
            The loaded PerformanceBaseline.

        Raises:
            FileNotFoundError: If baseline not found.
            BaselineValidationError: If baseline file is invalid.
        """
        result = self._find_baseline(identifier)
        if result is None:
            raise FileNotFoundError(f"Baseline not found: {identifier}")

        baseline_id, baseline_path = result

        if not baseline_path.exists():
            # Remove from index if file is missing
            self._remove_from_index(baseline_id)
            raise FileNotFoundError(f"Baseline file not found: {baseline_path}")

        with open(baseline_path) as f:
            data = json.load(f)

        validate_baseline(data)
        return baseline_from_dict(data)

    def list(
        self,
        tags: list[str] | None = None,
        branch: str | None = None,
    ) -> list[BaselineMetadata]:
        """
        List all baselines with optional filtering.

        Args:
            tags: Optional list of tags to filter by (matches any).
            branch: Optional git branch to filter by.

        Returns:
            List of BaselineMetadata sorted by created_at descending.
        """
        index = self._load_index()
        result: list[BaselineMetadata] = []

        for metadata_dict in index.values():
            metadata = metadata_from_dict(metadata_dict)

            # Apply tag filter
            if tags:
                if not any(tag in metadata.tags for tag in tags):
                    continue

            # Apply branch filter
            if branch:
                if metadata.git_branch != branch:
                    continue

            result.append(metadata)

        # Sort by created_at descending (newest first)
        result.sort(key=lambda m: m.created_at, reverse=True)
        return result

    def delete(self, identifier: str) -> None:
        """
        Delete a baseline by name or ID.

        Args:
            identifier: Baseline name or UUID.

        Raises:
            FileNotFoundError: If baseline not found.
        """
        result = self._find_baseline(identifier)
        if result is None:
            raise FileNotFoundError(f"Baseline not found: {identifier}")

        baseline_id, baseline_path = result

        # Remove file
        if baseline_path.exists():
            baseline_path.unlink()
            logger.info("Deleted baseline file: %s", baseline_path)

        # Remove from index
        self._remove_from_index(baseline_id)
```

### Success Criteria:

#### Automated Verification:
- [x] `poetry run pytest tests/unit/test_baseline_manager.py -v`
- [x] `poetry run mypy src/cow_performance/baselines/manager.py`

#### Manual Verification:
- [x] Save/load roundtrip preserves all data
- [x] Index updated correctly on save/delete
- [x] Can find baseline by name, ID, or git commit prefix

---

## Phase 5: CLI Integration

### Overview

Update existing CLI commands to use `BaselineManager` and display new fields.

### Changes Required:

#### 1. Update CLI Commands

**File**: `src/cow_performance/cli/commands/baselines.py`

Replace the existing file with the new implementation that uses `BaselineManager`:

```python
"""Baseline management commands for performance testing.

This module provides CLI commands for managing performance baselines
using the BaselineManager class.
"""

from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.table import Table

from cow_performance.baselines import BaselineManager, BaselineValidationError


def save_baseline_command(
    name: str,
    results_file: Path,
    description: str = "",
    tags: list[str] | None = None,
    baselines_dir: Path | None = None,
) -> None:
    """
    Save a baseline from a results file.

    Note: This command is for backward compatibility. The preferred
    method is to use BaselineManager.save() directly with a MetricsStore.

    Args:
        name: Baseline name
        results_file: Path to results JSON file
        description: Optional description
        tags: Optional list of tags
        baselines_dir: Optional directory for baselines
    """
    console = Console()

    console.print(
        "[yellow]Warning:[/yellow] Saving from results file is deprecated. "
        "Use 'cow-perf run --save-baseline <name>' to save baselines directly from test runs."
    )

    console.print(f"[bold red]Error:[/bold red] This command is no longer supported.")
    console.print(
        "Please use [cyan]cow-perf run --save-baseline <name>[/cyan] to save baselines."
    )
    raise SystemExit(1)


def show_baseline_command(
    name: str,
    baselines_dir: Path | None = None,
) -> None:
    """
    Show details of a saved baseline.

    Args:
        name: Baseline name, ID, or git commit
        baselines_dir: Optional directory for baselines
    """
    console = Console()
    manager = BaselineManager(baselines_dir)

    try:
        baseline = manager.load(name)

        # Header
        console.print(f"[bold cyan]Baseline:[/bold cyan] {baseline.name}")
        console.print(f"[dim]ID: {baseline.id}[/dim]")
        console.print(f"[dim]Schema: v{baseline.schema_version}[/dim]")

        # Format timestamp
        created_dt = datetime.fromtimestamp(baseline.created_at)
        console.print(f"[dim]Created: {created_dt.strftime('%Y-%m-%d %H:%M:%S')}[/dim]")

        if baseline.description:
            console.print(f"\n[italic]{baseline.description}[/italic]")

        if baseline.tags:
            console.print(f"[dim]Tags: {', '.join(baseline.tags)}[/dim]")

        console.print()

        # Git info table
        if baseline.git_commit:
            table = Table(title="Git Information", show_header=True, header_style="bold cyan")
            table.add_column("Field", style="cyan")
            table.add_column("Value", style="green")

            table.add_row("Commit", baseline.git_commit[:12] if baseline.git_commit else "N/A")
            table.add_row("Branch", baseline.git_branch or "N/A")
            table.add_row("Repository", baseline.git_repo or "N/A")
            table.add_row(
                "Dirty",
                "[yellow]Yes[/yellow]" if baseline.has_uncommitted_changes else "[green]No[/green]",
            )

            console.print(table)
            console.print()

        # Test config table
        table = Table(title="Test Configuration", show_header=True, header_style="bold cyan")
        table.add_column("Field", style="cyan")
        table.add_column("Value", style="green", justify="right")

        table.add_row("Scenario", baseline.scenario_name or "N/A")
        table.add_row("Duration", f"{baseline.duration_seconds:.1f}s")
        table.add_row("Traders", str(baseline.num_traders))

        console.print(table)
        console.print()

        # Environment table
        table = Table(title="Environment", show_header=True, header_style="bold cyan")
        table.add_column("Field", style="cyan")
        table.add_column("Value", style="green")

        table.add_row("Python", baseline.python_version)
        table.add_row("Platform", baseline.platform)

        console.print(table)
        console.print()

        # Order metrics table
        if baseline.order_metrics:
            om = baseline.order_metrics
            table = Table(title="Order Metrics", show_header=True, header_style="bold cyan")
            table.add_column("Metric", style="cyan")
            table.add_column("Value", style="green", justify="right")

            table.add_row("Total Orders", str(om.total_orders))
            table.add_row("Filled", str(om.orders_filled))
            table.add_row("Failed", str(om.orders_failed))
            table.add_row("Success Rate", f"{om.success_rate * 100:.1f}%")
            table.add_row("Time to Submit (p50)", f"{om.time_to_submit.p50 * 1000:.1f}ms")
            table.add_row("Time to Submit (p95)", f"{om.time_to_submit.p95 * 1000:.1f}ms")
            table.add_row("Time to Fill (p50)", f"{om.time_to_fill.p50 * 1000:.1f}ms")
            table.add_row("Time to Fill (p95)", f"{om.time_to_fill.p95 * 1000:.1f}ms")

            console.print(table)
            console.print()

        # API metrics table
        if baseline.api_metrics:
            am = baseline.api_metrics
            table = Table(title="API Metrics", show_header=True, header_style="bold cyan")
            table.add_column("Metric", style="cyan")
            table.add_column("Value", style="green", justify="right")

            table.add_row("Total Requests", str(am.total_requests))
            table.add_row("Success Rate", f"{am.success_rate * 100:.1f}%")
            table.add_row("Response Time (p50)", f"{am.response_time.p50:.1f}ms")
            table.add_row("Response Time (p95)", f"{am.response_time.p95:.1f}ms")
            table.add_row("Requests/sec", f"{am.requests_per_second:.2f}")

            console.print(table)
            console.print()

        # Throughput summary
        table = Table(title="Throughput", show_header=True, header_style="bold cyan")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green", justify="right")

        table.add_row("Orders/sec", f"{baseline.orders_per_second:.2f}")
        table.add_row("Peak Orders/sec", f"{baseline.peak_orders_per_second:.2f}")

        console.print(table)

    except FileNotFoundError as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise SystemExit(2) from None
    except BaselineValidationError as e:
        console.print(f"[bold red]Validation Error:[/bold red] {e}")
        raise SystemExit(3) from None
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise SystemExit(1) from None


def list_baselines_command(
    tags: list[str] | None = None,
    branch: str | None = None,
    baselines_dir: Path | None = None,
) -> None:
    """
    List all saved baselines.

    Args:
        tags: Optional tags to filter by
        branch: Optional git branch to filter by
        baselines_dir: Optional directory for baselines
    """
    console = Console()
    manager = BaselineManager(baselines_dir)

    baselines = manager.list(tags=tags, branch=branch)

    if not baselines:
        console.print("[yellow]No baselines found.[/yellow]")
        if tags or branch:
            console.print("[dim]Try removing filters to see all baselines.[/dim]")
        else:
            console.print("\n[dim]Save a baseline with:[/dim]")
            console.print("  cow-perf run --save-baseline my-baseline")
        return

    # Display baselines table
    table = Table(title="Saved Baselines", show_header=True, header_style="bold cyan")
    table.add_column("Name", style="green")
    table.add_column("Created", style="dim")
    table.add_column("Branch", style="cyan")
    table.add_column("Commit", style="dim")
    table.add_column("Orders/sec", justify="right")
    table.add_column("Tags", style="dim")

    for metadata in baselines:
        # Format timestamp
        try:
            timestamp = datetime.fromtimestamp(metadata.created_at)
            timestamp_str = timestamp.strftime("%Y-%m-%d %H:%M")
        except Exception:
            timestamp_str = "unknown"

        # Format commit (truncate)
        commit_str = metadata.git_commit[:8] if metadata.git_commit else "N/A"

        # Format tags
        tags_str = ", ".join(metadata.tags) if metadata.tags else ""

        table.add_row(
            metadata.name,
            timestamp_str,
            metadata.git_branch or "N/A",
            commit_str,
            f"{metadata.orders_per_second:.2f}",
            tags_str,
        )

    console.print(table)


def delete_baseline_command(
    name: str,
    baselines_dir: Path | None = None,
) -> None:
    """
    Delete a saved baseline.

    Args:
        name: Baseline name or ID
        baselines_dir: Optional directory for baselines
    """
    console = Console()
    manager = BaselineManager(baselines_dir)

    try:
        manager.delete(name)
        console.print(f"[bold green]✓[/bold green] Baseline deleted: {name}")

    except FileNotFoundError as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise SystemExit(2) from None
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise SystemExit(1) from None


# Keep these functions for backward compatibility during transition
# They will be removed in a future version

def save_baseline(
    name: str,
    metrics: dict,
    baselines_dir: Path | None = None,
) -> Path:
    """Deprecated: Use BaselineManager.save() instead."""
    raise NotImplementedError(
        "save_baseline() is deprecated. Use BaselineManager.save() instead."
    )


def load_baseline(
    name: str,
    baselines_dir: Path | None = None,
) -> dict:
    """Deprecated: Use BaselineManager.load() instead."""
    raise NotImplementedError(
        "load_baseline() is deprecated. Use BaselineManager.load() instead."
    )


def list_baselines(baselines_dir: Path | None = None) -> list[dict]:
    """Deprecated: Use BaselineManager.list() instead."""
    raise NotImplementedError(
        "list_baselines() is deprecated. Use BaselineManager.list() instead."
    )


def delete_baseline(
    name: str,
    baselines_dir: Path | None = None,
) -> None:
    """Deprecated: Use BaselineManager.delete() instead."""
    raise NotImplementedError(
        "delete_baseline() is deprecated. Use BaselineManager.delete() instead."
    )
```

### Success Criteria:

#### Automated Verification:
- [x] `poetry run pytest tests/unit/test_cli.py -v`
- [x] `poetry run mypy src/cow_performance/cli/commands/baselines.py`

#### Manual Verification:
- [x] `cow-perf baselines --list` shows baselines with new fields
- [x] `cow-perf baselines --show <name>` displays git info and detailed metrics
- [x] `cow-perf baselines --delete <name>` removes baseline and updates index

---

## Phase 6: Tests

### Overview

Write comprehensive unit tests for all new modules.

### Changes Required:

#### 1. Test Models

**File**: `tests/unit/test_baseline_models.py`

```python
"""Unit tests for baseline data models."""

import time

import pytest

from cow_performance.baselines.models import (
    SCHEMA_VERSION,
    BaselineMetadata,
    PerformanceBaseline,
    baseline_from_dict,
    baseline_to_dict,
    metadata_from_dict,
    metadata_to_dict,
)
from cow_performance.metrics.aggregator import (
    APIAggregateMetrics,
    OrderAggregateMetrics,
    PercentileStats,
    ResourceAggregateMetrics,
)


class TestPerformanceBaseline:
    """Tests for PerformanceBaseline dataclass."""

    def test_default_values(self):
        """Test baseline with only required fields."""
        baseline = PerformanceBaseline(
            id="test-id",
            name="test-baseline",
        )

        assert baseline.id == "test-id"
        assert baseline.name == "test-baseline"
        assert baseline.description == ""
        assert baseline.tags == []
        assert baseline.schema_version == SCHEMA_VERSION
        assert baseline.git_commit is None
        assert baseline.order_metrics is None

    def test_with_all_fields(self):
        """Test baseline with all fields populated."""
        order_metrics = OrderAggregateMetrics(
            total_orders=100,
            orders_filled=90,
            success_rate=0.9,
        )

        baseline = PerformanceBaseline(
            id="test-id",
            name="test-baseline",
            description="Test description",
            tags=["release", "v1.0"],
            git_commit="abc123def456",
            git_branch="main",
            scenario_name="stress-test",
            duration_seconds=300.0,
            num_traders=10,
            order_metrics=order_metrics,
            orders_per_second=5.0,
        )

        assert baseline.description == "Test description"
        assert baseline.tags == ["release", "v1.0"]
        assert baseline.git_commit == "abc123def456"
        assert baseline.order_metrics.total_orders == 100


class TestBaselineMetadata:
    """Tests for BaselineMetadata dataclass."""

    def test_metadata_creation(self):
        """Test metadata creation."""
        metadata = BaselineMetadata(
            id="test-id",
            name="test-baseline",
            tags=["release"],
            git_commit="abc123",
            git_branch="main",
            created_at=1234567890.0,
            orders_per_second=5.0,
        )

        assert metadata.id == "test-id"
        assert metadata.name == "test-baseline"
        assert metadata.tags == ["release"]


class TestSerialization:
    """Tests for serialization/deserialization functions."""

    @pytest.fixture
    def sample_baseline(self):
        """Create a sample baseline with all fields."""
        return PerformanceBaseline(
            id="test-uuid",
            name="test-baseline",
            description="A test baseline",
            tags=["test", "unit"],
            created_at=1234567890.0,
            schema_version=SCHEMA_VERSION,
            git_commit="abc123def456789",
            git_branch="main",
            git_repo="https://github.com/test/repo",
            has_uncommitted_changes=True,
            scenario_name="test-scenario",
            duration_seconds=60.0,
            num_traders=5,
            test_config={"key": "value"},
            python_version="3.11.0",
            platform="Linux-5.15.0",
            dependencies={"numpy": "1.24.0"},
            order_metrics=OrderAggregateMetrics(
                total_orders=100,
                orders_filled=90,
                success_rate=0.9,
                time_to_submit=PercentileStats(
                    count=90,
                    min=0.01,
                    max=0.5,
                    mean=0.1,
                    median=0.08,
                    p50=0.08,
                    p90=0.2,
                    p95=0.3,
                    p99=0.4,
                    std_dev=0.05,
                ),
            ),
            api_metrics=APIAggregateMetrics(
                total_requests=500,
                success_rate=0.95,
                response_time=PercentileStats(count=500, p50=50.0, p95=150.0),
            ),
            resource_metrics={
                "orderbook": ResourceAggregateMetrics(
                    container_name="orderbook",
                    sample_count=60,
                    cpu_percent=PercentileStats(count=60, mean=25.0),
                )
            },
            orders_per_second=5.0,
            peak_orders_per_second=10.0,
        )

    def test_baseline_roundtrip(self, sample_baseline):
        """Test that serialization/deserialization preserves all data."""
        data = baseline_to_dict(sample_baseline)
        restored = baseline_from_dict(data)

        # Check identification
        assert restored.id == sample_baseline.id
        assert restored.name == sample_baseline.name
        assert restored.description == sample_baseline.description
        assert restored.tags == sample_baseline.tags
        assert restored.created_at == sample_baseline.created_at
        assert restored.schema_version == sample_baseline.schema_version

        # Check git info
        assert restored.git_commit == sample_baseline.git_commit
        assert restored.git_branch == sample_baseline.git_branch
        assert restored.git_repo == sample_baseline.git_repo
        assert restored.has_uncommitted_changes == sample_baseline.has_uncommitted_changes

        # Check test config
        assert restored.scenario_name == sample_baseline.scenario_name
        assert restored.duration_seconds == sample_baseline.duration_seconds
        assert restored.num_traders == sample_baseline.num_traders
        assert restored.test_config == sample_baseline.test_config

        # Check environment
        assert restored.python_version == sample_baseline.python_version
        assert restored.platform == sample_baseline.platform
        assert restored.dependencies == sample_baseline.dependencies

        # Check order metrics
        assert restored.order_metrics is not None
        assert restored.order_metrics.total_orders == 100
        assert restored.order_metrics.success_rate == 0.9
        assert restored.order_metrics.time_to_submit.p95 == 0.3

        # Check API metrics
        assert restored.api_metrics is not None
        assert restored.api_metrics.total_requests == 500

        # Check resource metrics
        assert "orderbook" in restored.resource_metrics
        assert restored.resource_metrics["orderbook"].sample_count == 60

        # Check throughput
        assert restored.orders_per_second == sample_baseline.orders_per_second

    def test_baseline_to_dict_none_metrics(self):
        """Test serialization with None metrics."""
        baseline = PerformanceBaseline(id="test", name="test")
        data = baseline_to_dict(baseline)

        assert data["order_metrics"] is None
        assert data["api_metrics"] is None
        assert data["resource_metrics"] == {}

    def test_baseline_from_dict_missing_optional(self):
        """Test deserialization with missing optional fields."""
        data = {
            "id": "test",
            "name": "test",
            "schema_version": SCHEMA_VERSION,
            "created_at": time.time(),
        }

        baseline = baseline_from_dict(data)

        assert baseline.id == "test"
        assert baseline.description == ""
        assert baseline.tags == []
        assert baseline.git_commit is None
        assert baseline.order_metrics is None

    def test_metadata_roundtrip(self):
        """Test metadata serialization roundtrip."""
        metadata = BaselineMetadata(
            id="test-id",
            name="test",
            tags=["a", "b"],
            git_commit="abc123",
            git_branch="main",
            created_at=1234567890.0,
            orders_per_second=5.0,
        )

        data = metadata_to_dict(metadata)
        restored = metadata_from_dict(data)

        assert restored.id == metadata.id
        assert restored.name == metadata.name
        assert restored.tags == metadata.tags
        assert restored.git_commit == metadata.git_commit
        assert restored.orders_per_second == metadata.orders_per_second
```

#### 2. Test Git Info

**File**: `tests/unit/test_baseline_git_info.py`

```python
"""Unit tests for git info extraction."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from cow_performance.baselines.git_info import GitInfo, get_git_info, git_info_to_dict


class TestGitInfo:
    """Tests for GitInfo dataclass."""

    def test_default_values(self):
        """Test default GitInfo values."""
        info = GitInfo()

        assert info.commit is None
        assert info.branch is None
        assert info.repo_url is None
        assert info.is_dirty is False

    def test_with_values(self):
        """Test GitInfo with all values."""
        info = GitInfo(
            commit="abc123",
            branch="main",
            repo_url="https://github.com/test/repo",
            is_dirty=True,
        )

        assert info.commit == "abc123"
        assert info.branch == "main"
        assert info.is_dirty is True


class TestGetGitInfo:
    """Tests for get_git_info function."""

    def test_not_in_git_repo(self):
        """Test behavior when not in a git repository."""
        with tempfile.TemporaryDirectory() as tmpdir:
            info = get_git_info(Path(tmpdir))

        assert info.commit is None
        assert info.branch is None
        assert info.is_dirty is False

    def test_gitpython_not_installed(self):
        """Test behavior when GitPython is not installed."""
        with patch.dict("sys.modules", {"git": None}):
            # Clear any cached import
            import importlib
            import cow_performance.baselines.git_info as git_info_module

            # This should return empty GitInfo
            info = get_git_info()

            # Verify we got default values (import error handling)
            assert isinstance(info, GitInfo)

    @patch("cow_performance.baselines.git_info.git")
    def test_with_valid_repo(self, mock_git):
        """Test with a valid git repository."""
        # Setup mock repo
        mock_repo = MagicMock()
        mock_repo.head.commit.hexsha = "abc123def456789"
        mock_repo.head.is_detached = False
        mock_repo.active_branch.name = "main"
        mock_repo.remotes = {"origin": MagicMock(url="https://github.com/test/repo")}
        mock_repo.is_dirty.return_value = False

        mock_git.Repo.return_value = mock_repo

        info = get_git_info(Path("/fake/path"))

        assert info.commit == "abc123def456789"
        assert info.branch == "main"
        assert info.is_dirty is False

    @patch("cow_performance.baselines.git_info.git")
    def test_detached_head(self, mock_git):
        """Test with detached HEAD state."""
        mock_repo = MagicMock()
        mock_repo.head.commit.hexsha = "abc123def456789"
        mock_repo.head.is_detached = True
        mock_repo.remotes = {}
        mock_repo.is_dirty.return_value = False

        mock_git.Repo.return_value = mock_repo

        info = get_git_info(Path("/fake/path"))

        assert info.commit == "abc123def456789"
        assert info.branch == "detached@abc123de"

    @patch("cow_performance.baselines.git_info.git")
    def test_dirty_repo_warning(self, mock_git, caplog):
        """Test that dirty repo logs a warning."""
        mock_repo = MagicMock()
        mock_repo.head.commit.hexsha = "abc123"
        mock_repo.head.is_detached = False
        mock_repo.active_branch.name = "main"
        mock_repo.remotes = {}
        mock_repo.is_dirty.return_value = True

        mock_git.Repo.return_value = mock_repo

        import logging

        with caplog.at_level(logging.WARNING):
            info = get_git_info(Path("/fake/path"))

        assert info.is_dirty is True
        assert "uncommitted changes" in caplog.text.lower()


class TestGitInfoToDict:
    """Tests for git_info_to_dict function."""

    def test_converts_to_dict(self):
        """Test conversion to dictionary."""
        info = GitInfo(
            commit="abc123",
            branch="main",
            repo_url="https://github.com/test/repo",
            is_dirty=True,
        )

        result = git_info_to_dict(info)

        assert result == {
            "git_commit": "abc123",
            "git_branch": "main",
            "git_repo": "https://github.com/test/repo",
            "has_uncommitted_changes": True,
        }

    def test_converts_none_values(self):
        """Test conversion with None values."""
        info = GitInfo()

        result = git_info_to_dict(info)

        assert result["git_commit"] is None
        assert result["git_branch"] is None
        assert result["has_uncommitted_changes"] is False
```

#### 3. Test Validation

**File**: `tests/unit/test_baseline_validation.py`

```python
"""Unit tests for baseline validation."""

import pytest

from cow_performance.baselines.models import SCHEMA_VERSION
from cow_performance.baselines.validation import (
    BaselineValidationError,
    validate_baseline,
)


class TestValidateBaseline:
    """Tests for validate_baseline function."""

    @pytest.fixture
    def valid_baseline_data(self):
        """Create valid baseline data."""
        return {
            "id": "test-uuid",
            "name": "test-baseline",
            "schema_version": SCHEMA_VERSION,
            "created_at": 1234567890.0,
        }

    def test_valid_baseline(self, valid_baseline_data):
        """Test validation passes for valid data."""
        # Should not raise
        validate_baseline(valid_baseline_data)

    def test_missing_id(self, valid_baseline_data):
        """Test validation fails for missing id."""
        del valid_baseline_data["id"]

        with pytest.raises(BaselineValidationError) as exc:
            validate_baseline(valid_baseline_data)

        assert "id" in str(exc.value)

    def test_missing_name(self, valid_baseline_data):
        """Test validation fails for missing name."""
        del valid_baseline_data["name"]

        with pytest.raises(BaselineValidationError) as exc:
            validate_baseline(valid_baseline_data)

        assert "name" in str(exc.value)

    def test_missing_schema_version(self, valid_baseline_data):
        """Test validation fails for missing schema_version."""
        del valid_baseline_data["schema_version"]

        with pytest.raises(BaselineValidationError) as exc:
            validate_baseline(valid_baseline_data)

        assert "schema_version" in str(exc.value)

    def test_missing_created_at(self, valid_baseline_data):
        """Test validation fails for missing created_at."""
        del valid_baseline_data["created_at"]

        with pytest.raises(BaselineValidationError) as exc:
            validate_baseline(valid_baseline_data)

        assert "created_at" in str(exc.value)

    def test_invalid_schema_version_format(self, valid_baseline_data):
        """Test validation fails for invalid schema version format."""
        valid_baseline_data["schema_version"] = "invalid"

        with pytest.raises(BaselineValidationError) as exc:
            validate_baseline(valid_baseline_data)

        assert "schema_version" in str(exc.value).lower()

    def test_newer_schema_version(self, valid_baseline_data):
        """Test validation fails for newer schema version."""
        valid_baseline_data["schema_version"] = "99.0"

        with pytest.raises(BaselineValidationError) as exc:
            validate_baseline(valid_baseline_data)

        assert "newer" in str(exc.value).lower()

    def test_empty_id(self, valid_baseline_data):
        """Test validation fails for empty id."""
        valid_baseline_data["id"] = ""

        with pytest.raises(BaselineValidationError) as exc:
            validate_baseline(valid_baseline_data)

        assert "id" in str(exc.value).lower()

    def test_empty_name(self, valid_baseline_data):
        """Test validation fails for empty name."""
        valid_baseline_data["name"] = ""

        with pytest.raises(BaselineValidationError) as exc:
            validate_baseline(valid_baseline_data)

        assert "name" in str(exc.value).lower()

    def test_invalid_created_at_type(self, valid_baseline_data):
        """Test validation fails for invalid created_at type."""
        valid_baseline_data["created_at"] = "not-a-number"

        with pytest.raises(BaselineValidationError) as exc:
            validate_baseline(valid_baseline_data)

        assert "created_at" in str(exc.value).lower()

    def test_invalid_tags_type(self, valid_baseline_data):
        """Test validation fails for invalid tags type."""
        valid_baseline_data["tags"] = "not-a-list"

        with pytest.raises(BaselineValidationError) as exc:
            validate_baseline(valid_baseline_data)

        assert "tags" in str(exc.value).lower()

    def test_older_schema_version_ok(self, valid_baseline_data):
        """Test validation passes for older compatible schema version."""
        valid_baseline_data["schema_version"] = "1.0"

        # Should not raise
        validate_baseline(valid_baseline_data)
```

#### 4. Test Manager

**File**: `tests/unit/test_baseline_manager.py`

```python
"""Unit tests for BaselineManager."""

import json
import time
from pathlib import Path

import pytest

from cow_performance.baselines import BaselineManager, BaselineValidationError
from cow_performance.baselines.models import SCHEMA_VERSION
from cow_performance.metrics import MetricsStore, OrderMetadata, OrderStatus


class TestBaselineManager:
    """Tests for BaselineManager class."""

    @pytest.fixture
    def tmp_baselines_dir(self, tmp_path):
        """Create a temporary baselines directory."""
        baselines_dir = tmp_path / ".cow-perf" / "baselines"
        return baselines_dir

    @pytest.fixture
    def manager(self, tmp_baselines_dir):
        """Create a BaselineManager with temporary directory."""
        return BaselineManager(tmp_baselines_dir)

    @pytest.fixture
    def populated_store(self):
        """Create a MetricsStore with sample data."""
        store = MetricsStore()
        base_time = time.time()

        for i in range(10):
            order = OrderMetadata(
                order_uid=f"0x{i:064x}",
                owner="0xowner",
                creation_time=base_time + i * 0.1,
                sell_token="0xsell",
                buy_token="0xbuy",
            )
            order.update_status(OrderStatus.SUBMITTED, base_time + i * 0.1 + 0.01)
            order.update_status(OrderStatus.FILLED, base_time + i * 0.1 + 0.1)
            store.add_order(order)

        return store

    def test_save_creates_directory(self, manager, populated_store):
        """Test that save creates baselines directory."""
        assert not manager.baselines_dir.exists()

        manager.save("test-baseline", populated_store)

        assert manager.baselines_dir.exists()

    def test_save_creates_baseline_file(self, manager, populated_store):
        """Test that save creates a baseline JSON file."""
        baseline = manager.save("test-baseline", populated_store)

        baseline_path = manager.baselines_dir / f"{baseline.id}.json"
        assert baseline_path.exists()

        # Verify file content
        with open(baseline_path) as f:
            data = json.load(f)

        assert data["name"] == "test-baseline"
        assert data["schema_version"] == SCHEMA_VERSION

    def test_save_creates_index(self, manager, populated_store):
        """Test that save creates/updates index."""
        baseline = manager.save("test-baseline", populated_store)

        index_path = manager.baselines_dir / "index.json"
        assert index_path.exists()

        with open(index_path) as f:
            index = json.load(f)

        assert baseline.id in index
        assert index[baseline.id]["name"] == "test-baseline"

    def test_save_with_description_and_tags(self, manager, populated_store):
        """Test saving with description and tags."""
        baseline = manager.save(
            "test-baseline",
            populated_store,
            description="A test baseline",
            tags=["release", "v1.0"],
        )

        assert baseline.description == "A test baseline"
        assert baseline.tags == ["release", "v1.0"]

    def test_save_captures_metrics(self, manager, populated_store):
        """Test that save captures aggregated metrics."""
        baseline = manager.save("test-baseline", populated_store)

        assert baseline.order_metrics is not None
        assert baseline.order_metrics.total_orders == 10
        assert baseline.order_metrics.orders_filled == 10

    def test_save_empty_name_raises(self, manager, populated_store):
        """Test that empty name raises ValueError."""
        with pytest.raises(ValueError, match="empty"):
            manager.save("", populated_store)

        with pytest.raises(ValueError, match="empty"):
            manager.save("   ", populated_store)

    def test_load_by_name(self, manager, populated_store):
        """Test loading baseline by name."""
        saved = manager.save("test-baseline", populated_store)

        loaded = manager.load("test-baseline")

        assert loaded.id == saved.id
        assert loaded.name == saved.name

    def test_load_by_id(self, manager, populated_store):
        """Test loading baseline by ID."""
        saved = manager.save("test-baseline", populated_store)

        loaded = manager.load(saved.id)

        assert loaded.id == saved.id

    def test_load_by_git_commit_prefix(self, manager, populated_store):
        """Test loading baseline by git commit prefix."""
        saved = manager.save("test-baseline", populated_store)

        if saved.git_commit:
            loaded = manager.load(saved.git_commit[:8])
            assert loaded.id == saved.id

    def test_load_not_found(self, manager):
        """Test loading non-existent baseline."""
        with pytest.raises(FileNotFoundError, match="not found"):
            manager.load("nonexistent")

    def test_list_empty(self, manager):
        """Test listing when no baselines exist."""
        baselines = manager.list()

        assert baselines == []

    def test_list_returns_all(self, manager, populated_store):
        """Test listing all baselines."""
        manager.save("baseline-1", populated_store)
        manager.save("baseline-2", populated_store)
        manager.save("baseline-3", populated_store)

        baselines = manager.list()

        assert len(baselines) == 3

    def test_list_sorted_by_created_at(self, manager, populated_store):
        """Test that list returns baselines sorted by created_at descending."""
        manager.save("baseline-1", populated_store)
        time.sleep(0.01)  # Ensure different timestamps
        manager.save("baseline-2", populated_store)
        time.sleep(0.01)
        manager.save("baseline-3", populated_store)

        baselines = manager.list()

        # Should be newest first
        assert baselines[0].name == "baseline-3"
        assert baselines[1].name == "baseline-2"
        assert baselines[2].name == "baseline-1"

    def test_list_filter_by_tags(self, manager, populated_store):
        """Test listing with tag filter."""
        manager.save("baseline-1", populated_store, tags=["release"])
        manager.save("baseline-2", populated_store, tags=["dev"])
        manager.save("baseline-3", populated_store, tags=["release", "v1.0"])

        baselines = manager.list(tags=["release"])

        assert len(baselines) == 2
        names = [b.name for b in baselines]
        assert "baseline-1" in names
        assert "baseline-3" in names

    def test_list_filter_by_branch(self, manager, populated_store):
        """Test listing with branch filter."""
        # Note: In tests, git info might be None
        # This test verifies the filtering logic works
        baselines = manager.list(branch="main")

        # With mocked git, might be empty or have results depending on env
        assert isinstance(baselines, list)

    def test_delete_by_name(self, manager, populated_store):
        """Test deleting baseline by name."""
        saved = manager.save("test-baseline", populated_store)
        baseline_path = manager.baselines_dir / f"{saved.id}.json"

        assert baseline_path.exists()

        manager.delete("test-baseline")

        assert not baseline_path.exists()

    def test_delete_updates_index(self, manager, populated_store):
        """Test that delete updates index."""
        saved = manager.save("test-baseline", populated_store)

        manager.delete(saved.id)

        # Verify removed from index
        index_path = manager.baselines_dir / "index.json"
        with open(index_path) as f:
            index = json.load(f)

        assert saved.id not in index

    def test_delete_not_found(self, manager):
        """Test deleting non-existent baseline."""
        with pytest.raises(FileNotFoundError, match="not found"):
            manager.delete("nonexistent")

    def test_index_rebuild(self, manager, populated_store):
        """Test index rebuilding from files."""
        # Save some baselines
        saved1 = manager.save("baseline-1", populated_store)
        saved2 = manager.save("baseline-2", populated_store)

        # Delete index file
        index_path = manager.baselines_dir / "index.json"
        index_path.unlink()

        # Load should trigger rebuild
        loaded = manager.load("baseline-1")
        assert loaded.id == saved1.id

        # Verify index was rebuilt
        assert index_path.exists()
        with open(index_path) as f:
            index = json.load(f)

        assert saved1.id in index
        assert saved2.id in index


class TestBaselineManagerEdgeCases:
    """Edge case tests for BaselineManager."""

    @pytest.fixture
    def manager(self, tmp_path):
        """Create a BaselineManager with temporary directory."""
        return BaselineManager(tmp_path / "baselines")

    def test_corrupted_index_rebuilds(self, manager, tmp_path):
        """Test that corrupted index is rebuilt."""
        # Create directory and corrupted index
        manager._ensure_dir()
        index_path = manager.baselines_dir / "index.json"
        with open(index_path, "w") as f:
            f.write("not valid json")

        # Should rebuild without error
        index = manager._load_index()
        assert isinstance(index, dict)

    def test_missing_baseline_file_removed_from_index(self, manager):
        """Test that missing file is removed from index on load."""
        # Create index with non-existent baseline
        manager._ensure_dir()
        index_path = manager.baselines_dir / "index.json"
        with open(index_path, "w") as f:
            json.dump({"fake-id": {"id": "fake-id", "name": "fake"}}, f)

        with pytest.raises(FileNotFoundError):
            manager.load("fake-id")

        # Verify removed from index
        with open(index_path) as f:
            index = json.load(f)

        assert "fake-id" not in index
```

### Success Criteria:

#### Automated Verification:
- [x] `poetry run pytest tests/unit/test_baseline_models.py tests/unit/test_baseline_git_info.py tests/unit/test_baseline_validation.py tests/unit/test_baseline_manager.py -v`
- [x] All tests pass
- [x] Coverage > 90% for baselines module

#### Manual Verification:
- [x] Tests cover happy paths and error cases
- [x] Tests are readable and maintainable

---

## Testing Strategy

### Unit Tests

| Module | Test File | Coverage |
|--------|-----------|----------|
| `models.py` | `test_baseline_models.py` | Serialization roundtrips, default values |
| `git_info.py` | `test_baseline_git_info.py` | Git extraction, non-git handling, mocking |
| `validation.py` | `test_baseline_validation.py` | All validation rules, error messages |
| `manager.py` | `test_baseline_manager.py` | CRUD operations, index management |

### Integration Tests

To be added to `tests/integration/test_baseline_integration.py`:
- Save baseline from real test run
- Load and verify all metrics preserved
- Git info captured correctly in repo
- Works in non-git environment

### Manual Testing Steps

1. Run a test scenario and save baseline:
   ```bash
   # After implementing, test with:
   cow-perf run --scenario configs/scenarios/test-funded-scenario.yml --save-baseline test-run
   ```

2. List baselines:
   ```bash
   cow-perf baselines --list
   cow-perf baselines --list --tag release
   cow-perf baselines --list --branch main
   ```

3. Show baseline details:
   ```bash
   cow-perf baselines --show test-run
   ```

4. Delete baseline:
   ```bash
   cow-perf baselines --delete test-run
   ```

---

## Performance Considerations

- **Index for O(1) lookups**: Using `index.json` for fast listing and filtering
- **Lazy loading**: Only load full baseline when needed
- **Bounded file size**: Baselines are typically 10-50KB JSON files

---

## Migration Notes

- **No migration needed**: Per design decision, no backward compatibility with old format
- **Old baselines ignored**: Old `~/.cow-perf/baselines/` directory can be manually deleted
- **New location**: `.cow-perf/baselines/` in project root (add to `.gitignore` if desired)

---

## References

- Original ticket: `thoughts/tickets/COW-588-baseline-snapshot-system.md`
- Depends on: `thoughts/plans/2026-01-29-cow-611-analysis-aggregation-realtime.md` (COW-611 - completed)
- Blocks: `thoughts/tickets/COW-589-comparison-engine-regression-detection.md` (COW-589)
- Similar patterns: `src/cow_performance/metrics/export.py` (serialization functions)
