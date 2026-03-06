"""Unit tests for git info extraction."""

import logging
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from cow_performance.baselines.git_info import GitInfo, get_git_info, git_info_to_dict


class TestGitInfo:
    """Tests for GitInfo dataclass."""

    def test_default_values(self) -> None:
        """Test default GitInfo values."""
        info = GitInfo()

        assert info.commit is None
        assert info.branch is None
        assert info.repo_url is None
        assert info.is_dirty is False

    def test_with_values(self) -> None:
        """Test GitInfo with all values."""
        info = GitInfo(
            commit="abc123",
            branch="main",
            repo_url="https://github.com/test/repo",
            is_dirty=True,
        )

        assert info.commit == "abc123"
        assert info.branch == "main"
        assert info.is_dirty is True


class TestGetGitInfo:
    """Tests for get_git_info function."""

    def test_not_in_git_repo(self) -> None:
        """Test behavior when not in a git repository."""
        with tempfile.TemporaryDirectory() as tmpdir:
            info = get_git_info(Path(tmpdir))

        assert info.commit is None
        assert info.branch is None
        assert info.is_dirty is False

    def test_with_valid_repo(self) -> None:
        """Test with a valid git repository using real git module."""
        # Create a mock git module
        mock_git = MagicMock()
        mock_repo = MagicMock()
        mock_repo.head.commit.hexsha = "abc123def456789"
        mock_repo.head.is_detached = False
        mock_repo.active_branch.name = "main"
        mock_repo.remotes = {"origin": MagicMock(url="https://github.com/test/repo")}
        mock_repo.is_dirty.return_value = False

        mock_git.Repo.return_value = mock_repo

        # Patch at sys.modules level before import
        with patch.dict(sys.modules, {"git": mock_git}):
            # Need to reimport to pick up the mock
            import importlib

            import cow_performance.baselines.git_info as git_info_module

            importlib.reload(git_info_module)
            info = git_info_module.get_git_info(Path("/fake/path"))

            assert info.commit == "abc123def456789"
            assert info.branch == "main"
            assert info.is_dirty is False

        # Reload original module
        importlib.reload(git_info_module)

    def test_detached_head(self) -> None:
        """Test with detached HEAD state."""
        mock_git = MagicMock()
        mock_repo = MagicMock()
        mock_repo.head.commit.hexsha = "abc123def456789"
        mock_repo.head.is_detached = True
        mock_repo.remotes = {}
        mock_repo.is_dirty.return_value = False

        mock_git.Repo.return_value = mock_repo

        with patch.dict(sys.modules, {"git": mock_git}):
            import importlib

            import cow_performance.baselines.git_info as git_info_module

            importlib.reload(git_info_module)
            info = git_info_module.get_git_info(Path("/fake/path"))

            assert info.commit == "abc123def456789"
            assert info.branch == "detached@abc123de"

        importlib.reload(git_info_module)

    def test_dirty_repo_warning(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test that dirty repo logs a warning."""
        mock_git = MagicMock()
        mock_repo = MagicMock()
        mock_repo.head.commit.hexsha = "abc123"
        mock_repo.head.is_detached = False
        mock_repo.active_branch.name = "main"
        mock_repo.remotes = {}
        mock_repo.is_dirty.return_value = True

        mock_git.Repo.return_value = mock_repo

        with patch.dict(sys.modules, {"git": mock_git}):
            import importlib

            import cow_performance.baselines.git_info as git_info_module

            importlib.reload(git_info_module)

            with caplog.at_level(logging.WARNING):
                info = git_info_module.get_git_info(Path("/fake/path"))

            assert info.is_dirty is True
            assert "uncommitted changes" in caplog.text.lower()

        importlib.reload(git_info_module)


class TestGitInfoToDict:
    """Tests for git_info_to_dict function."""

    def test_converts_to_dict(self) -> None:
        """Test conversion to dictionary."""
        info = GitInfo(
            commit="abc123",
            branch="main",
            repo_url="https://github.com/test/repo",
            is_dirty=True,
        )

        result = git_info_to_dict(info)

        assert result == {
            "git_commit": "abc123",
            "git_branch": "main",
            "git_repo": "https://github.com/test/repo",
            "has_uncommitted_changes": True,
        }

    def test_converts_none_values(self) -> None:
        """Test conversion with None values."""
        info = GitInfo()

        result = git_info_to_dict(info)

        assert result["git_commit"] is None
        assert result["git_branch"] is None
        assert result["has_uncommitted_changes"] is False
