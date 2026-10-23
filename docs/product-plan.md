# Getter: product plan

Written 23 October 2026. Copied from the project doc
[Getter: product plan](https://claude.ai/artifact/17PjzxH6wzBWE9FCVnp2XE) on
23 October 2026. The build details are in [technical-plan.md](technical-plan.md)
and current status is in [roadmap.md](roadmap.md).

Getter starts as a free AI interview and feedback platform for candidates in one role family, adds a cheat-resistant certified assessment, and only then brings in companies with the promise of skipping the technical screen.

## Problem, vision and what we learned

**Problem.** Candidates sit through 4 to 6 interview rounds at many companies and are usually rejected without feedback. Companies spend senior engineers' time on loops that often end in a "no" a better first filter would have predicted.

**Vision.** Candidates are interviewed in depth once, on Getter. Companies use the resulting profile to replace their own technical rounds, and hire after a single behavioral or culture-fit interview.

**What the market research showed** (full detail in [product-critique.md](product-critique.md)):

- Triplebyte built nearly this product. Companies used it to skip early screens, never final rounds, and it was sold off in 2023.
- The businesses that survived either run interviews on the company's own rubric (Karat) or sell vetted contract work (Toptal, Turing, Mercor).
- Three risks could kill the idea: companies not trusting an outside bar, strong candidates not bothering, and AI-assisted cheating making a reusable score worthless.
- The honest outlook: a profitable small-to-mid business is achievable. A very large one depends on proving, with hire outcomes, that Getter's bar predicts job success.
- The real "why now": companies in 2026 are flooded with AI-written applications and AI-assisted interviews, so a trusted, verified signal is worth more than ever.

## Decisions

**Decided:**

| Decision | What we chose | Why |
| --- | --- | --- |
| Starting side | Candidates first; companies later | Solves the cold start; candidates get value before any company signs up |
| Phase 1 product | Free AI-driven practice interviews with honest, detailed feedback on gaps, plus learning recommendations | Feedback is what candidates lack today and will come back for |
| First promise to companies | Skip the technical interview round, not the whole loop | The promise companies have shown they accept |
| Practice vs evaluation | Practice stays private forever; a separate opt-in certified assessment is the only thing companies see | People won't practice honestly if a bad session can follow them |
| Integrity as a selling point | A cheat-resistant desktop interview app for certified assessments | Cheating is the biggest threat to a reusable score, and a real pain for companies in 2026 |
| Scope of the build | Website, backend, database, AI services and a desktop app, delivered in small phases | Ship and learn in order, not all at once |

**Still open** (recommendations in brackets):

- [x] First roles: backend engineer and DevOps/SRE engineer, junior to mid (decided 23 October)
- [x] Market: India first, interviews in English (decided 23 October)
- [x] Budget: ₹500 to ₹700 a month base, up to ₹5,000 to ₹10,000 with real traffic (decided 23 October); cost per interview in [technical-plan.md](technical-plan.md#budget-fit)
- [ ] Human interviewers, AI, or a mix (AI for practice and early rounds, a human for the final certified round)
- [ ] Revenue in phase 1 (one free interview, then paid interviews priced above their cost; course links only as a minor extra)
- [ ] Full-time hiring only, or contract and trial-to-hire too
- [ ] Whether to sell the secure interview app to companies on its own, and when

## Phase 1 product: practice interviews and feedback

A candidate signs up, picks a target role and level, and takes a voice interview with an AI interviewer in the browser. They get a detailed report within minutes. No desktop app is needed for practice.

**What one session includes:**

1. Short setup: target role, level, years of experience, and optionally a CV.
2. A 30 to 45 minute voice interview: a coding or problem-solving task, a design discussion sized to the level, and deep follow-up questions on the candidate's own past work.
3. A feedback report: a score per skill against the target level, specific moments from the transcript showing what was strong or missing, and the 3 most important gaps.
4. A learning plan for those gaps, with practice tasks and suggested material.
5. A progress view across sessions, so improvement is visible.

**What makes it different from existing mock-interview tools:** feedback calibrated to a real hiring bar for one role, not generic tips; depth of follow-up questions; and an honest verdict ("you would likely not pass a senior loop yet, because...").

**Rules from day one:** practice data is private; consent to be shown to companies is asked for separately and only applies to certified assessments; the AI never infers emotions or personality (this is banned in recruitment under the EU AI Act); free sessions are capped, because each voice session has a real AI cost.

**What we measure:** completed sessions, repeat sessions per candidate, how useful candidates rate the report, and how many strong candidates (above a senior bar) are in the pool. Total signups matter less than that last number.

## Secure interview app

**Verdict:** worth building for Getter's certified assessments, but it cannot be truly "spoof-free", the market already has many players, and there is no complete open-source app to fork. Build our own from open-source parts, and market it as "cheat-resistant, with evidence".

**What already exists.** The anti-cheating interview market appeared quickly after tools like Cluely and Interview Coder.

| Product | What it does | Notes |
| --- | --- | --- |
| [Truely by Validia](https://www.producthunt.com/p/truthful-by-validia/truely-by-validia) | Desktop app the candidate runs during a call; alarms if it detects Cluely-style assistants | Free, which sets a low price anchor ([TechCrunch](https://techcrunch.com/2025/07/09/why-cluelys-roy-lee-isnt-sweating-cheating-detectors/)) |
| [Talview](https://www.talview.com/blog/how-talview-blocks-cluely-cheating-app-in-online-exams-interviews) | Proctoring for exams and interviews; detects overlays, checks identity and environment | Established paid vendor |
| [BrightHire](https://brighthire.com/blog/detect-ai-cheating-interviews/) | Fraud signals shown inside Zoom during the interview | Works with tools companies already use |
| [Polygraf](https://www.polygraf.ai/interview-cheating-ai-detector/), [Sherlock](https://www.sherlock.sh/blog/interview-cheating-detection-tools), [Fabric](https://fabrichq.ai/blogs/ai-interview-cheating-detection), [InterviewGuard](https://www.interviewguard.io/solutions/ai-cheating-detection), Proctaroo | Detect AI help from transcripts, behaviour, gaze and response timing | Young products; none publishes independent accuracy or false-positive rates |
| HackerRank, CodeSignal, Proctorio, Honorlock (from memory) | Proctoring built into assessments and exams | Mature, but aimed at tests rather than live conversations |

**Open-source options.** [Safe Exam Browser](https://discover.trinitydc.edu/moodle/safeexam/) is a free, open-source lockdown browser for Windows and macOS, but it is built for exams, not video calls. An [Open edX proctoring toolset](https://openedx.atlassian.net/wiki/x/AQASPgE) is only a proposal. Nothing combines video calls, lockdown and detection, so forking isn't an option. Instead we assemble proven open-source parts: LiveKit (video calls), MediaPipe (face and gaze tracking), and Tauri or Electron (desktop shell), all from memory and to be confirmed.

**What the app can detect** on the candidate's own laptop: other running processes and hidden overlay windows, extra monitors and virtual machines, screen recording or mirroring, other voices in the room, the face leaving the frame or a second face, unusual gaze patterns, and identity mismatch against an ID check.

**What no app can prevent:** a second laptop or phone out of view, a helper off camera, an earpiece, or a video capture device feeding a second machine. Cheating tools are already moving to separate devices and browser tabs for this reason. So the app has to be paired with interview design: deep follow-up questions on the candidate's own work, which are hard to answer from a feed, and human review of anything flagged.

**Legal limits.** The EU AI Act bans AI that infers emotions in recruitment ([Bird & Bird](https://cm.twobirds.com/en/insights/2025/global/ai-and-the-workplace-navigating-prohibited-ai-practices-in-the-eu)). Gaze and face tracking are allowed for integrity checks, but never to judge stress, honesty or personality. Face data is biometric data under GDPR and some US state laws, so it needs explicit consent, short retention, and a human to decide on every flag.

**Would it sell on its own?** Yes, plausibly, and it may be easier to sell than the candidate marketplace: companies pay, the pain is acute right now, and there is no two-sided cold start. But three things work against it:

- **Switching cost.** Companies already interview in Zoom, Teams or Meet, and won't move every interview to a new video tool. A standalone product should sit alongside those tools (a companion app plus a meeting bot), not replace them.
- **Candidate resistance.** Strong candidates may refuse to install monitoring software for a company they are only exploring. This is acceptable for Getter's own certified assessment, which is opt-in and reusable, but harder for every company interview.
- **An arms race with free competitors.** Detection gets bypassed, and Truely is free. The defensible value is the combination: integrity checks plus a calibrated assessment plus human review.

**Recommendation:** build it in phase 2 for Getter's certified assessments, measure its false-positive rate, then offer it to companies as a companion to their existing video tools in phase 4.

**Chosen design (23 Oct): a secure browser wrapper.** The app is a locked-down browser that opens the company's own Zoom, Teams or Meet link inside it, unchanged, and runs the integrity checks the whole time. Each session is tied to its meeting link and reported live to the Getter portal, where the interviewer sees whether the candidate is verified. Build notes:

- Use Electron rather than Tauri. It ships its own Chromium, so Meet, Teams and the Zoom web client behave the same on every machine. Our face checks can also share the camera with the meeting inside one process.
- Flow: the company creates the interview in the portal and pastes the meeting link. The candidate opens a Getter invite, which launches the app, runs an ID and environment check, then opens the meeting.
- Prove that the person in the meeting is the person using the app. Otherwise a candidate can leave the app running as a decoy and join from a second device. Use a rotating code shown in both the app and the portal, plus periodic face matching.
- Test early: Google blocks account sign-in inside embedded browsers, so candidates may need to join Meet as guests. The Zoom web client and anonymous Teams join depend on the host's settings. Don't inject scripts into or modify the meeting pages, to stay within their terms.

## System architecture

The project doc has a diagram of the seven components; it is summarised here.

The website and the desktop app both talk to one backend, which runs the AI interviewer, scoring and the human review queue. Voice and video go through a realtime media server for practice and certified sessions alike. The desktop app adds integrity checks and is only needed for certified assessments. The proposed stack (Next.js, FastAPI, Postgres, LiveKit, Electron, MediaPipe) is a starting recommendation to confirm in phase 0, as is the choice of LLM, speech-to-text and text-to-speech providers.

## Phased roadmap

Each phase ships something usable and has a gate to pass before the next phase starts. Durations are rough guesses for a small team.

1. **Phase 0, foundation (about 2 to 3 weeks).** Repository layout, accounts and login, database schema, landing page with a waitlist, and choosing the AI providers. Settle the first role family and write the consent and data-retention policy.
   - Gate: a candidate can sign up and the stack deploys automatically.
2. **Phase 1, practice interviews (about 6 to 8 weeks).** Browser-based AI voice interview for one role, feedback report, learning plan, progress view, and a cap on free sessions. Start conversations with 2 or 3 companies during this phase.
   - Gate: candidates come back for repeat sessions and rate the reports as useful, and the pool includes a meaningful number of strong candidates.
3. **Phase 2, certified assessment and secure app (about 8 to 10 weeks).** Identity verification, the desktop interview app (process and overlay checks, monitor and VM checks, face and gaze checks, recording), a human review queue for flags, and an opt-in certified profile that expires after 6 to 12 months.
   - Gate: the false-positive rate is measured and low enough that reviewers rarely overturn flags.
4. **Phase 3, company pilots.** Company dashboard to view certified, anonymised profiles and request introductions; 2 or 3 partner companies skip their technical round for certified candidates.
   - Gate: certified candidates get offers after a single company interview clearly more often than the company's own pipeline does.
5. **Phase 4, revenue on both sides.** Paid company plans with a replacement guarantee, paid candidate tiers, more role families, and the secure app offered to companies as a companion to Zoom, Teams or Meet.

## Risks to watch

- **Crowded practice market.** Free AI mock interviews are common; only calibrated, honest, role-specific feedback stands out.
- **Weak pool.** Practice tools attract many juniors. Track strong candidates, not signups.
- **Company side stalls.** Start company conversations in phase 1, not after reaching scale.
- **AI cost.** Voice sessions cost money per minute; cap free use and watch cost per session.
- **Overclaiming integrity.** Never market "spoof-free"; one public bypass would damage trust.
- **Regulation.** No emotion inference; consent and human review for biometric checks; EU high-risk hiring duties apply from 2 December 2027.

## Sources

Market findings and history: [product-critique.md](product-critique.md). Anti-cheating market: [TechCrunch on Cluely and its detectors](https://techcrunch.com/2025/07/09/why-cluelys-roy-lee-isnt-sweating-cheating-detectors/), [Truely](https://www.producthunt.com/p/truthful-by-validia/truely-by-validia), [Talview](https://www.talview.com/blog/how-talview-blocks-cluely-cheating-app-in-online-exams-interviews), [BrightHire](https://brighthire.com/blog/detect-ai-cheating-interviews/), [Fabric](https://fabrichq.ai/blogs/ai-interview-cheating-detection). Open source: [Safe Exam Browser](https://discover.trinitydc.edu/moodle/safeexam/), [Open edX proctoring proposal](https://openedx.atlassian.net/wiki/x/AQASPgE). Law: [Bird & Bird on prohibited workplace AI](https://cm.twobirds.com/en/insights/2025/global/ai-and-the-workplace-navigating-prohibited-ai-practices-in-the-eu). Items marked "from memory" are unverified.
