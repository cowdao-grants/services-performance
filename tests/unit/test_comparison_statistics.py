"""Unit tests for statistical functions."""

import math

import pytest

from cow_performance.comparison.statistics import (
    calculate_cohens_d,
    calculate_percent_change,
    compare_percentile_stats,
    format_percent_change,
    interpret_effect_size,
    welchs_t_test,
)


class TestPercentChange:
    """Tests for percent change calculation."""

    def test_positive_change(self) -> None:
        """Test positive percent change."""
        assert calculate_percent_change(100, 110) == pytest.approx(0.10)

    def test_negative_change(self) -> None:
        """Test negative percent change."""
        assert calculate_percent_change(100, 90) == pytest.approx(-0.10)

    def test_double_value(self) -> None:
        """Test doubling the value."""
        assert calculate_percent_change(50, 100) == pytest.approx(1.0)

    def test_half_value(self) -> None:
        """Test halving the value."""
        assert calculate_percent_change(100, 50) == pytest.approx(-0.50)

    def test_zero_baseline_positive_current(self) -> None:
        """Test with zero baseline and positive current."""
        result = calculate_percent_change(0, 10)
        assert math.isinf(result)
        assert result > 0

    def test_zero_baseline_negative_current(self) -> None:
        """Test with zero baseline and negative current."""
        result = calculate_percent_change(0, -10)
        assert math.isinf(result)
        assert result < 0

    def test_both_zero(self) -> None:
        """Test with both zero."""
        assert calculate_percent_change(0, 0) == 0.0

    def test_no_change(self) -> None:
        """Test with no change."""
        assert calculate_percent_change(100, 100) == pytest.approx(0.0)

    def test_small_change(self) -> None:
        """Test small percentage change."""
        assert calculate_percent_change(100, 101) == pytest.approx(0.01)


class TestCohensD:
    """Tests for Cohen's d effect size."""

    def test_large_effect(self) -> None:
        """Test detection of large effect size."""
        # Large difference: 100 vs 200 with std of 50
        d = calculate_cohens_d(100, 200, 50, 50, 30, 30)
        assert d is not None
        assert abs(d) > 0.8  # Large effect

    def test_medium_effect(self) -> None:
        """Test detection of medium effect size."""
        # Medium difference
        d = calculate_cohens_d(100, 130, 50, 50, 30, 30)
        assert d is not None
        assert 0.5 <= abs(d) < 0.8

    def test_small_effect(self) -> None:
        """Test detection of small effect size."""
        # Small difference
        d = calculate_cohens_d(100, 110, 50, 50, 30, 30)
        assert d is not None
        assert 0.2 <= abs(d) < 0.5

    def test_small_sample_returns_none(self) -> None:
        """Test that small samples return None."""
        d = calculate_cohens_d(100, 200, 50, 50, 1, 1)
        assert d is None

    def test_zero_variance(self) -> None:
        """Test with zero variance."""
        d = calculate_cohens_d(100, 100, 0, 0, 30, 30)
        assert d is None

    def test_unequal_sample_sizes(self) -> None:
        """Test with unequal sample sizes."""
        d = calculate_cohens_d(100, 200, 50, 50, 20, 40)
        assert d is not None
        assert abs(d) > 0.8

    def test_positive_direction(self) -> None:
        """Test positive direction (current > baseline)."""
        d = calculate_cohens_d(100, 200, 50, 50, 30, 30)
        assert d is not None
        assert d > 0

    def test_negative_direction(self) -> None:
        """Test negative direction (current < baseline)."""
        d = calculate_cohens_d(200, 100, 50, 50, 30, 30)
        assert d is not None
        assert d < 0


class TestWelchsTTest:
    """Tests for Welch's t-test."""

    def test_significant_difference(self) -> None:
        """Test detection of significant difference."""
        result = welchs_t_test(100, 150, 20, 20, 30, 30)
        assert result is not None
        t_stat, p_value = result
        assert p_value < 0.05  # Should be significant

    def test_no_difference(self) -> None:
        """Test no difference returns high p-value."""
        result = welchs_t_test(100, 100, 20, 20, 30, 30)
        assert result is not None
        t_stat, p_value = result
        assert p_value > 0.05

    def test_small_sample_returns_none(self) -> None:
        """Test that very small samples return None."""
        result = welchs_t_test(100, 150, 20, 20, 1, 1)
        assert result is None

    def test_zero_variance_same_mean(self) -> None:
        """Test zero variance with same mean."""
        result = welchs_t_test(100, 100, 0, 0, 30, 30)
        assert result is not None
        t_stat, p_value = result
        assert t_stat == 0.0
        assert p_value == 1.0

    def test_zero_variance_different_mean(self) -> None:
        """Test zero variance with different mean."""
        result = welchs_t_test(100, 150, 0, 0, 30, 30)
        assert result is None

    def test_unequal_variances(self) -> None:
        """Test with unequal variances."""
        result = welchs_t_test(100, 150, 10, 30, 30, 30)
        assert result is not None
        t_stat, p_value = result
        assert p_value < 0.05


class TestComparePercentileStats:
    """Tests for compare_percentile_stats function."""

    def test_significant_difference(self) -> None:
        """Test detection of significant difference."""
        result = compare_percentile_stats(
            baseline_mean=100,
            baseline_std=20,
            baseline_count=30,
            current_mean=150,
            current_std=20,
            current_count=30,
            significance_level=0.05,
        )

        assert result.is_significant is True
        assert result.p_value is not None
        assert result.p_value < 0.05
        assert result.test_used == "Welch's t-test"

    def test_not_significant(self) -> None:
        """Test non-significant difference."""
        result = compare_percentile_stats(
            baseline_mean=100,
            baseline_std=20,
            baseline_count=30,
            current_mean=102,
            current_std=20,
            current_count=30,
            significance_level=0.05,
        )

        assert result.is_significant is False
        assert result.p_value is not None
        assert result.p_value > 0.05

    def test_effect_size_calculated(self) -> None:
        """Test that effect size is calculated."""
        result = compare_percentile_stats(
            baseline_mean=100,
            baseline_std=20,
            baseline_count=30,
            current_mean=150,
            current_std=20,
            current_count=30,
        )

        assert result.effect_size is not None
        assert abs(result.effect_size) > 0.8  # Large effect

    def test_small_sample_fallback(self) -> None:
        """Test fallback for small samples."""
        result = compare_percentile_stats(
            baseline_mean=100,
            baseline_std=20,
            baseline_count=1,
            current_mean=150,
            current_std=20,
            current_count=1,
        )

        # Should fall back to effect_size_only
        assert result.p_value is None
        assert result.test_used == "effect_size_only"


class TestInterpretEffectSize:
    """Tests for interpret_effect_size function."""

    def test_negligible(self) -> None:
        """Test negligible effect size."""
        assert interpret_effect_size(0.1) == "negligible"
        assert interpret_effect_size(-0.1) == "negligible"

    def test_small(self) -> None:
        """Test small effect size."""
        assert interpret_effect_size(0.3) == "small"
        assert interpret_effect_size(-0.3) == "small"

    def test_medium(self) -> None:
        """Test medium effect size."""
        assert interpret_effect_size(0.6) == "medium"
        assert interpret_effect_size(-0.6) == "medium"

    def test_large(self) -> None:
        """Test large effect size."""
        assert interpret_effect_size(1.0) == "large"
        assert interpret_effect_size(-1.0) == "large"

    def test_none(self) -> None:
        """Test None effect size."""
        assert interpret_effect_size(None) == "unknown"


class TestFormatPercentChange:
    """Tests for percent change formatting."""

    def test_positive(self) -> None:
        """Test positive change formatting."""
        assert format_percent_change(0.10) == "+10.0%"

    def test_negative(self) -> None:
        """Test negative change formatting."""
        assert format_percent_change(-0.05) == "-5.0%"

    def test_zero(self) -> None:
        """Test zero change formatting."""
        assert format_percent_change(0.0) == "+0.0%"

    def test_positive_infinity(self) -> None:
        """Test positive infinity formatting."""
        assert format_percent_change(float("inf")) == "inf%"

    def test_negative_infinity(self) -> None:
        """Test negative infinity formatting."""
        assert format_percent_change(float("-inf")) == "-inf%"

    def test_decimal_precision(self) -> None:
        """Test decimal precision."""
        assert format_percent_change(0.1234) == "+12.3%"
