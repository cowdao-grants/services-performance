"""Data models and text/JSON formatting for scaling experiment results."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ScalingPhaseResult:
    """Metrics captured for a single order-count level in a scaling experiment."""

    order_count_target: int
    """Target number of orders for this phase."""

    orders_submitted: int
    """Actual orders submitted during the phase."""

    orders_filled: int
    """Orders that reached the FILLED state."""

    duration_seconds: float
    """Wall-clock duration of the test phase."""

    p99_submission_latency_ms: float
    """99th-percentile creation-to-submission latency in milliseconds."""

    p99_lifecycle_latency_ms: float
    """99th-percentile end-to-end order lifecycle latency in milliseconds."""

    orders_per_second: float
    """Observed order submission throughput."""

    memory_delta_bytes: dict[str, int] = field(default_factory=dict)
    """RSS delta per container (after − before) in bytes."""

    total_memory_delta_bytes: int = 0
    """Sum of RSS deltas across all monitored containers."""


@dataclass
class ComplexityEntry:
    """Complexity analysis result for a single metric."""

    metric: str
    slope: float
    r_squared: float
    complexity_class: str
    label: str


@dataclass
class ScalingReport:
    """Complete scaling experiment report with per-phase data and complexity analysis."""

    scenario_name: str
    phases: list[ScalingPhaseResult]
    complexity_results: list[ComplexityEntry] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-serialisable dictionary."""
        return {
            "scenario_name": self.scenario_name,
            "phases": [
                {
                    "order_count_target": p.order_count_target,
                    "orders_submitted": p.orders_submitted,
                    "orders_filled": p.orders_filled,
                    "duration_seconds": round(p.duration_seconds, 2),
                    "p99_submission_latency_ms": round(p.p99_submission_latency_ms, 1),
                    "p99_lifecycle_latency_ms": round(p.p99_lifecycle_latency_ms, 1),
                    "orders_per_second": round(p.orders_per_second, 3),
                    "memory_delta_bytes": p.memory_delta_bytes,
                    "total_memory_delta_bytes": p.total_memory_delta_bytes,
                }
                for p in self.phases
            ],
            "complexity": [
                {
                    "metric": c.metric,
                    "slope": round(c.slope, 3),
                    "r_squared": round(c.r_squared, 3),
                    "complexity_class": c.complexity_class,
                    "label": c.label,
                }
                for c in self.complexity_results
            ],
        }

    def to_json(self) -> str:
        """Serialize to a pretty-printed JSON string."""
        return json.dumps(self.to_dict(), indent=2)
