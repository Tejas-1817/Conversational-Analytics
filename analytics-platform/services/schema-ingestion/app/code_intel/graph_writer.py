"""Write parsed AST results to Neo4j as a knowledge graph."""
from __future__ import annotations

import uuid
from contextlib import contextmanager

import structlog
from neo4j import GraphDatabase, Driver, Session

from app.config import get_settings
from app.code_intel.ast_parser import ParseResult

log = structlog.get_logger(__name__)


class GraphWriter:
    """Manages Neo4j connections and writes code structure as graph nodes/edges."""

    def __init__(self) -> None:
        settings = get_settings()
        self._driver: Driver = GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
        )
        log.info("neo4j_driver_initialized", uri=settings.neo4j_uri)

    def close(self) -> None:
        """Close the Neo4j driver connection."""
        self._driver.close()

    @contextmanager
    def _session(self):
        """Yield a Neo4j session and auto-close it."""
        session = self._driver.session()
        try:
            yield session
        finally:
            session.close()

    # ------------------------------------------------------------------
    # Schema setup
    # ------------------------------------------------------------------

    def create_indexes(self) -> None:
        """Create indexes and constraints for performance.
        Run once on first setup.
        """
        with self._session() as session:
            # Unique constraints
            session.run(
                "CREATE CONSTRAINT IF NOT EXISTS FOR (r:Repository) "
                "REQUIRE (r.repo_id) IS UNIQUE"
            )
            session.run(
                "CREATE INDEX IF NOT EXISTS FOR (f:File) ON (f.repo_id, f.path)"
            )
            session.run(
                "CREATE INDEX IF NOT EXISTS FOR (c:Class) ON (c.repo_id, c.name)"
            )
            session.run(
                "CREATE INDEX IF NOT EXISTS FOR (fn:Function) ON (fn.repo_id, fn.name)"
            )
            log.info("neo4j_indexes_created")

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------

    def write_repository(self, repo_id: str, name: str, url: str) -> None:
        """Create or update a Repository node."""
        with self._session() as session:
            session.run(
                """
                MERGE (r:Repository {repo_id: $repo_id})
                SET r.name = $name, r.url = $url,
                    r.last_ingested_at = datetime()
                """,
                repo_id=repo_id, name=name, url=url,
            )

    def write_file_results(self, repo_id: str, parse_result: ParseResult) -> None:
        """Write all parsed data from a single file into the graph.

        Creates File, Class, Function, Import nodes and their relationships.
        """
        fp = parse_result.file_path

        with self._session() as session:
            # --- File node ---
            session.run(
                """
                MERGE (f:File {repo_id: $repo_id, path: $path})
                SET f.language = $language
                WITH f
                MATCH (r:Repository {repo_id: $repo_id})
                MERGE (r)-[:CONTAINS]->(f)
                """,
                repo_id=repo_id, path=fp, language=parse_result.language,
            )

            # --- Classes ---
            for cls in parse_result.classes:
                session.run(
                    """
                    MERGE (c:Class {repo_id: $repo_id, name: $name, file_path: $file_path})
                    SET c.line_start = $line_start, c.line_end = $line_end,
                        c.docstring = $docstring, c.methods = $methods
                    WITH c
                    MATCH (f:File {repo_id: $repo_id, path: $file_path})
                    MERGE (f)-[:DEFINES]->(c)
                    """,
                    repo_id=repo_id,
                    name=cls.name,
                    file_path=cls.file_path,
                    line_start=cls.line_start,
                    line_end=cls.line_end,
                    docstring=cls.docstring[:500] if cls.docstring else "",
                    methods=cls.methods,
                )

                # INHERITS edges
                for base in cls.bases:
                    session.run(
                        """
                        MATCH (child:Class {repo_id: $repo_id, name: $child_name})
                        MERGE (parent:Class {repo_id: $repo_id, name: $parent_name})
                        MERGE (child)-[:INHERITS]->(parent)
                        """,
                        repo_id=repo_id,
                        child_name=cls.name,
                        parent_name=base,
                    )

            # --- Functions ---
            for func in parse_result.functions:
                session.run(
                    """
                    MERGE (fn:Function {repo_id: $repo_id, name: $name, file_path: $file_path})
                    SET fn.line_start = $line_start, fn.line_end = $line_end,
                        fn.docstring = $docstring, fn.params = $params,
                        fn.return_type = $return_type, fn.is_method = $is_method,
                        fn.parent_class = $parent_class
                    WITH fn
                    MATCH (f:File {repo_id: $repo_id, path: $file_path})
                    MERGE (f)-[:DEFINES]->(fn)
                    """,
                    repo_id=repo_id,
                    name=func.name,
                    file_path=func.file_path,
                    line_start=func.line_start,
                    line_end=func.line_end,
                    docstring=func.docstring[:500] if func.docstring else "",
                    params=func.params,
                    return_type=func.return_type,
                    is_method=func.is_method,
                    parent_class=func.parent_class,
                )

                # Link method to its class
                if func.is_method and func.parent_class:
                    session.run(
                        """
                        MATCH (c:Class {repo_id: $repo_id, name: $class_name})
                        MATCH (fn:Function {repo_id: $repo_id, name: $func_name, file_path: $file_path})
                        MERGE (c)-[:DEFINES_METHOD]->(fn)
                        """,
                        repo_id=repo_id,
                        class_name=func.parent_class,
                        func_name=func.name,
                        file_path=func.file_path,
                    )

            # --- Imports ---
            for imp in parse_result.imports:
                session.run(
                    """
                    MERGE (i:Import {repo_id: $repo_id, module_path: $module_path, file_path: $file_path})
                    SET i.names = $names, i.alias = $alias
                    WITH i
                    MATCH (f:File {repo_id: $repo_id, path: $file_path})
                    MERGE (f)-[:IMPORTS]->(i)
                    """,
                    repo_id=repo_id,
                    module_path=imp.module_path,
                    file_path=fp,
                    names=imp.names,
                    alias=imp.alias,
                )

            # --- Call edges ---
            for call in parse_result.calls:
                session.run(
                    """
                    MATCH (caller:Function {repo_id: $repo_id, name: $caller_name, file_path: $file_path})
                    MATCH (callee:Function {repo_id: $repo_id, name: $callee_name})
                    MERGE (caller)-[:CALLS {line: $line}]->(callee)
                    """,
                    repo_id=repo_id,
                    caller_name=call.caller,
                    callee_name=call.callee,
                    file_path=call.file_path,
                    line=call.line,
                )

    # ------------------------------------------------------------------
    # Delete operations (for re-ingestion)
    # ------------------------------------------------------------------

    def delete_file(self, repo_id: str, file_path: str) -> None:
        """Remove all nodes and relationships for a single file."""
        with self._session() as session:
            session.run(
                """
                MATCH (f:File {repo_id: $repo_id, path: $file_path})
                OPTIONAL MATCH (f)-[:DEFINES]->(n)
                DETACH DELETE n, f
                """,
                repo_id=repo_id, file_path=file_path,
            )

    def clear_repository(self, repo_id: str) -> None:
        """Remove the entire graph for a repository."""
        with self._session() as session:
            session.run(
                """
                MATCH (n {repo_id: $repo_id})
                DETACH DELETE n
                """,
                repo_id=repo_id,
            )
            log.info("repository_graph_cleared", repo_id=repo_id)

    # ------------------------------------------------------------------
    # Read operations (for verification)
    # ------------------------------------------------------------------

    def get_stats(self, repo_id: str) -> dict:
        """Return node/edge counts for a repository."""
        with self._session() as session:
            result = session.run(
                """
                MATCH (n {repo_id: $repo_id})
                RETURN labels(n)[0] AS label, count(n) AS count
                ORDER BY label
                """,
                repo_id=repo_id,
            )
            stats = {record["label"]: record["count"] for record in result}

            rel_result = session.run(
                """
                MATCH ({repo_id: $repo_id})-[r]->({repo_id: $repo_id})
                RETURN type(r) AS rel_type, count(r) AS count
                ORDER BY rel_type
                """,
                repo_id=repo_id,
            )
            stats["_relationships"] = {
                record["rel_type"]: record["count"] for record in rel_result
            }

            return stats
