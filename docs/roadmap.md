# Roadmap and tasks

Where the build stands and what comes next. The full phase plan and its gates
are in [product-plan.md](product-plan.md#phased-roadmap) and the detailed work
breakdown is in [technical-plan.md](technical-plan.md#work-breakdown). Last
updated 24 October 2026.

## Phases at a glance

| Phase | What ships | Gate to move on | Status |
| --- | --- | --- | --- |
| 0. Foundation | Repo, CI, local stack, auth, landing page, staging deploy, voice test, rubrics, policies | A candidate can sign up and the stack deploys automatically | In progress |
| 1. Practice interviews | AI interview in the browser for the two launch roles, feedback report, learning plan, progress view, free-session cap | Candidates come back and rate reports useful; the pool has strong candidates | Started (text interviews work) |
| 2. Certified assessment | Identity checks, Electron secure wrapper, human review queue, opt-in certified profile that expires | False-positive rate measured and low | Not started |
| 3. Company pilots | Company dashboard with anonymised certified profiles; 2 or 3 partners skip their technical round | Certified candidates get offers after one company interview more often than the company's own pipeline | Not started |
| 4. Revenue on both sides | Paid company plans with a replacement guarantee, paid candidate tiers, more roles, wrapper sold to companies | | Not started |

## Done

Grading queue: arq/Redis, bounded retries, recovery and offline fallback. PR link pending creation.

**[PR #1](https://github.com/godara01/getter/pull/1), merged 23 October 2026:
text practice interviews end to end.**

- Monorepo: FastAPI API in `services/api`, Next.js static site in `apps/web`
  (built for Cloudflare Pages), Postgres via Docker Compose, GitHub Actions CI
  running API tests on SQLite and Postgres, web unit tests and a browser
  end-to-end test.
- Provider-agnostic LLM gateway: adapters for any OpenAI-compatible API and
  for Anthropic, plus an offline dev model so everything runs with no keys.
  Per-task model routing in YAML, fallback to a second model, our own JSON
  validation with a repair retry, cost per call and per session in rupees.
- Rubrics and interview templates (versioned YAML) for backend and DevOps/SRE,
  junior and mid.
- Interview engine: four timed sections, follow-up questions when an answer is
  thin, time limits and follow-up budget enforced in code.
- Grader: a 1 to 4 score per skill, each backed by verbatim quotes checked in
  code, verdict computed from the scores, optional second grader that flags
  disagreements. A failed grading never produces a score.
- Website: pick a role, take the interview as a chat, read the report and
  learning plan, see past sessions.
- Eval harness (`python -m getter_api.evals`) that compares model configs
  against expert-graded transcripts. The shipped cases are synthetic and only
  test the harness.

## Needed from Sanket

These block real model choice and going live:

- [ ] **API keys for 2 or 3 AI providers** (for example Anthropic, Google and
  OpenAI, or a single OpenRouter account to start), with billing on a card
  that works for international payments. Add them as environment secrets,
  never paste them into chat.
- [ ] **20 to 30 interviews graded by an experienced interviewer** for each
  role (one person can cover both if qualified). This is what lets the eval
  harness pick the cheapest model that grades well enough.
- [ ] Accounts for staging: domain and DNS, Cloudflare Pages linked to the
  repo, a small server in Mumbai or Bangalore, managed Postgres and a storage
  bucket, Clerk, Resend, Sentry and PostHog.
- [ ] Later: a LiveKit Cloud project and speech-to-text and text-to-speech
  accounts, after the voice test.

## Next up

Roughly in order; each is about one pull request.

1. [ ] **Real accounts with Clerk.** Today sign-in is a dev email header that
   is refused in staging and production.
2. [ ] **Real model choice.** Run the eval harness across providers once keys
   and expert-graded transcripts exist; set the per-task models in config.
3. [ ] **Staging deploy.** Web on Cloudflare Pages, API on the small Mumbai
   server, managed Postgres, deployed from every merge to `master`.
4. [x] **Job queue for grading** (Redis and arq), so grading runs after the
   session instead of in the request.
5. [ ] **Landing page and waitlist**, consent records and the audit log.
6. [ ] **Free-session caps** using the per-session cost already tracked.
7. [ ] **Voice test**: a LiveKit room where the model holds a 5 minute spoken
   conversation; measure latency and cost per minute, then decide whether to
   keep LiveKit and which speech vendors to use.
8. [ ] **Coding and DevOps sections**: Monaco editor and sandboxed runs for
   backend, a browser terminal with scripted scenarios for DevOps.
9. [ ] **Razorpay paid tier** for more sessions.
10. [ ] **Privacy policy, terms and consent text**, version 1.

Phase 2 (identity checks and the Electron secure wrapper) gets its own
breakdown once phase 1 passes its gate.
