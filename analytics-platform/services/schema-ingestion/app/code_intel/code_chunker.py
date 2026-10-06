"""Split source code into semantically meaningful chunks for vector embedding.

Chunks at AST-aware boundaries (function, class, module level),
never by arbitrary line count.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field

import structlog

from app.code_intel.ast_parser import ParseResult

log = structlog.get_logger(__name__)


@dataclass
class CodeChunk:
    """A chunk of code ready for embedding."""
    id: str
    text: str                 # the code text to embed
    file_path: str
    chunk_type: str           # "function" | "class" | "module_header" | "config"
    name: str                 # function/class name, or "module_header"
    line_start: int
    line_end: int
    language: str
    repo_id: str
    metadata: dict = field(default_factory=dict)


class CodeChunker:
    """Split source code files into chunks at AST-aware boundaries."""

    def chunk_file(
        self,
        file_path: str,
        content: str,
        language: str,
        repo_id: str,
        parse_result: ParseResult | None,
    ) -> list[CodeChunk]:
        """Create chunks for a single source file.

        If parse_result is available, uses AST boundaries.
        Otherwise falls back to treating the whole file as one chunk.
        """
        lines = content.splitlines()
        chunks: list[CodeChunk] = []

        if parse_result is None:
            # No AST — treat entire file as one chunk (for config files, etc.)
            chunks.append(self._make_chunk(
                text=content,
                file_path=file_path,
                chunk_type="config",
                name=file_path.rsplit("/", 1)[-1],
                line_start=1,
                line_end=len(lines),
                language=language,
                repo_id=repo_id,
            ))
            return chunks

        # Track which lines are covered by functions/classes
        covered_lines: set[int] = set()

        # --- Function chunks ---
        for func in parse_result.functions:
            func_lines = lines[func.line_start - 1: func.line_end]
            func_text = "\n".join(func_lines)

            if func_text.strip():
                prefix = f"# Method of class {func.parent_class}\n" if func.is_method else ""
                chunks.append(self._make_chunk(
                    text=prefix + func_text,
                    file_path=file_path,
                    chunk_type="function",
                    name=func.name,
                    line_start=func.line_start,
                    line_end=func.line_end,
                    language=language,
                    repo_id=repo_id,
                    metadata={
                        "params": func.params,
                        "return_type": func.return_type,
                        "is_method": func.is_method,
                        "parent_class": func.parent_class,
                        "docstring": func.docstring[:200] if func.docstring else "",
                    },
                ))
                for ln in range(func.line_start, func.line_end + 1):
                    covered_lines.add(ln)

        # --- Class chunks (signature + docstring + method signatures only) ---
        for cls in parse_result.classes:
            class_summary = self._build_class_summary(cls, lines)
            if class_summary.strip():
                chunks.append(self._make_chunk(
                    text=class_summary,
                    file_path=file_path,
                    chunk_type="class",
                    name=cls.name,
                    line_start=cls.line_start,
                    line_end=cls.line_end,
                    language=language,
                    repo_id=repo_id,
                    metadata={
                        "bases": cls.bases,
                        "methods": cls.methods,
                        "docstring": cls.docstring[:200] if cls.docstring else "",
                    },
                ))
                for ln in range(cls.line_start, cls.line_end + 1):
                    covered_lines.add(ln)

        # --- Module header chunk (imports + top-level code not covered above) ---
        header_lines: list[str] = []
        for i, line in enumerate(lines, start=1):
            if i not in covered_lines:
                header_lines.append(line)
            if i in covered_lines and header_lines:
                break  # Stop at first class/function

        header_text = "\n".join(header_lines).strip()
        if header_text and len(header_text) > 20:  # skip trivially small headers
            chunks.append(self._make_chunk(
                text=header_text,
                file_path=file_path,
                chunk_type="module_header",
                name="module_header",
                line_start=1,
                line_end=len(header_lines),
                language=language,
                repo_id=repo_id,
            ))

        log.debug("file_chunked", path=file_path, chunks=len(chunks))
        return chunks

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _make_chunk(
        text: str,
        file_path: str,
        chunk_type: str,
        name: str,
        line_start: int,
        line_end: int,
        language: str,
        repo_id: str,
        metadata: dict | None = None,
    ) -> CodeChunk:
        """Create a CodeChunk with a unique ID."""
        return CodeChunk(
            id=str(uuid.uuid4()),
            text=text[:8000],  # Cap chunk size to avoid embedding limits
            file_path=file_path,
            chunk_type=chunk_type,
            name=name,
            line_start=line_start,
            line_end=line_end,
            language=language,
            repo_id=repo_id,
            metadata=metadata or {},
        )

    @staticmethod
    def _build_class_summary(cls, lines: list[str]) -> str:
        """Build a compact class summary: definition + docstring + method signatures."""
        class_lines = lines[cls.line_start - 1: cls.line_end]

        summary_parts: list[str] = []
        in_method = False
        method_indent = 0

        for line in class_lines:
            stripped = line.strip()

            # Always include the class definition line
            if stripped.startswith("class "):
                summary_parts.append(line)
                continue

            # Include docstrings (triple-quoted strings)
            if '"""' in stripped or "'''" in stripped:
                summary_parts.append(line)
                continue

            # Include method signatures (def lines)
            if stripped.startswith("def "):
                summary_parts.append(line)
                continue

            # Include decorators
            if stripped.startswith("@"):
                summary_parts.append(line)
                continue

        return "\n".join(summary_parts)
