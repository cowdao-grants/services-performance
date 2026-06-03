"""Unit tests for threshold configuration."""

import textwrap

import pytest

from cow_performance.comparison.models import MetricType, RegressionSeverity
from cow_performance.comparison.thresholds import (
    RELAXED_THRESHOLDS,
    STRICT_THRESHOLDS,
    MetricThresholds,
    RegressionThresholds,
    load_thresholds,
)


class TestMetricThresholds:
    """Tests for MetricThresholds."""

    def test_classify_latency_increase(self) -> None:
        """Test latency increase classification."""
        thresholds = MetricThresholds(minor=0.10, major=0.15, critical=0.30)

        assert thresholds.classify_severity(0.05, MetricType.LATENCY) == RegressionSeverity.NONE
        assert thresholds.classify_severity(0.10, MetricType.LATENCY) == RegressionSeverity.MINOR
        assert thresholds.classify_severity(0.15, MetricType.LATENCY) == RegressionSeverity.MAJOR
        assert thresholds.classify_severity(0.30, MetricType.LATENCY) == RegressionSeverity.CRITICAL

    def test_classify_latency_decrease_no_regression(self) -> None:
        """Test latency decrease is not a regression."""
        thresholds = MetricThresholds(minor=0.10, major=0.15, critical=0.30)

        # Negative change (decrease) should not trigger regression
        assert thresholds.classify_severity(-0.20, MetricType.LATENCY) == RegressionSeverity.NONE

    def test_classify_throughput_decrease(self) -> None:
        """Test throughput decrease classification (inverted)."""
        thresholds = MetricThresholds(minor=0.10, major=0.25, critical=0.50)

        # Negative change = decrease, which is bad for throughput
        assert thresholds.classify_severity(-0.05, MetricType.THROUGHPUT) == RegressionSeverity.NONE
        assert (
            thresholds.classify_severity(-0.10, MetricType.THROUGHPUT) == RegressionSeverity.MINOR
        )
        assert (
            thresholds.classify_severity(-0.25, MetricType.THROUGHPUT) == RegressionSeverity.MAJOR
        )
        assert (
            thresholds.classify_severity(-0.50, MetricType.THROUGHPUT)
            == RegressionSeverity.CRITICAL
        )

    def test_classify_throughput_increase_no_regression(self) -> None:
        """Test throughput increase is not a regression."""
        thresholds = MetricThresholds(minor=0.10, major=0.25, critical=0.50)

        # Positive change (increase) should not trigger regression for throughput
        assert thresholds.classify_severity(0.50, MetricType.THROUGHPUT) == RegressionSeverity.NONE

    def test_classify_resource_increase(self) -> None:
        """Test resource usage increase classification."""
        thresholds = MetricThresholds(minor=0.10, major=0.20, critical=0.50)

        assert thresholds.classify_severity(0.05, MetricType.RESOURCE) == RegressionSeverity.NONE
        assert thresholds.classify_severity(0.15, MetricType.RESOURCE) == RegressionSeverity.MINOR
        assert thresholds.classify_severity(0.25, MetricType.RESOURCE) == RegressionSeverity.MAJOR
        assert (
            thresholds.classify_severity(0.60, MetricType.RESOURCE) == RegressionSeverity.CRITICAL
        )

    def test_classify_error_rate_increase(self) -> None:
        """Test error rate increase classification."""
        thresholds = MetricThresholds(minor=0.01, major=0.02, critical=0.05)

        assert thresholds.classify_severity(0.005, MetricType.ERROR_RATE) == RegressionSeverity.NONE
        assert (
            thresholds.classify_severity(0.015, MetricType.ERROR_RATE) == RegressionSeverity.MINOR
        )
        assert (
            thresholds.classify_severity(0.025, MetricType.ERROR_RATE) == RegressionSeverity.MAJOR
        )
        assert (
            thresholds.classify_severity(0.06, MetricType.ERROR_RATE) == RegressionSeverity.CRITICAL
        )


class TestRegressionThresholds:
    """Tests for RegressionThresholds."""

    def test_default_thresholds(self) -> None:
        """Test default threshold values."""
        thresholds = RegressionThresholds()

        assert thresholds.latency.minor == 0.10
        assert thresholds.latency.major == 0.15
        assert thresholds.latency.critical == 0.30

        assert thresholds.throughput.minor == 0.10
        assert thresholds.throughput.major == 0.25
        assert thresholds.throughput.critical == 0.50

        assert thresholds.significance_level == 0.05
        assert thresholds.min_effect_size == 0.2

    def test_get_thresholds_for_type(self) -> None:
        """Test getting thresholds for specific metric types."""
        thresholds = RegressionThresholds()

        latency_t = thresholds.get_thresholds_for_type(MetricType.LATENCY)
        assert latency_t == thresholds.latency

        throughput_t = thresholds.get_thresholds_for_type(MetricType.THROUGHPUT)
        assert throughput_t == thresholds.throughput

    def test_classify_severity(self) -> None:
        """Test severity classification through RegressionThresholds."""
        thresholds = RegressionThresholds()

        # Latency increase
        severity = thresholds.classify_severity(0.20, MetricType.LATENCY)
        assert severity == RegressionSeverity.MAJOR

        # Throughput decrease
        severity = thresholds.classify_severity(-0.30, MetricType.THROUGHPUT)
        assert severity == RegressionSeverity.MAJOR

    def test_strict_thresholds(self) -> None:
        """Test strict threshold profile."""
        assert STRICT_THRESHOLDS.latency.minor == 0.05
        assert STRICT_THRESHOLDS.latency.critical == 0.20
        assert STRICT_THRESHOLDS.significance_level == 0.01

    def test_relaxed_thresholds(self) -> None:
        """Test relaxed threshold profile."""
        assert RELAXED_THRESHOLDS.latency.minor == 0.20
        assert RELAXED_THRESHOLDS.latency.critical == 0.50
        assert RELAXED_THRESHOLDS.significance_level == 0.10

    def test_serialization_roundtrip(self) -> None:
        """Test thresholds can be serialized and deserialized."""
        thresholds = RegressionThresholds()
        data = thresholds.to_dict()
        restored = RegressionThresholds.from_dict(data)

        assert restored.latency.minor == thresholds.latency.minor
        assert restored.latency.major == thresholds.latency.major
        assert restored.latency.critical == thresholds.latency.critical
        assert restored.throughput.minor == thresholds.throughput.minor
        assert restored.significance_level == thresholds.significance_level
        assert restored.min_effect_size == thresholds.min_effect_size

    def test_serialization_custom_thresholds(self) -> None:
        """Test serialization with custom thresholds."""
        thresholds = RegressionThresholds(
            latency=MetricThresholds(minor=0.05, major=0.10, critical=0.20),
            significance_level=0.01,
        )

        data = thresholds.to_dict()
        restored = RegressionThresholds.from_dict(data)

        assert restored.latency.minor == 0.05
        assert restored.significance_level == 0.01

    def test_from_dict_with_partial_data(self) -> None:
        """Test deserialization with partial data uses defaults."""
        data = {
            "significance_level": 0.01,
        }

        restored = RegressionThresholds.from_dict(data)

        assert restored.significance_level == 0.01
        # Latency should use defaults from MetricThresholds
        assert restored.latency.minor == 0.10

    def test_rate_significance_default(self) -> None:
        """rate_significance defaults to 0.01."""
        thresholds = RegressionThresholds()
        assert thresholds.rate_significance == 0.01

    def test_rate_significance_in_profiles(self) -> None:
        """Pre-configured profiles carry distinct rate_significance values."""
        assert STRICT_THRESHOLDS.rate_significance == 0.005
        assert RELAXED_THRESHOLDS.rate_significance == 0.02

    def test_to_dict_uses_statistics_section(self) -> None:
        """to_dict() nests significance fields under 'statistics'."""
        data = RegressionThresholds().to_dict()
        assert "statistics" in data
        stats = data["statistics"]
        assert stats["significance_level"] == 0.05
        assert stats["min_effect_size"] == 0.2
        assert stats["rate_significance"] == 0.01

    def test_serialization_roundtrip_includes_rate_significance(self) -> None:
        """Roundtrip via to_dict/from_dict preserves rate_significance."""
        original = RegressionThresholds(rate_significance=0.007)
        restored = RegressionThresholds.from_dict(original.to_dict())
        assert restored.rate_significance == 0.007

    def test_from_dict_flat_legacy_significance_keys(self) -> None:
        """from_dict() accepts the old flat-key format for backward compat."""
        data = {
            "significance_level": 0.01,
            "min_effect_size": 0.3,
            "rate_significance": 0.005,
        }
        restored = RegressionThresholds.from_dict(data)
        assert restored.significance_level == 0.01
        assert restored.min_effect_size == 0.3
        assert restored.rate_significance == 0.005

    def test_from_dict_nested_statistics_takes_priority_over_flat(self) -> None:
        """Nested [statistics] wins over flat key when both present."""
        data = {
            "significance_level": 0.99,  # flat (legacy) — should be ignored
            "statistics": {"significance_level": 0.01},
        }
        restored = RegressionThresholds.from_dict(data)
        assert restored.significance_level == 0.01


class TestFromToml:
    """Tests for RegressionThresholds.from_toml()."""

    def test_load_valid_toml(self, tmp_path: "pytest.fixture") -> None:
        """from_toml() loads all sections correctly."""
        toml_content = textwrap.dedent(
            """\
            [latency]
            minor = 0.05
            major = 0.10
            critical = 0.20

            [throughput]
            minor = 0.08
            major = 0.20
            critical = 0.40

            [error_rate]
            minor = 0.005
            major = 0.01
            critical = 0.03

            [resource]
            minor = 0.05
            major = 0.15
            critical = 0.35

            [statistics]
            significance_level = 0.01
            min_effect_size = 0.3
            rate_significance = 0.005
        """
        )
        config_file = tmp_path / "thresholds.toml"
        config_file.write_text(toml_content)

        t = RegressionThresholds.from_toml(config_file)

        assert t.latency.minor == 0.05
        assert t.latency.critical == 0.20
        assert t.throughput.major == 0.20
        assert t.error_rate.critical == 0.03
        assert t.resource.minor == 0.05
        assert t.significance_level == 0.01
        assert t.min_effect_size == 0.3
        assert t.rate_significance == 0.005

    def test_load_partial_toml_uses_defaults(self, tmp_path: "pytest.fixture") -> None:
        """Omitted TOML sections fall back to MetricThresholds defaults."""
        config_file = tmp_path / "partial.toml"
        config_file.write_text("[statistics]\nsignificance_level = 0.02\n")

        t = RegressionThresholds.from_toml(config_file)

        assert t.significance_level == 0.02
        assert t.latency.minor == 0.10  # default

    def test_missing_file_raises(self, tmp_path: "pytest.fixture") -> None:
        """from_toml() raises FileNotFoundError for missing file."""
        with pytest.raises(FileNotFoundError, match="Threshold config not found"):
            RegressionThresholds.from_toml(tmp_path / "nonexistent.toml")

    def test_invalid_toml_raises(self, tmp_path: "pytest.fixture") -> None:
        """from_toml() raises ValueError for unparseable content."""
        bad_file = tmp_path / "bad.toml"
        bad_file.write_text("not valid toml = = =")

        with pytest.raises(ValueError, match="Failed to parse threshold config"):
            RegressionThresholds.from_toml(bad_file)

    def test_string_path_accepted(self, tmp_path: "pytest.fixture") -> None:
        """from_toml() accepts a plain string path."""
        config_file = tmp_path / "thresholds.toml"
        config_file.write_text("[latency]\nminor = 0.07\n")

        t = RegressionThresholds.from_toml(str(config_file))
        assert t.latency.minor == 0.07


class TestLoadThresholds:
    """Tests for the load_thresholds() helper."""

    def test_defaults_when_no_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Returns built-in defaults when no env vars are set."""
        monkeypatch.delenv("COW_PERF_THRESHOLD_PROFILE", raising=False)
        monkeypatch.delenv("COW_PERF_THRESHOLD_FILE", raising=False)

        t = load_thresholds()
        assert t.latency.minor == 0.10
        assert t.significance_level == 0.05

    def test_explicit_toml_path(self, tmp_path: pytest.fixture, monkeypatch: pytest.MonkeyPatch) -> None:  # type: ignore[valid-type]
        """Explicit toml_path argument takes highest priority."""
        monkeypatch.setenv("COW_PERF_THRESHOLD_PROFILE", "strict")
        config_file = tmp_path / "custom.toml"
        config_file.write_text("[latency]\nminor = 0.03\n")

        t = load_thresholds(toml_path=config_file)
        assert t.latency.minor == 0.03  # file wins over env profile

    def test_env_file_used_when_no_explicit_path(
        self, tmp_path: pytest.fixture, monkeypatch: pytest.MonkeyPatch  # type: ignore[valid-type]
    ) -> None:
        """COW_PERF_THRESHOLD_FILE is used when no explicit path given."""
        monkeypatch.delenv("COW_PERF_THRESHOLD_PROFILE", raising=False)
        config_file = tmp_path / "env.toml"
        config_file.write_text("[latency]\nminor = 0.04\n")
        monkeypatch.setenv("COW_PERF_THRESHOLD_FILE", str(config_file))

        t = load_thresholds()
        assert t.latency.minor == 0.04

    def test_strict_profile(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """COW_PERF_THRESHOLD_PROFILE=strict returns STRICT_THRESHOLDS."""
        monkeypatch.delenv("COW_PERF_THRESHOLD_FILE", raising=False)
        monkeypatch.setenv("COW_PERF_THRESHOLD_PROFILE", "strict")

        t = load_thresholds()
        assert t.latency.minor == STRICT_THRESHOLDS.latency.minor
        assert t.significance_level == STRICT_THRESHOLDS.significance_level

    def test_relaxed_profile(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """COW_PERF_THRESHOLD_PROFILE=relaxed returns RELAXED_THRESHOLDS."""
        monkeypatch.delenv("COW_PERF_THRESHOLD_FILE", raising=False)
        monkeypatch.setenv("COW_PERF_THRESHOLD_PROFILE", "relaxed")

        t = load_thresholds()
        assert t.latency.minor == RELAXED_THRESHOLDS.latency.minor

    def test_default_profile_explicit(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """COW_PERF_THRESHOLD_PROFILE=default returns built-in defaults."""
        monkeypatch.delenv("COW_PERF_THRESHOLD_FILE", raising=False)
        monkeypatch.setenv("COW_PERF_THRESHOLD_PROFILE", "default")

        t = load_thresholds()
        assert t.latency.minor == 0.10

    def test_profile_case_insensitive(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Profile name matching is case-insensitive."""
        monkeypatch.delenv("COW_PERF_THRESHOLD_FILE", raising=False)
        monkeypatch.setenv("COW_PERF_THRESHOLD_PROFILE", "STRICT")

        t = load_thresholds()
        assert t.latency.minor == STRICT_THRESHOLDS.latency.minor

    def test_unknown_profile_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Unknown profile name raises ValueError with valid options listed."""
        monkeypatch.delenv("COW_PERF_THRESHOLD_FILE", raising=False)
        monkeypatch.setenv("COW_PERF_THRESHOLD_PROFILE", "bogus")

        with pytest.raises(ValueError, match="Unknown threshold profile 'bogus'"):
            load_thresholds()

    def test_env_file_takes_priority_over_profile(
        self, tmp_path: pytest.fixture, monkeypatch: pytest.MonkeyPatch  # type: ignore[valid-type]
    ) -> None:
        """COW_PERF_THRESHOLD_FILE takes priority over COW_PERF_THRESHOLD_PROFILE."""
        config_file = tmp_path / "file.toml"
        config_file.write_text("[latency]\nminor = 0.03\n")
        monkeypatch.setenv("COW_PERF_THRESHOLD_FILE", str(config_file))
        monkeypatch.setenv("COW_PERF_THRESHOLD_PROFILE", "strict")

        t = load_thresholds()
        assert t.latency.minor == 0.03  # file wins

    def test_configs_thresholds_toml_is_valid(self) -> None:
        """The checked-in configs/thresholds.toml parses without error."""
        t = RegressionThresholds.from_toml("configs/thresholds.toml")
        assert t.latency.minor == 0.10
        assert t.rate_significance == 0.01
