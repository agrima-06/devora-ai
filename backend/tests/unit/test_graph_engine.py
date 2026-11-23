"""Unit tests for Phase 10 Stage 10.1: Graph Engine and Symbol Resolution."""
import hashlib
import pytest
from app.services.graph_builder import (
    GraphExtractor,
    RawImport,
    resolve_js_ts_module_path,
    resolve_python_module_path,
)


def test_python_ast_symbol_extraction():
    """Verify that Python AST extracts classes, methods, functions, and constants with qualified names."""
    code = '''"""Test module for calculator."""
MAX_PRECISION = 10

class BaseEngine:
    """Base mathematical engine."""
    pass

class MathEngine(BaseEngine):
    """Core calculator."""

    def __init__(self, precision: int = 2):
        self.precision = precision

    def add(self, a: float, b: float) -> float:
        """Add two numbers."""
        return a + b

def calculate_average(values: list) -> float:
    """Calculate mean of numbers."""
    return sum(values) / len(values)
'''
    extractor = GraphExtractor()
    symbols, imports, calls, valid, err = extractor.parse_python(code, "src/calculator.py")

    assert valid is True
    assert err is None

    # Check constants
    constant_syms = [s for s in symbols if s.node_type == "CONSTANT"]
    assert len(constant_syms) == 1
    assert constant_syms[0].name == "MAX_PRECISION"
    assert constant_syms[0].qualified_name == "src/calculator.py:MAX_PRECISION"

    # Check classes
    class_syms = [s for s in symbols if s.node_type == "CLASS"]
    assert len(class_syms) == 2
    class_names = [s.name for s in class_syms]
    assert "BaseEngine" in class_names
    assert "MathEngine" in class_names

    math_engine = next(s for s in class_syms if s.name == "MathEngine")
    assert math_engine.qualified_name == "src/calculator.py:MathEngine"
    assert "BaseEngine" in math_engine.metadata.get("bases", [])

    # Check methods
    method_syms = [s for s in symbols if s.node_type == "METHOD"]
    assert len(method_syms) == 2
    method_qnames = [s.qualified_name for s in method_syms]
    assert "src/calculator.py:MathEngine.__init__" in method_qnames
    assert "src/calculator.py:MathEngine.add" in method_qnames

    # Check functions
    func_syms = [s for s in symbols if s.node_type == "FUNCTION"]
    assert len(func_syms) == 1
    assert func_syms[0].name == "calculate_average"
    assert func_syms[0].qualified_name == "src/calculator.py:calculate_average"


def test_python_import_extraction_and_resolution():
    """Verify that Python imports resolve to local relative files, standard libraries, or external packages."""
    repo_files = {
        "src/calculator.py",
        "src/utils.py",
        "src/engine/__init__.py",
        "src/engine/matrix.py",
        "tests/test_calculator.py",
    }

    # 1. Relative import in tests/test_calculator.py
    imp_relative = RawImport(
        file_path="src/calculator.py",
        module_str="utils",
        imported_symbols=["format_number"],
        is_relative=True,
        relative_level=1,
    )
    resolved_path, status = resolve_python_module_path("src/calculator.py", imp_relative, repo_files)
    assert status == "RESOLVED"
    assert resolved_path == "src/utils.py"

    # 2. Submodule relative import
    imp_submodule = RawImport(
        file_path="src/calculator.py",
        module_str="engine.matrix",
        imported_symbols=["Matrix"],
        is_relative=True,
        relative_level=1,
    )
    resolved_path, status = resolve_python_module_path("src/calculator.py", imp_submodule, repo_files)
    assert status == "RESOLVED"
    assert resolved_path == "src/engine/matrix.py"

    # 3. Absolute repo import
    imp_abs = RawImport(
        file_path="tests/test_calculator.py",
        module_str="src.calculator",
        imported_symbols=["MathEngine"],
        is_relative=False,
        relative_level=0,
    )
    resolved_path, status = resolve_python_module_path("tests/test_calculator.py", imp_abs, repo_files)
    assert status == "RESOLVED"
    assert resolved_path == "src/calculator.py"

    # 4. Standard library import (EXTERNAL)
    imp_stdlib = RawImport(
        file_path="src/calculator.py",
        module_str="math",
        imported_symbols=["sqrt"],
        is_relative=False,
    )
    _, status = resolve_python_module_path("src/calculator.py", imp_stdlib, repo_files)
    assert status == "EXTERNAL"

    # 5. Third-party library import (EXTERNAL)
    imp_third_party = RawImport(
        file_path="src/calculator.py",
        module_str="fastapi",
        imported_symbols=["APIRouter"],
        is_relative=False,
    )
    _, status = resolve_python_module_path("src/calculator.py", imp_third_party, repo_files)
    assert status == "EXTERNAL"

    # 6. Unresolved local import
    imp_missing = RawImport(
        file_path="src/calculator.py",
        module_str="src.nonexistent",
        imported_symbols=["Missing"],
        is_relative=False,
    )
    _, status = resolve_python_module_path("src/calculator.py", imp_missing, repo_files)
    assert status == "UNRESOLVED"


def test_js_ts_import_resolution():
    """Verify JavaScript/TypeScript import path resolution with extension probing."""
    repo_files = {
        "src/index.ts",
        "src/formatter.ts",
        "src/components/button.tsx",
        "src/utils/index.js",
    }

    # Relative ./formatter -> src/formatter.ts
    imp_ts = RawImport(
        file_path="src/index.ts",
        module_str="./formatter",
        imported_symbols=["formatResult"],
        is_relative=True,
    )
    resolved_path, status = resolve_js_ts_module_path("src/index.ts", imp_ts, repo_files)
    assert status == "RESOLVED"
    assert resolved_path == "src/formatter.ts"

    # Relative ./components/button -> src/components/button.tsx
    imp_tsx = RawImport(
        file_path="src/index.ts",
        module_str="./components/button",
        imported_symbols=["Button"],
        is_relative=True,
    )
    resolved_path, status = resolve_js_ts_module_path("src/index.ts", imp_tsx, repo_files)
    assert status == "RESOLVED"
    assert resolved_path == "src/components/button.tsx"

    # External package -> EXTERNAL
    imp_ext = RawImport(
        file_path="src/index.ts",
        module_str="react",
        imported_symbols=["useState"],
        is_relative=False,
    )
    _, status = resolve_js_ts_module_path("src/index.ts", imp_ext, repo_files)
    assert status == "EXTERNAL"


def test_content_hash_integrity():
    """Content hashes must be deterministic and sensitive to edits."""
    code_v1 = b"def hello(): return 'world'\n"
    code_v2 = b"def hello(): return 'devora'\n"

    h1 = hashlib.sha256(code_v1).hexdigest()
    h1_repeat = hashlib.sha256(code_v1).hexdigest()
    h2 = hashlib.sha256(code_v2).hexdigest()

    assert h1 == h1_repeat
    assert h1 != h2
    assert len(h1) == 64


def test_malformed_syntax_graceful_handling():
    """Syntax errors in user source code must not crash the parser and must mark syntax_valid=False."""
    bad_code = "def broken_func(:\n    return 42\n"
    extractor = GraphExtractor()
    symbols, imports, calls, valid, err = extractor.parse_python(bad_code, "src/broken.py")

    assert valid is False
    assert err is not None
    assert "SyntaxError" in err
    assert len(symbols) == 0
