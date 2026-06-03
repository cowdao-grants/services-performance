"""Git integration for baseline metadata."""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class GitInfo:
    """Git repository information."""

    commit: str | None = None
    branch: str | None = None
    repo_url: str | None = None
    is_dirty: bool = False


def get_git_info(repo_path: Path | None = None) -> GitInfo:
    """
    Extract git information from the current repository.

    Args:
        repo_path: Optional path to repository. Uses cwd if not specified.

    Returns:
        GitInfo with repository metadata. Returns empty GitInfo if not in a git repo.
    """
    try:
        import git
    except ImportError:
        logger.warning("GitPython not installed. Git info will not be captured.")
        return GitInfo()

    if repo_path is None:
        repo_path = Path.cwd()

    try:
        repo = git.Repo(repo_path, search_parent_directories=True)
    except git.InvalidGitRepositoryError:
        logger.debug("Not in a git repository: %s", repo_path)
        return GitInfo()
    except git.GitCommandNotFound:
        logger.warning("Git command not found. Git info will not be captured.")
        return GitInfo()

    info = GitInfo()

    # Get current commit hash
    try:
        info.commit = repo.head.commit.hexsha
    except Exception as e:
        logger.debug("Could not get commit hash: %s", e)

    # Get current branch name
    try:
        if not repo.head.is_detached:
            info.branch = repo.active_branch.name
        else:
            info.branch = f"detached@{info.commit[:8]}" if info.commit else "detached"
    except Exception as e:
        logger.debug("Could not get branch name: %s", e)

    # Get remote URL (origin)
    try:
        if "origin" in repo.remotes:
            info.repo_url = repo.remotes.origin.url
    except Exception as e:
        logger.debug("Could not get remote URL: %s", e)

    # Check for uncommitted changes
    try:
        info.is_dirty = repo.is_dirty(untracked_files=True)
        if info.is_dirty:
            logger.warning(
                "Repository has uncommitted changes. "
                "Baseline may not be reproducible from git commit."
            )
    except Exception as e:
        logger.debug("Could not check dirty status: %s", e)

    return info


def git_info_to_dict(info: GitInfo) -> dict[str, Any]:
    """Convert GitInfo to a dictionary for baseline storage."""
    return {
        "git_commit": info.commit,
        "git_branch": info.branch,
        "git_repo": info.repo_url,
        "has_uncommitted_changes": info.is_dirty,
    }
