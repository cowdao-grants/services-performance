"""Unit tests for CSV export functionality."""

import csv
from datetime import datetime

import pytest

from cow_performance.baselines.models import PerformanceBaseline
from cow_performance.metrics.aggregator import (
    OrderAggregateMetrics,
    PercentileStats,
    ResourceAggregateMetrics,
)
from cow_performance.reporting.csv_export import CSVExporter
from cow_performance.reporting.models import (
    ExecutiveSummary,
    PerformanceReport,
    Recommendation,
    RecommendationCategory,
    RecommendationSeverity,
    ReportVerdict,
)


@pytest.fixture
def sample_report():
    """Create a sample report for testing."""
    now = datetime.now()

    summary = ExecutiveSummary(
        test_name="csv-test",
        test_duration_seconds=300.0,
        test_start_time=now,
        test_end_time=now,
        total_orders_submitted=100,
        total_orders_filled=95,
        total_orders_failed=5,
        success_rate=0.95,
        average_throughput=1.5,
        peak_throughput=3.0,
        submission_latency_p95_ms=100.0,
        fill_latency_p95_ms=2500.0,
        total_lifecycle_p95_ms=3000.0,
        total_api_requests=500,
        api_success_rate=0.99,
        api_response_time_p95_ms=120.0,
        verdict=ReportVerdict.SUCCESS,
        verdict_reason="All metrics within acceptable thresholds",
    )

    baseline = PerformanceBaseline(
        id="test-baseline",
        name="csv-test",
        created_at=now.timestamp(),
        duration_seconds=300,
        order_metrics=OrderAggregateMetrics(
            total_orders=100,
            orders_submitted=100,
            orders_filled=95,
            orders_failed=5,
            success_rate=0.95,
            time_to_submit=PercentileStats(
                count=100,
                min=0.01,
                max=0.2,
                mean=0.05,
                p50=0.04,
                p90=0.08,
                p95=0.1,
                p99=0.15,
                std_dev=0.02,
            ),
            time_to_accept=PercentileStats(
                count=98,
                min=0.1,
                max=0.8,
                mean=0.3,
                p50=0.25,
                p90=0.5,
                p95=0.6,
                p99=0.75,
                std_dev=0.1,
            ),
            time_to_fill=PercentileStats(
                count=95,
                min=1.0,
                max=5.0,
                mean=2.0,
                p50=1.8,
                p90=2.8,
                p95=3.5,
                p99=4.5,
                std_dev=0.8,
            ),
            total_lifecycle=PercentileStats(
                count=95,
                min=1.5,
                max=6.0,
                mean=2.5,
                p50=2.2,
                p90=3.5,
                p95=4.0,
                p99=5.5,
                std_dev=1.0,
            ),
        ),
        resource_metrics={
            "orderbook": ResourceAggregateMetrics(
                container_name="orderbook",
                sample_count=60,
                cpu_percent=PercentileStats(
                    count=60,
                    min=10.0,
                    max=60.0,
                    mean=30.0,
                    p50=28.0,
                    p90=45.0,
                    p95=50.0,
                    p99=58.0,
                    std_dev=10.0,
                ),
                memory_percent=PercentileStats(
                    count=60,
                    min=40.0,
                    max=70.0,
                    mean=55.0,
                    p50=53.0,
                    p90=62.0,
                    p95=65.0,
                    p99=68.0,
                    std_dev=8.0,
                ),
            ),
            "solver": ResourceAggregateMetrics(
                container_name="solver",
                sample_count=60,
                cpu_percent=PercentileStats(count=60, mean=20.0, p50=18.0, p95=35.0, max=40.0),
                memory_percent=PercentileStats(count=60, mean=35.0, p50=33.0, p95=45.0, max=50.0),
            ),
        },
    )

    recommendations = [
        Recommendation(
            severity=RecommendationSeverity.WARNING,
            category=RecommendationCategory.LATENCY,
            title="Elevated latency",
            description="Test description",
            action="Test action",
            metric_name="fill_latency_p95",
        ),
    ]

    return PerformanceReport(
        report_id="csv-test-report",
        summary=summary,
        baseline=baseline,
        recommendations=recommendations,
    )


class TestCSVExporter:
    """Tests for CSVExporter class."""

    @pytest.fixture
    def exporter(self):
        """Create an exporter."""
        return CSVExporter()

    def test_export_to_directory(self, exporter, sample_report, tmp_path):
        """Test exporting all CSV files to directory."""
        exported = exporter.export_to_directory(sample_report, tmp_path)

        # Check all expected files were created
        assert "summary" in exported
        assert "latencies" in exported
        assert "resources" in exported
        assert "recommendations" in exported

        # Verify files exist
        for file_type, path in exported.items():
            assert path.exists(), f"{file_type} file should exist"
            assert path.stat().st_size > 0, f"{file_type} file should not be empty"

    def test_export_creates_directory(self, exporter, sample_report, tmp_path):
        """Test that export creates directory if it doesn't exist."""
        output_dir = tmp_path / "nested" / "path"
        exported = exporter.export_to_directory(sample_report, output_dir)

        assert output_dir.exists()
        assert len(exported) > 0

    def test_summary_csv_content(self, exporter, sample_report, tmp_path):
        """Test summary CSV contains expected data."""
        exported = exporter.export_to_directory(sample_report, tmp_path)

        with open(exported["summary"]) as f:
            reader = csv.reader(f)
            rows = list(reader)

        # Should have header + data rows
        assert len(rows) > 1

        # Convert to dict for easier checking
        data = {row[0]: row[1] for row in rows[1:]}

        assert data["test_name"] == "csv-test"
        assert data["total_orders_submitted"] == "100"
        assert data["success_rate"] == "0.95"
        assert data["verdict"] == "success"

    def test_latencies_csv_content(self, exporter, sample_report, tmp_path):
        """Test latencies CSV contains expected data."""
        exported = exporter.export_to_directory(sample_report, tmp_path)

        with open(exported["latencies"]) as f:
            reader = csv.reader(f)
            rows = list(reader)

        # Header + 4 latency stages
        assert len(rows) >= 5

        # Check header
        header = rows[0]
        assert "stage" in header
        assert "p95" in header
        assert "count" in header

        # Check data row (time_to_submit)
        submit_row = rows[1]
        assert submit_row[0] == "time_to_submit"

    def test_resources_csv_content(self, exporter, sample_report, tmp_path):
        """Test resources CSV contains expected data."""
        exported = exporter.export_to_directory(sample_report, tmp_path)

        with open(exported["resources"]) as f:
            reader = csv.reader(f)
            rows = list(reader)

        # Header + 2 containers
        assert len(rows) >= 3

        # Check header
        header = rows[0]
        assert "container" in header
        assert "cpu_p95" in header
        assert "memory_p95" in header

        # Check container names
        container_names = [row[0] for row in rows[1:]]
        assert "orderbook" in container_names
        assert "solver" in container_names

    def test_recommendations_csv_content(self, exporter, sample_report, tmp_path):
        """Test recommendations CSV contains expected data."""
        exported = exporter.export_to_directory(sample_report, tmp_path)

        with open(exported["recommendations"]) as f:
            reader = csv.reader(f)
            rows = list(reader)

        # Header + 1 recommendation
        assert len(rows) >= 2

        # Check header
        header = rows[0]
        assert "severity" in header
        assert "category" in header
        assert "title" in header
        assert "action" in header

        # Check data
        rec_row = rows[1]
        assert "warning" in rec_row
        assert "latency" in rec_row

    def test_export_summary_to_string(self, exporter, sample_report):
        """Test exporting summary to string."""
        output = exporter.export_summary_to_string(sample_report)

        assert "test_name,csv-test" in output
        assert "success_rate,0.95" in output
        assert "verdict,success" in output

    def test_export_empty_report(self, exporter, tmp_path):
        """Test exporting a report with no data."""
        report = PerformanceReport(report_id="empty")
        exported = exporter.export_to_directory(report, tmp_path)

        # No files should be created
        assert len(exported) == 0

    def test_export_partial_report(self, exporter, tmp_path):
        """Test exporting a report with only some data."""
        now = datetime.now()
        summary = ExecutiveSummary(
            test_name="partial",
            test_duration_seconds=60.0,
            test_start_time=now,
            test_end_time=now,
            total_orders_submitted=10,
            total_orders_filled=10,
            total_orders_failed=0,
            success_rate=1.0,
            average_throughput=1.0,
            peak_throughput=2.0,
            submission_latency_p95_ms=50.0,
            fill_latency_p95_ms=1000.0,
            total_lifecycle_p95_ms=1500.0,
            total_api_requests=50,
            api_success_rate=1.0,
            api_response_time_p95_ms=80.0,
            verdict=ReportVerdict.SUCCESS,
            verdict_reason="OK",
        )

        report = PerformanceReport(report_id="partial", summary=summary)
        exported = exporter.export_to_directory(report, tmp_path)

        # Only summary should be exported
        assert "summary" in exported
        assert "latencies" not in exported
        assert "resources" not in exported

    def test_latency_values_in_milliseconds(self, exporter, sample_report, tmp_path):
        """Test that latency values are exported in milliseconds."""
        exported = exporter.export_to_directory(sample_report, tmp_path)

        with open(exported["latencies"]) as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        # time_to_submit p95 is 0.1 seconds = 100ms
        submit_row = next(r for r in rows if r["stage"] == "time_to_submit")
        assert float(submit_row["p95"]) == 100.0  # 0.1 * 1000

    def test_csv_quoting(self, exporter, tmp_path):
        """Test that values with commas are properly quoted."""
        now = datetime.now()
        summary = ExecutiveSummary(
            test_name="test,with,commas",
            test_duration_seconds=60.0,
            test_start_time=now,
            test_end_time=now,
            total_orders_submitted=10,
            total_orders_filled=10,
            total_orders_failed=0,
            success_rate=1.0,
            average_throughput=1.0,
            peak_throughput=2.0,
            submission_latency_p95_ms=50.0,
            fill_latency_p95_ms=1000.0,
            total_lifecycle_p95_ms=1500.0,
            total_api_requests=50,
            api_success_rate=1.0,
            api_response_time_p95_ms=80.0,
            verdict=ReportVerdict.SUCCESS,
            verdict_reason="OK",
        )

        report = PerformanceReport(report_id="test", summary=summary)
        exported = exporter.export_to_directory(report, tmp_path)

        # Should be able to read it back correctly
        with open(exported["summary"]) as f:
            reader = csv.reader(f)
            rows = list(reader)

        data = {row[0]: row[1] for row in rows[1:]}
        assert data["test_name"] == "test,with,commas"
