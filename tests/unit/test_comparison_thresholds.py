"""Unit tests for threshold configuration."""


from cow_performance.comparison.models import MetricType, RegressionSeverity
from cow_performance.comparison.thresholds import (
    RELAXED_THRESHOLDS,
    STRICT_THRESHOLDS,
    MetricThresholds,
    RegressionThresholds,
)


class TestMetricThresholds:
    """Tests for MetricThresholds."""

    def test_classify_latency_increase(self) -> None:
        """Test latency increase classification."""
        thresholds = MetricThresholds(minor=0.10, major=0.15, critical=0.30)

        assert thresholds.classify_severity(0.05, MetricType.LATENCY) == RegressionSeverity.NONE
        assert thresholds.classify_severity(0.10, MetricType.LATENCY) == RegressionSeverity.MINOR
        assert thresholds.classify_severity(0.15, MetricType.LATENCY) == RegressionSeverity.MAJOR
        assert thresholds.classify_severity(0.30, MetricType.LATENCY) == RegressionSeverity.CRITICAL

    def test_classify_latency_decrease_no_regression(self) -> None:
        """Test latency decrease is not a regression."""
        thresholds = MetricThresholds(minor=0.10, major=0.15, critical=0.30)

        # Negative change (decrease) should not trigger regression
        assert thresholds.classify_severity(-0.20, MetricType.LATENCY) == RegressionSeverity.NONE

    def test_classify_throughput_decrease(self) -> None:
        """Test throughput decrease classification (inverted)."""
        thresholds = MetricThresholds(minor=0.10, major=0.25, critical=0.50)

        # Negative change = decrease, which is bad for throughput
        assert thresholds.classify_severity(-0.05, MetricType.THROUGHPUT) == RegressionSeverity.NONE
        assert (
            thresholds.classify_severity(-0.10, MetricType.THROUGHPUT) == RegressionSeverity.MINOR
        )
        assert (
            thresholds.classify_severity(-0.25, MetricType.THROUGHPUT) == RegressionSeverity.MAJOR
        )
        assert (
            thresholds.classify_severity(-0.50, MetricType.THROUGHPUT)
            == RegressionSeverity.CRITICAL
        )

    def test_classify_throughput_increase_no_regression(self) -> None:
        """Test throughput increase is not a regression."""
        thresholds = MetricThresholds(minor=0.10, major=0.25, critical=0.50)

        # Positive change (increase) should not trigger regression for throughput
        assert thresholds.classify_severity(0.50, MetricType.THROUGHPUT) == RegressionSeverity.NONE

    def test_classify_resource_increase(self) -> None:
        """Test resource usage increase classification."""
        thresholds = MetricThresholds(minor=0.10, major=0.20, critical=0.50)

        assert thresholds.classify_severity(0.05, MetricType.RESOURCE) == RegressionSeverity.NONE
        assert thresholds.classify_severity(0.15, MetricType.RESOURCE) == RegressionSeverity.MINOR
        assert thresholds.classify_severity(0.25, MetricType.RESOURCE) == RegressionSeverity.MAJOR
        assert (
            thresholds.classify_severity(0.60, MetricType.RESOURCE) == RegressionSeverity.CRITICAL
        )

    def test_classify_error_rate_increase(self) -> None:
        """Test error rate increase classification."""
        thresholds = MetricThresholds(minor=0.01, major=0.02, critical=0.05)

        assert thresholds.classify_severity(0.005, MetricType.ERROR_RATE) == RegressionSeverity.NONE
        assert (
            thresholds.classify_severity(0.015, MetricType.ERROR_RATE) == RegressionSeverity.MINOR
        )
        assert (
            thresholds.classify_severity(0.025, MetricType.ERROR_RATE) == RegressionSeverity.MAJOR
        )
        assert (
            thresholds.classify_severity(0.06, MetricType.ERROR_RATE) == RegressionSeverity.CRITICAL
        )


class TestRegressionThresholds:
    """Tests for RegressionThresholds."""

    def test_default_thresholds(self) -> None:
        """Test default threshold values."""
        thresholds = RegressionThresholds()

        assert thresholds.latency.minor == 0.10
        assert thresholds.latency.major == 0.15
        assert thresholds.latency.critical == 0.30

        assert thresholds.throughput.minor == 0.10
        assert thresholds.throughput.major == 0.25
        assert thresholds.throughput.critical == 0.50

        assert thresholds.significance_level == 0.05
        assert thresholds.min_effect_size == 0.2

    def test_get_thresholds_for_type(self) -> None:
        """Test getting thresholds for specific metric types."""
        thresholds = RegressionThresholds()

        latency_t = thresholds.get_thresholds_for_type(MetricType.LATENCY)
        assert latency_t == thresholds.latency

        throughput_t = thresholds.get_thresholds_for_type(MetricType.THROUGHPUT)
        assert throughput_t == thresholds.throughput

    def test_classify_severity(self) -> None:
        """Test severity classification through RegressionThresholds."""
        thresholds = RegressionThresholds()

        # Latency increase
        severity = thresholds.classify_severity(0.20, MetricType.LATENCY)
        assert severity == RegressionSeverity.MAJOR

        # Throughput decrease
        severity = thresholds.classify_severity(-0.30, MetricType.THROUGHPUT)
        assert severity == RegressionSeverity.MAJOR

    def test_strict_thresholds(self) -> None:
        """Test strict threshold profile."""
        assert STRICT_THRESHOLDS.latency.minor == 0.05
        assert STRICT_THRESHOLDS.latency.critical == 0.20
        assert STRICT_THRESHOLDS.significance_level == 0.01

    def test_relaxed_thresholds(self) -> None:
        """Test relaxed threshold profile."""
        assert RELAXED_THRESHOLDS.latency.minor == 0.20
        assert RELAXED_THRESHOLDS.latency.critical == 0.50
        assert RELAXED_THRESHOLDS.significance_level == 0.10

    def test_serialization_roundtrip(self) -> None:
        """Test thresholds can be serialized and deserialized."""
        thresholds = RegressionThresholds()
        data = thresholds.to_dict()
        restored = RegressionThresholds.from_dict(data)

        assert restored.latency.minor == thresholds.latency.minor
        assert restored.latency.major == thresholds.latency.major
        assert restored.latency.critical == thresholds.latency.critical
        assert restored.throughput.minor == thresholds.throughput.minor
        assert restored.significance_level == thresholds.significance_level
        assert restored.min_effect_size == thresholds.min_effect_size

    def test_serialization_custom_thresholds(self) -> None:
        """Test serialization with custom thresholds."""
        thresholds = RegressionThresholds(
            latency=MetricThresholds(minor=0.05, major=0.10, critical=0.20),
            significance_level=0.01,
        )

        data = thresholds.to_dict()
        restored = RegressionThresholds.from_dict(data)

        assert restored.latency.minor == 0.05
        assert restored.significance_level == 0.01

    def test_from_dict_with_partial_data(self) -> None:
        """Test deserialization with partial data uses defaults."""
        data = {
            "significance_level": 0.01,
        }

        restored = RegressionThresholds.from_dict(data)

        assert restored.significance_level == 0.01
        # Latency should use defaults from MetricThresholds
        assert restored.latency.minor == 0.10
