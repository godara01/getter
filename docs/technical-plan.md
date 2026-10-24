# Getter: technical plan

Written 23 October 2026, before any code existed. Copied from the project doc
[Getter: technical plan](https://claude.ai/artifact/4KbLJBThG1c2pbPHuLwZWi) on
23 October 2026. Product decisions are in [product-plan.md](product-plan.md);
what has been built so far is in [roadmap.md](roadmap.md).

> **Where the code differs from this plan (as of PR #1)**
>
> - **No LiteLLM.** The model gateway uses our own small httpx adapters (any
>   OpenAI-compatible API, Anthropic, and an offline dev model) in
>   `services/api/src/getter_api/llm/`. The design rules below (per-task
>   config, fallback, our own JSON validation, cost tracking) are unchanged.
> - **Website hosting is Cloudflare Pages**, as in the stack table. The
>   original doc's phase 0 checklist and account list named Vercel and
>   Fly.io/Render; this copy uses Cloudflare Pages and the small Mumbai server
>   to match the stack and budget decisions. Mentions of a specific model as
>   "the" choice were also reworded as examples, to match the no-lock-in
>   decision.
> - **Layout is smaller so far:** `apps/web` and `services/api` only.
>   Migrations live in `services/api/migrations`, and rubrics and templates in
>   `services/api/src/getter_api/content`, not in `infra/` and `packages/`.
> - **Interviews are text only** for now. Voice, the code sandbox,
>   Razorpay and deploys are not built yet. Clerk sign-in is implemented with
>   `@clerk/clerk-react` for static export and PyJWT/JWKS verification in the API;
>   local development still works without keys.
> - **Model names** in the budget and AI sections are examples. No provider is
>   chosen; the eval harness decides, per task, on cost and quality.

This is the build plan for the implementation thread: a Next.js website, a Python backend, Postgres, a model-neutral AI layer for the interviewer and grader, LiveKit for voice, and an Electron secure browser wrapper, delivered phase by phase.

## Tech stack

We use managed services wherever possible, so a small team spends its time on interviews and feedback, not infrastructure. Every choice is a recommendation to confirm in phase 0. Vendor details are from memory unless linked.

| Layer | Choice | Why | Fallback |
| --- | --- | --- | --- |
| Website | Next.js (React, TypeScript), Tailwind | One codebase for marketing pages, candidate app and company portal | Remix |
| Website hosting | Cloudflare Pages (free plan, commercial use allowed) | Fits the budget; Vercel's free plan is for non-commercial use only | Vercel Pro once revenue allows |
| Backend API | Python 3.12+, FastAPI, SQLAlchemy, Pydantic | Python has the strongest AI and audio tooling; FastAPI gives typed APIs and OpenAPI for free | Node.js with NestJS |
| Backend hosting | One small Linux server in Mumbai or Bangalore (AWS Lightsail or DigitalOcean), running Docker Compose | API, workers, Redis and the voice agent on one machine keeps the base cost around ₹400 to ₹600 a month | Google Cloud Run when traffic grows |
| Background jobs | Redis queue (arq) on the same server | Report generation and grading run after the call, not during it | Cloud task queue |
| Realtime voice and video | LiveKit Cloud free tier, with the LiveKit Agents framework for the AI interviewer | Open source WebRTC with a Python agent framework; can self-host later | Daily, Pipecat |
| Interviewer and grader AI | Any provider, behind our own model gateway; starting candidates include Claude, Gemini, OpenAI and open-weight models | No lock-in: each task (live turns, grading, reports) picks its model from config, chosen on eval score per rupee | OpenRouter as a single hosted endpoint |
| Speech-to-text | Deepgram or AssemblyAI (streaming) | Low-latency streaming transcription with speaker separation | Whisper, self-hosted |
| Text-to-speech | Cartesia or ElevenLabs (streaming), chosen on cost and quality in the phase 0 test | The biggest variable cost in a voice interview | Cloud provider TTS |
| Coding and shell sandbox | Judge0 (self-hosted) for code; short-lived Docker containers for DevOps tasks | Runs candidate code and commands safely | Piston |
| Code editor and terminal | Monaco editor and xterm.js | The VS Code editor and a real terminal in the browser | CodeMirror |
| Database | PostgreSQL 16 on Neon's free tier (or on the same server), with pgvector | Relational data plus vector search; no cost at launch | Supabase, AWS RDS |
| File storage | Cloudflare R2 (free up to 10 GB) | Recordings, transcripts, ID images, with lifecycle deletion | AWS S3 Mumbai |
| Auth | Clerk free tier | Candidate and company accounts, organisations for companies, SSO later | Auth.js, Supabase Auth |
| Secure wrapper | Electron, with native Node modules for Windows and macOS checks | Bundles Chromium so Meet, Teams and Zoom web behave identically | Tauri (rejected: system webviews differ) |
| Face and gaze | MediaPipe Face Landmarker, running locally in the wrapper | Open source; video frames never leave the laptop for this check | OpenCV models |
| Email | Resend free tier | Invites, reports, reminders | Postmark, SES |
| Payments | Razorpay | UPI, cards and netbanking for Indian candidates and companies | Cashfree, Stripe for international |
| Monitoring | Sentry and PostHog free tiers, OpenTelemetry | Catch failures in live interviews quickly | Grafana Cloud free tier |
| CI/CD | GitHub Actions | Already on GitHub; builds web, API and signed desktop installers | None needed |

## Launch scope (decided 23 October)

- **Roles:** backend engineer, junior to mid; DevOps and SRE engineer, junior to mid.
- **Market:** India first. Interviews in English. Prices in rupees, payments through Razorpay, servers in Mumbai or Bangalore for low latency.
- **Budget:** about ₹500 to ₹700 a month with no traffic, rising to ₹5,000 to ₹10,000 only when real usage justifies it.
- **Voice:** kept in the plan; vendors to be chosen after the phase 0 test.

**What the roles mean for interviews.** At junior to mid level the interviews test fundamentals and hands-on skill more than large-scale system design.

| Role | Sections |
| --- | --- |
| Backend, junior to mid | A coding task with tests; API and database design for a small service; debugging an existing piece of code; deep questions on the candidate's own projects |
| DevOps and SRE, junior to mid | Linux and networking troubleshooting in a real terminal; writing a Dockerfile or CI pipeline; reading logs and metrics to find an incident's cause; deep questions on systems the candidate has run |

DevOps tasks need a real shell, so each candidate gets a short-lived, locked-down container with no internet access, destroyed after the session. Phase 1 can start with scripted scenarios (prepared logs and command outputs) and add live containers once the budget allows.

## Budget fit

The base setup fits ₹500 to ₹700 a month. The cost of each interview is what decides how many free interviews we can offer. All free-tier limits and vendor prices below are from memory, except Claude's, and are to be confirmed in phase 0. Most services bill in US dollars, so you'll need a card that works internationally.

| Item | Choice | Approx. per month |
| --- | --- | --- |
| Server (API, workers, Redis, voice agent) | One small server in Mumbai or Bangalore | ₹400 to ₹600 |
| Website | Cloudflare Pages free plan | ₹0 |
| Database, storage, auth, email, monitoring | Free tiers of Neon, R2, Clerk, Resend, Sentry and PostHog | ₹0 at launch |
| LiveKit | Free tier | ₹0 at low use |
| Domain | .com or .in, paid yearly | about ₹70 to ₹100 |

**Rough cost of one 40 minute interview** (list prices at about ₹88 to the dollar; the phase 0 test measures the real number):

| Part | Voice interview | Text and code interview |
| --- | --- | --- |
| Claude for live turns (Claude Opus 5.5, about 60 turns, cached prompt) | ₹60 to ₹90 | ₹60 to ₹90 |
| Claude for grading (Claude Opus 5.5, high effort) | ₹25 to ₹40 | ₹25 to ₹40 |
| Speech-to-text | ₹20 to ₹30 | ₹0 |
| Text-to-speech | ₹40 to ₹250, depending on vendor | ₹0 |
| **Total** | **₹150 to ₹400** | **₹90 to ₹130** |

**What this means:** ₹10,000 a month covers roughly 25 to 65 voice interviews or 75 to 110 text interviews. So free use has to be small (for example, one free interview per candidate), and paid interviews must be priced above cost. The two biggest levers are text-to-speech vendor choice and which model handles the live turns. The model figures above are one example option; the provider-neutral layer lets each task use the cheapest model that passes the evals.

## Repository layout and environments

One monorepo in `godara01/getter`, managed with pnpm workspaces and Turborepo for the TypeScript parts and uv for Python. This is the target layout; see the note at the top for what exists today.

```
getter/
  apps/
    web/            Next.js: marketing site, candidate app, company portal
    desktop/        Electron secure browser wrapper (phase 2)
  services/
    api/            FastAPI: accounts, sessions, scoring, review queue
    interviewer/    LiveKit agent worker: speech-to-text, LLM, text-to-speech
    worker/         Background jobs: grading, reports, retention deletes
  packages/
    api-client/     TypeScript client generated from the API's OpenAPI schema
    rubrics/        Role rubrics and question banks as versioned YAML
    ui/             Shared React components
  infra/            Docker files, deploy config, database migrations (Alembic)
  docs/             Architecture notes and decision records
  .github/          CI workflows
```

**Environments:** `local` (Docker Compose with Postgres, Redis and a local LiveKit server), `staging` (deployed from every merge to `master`, test data only), and `production` (deployed from tagged releases). Each environment has its own database, storage bucket, LiveKit project and API keys. Secrets live in the hosting platform's secret store, never in the repo.

**Conventions:** typed everywhere (TypeScript strict, Pydantic models, mypy), database changes only through migrations, rubrics changed only by pull request so every score can be traced to the rubric version that produced it.

## Data model

Core tables, grouped by the phase that first needs them. Every table carries `id` (UUID), `created_at` and `updated_at`; personal data tables also carry a `deleted_at` for erasure requests.

| Table | Holds | Phase |
| --- | --- | --- |
| `users` | Login identity (from Clerk), name, email, country, role (candidate, company member, reviewer, admin) | 0 |
| `consents` | Each consent given or withdrawn: type (terms, recording, biometric checks, share with companies), version of the text, time | 0 |
| `candidate_profiles` | Target role family and level, years of experience, CV file, job-seeking status | 1 |
| `role_rubrics` | Role family, level, rubric version, skills and what each score means | 1 |
| `interview_templates` | Which rubric, the sections (coding, design, past work), time limits, question bank reference | 1 |
| `sessions` | Candidate, template, type (practice or certified), status, start and end times, AI cost | 1 |
| `session_turns` | Ordered transcript: speaker, text, timestamps, code snapshots | 1 |
| `skill_scores` | Session, skill, score, evidence (links to turns), rubric version, grader model and effort | 1 |
| `feedback_reports` | Session, summary, top gaps, strengths, verdict against the target level | 1 |
| `learning_items` | Gap, practice tasks, suggested material | 1 |
| `identity_verifications` | Candidate, method, result, provider reference (no raw ID images kept after checking) | 2 |
| `devices` | Wrapper installs: device key, OS, app version, signature status | 2 |
| `integrity_events` | Session, check type, severity, time, details (process name, monitor count, face absent and so on) | 2 |
| `review_cases` | Flagged sessions, assigned reviewer, decision, notes | 2 |
| `certified_profiles` | Candidate, linked certified sessions, scores shown to companies, expiry date, visibility | 2 |
| `companies`, `company_members` | Company account and its people (Clerk organisations) | 3 |
| `company_interviews` | Company, candidate, meeting link, scheduled time, wrapper session, live status | 3 |
| `introduction_requests` | Company asking to meet a certified candidate, candidate's answer | 3 |
| `hire_outcomes` | Offer made, hired, 3, 6 and 12 month feedback | 3 |
| `audit_log` | Who viewed or changed what, especially scores and certified profiles | 0 |

## Landing page, consent and audit records (implemented)

The public waitlist stores normalized email and role interest with a unique
email constraint. A persistent, hashed-IP attempt log limits validated requests
to five per rolling hour, across API restarts. Old attempts are pruned on
submission. Duplicate responses do not disclose whether an email already exists.
No email service is used. Behind a proxy, configure uvicorn to trust forwarded
headers only from that proxy; arbitrary X-Forwarded-For headers are ignored.

Explicit draft terms acceptance creates an account consent through
`POST /account/terms`; first practice admission also records it if absent.
The existing session consent remains one record per start. Consent records
carry text versions, acceptance time, and withdrawal status/time. Candidates
can list and withdraw only their own records. Withdrawal preserves history;
it does not erase interviews or terminate a running session. Starting again
requires accepting terms again. The static terms page and API text version
must be updated together when legally reviewed wording replaces the draft.

Report views, score-bearing session list views and session deletion write
minimal actor/action/target audit entries through one helper. Ownership is
checked before logging; transcript/report deletion retains the audit record.

## Grading worker (implemented)

With `GETTER_REDIS_URL` set, session completion enqueues a unique arq job.
Redis persistence and a minute-by-minute worker sweep recover missed enqueues;
API startup also re-enqueues unfinished grading. The worker locks the session
and skips any state other than `grading`, retries at most three times, and
leaves exhausted grading as `failed` with no score. Failed billable model
calls remain recorded. Without Redis, local/test runs use in-process grading.
Redis and one worker are additional always-on processes on the existing small
server, not paid managed services. Compose starts them together.

## Key flows

**Practice session (phase 1, browser only):**

1. The candidate signs in, completes their profile, and accepts the recording consent.
2. They pick a template (for example, "Backend engineer, mid"). The API creates a `session` and a LiveKit room, and returns a join token.
3. The browser joins the room with microphone (and optionally camera). The interviewer agent joins the same room.
4. The agent loop runs per turn: streaming speech-to-text, then the model decides the next question or follow-up from the rubric and transcript so far, then streaming text-to-speech. Every turn is saved to `session_turns`.
5. During coding sections the candidate writes in Monaco; snapshots and test runs go through the sandbox and are visible to the interviewer agent.
6. When the session ends, a background job grades the transcript against the rubric and writes `skill_scores`, `feedback_reports` and `learning_items`.
7. The candidate gets an email and sees the report, usually within a few minutes. Practice data is never visible to companies.

**Certified interview through the secure wrapper (phases 2 and 3):**

1. A company creates an interview in the portal and pastes its own Zoom, Teams or Meet link (or Getter runs its own certified AI interview).
2. The candidate receives an invite link. Opening it launches the wrapper through a custom URL scheme (`getter://`), or prompts them to install it.
3. The wrapper registers its device key, checks its own signature, and runs pre-flight checks: ID verification, camera and microphone, one monitor, no virtual machine, no blocked processes.
4. The wrapper opens the meeting link in a locked-down window and keeps checking for the whole call. It sends signed heartbeats and integrity events to the API every few seconds.
5. The portal shows the interviewer a live status (verified, warning or flagged), plus a rotating code that also appears in the wrapper, so the interviewer can confirm the person in the call is using the wrapper.
6. After the call, flagged sessions go to the human review queue. Only a reviewer can mark a session as failed for integrity reasons.

## AI design

**Model-neutral by design (decided 23 October).** No part of the product talks to an AI vendor directly. All calls go through one internal interface in services/api and services/interviewer:

- **Per-task model config.** Live turns, grading, report writing and the consistency check each name a provider and model in config (later in the database), so switching is a config change, not a code change.
- **One gateway.** Originally planned on the LiteLLM library; built instead as our own small adapters (see the note at the top). LiveKit Agents has plugins for several LLM providers, so the voice loop can switch too.
- **Our own structured outputs.** Every grading result is validated against our JSON schema in our code, with a retry on failure, because providers differ in how reliably they follow schemas.
- **Provider-neutral prompts,** stored and versioned in the repo. Provider features such as prompt caching are used where available but never required.
- **Eval-driven choice.** The expert-graded transcript set scores every candidate model. We pick the cheapest model that stays close enough to the expert's scores, separately for live turns and for grading.
- **Fallback.** If a provider fails or rate-limits, the gateway retries on a second configured model so an interview isn't lost.
- **Data rules per provider.** Only providers that let us opt out of training on our data and sign a data processing agreement may receive candidate data.

Model names elsewhere in this section and in Budget fit are examples of one option, not a commitment.

**Interviewer agent.** Runs as a LiveKit agent worker in Python. Its system prompt holds the role rubric, the interview plan and the rules: probe the candidate's own past work, ask one question at a time, never give answers away, never comment on emotions or personality. The rubric and plan sit at the start of the prompt so prompt caching keeps repeat turns cheap. Turn replies need to be fast, so we run them at low effort and measure response latency from the first day. The time budget per section is enforced in code, not left to the model.

**Grader.** A separate job runs after the session with a strong model at high effort (Claude Opus 5.5 was the example). It uses structured outputs that match a JSON schema: a score per skill, evidence quoting specific turns, the top three gaps, and a verdict against the target level. Grading never uses audio tone or video. A second grading pass checks consistency, and disagreements go to human review.

**Calibration and evals.** Before launch, an expert interviewer grades 20 to 30 real or mock transcripts by hand. That set becomes the eval: every change to prompts, rubric or model is scored against it, and we track how far AI scores are from the expert's. Rubrics are versioned, and every score records the rubric version, model and effort that produced it.

**Coding tasks.** The candidate codes in Monaco, and the code runs in an isolated sandbox with time and memory limits and no network access. The agent sees code snapshots and test results, not keystrokes.

**Cost controls.** New free sessions are checked against three limits: three
starts in a rolling 24 hours, ₹100 of recorded account model cost in a rolling
24 hours, and ₹300 of global model cost since midnight UTC. All are settings;
the account window is configurable. At or above a limit, admission returns 429
with a retry time and Retry-After header. Running interviews continue. Costs
include failed billable calls and retain account attribution after session
deletion. Offline calls cost zero. Admission also logs a warning when the
last day's average recorded model cost per remaining session exceeds ₹50
(configurable); deleted sessions still count toward spend limits. These are
limits on recorded spend, not reservations: concurrent ongoing sessions can
finish above a ceiling. Measure real model cost before adjusting pricing.

**Refusals and failures.** If the model declines, an API call fails or speech drops, the agent apologises, retries once, and otherwise ends the session cleanly and refunds the credit. A broken interview must never produce a score.

## Secure browser wrapper

An Electron app for Windows 10+ and macOS 13+ (Linux later, if asked for). It opens the meeting page unchanged in a locked-down window and runs these checks before and during the call.

| Check | How | When |
| --- | --- | --- |
| Known cheating tools running | Process list matched against a blocklist that updates from the server | Pre-flight and every few seconds |
| Hidden overlay windows (content that is hidden from screen share) | Window enumeration through native modules: on macOS the window sharing state, on Windows the capture-exclusion flag where the OS exposes it (to validate per OS version) | Continuous |
| Extra or mirrored monitors | Display APIs (Electron `screen` plus native calls) | Pre-flight and continuous |
| Virtual machine or remote desktop | Hardware and driver fingerprints, remote session flags | Pre-flight |
| Screen recording or capture software | Process list and capture-device enumeration | Pre-flight and continuous |
| Focus leaves the meeting window | Window focus and blur events; the wrapper runs full screen with app switching discouraged | Continuous |
| Face absent, multiple faces, gaze often off screen | MediaPipe on the local camera stream, shared with the meeting inside one process; only counts and timings are sent, not video | Continuous |
| Another voice in the room | Speaker count from the microphone stream | Continuous |
| Identity | ID document plus selfie match before the call, and periodic face match during it | Pre-flight and every few minutes |
| Person in the call is the wrapper user | Rotating code shown in both the wrapper and the portal | On demand by the interviewer |

**Tamper resistance:** signed and notarised builds; the app checks its own signature and reports its version; heartbeats are signed with a per-device key; developer tools and remote debugging are disabled; a missing heartbeat is itself an integrity event. The blocklist and check thresholds come from the server, so they can change without a new release.

**Permissions to request:** camera, microphone, and on macOS screen recording (for window and display checks) and accessibility. We explain each permission on screen before the OS prompt, and refuse to start a certified session without them.

**Meeting compatibility:** test Google Meet (guest join; Google blocks account sign-in in embedded browsers), Microsoft Teams web (anonymous join depends on the host's settings) and the Zoom web client (host must allow joining from the browser). We never inject scripts into or modify these pages.

**Limits we state openly:** a second device out of view, a helper off camera, an earpiece or a capture card cannot be detected from the laptop. Interview design (deep follow-ups) and human review cover these. Integrity signals are evidence for a reviewer, never an automatic fail.

## Security, privacy and compliance

- **Access control:** candidates see only their own data; companies see only certified profiles that candidates chose to share; reviewers see only assigned cases. Enforced in the API and backed by database row-level policies.
- **Encryption:** TLS everywhere; encryption at rest for the database and storage; recordings and ID data in a separate bucket with tighter access.
- **Retention:** recordings and raw transcripts deleted on a fixed schedule (proposal: 90 days for practice, 12 months for certified, to confirm with a lawyer); ID images deleted right after verification; scores kept while the profile is active.
- **Candidate rights:** download all their data, delete their account, withdraw consent for sharing at any time.
- **AI rules:** no emotion or personality inference (banned in recruitment under the EU AI Act); a human reviews every certified score and every integrity flag; every score shows its evidence; bias checks on scores by group once we have enough data.
- **Biometric data:** face checks count as biometric data under GDPR and some US state laws, so they need explicit opt-in consent, minimal storage and a stated purpose.
- **Vendors:** data processing agreements with every AI, speech and hosting vendor; check each vendor's data retention and model-training settings.
- **Regulation timeline:** India's Digital Personal Data Protection Act is the main law at launch (clear consent, purpose limits, breach notice, deletion on request). EU high-risk obligations for hiring AI apply from 2 December 2027 if we serve EU candidates. Design for both now (risk management, logging, human oversight, transparency), not later.
- **Audit log:** every view or change of a score, certified profile or review decision is recorded.

## Work breakdown

Each item is sized to be roughly one pull request. Phases 2 to 4 get their own breakdown once phase 1 passes its gate. The ticks below are as the plan was written; current progress is tracked in [roadmap.md](roadmap.md).

**Phase 0, foundation (about 2 to 3 weeks)**

- [ ] Monorepo scaffold: workspaces, Turborepo, uv, lint, format, type checks, pre-commit
- [ ] CI on GitHub Actions: lint, tests and build for web and API on every pull request
- [ ] Local stack with Docker Compose: Postgres, Redis, LiveKit server
- [ ] FastAPI skeleton: health check, settings, error handling, OpenAPI, generated TypeScript client
- [ ] Database setup with Alembic; first tables: `users`, `consents`, `audit_log`
- [ ] Auth with Clerk on web and API (candidate role first)
- [ ] Next.js skeleton: landing page, waitlist form, sign-in, empty dashboard
- [ ] Staging deploys: web on Cloudflare Pages, API on the small server, managed Postgres, storage bucket
- [ ] Monitoring: Sentry and PostHog in web and API
- [ ] Voice spike: a LiveKit room where the model holds a 5 minute spoken conversation; measure latency and cost per minute
- [ ] Write rubrics and interview templates as YAML for backend (junior to mid) and DevOps/SRE (junior to mid); needs the experts, see prerequisites
- [ ] Privacy policy, terms and consent text, version 1

**Phase 1, practice interviews (about 6 to 8 weeks)**

- [ ] Candidate onboarding: profile, target role and level, CV upload
- [ ] Session API: create session, LiveKit room and token, end session, status
- [ ] Interviewer agent: rubric-driven question plan, follow-ups, section timing, transcript saving
- [ ] Interview screen in the browser: audio, live captions, timer, section progress
- [ ] Coding section (Monaco editor, sandbox runs) and DevOps section (browser terminal, scripted scenarios first), with snapshots shared with the agent
- [ ] Grading job: structured scores with evidence, consistency check, report and learning plan
- [ ] Report page and email: scores, transcript moments, top gaps, learning plan
- [ ] Progress view across sessions
- [ ] Free-session caps and cost tracking per session
- [ ] Eval harness: expert-graded transcripts, score comparison on every prompt or rubric change
- [ ] Paid tier with Razorpay (UPI and cards): more sessions, deeper reports
- [ ] Admin tools: view sessions, re-run grading, handle deletion requests
- [ ] Launch to the waitlist; collect report-usefulness ratings

## What we need before starting

Only the first group blocks the implementation thread. Everything else can be set up while phase 0 runs.

**Before the implementation thread starts:**

- [x] **First roles:** backend engineer and DevOps/SRE engineer, junior to mid (decided 23 October)
- [x] **Market:** India first, English interviews (decided 23 October)
- [x] **Stack:** approved as listed; voice kept, vendors chosen after the phase 0 test (decided 23 October)
- [x] **Budget:** ₹500 to ₹700 a month base, up to ₹5,000 to ₹10,000 with real traffic (decided 23 October)
- [ ] **Model for live interview turns:** decided by the phase 0 comparison across providers on the expert-graded set (no vendor lock-in)
- [ ] **A card that works for international payments**, since most services bill in US dollars

**During phase 0 (accounts and keys, created by you, keys stored as environment secrets, never pasted into chat):**

- [ ] Domain name and DNS access
- [ ] API accounts with billing for the 2 or 3 AI providers we test (for example Anthropic, Google and OpenAI), or one OpenRouter account to start
- [ ] LiveKit Cloud project
- [ ] Speech-to-text and text-to-speech accounts (one each, after the latency test)
- [ ] Cloudflare account with Pages linked to the GitHub repo
- [ ] A small server in Mumbai or Bangalore (AWS Lightsail or DigitalOcean)
- [ ] Managed Postgres (Neon, Supabase or RDS) and a storage bucket (R2 or S3)
- [ ] Clerk account for authentication
- [ ] Email sending account (Resend or Postmark) with the domain verified
- [ ] Sentry and PostHog projects
- [ ] For this cloud environment: network access to these services, and their keys added as environment secrets

**Content and people (the most important non-code input):**

- [ ] Two experienced interviewers, one for backend and one for DevOps/SRE (one person can cover both if qualified), to write and review the rubrics and grade 20 to 30 transcripts each for calibration
- [ ] A question bank for each role: coding tasks with tests, small design prompts, DevOps troubleshooting scenarios with prepared logs, and follow-up patterns
- [ ] 10 to 20 friendly candidates to test practice interviews before launch

**Before phase 2 (secure wrapper and certified profiles):**

- [ ] Apple Developer Program membership, for signing and notarising the macOS app (about $99 a year, from memory)
- [ ] A Windows code-signing certificate (a few hundred dollars a year, from memory)
- [ ] Test machines: at least one Mac and one Windows laptop
- [ ] An identity verification provider (for example Persona, Onfido or Veriff)
- [ ] A lawyer's review of consent, biometric data, retention and the terms, in your main market

**Before phase 3 (company pilots):**

- [ ] 2 or 3 friendly companies willing to skip their technical round for certified candidates, ideally lined up during phase 1
