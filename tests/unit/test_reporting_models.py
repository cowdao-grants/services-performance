"""Unit tests for reporting data models."""

from datetime import datetime

from cow_performance.reporting.models import (
    ExecutiveSummary,
    PerformanceReport,
    Recommendation,
    RecommendationCategory,
    RecommendationSeverity,
    ReportVerdict,
)


class TestReportVerdict:
    """Tests for ReportVerdict enum."""

    def test_verdict_values(self):
        """Test verdict enum values."""
        assert ReportVerdict.SUCCESS.value == "success"
        assert ReportVerdict.WARNING.value == "warning"
        assert ReportVerdict.FAILURE.value == "failure"


class TestRecommendationSeverity:
    """Tests for RecommendationSeverity enum."""

    def test_severity_values(self):
        """Test severity enum values."""
        assert RecommendationSeverity.CRITICAL.value == "critical"
        assert RecommendationSeverity.WARNING.value == "warning"
        assert RecommendationSeverity.INFO.value == "info"


class TestRecommendationCategory:
    """Tests for RecommendationCategory enum."""

    def test_category_values(self):
        """Test category enum values."""
        assert RecommendationCategory.LATENCY.value == "latency"
        assert RecommendationCategory.THROUGHPUT.value == "throughput"
        assert RecommendationCategory.RELIABILITY.value == "reliability"
        assert RecommendationCategory.RESOURCE.value == "resource"
        assert RecommendationCategory.REGRESSION.value == "regression"


class TestRecommendation:
    """Tests for Recommendation dataclass."""

    def test_recommendation_creation(self):
        """Test creating a recommendation."""
        rec = Recommendation(
            severity=RecommendationSeverity.WARNING,
            category=RecommendationCategory.LATENCY,
            title="High latency detected",
            description="P95 latency exceeds threshold",
            action="Investigate API performance",
        )

        assert rec.severity == RecommendationSeverity.WARNING
        assert rec.category == RecommendationCategory.LATENCY
        assert rec.title == "High latency detected"
        assert rec.description == "P95 latency exceeds threshold"
        assert rec.action == "Investigate API performance"
        assert rec.metric_name is None
        assert rec.metric_value is None
        assert rec.threshold is None

    def test_recommendation_with_optional_fields(self):
        """Test recommendation with all optional fields."""
        rec = Recommendation(
            severity=RecommendationSeverity.CRITICAL,
            category=RecommendationCategory.RELIABILITY,
            title="Critical error rate",
            description="Error rate exceeds 20%",
            action="Review error logs",
            metric_name="error_rate",
            metric_value=0.25,
            threshold=0.05,
        )

        assert rec.metric_name == "error_rate"
        assert rec.metric_value == 0.25
        assert rec.threshold == 0.05


class TestExecutiveSummary:
    """Tests for ExecutiveSummary dataclass."""

    def test_summary_creation(self):
        """Test creating an executive summary."""
        now = datetime.now()
        summary = ExecutiveSummary(
            test_name="test-run",
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

        assert summary.test_name == "test-run"
        assert summary.total_orders_submitted == 100
        assert summary.success_rate == 0.95
        assert summary.verdict == ReportVerdict.SUCCESS

    def test_summary_with_key_findings(self):
        """Test summary with key findings."""
        now = datetime.now()
        summary = ExecutiveSummary(
            test_name="test",
            test_duration_seconds=60.0,
            test_start_time=now,
            test_end_time=now,
            total_orders_submitted=50,
            total_orders_filled=45,
            total_orders_failed=5,
            success_rate=0.90,
            average_throughput=0.75,
            peak_throughput=1.5,
            submission_latency_p95_ms=50.0,
            fill_latency_p95_ms=1000.0,
            total_lifecycle_p95_ms=1500.0,
            total_api_requests=200,
            api_success_rate=0.98,
            api_response_time_p95_ms=80.0,
            verdict=ReportVerdict.WARNING,
            verdict_reason="Success rate below 95%",
            key_findings=[
                "5 orders failed during test",
                "Success rate is 90%",
            ],
        )

        assert len(summary.key_findings) == 2
        assert "5 orders failed" in summary.key_findings[0]


class TestPerformanceReport:
    """Tests for PerformanceReport dataclass."""

    def test_report_creation(self):
        """Test creating a basic report."""
        report = PerformanceReport(report_id="test-123")

        assert report.report_id == "test-123"
        assert report.report_version == "1.0"
        assert report.summary is None
        assert report.baseline is None
        assert report.comparison is None
        assert report.recommendations == []

    def test_has_critical_issues_empty(self):
        """Test critical issue detection with no recommendations."""
        report = PerformanceReport(report_id="test")
        assert not report.has_critical_issues()

    def test_has_critical_issues_with_warning(self):
        """Test critical issue detection with only warnings."""
        report = PerformanceReport(report_id="test")
        report.recommendations.append(
            Recommendation(
                severity=RecommendationSeverity.WARNING,
                category=RecommendationCategory.LATENCY,
                title="Warning",
                description="Test",
                action="Test",
            )
        )
        assert not report.has_critical_issues()

    def test_has_critical_issues_with_critical(self):
        """Test critical issue detection with critical recommendation."""
        report = PerformanceReport(report_id="test")
        report.recommendations.append(
            Recommendation(
                severity=RecommendationSeverity.CRITICAL,
                category=RecommendationCategory.RELIABILITY,
                title="Critical",
                description="Test",
                action="Test",
            )
        )
        assert report.has_critical_issues()

    def test_get_recommendations_by_severity(self):
        """Test filtering recommendations by severity."""
        report = PerformanceReport(report_id="test")
        report.recommendations = [
            Recommendation(
                severity=RecommendationSeverity.CRITICAL,
                category=RecommendationCategory.RELIABILITY,
                title="Critical 1",
                description="",
                action="",
            ),
            Recommendation(
                severity=RecommendationSeverity.WARNING,
                category=RecommendationCategory.LATENCY,
                title="Warning 1",
                description="",
                action="",
            ),
            Recommendation(
                severity=RecommendationSeverity.CRITICAL,
                category=RecommendationCategory.THROUGHPUT,
                title="Critical 2",
                description="",
                action="",
            ),
        ]

        critical = report.get_recommendations_by_severity(RecommendationSeverity.CRITICAL)
        assert len(critical) == 2
        assert critical[0].title == "Critical 1"
        assert critical[1].title == "Critical 2"

        warnings = report.get_recommendations_by_severity(RecommendationSeverity.WARNING)
        assert len(warnings) == 1
        assert warnings[0].title == "Warning 1"

        info = report.get_recommendations_by_severity(RecommendationSeverity.INFO)
        assert len(info) == 0

    def test_get_recommendations_by_category(self):
        """Test filtering recommendations by category."""
        report = PerformanceReport(report_id="test")
        report.recommendations = [
            Recommendation(
                severity=RecommendationSeverity.WARNING,
                category=RecommendationCategory.LATENCY,
                title="Latency 1",
                description="",
                action="",
            ),
            Recommendation(
                severity=RecommendationSeverity.WARNING,
                category=RecommendationCategory.LATENCY,
                title="Latency 2",
                description="",
                action="",
            ),
            Recommendation(
                severity=RecommendationSeverity.WARNING,
                category=RecommendationCategory.RELIABILITY,
                title="Reliability 1",
                description="",
                action="",
            ),
        ]

        latency = report.get_recommendations_by_category(RecommendationCategory.LATENCY)
        assert len(latency) == 2

        reliability = report.get_recommendations_by_category(RecommendationCategory.RELIABILITY)
        assert len(reliability) == 1

        throughput = report.get_recommendations_by_category(RecommendationCategory.THROUGHPUT)
        assert len(throughput) == 0

    def test_report_with_metadata(self):
        """Test report with full metadata."""
        report = PerformanceReport(
            report_id="test-456",
            test_name="integration-test",
            scenario_name="high-load",
            git_commit="abc123",
            git_branch="main",
        )

        assert report.test_name == "integration-test"
        assert report.scenario_name == "high-load"
        assert report.git_commit == "abc123"
        assert report.git_branch == "main"
