"""Walk a cloned repository, detect languages, and filter out noise."""
from __future__ import annotations

import os
from dataclasses import dataclass

import structlog

log = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Language detection
# ---------------------------------------------------------------------------

EXTENSION_MAP: dict[str, str] = {
    ".py": "python",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".js": "javascript",
    ".jsx": "javascript",
    ".java": "java",
    ".go": "go",
    ".rs": "rust",
    ".cs": "c_sharp",
    ".rb": "ruby",
    ".php": "php",
    ".swift": "swift",
    ".kt": "kotlin",
    ".scala": "scala",
    ".sql": "sql",
    ".sh": "bash",
    ".yml": "yaml",
    ".yaml": "yaml",
    ".json": "json",
    ".toml": "toml",
    ".md": "markdown",
    ".dockerfile": "dockerfile",
}

# ---------------------------------------------------------------------------
# Skip rules
# ---------------------------------------------------------------------------

SKIP_DIRS: set[str] = {
    ".git", "node_modules", "__pycache__", ".tox", "venv",
    ".venv", "env", "dist", "build", ".next", ".nuxt",
    "vendor", "target", "bin", "obj", ".idea", ".vscode",
    ".mypy_cache", ".pytest_cache", "coverage", ".eggs",
    "site-packages", ".gradle", ".mvn", "out",
    # Multi-language translation docs to skip
    "zh", "es", "fr", "de", "pt", "ru", "ja", "ko", "it", "tr", "vi", "id", "uk", "fa", "he", "ar",
}

SKIP_EXTENSIONS: set[str] = {
    ".pyc", ".pyo", ".class", ".o", ".so", ".dll", ".exe",
    ".wasm", ".min.js", ".min.css", ".map", ".lock",
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".webp",
    ".woff", ".woff2", ".ttf", ".eot",
    ".mp4", ".mp3", ".wav", ".avi",
    ".zip", ".tar", ".gz", ".rar", ".7z", ".bz2",
    ".db", ".sqlite", ".sqlite3",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx",
}

SKIP_FILENAMES: set[str] = {
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
    "poetry.lock", "Pipfile.lock", "composer.lock",
    "Gemfile.lock", "Cargo.lock", "go.sum",
}

MAX_FILE_SIZE: int = 500 * 1024  # 500KB — skip generated/minified files


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class CodeFile:
    """A single source file discovered in the repository."""
    path: str           # relative path from repo root (e.g., "app/main.py")
    abs_path: str       # absolute path on disk
    language: str       # detected language (e.g., "python")
    content: str        # file content as string
    size_bytes: int     # file size


# ---------------------------------------------------------------------------
# Walker
# ---------------------------------------------------------------------------

class FileWalker:
    """Walk a repository directory and yield parseable source files."""

    def walk_repo(self, repo_path: str) -> list[CodeFile]:
        """Discover all source files in a cloned repository.

        Filters out binary files, vendor directories, lock files,
        and files larger than 500KB.
        """
        repo_path = os.path.abspath(repo_path)
        files: list[CodeFile] = []

        for root, dirs, filenames in os.walk(repo_path):
            # Prune skip directories (modifying dirs in-place skips them)
            dirs[:] = [
                d for d in dirs
                if d not in SKIP_DIRS and not d.startswith(".")
            ]

            for filename in filenames:
                abs_path = os.path.join(root, filename)
                rel_path = os.path.relpath(abs_path, repo_path).replace("\\", "/")

                if self._should_skip(filename, abs_path):
                    continue

                language = self._detect_language(filename)
                if not language:
                    continue

                try:
                    content = self._read_file(abs_path)
                    if content is None:
                        continue

                    size = os.path.getsize(abs_path)
                    files.append(CodeFile(
                        path=rel_path,
                        abs_path=abs_path,
                        language=language,
                        content=content,
                        size_bytes=size,
                    ))
                except Exception as exc:
                    log.warning("file_read_error", path=rel_path, error=str(exc))

        log.info("repo_walk_complete", total_files=len(files), repo=repo_path)
        return files

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def should_skip(self, path: str) -> bool:
        """Return True if path should be skipped based on dir, name, or extension."""
        norm_path = path.replace("\\", "/")
        parts = norm_path.split("/")
        filename = parts[-1]
        
        # Check parent directories
        for part in parts[:-1]:
            if part in SKIP_DIRS or (part.startswith(".") and part != "."):
                return True

        return self._should_skip(filename, path)

    def detect_language(self, path: str) -> str | None:
        """Public helper to detect language from path/filename."""
        filename = os.path.basename(path)
        return self._detect_language(filename)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _detect_language(filename: str) -> str | None:
        """Detect programming language from file extension."""
        # Handle Dockerfile (no extension)
        if filename.lower() in ("dockerfile", "dockerfile.dev", "dockerfile.prod"):
            return "dockerfile"

        _, ext = os.path.splitext(filename)
        ext = ext.lower()
        return EXTENSION_MAP.get(ext)

    @staticmethod
    def _should_skip(filename: str, abs_path: str) -> bool:
        """Return True if this file should be skipped."""
        # Skip by filename
        if filename in SKIP_FILENAMES:
            return True

        # Skip by extension
        _, ext = os.path.splitext(filename)
        if ext.lower() in SKIP_EXTENSIONS:
            return True

        # Skip hidden files
        if filename.startswith("."):
            return True

        # Skip files larger than MAX_FILE_SIZE if file exists on disk
        try:
            if os.path.exists(abs_path) and os.path.getsize(abs_path) > MAX_FILE_SIZE:
                return True
        except OSError:
            pass

        return False

    @staticmethod
    def _read_file(abs_path: str) -> str | None:
        """Read a file as UTF-8 text. Returns None for binary files."""
        try:
            with open(abs_path, "r", encoding="utf-8", errors="strict") as f:
                return f.read()
        except (UnicodeDecodeError, ValueError):
            # Binary file or encoding issue — skip
            return None
