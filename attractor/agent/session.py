"""Core agentic loop: Session, process_input, steering, events."""

from __future__ import annotations

import asyncio
import uuid
from collections import deque
from typing import Any

from attractor.agent.config import SessionConfig
from attractor.agent.events import EventEmitter, EventKind
from attractor.agent.execution.base import ExecutionEnvironment
from attractor.agent.loop_detection import detect_loop, tool_call_signature
from attractor.agent.profiles.base import ProviderProfile
from attractor.agent.prompts import discover_project_docs
from attractor.agent.subagent import SubagentManager
from attractor.agent.truncation import truncate_tool_output
from attractor.llm.client import Client
from attractor.llm.models import (
    FinishReason,
    Message,
    Request,
    Role,
    Usage,
)


class TurnResult:
    def __init__(
        self,
        text: str = "",
        tool_calls_made: int = 0,
        finish_reason: str = "stop",
        usage: Usage | None = None,
    ):
        self.text = text
        self.tool_calls_made = tool_calls_made
        self.finish_reason = finish_reason
        self.usage = usage


class Session:
    def __init__(
        self,
        client: Client,
        profile: ProviderProfile,
        environment: ExecutionEnvironment,
        config: SessionConfig | None = None,
    ):
        self._client = client
        self._profile = profile
        self._environment = environment
        self._config = config or SessionConfig()
        self._session_id = f"sess_{uuid.uuid4().hex[:12]}"

        self._conversation: list[Message] = []
        self._total_turns = 0
        self._tool_signatures: list[str] = []
        self._total_usage = Usage()

        self._steering_queue: deque[str] = deque()
        self._followup_queue: deque[str] = deque()

        self._events = EventEmitter()
        self._subagent_manager = SubagentManager(max_depth=self._config.max_subagent_depth)

        self._initialized = False

    @property
    def session_id(self) -> str:
        return self._session_id

    @property
    def events(self) -> EventEmitter:
        return self._events

    @property
    def total_usage(self) -> Usage:
        return self._total_usage

    @property
    def conversation(self) -> list[Message]:
        return list(self._conversation)

    def steer(self, instruction: str) -> None:
        self._steering_queue.append(instruction)

    def follow_up(self, text: str) -> None:
        self._followup_queue.append(text)

    def _initialize(self) -> None:
        if self._initialized:
            return

        project_docs = discover_project_docs(
            self._environment.working_directory(),
            provider=self._profile.id,
        )
        system_prompt = self._profile.build_system_prompt(self._environment, project_docs)
        self._conversation.append(Message.system(system_prompt))
        self._initialized = True
        self._events.emit_simple(EventKind.SESSION_START, self._session_id)

    async def process_input(self, user_input: str) -> TurnResult:
        self._initialize()

        self._conversation.append(Message.user(user_input))
        self._events.emit_simple(EventKind.USER_INPUT, self._session_id, text=user_input)

        result = await self._run_loop()

        while self._followup_queue:
            followup = self._followup_queue.popleft()
            self._conversation.append(Message.user(followup))
            result = await self._run_loop()

        return result

    async def _run_loop(self) -> TurnResult:
        tool_calls_made = 0
        last_text = ""
        last_usage: Usage | None = None
        last_finish_reason = "stop"

        max_rounds = self._config.max_tool_rounds_per_input
        round_count = 0

        while True:
            if self._steering_queue:
                steering = self._steering_queue.popleft()
                self._conversation.append(
                    Message(
                        role=Role.USER,
                        content=[Message.user(f"[STEERING] {steering}").content[0]],
                    )
                )
                self._events.emit_simple(
                    EventKind.STEERING_INJECTED,
                    self._session_id,
                    instruction=steering,
                )

            request = Request(
                model=self._profile.model,
                messages=list(self._conversation),
                provider=self._profile.id,
                tools=self._profile.tools(),
                reasoning_effort=self._config.reasoning_effort,
                provider_options=self._profile.provider_options(),
            )

            response = await self._client.complete(request)
            self._total_turns += 1
            if response.usage:
                self._total_usage = self._total_usage + response.usage

            last_text = response.text
            last_usage = response.usage
            last_finish_reason = response.finish_reason.reason

            if last_text:
                self._events.emit_simple(EventKind.ASSISTANT_TEXT_START, self._session_id)
                self._events.emit_simple(
                    EventKind.ASSISTANT_TEXT_DELTA,
                    self._session_id,
                    text=last_text,
                )
                self._events.emit_simple(EventKind.ASSISTANT_TEXT_END, self._session_id)

            tool_calls = response.tool_calls
            if not tool_calls or response.finish_reason.reason != FinishReason.TOOL_CALLS:
                self._conversation.append(response.message)
                break

            self._conversation.append(response.message)

            for tc in tool_calls:
                sig = tool_call_signature(tc.name, tc.arguments)
                self._tool_signatures.append(sig)

                self._events.emit_simple(
                    EventKind.TOOL_CALL_START,
                    self._session_id,
                    name=tc.name,
                    tool_call_id=tc.id,
                )

                output = await self._execute_tool(tc.name, tc.arguments)
                tool_calls_made += 1

                truncated = truncate_tool_output(
                    output,
                    tc.name,
                    char_limits=self._config.tool_output_limits or None,
                    line_limits=self._config.tool_line_limits or None,
                )

                self._events.emit_simple(
                    EventKind.TOOL_CALL_END,
                    self._session_id,
                    name=tc.name,
                    tool_call_id=tc.id,
                    output=output,
                )

                self._conversation.append(
                    Message.tool_result(
                        tool_call_id=tc.id,
                        content=truncated,
                    )
                )

            if self._config.enable_loop_detection:
                if detect_loop(
                    self._tool_signatures,
                    window_size=self._config.loop_detection_window,
                ):
                    self._events.emit_simple(EventKind.LOOP_DETECTION, self._session_id)
                    self._conversation.append(
                        Message.user("[SYSTEM] Possible loop detected. Please change approach.")
                    )

            round_count += 1
            if max_rounds > 0 and round_count >= max_rounds:
                self._events.emit_simple(EventKind.TURN_LIMIT, self._session_id)
                break

            if self._config.max_turns > 0 and self._total_turns >= self._config.max_turns:
                self._events.emit_simple(EventKind.TURN_LIMIT, self._session_id)
                break

        return TurnResult(
            text=last_text,
            tool_calls_made=tool_calls_made,
            finish_reason=last_finish_reason,
            usage=last_usage,
        )

    async def _execute_tool(self, name: str, arguments: dict[str, Any]) -> str:
        registered = self._profile.tool_registry.get(name)
        if not registered or not registered.executor:
            return f"Error: Unknown tool '{name}'"
        try:
            result = registered.executor(arguments, self._environment)
            if asyncio.iscoroutine(result):
                result = await result
            return str(result)
        except Exception as e:
            return f"Error executing {name}: {e}"

    async def close(self) -> None:
        self._subagent_manager.close_all()
        self._events.emit_simple(EventKind.SESSION_END, self._session_id)
