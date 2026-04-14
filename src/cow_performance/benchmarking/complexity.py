"""Algorithmic complexity analysis for scaling experiments.

Fits a power-law model y ~ x^k to (x, y) measurement pairs using
log-log linear regression and classifies the exponent k.
"""

from dataclasses import dataclass
from enum import StrEnum

import numpy as np


class ComplexityClass(StrEnum):
    """Algorithmic complexity classification based on power-law exponent."""

    SUBLINEAR = "sublinear"  # k < 0.8 — O(n^k), better than linear
    LINEAR = "linear"  # 0.8 ≤ k < 1.2 — O(n)
    LOG_LINEAR = "log_linear"  # 1.2 ≤ k < 1.8 — approx O(n log n)
    QUADRATIC = "quadratic"  # 1.8 ≤ k < 2.2 — O(n²)
    SUPERLINEAR = "superlinear"  # k ≥ 2.2 — O(n^k), worse than quadratic


@dataclass
class ComplexityFitResult:
    """Result of a power-law fit to a set of measurements."""

    slope: float
    """Power-law exponent k (y ~ x^k)."""

    intercept: float
    """Log-space intercept (log(a) in y = a * x^k)."""

    r_squared: float
    """Coefficient of determination on the log-log fit (0–1)."""

    complexity_class: ComplexityClass
    """Classified complexity bucket."""

    label: str
    """Human-readable complexity label, e.g. 'O(n) — linear'."""

    def is_good_fit(self) -> bool:
        """Return True if R² ≥ 0.90, indicating reliable classification."""
        return self.r_squared >= 0.90


class ComplexityAnalyzer:
    """Fits power-law models and classifies algorithmic complexity.

    Uses log-log linear regression: log(y) = k*log(x) + c, so y = e^c * x^k.
    The slope k is interpreted as the complexity exponent.

    Example:
        analyzer = ComplexityAnalyzer()
        result = analyzer.fit(
            x=[50, 100, 200, 400, 800],
            y=[12.1, 23.8, 47.2, 94.5, 189.0],
        )
        print(result.label)   # "O(n) — linear"
        print(result.slope)   # ~1.0
    """

    def fit(self, x: list[float], y: list[float]) -> ComplexityFitResult:
        """Fit a power-law model to the given (x, y) pairs.

        Args:
            x: Independent variable values (e.g. order counts). Must be positive.
            y: Dependent variable values (e.g. latencies). Must be positive.

        Returns:
            ComplexityFitResult with slope, R², class, and label.

        Raises:
            ValueError: If fewer than 2 positive data points remain after filtering.
        """
        xs = np.asarray(x, dtype=float)
        ys = np.asarray(y, dtype=float)

        mask = (xs > 0) & (ys > 0)
        xs, ys = xs[mask], ys[mask]

        if len(xs) < 2:
            raise ValueError("Need at least 2 positive (x, y) pairs for regression.")

        log_x = np.log(xs)
        log_y = np.log(ys)

        slope, intercept = np.polyfit(log_x, log_y, 1)

        predicted = slope * log_x + intercept
        ss_res = float(np.sum((log_y - predicted) ** 2))
        ss_tot = float(np.sum((log_y - float(np.mean(log_y))) ** 2))
        r_squared = 1.0 - ss_res / ss_tot if ss_tot > 0 else 1.0

        cls = self._classify(float(slope))
        label = self._label(cls, float(slope))

        return ComplexityFitResult(
            slope=float(slope),
            intercept=float(intercept),
            r_squared=r_squared,
            complexity_class=cls,
            label=label,
        )

    @staticmethod
    def _classify(slope: float) -> ComplexityClass:
        if slope < 0.8:
            return ComplexityClass.SUBLINEAR
        elif slope < 1.2:
            return ComplexityClass.LINEAR
        elif slope < 1.8:
            return ComplexityClass.LOG_LINEAR
        elif slope < 2.2:
            return ComplexityClass.QUADRATIC
        else:
            return ComplexityClass.SUPERLINEAR

    @staticmethod
    def _label(cls: ComplexityClass, slope: float) -> str:
        templates: dict[ComplexityClass, str] = {
            ComplexityClass.SUBLINEAR: f"O(n^{slope:.2f}) — sub-linear",
            ComplexityClass.LINEAR: "O(n) — linear",
            ComplexityClass.LOG_LINEAR: "O(n log n) — log-linear (approx.)",
            ComplexityClass.QUADRATIC: "O(n²) — quadratic",
            ComplexityClass.SUPERLINEAR: f"O(n^{slope:.2f}) — super-linear",
        }
        return templates[cls]
