"""Artifact store for pipeline execution outputs."""

from __future__ import annotations

import os
import uuid

from pydantic import BaseModel, Field

FILE_BACKING_THRESHOLD = 1024 * 1024  # 1MB


class Artifact(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    name: str
    stage_id: str = ""
    media_type: str = "text/plain"
    size: int = 0
    file_path: str | None = None
    inline_data: str | None = None


class ArtifactStore:
    def __init__(self, base_dir: str | None = None):
        self._base_dir = base_dir or os.path.join(os.getcwd(), ".attractor", "artifacts")
        self._artifacts: dict[str, Artifact] = {}

    def store(
        self,
        name: str,
        data: str,
        stage_id: str = "",
        media_type: str = "text/plain",
    ) -> Artifact:
        art = Artifact(name=name, stage_id=stage_id, media_type=media_type, size=len(data))

        if len(data) > FILE_BACKING_THRESHOLD:
            os.makedirs(self._base_dir, exist_ok=True)
            file_path = os.path.join(self._base_dir, f"{art.id}_{name}")
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(data)
            art.file_path = file_path
        else:
            art.inline_data = data

        self._artifacts[art.id] = art
        return art

    def retrieve(self, artifact_id: str) -> str | None:
        art = self._artifacts.get(artifact_id)
        if art is None:
            return None
        if art.inline_data is not None:
            return art.inline_data
        if art.file_path and os.path.exists(art.file_path):
            with open(art.file_path, encoding="utf-8") as f:
                return f.read()
        return None

    def list(self, stage_id: str | None = None) -> list[Artifact]:
        arts = list(self._artifacts.values())
        if stage_id:
            arts = [a for a in arts if a.stage_id == stage_id]
        return arts

    def remove(self, artifact_id: str) -> bool:
        art = self._artifacts.pop(artifact_id, None)
        if art is None:
            return False
        if art.file_path and os.path.exists(art.file_path):
            os.remove(art.file_path)
        return True
