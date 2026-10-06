"""GraphRAG Query Orchestrator for Code Intelligence.

Combines Neo4j structural graph traversal + ChromaDB vector search
to answer complex queries about repository architecture, call hierarchies,
and code behavior.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

import structlog

from app.config import get_settings
from app.code_intel.graph_writer import GraphWriter
from app.code_intel.vector_writer import VectorWriter

log = structlog.get_logger(__name__)


@dataclass
class CodeQueryResult:
    """The structured result returned by the GraphRAG query orchestrator."""
    query: str
    repo_id: str
    answer: str
    referenced_files: list[str] = field(default_factory=list)
    referenced_symbols: list[str] = field(default_factory=list)
    graph_facts: list[str] = field(default_factory=list)
    retrieved_chunks: list[dict[str, Any]] = field(default_factory=list)


class GraphRAGQueryEngine:
    """Combines Graph Knowledge (Neo4j) with Vector Retrieval (ChromaDB + Gemini) to answer code questions."""

    def __init__(self) -> None:
        self.graph_writer = GraphWriter()
        self.vector_writer = VectorWriter()
        self.settings = get_settings()

    # ------------------------------------------------------------------
    # Entity extraction heuristics
    # ------------------------------------------------------------------

    def _extract_entities(self, query: str) -> list[str]:
        """Extract candidate symbol names (functions, classes, files) and key concepts from query."""
        entities: set[str] = set()

        # Quoted identifiers: `foo`, 'foo', "foo"
        quoted = re.findall(r"[`'\"]([a-zA-Z0-9_\-\./]+)[`'\"]", query)
        entities.update(quoted)

        # PascalCase (e.g. UserService, OAuth2PasswordBearer)
        pascal = re.findall(r"\b[A-Z][a-zA-Z0-9]+(?:[A-Z][a-zA-Z0-9]*)*\b", query)
        entities.update(pascal)

        # snake_case with at least one underscore (e.g. verify_token, build_engine)
        snake = re.findall(r"\b[a-z0-9]+_[a-z0-9_]+\b", query)
        entities.update(snake)

        # Key technical terms from the query (words with >= 4 letters)
        keywords = re.findall(r"\b[a-zA-Z]{4,}\b", query)
        stop_words = {
            "what", "when", "where", "which", "about", "there", "their", "these",
            "those", "could", "would", "should", "explain", "describe", "detail",
            "against", "repo", "code", "file", "does", "have", "with", "this", "from"
        }
        for kw in keywords:
            if kw.lower() not in stop_words:
                entities.add(kw)

        return [e for e in entities if len(e) > 2][:8]


    # ------------------------------------------------------------------
    # Graph Traversal (Neo4j)
    # ------------------------------------------------------------------

    def _traverse_graph(self, repo_id: str, entities: list[str]) -> tuple[list[str], set[str], set[str]]:
        """Traverse the Neo4j graph for related classes, functions, calls, and files.

        Returns:
            (graph_facts, referenced_files, referenced_symbols)
        """
        graph_facts: list[str] = []
        referenced_files: set[str] = set()
        referenced_symbols: set[str] = set()

        if not entities:
            return graph_facts, referenced_files, referenced_symbols

        with self.graph_writer._session() as session:
            for entity in entities:
                # 1. Check for matching Functions
                fn_result = session.run(
                    """
                    MATCH (fn:Function {repo_id: $repo_id})
                    WHERE toLower(fn.name) CONTAINS toLower($entity)
                    OPTIONAL MATCH (f:File)-[:DEFINES]->(fn)
                    OPTIONAL MATCH (c:Class)-[:DEFINES_METHOD]->(fn)
                    OPTIONAL MATCH (caller:Function)-[:CALLS]->(fn)
                    OPTIONAL MATCH (fn)-[:CALLS]->(callee:Function)
                    RETURN fn.name AS name, fn.file_path AS file_path,
                           fn.line_start AS line_start, fn.line_end AS line_end,
                           fn.docstring AS docstring, fn.params AS params,
                           fn.return_type AS return_type,
                           c.name AS class_name,
                           collect(DISTINCT caller.name) AS callers,
                           collect(DISTINCT callee.name) AS callees
                    LIMIT 5
                    """,
                    repo_id=repo_id, entity=entity,
                )

                for r in fn_result:
                    name = r["name"]
                    fp = r["file_path"] or "unknown"
                    referenced_symbols.add(name)
                    if fp != "unknown":
                        referenced_files.add(fp)

                    fact = f"Function `{name}` is defined in `{fp}` (lines {r['line_start']}-{r['line_end']})."
                    if r["class_name"]:
                        fact += f" Method of class `{r['class_name']}`."
                    if r["params"]:
                        fact += f" Params: ({', '.join(r['params'])})."
                    if r["return_type"]:
                        fact += f" Returns: `{r['return_type']}`."
                    if r["callers"]:
                        valid_callers = [c for c in r["callers"] if c]
                        if valid_callers:
                            fact += f" Called by: {', '.join(f'`{c}`' for c in valid_callers[:5])}."
                    if r["callees"]:
                        valid_callees = [c for c in r["callees"] if c]
                        if valid_callees:
                            fact += f" Calls: {', '.join(f'`{c}`' for c in valid_callees[:5])}."
                    graph_facts.append(fact)

                # 2. Check for matching Classes
                cls_result = session.run(
                    """
                    MATCH (c:Class {repo_id: $repo_id})
                    WHERE toLower(c.name) CONTAINS toLower($entity)
                    OPTIONAL MATCH (c)-[:INHERITS]->(parent:Class)
                    OPTIONAL MATCH (child:Class)-[:INHERITS]->(c)
                    OPTIONAL MATCH (c)-[:DEFINES_METHOD]->(m:Function)
                    RETURN c.name AS name, c.file_path AS file_path,
                           c.line_start AS line_start, c.line_end AS line_end,
                           c.docstring AS docstring,
                           collect(DISTINCT parent.name) AS parents,
                           collect(DISTINCT child.name) AS children,
                           collect(DISTINCT m.name) AS methods
                    LIMIT 5
                    """,
                    repo_id=repo_id, entity=entity,
                )

                for r in cls_result:
                    name = r["name"]
                    fp = r["file_path"] or "unknown"
                    referenced_symbols.add(name)
                    if fp != "unknown":
                        referenced_files.add(fp)

                    fact = f"Class `{name}` is defined in `{fp}` (lines {r['line_start']}-{r['line_end']})."
                    if r["parents"]:
                        valid_parents = [p for p in r["parents"] if p]
                        if valid_parents:
                            fact += f" Inherits from: {', '.join(f'`{p}`' for p in valid_parents)}."
                    if r["methods"]:
                        valid_methods = [m for m in r["methods"] if m]
                        if valid_methods:
                            fact += f" Methods: {', '.join(f'`{m}`' for m in valid_methods[:8])}."
                    graph_facts.append(fact)

                # 3. Check for matching Files
                file_result = session.run(
                    """
                    MATCH (f:File {repo_id: $repo_id})
                    WHERE f.path CONTAINS $entity
                    OPTIONAL MATCH (f)-[:DEFINES]->(elem)
                    OPTIONAL MATCH (f)-[:IMPORTS]->(i:Import)
                    RETURN f.path AS path, f.language AS language,
                           collect(DISTINCT elem.name) AS defined_elements,
                           collect(DISTINCT i.module_path) AS imports
                    LIMIT 3
                    """,
                    repo_id=repo_id, entity=entity,
                )

                for r in file_result:
                    path = r["path"]
                    referenced_files.add(path)
                    fact = f"File `{path}` ({r['language']})."
                    if r["defined_elements"]:
                        valid_elems = [e for e in r["defined_elements"] if e]
                        if valid_elems:
                            fact += f" Defines: {', '.join(f'`{e}`' for e in valid_elems[:10])}."
                    if r["imports"]:
                        valid_imports = [i for i in r["imports"] if i]
                        if valid_imports:
                            fact += f" Imports: {', '.join(f'`{i}`' for i in valid_imports[:6])}."
                    graph_facts.append(fact)

        return graph_facts, referenced_files, referenced_symbols

    # ------------------------------------------------------------------
    # LLM Synthesis
    # ------------------------------------------------------------------

    def _synthesize_answer(
        self,
        query: str,
        graph_facts: list[str],
        retrieved_chunks: list[dict[str, Any]],
    ) -> str:
        """Call Gemini LLM with combined graph facts and code snippets."""
        prompt_parts: list[str] = [
            "You are an expert AI software architect and code intelligence assistant.",
            "You answer questions about the codebase using the provided knowledge graph relationships and semantic code snippets.",
            "",
            f"User Question: {query}",
            "",
        ]

        if graph_facts:
            prompt_parts.append("### Code Structure & Graph Relationships (from AST / Neo4j):")
            for fact in graph_facts:
                prompt_parts.append(f"- {fact}")
            prompt_parts.append("")

        if retrieved_chunks:
            prompt_parts.append("### Relevant Code Snippets (from Vector Search):")
            for chunk in retrieved_chunks:
                meta = chunk.get("metadata", {})
                fp = meta.get("file_path", "unknown")
                c_type = meta.get("chunk_type", "code")
                c_name = meta.get("name", "")
                l_start = meta.get("line_start", "")
                l_end = meta.get("line_end", "")
                text = chunk.get("text", "")
                prompt_parts.append(f"```\n// File: {fp} (lines {l_start}-{l_end}) | {c_type}: {c_name}\n{text}\n```\n")

        prompt_parts.extend([
            "### Instructions:",
            "1. Provide a direct, crystal-clear, and technically accurate explanation.",
            "2. Always reference exact file paths and line numbers when discussing functions, classes, or logic.",
            "3. Explain call sequences, inheritance chains, and architectural responsibilities clearly.",
            "4. If code examples help explain the flow, use clean markdown code blocks.",
            "5. If the provided context is insufficient to fully answer certain details, state what is known and note any missing parts honestly.",
        ])

        full_prompt = "\n".join(prompt_parts)

        # Call LLM via GeminiProvider or google.genai fallback
        try:
            from app.llm.providers.gemini import GeminiProvider
            provider = GeminiProvider()
            answer = provider.generate_chat_completion(prompt=full_prompt, temperature=0.1)
            return answer
        except Exception as exc:
            log.warning("gemini_provider_error_trying_direct_client", error=str(exc))
            try:
                from google import genai
                client = genai.Client(api_key=self.settings.gemini_api_key)
                response = client.models.generate_content(
                    model=getattr(self.settings, "gemini_model", "gemini-2.5-flash") or "gemini-2.5-flash",
                    contents=full_prompt,
                )
                return response.text or "Unable to generate code explanation."
            except Exception as final_exc:
                log.error("llm_synthesis_failed", error=str(final_exc))
                return (
                    f"### Graph Structure Found:\n"
                    + "\n".join(f"- {f}" for f in graph_facts)
                    + f"\n\n*(LLM generation error: {str(final_exc)})*"
                )

    # ------------------------------------------------------------------
    # Public Query Method
    # ------------------------------------------------------------------

    def query(
        self,
        question: str,
        repo_id: str,
        tenant_id: str,
        n_chunks: int = 8,
    ) -> CodeQueryResult:
        """Answer a code question using GraphRAG (Neo4j graph + ChromaDB vector search)."""
        log.info("graphrag_query_started", question=question, repo_id=repo_id, tenant_id=tenant_id)

        # 1. Extract entities from the question
        entities = self._extract_entities(question)
        log.info("entities_extracted", entities=entities)

        # 2. Graph traversal in Neo4j
        graph_facts, ref_files, ref_symbols = self._traverse_graph(repo_id, entities)

        # 3. Vector search in ChromaDB
        retrieved_chunks = self.vector_writer.search_code(
            tenant_id=tenant_id,
            repo_id=repo_id,
            query=question,
            n_results=n_chunks,
        )

        # Sort chunks to prioritize real code functions and classes first
        retrieved_chunks.sort(
            key=lambda c: 0 if c.get("metadata", {}).get("chunk_type") in ("function", "class") else 1
        )

        # Add files & symbols found in vector chunks to referenced sets
        for chunk in retrieved_chunks:
            meta = chunk.get("metadata", {})
            if "file_path" in meta and meta["file_path"]:
                ref_files.add(meta["file_path"])
            if "name" in meta and meta["name"] and meta["name"] != "module_header":
                ref_symbols.add(meta["name"])

        # 4. If no graph facts found yet, search graph for entities extracted from vector results
        if not graph_facts and retrieved_chunks:
            chunk_entities = [
                chunk.get("metadata", {}).get("name")
                for chunk in retrieved_chunks
                if chunk.get("metadata", {}).get("name")
            ]
            additional_entities = [e for e in chunk_entities if e and e != "module_header"][:3]
            if additional_entities:
                more_facts, more_files, more_symbols = self._traverse_graph(repo_id, additional_entities)
                graph_facts.extend(more_facts)
                ref_files.update(more_files)
                ref_symbols.update(more_symbols)

        # 5. Synthesize answer with LLM
        answer = self._synthesize_answer(
            query=question,
            graph_facts=graph_facts,
            retrieved_chunks=retrieved_chunks,
        )

        result = CodeQueryResult(
            query=question,
            repo_id=repo_id,
            answer=answer,
            referenced_files=sorted(list(ref_files)),
            referenced_symbols=sorted(list(ref_symbols)),
            graph_facts=graph_facts,
            retrieved_chunks=retrieved_chunks,
        )

        log.info(
            "graphrag_query_completed",
            repo_id=repo_id,
            referenced_files_count=len(result.referenced_files),
            referenced_symbols_count=len(result.referenced_symbols),
        )
        return result
