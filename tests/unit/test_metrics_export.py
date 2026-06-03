"""Unit tests for metrics export functionality."""

import json
import time

import pytest

from cow_performance.metrics import (
    APIMetrics,
    MetricsStore,
    OrderMetadata,
    OrderStatus,
    export_api_metrics_to_csv,
    export_orders_to_csv,
    export_store_to_json,
    order_metadata_to_dict,
    save_metrics_to_file,
)


class TestMetricsExport:
    """Tests for metrics export functions."""

    @pytest.fixture
    def populated_store(self):
        """Create a store with sample data."""
        store = MetricsStore()

        # Add orders
        metadata = OrderMetadata(
            order_uid="0x1234",
            owner="0xabcd",
            creation_time=time.time(),
        )
        metadata.update_status(OrderStatus.SUBMITTED)
        metadata.update_status(OrderStatus.FILLED)
        store.add_order(metadata)

        # Add API metrics
        store.add_api_metric(
            APIMetrics(
                endpoint="/api/v1/orders",
                method="POST",
                timestamp=time.time(),
                duration=0.150,
                status_code=201,
                payload_size=512,
            )
        )

        return store

    def test_order_metadata_to_dict(self):
        """Test converting order metadata to dict."""
        metadata = OrderMetadata(
            order_uid="0x1234",
            owner="0xabcd",
            creation_time=1000.0,
        )
        metadata.update_status(OrderStatus.FILLED, 1001.0)

        result = order_metadata_to_dict(metadata)

        assert result["order_uid"] == "0x1234"
        assert result["owner"] == "0xabcd"
        assert result["current_status"] == "filled"
        assert result["total_lifecycle_time"] == pytest.approx(1.0)

    def test_export_store_to_json(self, populated_store):
        """Test exporting store to JSON."""
        json_str = export_store_to_json(populated_store)
        data = json.loads(json_str)

        assert "orders" in data
        assert "api_metrics" in data
        assert "resource_metrics" in data
        assert "summary" in data
        assert len(data["orders"]) == 1

    def test_export_orders_to_csv(self, populated_store):
        """Test exporting orders to CSV."""
        csv_str = export_orders_to_csv(populated_store)

        lines = csv_str.strip().split("\n")
        assert len(lines) == 2  # header + 1 order
        assert "order_uid" in lines[0]
        assert "0x1234" in lines[1]

    def test_export_api_metrics_to_csv(self, populated_store):
        """Test exporting API metrics to CSV."""
        csv_str = export_api_metrics_to_csv(populated_store)

        lines = csv_str.strip().split("\n")
        assert len(lines) == 2  # header + 1 metric
        assert "endpoint" in lines[0]
        assert "/api/v1/orders" in lines[1]

    def test_save_metrics_to_file_json(self, populated_store, tmp_path):
        """Test saving metrics to JSON file."""
        output_path = tmp_path / "metrics.json"
        save_metrics_to_file(populated_store, output_path, format="json")

        assert output_path.exists()
        with open(output_path) as f:
            data = json.load(f)
        assert "orders" in data

    def test_save_metrics_to_file_csv_orders(self, populated_store, tmp_path):
        """Test saving orders to CSV file."""
        output_path = tmp_path / "orders.csv"
        save_metrics_to_file(populated_store, output_path, format="csv_orders")

        assert output_path.exists()
        content = output_path.read_text()
        assert "order_uid" in content

    def test_save_metrics_to_file_csv_api(self, populated_store, tmp_path):
        """Test saving API metrics to CSV file."""
        output_path = tmp_path / "api_metrics.csv"
        save_metrics_to_file(populated_store, output_path, format="csv_api")

        assert output_path.exists()
        content = output_path.read_text()
        assert "endpoint" in content

    def test_save_metrics_invalid_format(self, populated_store, tmp_path):
        """Test that invalid format raises ValueError."""
        output_path = tmp_path / "metrics.xyz"

        with pytest.raises(ValueError, match="Unsupported format"):
            save_metrics_to_file(populated_store, output_path, format="invalid")

    def test_save_metrics_creates_directories(self, populated_store, tmp_path):
        """Test that save creates parent directories."""
        output_path = tmp_path / "subdir" / "nested" / "metrics.json"
        save_metrics_to_file(populated_store, output_path, format="json")

        assert output_path.exists()

    def test_export_empty_store(self):
        """Test exporting an empty store."""
        store = MetricsStore()

        json_str = export_store_to_json(store)
        data = json.loads(json_str)

        assert data["orders"] == []
        assert data["api_metrics"] == {}
        assert data["resource_metrics"] == {}
        assert data["summary"]["orders"] == 0

    def test_export_json_not_pretty(self, populated_store):
        """Test exporting JSON without pretty printing."""
        json_str = export_store_to_json(populated_store, pretty=False)

        # Not pretty printed should be single line (no newlines after first)
        assert "\n" not in json_str.strip()
