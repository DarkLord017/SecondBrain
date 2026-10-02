System Design

<img width="3640" height="2420" alt="image" src="https://github.com/user-attachments/assets/2368a021-6673-4169-a298-6e0315c00593" />

## Running locally

1. `docker compose up -d` — starts Postgres, Redis, and Neo4j.
2. `cp .env.example .env` and fill in `OPENAI_API_KEY` (an OpenRouter key by default — `OPENAI_API_BASE_URL` points there unless you override it), `LLM_MODEL` (an OpenRouter-style slug, e.g. `anthropic/claude-sonnet-4.5`), `SUPERMEMORY_API_KEY`, and `LLAMAPARSE_API_KEY`.
3. `python3 -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"` (requires `libmagic` — `brew install libmagic` on macOS).
4. `uvicorn secondbrain.main:app --reload`

## What's built so far

An endpoint-first slice of the architecture above:

- `POST /auth/signup`, `POST /auth/login` — no real auth/session yet, just user records (dual-written to Postgres, Supermemory, and Neo4j on signup).
- `POST /notebooks`, `GET /notebooks`, `GET /notebooks/{id}` — notebook CRUD, dual-written to Supermemory + Neo4j on creation.
- `POST /notebooks/{id}/upload` — gateway firewall → MIME/size guardrails → malware scan → upload quota → branches to LlamaParse (handwritten notes) or directly to Supermemory's own file ingestion (everything else) → background idea extraction into the Neo4j graph.
- `POST /notebooks/{id}/chat` — firewall → throttle → cache (exact hash, then Supermemory similarity search) → spend cap → runs the LangGraph orchestrator (Hydrate → Planner → Fan-out → Router → Writer) as a background task.
- `WS /ws/runs/{run_id}` — streams the run's tokens/final answer via Redis pub/sub, replaying any buffered history so reconnects don't miss anything.

Only one tool-agent (**Finder**, over Supermemory) is wired into the orchestrator so far; Scout/Recall/Linker/Skeptic and the Neo4j-based clash check are not yet implemented. The `TOOL_REGISTRY` pattern in `secondbrain/orchestrator/registry.py` means adding them later is additive, not a rewrite.

Run `pytest` for the unit tests (firewall, throttle, spend-cap, cache, and a LangGraph control-flow smoke test — all passing with mocked LLM/DB/network calls, no live infra required).

