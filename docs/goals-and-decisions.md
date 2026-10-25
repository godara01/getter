# Goals and decisions

The short version of what Getter is for and what has been decided. The
reasoning is in [product-critique.md](product-critique.md),
[product-plan.md](product-plan.md) and [technical-plan.md](technical-plan.md).
Update this file by pull request whenever a decision changes.

## Goal

Build a service that scores candidates on their real skills, so companies can
hire them directly and skip long interview loops.

The single-interview hire is the destination, not the launch promise. Getter
earns it in stages: first a candidate product people want on its own, then a
certified assessment companies can trust, then proof from hire outcomes that
Getter's bar predicts job success.

## Phase 1 direction

- **Candidates first.** Phase 1 is an AI mock-interview platform with honest,
  detailed feedback on gaps and a learning plan. It builds the candidate base
  before any company signs up.
- **Practice stays private.** Practice sessions are never shown to companies.
  A separate, opt-in certified assessment comes later and is the only thing
  companies see.
- **Company side later.** The first promise to companies will be "skip the
  technical screen", not "skip the whole loop".

## Decisions

| Area | Decision | Decided |
| --- | --- | --- |
| First roles | Backend engineer and DevOps/SRE engineer, junior to mid | 23 Oct 2026 |
| Market | India first, interviews in English, prices in rupees | 23 Oct 2026 |
| Website | Next.js, hosted on Cloudflare Pages (free plan allows commercial use) | 23 Oct 2026 |
| Backend | Python, FastAPI, Postgres | 23 Oct 2026 |
| Payments | Razorpay (UPI, cards, netbanking) | 23 Oct 2026 |
| Voice | LiveKit kept in the plan, to be re-evaluated after a latency and cost test | 23 Oct 2026 |
| Free practice limits | Admission uses recorded model spend: initially ₹100 per account over 24 hours and ₹300 globally per UTC day, alongside the session-count cap. Configurable operational defaults, not paid-tier pricing; running sessions continue | 24 Oct 2026 |
| DevOps practice | A scripted terminal, never a real shell: commands are matched to scenario output, so there is nothing to escape from and no per-session cost. Commands are quotable evidence; terminal output is not | 25 Oct 2026 |
| Paid packs | Razorpay, packs of interviews (credits) rather than a subscription. Credits are used only after the free daily limits. Launch prices (₹499 for 5, ₹1,199 for 15) are placeholders for Sanket to set | 25 Oct 2026 |
| Privacy | Draft privacy policy and terms v2 in plain language, aimed at India's DPDP Act; candidates can download their data; erasure on request; payment records are kept. Needs legal review before launch | 25 Oct 2026 |
| Voice test | Built as a kit: LiveKit admin token plus a scorecard. Proposed limits (median 1.5 s, 95th percentile 3 s, ₹10 a minute) are for Sanket to confirm | 25 Oct 2026 |
| Budget | ₹5,000 to ₹10,000 a month at most; idle cost ₹500 to ₹700 a month; scale up only with real traffic | 23 Oct 2026 |
| AI models | No lock-in to any one provider, Claude included. A provider-agnostic LLM layer; each task (interview turns, grading, checks) uses the best value-for-money model, chosen by evals | 23 Oct 2026 |
| Grading rules | Every score quotes the candidate's own words; the verdict is computed in code; no emotion or personality inference; a failed grading produces no score | 23 Oct 2026 |
| Secure interview app | An Electron wrapper that opens the company's Zoom, Teams or Meet link inside it, runs integrity checks, and reports them to the portal against that meeting link | 23 Oct 2026 |
| Integrity claims | Market the app as "cheat-resistant", never "spoof-free". Integrity flags are evidence for a human reviewer, never an automatic fail | 23 Oct 2026 |

## Still open

- Human interviewers, AI, or a mix for the certified round (recommended: AI
  for practice and early rounds, a human for the final certified round).
- Revenue in phase 1 (recommended: one free interview, then paid interviews
  priced above their cost).
- Full-time hiring only, or contract and trial-to-hire too.
- Whether to sell the secure interview app to companies on its own, and when.
- Which AI model handles each task. Needs API keys and expert-graded
  transcripts; see [roadmap.md](roadmap.md).
- Speech-to-text and text-to-speech vendors, after the voice test.
