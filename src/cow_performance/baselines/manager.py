"""Baseline manager for CRUD operations."""

import json
import logging
import platform
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
            # Check if there are baseline files to rebuild from
            if self._baselines_dir.exists():
                baseline_files = list(self._baselines_dir.glob("*.json"))
                if baseline_files:
                    return self._rebuild_index()
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
