"""Tests for attractor.agent.execution.local.LocalExecutionEnvironment."""

from __future__ import annotations

import pytest

from attractor.agent.execution.local import LocalExecutionEnvironment


@pytest.fixture
def env(tmp_path):
    return LocalExecutionEnvironment(working_dir=str(tmp_path))


class TestReadFile:
    async def test_full_read(self, env, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("alpha\nbeta\ngamma\n")
        result = await env.read_file(str(f))
        assert "1 | alpha" in result
        assert "2 | beta" in result
        assert "3 | gamma" in result

    async def test_with_offset(self, env, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("a\nb\nc\nd\ne\n")
        result = await env.read_file(str(f), offset=3)
        assert "3 | c" in result
        assert "1 | a" not in result

    async def test_with_limit(self, env, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("a\nb\nc\nd\ne\n")
        result = await env.read_file(str(f), limit=2)
        assert "1 | a" in result
        assert "2 | b" in result
        assert "3 | c" not in result

    async def test_with_offset_and_limit(self, env, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("a\nb\nc\nd\ne\n")
        result = await env.read_file(str(f), offset=2, limit=2)
        assert "2 | b" in result
        assert "3 | c" in result
        assert "1 | a" not in result
        assert "4 | d" not in result


class TestWriteFile:
    async def test_creates_file_and_dirs(self, env, tmp_path):
        target = tmp_path / "deep" / "nested" / "file.txt"
        await env.write_file(str(target), "content here")
        assert target.exists()
        assert target.read_text() == "content here"

    async def test_overwrites_existing(self, env, tmp_path):
        f = tmp_path / "existing.txt"
        f.write_text("old")
        await env.write_file(str(f), "new")
        assert f.read_text() == "new"


class TestFileExists:
    async def test_existing_file(self, env, tmp_path):
        f = tmp_path / "exists.txt"
        f.write_text("hi")
        assert await env.file_exists(str(f)) is True

    async def test_nonexistent_file(self, env, tmp_path):
        assert await env.file_exists(str(tmp_path / "nope.txt")) is False

    async def test_directory(self, env, tmp_path):
        d = tmp_path / "adir"
        d.mkdir()
        assert await env.file_exists(str(d)) is True


class TestExecCommand:
    async def test_simple_echo(self, env):
        result = await env.exec_command("echo hello")
        assert result.exit_code == 0
        assert "hello" in result.stdout
        assert result.timed_out is False

    async def test_nonzero_exit(self, env):
        result = await env.exec_command("exit 1")
        assert result.exit_code == 1

    async def test_timeout_short_sleep(self, env):
        result = await env.exec_command("sleep 0.1", timeout_ms=5000)
        assert result.timed_out is False
        assert result.exit_code == 0

    async def test_stderr_captured(self, env):
        result = await env.exec_command("echo err >&2")
        assert "err" in result.stderr


class TestListDirectory:
    async def test_lists_entries(self, env, tmp_path):
        (tmp_path / "file_a.txt").write_text("a")
        (tmp_path / "file_b.txt").write_text("bb")
        (tmp_path / "subdir").mkdir()

        entries = await env.list_directory(str(tmp_path))
        names = {e.name for e in entries}
        assert "file_a.txt" in names
        assert "file_b.txt" in names
        assert "subdir" in names

        file_entry = next(e for e in entries if e.name == "file_a.txt")
        assert file_entry.is_dir is False
        assert file_entry.size is not None

        dir_entry = next(e for e in entries if e.name == "subdir")
        assert dir_entry.is_dir is True

    async def test_empty_directory(self, env, tmp_path):
        d = tmp_path / "empty"
        d.mkdir()
        entries = await env.list_directory(str(d))
        assert entries == []

    async def test_nonexistent_directory(self, env, tmp_path):
        entries = await env.list_directory(str(tmp_path / "ghost"))
        assert entries == []
