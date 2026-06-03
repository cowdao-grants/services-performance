"""Tests for template-based scenario generation."""


import pytest
import yaml

from cow_performance.scenarios.templates import (
    ParameterError,
    TemplateError,
    TemplateExpander,
    TemplateNotFoundError,
    expand_template,
)


class TestTemplateExpander:
    """Test template expansion logic."""

    def test_expand_string_simple(self):
        """Test simple parameter expansion in string."""
        expander = TemplateExpander()

        text = "Test with ${num_traders} traders"
        parameters = {"num_traders": 10}

        result = expander.expand_string(text, parameters)

        assert result == "Test with 10 traders"

    def test_expand_string_multiple_params(self):
        """Test multiple parameters in one string."""
        expander = TemplateExpander()

        text = "Run ${num_traders} traders for ${duration} seconds"
        parameters = {"num_traders": 10, "duration": 60}

        result = expander.expand_string(text, parameters)

        assert result == "Run 10 traders for 60 seconds"

    def test_expand_string_with_default(self):
        """Test parameter with default value."""
        expander = TemplateExpander()

        text = "Rate: ${rate:-60}"
        parameters = {}

        result = expander.expand_string(text, parameters)

        assert result == "Rate: 60"

    def test_expand_string_override_default(self):
        """Test overriding default value."""
        expander = TemplateExpander()

        text = "Rate: ${rate:-60}"
        parameters = {"rate": 100}

        result = expander.expand_string(text, parameters)

        assert result == "Rate: 100"

    def test_expand_string_required_param_missing(self):
        """Test error when required parameter is missing."""
        expander = TemplateExpander()

        text = "Test with ${num_traders} traders"
        parameters = {}

        with pytest.raises(ParameterError) as exc_info:
            expander.expand_string(text, parameters)

        assert "num_traders" in str(exc_info.value)
        assert "not provided" in str(exc_info.value).lower()

    def test_expand_dict_simple(self):
        """Test parameter expansion in dictionary."""
        expander = TemplateExpander()

        config = {"name": "${test_name}", "num_traders": "${num_traders}"}
        parameters = {"test_name": "My Test", "num_traders": 10}

        result = expander.expand_dict(config, parameters)

        assert result == {"name": "My Test", "num_traders": "10"}

    def test_expand_dict_nested(self):
        """Test parameter expansion in nested dictionary."""
        expander = TemplateExpander()

        config = {
            "name": "${test_name}",
            "metadata": {
                "expected_orders": "${expected_orders}",
                "resources": {"min_memory_gb": "${memory}"},
            },
        }
        parameters = {"test_name": "Test", "expected_orders": 100, "memory": 8}

        result = expander.expand_dict(config, parameters)

        assert result == {
            "name": "Test",
            "metadata": {
                "expected_orders": "100",
                "resources": {"min_memory_gb": "8"},
            },
        }

    def test_expand_list(self):
        """Test parameter expansion in list."""
        expander = TemplateExpander()

        items = ["${tag1}", "${tag2}", "fixed"]
        parameters = {"tag1": "load-test", "tag2": "performance"}

        result = expander.expand_list(items, parameters)

        assert result == ["load-test", "performance", "fixed"]

    def test_expand_dict_with_list(self):
        """Test parameter expansion in dict containing lists."""
        expander = TemplateExpander()

        config = {
            "name": "${test_name}",
            "tags": ["${env}", "test"],
        }
        parameters = {"test_name": "My Test", "env": "staging"}

        result = expander.expand_dict(config, parameters)

        assert result == {
            "name": "My Test",
            "tags": ["staging", "test"],
        }

    def test_expand_dict_preserves_types(self):
        """Test that non-string types are preserved."""
        expander = TemplateExpander()

        config = {
            "name": "${test_name}",
            "num_traders": 10,
            "duration": 60,
            "ratio": 0.5,
            "enabled": True,
            "optional": None,
        }
        parameters = {"test_name": "Test"}

        result = expander.expand_dict(config, parameters)

        assert result == {
            "name": "Test",
            "num_traders": 10,
            "duration": 60,
            "ratio": 0.5,
            "enabled": True,
            "optional": None,
        }


class TestTemplateFinding:
    """Test template file finding."""

    def test_find_template_with_template_yml_extension(self, tmp_path):
        """Test finding template with .template.yml extension."""
        template_dir = tmp_path / "templates"
        template_dir.mkdir()

        template_file = template_dir / "test.template.yml"
        template_file.write_text("name: test")

        expander = TemplateExpander(template_dirs=[template_dir])
        found = expander.find_template("test")

        assert found == template_file

    def test_find_template_with_yml_extension(self, tmp_path):
        """Test finding template with .yml extension."""
        template_dir = tmp_path / "templates"
        template_dir.mkdir()

        template_file = template_dir / "test.yml"
        template_file.write_text("name: test")

        expander = TemplateExpander(template_dirs=[template_dir])
        found = expander.find_template("test")

        assert found == template_file

    def test_find_template_prefers_template_yml(self, tmp_path):
        """Test that .template.yml is preferred over .yml."""
        template_dir = tmp_path / "templates"
        template_dir.mkdir()

        template_file1 = template_dir / "test.template.yml"
        template_file1.write_text("name: template")

        template_file2 = template_dir / "test.yml"
        template_file2.write_text("name: regular")

        expander = TemplateExpander(template_dirs=[template_dir])
        found = expander.find_template("test")

        assert found == template_file1

    def test_find_template_not_found(self, tmp_path):
        """Test when template is not found."""
        template_dir = tmp_path / "templates"
        template_dir.mkdir()

        expander = TemplateExpander(template_dirs=[template_dir])
        found = expander.find_template("nonexistent")

        assert found is None

    def test_find_template_searches_multiple_dirs(self, tmp_path):
        """Test searching in multiple directories."""
        dir1 = tmp_path / "templates1"
        dir1.mkdir()

        dir2 = tmp_path / "templates2"
        dir2.mkdir()

        # Put template in second directory
        template_file = dir2 / "test.template.yml"
        template_file.write_text("name: test")

        expander = TemplateExpander(template_dirs=[dir1, dir2])
        found = expander.find_template("test")

        assert found == template_file


class TestTemplateLoading:
    """Test template file loading."""

    def test_load_template_success(self, tmp_path):
        """Test loading a valid template."""
        template_dir = tmp_path / "templates"
        template_dir.mkdir()

        template_file = template_dir / "test.template.yml"
        template_file.write_text(
            yaml.dump(
                {
                    "name": "${test_name}",
                    "num_traders": "${num_traders:-10}",
                }
            )
        )

        expander = TemplateExpander(template_dirs=[template_dir])
        template = expander.load_template("test")

        assert template == {
            "name": "${test_name}",
            "num_traders": "${num_traders:-10}",
        }

    def test_load_template_not_found(self, tmp_path):
        """Test error when template doesn't exist."""
        template_dir = tmp_path / "templates"
        template_dir.mkdir()

        expander = TemplateExpander(template_dirs=[template_dir])

        with pytest.raises(TemplateNotFoundError) as exc_info:
            expander.load_template("nonexistent")

        assert "not found" in str(exc_info.value).lower()

    def test_load_template_empty_file(self, tmp_path):
        """Test error when template file is empty."""
        template_dir = tmp_path / "templates"
        template_dir.mkdir()

        template_file = template_dir / "test.template.yml"
        template_file.write_text("")

        expander = TemplateExpander(template_dirs=[template_dir])

        with pytest.raises(TemplateError) as exc_info:
            expander.load_template("test")

        assert "empty" in str(exc_info.value).lower()

    def test_load_template_invalid_yaml(self, tmp_path):
        """Test error when template has invalid YAML."""
        template_dir = tmp_path / "templates"
        template_dir.mkdir()

        template_file = template_dir / "test.template.yml"
        template_file.write_text("invalid: yaml: syntax: error:")

        expander = TemplateExpander(template_dirs=[template_dir])

        with pytest.raises(TemplateError) as exc_info:
            expander.load_template("test")

        assert "parse" in str(exc_info.value).lower()

    def test_load_template_not_dict(self, tmp_path):
        """Test error when template is not a dictionary."""
        template_dir = tmp_path / "templates"
        template_dir.mkdir()

        template_file = template_dir / "test.template.yml"
        template_file.write_text("- item1\n- item2\n")

        expander = TemplateExpander(template_dirs=[template_dir])

        with pytest.raises(TemplateError) as exc_info:
            expander.load_template("test")

        assert "must be a dictionary" in str(exc_info.value).lower()


class TestTemplateExpansion:
    """Test full template expansion."""

    def test_expand_template_simple(self, tmp_path):
        """Test expanding a simple template."""
        template_dir = tmp_path / "templates"
        template_dir.mkdir()

        template_file = template_dir / "simple.template.yml"
        template_file.write_text(
            yaml.dump(
                {
                    "name": "${test_name}",
                    "num_traders": "${num_traders}",
                    "duration": "${duration:-60}",
                }
            )
        )

        expander = TemplateExpander(template_dirs=[template_dir])
        result = expander.expand_template("simple", {"test_name": "My Test", "num_traders": 20})

        assert result == {
            "name": "My Test",
            "num_traders": "20",
            "duration": "60",  # Default
        }

    def test_expand_template_with_metadata(self, tmp_path):
        """Test that template_metadata is removed during expansion."""
        template_dir = tmp_path / "templates"
        template_dir.mkdir()

        template_file = template_dir / "test.template.yml"
        template_file.write_text(
            yaml.dump(
                {
                    "template_metadata": {
                        "name": "test",
                        "parameters": [{"name": "test_name", "required": True}],
                    },
                    "name": "${test_name}",
                    "num_traders": 10,
                }
            )
        )

        expander = TemplateExpander(template_dirs=[template_dir])
        result = expander.expand_template("test", {"test_name": "My Test"})

        # template_metadata should be removed
        assert "template_metadata" not in result
        assert result == {"name": "My Test", "num_traders": 10}

    def test_expand_template_complex(self, tmp_path):
        """Test expanding a complex template with nested structures."""
        template_dir = tmp_path / "templates"
        template_dir.mkdir()

        template_file = template_dir / "complex.template.yml"
        template_file.write_text(
            yaml.dump(
                {
                    "name": "${test_name}",
                    "num_traders": "${num_traders}",
                    "tags": ["${env}", "test"],
                    "metadata": {
                        "expected_orders": "${expected_orders}",
                        "resources": {"min_memory_gb": "${memory:-4}"},
                    },
                }
            )
        )

        expander = TemplateExpander(template_dirs=[template_dir])
        result = expander.expand_template(
            "complex",
            {
                "test_name": "Complex Test",
                "num_traders": 50,
                "env": "production",
                "expected_orders": 1000,
            },
        )

        assert result == {
            "name": "Complex Test",
            "num_traders": "50",
            "tags": ["production", "test"],
            "metadata": {
                "expected_orders": "1000",
                "resources": {"min_memory_gb": "4"},  # Default
            },
        }

    def test_expand_template_missing_required_param(self, tmp_path):
        """Test error when required parameter is missing."""
        template_dir = tmp_path / "templates"
        template_dir.mkdir()

        template_file = template_dir / "test.template.yml"
        template_file.write_text(yaml.dump({"name": "${test_name}", "num_traders": 10}))

        expander = TemplateExpander(template_dirs=[template_dir])

        with pytest.raises(ParameterError) as exc_info:
            expander.expand_template("test", {})

        assert "test_name" in str(exc_info.value)


class TestConvenienceFunction:
    """Test convenience function for template expansion."""

    def test_expand_template_function(self, tmp_path):
        """Test expand_template convenience function."""
        template_dir = tmp_path / "templates"
        template_dir.mkdir()

        template_file = template_dir / "test.template.yml"
        template_file.write_text(yaml.dump({"name": "${test_name}", "num_traders": 10}))

        result = expand_template("test", {"test_name": "My Test"}, [template_dir])

        assert result == {"name": "My Test", "num_traders": 10}
