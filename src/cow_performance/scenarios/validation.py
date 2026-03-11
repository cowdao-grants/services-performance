"""Success criteria validation for performance test results."""

from dataclasses import dataclass

from rich.console import Console
from rich.table import Table

from cow_performance.cli.commands.scenarios import SuccessCriteria


@dataclass
class ValidationFailure:
    """A single validation failure."""

    criterion: str
    expected: str
    actual: str
    message: str


@dataclass
class ValidationResult:
    """Result of validating test results against success criteria."""

    passed: bool
    failures: list[ValidationFailure]
    total_checks: int

    @property
    def success_rate(self) -> float:
        """Calculate the success rate of validation checks."""
        if self.total_checks == 0:
            return 1.0
        passed_checks = self.total_checks - len(self.failures)
        return passed_checks / self.total_checks


class SuccessCriteriaValidator:
    """Validator for test results against success criteria."""

    def __init__(self, criteria: SuccessCriteria):
        """Initialize validator with success criteria.

        Args:
            criteria: Success criteria to validate against
        """
        self.criteria = criteria

    def validate(
        self,
        success_rate: float | None = None,
        p95_latency_seconds: float | None = None,
        error_rate: float | None = None,
        throughput_per_second: float | None = None,
    ) -> ValidationResult:
        """Validate test results against success criteria.

        Args:
            success_rate: Order success rate (0.0-1.0)
            p95_latency_seconds: P95 latency in seconds
            error_rate: Error rate (0.0-1.0)
            throughput_per_second: Throughput in orders per second

        Returns:
            ValidationResult with pass/fail status and any failures
        """
        failures: list[ValidationFailure] = []
        total_checks = 0

        # Check min success rate
        if self.criteria.min_success_rate is not None and success_rate is not None:
            total_checks += 1
            if success_rate < self.criteria.min_success_rate:
                failures.append(
                    ValidationFailure(
                        criterion="Min Success Rate",
                        expected=f">= {self.criteria.min_success_rate:.1%}",
                        actual=f"{success_rate:.1%}",
                        message=f"Success rate {success_rate:.1%} is below minimum {self.criteria.min_success_rate:.1%}",
                    )
                )

        # Check max P95 latency
        if self.criteria.max_p95_latency_seconds is not None and p95_latency_seconds is not None:
            total_checks += 1
            if p95_latency_seconds > self.criteria.max_p95_latency_seconds:
                failures.append(
                    ValidationFailure(
                        criterion="Max P95 Latency",
                        expected=f"<= {self.criteria.max_p95_latency_seconds}s",
                        actual=f"{p95_latency_seconds:.2f}s",
                        message=f"P95 latency {p95_latency_seconds:.2f}s exceeds maximum {self.criteria.max_p95_latency_seconds}s",
                    )
                )

        # Check max error rate
        if self.criteria.max_error_rate is not None and error_rate is not None:
            total_checks += 1
            if error_rate > self.criteria.max_error_rate:
                failures.append(
                    ValidationFailure(
                        criterion="Max Error Rate",
                        expected=f"<= {self.criteria.max_error_rate:.1%}",
                        actual=f"{error_rate:.1%}",
                        message=f"Error rate {error_rate:.1%} exceeds maximum {self.criteria.max_error_rate:.1%}",
                    )
                )

        # Check min throughput
        if (
            self.criteria.min_throughput_per_second is not None
            and throughput_per_second is not None
        ):
            total_checks += 1
            if throughput_per_second < self.criteria.min_throughput_per_second:
                failures.append(
                    ValidationFailure(
                        criterion="Min Throughput",
                        expected=f">= {self.criteria.min_throughput_per_second} orders/s",
                        actual=f"{throughput_per_second:.2f} orders/s",
                        message=f"Throughput {throughput_per_second:.2f} orders/s is below minimum {self.criteria.min_throughput_per_second} orders/s",
                    )
                )

        return ValidationResult(
            passed=len(failures) == 0,
            failures=failures,
            total_checks=total_checks,
        )

    def validate_from_dict(self, results: dict) -> ValidationResult:
        """Validate test results from a dictionary.

        Args:
            results: Dictionary containing test results with keys:
                - success_rate (float)
                - p95_latency_seconds (float)
                - error_rate (float)
                - throughput_per_second (float)

        Returns:
            ValidationResult with pass/fail status and any failures
        """
        return self.validate(
            success_rate=results.get("success_rate"),
            p95_latency_seconds=results.get("p95_latency_seconds"),
            error_rate=results.get("error_rate"),
            throughput_per_second=results.get("throughput_per_second"),
        )


def display_validation_result(result: ValidationResult, console: Console | None = None) -> None:
    """Display validation result in a nice format.

    Args:
        result: Validation result to display
        console: Optional Rich console for output (creates new one if not provided)
    """
    if console is None:
        console = Console()

    # Display overall result
    if result.passed:
        console.print("\n[bold green]✓ Success Criteria: PASSED[/bold green]")
        console.print(f"All {result.total_checks} criteria met successfully.")
    else:
        console.print("\n[bold red]✗ Success Criteria: FAILED[/bold red]")
        console.print(
            f"{len(result.failures)}/{result.total_checks} criteria failed "
            f"({result.success_rate:.0%} pass rate)"
        )

    # Display failures if any
    if result.failures:
        console.print()
        table = Table(title="Failed Criteria", show_header=True, header_style="bold red")
        table.add_column("Criterion", style="cyan")
        table.add_column("Expected", style="yellow")
        table.add_column("Actual", style="red")
        table.add_column("Message", style="dim")

        for failure in result.failures:
            table.add_row(
                failure.criterion,
                failure.expected,
                failure.actual,
                failure.message,
            )

        console.print(table)
    console.print()
