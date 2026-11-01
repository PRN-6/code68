"""Tests for Code68 tools."""

import sys

import pytest

from code68.tools.filesystem import FilesystemTools
from code68.tools.search import SearchTools
from code68.tools.terminal import TerminalTools


def test_filesystem_read_and_write(temp_workspace):
    fs = FilesystemTools(temp_workspace)

    # Write file
    write_res = fs.write_file("new_dir/test.txt", "line 1\nline 2\n")
    assert "Successfully wrote" in write_res
    assert (temp_workspace / "new_dir" / "test.txt").exists()

    # Read file
    read_res = fs.read_file("new_dir/test.txt")
    assert "line 1" in read_res
    assert "line 2" in read_res
    assert "1 | line 1" in read_res


def test_filesystem_edit_file_and_diff(temp_workspace):
    fs = FilesystemTools(temp_workspace)
    sample_path = "sample.py"

    # Edit file
    edit_res = fs.edit_file(
        path=sample_path,
        old_text="return 'world'",
        new_text="return 'code68'",
    )
    assert "Successfully edited" in edit_res
    assert "```diff" in edit_res
    assert "-    return 'world'" in edit_res
    assert "+    return 'code68'" in edit_res

    # Check updated content
    content = (temp_workspace / sample_path).read_text(encoding="utf-8")
    assert "return 'code68'" in content


def test_filesystem_edit_crlf_lf_handling(temp_workspace):
    fs = FilesystemTools(temp_workspace)
    crlf_file = temp_workspace / "crlf.py"
    # Write a file with explicit Windows CRLF line endings
    crlf_file.write_bytes(b"def foo():\r\n    x = 1\r\n    return x\r\n")

    # LLM requests edit using Unix LF line endings
    edit_res = fs.edit_file(
        path="crlf.py",
        old_text="    x = 1\n    return x",
        new_text="    x = 42\n    return x",
    )
    assert "Successfully edited" in edit_res
    updated_bytes = crlf_file.read_bytes()
    assert b"42" in updated_bytes


def test_filesystem_edit_not_found(temp_workspace):
    fs = FilesystemTools(temp_workspace)
    edit_res = fs.edit_file(
        path="sample.py",
        old_text="nonexistent text snippet",
        new_text="replacement",
    )
    assert "Error: Target text not found" in edit_res


def test_filesystem_directory_operations(temp_workspace):
    fs = FilesystemTools(temp_workspace)

    # Create dir
    res = fs.create_directory("subdir/nested")
    assert "Successfully created" in res
    assert (temp_workspace / "subdir" / "nested").is_dir()

    # List dir
    list_res = fs.list_directory(".")
    assert "sample.py" in list_res
    assert "subdir" in list_res

    # Delete file
    del_res = fs.delete_file("sample.py")
    assert "Successfully deleted" in del_res
    assert not (temp_workspace / "sample.py").exists()


def test_search_tools(temp_workspace):
    search = SearchTools(temp_workspace)

    # Search file content
    res = search.search_files(query="world")
    assert "sample.py" in res

    # Find files pattern
    found = search.find_files(pattern="*.py")
    assert "sample.py" in found

    # Search symbols
    syms = search.search_symbols(name="hello")
    assert "hello" in syms
    assert "sample.py" in syms


@pytest.mark.asyncio
async def test_terminal_run_command(temp_workspace):
    term = TerminalTools(temp_workspace)
    res = await term.run_command(f'"{sys.executable}" -c "print(\'Hello from terminal\')"')
    assert "Hello from terminal" in res
    assert "Exit Code: 0" in res


@pytest.mark.asyncio
async def test_terminal_timeout(temp_workspace):
    term = TerminalTools(temp_workspace)
    # 1 second timeout on 3 second sleep
    res = await term.run_command(f'"{sys.executable}" -c "import time; time.sleep(3)"', timeout=1)
    assert "timed out after 1 seconds" in res
