"""Automated reporting for performance testing."""

from cow_performance.reporting.csv_export import CSVExporter
from cow_performance.reporting.formatters import (
    JSONReportFormatter,
    MarkdownReportFormatter,
    TextReportFormatter,
)
from cow_performance.reporting.generator import ReportGenerator
from cow_performance.reporting.models import (
    ExecutiveSummary,
    PerformanceReport,
    Recommendation,
    RecommendationCategory,
    RecommendationSeverity,
    ReportVerdict,
)
from cow_performance.reporting.recommendations import RecommendationsEngine
from cow_performance.reporting.summary import (
    format_duration,
    format_latency,
    format_rate,
    generate_executive_summary,
)

__all__ = [
    # Main generator
    "ReportGenerator",
    # Models
    "ExecutiveSummary",
    "PerformanceReport",
    "Recommendation",
    "RecommendationCategory",
    "RecommendationSeverity",
    "ReportVerdict",
    # Components
    "RecommendationsEngine",
    "CSVExporter",
    # Formatters
    "TextReportFormatter",
    "MarkdownReportFormatter",
    "JSONReportFormatter",
    # Utilities
    "generate_executive_summary",
    "format_duration",
    "format_latency",
    "format_rate",
]
