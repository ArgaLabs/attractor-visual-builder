"""Starlette app with 9 pipeline endpoints + visual builder."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from starlette.applications import Starlette
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, Response
from starlette.routing import Route

from attractor.pipeline.parser import ParseError, parse_dot
from attractor.pipeline.validator import validate as validate_graph
from attractor.server.dot_generator import generate_dot
from attractor.server.models import (
    AnswerRequest,
    CreatePipelineRequest,
    ValidateRequest,
)
from attractor.server.pipeline_manager import PipelineManager
from attractor.server.sse import event_stream_generator

STATIC_DIR = Path(__file__).parent / "static"
manager = PipelineManager()


# --- Pipeline CRUD endpoints ---


async def create_pipeline(request: Request) -> JSONResponse:
    """POST /pipelines - Start a pipeline from DOT source."""
    body = await request.json()
    req = CreatePipelineRequest(**body)

    try:
        managed = await manager.create_and_run(
            dot_source=req.dot_source,
            context_data=req.context,
        )
        return JSONResponse(managed.info().model_dump(), status_code=201)
    except ParseError as e:
        return JSONResponse(
            {"error": f"DOT parse error: {e}"}, status_code=400
        )
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


# --- Utility endpoints ---


async def validate_dot(request: Request) -> JSONResponse:
    """POST /validate - Validate a DOT file."""
    body = await request.json()
    req = ValidateRequest(**body)

    try:
        graph = parse_dot(req.dot_source)
    except ParseError as e:
        return JSONResponse({
            "valid": False,
            "diagnostics": [
                {
                    "rule": "parse_error",
                    "severity": "error",
                    "message": str(e),
                }
            ],
        })

    diagnostics = validate_graph(graph)
    diag_list = [d.model_dump() for d in diagnostics]
    has_errors = any(
        d.severity.value == "error" for d in diagnostics
    )

    return JSONResponse({
        "valid": not has_errors,
        "diagnostics": diag_list,
    })


async def generate_dot_endpoint(request: Request) -> JSONResponse:
    """POST /generate-dot - Generate DOT from visual graph definition."""
    body = await request.json()
    nodes = body.get("nodes", [])
    edges = body.get("edges", [])
    graph_attrs = body.get("graph_attrs", {})

    dot_source = generate_dot(nodes, edges, graph_attrs)
    return JSONResponse({"dot_source": dot_source})


async def list_pipelines(request: Request) -> JSONResponse:
    """GET /pipelines - List all pipelines."""
    pipelines = manager.list_all()
    return JSONResponse([p.model_dump() for p in pipelines])


# --- Visual builder ---


async def visual_builder(request: Request) -> HTMLResponse:
    """GET / - Serve the visual DOT builder."""
    html_path = STATIC_DIR / "index.html"
    content = html_path.read_text(encoding="utf-8")
    return HTMLResponse(content)


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
        Route("/validate", validate_dot, methods=["POST"]),
        Route("/generate-dot", generate_dot_endpoint, methods=["POST"]),
    ]

    app = Starlette(routes=routes)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    return app
