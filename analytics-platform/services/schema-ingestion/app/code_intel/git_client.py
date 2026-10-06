"""Git operations — clone, pull, and detect changed files."""
from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, field

import git
import structlog

from app.config import get_settings

log = structlog.get_logger(__name__)


@dataclass
class DiffResult:
    """Files that changed between two commits."""
    added: list[str] = field(default_factory=list)
    modified: list[str] = field(default_factory=list)
    deleted: list[str] = field(default_factory=list)


class GitClient:
    """Clone and sync Git repositories."""

    def __init__(self) -> None:
        settings = get_settings()
        self.base_dir = os.path.abspath(settings.code_repos_clone_dir)
        os.makedirs(self.base_dir, exist_ok=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def clone_or_pull_repo(self, url: str, branch: str = "main") -> tuple[str, DiffResult | None]:
        """Clone if new, or pull latest changes and return DiffResult if exists."""
        repo_name = self._repo_name_from_url(url)
        local_path = os.path.join(self.base_dir, repo_name)

        if os.path.exists(os.path.join(local_path, ".git")):
            log.info("repo_already_cloned_pulling", repo=repo_name)
            diff_result = self.pull_repo(local_path)
            return local_path, diff_result

        log.info("cloning_repo", url=url, branch=branch, target=local_path)
        try:
            git.Repo.clone_from(
                url,
                local_path,
                branch=branch,
                depth=1,              # shallow clone — fast
                single_branch=True,
            )
            log.info("clone_complete", repo=repo_name, path=local_path)
        except git.GitCommandError as exc:
            log.error("clone_failed", url=url, error=str(exc))
            raise RuntimeError(f"Failed to clone {url}: {exc}") from exc

        return local_path, None  # None indicates a brand-new full clone


    def pull_repo(self, local_path: str) -> DiffResult:
        """Pull latest changes and return which files changed."""
        repo = git.Repo(local_path)

        # Remember current HEAD before pulling
        old_head = repo.head.commit.hexsha

        try:
            origin = repo.remotes.origin
            origin.pull()
        except git.GitCommandError as exc:
            log.error("pull_failed", path=local_path, error=str(exc))
            raise RuntimeError(f"Failed to pull {local_path}: {exc}") from exc

        new_head = repo.head.commit.hexsha

        if old_head == new_head:
            log.info("repo_already_up_to_date", path=local_path)
            return DiffResult()

        return self.get_changed_files(local_path, old_head, new_head)

    def get_changed_files(
        self, local_path: str, old_sha: str, new_sha: str
    ) -> DiffResult:
        """Compare two commits and return added/modified/deleted files."""
        repo = git.Repo(local_path)
        result = DiffResult()

        diffs = repo.commit(old_sha).diff(repo.commit(new_sha))

        for diff in diffs:
            if diff.new_file:
                result.added.append(diff.b_path)
            elif diff.deleted_file:
                result.deleted.append(diff.a_path)
            elif diff.renamed_file:
                result.deleted.append(diff.a_path)
                result.added.append(diff.b_path)
            else:
                result.modified.append(diff.b_path or diff.a_path)

        log.info(
            "diff_computed",
            added=len(result.added),
            modified=len(result.modified),
            deleted=len(result.deleted),
        )
        return result

    def delete_repo(self, local_path: str) -> None:
        """Remove a cloned repository from disk."""
        if os.path.exists(local_path):
            shutil.rmtree(local_path, ignore_errors=True)
            log.info("repo_deleted", path=local_path)

    def get_all_files(self, local_path: str) -> list[str]:
        """Return every tracked file path in the repo (relative paths)."""
        repo = git.Repo(local_path)
        # ls-files returns all tracked files
        tracked = repo.git.ls_files().splitlines()
        return tracked

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _repo_name_from_url(url: str) -> str:
        """Extract a folder-safe name from a Git URL.

        Examples:
            https://github.com/org/repo.git  → org_repo
            git@github.com:org/repo.git      → org_repo
        """
        # Remove trailing .git
        clean = url.rstrip("/").removesuffix(".git")

        # Handle SSH format (git@github.com:org/repo)
        if ":" in clean and "@" in clean:
            clean = clean.split(":")[-1]
        else:
            # HTTPS format — take last two path segments
            parts = clean.split("/")
            clean = "/".join(parts[-2:]) if len(parts) >= 2 else parts[-1]

        # Replace / with _
        return clean.replace("/", "_").replace("\\", "_")
