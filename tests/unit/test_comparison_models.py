"""Unit tests for comparison data models."""


from cow_performance.comparison.models import (
    ComparisonResult,
    ComparisonVerdict,
    MetricComparison,
    MetricType,
    RegressionSeverity,
)


class TestMetricComparison:
    """Tests for MetricComparison dataclass."""

    def test_latency_increase_is_regression(self) -> None:
        """Latency increase should be marked as regression."""
        comparison = MetricComparison(
            metric_name="time_to_fill",
            metric_type=MetricType.LATENCY,
            baseline_value=0.1,
            current_value=0.15,
            absolute_diff=0.05,
            percent_change=0.50,
            is_significant=True,
            regression_severity=RegressionSeverity.CRITICAL,
        )
        assert comparison.is_regression is True
        assert comparison.is_improvement is False

    def test_latency_decrease_is_improvement(self) -> None:
        """Latency decrease should be marked as improvement."""
        comparison = MetricComparison(
            metric_name="time_to_fill",
            metric_type=MetricType.LATENCY,
            baseline_value=0.15,
            current_value=0.1,
            absolute_diff=-0.05,
            percent_change=-0.33,
            is_significant=True,
            regression_severity=RegressionSeverity.NONE,
        )
        assert comparison.is_regression is False
        assert comparison.is_improvement is True

    def test_throughput_decrease_is_regression(self) -> None:
        """Throughput decrease should be marked as regression."""
        comparison = MetricComparison(
            metric_name="orders_per_second",
            metric_type=MetricType.THROUGHPUT,
            baseline_value=10.0,
            current_value=5.0,
            absolute_diff=-5.0,
            percent_change=-0.50,
            is_significant=True,
            regression_severity=RegressionSeverity.CRITICAL,
        )
        assert comparison.is_regression is True
        assert comparison.is_improvement is False

    def test_throughput_increase_is_improvement(self) -> None:
        """Throughput increase should be marked as improvement."""
        comparison = MetricComparison(
            metric_name="orders_per_second",
            metric_type=MetricType.THROUGHPUT,
            baseline_value=5.0,
            current_value=10.0,
            absolute_diff=5.0,
            percent_change=1.0,
            is_significant=True,
            regression_severity=RegressionSeverity.NONE,
        )
        assert comparison.is_regression is False
        assert comparison.is_improvement is True

    def test_not_significant_not_regression(self) -> None:
        """Non-significant change should not be marked as regression."""
        comparison = MetricComparison(
            metric_name="time_to_fill",
            metric_type=MetricType.LATENCY,
            baseline_value=0.1,
            current_value=0.12,
            absolute_diff=0.02,
            percent_change=0.20,
            is_significant=False,
            regression_severity=RegressionSeverity.MINOR,
        )
        assert comparison.is_regression is False

    def test_not_significant_not_improvement(self) -> None:
        """Non-significant change should not be marked as improvement."""
        comparison = MetricComparison(
            metric_name="time_to_fill",
            metric_type=MetricType.LATENCY,
            baseline_value=0.12,
            current_value=0.1,
            absolute_diff=-0.02,
            percent_change=-0.167,
            is_significant=False,
            regression_severity=RegressionSeverity.NONE,
        )
        assert comparison.is_improvement is False

    def test_resource_increase_is_regression(self) -> None:
        """Resource usage increase should be marked as regression."""
        comparison = MetricComparison(
            metric_name="cpu_percent",
            metric_type=MetricType.RESOURCE,
            baseline_value=25.0,
            current_value=50.0,
            absolute_diff=25.0,
            percent_change=1.0,
            is_significant=True,
            regression_severity=RegressionSeverity.CRITICAL,
        )
        assert comparison.is_regression is True

    def test_error_rate_increase_is_regression(self) -> None:
        """Error rate increase should be marked as regression."""
        comparison = MetricComparison(
            metric_name="failure_rate",
            metric_type=MetricType.ERROR_RATE,
            baseline_value=0.01,
            current_value=0.05,
            absolute_diff=0.04,
            percent_change=4.0,
            is_significant=True,
            regression_severity=RegressionSeverity.CRITICAL,
        )
        assert comparison.is_regression is True


class TestComparisonResult:
    """Tests for ComparisonResult dataclass."""

    def test_add_comparison(self) -> None:
        """Test adding comparisons updates counts correctly."""
        result = ComparisonResult(
            baseline_id="baseline-1",
            baseline_name="baseline",
            current_id="current-1",
            current_name="current",
        )

        # Add a critical regression
        result.add_comparison(
            MetricComparison(
                metric_name="latency",
                metric_type=MetricType.LATENCY,
                baseline_value=0.1,
                current_value=0.2,
                absolute_diff=0.1,
                percent_change=1.0,
                is_significant=True,
                regression_severity=RegressionSeverity.CRITICAL,
            )
        )

        assert result.total_metrics_compared == 1
        assert result.significant_changes == 1
        assert result.critical_count == 1
        assert len(result.regressions) == 1

    def test_add_multiple_comparisons(self) -> None:
        """Test adding multiple comparisons."""
        result = ComparisonResult(
            baseline_id="b1",
            baseline_name="base",
            current_id="c1",
            current_name="curr",
        )

        # Add critical
        result.add_comparison(
            MetricComparison(
                metric_name="latency1",
                metric_type=MetricType.LATENCY,
                baseline_value=0.1,
                current_value=0.2,
                absolute_diff=0.1,
                percent_change=1.0,
                is_significant=True,
                regression_severity=RegressionSeverity.CRITICAL,
            )
        )

        # Add major
        result.add_comparison(
            MetricComparison(
                metric_name="latency2",
                metric_type=MetricType.LATENCY,
                baseline_value=0.1,
                current_value=0.15,
                absolute_diff=0.05,
                percent_change=0.5,
                is_significant=True,
                regression_severity=RegressionSeverity.MAJOR,
            )
        )

        # Add minor
        result.add_comparison(
            MetricComparison(
                metric_name="latency3",
                metric_type=MetricType.LATENCY,
                baseline_value=0.1,
                current_value=0.12,
                absolute_diff=0.02,
                percent_change=0.2,
                is_significant=True,
                regression_severity=RegressionSeverity.MINOR,
            )
        )

        assert result.total_metrics_compared == 3
        assert result.critical_count == 1
        assert result.major_count == 1
        assert result.minor_count == 1
        assert len(result.regressions) == 3

    def test_verdict_calculation_regression_with_critical(self) -> None:
        """Test verdict is regression when critical issues exist."""
        result = ComparisonResult(
            baseline_id="b1",
            baseline_name="base",
            current_id="c1",
            current_name="curr",
        )

        result.add_comparison(
            MetricComparison(
                metric_name="latency",
                metric_type=MetricType.LATENCY,
                baseline_value=0.1,
                current_value=0.2,
                absolute_diff=0.1,
                percent_change=1.0,
                is_significant=True,
                regression_severity=RegressionSeverity.CRITICAL,
            )
        )

        result.calculate_verdict()
        assert result.verdict == ComparisonVerdict.REGRESSION

    def test_verdict_calculation_regression_with_multiple_major(self) -> None:
        """Test verdict is regression with 2+ major regressions."""
        result = ComparisonResult(
            baseline_id="b1",
            baseline_name="base",
            current_id="c1",
            current_name="curr",
        )

        # Add two major regressions
        for i in range(2):
            result.add_comparison(
                MetricComparison(
                    metric_name=f"latency{i}",
                    metric_type=MetricType.LATENCY,
                    baseline_value=0.1,
                    current_value=0.15,
                    absolute_diff=0.05,
                    percent_change=0.5,
                    is_significant=True,
                    regression_severity=RegressionSeverity.MAJOR,
                )
            )

        result.calculate_verdict()
        assert result.verdict == ComparisonVerdict.REGRESSION

    def test_verdict_calculation_improvement(self) -> None:
        """Test verdict is improvement when more improvements than regressions."""
        result = ComparisonResult(
            baseline_id="b1",
            baseline_name="base",
            current_id="c1",
            current_name="curr",
        )

        # Add improvement
        comp = MetricComparison(
            metric_name="latency",
            metric_type=MetricType.LATENCY,
            baseline_value=0.2,
            current_value=0.1,
            absolute_diff=-0.1,
            percent_change=-0.5,
            is_significant=True,
            regression_severity=RegressionSeverity.NONE,
        )
        result.add_comparison(comp)

        result.calculate_verdict()
        assert result.verdict == ComparisonVerdict.IMPROVEMENT

    def test_verdict_calculation_neutral(self) -> None:
        """Test verdict is neutral when no significant changes."""
        result = ComparisonResult(
            baseline_id="b1",
            baseline_name="base",
            current_id="c1",
            current_name="curr",
        )

        # Add non-significant change
        result.add_comparison(
            MetricComparison(
                metric_name="latency",
                metric_type=MetricType.LATENCY,
                baseline_value=0.1,
                current_value=0.101,
                absolute_diff=0.001,
                percent_change=0.01,
                is_significant=False,
                regression_severity=RegressionSeverity.NONE,
            )
        )

        result.calculate_verdict()
        assert result.verdict == ComparisonVerdict.NEUTRAL

    def test_regressions_sorted_by_severity(self) -> None:
        """Test that regressions are sorted by severity after calculate_verdict."""
        result = ComparisonResult(
            baseline_id="b1",
            baseline_name="base",
            current_id="c1",
            current_name="curr",
        )

        # Add in reverse order
        result.add_comparison(
            MetricComparison(
                metric_name="minor",
                metric_type=MetricType.LATENCY,
                baseline_value=0.1,
                current_value=0.12,
                absolute_diff=0.02,
                percent_change=0.2,
                is_significant=True,
                regression_severity=RegressionSeverity.MINOR,
            )
        )
        result.add_comparison(
            MetricComparison(
                metric_name="critical",
                metric_type=MetricType.LATENCY,
                baseline_value=0.1,
                current_value=0.2,
                absolute_diff=0.1,
                percent_change=1.0,
                is_significant=True,
                regression_severity=RegressionSeverity.CRITICAL,
            )
        )

        result.calculate_verdict()

        # Critical should be first
        assert result.regressions[0].regression_severity == RegressionSeverity.CRITICAL
        assert result.regressions[1].regression_severity == RegressionSeverity.MINOR
