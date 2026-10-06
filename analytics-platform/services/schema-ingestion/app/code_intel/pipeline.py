"""End-to-end ingestion pipeline orchestrator for code repositories.

Coordinates:
1. Git clone / pull
2. File discovery & language filtering
3. AST parsing (classes, functions, imports, call graphs)
4. Neo4j graph storage
5. AST-aware code chunking
6. Gemini vector embeddings & ChromaDB storage
"""
from __future__ import annotations

import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable

import structlog

from app.code_intel.ast_parser import ASTParser, ParseResult
from app.code_intel.code_chunker import CodeChunker, CodeChunk
from app.code_intel.file_walker import FileWalker, CodeFile
from app.code_intel.git_client import GitClient
from app.code_intel.graph_writer import GraphWriter
from app.code_intel.vector_writer import VectorWriter

log = structlog.get_logger(__name__)


@dataclass
class IngestionProgress:
    """Tracks the progress of a repository ingestion run."""
    repo_id: str
    status: str = "queued"  # "queued", "cloning", "discovering_files", "building_knowledge_graph", "embedding_vectors", "completed", "failed"
    total_files: int = 0
    processed_files: int = 0
    total_chunks: int = 0
    embedded_chunks: int = 0
    error_message: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    stats: dict[str, Any] = field(default_factory=dict)


# In-memory status tracker for quick API status polling
_INGESTION_STATUS_STORE: dict[str, IngestionProgress] = {}


def get_pipeline_status(repo_id: str) -> IngestionProgress | None:
    """Retrieve current in-memory status for an ingestion job."""
    return _INGESTION_STATUS_STORE.get(repo_id)


class CodeIntelPipeline:
    """Orchestrates end-to-end ingestion of a code repository into Neo4j and ChromaDB."""

    def __init__(self) -> None:
        self.git_client = GitClient()
        self.file_walker = FileWalker()
        self.ast_parser = ASTParser()
        self.graph_writer = GraphWriter()
        self.code_chunker = CodeChunker()
        self.vector_writer = VectorWriter()

    def run_pipeline(
        self,
        tenant_id: str,
        repo_url: str,
        repo_name: str | None = None,
        branch: str = "main",
        repo_id: str | None = None,
        progress_callback: Callable[[IngestionProgress], None] | None = None,
    ) -> IngestionProgress:
        """Run the full ingestion pipeline.

        Args:
            tenant_id: Tenant UUID or identifier.
            repo_url: Git clone URL.
            repo_name: Human-friendly name for repository (defaults to parsed from URL).
            branch: Git branch to clone.
            repo_id: Optional existing repo UUID; generated if not supplied.
            progress_callback: Optional hook called on progress updates.

        Returns:
            IngestionProgress object with final stats.
        """
        if not repo_name:
            repo_name = self.git_client._repo_name_from_url(repo_url)

        if not repo_id:
            repo_id = str(uuid.uuid4())

        progress = IngestionProgress(
            repo_id=repo_id,
            status="cloning",
            started_at=datetime.utcnow(),
        )
        _INGESTION_STATUS_STORE[repo_id] = progress

        def _notify(stage: str):
            progress.status = stage
            if progress_callback:
                progress_callback(progress)

        try:
            log.info("starting_repo_ingestion", repo_id=repo_id, url=repo_url, branch=branch)

            # ------------------------------------------------------------------
            # 1. Ensure Neo4j Schema / Constraints
            # ------------------------------------------------------------------
            self.graph_writer.create_indexes()
            self.graph_writer.write_repository(repo_id=repo_id, name=repo_name, url=repo_url)

            # ------------------------------------------------------------------
            # 2. Git Clone or Pull (Incremental Diff Check)
            # ------------------------------------------------------------------
            _notify("cloning")
            local_path, diff_result = self.git_client.clone_or_pull_repo(repo_url, branch=branch)

            # --- INCREMENTAL SYNC PATH ---
            if diff_result is not None:
                total_changes = len(diff_result.added) + len(diff_result.modified) + len(diff_result.deleted)
                
                # If no commits were pulled, finish immediately
                if total_changes == 0:
                    log.info("repo_already_up_to_date_skipping", repo_id=repo_id)
                    progress.status = "completed"
                    progress.completed_at = datetime.utcnow()
                    return progress

                _notify("syncing_incremental_diffs")
                log.info("processing_incremental_diffs", 
                         added=len(diff_result.added), 
                         modified=len(diff_result.modified), 
                         deleted=len(diff_result.deleted))

                # 1. Clean up stale AST graph nodes & vectors for modified/deleted files
                files_to_clean = diff_result.deleted + diff_result.modified
                for rel_path in files_to_clean:
                    self.graph_writer.delete_file(repo_id=repo_id, file_path=rel_path)

                # 2. Re-index ONLY added and modified files
                files_to_reindex = diff_result.added + diff_result.modified
                target_code_files = []
                for rel_path in files_to_reindex:
                    abs_path = os.path.join(local_path, rel_path)
                    if os.path.exists(abs_path) and not self.file_walker.should_skip(rel_path):
                        content = self.file_walker._read_file(abs_path)
                        lang = self.file_walker.detect_language(rel_path)
                        if content and lang:
                            target_code_files.append(CodeFile(
                                path=rel_path,
                                abs_path=abs_path,
                                language=lang,
                                content=content,
                                size_bytes=len(content.encode('utf-8'))
                            ))
                
                code_files = target_code_files
            else:
                # --- INITIAL FULL INGESTION PATH ---
                _notify("discovering_files")
                code_files = self.file_walker.walk_repo(local_path)

            progress.total_files = len(code_files)
            log.info("files_discovered", count=len(code_files), repo_id=repo_id)

            # ------------------------------------------------------------------
            # 4. AST Parsing & Graph Population
            # ------------------------------------------------------------------
            _notify("building_knowledge_graph")

            parse_results: list[ParseResult] = []
            all_chunks: list[CodeChunk] = []

            for idx, code_file in enumerate(code_files):
                parse_result = self.ast_parser.parse_file(
                    file_path=code_file.path,
                    content=code_file.content,
                    language=code_file.language,
                )
                if parse_result is not None:
                    parse_results.append(parse_result)
                    # Write nodes & edges into Neo4j
                    self.graph_writer.write_file_results(repo_id=repo_id, parse_result=parse_result)
                else:
                    log.info("skipping_graph_write_unsupported_lang",
                             file=code_file.path, language=code_file.language)

                # Generate semantic chunks
                chunks = self.code_chunker.chunk_file(
                    file_path=code_file.path,
                    content=code_file.content,
                    language=code_file.language,
                    repo_id=repo_id,
                    parse_result=parse_result,
                )
                all_chunks.extend(chunks)

                progress.processed_files = idx + 1
                if (idx + 1) % 10 == 0 or idx + 1 == len(code_files):
                    log.info("ast_processing_progress", current=idx + 1, total=len(code_files))
                    if progress_callback:
                        progress_callback(progress)

            # ------------------------------------------------------------------
            # 5. Vector Embedding & Storage
            # ------------------------------------------------------------------
            _notify("embedding_vectors")
            progress.total_chunks = len(all_chunks)
            log.info("embedding_chunks", total_chunks=len(all_chunks), repo_id=repo_id)

            embedded_count = self.vector_writer.store_chunks(
                tenant_id=tenant_id,
                repo_id=repo_id,
                chunks=all_chunks,
            )
            progress.embedded_chunks = embedded_count

            # ------------------------------------------------------------------
            # 6. Gather Final Statistics
            # ------------------------------------------------------------------
            neo4j_stats = self.graph_writer.get_stats(repo_id)

            progress.status = "completed"
            progress.completed_at = datetime.utcnow()
            progress.stats = {
                "repo_id": repo_id,
                "repo_name": repo_name,
                "repo_url": repo_url,
                "branch": branch,
                "total_files": progress.total_files,
                "total_chunks": progress.total_chunks,
                "embedded_chunks": progress.embedded_chunks,
                "graph": neo4j_stats,
            }

            log.info("repo_ingestion_completed", repo_id=repo_id, stats=progress.stats)
            if progress_callback:
                progress_callback(progress)

            return progress

        except Exception as exc:
            log.error("repo_ingestion_failed", repo_id=repo_id, error=str(exc), exc_info=True)
            progress.status = "failed"
            progress.error_message = str(exc)
            progress.completed_at = datetime.utcnow()
            if progress_callback:
                progress_callback(progress)
            raise
