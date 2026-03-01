"""Interviewer interface and implementations for human-in-the-loop."""

from __future__ import annotations

import abc
import asyncio
from collections import deque
from typing import Any


class Interviewer(abc.ABC):
    @abc.abstractmethod
    async def ask(
        self,
        prompt: str,
        options: list[str],
        timeout: float | None = None,
        default: str | None = None,
    ) -> str: ...


class AutoApproveInterviewer(Interviewer):
    async def ask(
        self,
        prompt: str,
        options: list[str],
        timeout: float | None = None,
        default: str | None = None,
    ) -> str:
        if default:
            return default
        return options[0] if options else ""


class ConsoleInterviewer(Interviewer):
    async def ask(
        self,
        prompt: str,
        options: list[str],
        timeout: float | None = None,
        default: str | None = None,
    ) -> str:
        print(f"\n{prompt}")
        for i, opt in enumerate(options):
            print(f"  [{i + 1}] {opt}")
        if default:
            print(f"  (default: {default})")

        try:
            response = await asyncio.get_event_loop().run_in_executor(None, input, "Your choice: ")
            response = response.strip()

            if not response and default:
                return default

            try:
                idx = int(response) - 1
                if 0 <= idx < len(options):
                    return options[idx]
            except ValueError:
                pass

            for opt in options:
                if opt.lower() == response.lower() or opt.startswith(response):
                    return opt

            return response or (default or options[0] if options else "")

        except (EOFError, KeyboardInterrupt):
            return default or (options[0] if options else "")


class CallbackInterviewer(Interviewer):
    def __init__(self, callback: Any):
        self._callback = callback

    async def ask(
        self,
        prompt: str,
        options: list[str],
        timeout: float | None = None,
        default: str | None = None,
    ) -> str:
        result = self._callback(prompt, options, default)
        if asyncio.iscoroutine(result):
            result = await result
        return str(result)


class QueueInterviewer(Interviewer):
    def __init__(self, answers: list[str] | None = None):
        self._answers: deque[str] = deque(answers or [])

    def enqueue(self, answer: str) -> None:
        self._answers.append(answer)

    async def ask(
        self,
        prompt: str,
        options: list[str],
        timeout: float | None = None,
        default: str | None = None,
    ) -> str:
        if self._answers:
            return self._answers.popleft()
        return default or (options[0] if options else "")


class RecordingInterviewer(Interviewer):
    def __init__(self, inner: Interviewer):
        self._inner = inner
        self.recordings: list[dict[str, Any]] = []

    async def ask(
        self,
        prompt: str,
        options: list[str],
        timeout: float | None = None,
        default: str | None = None,
    ) -> str:
        result = await self._inner.ask(prompt, options, timeout, default)
        self.recordings.append(
            {
                "prompt": prompt,
                "options": options,
                "default": default,
                "selected": result,
            }
        )
        return result
