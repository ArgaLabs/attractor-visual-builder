"""Starlette app with 9 pipeline endpoints + visual builder."""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any

from starlette.applications import Starlette
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import FileResponse, HTMLResponse, JSONResponse, Response
from starlette.routing import Route

from attractor.pipeline.parser import ParseError, parse_dot
from attractor.pipeline.validator import validate as validate_graph
from attractor.server.dot_generator import generate_dot
from attractor.server.models import (
    AnswerRequest,
    CreatePipelineRequest,
    CreateScheduleRequest,
    ValidateRequest,
)
from attractor.server.pipeline_manager import PipelineManager
from attractor.server.scheduler import Scheduler
from attractor.server.sse import event_stream_generator

STATIC_DIR = Path(__file__).parent / "static"
UPLOAD_DIR = Path("/tmp/attractor/uploads")
UPLOAD_MAX_AGE_SECONDS = 24 * 3600  # auto-clean files older than 24 h

manager = PipelineManager()
scheduler = Scheduler(pipeline_manager=manager)


# --- Pipeline CRUD endpoints ---


async def create_pipeline(request: Request) -> JSONResponse:
    """POST /pipelines - Start a pipeline from DOT source."""
    try:
        body = await request.json()
        req = CreatePipelineRequest(**body)
        managed = await manager.create_and_run(
            dot_source=req.dot_source,
            context_data=req.context,
        )
        return JSONResponse(managed.info().model_dump(), status_code=201)
    except ParseError as e:
        return JSONResponse({"error": f"DOT parse error: {e}"}, status_code=400)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)


async def get_pipeline(request: Request) -> JSONResponse:
    """GET /pipelines/{id} - Pipeline status and progress."""
    pipeline_id = request.path_params["id"]
    managed = manager.get(pipeline_id)
    if not managed:
        return JSONResponse(
            {"error": "Pipeline not found"}, status_code=404
        )
    return JSONResponse(managed.info().model_dump())


async def get_pipeline_events(request: Request) -> Response:
    """GET /pipelines/{id}/events - SSE event stream (real-time)."""
    from starlette.responses import StreamingResponse

    pipeline_id = request.path_params["id"]
    managed = manager.get(pipeline_id)
    if not managed:
        return JSONResponse(
            {"error": "Pipeline not found"}, status_code=404
        )

    def _get_events(pid: str) -> list[dict[str, Any]] | None:
        p = manager.get(pid)
        return p.events if p else None

    return StreamingResponse(
        event_stream_generator(pipeline_id, _get_events),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


async def cancel_pipeline(request: Request) -> JSONResponse:
    """POST /pipelines/{id}/cancel - Cancel a running pipeline."""
    pipeline_id = request.path_params["id"]
    success = await manager.cancel(pipeline_id)
    if success:
        return JSONResponse({"status": "cancelled"})
    managed = manager.get(pipeline_id)
    if not managed:
        return JSONResponse(
            {"error": "Pipeline not found"}, status_code=404
        )
    return JSONResponse(
        {"error": "Pipeline is not running"}, status_code=409
    )


async def get_pipeline_graph(request: Request) -> JSONResponse:
    """GET /pipelines/{id}/graph - Graph structure as JSON."""
    pipeline_id = request.path_params["id"]
    managed = manager.get(pipeline_id)
    if not managed:
        return JSONResponse(
            {"error": "Pipeline not found"}, status_code=404
        )

    nodes = [
        {
            "id": n.id,
            "type": n.type,
            "label": n.label,
            "attrs": n.attrs,
        }
        for n in managed.graph.nodes.values()
    ]
    edges = [
        {
            "source": e.source,
            "target": e.target,
            "label": e.label,
            "condition": e.condition,
            "weight": e.weight,
            "attrs": e.attrs,
        }
        for e in managed.graph.edges
    ]

    return JSONResponse({
        "nodes": nodes,
        "edges": edges,
        "attrs": managed.graph.attrs,
    })


async def get_pipeline_questions(request: Request) -> JSONResponse:
    """GET /pipelines/{id}/questions - Pending human gate questions."""
    pipeline_id = request.path_params["id"]
    managed = manager.get(pipeline_id)
    if not managed:
        return JSONResponse(
            {"error": "Pipeline not found"}, status_code=404
        )

    questions = [
        q.model_dump() for q in managed.pending_questions.values()
    ]
    return JSONResponse({"questions": questions})


async def answer_question(request: Request) -> JSONResponse:
    """POST /pipelines/{id}/questions/{qid}/answer."""
    pipeline_id = request.path_params["id"]
    qid = request.path_params["qid"]
    managed = manager.get(pipeline_id)
    if not managed:
        return JSONResponse(
            {"error": "Pipeline not found"}, status_code=404
        )

    body = await request.json()
    req = AnswerRequest(**body)
    managed.interviewer.enqueue(req.answer)
    managed.pending_questions.pop(qid, None)
    return JSONResponse({"status": "answered"})


async def get_checkpoint(request: Request) -> JSONResponse:
    """GET /pipelines/{id}/checkpoint - Checkpoint state."""
    pipeline_id = request.path_params["id"]
    managed = manager.get(pipeline_id)
    if not managed:
        return JSONResponse(
            {"error": "Pipeline not found"}, status_code=404
        )

    if managed.result:
        return JSONResponse({
            "execution_order": managed.result.execution_order,
            "nodes_completed": managed.nodes_completed,
            "current_node": managed.current_node,
        })
    return JSONResponse({
        "execution_order": [],
        "nodes_completed": managed.nodes_completed,
        "current_node": managed.current_node,
    })


async def get_context(request: Request) -> JSONResponse:
    """GET /pipelines/{id}/context - Context key-value store."""
    pipeline_id = request.path_params["id"]
    managed = manager.get(pipeline_id)
    if not managed:
        return JSONResponse(
            {"error": "Pipeline not found"}, status_code=404
        )


    snapshot = managed.context.snapshot()
    safe = json.loads(json.dumps(snapshot, default=str))
    return JSONResponse(safe)


async def get_pipeline_log(request: Request) -> JSONResponse:
    """GET /pipelines/{id}/log - Full event log + context snapshot (for result panel)."""
    pipeline_id = request.path_params["id"]
    managed = manager.get(pipeline_id)
    if not managed:
        return JSONResponse({"error": "Pipeline not found"}, status_code=404)

    snapshot = managed.context.snapshot()
    safe_context = json.loads(json.dumps(snapshot, default=str))

    return JSONResponse({
        "id": pipeline_id,
        "status": managed.status.value,
        "nodes_completed": managed.nodes_completed,
        "execution_order": (
            managed.result.execution_order if managed.result else managed.nodes_completed
        ),
        "duration": (managed.completed_at - managed.created_at) if managed.completed_at else None,
        "error": managed.error,
        "context": safe_context,
        "events": managed.events[-100:],  # last 100 events
    })


# --- Utility endpoints ---


async def validate_dot(request: Request) -> JSONResponse:
    """POST /validate - Validate a DOT file."""
    try:
        body = await request.json()
        req = ValidateRequest(**body)
        try:
            graph = parse_dot(req.dot_source)
        except ParseError as e:
            return JSONResponse({
                "valid": False,
                "diagnostics": [{"rule": "parse_error", "severity": "error", "message": str(e)}],
            })
        diagnostics = validate_graph(graph)
        diag_list = [d.model_dump() for d in diagnostics]
        has_errors = any(d.severity.value == "error" for d in diagnostics)
        return JSONResponse({"valid": not has_errors, "diagnostics": diag_list})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)


async def generate_dot_endpoint(request: Request) -> JSONResponse:
    """POST /generate-dot - Generate DOT from visual graph definition."""
    try:
        body = await request.json()
        nodes = body.get("nodes", [])
        edges = body.get("edges", [])
        graph_attrs = body.get("graph_attrs", {})
        dot_source = generate_dot(nodes, edges, graph_attrs)
        return JSONResponse({"dot_source": dot_source})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)


async def list_pipelines(request: Request) -> JSONResponse:
    """GET /pipelines - List all pipelines."""
    pipelines = manager.list_all()
    return JSONResponse([p.model_dump() for p in pipelines])


# --- File upload endpoints ---


def _cleanup_old_uploads() -> None:
    """Remove upload directories older than UPLOAD_MAX_AGE_SECONDS."""
    if not UPLOAD_DIR.exists():
        return
    cutoff = time.time() - UPLOAD_MAX_AGE_SECONDS
    for entry in UPLOAD_DIR.iterdir():
        if entry.is_dir():
            try:
                mtime = entry.stat().st_mtime
                if mtime < cutoff:
                    import shutil
                    shutil.rmtree(entry, ignore_errors=True)
            except OSError:
                pass


async def upload_file(request: Request) -> JSONResponse:
    """POST /upload — accept a multipart file, store in /tmp, return path + context key."""
    _cleanup_old_uploads()

    try:
        form = await request.form()
    except Exception as e:
        return JSONResponse({"error": f"Invalid form data: {e}"}, status_code=400)

    file_field = form.get("file")
    if file_field is None:
        return JSONResponse({"error": "No file field in request"}, status_code=400)

    filename = getattr(file_field, "filename", None) or "upload"
    # Sanitise filename — keep only safe characters
    safe_name = "".join(c for c in filename if c.isalnum() or c in "._- ").strip() or "upload"

    file_id = uuid.uuid4().hex[:12]
    dest_dir = UPLOAD_DIR / file_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / safe_name

    contents: bytes = await file_field.read()
    dest_path.write_bytes(contents)

    # Derive a sensible context key from the filename stem
    stem = Path(safe_name).stem.lower().replace(" ", "_").replace("-", "_")
    context_key = f"{stem}_file"

    return JSONResponse({
        "file_id": file_id,
        "filename": safe_name,
        "path": str(dest_path),
        "size": len(contents),
        "context_key": context_key,
    }, status_code=201)


async def delete_upload(request: Request) -> JSONResponse:
    """DELETE /upload/{file_id} — remove an uploaded file."""
    file_id = request.path_params["file_id"]
    target = UPLOAD_DIR / file_id
    if not target.exists():
        return JSONResponse({"error": "File not found"}, status_code=404)
    import shutil
    shutil.rmtree(target, ignore_errors=True)
    return JSONResponse({"status": "deleted"})


# --- Schedule endpoints ---


async def create_schedule(request: Request) -> JSONResponse:
    """POST /schedules - Create a recurring pipeline schedule."""
    try:
        body = await request.json()
        req = CreateScheduleRequest(**body)
        sched = await scheduler.create(
            dot_source=req.dot_source,
            interval_seconds=req.interval_seconds,
            duration_seconds=req.duration_seconds,
            carry_context=req.carry_context,
            initial_context=req.context,
        )
        return JSONResponse(sched.info(), status_code=201)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=422)


async def list_schedules(request: Request) -> JSONResponse:
    """GET /schedules - List all schedules."""
    return JSONResponse(scheduler.list_all())


async def get_schedule(request: Request) -> JSONResponse:
    """GET /schedules/{id} - Get a single schedule."""
    sched = scheduler.get(request.path_params["id"])
    if not sched:
        return JSONResponse({"error": "Schedule not found"}, status_code=404)
    return JSONResponse(sched.info())


async def cancel_schedule(request: Request) -> JSONResponse:
    """DELETE /schedules/{id} - Cancel a schedule."""
    ok = await scheduler.cancel(request.path_params["id"])
    if not ok:
        sched = scheduler.get(request.path_params["id"])
        if not sched:
            return JSONResponse({"error": "Schedule not found"}, status_code=404)
        return JSONResponse(
            {"error": f"Schedule is already {sched.status.value}"}, status_code=409
        )
    return JSONResponse({"status": "cancelled"})


# --- Visual builder ---


async def visual_builder(request: Request) -> HTMLResponse:
    """GET / - Serve the visual DOT builder."""
    html_path = STATIC_DIR / "index.html"
    content = html_path.read_text(encoding="utf-8")
    return HTMLResponse(content)


MIME_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
    ".css": "text/css",
    ".js": "application/javascript",
    ".woff": "font/woff",
    ".woff2": "font/woff2",
    ".ttf": "font/ttf",
    ".json": "application/json",
}


async def serve_static(request: Request) -> Response:
    """Serve static assets from the static directory (including Vite build output)."""
    # Support both /{filename} and /assets/{filename} via path param
    path_val: str = request.path_params.get("path", "") or request.path_params.get("filename", "")
    file_path = (STATIC_DIR / path_val).resolve()

    # Security: prevent path traversal outside STATIC_DIR
    try:
        file_path.relative_to(STATIC_DIR.resolve())
    except ValueError:
        return Response("Forbidden", status_code=403)

    if not file_path.exists() or not file_path.is_file():
        return Response("Not found", status_code=404)

    mime = MIME_TYPES.get(file_path.suffix.lower(), "application/octet-stream")
    return FileResponse(str(file_path), media_type=mime)


# --- App factory ---


def create_app() -> Starlette:
    routes = [
        Route("/", visual_builder),
        Route("/pipelines", list_pipelines, methods=["GET"]),
        Route("/pipelines", create_pipeline, methods=["POST"]),
        Route("/pipelines/{id}", get_pipeline, methods=["GET"]),
        Route(
            "/pipelines/{id}/events",
            get_pipeline_events,
            methods=["GET"],
        ),
        Route(
            "/pipelines/{id}/cancel",
            cancel_pipeline,
            methods=["POST"],
        ),
        Route(
            "/pipelines/{id}/graph",
            get_pipeline_graph,
            methods=["GET"],
        ),
        Route(
            "/pipelines/{id}/questions",
            get_pipeline_questions,
            methods=["GET"],
        ),
        Route(
            "/pipelines/{id}/questions/{qid}/answer",
            answer_question,
            methods=["POST"],
        ),
        Route(
            "/pipelines/{id}/checkpoint",
            get_checkpoint,
            methods=["GET"],
        ),
        Route(
            "/pipelines/{id}/context",
            get_context,
            methods=["GET"],
        ),
        Route(
            "/pipelines/{id}/log",
            get_pipeline_log,
            methods=["GET"],
        ),
        Route("/validate", validate_dot, methods=["POST"]),
        Route("/generate-dot", generate_dot_endpoint, methods=["POST"]),
        Route("/upload", upload_file, methods=["POST"]),
        Route("/upload/{file_id}", delete_upload, methods=["DELETE"]),
        Route("/schedules", list_schedules, methods=["GET"]),
        Route("/schedules", create_schedule, methods=["POST"]),
        Route("/schedules/{id}", get_schedule, methods=["GET"]),
        Route("/schedules/{id}", cancel_schedule, methods=["DELETE"]),
        # Catch-all for Vite build static assets (e.g. /assets/index-*.js)
        Route("/{path:path}", serve_static, methods=["GET"]),
    ]

    app = Starlette(routes=routes)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    return app
