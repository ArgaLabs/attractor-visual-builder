"""Tool handler: shell command execution."""

from __future__ import annotations

import asyncio

from attractor.pipeline.handlers.base import Handler, HandlerInput
from attractor.pipeline.outcome import Outcome, StageStatus


class ToolHandler(Handler):
    async def execute(self, input: HandlerInput) -> Outcome:
        command = input.node.attrs.get("command")
        if not command:
            return Outcome(
                status=StageStatus.FAIL,
                message="Tool node has no 'command' attribute",
            )

        timeout = input.node.timeout or 60
        goal = input.context.get("goal", "")
        command = str(command).replace("$goal", str(goal))

        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=input.stage_dir or None,
            )
            stdout_bytes, stderr_bytes = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            stdout = stdout_bytes.decode(errors="replace")
            stderr = stderr_bytes.decode(errors="replace")
            exit_code = proc.returncode or 0

            if exit_code == 0:
                return Outcome(
                    status=StageStatus.SUCCESS,
                    message=stdout,
                    context_updates={"tool.stdout": stdout, "tool.exit_code": exit_code},
                )
            else:
                return Outcome(
                    status=StageStatus.FAIL,
                    message=f"Command exited with code {exit_code}: {stderr}",
                    context_updates={
                        "tool.stdout": stdout,
                        "tool.stderr": stderr,
                        "tool.exit_code": exit_code,
                    },
                )

        except asyncio.TimeoutError:
            return Outcome(
                status=StageStatus.FAIL,
                message=f"Command timed out after {timeout}s",
            )
        except Exception as e:
            return Outcome(
                status=StageStatus.FAIL,
                message=f"Command execution error: {e}",
            )
