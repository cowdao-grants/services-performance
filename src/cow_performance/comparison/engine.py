"""Comparison engine for performance baselines."""

from __future__ import annotations

import logging
from datetime import datetime

from cow_performance.baselines.models import PerformanceBaseline
from cow_performance.comparison.models import (
    ComparisonResult,
    MetricComparison,
    MetricType,
)
from cow_performance.comparison.statistics import (
    calculate_percent_change,
    compare_percentile_stats,
    format_percent_change,
    interpret_effect_size,
)
from cow_performance.comparison.thresholds import RegressionThresholds
from cow_performance.metrics.aggregator import (
    APIAggregateMetrics,
    OrderAggregateMetrics,
    PercentileStats,
    ResourceAggregateMetrics,
)

logger = logging.getLogger(__name__)


class ComparisonEngine:
    """
    Engine for comparing performance baselines.

    Compares aggregated metrics between a baseline and current run,
    calculates statistical significance, and classifies regressions.

    Example:
        engine = ComparisonEngine()
        result = engine.compare(baseline, current)
        if result.verdict == ComparisonVerdict.REGRESSION:
            print(f"Found {result.critical_count} critical regressions")
    """

    def __init__(
        self,
        thresholds: RegressionThresholds | None = None,
    ):
        """
        Initialize the comparison engine.

        Args:
            thresholds: Optional threshold configuration.
                       Uses default thresholds if not specified.
        """
        self._thresholds = thresholds or RegressionThresholds()

    @property
    def thresholds(self) -> RegressionThresholds:
        """Get the current threshold configuration."""
        return self._thresholds

    def compare(
        self,
        baseline: PerformanceBaseline,
        current: PerformanceBaseline,
    ) -> ComparisonResult:
        """
        Compare two baselines and generate a comparison result.

        Args:
            baseline: The reference baseline
            current: The current run to compare

        Returns:
            ComparisonResult with detailed metric comparisons
        """
        result = ComparisonResult(
            baseline_id=baseline.id,
            baseline_name=baseline.name,
            current_id=current.id,
            current_name=current.name,
            compared_at=datetime.now(),
        )

        # Compare order metrics
        if baseline.order_metrics and current.order_metrics:
            self._compare_order_metrics(
                baseline.order_metrics,
                current.order_metrics,
                result,
            )

        # Compare API metrics
        if baseline.api_metrics and current.api_metrics:
            self._compare_api_metrics(
                baseline.api_metrics,
                current.api_metrics,
                result,
            )

        # Compare throughput metrics
        self._compare_throughput(baseline, current, result)

        # Compare resource metrics
        self._compare_resource_metrics(
            baseline.resource_metrics,
            current.resource_metrics,
            result,
        )

        # Calculate overall verdict
        result.calculate_verdict()

        logger.info(
            "Comparison complete: %s vs %s - verdict: %s, "
            "%d critical, %d major, %d minor regressions",
            baseline.name,
            current.name,
            result.verdict.value,
            result.critical_count,
            result.major_count,
            result.minor_count,
        )

        return result

    def _compare_percentile_stats(
        self,
        metric_name: str,
        metric_type: MetricType,
        baseline_stats: PercentileStats,
        current_stats: PercentileStats,
    ) -> MetricComparison:
        """
        Compare two PercentileStats objects.

        Args:
            metric_name: Name for this metric
            metric_type: Type of metric (latency, throughput, etc.)
            baseline_stats: Baseline statistics
            current_stats: Current statistics

        Returns:
            MetricComparison for this metric
        """
        # Calculate percent change using p95 (more robust than mean for latency)
        baseline_value = baseline_stats.p95
        current_value = current_stats.p95
        percent_change = calculate_percent_change(baseline_value, current_value)

        # Statistical comparison using mean and std
        stat_result = compare_percentile_stats(
            baseline_mean=baseline_stats.mean,
            baseline_std=baseline_stats.std_dev,
            baseline_count=baseline_stats.count,
            current_mean=current_stats.mean,
            current_std=current_stats.std_dev,
            current_count=current_stats.count,
            significance_level=self._thresholds.significance_level,
        )

        # Classify severity
        severity = self._thresholds.classify_severity(percent_change, metric_type)

        # Generate context
        context = self._generate_context(
            metric_name,
            metric_type,
            percent_change,
            stat_result.is_significant,
            severity.value,
            stat_result.effect_size,
        )

        return MetricComparison(
            metric_name=metric_name,
            metric_type=metric_type,
            baseline_value=baseline_value,
            current_value=current_value,
            absolute_diff=current_value - baseline_value,
            percent_change=percent_change,
            p_value=stat_result.p_value,
            effect_size=stat_result.effect_size,
            is_significant=stat_result.is_significant,
            regression_severity=severity,
            context=context,
        )

    def _compare_rate(
        self,
        metric_name: str,
        metric_type: MetricType,
        baseline_value: float,
        current_value: float,
    ) -> MetricComparison:
        """
        Compare simple rate metrics (success_rate, failure_rate).

        Args:
            metric_name: Name for this metric
            metric_type: Type of metric
            baseline_value: Baseline rate
            current_value: Current rate

        Returns:
            MetricComparison for this metric
        """
        percent_change = calculate_percent_change(baseline_value, current_value)

        # For rates, we use absolute difference for significance
        # (e.g., going from 0.95 to 0.93 is a 2 percentage point drop)
        absolute_diff = current_value - baseline_value

        # Simple significance check for rates: configurable minimum absolute change
        is_significant = abs(absolute_diff) > self._thresholds.rate_significance

        # Classify severity
        severity = self._thresholds.classify_severity(percent_change, metric_type)

        # Generate context
        context = self._generate_rate_context(
            metric_name,
            metric_type,
            baseline_value,
            current_value,
            absolute_diff,
        )

        return MetricComparison(
            metric_name=metric_name,
            metric_type=metric_type,
            baseline_value=baseline_value,
            current_value=current_value,
            absolute_diff=absolute_diff,
            percent_change=percent_change,
            is_significant=is_significant,
            regression_severity=severity,
            context=context,
        )

    def _compare_order_metrics(
        self,
        baseline: OrderAggregateMetrics,
        current: OrderAggregateMetrics,
        result: ComparisonResult,
    ) -> None:
        """Compare order lifecycle metrics."""
        # Compare success rate (higher is better, like throughput)
        result.add_comparison(
            self._compare_rate(
                "order_success_rate",
                MetricType.THROUGHPUT,
                baseline.success_rate,
                current.success_rate,
            )
        )

        # Compare latency metrics
        latency_metrics = [
            ("time_to_submit", baseline.time_to_submit, current.time_to_submit),
            ("time_to_accept", baseline.time_to_accept, current.time_to_accept),
            ("time_to_fill", baseline.time_to_fill, current.time_to_fill),
            ("total_lifecycle", baseline.total_lifecycle, current.total_lifecycle),
        ]

        for name, baseline_stats, current_stats in latency_metrics:
            if baseline_stats.count > 0 and current_stats.count > 0:
                result.add_comparison(
                    self._compare_percentile_stats(
                        f"order_{name}",
                        MetricType.LATENCY,
                        baseline_stats,
                        current_stats,
                    )
                )

    def _compare_api_metrics(
        self,
        baseline: APIAggregateMetrics,
        current: APIAggregateMetrics,
        result: ComparisonResult,
    ) -> None:
        """Compare API metrics."""
        # Compare success rate (higher is better, like throughput)
        result.add_comparison(
            self._compare_rate(
                "api_success_rate",
                MetricType.THROUGHPUT,
                baseline.success_rate,
                current.success_rate,
            )
        )

        # Compare response time
        if baseline.response_time.count > 0 and current.response_time.count > 0:
            result.add_comparison(
                self._compare_percentile_stats(
                    "api_response_time",
                    MetricType.LATENCY,
                    baseline.response_time,
                    current.response_time,
                )
            )

        # Compare throughput
        result.add_comparison(
            self._compare_rate(
                "api_requests_per_second",
                MetricType.THROUGHPUT,
                baseline.requests_per_second,
                current.requests_per_second,
            )
        )

    def _compare_throughput(
        self,
        baseline: PerformanceBaseline,
        current: PerformanceBaseline,
        result: ComparisonResult,
    ) -> None:
        """Compare throughput metrics."""
        result.add_comparison(
            self._compare_rate(
                "orders_per_second",
                MetricType.THROUGHPUT,
                baseline.orders_per_second,
                current.orders_per_second,
            )
        )

        result.add_comparison(
            self._compare_rate(
                "peak_orders_per_second",
                MetricType.THROUGHPUT,
                baseline.peak_orders_per_second,
                current.peak_orders_per_second,
            )
        )

    def _compare_resource_metrics(
        self,
        baseline_resources: dict[str, ResourceAggregateMetrics],
        current_resources: dict[str, ResourceAggregateMetrics],
        result: ComparisonResult,
    ) -> None:
        """Compare resource utilization metrics."""
        # Find common containers
        common_containers = set(baseline_resources.keys()) & set(current_resources.keys())

        for container in common_containers:
            baseline = baseline_resources[container]
            current = current_resources[container]

            if baseline.sample_count > 0 and current.sample_count > 0:
                # Compare CPU usage
                result.add_comparison(
                    self._compare_percentile_stats(
                        f"resource_{container}_cpu",
                        MetricType.RESOURCE,
                        baseline.cpu_percent,
                        current.cpu_percent,
                    )
                )

                # Compare memory usage
                result.add_comparison(
                    self._compare_percentile_stats(
                        f"resource_{container}_memory",
                        MetricType.RESOURCE,
                        baseline.memory_percent,
                        current.memory_percent,
                    )
                )

    def _generate_context(
        self,
        metric_name: str,
        metric_type: MetricType,
        percent_change: float,
        is_significant: bool,
        severity: str,
        effect_size: float | None,
    ) -> str:
        """Generate human-readable context for a comparison."""
        change_str = format_percent_change(percent_change)
        effect_str = interpret_effect_size(effect_size)

        if not is_significant:
            return f"{metric_name}: {change_str} (not statistically significant)"

        direction = "increased" if percent_change > 0 else "decreased"

        if metric_type == MetricType.THROUGHPUT:
            good_bad = "improved" if percent_change > 0 else "degraded"
        else:
            good_bad = "degraded" if percent_change > 0 else "improved"

        return (
            f"{metric_name}: {change_str} ({direction}, {good_bad}), "
            f"severity={severity}, effect size={effect_str}"
        )

    def _generate_rate_context(
        self,
        metric_name: str,
        metric_type: MetricType,
        baseline_value: float,
        current_value: float,
        absolute_diff: float,
    ) -> str:
        """Generate context for rate metric comparison."""
        baseline_pct = baseline_value * 100
        current_pct = current_value * 100
        diff_pct = absolute_diff * 100

        if metric_type == MetricType.ERROR_RATE:
            # For error rates, lower is better
            if metric_name.endswith("success_rate"):
                good_bad = "improved" if absolute_diff > 0 else "degraded"
            else:
                good_bad = "degraded" if absolute_diff > 0 else "improved"
        elif metric_type == MetricType.THROUGHPUT:
            good_bad = "improved" if absolute_diff > 0 else "degraded"
        else:
            good_bad = "changed"

        sign = "+" if absolute_diff >= 0 else ""
        return (
            f"{metric_name}: {baseline_pct:.1f}% -> {current_pct:.1f}% "
            f"({sign}{diff_pct:.1f} pp, {good_bad})"
        )
