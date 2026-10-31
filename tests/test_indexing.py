"""Tests for indexing, scanner, and codebase intelligence."""

from code68.indexing.ignore import IgnoreFilter
from code68.indexing.retrieval import ContextRetriever
from code68.indexing.scanner import CodebaseScanner
from code68.indexing.symbols import SymbolExtractor


def test_ignore_filter(temp_workspace):
    # Create gitignore
    (temp_workspace / ".gitignore").write_text("*.log\nsecret_dir/\n", encoding="utf-8")
    ig = IgnoreFilter(temp_workspace)

    assert ig.is_ignored(temp_workspace / ".git" / "config")
    assert ig.is_ignored(temp_workspace / "__pycache__" / "file.pyc")
    assert ig.is_ignored(temp_workspace / "app.log")
    assert ig.is_ignored(temp_workspace / "secret_dir" / "file.txt")
    assert not ig.is_ignored(temp_workspace / "sample.py")


def test_symbol_extractor():
    code = """
class Calculator:
    \"\"\"Performs arithmetic.\"\"\"
    def add(self, a: int, b: int) -> int:
        return a + b

async def fetch_data(url: str):
    \"\"\"Fetch remote content.\"\"\"
    pass
"""
    symbols = SymbolExtractor.extract_python_symbols(code)
    names = [s.name for s in symbols]

    assert "Calculator" in names
    assert "Calculator.add" in names
    assert "fetch_data" in names

    calc_sym = next(s for s in symbols if s.name == "Calculator")
    assert calc_sym.kind == "class"
    assert calc_sym.docstring == "Performs arithmetic."

    fetch_sym = next(s for s in symbols if s.name == "fetch_data")
    assert fetch_sym.kind == "async_function"
    assert "async def fetch_data" in fetch_sym.signature


def test_scanner_and_retrieval(temp_workspace):
    scanner = CodebaseScanner(temp_workspace)
    meta = scanner.scan()

    assert "Python" in meta.detected_languages
    assert meta.total_files >= 2

    retriever = ContextRetriever(temp_workspace)
    tree = retriever.generate_project_tree()
    assert "sample.py" in tree
    assert "README.md" in tree
