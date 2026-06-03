"""Unit tests for package initialization."""

import cow_performance


class TestPackageInit:
    """Test package initialization."""

    def test_version_exists(self) -> None:
        """Test that version is defined."""
        assert hasattr(cow_performance, "__version__")
        assert isinstance(cow_performance.__version__, str)
        assert cow_performance.__version__ == "0.1.0"

    def test_author_exists(self) -> None:
        """Test that author is defined."""
        assert hasattr(cow_performance, "__author__")
        assert isinstance(cow_performance.__author__, str)

    def test_license_exists(self) -> None:
        """Test that license is defined."""
        assert hasattr(cow_performance, "__license__")
        assert cow_performance.__license__ == "MIT"
