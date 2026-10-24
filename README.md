# Getter

Getter rates engineers on their real skills so companies can hire them without
long interview loops. Phase 1 builds the candidate side: free AI practice
interviews with honest, evidence-based feedback. Practice results are private
to the candidate.

Plans, goals and progress live in [docs/](docs/README.md):
[goals and decisions](docs/goals-and-decisions.md) ·
[roadmap](docs/roadmap.md) · [product plan](docs/product-plan.md) ·
[technical plan](docs/technical-plan.md) ·
[product critique](docs/product-critique.md)

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
- **Waitlist and consent records**: email/role signup, draft terms acceptance,
  private consent list and withdrawal, and audited report/score views and deletion.
- **Eval harness** that scores any model config against expert-graded
  transcripts, to pick the cheapest model that grades close enough.

- **Clerk accounts** with cached JWT verification, plus offline dev email sign-in.

Not yet: voice, code sandbox,
payments, deploys. See the [roadmap](docs/roadmap.md) for the order.

## Layout

```
apps/web          Next.js site (static export for Cloudflare Pages)
services/api      FastAPI service, interview engine, grader, LLM gateway
  src/getter_api/content   rubrics and interview templates (YAML, versioned)
  src/getter_api/llm       provider-neutral model gateway and adapters
  src/getter_api/evals     model comparison against expert grades
docs              plans, goals, decisions and roadmap
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

The landing page waitlist sends no email. The API allows five validated
submissions per IP per hour (`GETTER_WAITLIST_REQUESTS_PER_HOUR`). Terms are
clearly marked **draft, pending legal review** at `/terms/`; accepting them
records the text version at account registration and at each session start.
`/consents/` lists and withdraws those records. Withdrawal does not delete
interviews; use My interviews to erase transcripts and reports.

## Clerk accounts

Local use needs no account or key. To use Clerk, set
`NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` when building the static web app. Set
`GETTER_AUTH_MODE=clerk`, `GETTER_CLERK_ISSUER`, `GETTER_CLERK_JWKS_URL` and
`GETTER_CLERK_AUTHORIZED_PARTIES` (a JSON list of allowed web origins) on the API.
See both `.env.example` files. In staging/production dev authentication is
refused. Clerk subjects create candidate accounts on first use; default tokens
do not include email, so the API stores an internal placeholder address and
never links existing dev accounts by email. Configure Clerk's sign-up terms
when preparing a deployed instance.
