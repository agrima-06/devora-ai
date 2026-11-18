"""Code parsing service: Python AST and Tree-sitter multi-language symbol and dependency extraction."""
import ast
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
from app.core.logging import get_logger

logger = get_logger("parser_service")

# Try initializing Tree-sitter grammars
TREE_SITTER_AVAILABLE = False
TS_PARSERS: Dict[str, Any] = {}

try:
    import tree_sitter
    import tree_sitter_python
    import tree_sitter_javascript
    import tree_sitter_typescript
    import tree_sitter_go
    import tree_sitter_java

    TS_PARSERS["Python"] = tree_sitter.Parser(tree_sitter.Language(tree_sitter_python.language()))
    TS_PARSERS["JavaScript"] = tree_sitter.Parser(tree_sitter.Language(tree_sitter_javascript.language()))
    TS_PARSERS["TypeScript"] = tree_sitter.Parser(tree_sitter.Language(tree_sitter_typescript.language_typescript()))
    TS_PARSERS["TypeScript (React)"] = tree_sitter.Parser(tree_sitter.Language(tree_sitter_typescript.language_tsx()))
    TS_PARSERS["Go"] = tree_sitter.Parser(tree_sitter.Language(tree_sitter_go.language()))
    TS_PARSERS["Java"] = tree_sitter.Parser(tree_sitter.Language(tree_sitter_java.language()))

    TREE_SITTER_AVAILABLE = True
except Exception as e:
    logger.warning("treesitter_init_failed", error=str(e))


class PythonASTVisitor(ast.NodeVisitor):
    """AST visitor extracting structural symbols and dependencies from Python source."""

    def __init__(self):
        self.symbols: List[Dict[str, Any]] = []
        self.imports: List[str] = []
        self.calls: Set[str] = set()
        self.current_class: Optional[str] = None

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            self.imports.append(alias.name)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        module = node.module or ""
        for alias in node.names:
            full_name = f"{module}.{alias.name}" if module else alias.name
            self.imports.append(full_name)
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef):
        bases = [ast.unparse(b) for b in node.bases]
        docstring = ast.get_docstring(node)
        self.symbols.append({
            "name": node.name,
            "type": "class",
            "start_line": node.lineno,
            "end_line": getattr(node, "end_lineno", node.lineno),
            "signature": f"class {node.name}({', '.join(bases)})" if bases else f"class {node.name}",
            "docstring": docstring or "",
            "parent": self.current_class,
        })
        prev_class = self.current_class
        self.current_class = node.name
        self.generic_visit(node)
        self.current_class = prev_class

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self._record_function(node, is_async=False)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        self._record_function(node, is_async=True)

    def _record_function(self, node: Any, is_async: bool):
        args = [arg.arg for arg in node.args.args]
        return_type = ast.unparse(node.returns) if node.returns else ""
        docstring = ast.get_docstring(node)
        prefix = "async def" if is_async else "def"
        sig = f"{prefix} {node.name}({', '.join(args)})"
        if return_type:
            sig += f" -> {return_type}"

        sym_type = "method" if self.current_class else "function"
        full_name = f"{self.current_class}.{node.name}" if self.current_class else node.name

        self.symbols.append({
            "name": full_name,
            "type": sym_type,
            "start_line": node.lineno,
            "end_line": getattr(node, "end_lineno", node.lineno),
            "signature": sig,
            "docstring": docstring or "",
            "parent": self.current_class,
        })
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call):
        try:
            if isinstance(node.func, ast.Name):
                self.calls.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                self.calls.add(node.func.attr)
        except Exception:
            pass
        self.generic_visit(node)


class CodeParserService:
    """Multi-language static code parser extracting symbols, dependencies, and file summaries."""

    def parse_python_ast(self, content: str, file_path: str) -> Dict[str, Any]:
        """Parse Python source using standard AST."""
        try:
            tree = ast.parse(content, filename=file_path)
            visitor = PythonASTVisitor()
            visitor.visit(tree)

            return {
                "symbols": visitor.symbols,
                "imports": sorted(list(set(visitor.imports))),
                "calls": sorted(list(visitor.calls)),
                "syntax_valid": True,
            }
        except SyntaxError as e:
            logger.debug("python_syntax_error", file=file_path, line=e.lineno)
            return {
                "symbols": [],
                "imports": [],
                "calls": [],
                "syntax_valid": False,
                "error": str(e),
            }

    def parse_treesitter(self, content: bytes, language: str, file_path: str) -> Dict[str, Any]:
        """Parse source code using Tree-sitter for non-Python or as a multi-language analyzer."""
        parser = TS_PARSERS.get(language)
        if not parser:
            return {"symbols": [], "imports": [], "syntax_valid": False}

        try:
            tree = parser.parse(content)
            symbols: List[Dict[str, Any]] = []
            imports: List[str] = []

            lines = content.splitlines()

            def get_text(node):
                return content[node.start_byte : node.end_byte].decode("utf-8", errors="ignore")

            def traverse(node):
                node_type = node.type

                # JavaScript / TypeScript / React
                if node_type in {"function_declaration", "method_definition", "arrow_function"}:
                    name_node = node.child_by_field_name("name")
                    name = get_text(name_node) if name_node else "anonymous"
                    start_line = node.start_point[0] + 1
                    end_line = node.end_point[0] + 1
                    sig_line = lines[node.start_point[0]].decode("utf-8", errors="ignore").strip() if node.start_point[0] < len(lines) else ""
                    symbols.append({
                        "name": name,
                        "type": "function" if node_type != "method_definition" else "method",
                        "start_line": start_line,
                        "end_line": end_line,
                        "signature": sig_line,
                        "docstring": "",
                    })
                elif node_type in {"class_declaration", "interface_declaration"}:
                    name_node = node.child_by_field_name("name")
                    if name_node:
                        name = get_text(name_node)
                        start_line = node.start_point[0] + 1
                        end_line = node.end_point[0] + 1
                        symbols.append({
                            "name": name,
                            "type": "class" if node_type == "class_declaration" else "interface",
                            "start_line": start_line,
                            "end_line": end_line,
                            "signature": f"{node_type.replace('_declaration', '')} {name}",
                            "docstring": "",
                        })
                elif node_type == "import_statement":
                    imports.append(get_text(node).strip())

                # Go
                elif node_type == "function_declaration":
                    name_node = node.child_by_field_name("name")
                    if name_node:
                        symbols.append({
                            "name": get_text(name_node),
                            "type": "function",
                            "start_line": node.start_point[0] + 1,
                            "end_line": node.end_point[0] + 1,
                            "signature": lines[node.start_point[0]].decode("utf-8", errors="ignore").strip(),
                            "docstring": "",
                        })
                elif node_type == "method_declaration":
                    name_node = node.child_by_field_name("name")
                    if name_node:
                        symbols.append({
                            "name": get_text(name_node),
                            "type": "method",
                            "start_line": node.start_point[0] + 1,
                            "end_line": node.end_point[0] + 1,
                            "signature": lines[node.start_point[0]].decode("utf-8", errors="ignore").strip(),
                            "docstring": "",
                        })

                # Java
                elif node_type == "method_declaration":
                    name_node = node.child_by_field_name("name")
                    if name_node:
                        symbols.append({
                            "name": get_text(name_node),
                            "type": "method",
                            "start_line": node.start_point[0] + 1,
                            "end_line": node.end_point[0] + 1,
                            "signature": lines[node.start_point[0]].decode("utf-8", errors="ignore").strip(),
                            "docstring": "",
                        })

                for child in node.children:
                    traverse(child)

            traverse(tree.root_node)

            return {
                "symbols": symbols,
                "imports": imports,
                "syntax_valid": not tree.root_node.has_error,
            }

        except Exception as exc:
            logger.debug("treesitter_parse_error", file=file_path, error=str(exc))
            return {"symbols": [], "imports": [], "syntax_valid": False}

    def parse_file(self, full_path: Path, rel_path: str, language: Optional[str]) -> Dict[str, Any]:
        """Unified parser extracting symbols, dependencies, and generating a file summary."""
        if not full_path.exists() or not full_path.is_file():
            return {"symbols": [], "imports": [], "summary": ""}

        try:
            content_bytes = full_path.read_bytes()
            content_str = content_bytes.decode("utf-8", errors="ignore")
        except Exception:
            return {"symbols": [], "imports": [], "summary": ""}

        result: Dict[str, Any] = {"rel_path": rel_path, "symbols": [], "imports": [], "calls": []}

        # 1. If Python, use AST for comprehensive class/function/docstring extraction
        if language == "Python":
            ast_res = self.parse_python_ast(content_str, rel_path)
            result["symbols"] = ast_res.get("symbols", [])
            result["imports"] = ast_res.get("imports", [])
            result["calls"] = ast_res.get("calls", [])

        # 2. For other languages (or Python fallback), use Tree-sitter
        elif language and language in TS_PARSERS:
            ts_res = self.parse_treesitter(content_bytes, language, rel_path)
            result["symbols"] = ts_res.get("symbols", [])
            result["imports"] = ts_res.get("imports", [])

        # 3. Generate file-level summary
        classes = [s["name"] for s in result["symbols"] if s["type"] in {"class", "interface"}]
        functions = [s["name"] for s in result["symbols"] if s["type"] in {"function", "method"}]

        summary_parts = []
        if classes:
            summary_parts.append(f"Defines classes: {', '.join(classes[:5])}")
        if functions:
            summary_parts.append(f"Defines functions: {', '.join(functions[:8])}")
        if result["imports"]:
            summary_parts.append(f"Imports: {', '.join(result['imports'][:6])}")

        result["summary"] = "; ".join(summary_parts) if summary_parts else f"Source file ({language or 'unknown'})"
        return result
