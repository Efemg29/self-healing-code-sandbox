# Self-Healing Code Sandbox

State-machine engine that generates Python code with an LLM, runs it inside an isolated sandbox, and autonomously patches failures through reflection.

## What it does

1. Accepts a natural-language coding task
2. Generates implementation + pytest suite (`instructor` + structured Pydantic schemas)
3. Executes tests in a locked-down Docker sandbox (or local pytest fallback)
4. Prunes traceback noise, reflects on the error, and retries (default max 3)

## Project layout

```text
core/
  config.py           # Environment settings
  models.py           # Strict Pydantic I/O schemas
  prompts.py          # System prompts
  llm_client.py       # Instructor-wrapped OpenAI client (+ mock mode)
  state_machine.py    # Generate → test → reflect loop
sandbox/
  docker_runner.py    # Container lifecycle + security constraints
  error_pruner.py     # Traceback sanitizer
main.py               # FastAPI UI/API + CLI
Dockerfile.sandbox    # Image used by the Docker sandbox
requirements.txt
```

## Quick start

```bash
chmod +x scripts/setup.sh
./scripts/setup.sh
```

Or manually:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
pytest
```

Without `OPENAI_API_KEY`, the app auto-enables **mock LLM mode** so you can demo the full loop offline.

### API / UI

```bash
python main.py serve
```

Open [http://127.0.0.1:43127](http://127.0.0.1:43127) — interactive UI, docs at `/docs`, health at `/health`.

### CLI

```bash
python main.py run "Write a function add(a, b) that returns the sum of two numbers."
```

### Tests

```bash
pytest
```

## Docker sandbox (recommended for production)

Build the sandbox image:

```bash
docker build -f Dockerfile.sandbox -t self-healing-sandbox:latest .
```

Hardening applied by `sandbox/docker_runner.py`:

| Constraint | Value |
|---|---|
| Network | `network_mode="none"` |
| Filesystem | `read_only=True` (+ `/app` bind mount, `/tmp` tmpfs) |
| Memory | `256m` |
| CPU | `0.5` core (`nano_cpus=500000000`) |
| PIDs | `50` (fork-bomb protection) |
| User | `nobody` |
| Timeout | 5s then `SIGKILL` |

If Docker is unavailable and `ALLOW_LOCAL_SANDBOX=true` (default), tests run with host `pytest` under the same timeout.

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `OPENAI_API_KEY` | unset | Live LLM calls |
| `OPENAI_MODEL` | `gpt-4o` | Chat model |
| `MAX_RETRIES` | `3` | Reflection loop attempts |
| `SANDBOX_TIMEOUT_SECONDS` | `5` | Kill runaway code |
| `SANDBOX_IMAGE` | `self-healing-sandbox:latest` | Sandbox image tag |
| `MOCK_LLM` | auto if no key | Offline deterministic generator |
| `ALLOW_LOCAL_SANDBOX` | `true` | Host pytest fallback |
| `PORT` | `43127` | API port |

## API

`POST /heal`

```json
{ "task_description": "Write a function factorial(n) that returns n!." }
```

Returns a `HealResult` with status, patched code, attempt history, and sandbox output.

## License

MIT
