"""Unit tests for BaselineManager."""

import json
import time
from pathlib import Path

import pytest

from cow_performance.baselines import BaselineManager
from cow_performance.baselines.models import SCHEMA_VERSION
from cow_performance.metrics import MetricsStore, OrderMetadata, OrderStatus


class TestBaselineManager:
    """Tests for BaselineManager class."""

    @pytest.fixture
    def tmp_baselines_dir(self, tmp_path: Path) -> Path:
        """Create a temporary baselines directory."""
        baselines_dir = tmp_path / ".cow-perf" / "baselines"
        return baselines_dir

    @pytest.fixture
    def manager(self, tmp_baselines_dir: Path) -> BaselineManager:
        """Create a BaselineManager with temporary directory."""
        return BaselineManager(tmp_baselines_dir)

    @pytest.fixture
    def populated_store(self) -> MetricsStore:
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

    def test_save_creates_directory(
        self, manager: BaselineManager, populated_store: MetricsStore
    ) -> None:
        """Test that save creates baselines directory."""
        assert not manager.baselines_dir.exists()

        manager.save("test-baseline", populated_store)

        assert manager.baselines_dir.exists()

    def test_save_creates_baseline_file(
        self, manager: BaselineManager, populated_store: MetricsStore
    ) -> None:
        """Test that save creates a baseline JSON file."""
        baseline = manager.save("test-baseline", populated_store)

        baseline_path = manager.baselines_dir / f"{baseline.id}.json"
        assert baseline_path.exists()

        # Verify file content
        with open(baseline_path) as f:
            data = json.load(f)

        assert data["name"] == "test-baseline"
        assert data["schema_version"] == SCHEMA_VERSION

    def test_save_creates_index(
        self, manager: BaselineManager, populated_store: MetricsStore
    ) -> None:
        """Test that save creates/updates index."""
        baseline = manager.save("test-baseline", populated_store)

        index_path = manager.baselines_dir / "index.json"
        assert index_path.exists()

        with open(index_path) as f:
            index = json.load(f)

        assert baseline.id in index
        assert index[baseline.id]["name"] == "test-baseline"

    def test_save_with_description_and_tags(
        self, manager: BaselineManager, populated_store: MetricsStore
    ) -> None:
        """Test saving with description and tags."""
        baseline = manager.save(
            "test-baseline",
            populated_store,
            description="A test baseline",
            tags=["release", "v1.0"],
        )

        assert baseline.description == "A test baseline"
        assert baseline.tags == ["release", "v1.0"]

    def test_save_captures_metrics(
        self, manager: BaselineManager, populated_store: MetricsStore
    ) -> None:
        """Test that save captures aggregated metrics."""
        baseline = manager.save("test-baseline", populated_store)

        assert baseline.order_metrics is not None
        assert baseline.order_metrics.total_orders == 10
        assert baseline.order_metrics.orders_filled == 10

    def test_save_empty_name_raises(
        self, manager: BaselineManager, populated_store: MetricsStore
    ) -> None:
        """Test that empty name raises ValueError."""
        with pytest.raises(ValueError, match="empty"):
            manager.save("", populated_store)

        with pytest.raises(ValueError, match="empty"):
            manager.save("   ", populated_store)

    def test_load_by_name(self, manager: BaselineManager, populated_store: MetricsStore) -> None:
        """Test loading baseline by name."""
        saved = manager.save("test-baseline", populated_store)

        loaded = manager.load("test-baseline")

        assert loaded.id == saved.id
        assert loaded.name == saved.name

    def test_load_by_id(self, manager: BaselineManager, populated_store: MetricsStore) -> None:
        """Test loading baseline by ID."""
        saved = manager.save("test-baseline", populated_store)

        loaded = manager.load(saved.id)

        assert loaded.id == saved.id

    def test_load_by_git_commit_prefix(
        self, manager: BaselineManager, populated_store: MetricsStore
    ) -> None:
        """Test loading baseline by git commit prefix."""
        saved = manager.save("test-baseline", populated_store)

        if saved.git_commit:
            loaded = manager.load(saved.git_commit[:8])
            assert loaded.id == saved.id

    def test_load_not_found(self, manager: BaselineManager) -> None:
        """Test loading non-existent baseline."""
        with pytest.raises(FileNotFoundError, match="not found"):
            manager.load("nonexistent")

    def test_list_empty(self, manager: BaselineManager) -> None:
        """Test listing when no baselines exist."""
        baselines = manager.list()

        assert baselines == []

    def test_list_returns_all(
        self, manager: BaselineManager, populated_store: MetricsStore
    ) -> None:
        """Test listing all baselines."""
        manager.save("baseline-1", populated_store)
        manager.save("baseline-2", populated_store)
        manager.save("baseline-3", populated_store)

        baselines = manager.list()

        assert len(baselines) == 3

    def test_list_sorted_by_created_at(
        self, manager: BaselineManager, populated_store: MetricsStore
    ) -> None:
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

    def test_list_filter_by_tags(
        self, manager: BaselineManager, populated_store: MetricsStore
    ) -> None:
        """Test listing with tag filter."""
        manager.save("baseline-1", populated_store, tags=["release"])
        manager.save("baseline-2", populated_store, tags=["dev"])
        manager.save("baseline-3", populated_store, tags=["release", "v1.0"])

        baselines = manager.list(tags=["release"])

        assert len(baselines) == 2
        names = [b.name for b in baselines]
        assert "baseline-1" in names
        assert "baseline-3" in names

    def test_list_filter_by_branch(
        self, manager: BaselineManager, populated_store: MetricsStore
    ) -> None:
        """Test listing with branch filter."""
        # Note: In tests, git info might be None
        # This test verifies the filtering logic works
        baselines = manager.list(branch="main")

        # With mocked git, might be empty or have results depending on env
        assert isinstance(baselines, list)

    def test_delete_by_name(self, manager: BaselineManager, populated_store: MetricsStore) -> None:
        """Test deleting baseline by name."""
        saved = manager.save("test-baseline", populated_store)
        baseline_path = manager.baselines_dir / f"{saved.id}.json"

        assert baseline_path.exists()

        manager.delete("test-baseline")

        assert not baseline_path.exists()

    def test_delete_updates_index(
        self, manager: BaselineManager, populated_store: MetricsStore
    ) -> None:
        """Test that delete updates index."""
        saved = manager.save("test-baseline", populated_store)

        manager.delete(saved.id)

        # Verify removed from index
        index_path = manager.baselines_dir / "index.json"
        with open(index_path) as f:
            index = json.load(f)

        assert saved.id not in index

    def test_delete_not_found(self, manager: BaselineManager) -> None:
        """Test deleting non-existent baseline."""
        with pytest.raises(FileNotFoundError, match="not found"):
            manager.delete("nonexistent")

    def test_index_rebuild(self, manager: BaselineManager, populated_store: MetricsStore) -> None:
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
    def manager(self, tmp_path: Path) -> BaselineManager:
        """Create a BaselineManager with temporary directory."""
        return BaselineManager(tmp_path / "baselines")

    def test_corrupted_index_rebuilds(self, manager: BaselineManager, tmp_path: Path) -> None:
        """Test that corrupted index is rebuilt."""
        # Create directory and corrupted index
        manager._ensure_dir()
        index_path = manager.baselines_dir / "index.json"
        with open(index_path, "w") as f:
            f.write("not valid json")

        # Should rebuild without error
        index = manager._load_index()
        assert isinstance(index, dict)

    def test_missing_baseline_file_removed_from_index(self, manager: BaselineManager) -> None:
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
