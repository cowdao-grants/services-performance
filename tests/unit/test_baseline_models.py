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

    def test_default_values(self) -> None:
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

    def test_with_all_fields(self) -> None:
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
        assert baseline.order_metrics is not None
        assert baseline.order_metrics.total_orders == 100


class TestBaselineMetadata:
    """Tests for BaselineMetadata dataclass."""

    def test_metadata_creation(self) -> None:
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
    def sample_baseline(self) -> PerformanceBaseline:
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

    def test_baseline_roundtrip(self, sample_baseline: PerformanceBaseline) -> None:
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

    def test_baseline_to_dict_none_metrics(self) -> None:
        """Test serialization with None metrics."""
        baseline = PerformanceBaseline(id="test", name="test")
        data = baseline_to_dict(baseline)

        assert data["order_metrics"] is None
        assert data["api_metrics"] is None
        assert data["resource_metrics"] == {}

    def test_baseline_from_dict_missing_optional(self) -> None:
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

    def test_metadata_roundtrip(self) -> None:
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
