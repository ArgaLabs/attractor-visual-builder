# Attractor

A DOT-based pipeline runner for multi-stage AI workflows, with a visual browser-based builder for designing pipelines without writing any code.

---

## Contents

- [Overview](#overview)
- [Quick Start](#quick-start)
- [Using the Visual Builder](#using-the-visual-builder)
  - [Adding Nodes](#adding-nodes)
  - [Connecting Nodes](#connecting-nodes)
  - [Node Types](#node-types)
  - [Defining Conditions](#defining-conditions)
  - [Pipeline Settings](#pipeline-settings)
  - [Viewing the DOT Source](#viewing-the-dot-source)
- [External Skills and Tool Calls](#external-skills-and-tool-calls)
- [Example: Build, Lint, and Browser-Validate a Web App](#example-build-lint-and-browser-validate-a-web-app)
- [Running & Validating a Pipeline](#running--validating-a-pipeline)
- [API Reference](#api-reference)
- [Environment Variables](#environment-variables)
- [Running Tests](#running-tests)

---

## Overview

Attractor pipelines are directed graphs described in [Graphviz DOT syntax](https://graphviz.org/doc/info/lang.html). Each node in the graph is a **stage** — an LLM call, a shell command, an HTTP request to an external skill, a human approval step, or a branching point. Edges carry optional **conditions** that determine which path the engine takes at runtime.

The visual builder lets you design these graphs in a browser, then validate or run them against the HTTP API backend.

---

## Quick Start

**Requirements:** Python 3.11+

```bash
# 1. Clone and install
git clone https://github.com/your-org/agent-builder
cd agent-builder
pip install -e ".[dev]"

# 2. Add your API keys
cat > .env << 'EOF'
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-proj-...
GEMINI_API_KEY=AIza...
EOF

# 3. Start the backend server
python -m attractor.server

# 4. Open the visual builder
open http://localhost:8000
```

The server starts on **http://localhost:8000** by default. The visual builder is served from the same origin at `/`.

---

## Using the Visual Builder

The builder is a single-page app at `http://localhost:8000`. It has three panels:

| Panel | Purpose |
|---|---|
| **Left** | Node palette, connection tool, pipeline settings |
| **Center** | Interactive graph canvas |
| **Right** | Properties for the selected node or edge |

### Adding Nodes

Click any node type in the left panel to add it to the canvas. The node appears near the center — drag it to reposition. You can add multiple nodes of the same type (except **Start** and **Exit**, which are singletons).

### Connecting Nodes

1. Click **Connect Nodes** in the left panel (it turns blue when active).
2. Click the **source** node — it highlights with a blue border.
3. Click the **target** node — an arrow is drawn between them.
4. Click **Cancel** or press the button again to exit connection mode.

Each arrow is an **edge**. Click any edge on the canvas to open its properties in the right panel.

### Node Types

| Node | Purpose |
|---|---|
| **Start** | Entry point — every pipeline must have exactly one. |
| **LLM Call** | Sends a prompt to a language model and stores the response in pipeline context. |
| **Conditional** | Routing node — evaluates conditions on outgoing edges and follows the first match. |
| **Human Gate** | Pauses execution and waits for a human to approve or reject before continuing. |
| **Tool / Shell** | Runs a shell command and captures stdout/stderr into the pipeline context. |
| **HTTP Request** | Calls an external URL (GET/POST/PUT/etc.). Use for webhooks, browser APIs, or any external skill. |
| **Parallel Fork** | Fans out — launches multiple branches concurrently. |
| **Fan-In Join** | Collects results from all parallel branches before continuing. |
| **Manager Loop** | Supervisor node — observes a sub-pipeline and can steer or abort it. |
| **Exit** | Terminal node — every pipeline must have exactly one. |

Click a node on the canvas to edit its properties in the right panel. Fields vary by node type.

---

### Defining Conditions

> **Key concept:** conditions are set on **edges** (arrows), not on nodes.

A **Conditional** node is just a routing point. The logic lives on the arrows leaving it. When the engine reaches a Conditional node, it evaluates each outgoing edge's condition in order and takes the first one that matches.

**How to set a condition:**

1. Add a **Conditional** node and connect it to two or more target nodes.
2. Click the **Conditional** node — the right panel lists its outgoing edges.
3. Click an edge in that list (or click the arrow directly on the canvas).
4. In the right panel, fill in the **Condition** field.

**Condition syntax:**

| Expression | Meaning |
|---|---|
| `outcome=success` | The previous node's outcome equals `success` |
| `outcome=failure` | The previous node's outcome equals `failure` |
| `http.status_code=200` | An HTTP node returned status 200 |
| `tool.exit_code=0` | A shell command exited cleanly |
| `key!=value` | Not-equals check |
| `a=1 && b=2` | Both conditions must be true (AND) |
| *(empty)* | Default / fallback — always matches |

The engine checks edges in the order they appear in the DOT file (top-to-bottom as drawn). **Leave one edge with no condition** as a catch-all fallback to avoid a dead-end.

---

### Pipeline Settings

The **Pipeline Settings** section in the left panel applies to the whole graph:

| Field | Purpose |
|---|---|
| **Name** | The graph name used in the DOT `digraph` declaration. |
| **Goal** | A plain-language description stored as a graph attribute. LLM nodes can reference it via `$goal`. |
| **Model Stylesheet** | CSS-like rules that assign LLM models to nodes. Applied before execution. |

**Model Stylesheet syntax:**

```css
/* All nodes use Sonnet by default */
* { llm_model: claude-sonnet-4-5; }

/* Nodes with class "heavy" use Opus instead */
.heavy { llm_model: claude-opus-4-6; }

/* A specific node by ID */
#review_code { llm_model: gpt-5.2; }
```

Individual nodes can override the stylesheet model using the **LLM Model Override** dropdown in the node's properties panel.

---

### Viewing the DOT Source

Click **Source** in the top bar to toggle a panel at the bottom that shows the generated DOT file in real time. Click **Copy** to copy it to the clipboard.

---

## External Skills and Tool Calls

Attractor supports external skills at two levels:

### 1. Shell-based skills (Tool / Shell node)

Any skill that can be invoked from the command line works directly as a **Tool / Shell** node:

| Skill | Command |
|---|---|
| Run tests | `npm test` |
| Lint | `npx eslint src/ --max-warnings 0` |
| Build | `npm run build` |
| Playwright browser tests | `npx playwright test` |
| Lighthouse audit | `npx lighthouse https://localhost:3000 --output json` |
| Any CLI tool | `your-tool --flag` |

The node captures `stdout`, `stderr`, and `exit_code` into the pipeline context. Use a **Conditional** node after it with `tool.exit_code=0` to branch on success/failure.

### 2. HTTP-based skills (HTTP Request node)

Any skill that exposes an HTTP API works as an **HTTP Request** node. This covers:

- **Browser automation services** — BrowserStack Automate, Sauce Labs, LambdaTest
- **Custom skill servers** — your own FastAPI or Express microservice
- **MCP tool servers** — any MCP server with an HTTP transport
- **Webhooks** — GitHub Actions, Slack, PagerDuty, etc.
- **External AI services** — vision APIs, document parsers, code scanners

**HTTP node fields:**

| Field | Description |
|---|---|
| **URL** | Full endpoint URL. Supports `${variable}` interpolation from pipeline context. |
| **Method** | GET, POST, PUT, PATCH, or DELETE. |
| **Request Body** | JSON string to POST. Supports `${variable}` interpolation. |
| **Headers** | JSON object of headers. Use `{"Authorization": "Bearer ${MY_TOKEN}"}`. |

**Response context keys written after the request:**

| Key | Value |
|---|---|
| `http.status_code` | Integer status code (e.g. `200`) |
| `http.body` | Raw response body text |
| `http.json` | Parsed JSON object (if response is JSON) |
| `outcome` | `"success"` for 2xx, `"failure"` otherwise |

**Example: call a Playwright-as-a-service endpoint**

```dot
browser_check [shape=cds, url="https://my-browser-service.internal/run",
               method="POST",
               body="{\"url\": \"https://localhost:3000\", \"checks\": [\"title\", \"cta\"]}"]
```

### 3. Writing a custom Python handler

For full control, implement the `Handler` interface and register it before calling `run()`:

```python
from attractor.pipeline.handlers.base import Handler, HandlerInput
from attractor.pipeline.outcome import Outcome, StageStatus
from attractor.pipeline.engine import create_default_registry, run

class SlackNotifyHandler(Handler):
    async def execute(self, input: HandlerInput) -> Outcome:
        message = input.node.attrs.get("message", "Pipeline reached this stage.")
        # ... call Slack API ...
        return Outcome(status=StageStatus.SUCCESS, message="Slack notified")

registry = create_default_registry()
registry.register("slack", SlackNotifyHandler())

# Now any node with shape=slack in your DOT file will use this handler
await run(graph, registry=registry)
```

---

## Example: Build, Lint, and Browser-Validate a Web App

This pipeline builds a frontend app, checks for lint errors, asks an LLM to review the build output, then uses a browser automation step to validate the live page — looping back to fix issues if any check fails.

### Pipeline flow

```
start
  ↓
npm_build         [Tool: npm run build]
  ↓
check_build       [Conditional]
  ├─(outcome=failure)→ fix_build_errors  [LLM: fix the build errors]
  │                        ↓ back to npm_build
  └─(outcome=success)→ lint
  ↓
lint              [Tool: npx eslint src/ --max-warnings 0]
  ↓
check_lint        [Conditional]
  ├─(outcome=failure)→ fix_lint_errors   [LLM: fix the lint errors]
  │                        ↓ back to lint
  └─(outcome=success)→ browser_validate
  ↓
browser_validate  [HTTP: POST to Playwright service]
  ↓
check_browser     [Conditional]
  ├─(outcome=failure)→ fix_ui_errors     [LLM: fix the UI issues found]
  │                        ↓ back to npm_build
  └─(outcome=success)→ exit
```

### Steps in the builder

1. Add a **Start** node.
2. Add a **Tool** node, rename it `npm_build`, set command to `npm run build`.
3. Add a **Conditional** node, rename it `check_build`.
4. Add an **LLM Call** node, rename it `fix_build_errors`, set prompt to:
   `The build failed with this output: ${tool.stdout}. Fix the errors and explain what you changed.`
5. Add a **Tool** node, rename it `lint`, set command to `npx eslint src/ --max-warnings 0`.
6. Add a **Conditional** node, rename it `check_lint`.
7. Add an **LLM Call** node, rename it `fix_lint_errors`, set prompt to:
   `ESLint found these warnings/errors: ${tool.stdout}. Fix all of them.`
8. Add an **HTTP Request** node, rename it `browser_validate`. Set:
   - URL: `https://my-playwright-service.internal/validate`
   - Method: `POST`
   - Body: `{"url": "http://localhost:3000", "checks": ["title", "cta_visible", "no_console_errors"]}`
9. Add a **Conditional** node, rename it `check_browser`.
10. Add an **LLM Call** node, rename it `fix_ui_errors`, set prompt to:
    `Browser validation failed: ${http.body}. Fix the UI issues described.`
11. Add an **Exit** node.

**Connect them:**

| From | To | Condition |
|---|---|---|
| `start` | `npm_build` | — |
| `npm_build` | `check_build` | — |
| `check_build` | `fix_build_errors` | `outcome=failure` |
| `fix_build_errors` | `npm_build` | — |
| `check_build` | `lint` | `outcome=success` |
| `lint` | `check_lint` | — |
| `check_lint` | `fix_lint_errors` | `outcome=failure` |
| `fix_lint_errors` | `lint` | — |
| `check_lint` | `browser_validate` | `outcome=success` |
| `browser_validate` | `check_browser` | — |
| `check_browser` | `fix_ui_errors` | `outcome=failure` |
| `fix_ui_errors` | `npm_build` | — |
| `check_browser` | `exit` | `outcome=success` |

12. In **Pipeline Settings**, set **Goal** to describe the app under test.
13. Click **Validate**, then **Run Pipeline**.

### The generated DOT

```dot
digraph WebAppPipeline {
    graph [goal="Build, lint, and browser-validate the frontend app",
           model_stylesheet="* { llm_model: claude-sonnet-4-5; }"]

    start            [shape=Mdiamond]
    npm_build        [shape=parallelogram, command="npm run build"]
    check_build      [shape=diamond]
    fix_build_errors [shape=box,
                      prompt="The build failed: ${tool.stdout}. Fix the errors."]
    lint             [shape=parallelogram, command="npx eslint src/ --max-warnings 0"]
    check_lint       [shape=diamond]
    fix_lint_errors  [shape=box,
                      prompt="ESLint found errors: ${tool.stdout}. Fix all of them."]
    browser_validate [shape=cds, url="https://my-playwright-service.internal/validate",
                      method="POST",
                      body="{\"url\": \"http://localhost:3000\"}"]
    check_browser    [shape=diamond]
    fix_ui_errors    [shape=box,
                      prompt="Browser validation failed: ${http.body}. Fix the UI issues."]
    exit             [shape=Msquare]

    start            -> npm_build
    npm_build        -> check_build
    check_build      -> fix_build_errors  [condition="outcome=failure"]
    fix_build_errors -> npm_build
    check_build      -> lint              [condition="outcome=success"]
    lint             -> check_lint
    check_lint       -> fix_lint_errors   [condition="outcome=failure"]
    fix_lint_errors  -> lint
    check_lint       -> browser_validate  [condition="outcome=success"]
    browser_validate -> check_browser
    check_browser    -> fix_ui_errors     [condition="outcome=failure"]
    fix_ui_errors    -> npm_build
    check_browser    -> exit              [condition="outcome=success"]
}
```

---

## Running & Validating a Pipeline

| Button | What it does |
|---|---|
| **Validate** | Sends the DOT source to `POST /validate` and shows any lint errors (missing start/exit, unreachable nodes, invalid conditions, etc.). |
| **Run Pipeline** | Sends the DOT source to `POST /pipelines` to start execution. A toast notification shows the pipeline ID and polls for completion. |

---

## API Reference

The backend exposes a REST API at `http://localhost:8000`.

| Method | Path | Description |
|---|---|---|
| `GET` | `/pipelines` | List all pipelines |
| `POST` | `/pipelines` | Create and start a pipeline — body: `{ "dot_source": "..." }` |
| `GET` | `/pipelines/{id}` | Get pipeline status and metadata |
| `DELETE` | `/pipelines/{id}` | Cancel a running pipeline |
| `GET` | `/pipelines/{id}/events` | SSE stream of real-time pipeline events |
| `GET` | `/pipelines/{id}/context` | Get the current pipeline context (key-value store) |
| `GET` | `/pipelines/{id}/question` | Get pending human-gate question (if any) |
| `POST` | `/pipelines/{id}/answer` | Answer a human-gate question — body: `{ "answer": "..." }` |
| `POST` | `/validate` | Validate a DOT string — body: `{ "dot_source": "..." }` |
| `POST` | `/generate-dot` | Generate DOT from a JSON graph definition |
| `GET` | `/` | Serves the visual builder UI |

---

## Environment Variables

| Variable | Required for |
|---|---|
| `ANTHROPIC_API_KEY` | Claude models (Opus, Sonnet) |
| `OPENAI_API_KEY` | GPT models |
| `GEMINI_API_KEY` | Gemini models |
| `HOST` | Server bind address (default: `0.0.0.0`) |
| `PORT` | Server port (default: `8000`) |

---

## Running Tests

```bash
# Run all unit tests
pytest

# Run with coverage
pytest --cov=attractor --cov-report=term-missing

# Run only a specific layer
pytest tests/llm/
pytest tests/agent/
pytest tests/pipeline/

# Run integration tests (requires API keys in .env)
pytest -m integration
```

Tests are organised into three layers matching the codebase:

- `tests/llm/` — Unified LLM client (models, adapters, retry, streaming)
- `tests/agent/` — Coding agent loop (tools, session, profiles, subagents)
- `tests/pipeline/` — Pipeline engine (parser, validator, conditions, handlers)
- `tests/integration/` — End-to-end smoke tests against real APIs
