"""Tests for scenario success criteria validation."""


from cow_performance.cli.commands.scenarios import SuccessCriteria
from cow_performance.scenarios.validation import (
    SuccessCriteriaValidator,
    ValidationFailure,
    ValidationResult,
)


class TestValidationResult:
    """Test ValidationResult dataclass."""

    def test_success_rate_all_passed(self):
        """Test success rate with no failures."""
        result = ValidationResult(passed=True, failures=[], total_checks=4)
        assert result.success_rate == 1.0

    def test_success_rate_some_failed(self):
        """Test success rate with some failures."""
        failures = [
            ValidationFailure(
                criterion="Test",
                expected="X",
                actual="Y",
                message="Failed",
            )
        ]
        result = ValidationResult(passed=False, failures=failures, total_checks=4)
        assert result.success_rate == 0.75  # 3/4 passed

    def test_success_rate_all_failed(self):
        """Test success rate with all failures."""
        failures = [
            ValidationFailure(
                criterion="Test1",
                expected="X",
                actual="Y",
                message="Failed",
            ),
            ValidationFailure(
                criterion="Test2",
                expected="X",
                actual="Y",
                message="Failed",
            ),
        ]
        result = ValidationResult(passed=False, failures=failures, total_checks=2)
        assert result.success_rate == 0.0

    def test_success_rate_no_checks(self):
        """Test success rate with no checks."""
        result = ValidationResult(passed=True, failures=[], total_checks=0)
        assert result.success_rate == 1.0


class TestSuccessCriteriaValidator:
    """Test SuccessCriteriaValidator."""

    def test_all_criteria_pass(self):
        """Test when all criteria pass."""
        criteria = SuccessCriteria(
            min_success_rate=0.90,
            max_p95_latency_seconds=10.0,
            max_error_rate=0.10,
            min_throughput_per_second=5.0,
        )
        validator = SuccessCriteriaValidator(criteria)

        result = validator.validate(
            success_rate=0.95,
            p95_latency_seconds=8.0,
            error_rate=0.05,
            throughput_per_second=6.0,
        )

        assert result.passed is True
        assert len(result.failures) == 0
        assert result.total_checks == 4
        assert result.success_rate == 1.0

    def test_success_rate_failure(self):
        """Test when success rate fails."""
        criteria = SuccessCriteria(min_success_rate=0.90)
        validator = SuccessCriteriaValidator(criteria)

        result = validator.validate(success_rate=0.85)

        assert result.passed is False
        assert len(result.failures) == 1
        assert result.failures[0].criterion == "Min Success Rate"
        assert "85.0%" in result.failures[0].actual
        assert "90.0%" in result.failures[0].expected

    def test_p95_latency_failure(self):
        """Test when P95 latency fails."""
        criteria = SuccessCriteria(max_p95_latency_seconds=10.0)
        validator = SuccessCriteriaValidator(criteria)

        result = validator.validate(p95_latency_seconds=15.0)

        assert result.passed is False
        assert len(result.failures) == 1
        assert result.failures[0].criterion == "Max P95 Latency"
        assert "15.00s" in result.failures[0].actual
        assert "10.0s" in result.failures[0].expected

    def test_error_rate_failure(self):
        """Test when error rate fails."""
        criteria = SuccessCriteria(max_error_rate=0.05)
        validator = SuccessCriteriaValidator(criteria)

        result = validator.validate(error_rate=0.10)

        assert result.passed is False
        assert len(result.failures) == 1
        assert result.failures[0].criterion == "Max Error Rate"
        assert "10.0%" in result.failures[0].actual
        assert "5.0%" in result.failures[0].expected

    def test_throughput_failure(self):
        """Test when throughput fails."""
        criteria = SuccessCriteria(min_throughput_per_second=10.0)
        validator = SuccessCriteriaValidator(criteria)

        result = validator.validate(throughput_per_second=8.0)

        assert result.passed is False
        assert len(result.failures) == 1
        assert result.failures[0].criterion == "Min Throughput"
        assert "8.00" in result.failures[0].actual
        assert "10.0" in result.failures[0].expected

    def test_multiple_failures(self):
        """Test when multiple criteria fail."""
        criteria = SuccessCriteria(
            min_success_rate=0.90,
            max_p95_latency_seconds=10.0,
            max_error_rate=0.05,
            min_throughput_per_second=10.0,
        )
        validator = SuccessCriteriaValidator(criteria)

        result = validator.validate(
            success_rate=0.85,  # Too low
            p95_latency_seconds=15.0,  # Too high
            error_rate=0.03,  # OK
            throughput_per_second=8.0,  # Too low
        )

        assert result.passed is False
        assert len(result.failures) == 3
        assert result.total_checks == 4
        assert result.success_rate == 0.25  # 1/4 passed

        # Check all expected failures are present
        criteria_names = [f.criterion for f in result.failures]
        assert "Min Success Rate" in criteria_names
        assert "Max P95 Latency" in criteria_names
        assert "Min Throughput" in criteria_names

    def test_partial_criteria_pass(self):
        """Test with only some criteria defined."""
        # Only check success rate and latency, ignore others
        criteria = SuccessCriteria(
            min_success_rate=0.90,
            max_p95_latency_seconds=10.0,
        )
        validator = SuccessCriteriaValidator(criteria)

        result = validator.validate(
            success_rate=0.95,
            p95_latency_seconds=8.0,
            error_rate=0.50,  # High but not checked
            throughput_per_second=0.1,  # Low but not checked
        )

        assert result.passed is True
        assert len(result.failures) == 0
        assert result.total_checks == 2

    def test_missing_result_values(self):
        """Test when some result values are missing."""
        criteria = SuccessCriteria(
            min_success_rate=0.90,
            max_p95_latency_seconds=10.0,
        )
        validator = SuccessCriteriaValidator(criteria)

        # Only provide success_rate, not latency
        result = validator.validate(success_rate=0.95)

        # Should only check success_rate since latency is None
        assert result.passed is True
        assert len(result.failures) == 0
        assert result.total_checks == 1

    def test_validate_from_dict(self):
        """Test validation from dictionary."""
        criteria = SuccessCriteria(
            min_success_rate=0.90,
            max_p95_latency_seconds=10.0,
            max_error_rate=0.10,
            min_throughput_per_second=5.0,
        )
        validator = SuccessCriteriaValidator(criteria)

        results = {
            "success_rate": 0.95,
            "p95_latency_seconds": 8.0,
            "error_rate": 0.05,
            "throughput_per_second": 6.0,
        }

        result = validator.validate_from_dict(results)

        assert result.passed is True
        assert len(result.failures) == 0
        assert result.total_checks == 4

    def test_validate_from_dict_with_failures(self):
        """Test validation from dictionary with failures."""
        criteria = SuccessCriteria(
            min_success_rate=0.90,
            min_throughput_per_second=10.0,
        )
        validator = SuccessCriteriaValidator(criteria)

        results = {
            "success_rate": 0.85,
            "throughput_per_second": 8.0,
        }

        result = validator.validate_from_dict(results)

        assert result.passed is False
        assert len(result.failures) == 2

    def test_edge_case_exact_threshold(self):
        """Test when value exactly matches threshold."""
        criteria = SuccessCriteria(
            min_success_rate=0.90,
            max_p95_latency_seconds=10.0,
        )
        validator = SuccessCriteriaValidator(criteria)

        result = validator.validate(success_rate=0.90, p95_latency_seconds=10.0)

        # Exactly meeting threshold should pass
        assert result.passed is True
        assert len(result.failures) == 0

    def test_edge_case_just_below_threshold(self):
        """Test when value is just below min threshold."""
        criteria = SuccessCriteria(min_success_rate=0.90)
        validator = SuccessCriteriaValidator(criteria)

        result = validator.validate(success_rate=0.8999)

        assert result.passed is False
        assert len(result.failures) == 1

    def test_edge_case_just_above_threshold(self):
        """Test when value is just above max threshold."""
        criteria = SuccessCriteria(max_p95_latency_seconds=10.0)
        validator = SuccessCriteriaValidator(criteria)

        result = validator.validate(p95_latency_seconds=10.001)

        assert result.passed is False
        assert len(result.failures) == 1

    def test_no_criteria_defined(self):
        """Test with no criteria defined (all None)."""
        criteria = SuccessCriteria()
        validator = SuccessCriteriaValidator(criteria)

        result = validator.validate(
            success_rate=0.50,
            p95_latency_seconds=100.0,
            error_rate=0.50,
            throughput_per_second=0.1,
        )

        # No criteria to check, should pass
        assert result.passed is True
        assert len(result.failures) == 0
        assert result.total_checks == 0
