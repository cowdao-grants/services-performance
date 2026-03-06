"""Recommendations engine for performance analysis."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from cow_performance.baselines.models import PerformanceBaseline
from cow_performance.reporting.models import (
    Recommendation,
    RecommendationCategory,
    RecommendationSeverity,
)

if TYPE_CHECKING:
    from cow_performance.comparison.models import ComparisonResult

logger = logging.getLogger(__name__)

# Thresholds for recommendations
LATENCY_THRESHOLDS = {
    "submission_p95_warning_ms": 500,
    "submission_p95_critical_ms": 2000,
    "fill_p95_warning_ms": 5000,
    "fill_p95_critical_ms": 15000,
}

THROUGHPUT_THRESHOLDS = {
    "min_orders_per_second": 0.5,
    "warning_utilization": 0.5,  # 50% of target
}

RELIABILITY_THRESHOLDS = {
    "success_rate_warning": 0.95,
    "success_rate_critical": 0.80,
    "api_success_rate_warning": 0.99,
}

RESOURCE_THRESHOLDS = {
    "cpu_warning_percent": 70,
    "cpu_critical_percent": 90,
    "memory_warning_percent": 70,
    "memory_critical_percent": 90,
}


class RecommendationsEngine:
    """
    Analyzes metrics and generates actionable recommendations.

    Example:
        engine = RecommendationsEngine()
        recommendations = engine.analyze(baseline)
        for rec in recommendations:
            print(f"[{rec.severity}] {rec.title}: {rec.action}")
    """

    def __init__(
        self,
        latency_thresholds: dict | None = None,
        throughput_thresholds: dict | None = None,
        reliability_thresholds: dict | None = None,
        resource_thresholds: dict | None = None,
    ):
        """
        Initialize the recommendations engine.

        Args:
            latency_thresholds: Custom latency thresholds
            throughput_thresholds: Custom throughput thresholds
            reliability_thresholds: Custom reliability thresholds
            resource_thresholds: Custom resource thresholds
        """
        self._latency = latency_thresholds or LATENCY_THRESHOLDS
        self._throughput = throughput_thresholds or THROUGHPUT_THRESHOLDS
        self._reliability = reliability_thresholds or RELIABILITY_THRESHOLDS
        self._resource = resource_thresholds or RESOURCE_THRESHOLDS

    def analyze(self, baseline: PerformanceBaseline) -> list[Recommendation]:
        """
        Analyze a baseline and generate recommendations.

        Args:
            baseline: The performance baseline to analyze

        Returns:
            List of recommendations sorted by severity
        """
        recommendations: list[Recommendation] = []

        # Analyze order metrics
        if baseline.order_metrics:
            recommendations.extend(self._analyze_latency(baseline))
            recommendations.extend(self._analyze_reliability(baseline))

        # Analyze API metrics
        if baseline.api_metrics:
            recommendations.extend(self._analyze_api_performance(baseline))

        # Analyze throughput
        recommendations.extend(self._analyze_throughput(baseline))

        # Analyze resource utilization
        if baseline.resource_metrics:
            recommendations.extend(self._analyze_resources(baseline))

        # Sort by severity (critical first)
        severity_order = {
            RecommendationSeverity.CRITICAL: 0,
            RecommendationSeverity.WARNING: 1,
            RecommendationSeverity.INFO: 2,
        }
        recommendations.sort(key=lambda r: severity_order[r.severity])

        return recommendations

    def _analyze_latency(self, baseline: PerformanceBaseline) -> list[Recommendation]:
        """Analyze latency metrics and generate recommendations."""
        recommendations: list[Recommendation] = []
        om = baseline.order_metrics
        if not om:
            return recommendations

        # Check submission latency
        submission_p95_ms = om.time_to_submit.p95 * 1000
        if submission_p95_ms > self._latency["submission_p95_critical_ms"]:
            recommendations.append(
                Recommendation(
                    severity=RecommendationSeverity.CRITICAL,
                    category=RecommendationCategory.LATENCY,
                    title="Critical submission latency",
                    description=(
                        f"Order submission P95 latency is {submission_p95_ms:.0f}ms, "
                        f"exceeding the critical threshold of "
                        f"{self._latency['submission_p95_critical_ms']}ms."
                    ),
                    action="Investigate API endpoint performance and network connectivity.",
                    metric_name="time_to_submit_p95",
                    metric_value=submission_p95_ms,
                    threshold=self._latency["submission_p95_critical_ms"],
                )
            )
        elif submission_p95_ms > self._latency["submission_p95_warning_ms"]:
            recommendations.append(
                Recommendation(
                    severity=RecommendationSeverity.WARNING,
                    category=RecommendationCategory.LATENCY,
                    title="Elevated submission latency",
                    description=(
                        f"Order submission P95 latency is {submission_p95_ms:.0f}ms, "
                        f"above the warning threshold of "
                        f"{self._latency['submission_p95_warning_ms']}ms."
                    ),
                    action=(
                        "Monitor API response times and consider " "rate limiting adjustments."
                    ),
                    metric_name="time_to_submit_p95",
                    metric_value=submission_p95_ms,
                    threshold=self._latency["submission_p95_warning_ms"],
                )
            )

        # Check fill latency
        fill_p95_ms = om.time_to_fill.p95 * 1000
        if fill_p95_ms > self._latency["fill_p95_critical_ms"]:
            recommendations.append(
                Recommendation(
                    severity=RecommendationSeverity.CRITICAL,
                    category=RecommendationCategory.LATENCY,
                    title="Critical fill latency",
                    description=(
                        f"Order fill P95 latency is {fill_p95_ms:.0f}ms, "
                        f"exceeding the critical threshold of "
                        f"{self._latency['fill_p95_critical_ms']}ms."
                    ),
                    action=(
                        "Investigate solver performance, orderbook indexing, "
                        "and settlement transaction processing."
                    ),
                    metric_name="time_to_fill_p95",
                    metric_value=fill_p95_ms,
                    threshold=self._latency["fill_p95_critical_ms"],
                )
            )
        elif fill_p95_ms > self._latency["fill_p95_warning_ms"]:
            recommendations.append(
                Recommendation(
                    severity=RecommendationSeverity.WARNING,
                    category=RecommendationCategory.LATENCY,
                    title="Elevated fill latency",
                    description=(
                        f"Order fill P95 latency is {fill_p95_ms:.0f}ms, "
                        f"above the warning threshold of "
                        f"{self._latency['fill_p95_warning_ms']}ms."
                    ),
                    action="Review solver configuration and market liquidity.",
                    metric_name="time_to_fill_p95",
                    metric_value=fill_p95_ms,
                    threshold=self._latency["fill_p95_warning_ms"],
                )
            )

        return recommendations

    def _analyze_reliability(self, baseline: PerformanceBaseline) -> list[Recommendation]:
        """Analyze reliability metrics."""
        recommendations: list[Recommendation] = []
        om = baseline.order_metrics
        if not om:
            return recommendations

        success_rate = om.success_rate
        if success_rate < self._reliability["success_rate_critical"]:
            recommendations.append(
                Recommendation(
                    severity=RecommendationSeverity.CRITICAL,
                    category=RecommendationCategory.RELIABILITY,
                    title="Critical order failure rate",
                    description=(
                        f"Order success rate is {success_rate:.1%}, "
                        f"below the critical threshold of "
                        f"{self._reliability['success_rate_critical']:.0%}."
                    ),
                    action=(
                        "Investigate order rejection reasons. Check error logs for "
                        "insufficient funds, invalid orders, or API errors."
                    ),
                    metric_name="success_rate",
                    metric_value=success_rate,
                    threshold=self._reliability["success_rate_critical"],
                )
            )
        elif success_rate < self._reliability["success_rate_warning"]:
            recommendations.append(
                Recommendation(
                    severity=RecommendationSeverity.WARNING,
                    category=RecommendationCategory.RELIABILITY,
                    title="Elevated order failure rate",
                    description=(
                        f"Order success rate is {success_rate:.1%}, "
                        f"below the target of "
                        f"{self._reliability['success_rate_warning']:.0%}."
                    ),
                    action="Review failed orders to identify common failure patterns.",
                    metric_name="success_rate",
                    metric_value=success_rate,
                    threshold=self._reliability["success_rate_warning"],
                )
            )

        return recommendations

    def _analyze_api_performance(self, baseline: PerformanceBaseline) -> list[Recommendation]:
        """Analyze API performance metrics."""
        recommendations: list[Recommendation] = []
        am = baseline.api_metrics
        if not am:
            return recommendations

        if am.success_rate < self._reliability["api_success_rate_warning"]:
            recommendations.append(
                Recommendation(
                    severity=RecommendationSeverity.WARNING,
                    category=RecommendationCategory.RELIABILITY,
                    title="API experiencing failures",
                    description=(
                        f"API success rate is {am.success_rate:.1%}, "
                        f"below the expected "
                        f"{self._reliability['api_success_rate_warning']:.0%}."
                    ),
                    action=(
                        "Check API error responses and status codes. "
                        "Review rate limiting and connection pooling settings."
                    ),
                    metric_name="api_success_rate",
                    metric_value=am.success_rate,
                    threshold=self._reliability["api_success_rate_warning"],
                )
            )

        return recommendations

    def _analyze_throughput(self, baseline: PerformanceBaseline) -> list[Recommendation]:
        """Analyze throughput metrics."""
        recommendations: list[Recommendation] = []

        if baseline.orders_per_second < self._throughput["min_orders_per_second"]:
            recommendations.append(
                Recommendation(
                    severity=RecommendationSeverity.WARNING,
                    category=RecommendationCategory.THROUGHPUT,
                    title="Low throughput detected",
                    description=(
                        f"Average throughput is {baseline.orders_per_second:.2f} "
                        f"orders/second, below the minimum expected of "
                        f"{self._throughput['min_orders_per_second']} orders/second."
                    ),
                    action=(
                        "Check rate limiting configuration, network latency, "
                        "and trader concurrency settings."
                    ),
                    metric_name="orders_per_second",
                    metric_value=baseline.orders_per_second,
                    threshold=self._throughput["min_orders_per_second"],
                )
            )

        return recommendations

    def _analyze_resources(self, baseline: PerformanceBaseline) -> list[Recommendation]:
        """Analyze resource utilization metrics."""
        recommendations: list[Recommendation] = []

        for container_name, metrics in baseline.resource_metrics.items():
            # Check CPU
            cpu_p95 = metrics.cpu_percent.p95
            if cpu_p95 > self._resource["cpu_critical_percent"]:
                recommendations.append(
                    Recommendation(
                        severity=RecommendationSeverity.CRITICAL,
                        category=RecommendationCategory.RESOURCE,
                        title=f"Critical CPU usage on {container_name}",
                        description=(
                            f"Container '{container_name}' CPU usage P95 is "
                            f"{cpu_p95:.1f}%, exceeding the critical threshold of "
                            f"{self._resource['cpu_critical_percent']}%."
                        ),
                        action=(
                            "Consider scaling horizontally or optimizing "
                            "the container's workload."
                        ),
                        metric_name=f"{container_name}_cpu_p95",
                        metric_value=cpu_p95,
                        threshold=self._resource["cpu_critical_percent"],
                    )
                )
            elif cpu_p95 > self._resource["cpu_warning_percent"]:
                recommendations.append(
                    Recommendation(
                        severity=RecommendationSeverity.WARNING,
                        category=RecommendationCategory.RESOURCE,
                        title=f"High CPU usage on {container_name}",
                        description=(
                            f"Container '{container_name}' CPU usage P95 is " f"{cpu_p95:.1f}%."
                        ),
                        action="Monitor CPU usage trends and consider optimization.",
                        metric_name=f"{container_name}_cpu_p95",
                        metric_value=cpu_p95,
                        threshold=self._resource["cpu_warning_percent"],
                    )
                )

            # Check memory
            mem_p95 = metrics.memory_percent.p95
            if mem_p95 > self._resource["memory_critical_percent"]:
                recommendations.append(
                    Recommendation(
                        severity=RecommendationSeverity.CRITICAL,
                        category=RecommendationCategory.RESOURCE,
                        title=f"Critical memory usage on {container_name}",
                        description=(
                            f"Container '{container_name}' memory usage P95 is "
                            f"{mem_p95:.1f}%, exceeding the critical threshold of "
                            f"{self._resource['memory_critical_percent']}%."
                        ),
                        action=(
                            "Investigate memory leaks or increase memory limits. "
                            "Consider restarting the container."
                        ),
                        metric_name=f"{container_name}_memory_p95",
                        metric_value=mem_p95,
                        threshold=self._resource["memory_critical_percent"],
                    )
                )
            elif mem_p95 > self._resource["memory_warning_percent"]:
                recommendations.append(
                    Recommendation(
                        severity=RecommendationSeverity.WARNING,
                        category=RecommendationCategory.RESOURCE,
                        title=f"High memory usage on {container_name}",
                        description=(
                            f"Container '{container_name}' memory usage P95 is " f"{mem_p95:.1f}%."
                        ),
                        action="Monitor memory usage trends and review allocation.",
                        metric_name=f"{container_name}_memory_p95",
                        metric_value=mem_p95,
                        threshold=self._resource["memory_warning_percent"],
                    )
                )

        return recommendations

    def analyze_comparison(self, comparison: ComparisonResult) -> list[Recommendation]:
        """
        Generate recommendations from a comparison result.

        Args:
            comparison: ComparisonResult from COW-589

        Returns:
            List of regression-related recommendations
        """
        recommendations: list[Recommendation] = []

        # Import here to avoid circular dependency
        try:
            from cow_performance.comparison.models import RegressionSeverity
        except ImportError:
            logger.warning("Comparison module not available")
            return recommendations

        for regression in comparison.regressions:
            if regression.regression_severity == RegressionSeverity.CRITICAL:
                severity = RecommendationSeverity.CRITICAL
            elif regression.regression_severity == RegressionSeverity.MAJOR:
                severity = RecommendationSeverity.WARNING
            else:
                severity = RecommendationSeverity.INFO

            recommendations.append(
                Recommendation(
                    severity=severity,
                    category=RecommendationCategory.REGRESSION,
                    title=f"Regression detected: {regression.metric_name}",
                    description=regression.context,
                    action=(
                        "Review recent changes that may have impacted this metric. "
                        "Consider reverting or optimizing the affected code."
                    ),
                    metric_name=regression.metric_name,
                    metric_value=regression.current_value,
                    threshold=regression.baseline_value,
                )
            )

        return recommendations
