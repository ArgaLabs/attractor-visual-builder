"""Shared test fixtures."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest

from attractor.agent.execution.base import (
    DirEntry,
    ExecResult,
    ExecutionEnvironment,
    GrepOptions,
)
from attractor.llm.adapters.base import ProviderAdapter
from attractor.llm.client import Client
from attractor.llm.models import (
    ContentPart,
    FinishReason,
    Message,
    Request,
    Response,
    Role,
    StreamEvent,
    StreamEventType,
    Usage,
)


class FakeAdapter(ProviderAdapter):
    """In-memory adapter that returns canned responses."""

    def __init__(
        self,
        canned_response: Response | None = None,
        stream_events: list[StreamEvent] | None = None,
    ):
        self._canned = canned_response or Response(
            model="fake-model",
            provider="fake",
            message=Message(
                role=Role.ASSISTANT,
                content=[ContentPart.text_part("canned reply")],
            ),
            finish_reason=FinishReason(reason=FinishReason.STOP),
            usage=Usage(input_tokens=10, output_tokens=5, total_tokens=15),
        )
        self._stream_events = stream_events or [
            StreamEvent(type=StreamEventType.TEXT_DELTA, delta="canned "),
            StreamEvent(type=StreamEventType.TEXT_DELTA, delta="reply"),
            StreamEvent(
                type=StreamEventType.FINISH,
                finish_reason=FinishReason(reason=FinishReason.STOP),
                usage=Usage(input_tokens=10, output_tokens=5, total_tokens=15),
            ),
        ]
        self._requests: list[Request] = []

    @property
    def name(self) -> str:
        return "fake"

    async def complete(self, request: Request) -> Response:
        self._requests.append(request)
        return self._canned

    async def stream(self, request: Request) -> AsyncIterator[StreamEvent]:
        self._requests.append(request)
        for ev in self._stream_events:
            yield ev


class InMemoryExecutionEnvironment(ExecutionEnvironment):
    """In-memory execution environment backed by a dict filesystem."""

    def __init__(self) -> None:
        self._files: dict[str, str] = {}
        self._cwd = "/workspace"

    async def read_file(
        self, path: str, offset: int | None = None, limit: int | None = None
    ) -> str:
        content = self._files.get(path, "")
        lines = content.splitlines(keepends=True)
        if offset is not None:
            lines = lines[offset:]
        if limit is not None:
            lines = lines[:limit]
        return "".join(lines)

    async def write_file(self, path: str, content: str) -> None:
        self._files[path] = content

    async def file_exists(self, path: str) -> bool:
        return path in self._files

    async def list_directory(self, path: str, depth: int = 1) -> list[DirEntry]:
        entries: list[DirEntry] = []
        seen: set[str] = set()
        prefix = path.rstrip("/") + "/"
        for fpath in self._files:
            if fpath.startswith(prefix):
                relative = fpath[len(prefix) :]
                top = relative.split("/")[0]
                if top not in seen:
                    seen.add(top)
                    is_dir = "/" in relative
                    entries.append(DirEntry(name=top, is_dir=is_dir))
        return entries

    async def exec_command(
        self,
        command: str,
        timeout_ms: int = 10000,
        working_dir: str | None = None,
        env_vars: dict[str, str] | None = None,
    ) -> ExecResult:
        return ExecResult(stdout="", stderr="", exit_code=0)

    async def grep(self, pattern: str, path: str, options: GrepOptions | None = None) -> str:
        return ""

    async def glob(self, pattern: str, path: str | None = None) -> list[str]:
        return []

    def working_directory(self) -> str:
        return self._cwd


@pytest.fixture
def tmp_dir(tmp_path):
    return tmp_path


@pytest.fixture
def fake_adapter():
    return FakeAdapter()


@pytest.fixture
def mock_llm_client(fake_adapter):
    return Client(providers={"fake": fake_adapter}, default_provider="fake")


@pytest.fixture
def mock_exec_env():
    return InMemoryExecutionEnvironment()
