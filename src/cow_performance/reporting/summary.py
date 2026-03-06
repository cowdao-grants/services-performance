"""Summary statistics generation for performance reports."""

import logging
from datetime import datetime

from cow_performance.baselines.models import PerformanceBaseline
from cow_performance.reporting.models import ExecutiveSummary, ReportVerdict

logger = logging.getLogger(__name__)

# Verdict thresholds
SUCCESS_RATE_WARNING_THRESHOLD = 0.95  # Below 95% = warning
SUCCESS_RATE_FAILURE_THRESHOLD = 0.80  # Below 80% = failure
LATENCY_WARNING_MULTIPLIER = 2.0  # 2x expected = warning
LATENCY_FAILURE_MULTIPLIER = 5.0  # 5x expected = failure
EXPECTED_FILL_LATENCY_MS = 5000.0  # Expected P95 fill latency


def generate_executive_summary(
    baseline: PerformanceBaseline,
    test_name: str | None = None,
) -> ExecutiveSummary:
    """
    Generate an executive summary from a performance baseline.

    Args:
        baseline: The performance baseline containing aggregated metrics
        test_name: Optional test name override

    Returns:
        ExecutiveSummary with key metrics and verdict
    """
    # Calculate timestamps
    test_end = datetime.fromtimestamp(baseline.created_at)
    test_start = datetime.fromtimestamp(baseline.created_at - baseline.duration_seconds)

    # Extract order metrics
    order_metrics = baseline.order_metrics
    api_metrics = baseline.api_metrics

    # Extract order counts
    if order_metrics:
        total_submitted = order_metrics.orders_submitted
        total_filled = order_metrics.orders_filled
        total_failed = order_metrics.orders_failed
        success_rate = order_metrics.success_rate
        submission_latency_p95 = order_metrics.time_to_submit.p95 * 1000  # to ms
        fill_latency_p95 = order_metrics.time_to_fill.p95 * 1000  # to ms
        lifecycle_latency_p95 = order_metrics.total_lifecycle.p95 * 1000  # to ms
    else:
        total_submitted = 0
        total_filled = 0
        total_failed = 0
        success_rate = 0.0
        submission_latency_p95 = 0.0
        fill_latency_p95 = 0.0
        lifecycle_latency_p95 = 0.0

    # Extract API metrics
    if api_metrics:
        total_api_requests = api_metrics.total_requests
        api_success_rate = api_metrics.success_rate
        api_response_p95 = api_metrics.response_time.p95
    else:
        total_api_requests = 0
        api_success_rate = 0.0
        api_response_p95 = 0.0

    # Determine verdict
    verdict, verdict_reason, findings = _determine_verdict(
        success_rate=success_rate,
        fill_latency_p95_ms=fill_latency_p95,
        api_success_rate=api_success_rate,
        total_failed=total_failed,
    )

    return ExecutiveSummary(
        test_name=test_name or baseline.name,
        test_duration_seconds=baseline.duration_seconds,
        test_start_time=test_start,
        test_end_time=test_end,
        total_orders_submitted=total_submitted,
        total_orders_filled=total_filled,
        total_orders_failed=total_failed,
        success_rate=success_rate,
        average_throughput=baseline.orders_per_second,
        peak_throughput=baseline.peak_orders_per_second,
        submission_latency_p95_ms=submission_latency_p95,
        fill_latency_p95_ms=fill_latency_p95,
        total_lifecycle_p95_ms=lifecycle_latency_p95,
        total_api_requests=total_api_requests,
        api_success_rate=api_success_rate,
        api_response_time_p95_ms=api_response_p95,
        verdict=verdict,
        verdict_reason=verdict_reason,
        key_findings=findings,
    )


def _determine_verdict(
    success_rate: float,
    fill_latency_p95_ms: float,
    api_success_rate: float,
    total_failed: int,
) -> tuple[ReportVerdict, str, list[str]]:
    """
    Determine the overall verdict based on metrics.

    Returns:
        Tuple of (verdict, reason, list of key findings)
    """
    findings: list[str] = []
    issues: list[str] = []

    # Check success rate
    if success_rate >= SUCCESS_RATE_WARNING_THRESHOLD:
        findings.append(f"Order success rate is excellent ({success_rate:.1%})")
    elif success_rate >= SUCCESS_RATE_FAILURE_THRESHOLD:
        issues.append(f"Order success rate is below target ({success_rate:.1%})")
        findings.append(f"Order success rate needs attention ({success_rate:.1%})")
    else:
        issues.append(f"Critical: Order success rate is very low ({success_rate:.1%})")
        findings.append(f"Order success rate is critically low ({success_rate:.1%})")

    # Check latency
    if fill_latency_p95_ms > 0:
        if fill_latency_p95_ms <= EXPECTED_FILL_LATENCY_MS:
            findings.append(
                f"Fill latency is within expectations (P95: {fill_latency_p95_ms:.0f}ms)"
            )
        elif fill_latency_p95_ms <= EXPECTED_FILL_LATENCY_MS * LATENCY_WARNING_MULTIPLIER:
            findings.append(f"Fill latency is elevated (P95: {fill_latency_p95_ms:.0f}ms)")
        else:
            issues.append(f"Fill latency is very high (P95: {fill_latency_p95_ms:.0f}ms)")
            findings.append(f"Fill latency is critically high (P95: {fill_latency_p95_ms:.0f}ms)")

    # Check API success rate
    if api_success_rate < 0.99:
        issues.append(f"API success rate is below 99% ({api_success_rate:.1%})")
        findings.append(f"API experiencing some failures ({api_success_rate:.1%} success)")

    # Check failed orders
    if total_failed > 0:
        findings.append(f"{total_failed} orders failed during the test")

    # Determine final verdict
    critical_issues = [i for i in issues if "Critical" in i]
    if critical_issues:
        return (
            ReportVerdict.FAILURE,
            critical_issues[0],
            findings,
        )
    elif issues:
        return (
            ReportVerdict.WARNING,
            issues[0],
            findings,
        )
    else:
        return (
            ReportVerdict.SUCCESS,
            "All metrics within acceptable thresholds",
            findings,
        )


def format_duration(seconds: float) -> str:
    """Format duration in human-readable form."""
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f}m"
    else:
        hours = seconds / 3600
        return f"{hours:.1f}h"


def format_rate(rate: float) -> str:
    """Format rate as percentage."""
    return f"{rate * 100:.1f}%"


def format_latency(ms: float) -> str:
    """Format latency in appropriate units."""
    if ms < 1:
        return f"{ms * 1000:.0f}μs"
    elif ms < 1000:
        return f"{ms:.1f}ms"
    else:
        return f"{ms / 1000:.2f}s"
