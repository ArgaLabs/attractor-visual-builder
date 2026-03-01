"""Tests for attractor.agent.tools.core."""

from __future__ import annotations

import pytest

from attractor.agent.execution.local import LocalExecutionEnvironment
from attractor.agent.tools.core import (
    edit_file_exec,
    glob_exec,
    grep_exec,
    read_file_exec,
    shell_exec,
    write_file_exec,
)


@pytest.fixture
def env(tmp_path):
    return LocalExecutionEnvironment(working_dir=str(tmp_path))


@pytest.fixture
def sample_file(tmp_path):
    f = tmp_path / "sample.txt"
    f.write_text("line1\nline2\nline3\nline4\nline5\n")
    return f


class TestReadFileExec:
    async def test_returns_line_numbered_content(self, env, sample_file):
        result = await read_file_exec({"file_path": str(sample_file)}, env)
        assert "1 | line1" in result
        assert "5 | line5" in result

    async def test_with_offset_and_limit(self, env, sample_file):
        result = await read_file_exec({"file_path": str(sample_file), "offset": 2, "limit": 2}, env)
        assert "2 | line2" in result
        assert "3 | line3" in result
        assert "1 | line1" not in result
        assert "4 | line4" not in result


class TestWriteFileExec:
    async def test_creates_file(self, env, tmp_path):
        target = tmp_path / "sub" / "new.txt"
        result = await write_file_exec({"file_path": str(target), "content": "hello world"}, env)
        assert "Successfully wrote" in result
        assert target.exists()
        assert target.read_text() == "hello world"


class TestEditFileExec:
    async def test_replaces_text(self, env, sample_file):
        result = await edit_file_exec(
            {
                "file_path": str(sample_file),
                "old_string": "line3",
                "new_string": "LINE_THREE",
            },
            env,
        )
        assert "1 replacement" in result
        content = sample_file.read_text()
        assert "LINE_THREE" in content
        assert "line3" not in content

    async def test_error_if_not_found(self, env, sample_file):
        result = await edit_file_exec(
            {
                "file_path": str(sample_file),
                "old_string": "nonexistent",
                "new_string": "replacement",
            },
            env,
        )
        assert "Error" in result
        assert "not found" in result

    async def test_error_if_not_unique(self, env, tmp_path):
        f = tmp_path / "dup.txt"
        f.write_text("aaa\naaa\nbbb\n")
        result = await edit_file_exec(
            {
                "file_path": str(f),
                "old_string": "aaa",
                "new_string": "ccc",
            },
            env,
        )
        assert "Error" in result
        assert "2 times" in result

    async def test_replace_all(self, env, tmp_path):
        f = tmp_path / "dup.txt"
        f.write_text("aaa\naaa\nbbb\n")
        result = await edit_file_exec(
            {
                "file_path": str(f),
                "old_string": "aaa",
                "new_string": "ccc",
                "replace_all": True,
            },
            env,
        )
        assert "2 replacement" in result
        assert "aaa" not in f.read_text()


class TestShellExec:
    async def test_returns_output_with_exit_code(self, env):
        result = await shell_exec({"command": "echo hello"}, env)
        assert "hello" in result
        assert "Exit code: 0" in result

    async def test_nonzero_exit_code(self, env):
        result = await shell_exec({"command": "exit 42"}, env)
        assert "Exit code: 42" in result


class TestGrepExec:
    async def test_grep_finds_pattern(self, env, sample_file):
        result = await grep_exec({"pattern": "line[23]", "path": str(sample_file)}, env)
        assert "line2" in result
        assert "line3" in result

    async def test_grep_no_match_returns_empty(self, env, sample_file):
        result = await grep_exec({"pattern": "zzzzz", "path": str(sample_file)}, env)
        assert "zzzzz" not in result


class TestGlobExec:
    async def test_glob_finds_files(self, env, tmp_path):
        (tmp_path / "a.py").write_text("")
        (tmp_path / "b.py").write_text("")
        (tmp_path / "c.txt").write_text("")

        result = await glob_exec({"pattern": "*.py", "path": str(tmp_path)}, env)
        assert "a.py" in result
        assert "b.py" in result
        assert "c.txt" not in result
