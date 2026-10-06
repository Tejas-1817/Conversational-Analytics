"""Parse source code into AST nodes using tree-sitter.

Extracts classes, functions, imports, and call relationships
from Python, TypeScript, JavaScript, and Java files.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import structlog
import tree_sitter

log = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Language grammar loaders
# ---------------------------------------------------------------------------

def _get_language(lang_name: str) -> tree_sitter.Language | None:
    """Load a tree-sitter language grammar.

    Since tree-sitter-languages doesn't support Python 3.13,
    we use individual language packages instead.
    """
    try:
        if lang_name == "python":
            import tree_sitter_python
            return tree_sitter.Language(tree_sitter_python.language())
        elif lang_name in ("typescript", "tsx"):
            import tree_sitter_typescript
            return tree_sitter.Language(tree_sitter_typescript.language_typescript())
        elif lang_name in ("javascript", "jsx"):
            import tree_sitter_javascript
            return tree_sitter.Language(tree_sitter_javascript.language())
        elif lang_name == "java":
            import tree_sitter_java
            return tree_sitter.Language(tree_sitter_java.language())
        else:
            log.debug("unsupported_language", language=lang_name)
            return None
    except ImportError:
        log.warning("language_grammar_not_installed", language=lang_name)
        return None


# ---------------------------------------------------------------------------
# Node types per language
# ---------------------------------------------------------------------------

# Maps language -> (class_node_type, function_node_type, import_node_types)
LANGUAGE_NODE_TYPES: dict[str, dict[str, list[str]]] = {
    "python": {
        "class": ["class_definition"],
        "function": ["function_definition"],
        "import": ["import_statement", "import_from_statement"],
        "call": ["call"],
    },
    "typescript": {
        "class": ["class_declaration"],
        "function": ["function_declaration", "method_definition", "arrow_function"],
        "import": ["import_statement"],
        "call": ["call_expression"],
    },
    "javascript": {
        "class": ["class_declaration"],
        "function": ["function_declaration", "method_definition", "arrow_function"],
        "import": ["import_statement"],
        "call": ["call_expression"],
    },
    "java": {
        "class": ["class_declaration", "interface_declaration"],
        "function": ["method_declaration", "constructor_declaration"],
        "import": ["import_declaration"],
        "call": ["method_invocation"],
    },
}


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class ClassInfo:
    name: str
    file_path: str
    line_start: int
    line_end: int
    docstring: str = ""
    bases: list[str] = field(default_factory=list)
    methods: list[str] = field(default_factory=list)


@dataclass
class FunctionInfo:
    name: str
    file_path: str
    line_start: int
    line_end: int
    docstring: str = ""
    params: list[str] = field(default_factory=list)
    return_type: str = ""
    is_method: bool = False
    parent_class: str = ""


@dataclass
class ImportInfo:
    module_path: str
    names: list[str] = field(default_factory=list)
    alias: str = ""
    file_path: str = ""


@dataclass
class CallInfo:
    caller: str
    callee: str
    file_path: str
    line: int


@dataclass
class ParseResult:
    """Complete parsed output for a single source file."""
    file_path: str
    language: str
    classes: list[ClassInfo] = field(default_factory=list)
    functions: list[FunctionInfo] = field(default_factory=list)
    imports: list[ImportInfo] = field(default_factory=list)
    calls: list[CallInfo] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

class ASTParser:
    """Parse source code files using tree-sitter and extract structural information."""

    def __init__(self) -> None:
        self._parsers: dict[str, tree_sitter.Parser] = {}

    def parse_file(self, file_path: str, content: str, language: str) -> ParseResult | None:
        """Parse a source file and extract classes, functions, imports, and calls.

        Returns None if the language is not supported.
        """
        parser = self._get_parser(language)
        if parser is None:
            return None

        node_types = LANGUAGE_NODE_TYPES.get(language)
        if node_types is None:
            return None

        tree = parser.parse(content.encode("utf-8"))
        result = ParseResult(file_path=file_path, language=language)

        self._walk_tree(
            node=tree.root_node,
            content=content,
            file_path=file_path,
            language=language,
            node_types=node_types,
            result=result,
            parent_class=None,
        )

        log.debug(
            "file_parsed",
            path=file_path,
            classes=len(result.classes),
            functions=len(result.functions),
            imports=len(result.imports),
            calls=len(result.calls),
        )
        return result

    # ------------------------------------------------------------------
    # Tree walking
    # ------------------------------------------------------------------

    def _walk_tree(
        self,
        node: tree_sitter.Node,
        content: str,
        file_path: str,
        language: str,
        node_types: dict,
        result: ParseResult,
        parent_class: str | None,
    ) -> None:
        """Recursively walk the AST and extract information."""

        # --- Class definitions ---
        if node.type in node_types["class"]:
            class_info = self._extract_class(node, content, file_path, language)
            if class_info:
                result.classes.append(class_info)
                # Walk children with class context
                for child in node.children:
                    self._walk_tree(
                        child, content, file_path, language,
                        node_types, result, parent_class=class_info.name,
                    )
                return  # Don't double-walk children

        # --- Function definitions ---
        elif node.type in node_types["function"]:
            func_info = self._extract_function(
                node, content, file_path, language, parent_class,
            )
            if func_info:
                result.functions.append(func_info)

                # If it's a method, record it on the parent class
                if parent_class:
                    for cls in result.classes:
                        if cls.name == parent_class:
                            cls.methods.append(func_info.name)

                # Extract calls within this function
                calls = self._extract_calls(
                    node, content, file_path, language,
                    caller_name=func_info.name, node_types=node_types,
                )
                result.calls.extend(calls)

        # --- Import statements ---
        elif node.type in node_types["import"]:
            import_info = self._extract_import(node, content, file_path, language)
            if import_info:
                result.imports.append(import_info)

        # Recurse into children
        for child in node.children:
            self._walk_tree(
                child, content, file_path, language,
                node_types, result, parent_class,
            )

    # ------------------------------------------------------------------
    # Extractors
    # ------------------------------------------------------------------

    def _extract_class(
        self, node: tree_sitter.Node, content: str, file_path: str, language: str,
    ) -> ClassInfo | None:
        """Extract class name, bases, and docstring."""
        name_node = node.child_by_field_name("name")
        if not name_node:
            return None

        name = self._node_text(name_node, content)
        bases: list[str] = []

        # Extract base classes (Python: argument_list, Java/TS: superclass)
        if language == "python":
            for child in node.children:
                if child.type == "argument_list":
                    for arg in child.children:
                        if arg.type == "identifier":
                            bases.append(self._node_text(arg, content))
                        elif arg.type == "attribute":
                            bases.append(self._node_text(arg, content))

        elif language in ("typescript", "javascript", "java"):
            for child in node.children:
                if child.type in ("class_heritage", "superclass", "super_interfaces"):
                    for sub in child.children:
                        if sub.type in ("identifier", "type_identifier"):
                            bases.append(self._node_text(sub, content))

        docstring = self._extract_docstring(node, content, language)

        return ClassInfo(
            name=name,
            file_path=file_path,
            line_start=node.start_point[0] + 1,
            line_end=node.end_point[0] + 1,
            docstring=docstring,
            bases=bases,
        )

    def _extract_function(
        self,
        node: tree_sitter.Node,
        content: str,
        file_path: str,
        language: str,
        parent_class: str | None,
    ) -> FunctionInfo | None:
        """Extract function name, parameters, return type, and docstring."""
        name_node = node.child_by_field_name("name")
        if not name_node:
            return None

        name = self._node_text(name_node, content)
        params: list[str] = []
        return_type = ""

        # Extract parameters
        params_node = node.child_by_field_name("parameters")
        if params_node:
            for child in params_node.children:
                if child.type in ("identifier", "typed_parameter",
                                  "formal_parameter", "required_parameter",
                                  "optional_parameter"):
                    param_name_node = child.child_by_field_name("name") or child
                    if param_name_node.type == "identifier":
                        param_text = self._node_text(param_name_node, content)
                        if param_text != "self" and param_text != "cls":
                            params.append(param_text)

        # Extract return type (Python: -> annotation)
        return_node = node.child_by_field_name("return_type")
        if return_node:
            return_type = self._node_text(return_node, content)

        docstring = self._extract_docstring(node, content, language)

        return FunctionInfo(
            name=name,
            file_path=file_path,
            line_start=node.start_point[0] + 1,
            line_end=node.end_point[0] + 1,
            docstring=docstring,
            params=params,
            return_type=return_type,
            is_method=parent_class is not None,
            parent_class=parent_class or "",
        )

    def _extract_import(
        self, node: tree_sitter.Node, content: str, file_path: str, language: str,
    ) -> ImportInfo | None:
        """Extract import module path and imported names."""
        full_text = self._node_text(node, content).strip()

        if language == "python":
            return self._parse_python_import(full_text, file_path)
        elif language in ("typescript", "javascript"):
            return self._parse_ts_import(full_text, file_path)
        elif language == "java":
            return self._parse_java_import(full_text, file_path)

        return ImportInfo(module_path=full_text, file_path=file_path)

    def _extract_calls(
        self,
        func_node: tree_sitter.Node,
        content: str,
        file_path: str,
        language: str,
        caller_name: str,
        node_types: dict,
    ) -> list[CallInfo]:
        """Find all function/method calls within a function body."""
        calls: list[CallInfo] = []
        call_types = node_types.get("call", [])

        def _find_calls(node: tree_sitter.Node) -> None:
            if node.type in call_types:
                callee = self._extract_call_name(node, content, language)
                if callee and callee != caller_name:  # skip self-recursion noise
                    calls.append(CallInfo(
                        caller=caller_name,
                        callee=callee,
                        file_path=file_path,
                        line=node.start_point[0] + 1,
                    ))
            for child in node.children:
                _find_calls(child)

        # Walk function body only
        body_node = func_node.child_by_field_name("body")
        if body_node:
            _find_calls(body_node)
        else:
            # Some languages don't have a "body" field — walk all children
            for child in func_node.children:
                _find_calls(child)

        return calls

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _extract_call_name(
        self, call_node: tree_sitter.Node, content: str, language: str,
    ) -> str:
        """Extract the function/method name from a call expression."""
        if language == "python":
            func_node = call_node.child_by_field_name("function")
        elif language == "java":
            func_node = call_node.child_by_field_name("name")
        else:
            func_node = call_node.child_by_field_name("function")

        if func_node is None:
            return ""

        # Simple call: foo()
        if func_node.type == "identifier":
            return self._node_text(func_node, content)

        # Method call: obj.method()
        if func_node.type in ("attribute", "member_expression"):
            attr_node = func_node.child_by_field_name("attribute") or \
                        func_node.child_by_field_name("property")
            if attr_node:
                return self._node_text(attr_node, content)

        return self._node_text(func_node, content)

    def _extract_docstring(
        self, node: tree_sitter.Node, content: str, language: str,
    ) -> str:
        """Extract docstring from a class or function node."""
        if language == "python":
            body = node.child_by_field_name("body")
            if body and body.children:
                first = body.children[0]
                if first.type == "expression_statement" and first.children:
                    string_node = first.children[0]
                    if string_node.type == "string":
                        raw = self._node_text(string_node, content)
                        return raw.strip("\"'").strip()

        elif language in ("typescript", "javascript", "java"):
            # Look for comment node immediately preceding
            idx = node.parent.children.index(node) if node.parent else -1
            if idx > 0:
                prev = node.parent.children[idx - 1]
                if prev.type == "comment":
                    return self._node_text(prev, content).strip("/* \n")

        return ""

    def _get_parser(self, language: str) -> tree_sitter.Parser | None:
        """Get or create a parser for the given language."""
        if language in self._parsers:
            return self._parsers[language]

        lang = _get_language(language)
        if lang is None:
            return None

        parser = tree_sitter.Parser(lang)
        self._parsers[language] = parser
        return parser

    @staticmethod
    def _node_text(node: tree_sitter.Node, content: str) -> str:
        """Get the source text for a tree-sitter node."""
        return content[node.start_byte:node.end_byte]

    # ------------------------------------------------------------------
    # Python import parsing
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_python_import(text: str, file_path: str) -> ImportInfo:
        """Parse 'from x.y import z, w' or 'import x.y'."""
        if text.startswith("from "):
            parts = text.split(" import ", 1)
            module = parts[0].replace("from ", "").strip()
            names = []
            if len(parts) > 1:
                names = [n.strip() for n in parts[1].split(",")]
            return ImportInfo(module_path=module, names=names, file_path=file_path)
        else:
            module = text.replace("import ", "").strip()
            return ImportInfo(module_path=module, file_path=file_path)

    @staticmethod
    def _parse_ts_import(text: str, file_path: str) -> ImportInfo:
        """Parse TypeScript/JS import statements."""
        # import { x, y } from 'module'
        if "from" in text:
            parts = text.split("from", 1)
            module = parts[1].strip().strip("'\"; ")
            return ImportInfo(module_path=module, file_path=file_path)
        return ImportInfo(module_path=text, file_path=file_path)

    @staticmethod
    def _parse_java_import(text: str, file_path: str) -> ImportInfo:
        """Parse Java import declarations."""
        # import com.example.ClassName;
        module = text.replace("import ", "").replace("static ", "").strip("; ")
        return ImportInfo(module_path=module, file_path=file_path)
