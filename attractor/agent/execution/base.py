"""Execution environment interface."""

from __future__ import annotations

import abc

from pydantic import BaseModel


class ExecResult(BaseModel):
    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0
    timed_out: bool = False
    duration_ms: int = 0


class DirEntry(BaseModel):
    name: str
    is_dir: bool = False
    size: int | None = None


class GrepOptions(BaseModel):
    case_insensitive: bool = False
    max_results: int = 100
    glob_filter: str | None = None


class ExecutionEnvironment(abc.ABC):
    @abc.abstractmethod
    async def read_file(
        self, path: str, offset: int | None = None, limit: int | None = None
    ) -> str: ...

    @abc.abstractmethod
    async def write_file(self, path: str, content: str) -> None: ...

    @abc.abstractmethod
    async def file_exists(self, path: str) -> bool: ...

    @abc.abstractmethod
    async def list_directory(self, path: str, depth: int = 1) -> list[DirEntry]: ...

    @abc.abstractmethod
    async def exec_command(
        self,
        command: str,
        timeout_ms: int = 10000,
        working_dir: str | None = None,
        env_vars: dict[str, str] | None = None,
    ) -> ExecResult: ...

    @abc.abstractmethod
    async def grep(self, pattern: str, path: str, options: GrepOptions | None = None) -> str: ...

    @abc.abstractmethod
    async def glob(self, pattern: str, path: str | None = None) -> list[str]: ...

    async def initialize(self) -> None:
        pass

    async def cleanup(self) -> None:
        pass

    @abc.abstractmethod
    def working_directory(self) -> str: ...

    def platform(self) -> str:
        import sys

        return sys.platform

    def os_version(self) -> str:
        import platform as _p

        return _p.platform()
