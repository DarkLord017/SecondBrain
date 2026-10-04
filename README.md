System Design

<img width="1288" height="822" alt="image" src="https://github.com/user-attachments/assets/d1aa2f52-c913-492d-b4ec-52a78053160f" />


## Running locally

1. `docker compose up -d` — starts Postgres, Redis, and Neo4j.
2. `cp .env.example .env` and fill in `OPENAI_API_KEY` (an OpenRouter key by default — `OPENAI_API_BASE_URL` points there unless you override it), `LLM_MODEL` (an OpenRouter-style slug, e.g. `anthropic/claude-sonnet-4.5`), `SUPERMEMORY_API_KEY`, `LLAMAPARSE_API_KEY`, and `TAVILY_API_KEY`. `LANGFUSE_PUBLIC_KEY`/`LANGFUSE_SECRET_KEY` are optional — chat works fine without them, you just don't get tracing. `NEO4J_PASSWORD` defaults to `changeme123`, matching `docker-compose.yml`.
3. `python3 -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"` (requires `libmagic` — `brew install libmagic` on macOS).
4. `uvicorn secondbrain.main:app --reload`

## Endpoints

| Method & Path | Notes |
|---|---|
| `POST /auth/signup`, `POST /auth/login` | No real auth/session — just user records, dual-written to Postgres + Supermemory + Neo4j. |
| `POST /notebooks`, `GET /notebooks`, `GET /notebooks/{id}` | Notebook CRUD, dual-written to Supermemory + Neo4j on creation. |
| `POST /notebooks/{id}/upload` | See **Upload pipeline** below. |
| `GET /notebooks/{id}/documents/{document_id}` | Poll processing status: `queued → done \| failed \| timeout`. |
| `POST /notebooks/{id}/chat` | Runs the orchestrator as a background task; returns `run_id` immediately regardless of whether a client ever connects to the WS. |
| `GET /runs/{run_id}` | Polling fallback — works with no WebSocket involved at all. |
| `WS /ws/runs/{run_id}` | Streams `token` / `status` / `final` / `error` frames via Redis pub/sub, replaying any buffered history first so reconnects don't miss anything. |

## Upload pipeline

Gateway firewall → MIME/size guardrails (magic-byte sniffing, never trusts client content-type) → malware scan → per-(user, notebook) upload quota → branches on type:

- **Handwritten notes** → LlamaParse (handwriting → markdown) → `Supermemory.add_document`.
- **Everything else** (PDF, docs, images, audio, video, plain text) → straight to Supermemory's own file ingestion (`/v3/documents/file`), which parses it.

Either way, once Supermemory's parsed text comes back, a background task extracts key concepts (structured LLM call) and merges them into the Neo4j idea graph (`(:Notebook)-[:HAS_IDEA]->(:Idea)`, plus `RELATES_TO`/`CONTRADICTS` edges) — this runs *after* the document's status flips to `done`, so `done` means "text is in and searchable," not "idea graph is updated yet." A retry worker (`ingestion/retry_worker.py`) sweeps documents stuck in `timeout` every 2 minutes.

## Orchestrator

LangGraph, real agent↔tools loop (not a fixed plan-then-execute pipeline):

```
hydrate → warm_up → prime_context → agent ⇄ tools → finalize → fact_check → END
```

- **hydrate** — loads notebook context, resets per-turn `tool_results`/`citation_flags`, appends the new question to `messages`.
- **warm_up** / **prime_context** — proactive RAG: a quick Recall / Finder search before the agent's first turn, folded into its system prompt as background context (not a fake tool-call message), so it isn't deciding blind.
- **agent** — calls the LLM with `bind_tools()` over the `TOOL_REGISTRY`; its own final non-tool-calling message *is* the cited answer (no separate writer call).
- **tools** — executes whichever tools the model actually requested (in parallel), wrapped as real `StructuredTool`s so each call shows up as its own traced span, not buried inside one opaque node.
- Loops agent ↔ tools up to `MAX_AGENT_STEPS` (4) round trips before forcing a finalize.
- **finalize** — packages `citations` from accumulated tool results and the final answer text; no LLM call.
- **fact_check** — post-hoc: for every `[n]` the final answer actually cites, re-verifies the claim against a fresh Tavily web search + LLM judgment (independent of the originally retrieved source, so it catches a hallucinated or misattributed citation, not just a self-confirming echo). Runs all citations concurrently.

**Conversation memory**: a real `AsyncPostgresSaver` checkpointer, keyed by a stable `thread_id = f"{notebook_id}:{user_id}"` (not per-message `run_id`), so follow-up questions in the same notebook resolve using prior turns.

**Tools** (`TOOL_REGISTRY` in `orchestrator/registry.py` — adding one is additive, never a rewrite):

| Tool | Backs onto | Scope |
|---|---|---|
| **Finder** | Supermemory | The user's own uploaded notes in this notebook. |
| **Scout** | Tavily | The public web, for anything outside the notebook. |
| **Recall** | Supermemory | Facts previously learned about the user as a person (profile, preferences) — not notebook content. |
| **Linker** | Neo4j | How ideas in this notebook connect to each other (the idea graph), not raw content. |
| **Skeptic** | Neo4j | Known contradictions between ideas in this notebook. |

**Observability**: Langfuse (optional, enabled when `LANGFUSE_PUBLIC_KEY`/`LANGFUSE_SECRET_KEY` are set) traces both the LLM calls and every real tool execution as its own span.

## Gateway

`gateway/firewall.py` (Guardrails AI — prompt-injection/banned-keyword rejection, PII/secret redaction on the way out), `gateway/throttle.py` and `gateway/spend_cap.py` (per-`(user_id, notebook_id)`, reserve→settle pattern), `gateway/cache.py` (Redis exact-hash check first, then a Supermemory similarity search before falling through to a full orchestrator run).

## Testing

- Unit tests live next to the code they test (`secondbrain/<module>/tests/*.py`), run with `pytest` — mocked LLM/DB/network calls, no live infra required.
- Live, non-pytest scripts (`secondbrain/<module>/tests/real_*_check.py` and the top-level `tests/real_*_check.py`) hit the real Supermemory/Tavily/LLM/Neo4j/Postgres/Redis stack directly — including full HTTP-API end-to-end flows, upload fan-out verification across all three stores, and chat response verification both via WebSocket streaming and plain HTTP polling. Run these individually (`python tests/real_full_api_flow_check.py`, etc.) against a running `docker compose up -d` stack and `uvicorn` server; they're not part of the `pytest` run.
