"""Graph Extraction and Multi-Language Resolution Engine for Devora AI."""
import ast
import hashlib
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from app.core.logging import get_logger
from app.services.parser_service import TS_PARSERS, CodeParserService

logger = get_logger("graph_builder")

# Standard Python libraries to classify as EXTERNAL
PYTHON_STDLIB: Set[str] = {
    "os", "sys", "re", "math", "json", "typing", "datetime", "time", "pathlib",
    "uuid", "hashlib", "asyncio", "subprocess", "tempfile", "unittest", "logging",
    "collections", "itertools", "functools", "copy", "shutil", "glob", "fnmatch",
    "io", "traceback", "inspect", "enum", "dataclasses", "abc", "contextlib",
    "socket", "ssl", "http", "urllib", "email", "threading", "multiprocessing",
    "concurrent", "queue", "csv", "xml", "html", "pickle", "sqlite3", "base64",
    "binascii", "struct", "platform", "argparse", "weakref", "warnings",
}


class RawSymbol:
    """Represents an extracted code entity before persistence."""
    def __init__(
        self,
        node_type: str,
        name: str,
        qualified_name: str,
        file_path: str,
        language: str,
        start_line: Optional[int] = None,
        end_line: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
        parent_name: Optional[str] = None,
    ):
        self.node_type = node_type
        self.name = name
        self.qualified_name = qualified_name
        self.file_path = file_path
        self.language = language
        self.start_line = start_line
        self.end_line = end_line
        self.metadata = metadata or {}
        self.parent_name = parent_name


class RawImport:
    """Represents an import statement extracted from a file."""
    def __init__(
        self,
        file_path: str,
        module_str: str,
        imported_symbols: List[str],
        is_relative: bool = False,
        relative_level: int = 0,
        alias: Optional[str] = None,
        line_number: Optional[int] = None,
        raw_statement: str = "",
    ):
        self.file_path = file_path
        self.module_str = module_str
        self.imported_symbols = imported_symbols
        self.is_relative = is_relative
        self.relative_level = relative_level
        self.alias = alias
        self.line_number = line_number
        self.raw_statement = raw_statement


class RawCall:
    """Represents an invocation of a function or method."""
    def __init__(
        self,
        source_symbol_qname: str,
        target_name: str,
        file_path: str,
        line_number: Optional[int] = None,
    ):
        self.source_symbol_qname = source_symbol_qname
        self.target_name = target_name
        self.file_path = file_path
        self.line_number = line_number


class PythonGraphVisitor(ast.NodeVisitor):
    """AST visitor generating detailed node definitions, imports, and calls for Python source."""

    def __init__(self, file_path: str):
        self.file_path = file_path
        self.symbols: List[RawSymbol] = []
        self.imports: List[RawImport] = []
        self.calls: List[RawCall] = []
        self.current_scope: List[str] = []  # Stack of class/function names

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            self.imports.append(
                RawImport(
                    file_path=self.file_path,
                    module_str=alias.name,
                    imported_symbols=[],
                    is_relative=False,
                    relative_level=0,
                    alias=alias.asname,
                    line_number=node.lineno,
                    raw_statement=ast.unparse(node),
                )
            )
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        module = node.module or ""
        symbols = [alias.name for alias in node.names]
        self.imports.append(
            RawImport(
                file_path=self.file_path,
                module_str=module,
                imported_symbols=symbols,
                is_relative=node.level > 0,
                relative_level=node.level,
                line_number=node.lineno,
                raw_statement=ast.unparse(node),
            )
        )
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef):
        parent_class = self.current_scope[-1] if self.current_scope else None
        qname = f"{self.file_path}:{node.name}" if not parent_class else f"{self.file_path}:{parent_class}.{node.name}"
        bases = [ast.unparse(b) for b in node.bases]
        docstring = ast.get_docstring(node) or ""

        self.symbols.append(
            RawSymbol(
                node_type="CLASS",
                name=node.name,
                qualified_name=qname,
                file_path=self.file_path,
                language="Python",
                start_line=node.lineno,
                end_line=getattr(node, "end_lineno", node.lineno),
                metadata={
                    "bases": bases,
                    "docstring": docstring,
                    "signature": f"class {node.name}({', '.join(bases)})" if bases else f"class {node.name}",
                },
                parent_name=parent_class,
            )
        )

        self.current_scope.append(node.name)
        self.generic_visit(node)
        self.current_scope.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self._record_func(node, is_async=False)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        self._record_func(node, is_async=True)

    def _record_func(self, node: Any, is_async: bool):
        is_method = len(self.current_scope) > 0
        parent = self.current_scope[-1] if is_method else None
        sym_type = "METHOD" if is_method else "FUNCTION"

        if is_method:
            qname = f"{self.file_path}:{parent}.{node.name}"
        else:
            qname = f"{self.file_path}:{node.name}"

        args = [arg.arg for arg in node.args.args]
        return_type = ast.unparse(node.returns) if node.returns else ""
        docstring = ast.get_docstring(node) or ""
        prefix = "async def" if is_async else "def"
        sig = f"{prefix} {node.name}({', '.join(args)})"
        if return_type:
            sig += f" -> {return_type}"

        self.symbols.append(
            RawSymbol(
                node_type=sym_type,
                name=node.name,
                qualified_name=qname,
                file_path=self.file_path,
                language="Python",
                start_line=node.lineno,
                end_line=getattr(node, "end_lineno", node.lineno),
                metadata={
                    "signature": sig,
                    "docstring": docstring,
                    "is_async": is_async,
                    "arguments": args,
                    "return_type": return_type,
                },
                parent_name=parent,
            )
        )

        self.current_scope.append(node.name)
        self.generic_visit(node)
        self.current_scope.pop()

    def visit_Call(self, node: ast.Call):
        scope_qname = (
            f"{self.file_path}:{'.'.join(self.current_scope)}"
            if self.current_scope
            else self.file_path
        )
        try:
            target_name = None
            if isinstance(node.func, ast.Name):
                target_name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                target_name = node.func.attr
            if target_name:
                self.calls.append(
                    RawCall(
                        source_symbol_qname=scope_qname,
                        target_name=target_name,
                        file_path=self.file_path,
                        line_number=node.lineno,
                    )
                )
        except Exception:
            pass
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign):
        # Top-level constant extraction
        if not self.current_scope:
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id.isupper():
                    qname = f"{self.file_path}:{target.id}"
                    val_str = ""
                    try:
                        val_str = ast.unparse(node.value)
                    except Exception:
                        pass
                    self.symbols.append(
                        RawSymbol(
                            node_type="CONSTANT",
                            name=target.id,
                            qualified_name=qname,
                            file_path=self.file_path,
                            language="Python",
                            start_line=node.lineno,
                            end_line=getattr(node, "end_lineno", node.lineno),
                            metadata={"value_preview": val_str[:100]},
                        )
                    )
        self.generic_visit(node)


class GraphExtractor:
    """Extracts symbols, declarations, imports, and calls across repository files."""

    def __init__(self, parser_service: Optional[CodeParserService] = None):
        self.parser_service = parser_service or CodeParserService()

    def parse_python(self, content_str: str, file_path: str) -> Tuple[List[RawSymbol], List[RawImport], List[RawCall], bool, Optional[str]]:
        """Parse Python source using Python AST visitor."""
        try:
            tree = ast.parse(content_str, filename=file_path)
            visitor = PythonGraphVisitor(file_path=file_path)
            visitor.visit(tree)
            return visitor.symbols, visitor.imports, visitor.calls, True, None
        except SyntaxError as e:
            logger.debug("python_syntax_error", file=file_path, line=e.lineno, error=str(e))
            return [], [], [], False, f"SyntaxError at line {e.lineno}: {e.msg}"
        except Exception as e:
            logger.debug("python_parse_failed", file=file_path, error=str(e))
            return [], [], [], False, str(e)

    def parse_treesitter_generic(
        self,
        content_bytes: bytes,
        language: str,
        file_path: str,
    ) -> Tuple[List[RawSymbol], List[RawImport], List[RawCall], bool, Optional[str]]:
        """Extract symbols and imports using Tree-sitter for TS, JS, Go, Java."""
        parser = TS_PARSERS.get(language)
        if not parser:
            return [], [], [], False, f"No Tree-sitter parser available for language {language}"

        try:
            tree = parser.parse(content_bytes)
            symbols: List[RawSymbol] = []
            imports: List[RawImport] = []
            calls: List[RawCall] = []

            lines = content_bytes.splitlines()

            def get_text(node):
                return content_bytes[node.start_byte : node.end_byte].decode("utf-8", errors="ignore")

            def traverse(node, current_class=None):
                node_type = node.type

                # JavaScript / TypeScript
                if node_type in {"class_declaration", "interface_declaration"}:
                    name_node = node.child_by_field_name("name")
                    if name_node:
                        c_name = get_text(name_node)
                        qname = f"{file_path}:{c_name}"
                        sym_type = "CLASS" if node_type == "class_declaration" else "INTERFACE"
                        symbols.append(
                            RawSymbol(
                                node_type=sym_type,
                                name=c_name,
                                qualified_name=qname,
                                file_path=file_path,
                                language=language,
                                start_line=node.start_point[0] + 1,
                                end_line=node.end_point[0] + 1,
                                metadata={"signature": f"{sym_type.lower()} {c_name}"},
                            )
                        )
                        for child in node.children:
                            traverse(child, current_class=c_name)
                        return

                elif node_type in {"function_declaration", "arrow_function", "method_definition"}:
                    name_node = node.child_by_field_name("name")
                    name = get_text(name_node) if name_node else "anonymous"
                    is_method = current_class is not None or node_type == "method_definition"
                    qname = f"{file_path}:{current_class}.{name}" if current_class else f"{file_path}:{name}"
                    sym_type = "METHOD" if is_method else "FUNCTION"
                    sig = lines[node.start_point[0]].decode("utf-8", errors="ignore").strip() if node.start_point[0] < len(lines) else name

                    symbols.append(
                        RawSymbol(
                            node_type=sym_type,
                            name=name,
                            qualified_name=qname,
                            file_path=file_path,
                            language=language,
                            start_line=node.start_point[0] + 1,
                            end_line=node.end_point[0] + 1,
                            metadata={"signature": sig},
                            parent_name=current_class,
                        )
                    )

                elif node_type == "import_statement":
                    import_text = get_text(node).strip()
                    # e.g. import { formatResult } from './formatter';
                    module_match = ""
                    if "from" in import_text:
                        parts = import_text.split("from")
                        if len(parts) > 1:
                            module_match = parts[1].strip().strip(";'\"")
                    else:
                        module_match = import_text.replace("import", "").strip().strip(";'\"")

                    imports.append(
                        RawImport(
                            file_path=file_path,
                            module_str=module_match,
                            imported_symbols=[],
                            is_relative=module_match.startswith("."),
                            line_number=node.start_point[0] + 1,
                            raw_statement=import_text,
                        )
                    )

                # Go
                elif node_type == "function_declaration":
                    name_node = node.child_by_field_name("name")
                    if name_node:
                        name = get_text(name_node)
                        symbols.append(
                            RawSymbol(
                                node_type="FUNCTION",
                                name=name,
                                qualified_name=f"{file_path}:{name}",
                                file_path=file_path,
                                language="Go",
                                start_line=node.start_point[0] + 1,
                                end_line=node.end_point[0] + 1,
                                metadata={"signature": lines[node.start_point[0]].decode("utf-8", errors="ignore").strip()},
                            )
                        )

                elif node_type == "method_declaration":
                    name_node = node.child_by_field_name("name")
                    if name_node:
                        name = get_text(name_node)
                        symbols.append(
                            RawSymbol(
                                node_type="METHOD",
                                name=name,
                                qualified_name=f"{file_path}:{name}",
                                file_path=file_path,
                                language="Go",
                                start_line=node.start_point[0] + 1,
                                end_line=node.end_point[0] + 1,
                                metadata={"signature": lines[node.start_point[0]].decode("utf-8", errors="ignore").strip()},
                            )
                        )

                # Java
                elif node_type == "method_declaration":
                    name_node = node.child_by_field_name("name")
                    if name_node:
                        name = get_text(name_node)
                        symbols.append(
                            RawSymbol(
                                node_type="METHOD",
                                name=name,
                                qualified_name=f"{file_path}:{name}",
                                file_path=file_path,
                                language="Java",
                                start_line=node.start_point[0] + 1,
                                end_line=node.end_point[0] + 1,
                                metadata={"signature": lines[node.start_point[0]].decode("utf-8", errors="ignore").strip()},
                            )
                        )

                for child in node.children:
                    traverse(child, current_class=current_class)

            traverse(tree.root_node)
            return symbols, imports, calls, not tree.root_node.has_error, None

        except Exception as e:
            logger.debug("treesitter_parse_failed", file=file_path, error=str(e))
            return [], [], [], False, str(e)


def resolve_python_module_path(
    source_file_path: str,
    raw_import: RawImport,
    all_file_paths: Set[str],
) -> Tuple[Optional[str], str]:
    """Resolve Python module import to a concrete relative file path in the repository.
    Returns (resolved_file_path, resolution_status).
    """
    module_str = raw_import.module_str
    first_part = module_str.split(".")[0] if module_str else ""

    # 1. Check if standard library
    if not raw_import.is_relative and first_part in PYTHON_STDLIB:
        return None, "EXTERNAL"

    # 2. Relative import resolution (e.g. from .calculator import MathEngine)
    if raw_import.is_relative:
        source_dir = Path(source_file_path).parent
        # Go up `relative_level - 1` directories for dot count
        current_dir = source_dir
        for _ in range(raw_import.relative_level - 1):
            current_dir = current_dir.parent

        if module_str:
            target_rel = current_dir / module_str.replace(".", "/")
        else:
            target_rel = current_dir

        candidate_py = f"{target_rel}.py"
        candidate_init = f"{target_rel}/__init__.py"

        # Normalize relative path
        norm_py = os.path.normpath(candidate_py)
        norm_init = os.path.normpath(candidate_init)

        if norm_py in all_file_paths:
            return norm_py, "RESOLVED"
        if norm_init in all_file_paths:
            return norm_init, "RESOLVED"
        if str(target_rel) in all_file_paths:
            return str(target_rel), "RESOLVED"

        # Check if imported symbol is actually a module file (e.g. from . import calculator)
        for sym in raw_import.imported_symbols:
            candidate_sym = os.path.normpath(f"{current_dir}/{sym}.py")
            if candidate_sym in all_file_paths:
                return candidate_sym, "RESOLVED"

        return None, "UNRESOLVED"

    # 3. Absolute import from repository root (e.g. from src.calculator import MathEngine)
    module_path = module_str.replace(".", "/")
    candidate_py = f"{module_path}.py"
    candidate_init = f"{module_path}/__init__.py"

    if candidate_py in all_file_paths:
        return candidate_py, "RESOLVED"
    if candidate_init in all_file_paths:
        return candidate_init, "RESOLVED"

    # Check if first part is a known top-level directory in the repo
    top_dir = module_str.split(".")[0]
    has_top_dir = any(p.startswith(f"{top_dir}/") for p in all_file_paths)
    if not has_top_dir:
        # Third-party library (e.g. fastapi, pydantic, pytest)
        return None, "EXTERNAL"

    return None, "UNRESOLVED"


def resolve_js_ts_module_path(
    source_file_path: str,
    raw_import: RawImport,
    all_file_paths: Set[str],
) -> Tuple[Optional[str], str]:
    """Resolve JavaScript/TypeScript import to a concrete file path."""
    module_str = raw_import.module_str
    if not raw_import.is_relative and not module_str.startswith("."):
        # e.g. import React from 'react' -> EXTERNAL
        return None, "EXTERNAL"

    source_dir = Path(source_file_path).parent
    base_candidate = os.path.normpath(str(source_dir / module_str))

    extensions = [".ts", ".tsx", ".js", ".jsx", "/index.ts", "/index.tsx", "/index.js"]
    for ext in extensions:
        cand = f"{base_candidate}{ext}"
        if cand in all_file_paths:
            return cand, "RESOLVED"

    if base_candidate in all_file_paths:
        return base_candidate, "RESOLVED"

    return None, "UNRESOLVED"
