"""Application entry point: FastAPI service + CLI runner."""

from __future__ import annotations

import argparse
import json
import logging
import sys

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from core.config import get_settings
from core.models import HealRequest, HealResult
from core.state_machine import SelfHealingStateMachine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("self_healing_engine")

settings = get_settings()
app = FastAPI(
    title="Self-Healing Code Sandbox",
    description=(
        "Generate Python code with an LLM, execute it in an isolated sandbox, "
        "and autonomously patch failures via reflection."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    mode = "MOCK LLM (offline demo)" if settings.mock_llm else f"Live ({settings.openai_model})"
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Self-Healing Code Sandbox</title>
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&family=Space+Grotesk:wght@500;700&display=swap" rel="stylesheet" />
  <style>
    :root {{
      --bg0: #0f1c18;
      --bg1: #17352c;
      --ink: #e8f2ec;
      --muted: #9bb5a8;
      --accent: #3dd68c;
      --accent-dim: #1f6f4a;
      --danger: #ff7b72;
      --panel: rgba(15, 36, 28, 0.72);
      --line: rgba(61, 214, 140, 0.22);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      min-height: 100vh;
      font-family: "IBM Plex Sans", sans-serif;
      color: var(--ink);
      background:
        radial-gradient(1200px 600px at 10% -10%, #245844 0%, transparent 55%),
        radial-gradient(900px 500px at 100% 0%, #1a3d55 0%, transparent 50%),
        linear-gradient(160deg, var(--bg0), var(--bg1) 55%, #0c1613);
    }}
    main {{
      width: min(920px, calc(100% - 2rem));
      margin: 0 auto;
      padding: 3.5rem 0 4rem;
    }}
    .brand {{
      font-family: "Space Grotesk", sans-serif;
      font-size: clamp(2rem, 5vw, 3.1rem);
      font-weight: 700;
      letter-spacing: -0.03em;
      margin: 0 0 0.4rem;
    }}
    .lede {{
      color: var(--muted);
      max-width: 42rem;
      line-height: 1.55;
      margin: 0 0 1.75rem;
    }}
    .mode {{
      display: inline-block;
      margin-bottom: 1.25rem;
      color: var(--accent);
      border-bottom: 1px solid var(--accent-dim);
      padding-bottom: 0.15rem;
      font-size: 0.92rem;
    }}
    label {{
      display: block;
      font-size: 0.85rem;
      color: var(--muted);
      margin-bottom: 0.45rem;
    }}
    textarea {{
      width: 100%;
      min-height: 7.5rem;
      resize: vertical;
      border: 1px solid var(--line);
      background: var(--panel);
      color: var(--ink);
      border-radius: 10px;
      padding: 0.9rem 1rem;
      font: inherit;
      line-height: 1.45;
    }}
    textarea:focus {{
      outline: 2px solid rgba(61, 214, 140, 0.35);
      border-color: var(--accent);
    }}
    .actions {{
      display: flex;
      gap: 0.75rem;
      flex-wrap: wrap;
      margin-top: 1rem;
    }}
    button {{
      font-family: "Space Grotesk", sans-serif;
      font-weight: 500;
      border: 0;
      border-radius: 8px;
      padding: 0.75rem 1.15rem;
      cursor: pointer;
      background: var(--accent);
      color: #062316;
    }}
    button.secondary {{
      background: transparent;
      color: var(--ink);
      border: 1px solid var(--line);
    }}
    button:disabled {{
      opacity: 0.55;
      cursor: wait;
    }}
    #status {{
      margin-top: 1rem;
      color: var(--muted);
      min-height: 1.4rem;
    }}
    #status.error {{ color: var(--danger); }}
    #status.ok {{ color: var(--accent); }}
    pre {{
      margin-top: 1.25rem;
      background: rgba(6, 16, 12, 0.8);
      border: 1px solid var(--line);
      border-radius: 10px;
      padding: 1rem;
      overflow: auto;
      max-height: 28rem;
      font-size: 0.84rem;
      line-height: 1.45;
      white-space: pre-wrap;
    }}
    .links {{
      margin-top: 1.5rem;
      color: var(--muted);
      font-size: 0.9rem;
    }}
    .links a {{ color: var(--accent); }}
  </style>
</head>
<body>
  <main>
    <p class="mode">{mode}</p>
    <h1 class="brand">Self-Healing Code Sandbox</h1>
    <p class="lede">
      Describe a Python task. The engine generates code and tests, runs them in an
      isolated sandbox, and reflects on failures until the suite passes or retries are exhausted.
    </p>
    <label for="task">Task description</label>
    <textarea id="task" placeholder="Write a function add(a, b) that returns the sum of two numbers.">Write a function add(a, b) that returns the sum of two numbers.</textarea>
    <div class="actions">
      <button id="run" type="button">Heal &amp; run</button>
      <button class="secondary" id="factorial" type="button">Try factorial demo</button>
    </div>
    <p id="status"></p>
    <pre id="out">Results will appear here.</pre>
    <p class="links">
      API docs: <a href="/docs">/docs</a> · Health: <a href="/health">/health</a>
    </p>
  </main>
  <script>
    const statusEl = document.getElementById("status");
    const outEl = document.getElementById("out");
    const taskEl = document.getElementById("task");
    const runBtn = document.getElementById("run");

    document.getElementById("factorial").addEventListener("click", () => {{
      taskEl.value = "Write a function factorial(n) that returns n! for non-negative integers.";
    }});

    runBtn.addEventListener("click", async () => {{
      const task = taskEl.value.trim();
      if (!task) {{
        statusEl.className = "error";
        statusEl.textContent = "Enter a task description.";
        return;
      }}
      runBtn.disabled = true;
      statusEl.className = "";
      statusEl.textContent = "Running generate → sandbox → reflect loop…";
      outEl.textContent = "";
      try {{
        const res = await fetch("/heal", {{
          method: "POST",
          headers: {{ "Content-Type": "application/json" }},
          body: JSON.stringify({{ task_description: task }}),
        }});
        const data = await res.json();
        if (!res.ok) {{
          throw new Error(data.detail || res.statusText);
        }}
        statusEl.className = data.status === "success" ? "ok" : "error";
        statusEl.textContent = data.status === "success"
          ? `Success in ${{data.attempts}} attempt(s)`
          : `Failed after ${{data.attempts}} attempt(s)`;
        outEl.textContent = JSON.stringify(data, null, 2);
      }} catch (err) {{
        statusEl.className = "error";
        statusEl.textContent = err.message || String(err);
      }} finally {{
        runBtn.disabled = false;
      }}
    }});
  </script>
</body>
</html>"""


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "mock_llm": settings.mock_llm,
        "model": settings.openai_model,
        "max_retries": settings.max_retries,
        "allow_local_sandbox": settings.allow_local_sandbox,
    }


@app.post("/heal", response_model=HealResult)
def heal(request: HealRequest) -> HealResult:
    """Generate, sandbox-test, and self-correct code for a task description."""
    try:
        machine = SelfHealingStateMachine(settings=settings)
        return machine.run(request.task_description)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Heal pipeline failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


def run_cli(task_description: str) -> int:
    machine = SelfHealingStateMachine(settings=get_settings())
    result = machine.run(task_description)
    print(json.dumps(result.model_dump(mode="json"), indent=2))
    return 0 if result.status.value == "success" else 1


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Self-Healing Code Sandbox — API server or one-shot CLI"
    )
    sub = parser.add_subparsers(dest="command")

    serve = sub.add_parser("serve", help="Start the FastAPI server (default)")
    serve.add_argument("--host", default=None)
    serve.add_argument("--port", type=int, default=None)

    cli = sub.add_parser("run", help="Run a single heal job on the CLI")
    cli.add_argument("task", help="Natural-language coding task")

    args = parser.parse_args(argv)
    command = args.command or "serve"

    if command == "run":
        raise SystemExit(run_cli(args.task))

    host = args.host or settings.host
    port = args.port or settings.port
    logger.info(
        "Starting server on %s:%s (mock_llm=%s)",
        host,
        port,
        settings.mock_llm,
    )
    uvicorn.run("main:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    main(sys.argv[1:])
