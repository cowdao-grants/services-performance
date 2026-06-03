"""Statistical functions for performance comparison."""

import math
from dataclasses import dataclass

from scipy import stats


@dataclass
class StatisticalResult:
    """Result of statistical comparison."""

    p_value: float | None
    effect_size: float | None  # Cohen's d
    is_significant: bool
    test_used: str  # Name of the statistical test used


def calculate_percent_change(
    baseline_value: float,
    current_value: float,
) -> float:
    """
    Calculate percentage change between baseline and current.

    Args:
        baseline_value: The baseline (reference) value
        current_value: The current (test) value

    Returns:
        Percentage change as a decimal (0.10 = 10% increase)
        Positive = increase, negative = decrease
    """
    if baseline_value == 0:
        if current_value == 0:
            return 0.0
        # Infinite change from zero - return large value
        return float("inf") if current_value > 0 else float("-inf")

    return (current_value - baseline_value) / abs(baseline_value)


def calculate_cohens_d(
    baseline_mean: float,
    current_mean: float,
    baseline_std: float,
    current_std: float,
    baseline_n: int,
    current_n: int,
) -> float | None:
    """
    Calculate Cohen's d effect size.

    Uses pooled standard deviation for two independent samples.

    Args:
        baseline_mean: Mean of baseline sample
        current_mean: Mean of current sample
        baseline_std: Standard deviation of baseline
        current_std: Standard deviation of current
        baseline_n: Sample size of baseline
        current_n: Sample size of current

    Returns:
        Cohen's d value, or None if calculation not possible
    """
    if baseline_n < 2 or current_n < 2:
        return None

    # Calculate pooled standard deviation
    pooled_variance = (
        (baseline_n - 1) * baseline_std**2 + (current_n - 1) * current_std**2
    ) / (baseline_n + current_n - 2)

    if pooled_variance <= 0:
        return None

    pooled_std = math.sqrt(pooled_variance)

    if pooled_std == 0:
        return None

    return (current_mean - baseline_mean) / pooled_std


def welchs_t_test(
    baseline_mean: float,
    current_mean: float,
    baseline_std: float,
    current_std: float,
    baseline_n: int,
    current_n: int,
) -> tuple[float, float] | None:
    """
    Perform Welch's t-test for unequal variances.

    Args:
        baseline_mean: Mean of baseline sample
        current_mean: Mean of current sample
        baseline_std: Standard deviation of baseline
        current_std: Standard deviation of current
        baseline_n: Sample size of baseline
        current_n: Sample size of current

    Returns:
        Tuple of (t-statistic, p-value) or None if not calculable
    """
    if baseline_n < 2 or current_n < 2:
        return None

    if baseline_std == 0 and current_std == 0:
        # No variance in either sample
        if baseline_mean == current_mean:
            return (0.0, 1.0)  # No difference
        return None

    # Calculate standard error
    se_baseline = baseline_std**2 / baseline_n
    se_current = current_std**2 / current_n
    se_diff = math.sqrt(se_baseline + se_current)

    if se_diff == 0:
        return None

    # Calculate t-statistic
    t_stat = (current_mean - baseline_mean) / se_diff

    # Calculate degrees of freedom (Welch-Satterthwaite)
    numerator = (se_baseline + se_current) ** 2
    denominator = (se_baseline**2 / (baseline_n - 1)) + (se_current**2 / (current_n - 1))

    if denominator == 0:
        return None

    df = numerator / denominator

    # Calculate two-tailed p-value
    p_value = 2 * stats.t.sf(abs(t_stat), df)

    return (t_stat, p_value)


def compare_percentile_stats(
    baseline_mean: float,
    baseline_std: float,
    baseline_count: int,
    current_mean: float,
    current_std: float,
    current_count: int,
    significance_level: float = 0.05,
) -> StatisticalResult:
    """
    Compare two samples using statistical tests.

    Uses Welch's t-test (robust to unequal variances).
    Falls back to simple comparison if sample sizes are too small.

    Args:
        baseline_mean: Mean of baseline
        baseline_std: Std dev of baseline
        baseline_count: Sample size of baseline
        current_mean: Mean of current
        current_std: Std dev of current
        current_count: Sample size of current
        significance_level: P-value threshold for significance

    Returns:
        StatisticalResult with p-value, effect size, and significance
    """
    # Calculate effect size
    effect_size = calculate_cohens_d(
        baseline_mean,
        current_mean,
        baseline_std,
        current_std,
        baseline_count,
        current_count,
    )

    # Try t-test
    t_test_result = welchs_t_test(
        baseline_mean,
        current_mean,
        baseline_std,
        current_std,
        baseline_count,
        current_count,
    )

    if t_test_result is not None:
        _, p_value = t_test_result
        return StatisticalResult(
            p_value=float(p_value),
            effect_size=effect_size,
            is_significant=bool(p_value < significance_level),
            test_used="Welch's t-test",
        )

    # Fallback: no statistical test possible
    # Consider significant if there's a meaningful effect size
    is_significant = effect_size is not None and abs(effect_size) >= 0.5

    return StatisticalResult(
        p_value=None,
        effect_size=effect_size,
        is_significant=is_significant,
        test_used="effect_size_only",
    )


def interpret_effect_size(cohens_d: float | None) -> str:
    """
    Interpret Cohen's d effect size.

    Args:
        cohens_d: Cohen's d value

    Returns:
        Human-readable interpretation
    """
    if cohens_d is None:
        return "unknown"

    d = abs(cohens_d)
    if d < 0.2:
        return "negligible"
    elif d < 0.5:
        return "small"
    elif d < 0.8:
        return "medium"
    else:
        return "large"


def format_percent_change(percent_change: float) -> str:
    """
    Format percentage change for display.

    Args:
        percent_change: Decimal percentage (0.10 = 10%)

    Returns:
        Formatted string like "+10.0%" or "-5.2%"
    """
    if math.isinf(percent_change):
        return "inf%" if percent_change > 0 else "-inf%"

    sign = "+" if percent_change >= 0 else ""
    return f"{sign}{percent_change * 100:.1f}%"
