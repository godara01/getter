# Getter

Getter rates engineers on their real skills so companies can hire them without
long interview loops. Phase 1 builds the candidate side: free AI practice
interviews with honest, evidence-based feedback. Practice results are private
to the candidate.

Plans: [product plan](https://claude.ai/artifact/17PjzxH6wzBWE9FCVnp2XE) ·
[technical plan](https://claude.ai/artifact/4KbLJBThG1c2pbPHuLwZWi)

## What works today

- **Text practice interviews** for two launch roles: backend engineer and
  DevOps/SRE engineer, junior to mid level. Four timed sections each (past
  work, design, debugging or troubleshooting, and a concurrency or incident
  scenario), with follow-up questions when an answer is thin.
- **Feedback report**: a 1 to 4 score per rubric skill, each backed by quotes
  of the candidate's own words, a verdict against the target level, strengths,
  and a learning plan for the top gaps.
- **Provider-neutral AI layer**: every AI call goes through one gateway with
  per-task model routing in YAML, fallback to a second model, our own JSON
  validation with a repair retry, and cost tracking per call and per session.
  Adapters cover any OpenAI-compatible API (OpenAI, OpenRouter, Gemini, Groq,
  DeepSeek, Ollama, vLLM) and Anthropic. An offline dev model lets everything
  run with no keys.
- **Eval harness** that scores any model config against expert-graded
  transcripts, to pick the cheapest model that grades close enough.

Not yet: real sign-in (a dev email header for now), voice, code sandbox,
payments, deploys. See the technical plan for the order.

## Layout

```
apps/web          Next.js site (static export for Cloudflare Pages)
services/api      FastAPI service, interview engine, grader, LLM gateway
  src/getter_api/content   rubrics and interview templates (YAML, versioned)
  src/getter_api/llm       provider-neutral model gateway and adapters
  src/getter_api/evals     model comparison against expert grades
```

## Run it locally

Needs Python 3.12+ with [uv](https://docs.astral.sh/uv/), Node 22 and pnpm.

```sh
# API on http://localhost:8000 (SQLite by default, offline dev models)
cd services/api
uv sync
uv run alembic upgrade head
uv run uvicorn getter_api.main:create_app --factory --reload

# Website on http://localhost:3000
pnpm install
pnpm web:dev
```

Or run Postgres and the API with `docker compose up --build`.

To use real models, copy `services/api/src/getter_api/llm/llm.example.yaml`,
fill in models and prices, set `GETTER_LLM_CONFIG` to its path and export the
API keys it names.

## Tests

```sh
cd services/api && uv run pytest     # API, gateway, grading, evals
cd apps/web && pnpm test              # web unit tests
cd apps/web && NEXT_PUBLIC_API_URL=http://localhost:8100 pnpm build && pnpm e2e
                                      # a full interview in a real browser
```

CI runs all of these on every pull request, with the API tests on both SQLite
and Postgres.
