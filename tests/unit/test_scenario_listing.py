"""Tests for scenario listing with filtering and search."""


import pytest

from cow_performance.cli.commands.scenarios import (
    ScenarioConfig,
    list_scenarios_command,
    save_scenario_to_yaml,
)


@pytest.fixture
def scenarios_dir(tmp_path):
    """Create a temporary scenarios directory with test scenarios."""
    scenarios = tmp_path / "scenarios"
    scenarios.mkdir()
    return scenarios


@pytest.fixture
def sample_scenarios(scenarios_dir):
    """Create sample scenario files for testing."""
    # Regression test scenario
    regression = ScenarioConfig(
        name="regression-test",
        description="Fast CI/CD regression test",
        version="1.0",
        tags=["regression", "ci-cd", "short"],
        num_traders=10,
        duration=120,
        trading_pattern="constant_rate",
        base_rate=300.0,
        market_order_ratio=0.5,
        limit_order_ratio=0.5,
    )
    save_scenario_to_yaml(regression, scenarios_dir / "regression-test.yml")

    # Stress test scenario
    stress = ScenarioConfig(
        name="stress-test",
        description="High frequency stress test",
        version="1.0",
        tags=["stress", "edge-case", "short"],
        num_traders=100,
        duration=180,
        trading_pattern="constant_rate",
        base_rate=6000.0,
        market_order_ratio=0.5,
        limit_order_ratio=0.5,
    )
    save_scenario_to_yaml(stress, scenarios_dir / "stress-test.yml")

    # Sustained load scenario
    sustained = ScenarioConfig(
        name="sustained-load",
        description="Long-running stability test",
        version="1.0",
        tags=["stability", "long", "sustained"],
        num_traders=25,
        duration=1800,
        trading_pattern="constant_rate",
        base_rate=600.0,
        market_order_ratio=0.5,
        limit_order_ratio=0.5,
    )
    save_scenario_to_yaml(sustained, scenarios_dir / "sustained-load.yml")

    # Baseline scenario (no tags)
    baseline = ScenarioConfig(
        name="baseline",
        description="Standard baseline test",
        version="1.0",
        tags=[],
        num_traders=10,
        duration=60,
        trading_pattern="constant_rate",
        base_rate=300.0,
        market_order_ratio=0.5,
        limit_order_ratio=0.5,
    )
    save_scenario_to_yaml(baseline, scenarios_dir / "baseline.yml")

    return scenarios_dir


class TestScenarioListing:
    """Test scenario listing functionality."""

    def test_list_all_scenarios(self, sample_scenarios, capsys):
        """Test listing all scenarios without filters."""
        list_scenarios_command(scenarios_dir=sample_scenarios)
        captured = capsys.readouterr()

        # Should show all 4 scenarios (check for partial matches due to Rich text wrapping)
        assert "regression" in captured.out
        assert "stress" in captured.out
        assert "sustained" in captured.out
        assert "baseline" in captured.out

    def test_filter_by_single_tag(self, sample_scenarios, capsys):
        """Test filtering by a single tag."""
        list_scenarios_command(scenarios_dir=sample_scenarios, tags=["short"])
        captured = capsys.readouterr()

        # Should show scenarios with "short" tag
        assert "regression" in captured.out
        assert "stress" in captured.out

        # Should not show scenarios without "short" tag
        assert "sustained" not in captured.out
        assert "baseline" not in captured.out

    def test_filter_by_multiple_tags(self, sample_scenarios, capsys):
        """Test filtering by multiple tags (must match all)."""
        list_scenarios_command(scenarios_dir=sample_scenarios, tags=["short", "regression"])
        captured = capsys.readouterr()

        # Should only show regression-test (has both tags)
        assert "regression" in captured.out

        # Should not show others
        assert "stress" not in captured.out
        assert "sustained" not in captured.out
        assert "baseline" not in captured.out

    def test_filter_by_search_name(self, sample_scenarios, capsys):
        """Test searching by scenario name."""
        list_scenarios_command(scenarios_dir=sample_scenarios, search="stress")
        captured = capsys.readouterr()

        # Should show stress-test
        assert "stress-test" in captured.out

        # Should not show others
        assert "regression-test" not in captured.out
        assert "sustained-load" not in captured.out

    def test_filter_by_search_description(self, sample_scenarios, capsys):
        """Test searching by scenario description."""
        list_scenarios_command(scenarios_dir=sample_scenarios, search="stability")
        captured = capsys.readouterr()

        # Should show sustained-load (description contains "stability")
        assert "sustained-load" in captured.out

        # Should not show others
        assert "regression-test" not in captured.out
        assert "stress-test" not in captured.out

    def test_filter_by_tag_and_search(self, sample_scenarios, capsys):
        """Test combining tag filter and search."""
        list_scenarios_command(scenarios_dir=sample_scenarios, tags=["short"], search="stress")
        captured = capsys.readouterr()

        # Should show stress-test (has "short" tag and "stress" in name)
        assert "stress-test" in captured.out

        # Should not show others
        assert "regression-test" not in captured.out
        assert "sustained-load" not in captured.out

    def test_no_matching_scenarios(self, sample_scenarios, capsys):
        """Test when no scenarios match the filters."""
        list_scenarios_command(scenarios_dir=sample_scenarios, tags=["nonexistent"])
        captured = capsys.readouterr()

        # Should show "no scenarios match" message
        assert "No scenarios match" in captured.out

    def test_simple_view(self, sample_scenarios, capsys):
        """Test simple view without metadata."""
        list_scenarios_command(scenarios_dir=sample_scenarios, show_metadata=False)
        captured = capsys.readouterr()

        # Should show all scenarios
        assert "regression-test" in captured.out
        assert "stress-test" in captured.out

        # Simple view should show "Traders" and "Pattern" columns
        assert "Traders" in captured.out
        assert "Pattern" in captured.out

    def test_metadata_view(self, sample_scenarios, capsys):
        """Test metadata view with tags and resources."""
        list_scenarios_command(scenarios_dir=sample_scenarios, show_metadata=True)
        captured = capsys.readouterr()

        # Should show all scenarios
        assert "regression" in captured.out

        # Metadata view should show "Tags" column
        assert "Tags" in captured.out
        # Metadata view should not show "Traders" column (that's simple view)
        # Note: "Pattern" doesn't appear in either view in the table header

    def test_subdirectory_scenarios(self, tmp_path, capsys):
        """Test finding scenarios in subdirectories."""
        # Create scenarios in nested directories
        scenarios_dir = tmp_path / "scenarios"
        enhanced_dir = scenarios_dir / "enhanced"
        enhanced_dir.mkdir(parents=True)

        scenario = ScenarioConfig(
            name="nested-scenario",
            description="Scenario in subdirectory",
            tags=["nested"],
            num_traders=10,
            duration=60,
            trading_pattern="constant_rate",
            base_rate=300.0,
            market_order_ratio=1.0,
            limit_order_ratio=0.0,
        )
        save_scenario_to_yaml(scenario, enhanced_dir / "nested.yml")

        list_scenarios_command(scenarios_dir=scenarios_dir)
        captured = capsys.readouterr()

        # Should find scenario in subdirectory
        assert "nested-scenario" in captured.out
        assert "enhanced/nested.yml" in captured.out or "enhanced\\nested.yml" in captured.out

    def test_invalid_scenario_handling(self, scenarios_dir, capsys):
        """Test handling of invalid scenario files."""
        # Create an invalid scenario file
        invalid_file = scenarios_dir / "invalid.yml"
        with open(invalid_file, "w") as f:
            f.write("name: test\n# Missing required fields\n")

        list_scenarios_command(scenarios_dir=scenarios_dir)
        captured = capsys.readouterr()

        # Should show error table for invalid scenarios
        # The error table has "Errors" as title
        assert "Errors" in captured.out or "invalid.yml" in captured.out

    def test_empty_directory(self, tmp_path, capsys):
        """Test listing scenarios in empty directory."""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()

        list_scenarios_command(scenarios_dir=empty_dir)
        captured = capsys.readouterr()

        # Should show "no scenario files found" message
        assert "No scenario files found" in captured.out

    def test_nonexistent_directory(self, tmp_path, capsys):
        """Test listing scenarios when directory doesn't exist."""
        nonexistent = tmp_path / "nonexistent"

        list_scenarios_command(scenarios_dir=nonexistent)
        captured = capsys.readouterr()

        # Should show helpful message about creating scenarios
        assert "No scenarios directory found" in captured.out
        assert "Create scenarios with" in captured.out


class TestTagFiltering:
    """Test tag filtering logic."""

    def test_case_sensitive_tag_matching(self, sample_scenarios, capsys):
        """Test that tag matching is case-sensitive."""
        list_scenarios_command(scenarios_dir=sample_scenarios, tags=["Short"])
        captured = capsys.readouterr()

        # Should not match "short" (case mismatch)
        assert "No scenarios match" in captured.out

    def test_multiple_tags_must_all_match(self, sample_scenarios, capsys):
        """Test that multiple tags require ALL to match (AND logic)."""
        list_scenarios_command(
            scenarios_dir=sample_scenarios, tags=["short", "regression", "nonexistent"]
        )
        captured = capsys.readouterr()

        # Should not match (nonexistent tag)
        assert "No scenarios match" in captured.out

    def test_tag_display_truncation(self, scenarios_dir, capsys):
        """Test that long tag lists are truncated in display."""
        # Create scenario with many tags
        many_tags = ScenarioConfig(
            name="many-tags-scenario",
            description="Scenario with many tags",
            tags=["tag1", "tag2", "tag3", "tag4", "tag5"],
            num_traders=10,
            duration=60,
            trading_pattern="constant_rate",
            base_rate=300.0,
            market_order_ratio=1.0,
            limit_order_ratio=0.0,
        )
        save_scenario_to_yaml(many_tags, scenarios_dir / "many-tags.yml")

        list_scenarios_command(scenarios_dir=scenarios_dir, show_metadata=True)
        captured = capsys.readouterr()

        # Should show first 3 tags and indicate more
        assert "tag1" in captured.out
        assert "+2" in captured.out  # Indicating 2 more tags


class TestSearchFunctionality:
    """Test search functionality."""

    def test_case_insensitive_search(self, sample_scenarios, capsys):
        """Test that search is case-insensitive."""
        list_scenarios_command(scenarios_dir=sample_scenarios, search="STRESS")
        captured = capsys.readouterr()

        # Should match "stress-test" despite case difference
        assert "stress-test" in captured.out

    def test_partial_match_in_name(self, sample_scenarios, capsys):
        """Test partial matching in scenario name."""
        list_scenarios_command(scenarios_dir=sample_scenarios, search="load")
        captured = capsys.readouterr()

        # Should match "sustained-load"
        assert "sustained-load" in captured.out

    def test_partial_match_in_description(self, sample_scenarios, capsys):
        """Test partial matching in scenario description."""
        list_scenarios_command(scenarios_dir=sample_scenarios, search="fast")
        captured = capsys.readouterr()

        # Should match regression-test (description contains "Fast")
        assert "regression" in captured.out

    def test_search_no_matches(self, sample_scenarios, capsys):
        """Test search with no matches."""
        list_scenarios_command(scenarios_dir=sample_scenarios, search="nonexistent-term")
        captured = capsys.readouterr()

        # Should show "no scenarios match" message
        assert "No scenarios match" in captured.out
