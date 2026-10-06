"""Unit tests for Code Intelligence (AST parsing, chunking, file walking, and GraphRAG retrieval)."""
import pytest
from app.code_intel.ast_parser import ASTParser
from app.code_intel.code_chunker import CodeChunker
from app.code_intel.file_walker import FileWalker


SAMPLE_PYTHON_CODE = '''"""Sample module for testing code intelligence."""
import os
from typing import List

class BaseService:
    """Base class for services."""
    def __init__(self, name: str):
        self.name = name

    def ping(self) -> bool:
        return True


class AuthService(BaseService):
    """Handles authentication and tokens."""
    def verify_token(self, token: str) -> bool:
        """Verify JWT signature."""
        if not token:
            return False
        return self.decode_jwt(token)

    def decode_jwt(self, raw_token: str) -> bool:
        """Decode raw token string."""
        return len(raw_token) > 5


def helper_function(x: int, y: int) -> int:
    """Add two numbers."""
    return x + y
'''


def test_ast_parser_python():
    parser = ASTParser()
    result = parser.parse_file("app/auth.py", SAMPLE_PYTHON_CODE, "python")

    assert result.file_path == "app/auth.py"
    assert result.language == "python"

    # Verify Classes
    class_names = [c.name for c in result.classes]
    assert "BaseService" in class_names
    assert "AuthService" in class_names

    auth_cls = next(c for c in result.classes if c.name == "AuthService")
    assert "BaseService" in auth_cls.bases
    assert "verify_token" in auth_cls.methods
    assert "decode_jwt" in auth_cls.methods

    # Verify Functions
    func_names = [f.name for f in result.functions]
    assert "verify_token" in func_names
    assert "decode_jwt" in func_names
    assert "helper_function" in func_names

    # Verify Calls
    caller_callees = [(c.caller, c.callee) for c in result.calls]
    assert ("verify_token", "decode_jwt") in caller_callees

    # Verify Imports
    imported_modules = [i.module_path for i in result.imports]
    assert "os" in imported_modules
    assert "typing" in imported_modules


def test_code_chunker():
    parser = ASTParser()
    result = parser.parse_file("app/auth.py", SAMPLE_PYTHON_CODE, "python")

    chunker = CodeChunker()
    chunks = chunker.chunk_file("app/auth.py", SAMPLE_PYTHON_CODE, "python", "repo_123", result)

    assert len(chunks) > 0
    chunk_types = {c.chunk_type for c in chunks}
    assert "function" in chunk_types
    assert "class" in chunk_types
    assert "module_header" in chunk_types

    # Ensure metadata contains file_path and repo_id
    for chunk in chunks:
        assert chunk.repo_id == "repo_123"
        assert chunk.file_path == "app/auth.py"
        assert chunk.text != ""


def test_file_walker_skip_rules():
    walker = FileWalker()
    assert walker.should_skip("node_modules/package/index.js") is True
    assert walker.should_skip(".git/config") is True
    assert walker.should_skip("__pycache__/main.cpython-313.pyc") is True
    assert walker.should_skip("package-lock.json") is True
    assert walker.should_skip("app/services/auth.py") is False
