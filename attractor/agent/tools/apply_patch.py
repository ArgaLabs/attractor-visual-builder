"""Apply patch in v4a format (OpenAI codex-rs compatible)."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field


@dataclass
class Hunk:
    context_hint: str = ""
    lines: list[tuple[str, str]] = field(default_factory=list)  # (prefix, content)


@dataclass
class PatchOp:
    op: str  # "add", "delete", "update"
    path: str = ""
    new_path: str | None = None
    content_lines: list[str] = field(default_factory=list)
    hunks: list[Hunk] = field(default_factory=list)


def parse_patch(patch_text: str) -> list[PatchOp]:
    lines = patch_text.split("\n")
    ops: list[PatchOp] = []
    i = 0

    while i < len(lines):
        line = lines[i]

        if line.startswith("*** Add File: "):
            path = line[len("*** Add File: ") :].strip()
            i += 1
            content_lines: list[str] = []
            while i < len(lines):
                if lines[i].startswith("*** "):
                    break
                if lines[i].startswith("+"):
                    content_lines.append(lines[i][1:])
                i += 1
            ops.append(PatchOp(op="add", path=path, content_lines=content_lines))
            continue

        if line.startswith("*** Delete File: "):
            path = line[len("*** Delete File: ") :].strip()
            ops.append(PatchOp(op="delete", path=path))
            i += 1
            continue

        if line.startswith("*** Update File: "):
            path = line[len("*** Update File: ") :].strip()
            i += 1
            new_path = None
            if i < len(lines) and lines[i].startswith("*** Move to: "):
                new_path = lines[i][len("*** Move to: ") :].strip()
                i += 1

            hunks: list[Hunk] = []
            while i < len(lines):
                if lines[i].startswith("*** ") and not lines[i].startswith("*** End of File"):
                    break
                if lines[i].startswith("@@ "):
                    hint = lines[i][3:].strip()
                    i += 1
                    hunk_lines: list[tuple[str, str]] = []
                    while i < len(lines):
                        if lines[i].startswith("@@ ") or (
                            lines[i].startswith("*** ")
                            and not lines[i].startswith("*** End of File")
                        ):
                            break
                        if lines[i].startswith("*** End of File"):
                            i += 1
                            break
                        if lines[i] and lines[i][0] in (" ", "-", "+"):
                            hunk_lines.append((lines[i][0], lines[i][1:]))
                        elif lines[i] == "":
                            hunk_lines.append((" ", ""))
                        i += 1
                    hunks.append(Hunk(context_hint=hint, lines=hunk_lines))
                    continue
                i += 1

            ops.append(PatchOp(op="update", path=path, new_path=new_path, hunks=hunks))
            continue

        i += 1

    return ops


def _find_hunk_position(file_lines: list[str], hunk: Hunk) -> int | None:
    context_lines = [(prefix, content) for prefix, content in hunk.lines if prefix in (" ", "-")]

    if not context_lines:
        return 0

    if hunk.context_hint:
        for i, line in enumerate(file_lines):
            if hunk.context_hint.strip() in line:
                return _try_match_from(file_lines, context_lines, max(0, i - 1))

    for start in range(len(file_lines)):
        pos = _try_match_from(file_lines, context_lines, start)
        if pos is not None:
            return pos

    for start in range(len(file_lines)):
        pos = _try_match_fuzzy(file_lines, context_lines, start)
        if pos is not None:
            return pos

    return None


def _try_match_from(
    file_lines: list[str], context_lines: list[tuple[str, str]], start: int
) -> int | None:
    if start + len(context_lines) > len(file_lines):
        return None
    for j, (_, expected) in enumerate(context_lines):
        if file_lines[start + j].rstrip() != expected.rstrip():
            return None
    return start


def _try_match_fuzzy(
    file_lines: list[str], context_lines: list[tuple[str, str]], start: int
) -> int | None:
    if start + len(context_lines) > len(file_lines):
        return None
    for j, (_, expected) in enumerate(context_lines):
        a = re.sub(r"\s+", " ", file_lines[start + j].strip())
        b = re.sub(r"\s+", " ", expected.strip())
        if a != b:
            return None
    return start


def apply_patch(patch_text: str, base_dir: str) -> list[str]:
    ops = parse_patch(patch_text)
    affected: list[str] = []

    for op in ops:
        full_path = os.path.join(base_dir, op.path)

        if op.op == "add":
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, "w", encoding="utf-8") as f:
                f.write("\n".join(op.content_lines))
                if op.content_lines:
                    f.write("\n")
            affected.append(op.path)

        elif op.op == "delete":
            if os.path.exists(full_path):
                os.remove(full_path)
            affected.append(op.path)

        elif op.op == "update":
            if not os.path.exists(full_path):
                raise FileNotFoundError(f"Cannot update: {op.path} not found")

            with open(full_path, encoding="utf-8") as f:
                file_lines = f.read().split("\n")

            if file_lines and file_lines[-1] == "":
                file_lines = file_lines[:-1]

            for hunk in op.hunks:
                pos = _find_hunk_position(file_lines, hunk)
                if pos is None:
                    raise ValueError(
                        f"Could not locate hunk in {op.path}: context hint '{hunk.context_hint}'"
                    )

                new_lines: list[str] = file_lines[:pos]
                fi = pos
                for prefix, content in hunk.lines:
                    if prefix == " ":
                        if fi < len(file_lines):
                            new_lines.append(file_lines[fi])
                            fi += 1
                        else:
                            new_lines.append(content)
                    elif prefix == "-":
                        fi += 1
                    elif prefix == "+":
                        new_lines.append(content)

                new_lines.extend(file_lines[fi:])
                file_lines = new_lines

            with open(full_path, "w", encoding="utf-8") as f:
                f.write("\n".join(file_lines))
                if file_lines:
                    f.write("\n")

            if op.new_path:
                new_full = os.path.join(base_dir, op.new_path)
                os.makedirs(os.path.dirname(new_full), exist_ok=True)
                os.rename(full_path, new_full)
                affected.append(op.new_path)
            else:
                affected.append(op.path)

    return affected
