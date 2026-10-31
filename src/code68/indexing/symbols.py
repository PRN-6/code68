"""AST-based symbol extraction for Python and code analysis."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class SymbolInfo(BaseModel):
    """Extracted code symbol details."""

    name: str
    kind: str  # 'function', 'async_function', 'class', 'method'
    line_number: int
    end_line_number: int
    signature: str
    docstring: Optional[str] = None


class SymbolExtractor:
    """Extracts symbols from source code files using Python AST."""

    @staticmethod
    def extract_python_symbols(source_code: str, file_name: str = "") -> List[SymbolInfo]:
        """Extract top-level and method definitions from Python code."""
        symbols: List[SymbolInfo] = []
        try:
            tree = ast.parse(source_code, filename=file_name)
        except Exception:
            return symbols

        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                kind = "async_function" if isinstance(node, ast.AsyncFunctionDef) else "function"
                sig = SymbolExtractor._get_func_signature(node)
                doc = ast.get_docstring(node)
                end_lineno = getattr(node, "end_lineno", node.lineno)
                symbols.append(
                    SymbolInfo(
                        name=node.name,
                        kind=kind,
                        line_number=node.lineno,
                        end_line_number=end_lineno,
                        signature=sig,
                        docstring=doc.splitlines()[0] if doc else None,
                    )
                )
            elif isinstance(node, ast.ClassDef):
                doc = ast.get_docstring(node)
                end_lineno = getattr(node, "end_lineno", node.lineno)
                symbols.append(
                    SymbolInfo(
                        name=node.name,
                        kind="class",
                        line_number=node.lineno,
                        end_line_number=end_lineno,
                        signature=f"class {node.name}",
                        docstring=doc.splitlines()[0] if doc else None,
                    )
                )
                # Extract methods
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        method_kind = "async_method" if isinstance(item, ast.AsyncFunctionDef) else "method"
                        method_sig = SymbolExtractor._get_func_signature(item)
                        method_doc = ast.get_docstring(item)
                        m_end = getattr(item, "end_lineno", item.lineno)
                        symbols.append(
                            SymbolInfo(
                                name=f"{node.name}.{item.name}",
                                kind=method_kind,
                                line_number=item.lineno,
                                end_line_number=m_end,
                                signature=method_sig,
                                docstring=method_doc.splitlines()[0] if method_doc else None,
                            )
                        )

        return symbols

    @staticmethod
    def _get_func_signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
        args_list = []
        for a in node.args.args:
            arg_str = a.arg
            if a.annotation:
                arg_str += f": {ast.unparse(a.annotation)}"
            args_list.append(arg_str)

        ret = f" -> {ast.unparse(node.returns)}" if node.returns else ""
        prefix = "async def " if isinstance(node, ast.AsyncFunctionDef) else "def "
        return f"{prefix}{node.name}({', '.join(args_list)}){ret}"
