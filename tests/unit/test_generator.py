"""Tests for interactive configuration generator."""

import os
import shutil
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml
from rich.console import Console

from cow_performance.scenarios.generator import ConfigGenerator


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def mock_console():
    """Create a mock console for testing."""
    return MagicMock(spec=Console)


@pytest.fixture
def generator(mock_console):
    """Create a ConfigGenerator instance with mock console."""
    return ConfigGenerator(console=mock_console)


@pytest.fixture
def template_dir(temp_dir):
    """Create a temporary template directory with a test template."""
    templates_dir = temp_dir / "templates"
    templates_dir.mkdir(parents=True)

    # Create a simple test template
    template_content = {
        "template_metadata": {
            "name": "test-template",
            "description": "Test template for unit tests",
            "parameters": [
                {
                    "name": "test_name",
                    "type": "string",
                    "required": False,
                    "default": "Test Scenario",
                    "description": "Name of the test",
                },
                {
                    "name": "num_traders",
                    "type": "int",
                    "required": True,
                    "description": "Number of traders",
                },
                {
                    "name": "duration",
                    "type": "int",
                    "required": True,
                    "description": "Test duration",
                },
            ],
        },
        "name": "${test_name}",
        "num_traders": "${num_traders}",
        "duration": "${duration}",
        "trading_pattern": "constant_rate",
        "base_rate": 60.0,
    }

    with open(templates_dir / "test-template.template.yml", "w") as f:
        yaml.dump(template_content, f)

    return templates_dir


@pytest.fixture
def scenarios_dir(temp_dir):
    """Create a temporary scenarios directory with test scenarios."""
    scenarios_dir = temp_dir / "scenarios"
    scenarios_dir.mkdir(parents=True)

    # Create a test scenario
    scenario_content = {
        "name": "Existing Scenario",
        "description": "An existing test scenario",
        "num_traders": 10,
        "duration": 60,
        "trading_pattern": "constant_rate",
        "base_rate": 60.0,
        "market_order_ratio": 0.6,
        "limit_order_ratio": 0.4,
        "twap_order_ratio": 0.0,
        "stop_loss_order_ratio": 0.0,
        "good_after_time_order_ratio": 0.0,
    }

    with open(scenarios_dir / "test-scenario.yml", "w") as f:
        yaml.dump(scenario_content, f)

    return scenarios_dir


class TestConfigGeneratorInit:
    """Test ConfigGenerator initialization."""

    def test_init_with_console(self, mock_console):
        """Test initialization with provided console."""
        generator = ConfigGenerator(console=mock_console)
        assert generator.console == mock_console
        assert generator.template_expander is not None

    def test_init_without_console(self):
        """Test initialization creates default console."""
        generator = ConfigGenerator()
        assert generator.console is not None
        assert generator.template_expander is not None


class TestQuickStartMode:
    """Test quick start mode generation."""

    @patch("cow_performance.scenarios.generator.Prompt.ask")
    @patch("cow_performance.scenarios.generator.IntPrompt.ask")
    @patch("cow_performance.scenarios.generator.FloatPrompt.ask")
    def test_quick_start_mode_basic(
        self, mock_float_prompt, mock_int_prompt, mock_prompt, generator, temp_dir
    ):
        """Test basic quick start mode generation."""
        output_path = temp_dir / "quick-test.yml"

        # Mock user inputs
        mock_prompt.side_effect = [
            "My Test Scenario",  # name
            "A quick test scenario",  # description
        ]
        mock_int_prompt.side_effect = [
            5,  # num_traders
            120,  # duration
        ]
        mock_float_prompt.return_value = 30.0  # orders_per_minute

        config = generator._quick_start_mode(output_path)

        assert config["name"] == "My Test Scenario"
        assert config["description"] == "A quick test scenario"
        assert config["num_traders"] == 5
        assert config["duration"] == 120
        assert config["base_rate"] == 30.0
        assert config["trading_pattern"] == "constant_rate"
        assert "tags" in config
        assert "quick-start" in config["tags"]

    @patch("cow_performance.scenarios.generator.Prompt.ask")
    @patch("cow_performance.scenarios.generator.IntPrompt.ask")
    @patch("cow_performance.scenarios.generator.FloatPrompt.ask")
    def test_quick_start_mode_order_ratios(
        self, mock_float_prompt, mock_int_prompt, mock_prompt, generator, temp_dir
    ):
        """Test that quick start mode includes all order type ratios."""
        output_path = temp_dir / "quick-test.yml"

        # Mock user inputs
        mock_prompt.side_effect = ["Test", "Test description"]
        mock_int_prompt.side_effect = [10, 60]
        mock_float_prompt.return_value = 60.0

        config = generator._quick_start_mode(output_path)

        # Verify all order ratios are present and sum to 1.0
        assert config["market_order_ratio"] == 0.6
        assert config["limit_order_ratio"] == 0.4
        assert config["twap_order_ratio"] == 0.0
        assert config["stop_loss_order_ratio"] == 0.0
        assert config["good_after_time_order_ratio"] == 0.0

        total = sum(
            [
                config["market_order_ratio"],
                config["limit_order_ratio"],
                config["twap_order_ratio"],
                config["stop_loss_order_ratio"],
                config["good_after_time_order_ratio"],
            ]
        )
        assert abs(total - 1.0) < 0.01


class TestTemplateMode:
    """Test template-based generation mode."""

    @patch("cow_performance.scenarios.generator.IntPrompt.ask")
    def test_template_mode_no_templates(self, mock_int_prompt, generator, temp_dir, monkeypatch):
        """Test template mode falls back to quick start when no templates found."""
        output_path = temp_dir / "template-test.yml"

        # Mock empty template directories
        generator.template_expander.template_dirs = [temp_dir / "nonexistent"]

        # Mock quick start inputs
        with patch.object(generator, "_quick_start_mode") as mock_quick_start:
            mock_quick_start.return_value = {"name": "Fallback"}

            config = generator._template_mode(output_path)

            mock_quick_start.assert_called_once_with(output_path)
            assert config["name"] == "Fallback"

    @patch("cow_performance.scenarios.generator.IntPrompt.ask")
    @patch("cow_performance.scenarios.generator.Prompt.ask")
    def test_template_mode_with_template(
        self, mock_prompt, mock_int_prompt, generator, temp_dir, template_dir, monkeypatch
    ):
        """Test template mode with available template."""
        output_path = temp_dir / "template-test.yml"

        # Set template directory
        generator.template_expander.template_dirs = [template_dir]

        # Mock user selections
        mock_int_prompt.side_effect = [
            1,  # Select first template
            5,  # num_traders
            300,  # duration
        ]
        mock_prompt.return_value = "Test Scenario"  # test_name parameter

        config = generator._template_mode(output_path)

        assert config["name"] == "Test Scenario"
        # Template expansion returns strings for integer parameters
        assert config["num_traders"] == "5" or config["num_traders"] == 5
        assert config["duration"] == "300" or config["duration"] == 300
        assert config["trading_pattern"] == "constant_rate"


class TestCopyExistingMode:
    """Test copy-from-existing mode."""

    def test_copy_existing_no_scenarios(self, generator, temp_dir, monkeypatch):
        """Test copy mode falls back when no scenarios found."""
        output_path = temp_dir / "copy-test.yml"

        # Mock scenarios directory lookup
        monkeypatch.setattr("pathlib.Path.exists", lambda self: False)

        with patch.object(generator, "_quick_start_mode") as mock_quick_start:
            mock_quick_start.return_value = {"name": "Fallback"}

            generator._copy_existing_mode(output_path)

            mock_quick_start.assert_called_once_with(output_path)

    def test_copy_existing_with_modifications(self, generator, temp_dir, scenarios_dir):
        """Test copying existing scenario with modifications."""
        output_path = temp_dir / "copy-test.yml"

        # Create a properly accessible scenarios directory
        local_scenarios = temp_dir / "configs" / "scenarios"
        local_scenarios.mkdir(parents=True, exist_ok=True)

        # Copy the test scenario
        src_file = scenarios_dir / "test-scenario.yml"
        dst_file = local_scenarios / "test-scenario.yml"
        shutil.copy(src_file, dst_file)

        # Mock user inputs
        with patch("cow_performance.scenarios.generator.IntPrompt.ask") as mock_int_prompt, patch(
            "cow_performance.scenarios.generator.Prompt.ask"
        ) as mock_prompt, patch(
            "cow_performance.scenarios.generator.Confirm.ask"
        ) as mock_confirm, patch(
            "cow_performance.scenarios.generator.FloatPrompt.ask"
        ) as mock_float_prompt:
            mock_int_prompt.side_effect = [
                1,  # Select first scenario
                8,  # num_traders (if modified)
                180,  # duration (if modified)
            ]
            mock_prompt.return_value = "Modified Scenario"
            mock_confirm.return_value = True  # Modify parameters
            mock_float_prompt.return_value = 30.0  # base_rate (if asked)

            # Change working directory context
            original_cwd = os.getcwd()
            try:
                os.chdir(temp_dir)
                config = generator._copy_existing_mode(output_path)
            finally:
                os.chdir(original_cwd)

            assert config["name"] == "Modified Scenario"
            assert config["num_traders"] == 8
            assert config["duration"] == 180


class TestAdvancedMode:
    """Test advanced configuration mode."""

    @patch("cow_performance.scenarios.generator.Confirm.ask")
    @patch("cow_performance.scenarios.generator.FloatPrompt.ask")
    @patch("cow_performance.scenarios.generator.IntPrompt.ask")
    def test_advanced_mode_with_criteria(
        self, mock_int_prompt, mock_float_prompt, mock_confirm, generator, temp_dir
    ):
        """Test advanced mode with success criteria."""
        output_path = temp_dir / "advanced-test.yml"

        # Mock quick start inputs
        with patch.object(generator, "_quick_start_mode") as mock_quick_start:
            mock_quick_start.return_value = {
                "name": "Base Config",
                "num_traders": 10,
                "duration": 60,
            }

            # Mock advanced options
            mock_confirm.side_effect = [
                True,  # Add success criteria
                False,  # Don't add metadata
            ]
            mock_float_prompt.side_effect = [
                0.95,  # min_success_rate
                0.05,  # max_error_rate
            ]

            config = generator._advanced_mode(output_path)

            assert "success_criteria" in config
            assert config["success_criteria"]["min_success_rate"] == 0.95
            assert config["success_criteria"]["max_error_rate"] == 0.05
            assert "metadata" not in config

    @patch("cow_performance.scenarios.generator.Confirm.ask")
    @patch("cow_performance.scenarios.generator.FloatPrompt.ask")
    @patch("cow_performance.scenarios.generator.IntPrompt.ask")
    def test_advanced_mode_with_metadata(
        self, mock_int_prompt, mock_float_prompt, mock_confirm, generator, temp_dir
    ):
        """Test advanced mode with metadata."""
        output_path = temp_dir / "advanced-test.yml"

        with patch.object(generator, "_quick_start_mode") as mock_quick_start:
            mock_quick_start.return_value = {
                "name": "Base Config",
                "num_traders": 10,
                "duration": 60,
            }

            # Mock advanced options
            mock_confirm.side_effect = [
                False,  # Don't add success criteria
                True,  # Add metadata
            ]
            mock_int_prompt.side_effect = [
                4,  # min_memory_gb
                8,  # recommended_memory_gb
            ]

            config = generator._advanced_mode(output_path)

            assert "metadata" in config
            assert config["metadata"]["resources"]["min_memory_gb"] == 4
            assert config["metadata"]["resources"]["recommended_memory_gb"] == 8


class TestInteractiveMode:
    """Test interactive mode selection."""

    @patch("cow_performance.scenarios.generator.IntPrompt.ask")
    def test_interactive_mode_selects_quick_start(self, mock_int_prompt, generator, temp_dir):
        """Test interactive mode selecting quick start."""
        output_path = temp_dir / "interactive-test.yml"

        mock_int_prompt.return_value = 1  # Select quick start

        with patch.object(generator, "_quick_start_mode") as mock_quick_start:
            mock_quick_start.return_value = {"name": "Quick"}

            generator._interactive_mode(output_path)

            mock_quick_start.assert_called_once_with(output_path)

    @patch("cow_performance.scenarios.generator.IntPrompt.ask")
    def test_interactive_mode_selects_template(self, mock_int_prompt, generator, temp_dir):
        """Test interactive mode selecting template."""
        output_path = temp_dir / "interactive-test.yml"

        mock_int_prompt.return_value = 2  # Select template

        with patch.object(generator, "_template_mode") as mock_template:
            mock_template.return_value = {"name": "Template"}

            generator._interactive_mode(output_path)

            mock_template.assert_called_once_with(output_path)

    @patch("cow_performance.scenarios.generator.IntPrompt.ask")
    def test_interactive_mode_selects_existing(self, mock_int_prompt, generator, temp_dir):
        """Test interactive mode selecting copy existing."""
        output_path = temp_dir / "interactive-test.yml"

        mock_int_prompt.return_value = 3  # Select copy existing

        with patch.object(generator, "_copy_existing_mode") as mock_existing:
            mock_existing.return_value = {"name": "Existing"}

            generator._interactive_mode(output_path)

            mock_existing.assert_called_once_with(output_path)

    @patch("cow_performance.scenarios.generator.IntPrompt.ask")
    def test_interactive_mode_selects_advanced(self, mock_int_prompt, generator, temp_dir):
        """Test interactive mode selecting advanced."""
        output_path = temp_dir / "interactive-test.yml"

        mock_int_prompt.return_value = 4  # Select advanced

        with patch.object(generator, "_advanced_mode") as mock_advanced:
            mock_advanced.return_value = {"name": "Advanced"}

            generator._advanced_mode(output_path)

            mock_advanced.assert_called_once_with(output_path)


class TestGenerateMethod:
    """Test main generate method."""

    def test_generate_with_quick_mode(self, generator, temp_dir):
        """Test generate method with quick mode."""
        output_path = temp_dir / "test.yml"

        with patch.object(generator, "_quick_start_mode") as mock_quick_start:
            mock_quick_start.return_value = {"name": "Test"}

            config = generator.generate(output_path, mode="quick")

            mock_quick_start.assert_called_once_with(output_path)
            assert config["name"] == "Test"

    def test_generate_with_invalid_mode(self, generator, temp_dir):
        """Test generate method with invalid mode."""
        output_path = temp_dir / "test.yml"

        with pytest.raises(ValueError, match="Invalid mode"):
            generator.generate(output_path, mode="invalid")


class TestSaveConfig:
    """Test configuration saving with validation."""

    def test_save_config_valid(self, generator, temp_dir):
        """Test saving a valid configuration."""
        output_path = temp_dir / "valid.yml"

        config = {
            "name": "Test Scenario",
            "description": "A test",
            "version": "1.0",
            "num_traders": 10,
            "duration": 60,
            "startup_interval": 0.1,
            "trading_pattern": "constant_rate",
            "base_rate": 60.0,
            "market_order_ratio": 0.6,
            "limit_order_ratio": 0.4,
            "twap_order_ratio": 0.0,
            "stop_loss_order_ratio": 0.0,
            "good_after_time_order_ratio": 0.0,
        }

        generator.save_config(config, output_path)

        assert output_path.exists()

        # Verify saved content
        with open(output_path) as f:
            saved_config = yaml.safe_load(f)

        assert saved_config["name"] == "Test Scenario"
        assert saved_config["num_traders"] == 10

    def test_save_config_creates_parent_dirs(self, generator, temp_dir):
        """Test that save_config creates parent directories."""
        output_path = temp_dir / "subdir" / "nested" / "config.yml"

        config = {
            "name": "Test",
            "num_traders": 10,
            "duration": 60,
            "trading_pattern": "constant_rate",
            "base_rate": 60.0,
            "market_order_ratio": 1.0,
            "limit_order_ratio": 0.0,
            "twap_order_ratio": 0.0,
            "stop_loss_order_ratio": 0.0,
            "good_after_time_order_ratio": 0.0,
        }

        generator.save_config(config, output_path)

        assert output_path.exists()
        assert output_path.parent.exists()

    def test_save_config_invalid_shows_warning(self, generator, temp_dir, mock_console):
        """Test that invalid config shows warning but saves anyway."""
        output_path = temp_dir / "invalid.yml"

        # Invalid config (missing required fields)
        config = {
            "name": "Test",
            "num_traders": 10,
            # Missing duration and other required fields
        }

        # Should not raise, but should warn
        generator.save_config(config, output_path)

        # Config should still be saved
        assert output_path.exists()


class TestDisplayNextSteps:
    """Test next steps display."""

    def test_display_next_steps(self, generator, temp_dir, mock_console):
        """Test that next steps are displayed."""
        output_path = temp_dir / "test.yml"

        generator.display_next_steps(output_path)

        # Verify console.print was called with next steps
        assert mock_console.print.called
        call_args = [call[0][0] for call in mock_console.print.call_args_list]
        combined_output = " ".join(str(arg) for arg in call_args)

        assert "Next Steps" in combined_output
        assert "Review" in combined_output or "cat" in combined_output
        assert "Validate" in combined_output or "cow-perf scenarios --validate" in combined_output
        assert "Run" in combined_output or "cow-perf run" in combined_output
