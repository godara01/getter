# Getter: critique of the product idea

Written 22 October 2026. Copied from the project doc
[Getter: critique of the product idea](https://claude.ai/artifact/3Cjm4rihN4j1ws7oSPdsAE)
on 23 October 2026. The decisions it led to are in
[goals-and-decisions.md](goals-and-decisions.md).

**Bottom line:** the problem is real and the idea is worth building, but not in the form "companies hire after one interview" on day one. Triplebyte built nearly this product, and companies used it to skip early screens, never their final rounds. Three things could kill it: companies refusing to trust an outside bar (C1), strong candidates not bothering (K2), and AI-assisted cheating making a reusable score untrustworthy (A1). Each has a fix, and the fixes point to one shape: start candidate-first with deep interviews and real feedback in one role family, promise companies only "skip the screen" at first, and prove with hire outcomes that Getter's bar predicts success before asking them to drop the rest of the loop.

## The idea, and what is right about it

**The idea:** candidates go through a few deep interview rounds once, on Getter. Getter builds a skills profile. Companies browse profiles of people actively looking, and replace their own technical loop with a single interview (or only a behavioral and culture-fit round).

The problem is real and well documented. Engineers routinely run 4 to 6 round loops at several companies at once, and most rejections come with no feedback. Companies spend senior engineer hours on interviews, and many loops end with a "no" that a better first filter would have predicted.

Three things in the idea are genuinely right:

- **Interview once, reuse many times** is the only way to cut total effort across the market. Every other fix just moves the work around.
- **Depth over breadth.** A long, probing interview is a better signal than a resume or a 60 minute LeetCode screen.
- **"Actively looking" pool.** Recruiters spend most of their time finding people who want to move. A pool that is pre-filtered for intent is valuable on its own.

The hard part is not whether the problem exists. It is whether companies will actually *skip* their own loop on the strength of someone else's interview. That question decides the whole business, and most of this doc is about it.

## Who tried this, and what happened

Nobody has yet got companies to skip their final round on the strength of a third-party interview. The ones that survived either run the company's *own* interview for a fee, or sell contract work where the company takes less risk.

| Company | What it did | What happened | Lesson for Getter |
| --- | --- | --- | --- |
| [Triplebyte](https://techcrunch.com/?p=2502886) (2015) | Almost exactly this idea: one deep technical interview, then candidates "skip to the final round" at partner companies | Raised just under $50M. In March 2023 Karat bought only the assessment tech; the marketplace was shut down and candidates lost their profiles ([Karat FAQ](https://connect.karat.com/tb-candidates)). In 2020 it faced a backlash for making profiles public by default ([write-up](https://mjtsai.com/blog/2020/05/26/public-triplebyte-profiles)) | Companies used it to skip *screens*, not onsites. Candidate trust is fragile. A placement-fee marketplace dies in a hiring downturn |
| [Hired](https://lhh.com/uk/en/hired) (2012) | Reverse marketplace: vetted candidates, companies send interview requests | Bought by Vettery (Adecco) in 2020; folded into LHH in June 2024 | A curated "actively looking" pool alone is not a moat; it becomes a recruiting agency |
| Karat | Runs the first technical interview *on behalf of* a company, with that company's rubric, paid per interview | Still operating, and was the buyer of Triplebyte's assessment tech | Companies pay to outsource interviews when the bar is *theirs*. They don't accept a generic bar |
| [CodeSignal GCA](https://support.codesignal.com/hc/en-us/articles/1500008654661-How-can-I-share-my-past-assessment-result-with-companies) | A standardized coding score candidates can reuse across companies | Works, but only as an online-assessment filter, and only for companies that opt into that exact test | A portable score can replace the *first* screen. That is a smaller promise than Getter's |
| Toptal (from memory, approximate) | Claims to vet the "top 3%" of freelancers | A large, durable business selling contract work with a markup | Vetting sells well when the buyer risks a contract, not a full-time hire |
| [Turing](https://sacra.com/c/turing/) (2018) | Vetted remote developer marketplace | Pivoted in 2022 to selling expert work to AI labs; about $300M annualized revenue end of 2024 (Sacra estimate) | The vetted pool was worth more as labor than as hiring leads |
| [Mercor](https://www.nbcnewyork.com/news/business/money-report/ai-hiring-startup-mercor-now-valued-at-2-billion-after-strong-recent-growth/6157317/?amp=1) (2023) | AI interviewer plus a talent marketplace | $2B valuation in Feb 2025 with a >$75M run rate; reportedly $10B later in 2025. Most demand comes from AI labs hiring experts | AI interviews at scale are proven. The paying demand was a concentrated buyer, not "companies in general" |
| interviewing.io (from memory) | Anonymous mock interviews; strong performers get fast-tracked to companies | Survives as a practice business with hiring on the side | Candidates pay for practice and feedback, which can fund the supply side |

The common thread: the *signal* has been built many times and works. The *market* for "skip our loop because a third party vouched" has not formed.

## Company side

**C1. Companies won't give up their own technical bar (could kill it).** The interview loop is not only a skill check. It is how a team calibrates against *its* bar, and how the hiring manager defends the hire internally. A bad hire costs months of salary and team time, so skipping the loop has to feel safe to the manager who signs off. Triplebyte's experience shows the realistic outcome: companies drop the phone screen and keep the onsite. If that happens to Getter, candidates save one round, not four, and the core promise breaks.

**C2. Many rejections are not about skills.** A candidate fails a loop because of level (senior vs staff), the team's specific stack, a stronger candidate in the same pool, headcount freezes, compensation, or a manager's taste. A skills profile cannot answer "is this person a senior on *our* scale" or "are they better than the other three finalists". So even a perfect assessment removes only part of the waste.

**C3. A generic score does not map to a specific job.** "Strong in distributed systems" means different things at a 20 person startup and at a bank. Companies will want the profile expressed against their role, not against Getter's taxonomy. This is fixable by scoring against role requirements rather than one global number.

**C4. Disintermediation.** Once a company sees a profile with a name, it can contact the candidate directly and skip your fee. Every marketplace in hiring fights this. It is fixable with contract terms, anonymized profiles until a request is accepted, or a subscription instead of a per-hire fee.

**C5. The pool may look weaker than it is (adverse selection).** Companies will notice who is on the platform. If it is mostly people with time for several long interviews, such as juniors and those between jobs, buyers will discount the whole pool. See K2 on the candidate side.

**C6. Recruiting budgets are cyclical.** Placement fees (typically 15 to 25 percent of first-year salary at agencies) vanish in a hiring freeze. Triplebyte ran out of runway and Hired was folded into a staffing brand in the 2022 to 2024 downturn. Any plan has to survive a year when companies hire very little.

## Candidate side

**K1. Day one, Getter adds interviews instead of removing them.** Until companies actually skip their loops, a candidate who does Getter's "few rounds" still does every company's loop too. The pitch only works once enough companies honour the profile, which is the cold-start problem in another form.

**K2. The best candidates have the least reason to join (could kill it).** Strong engineers get referrals and inbound recruiter messages. Several hours of in-depth interviews for a speculative benefit is a bad trade for them. The people most willing to sit long assessments are those with fewer options. That skews the pool, which is exactly what buyers notice (C5).

**K3. A bad score is scary.** Candidates fear a permanent record that follows them, gets seen by their current employer, or is shown to companies they never chose. Triplebyte's 2020 "public by default" backlash and the loss of every profile when it shut down are the cautionary tales. This is fixable with clear ownership rules (see the table below).

**K4. One bad day decides too much.** Interview performance varies with nerves, sleep and the interviewer. Today a bad day costs one company. On Getter it could cost access to every company at once, unless retakes are allowed and old attempts are hidden.

**K5. Scores go stale.** Skills change within months, especially with AI tooling shifting what engineers do. A profile from a year ago is less useful, so profiles need an expiry and a cheap way to refresh.

**K6. The feedback promise is a real differentiator.** Companies rarely explain rejections, partly for legal reasons. Getter is the assessor, so it *can* give detailed, actionable feedback. That is something candidates will value even before any company uses the profile, and it should be central rather than a side feature.

## Assessment, integrity, legal and money

**A1. Cheating and identity fraud undermine a reusable score (could kill it).** Tools like Interview Coder sell undetectable AI help during live coding interviews, and Google's CEO suggested returning to in-person interviews partly because of this ([report](https://www.eweek.com/news/tech-hiring-interviews-ai-hacks/)). A single company can catch a cheater at the onsite. Getter's score is reused by many companies, so one fraudulent profile damages trust with all of them. Fixes: verified identity, interviews that probe *why* (follow-up questions on the candidate's own past work are hard to fake), allowing AI tools openly and judging how they are used, and treating the company's final interview as a spot-check that feeds back into the score.

**A2. A score is only an opinion until it predicts job performance.** Companies will ask, "Do people you rate highly actually do well?" Answering requires collecting outcome data from hiring companies at 3, 6 and 12 months. Without that loop, Getter cannot prove its bar is better than the company's own, and cannot improve it.

**A3. Deep interviews are expensive, and most candidates are never hired.** A few hours of senior interviewer time per candidate, across a pool where most never get placed, is a cost that a per-hire fee may not cover. AI interviewers (Mercor's model) cut that cost sharply, but they bring candidate distrust and the legal duties in A4. A sensible split is AI for breadth and early rounds, humans for the deep final round.

**A4. Hiring AI is a regulated activity.** The EU AI Act classes recruitment and candidate screening AI as high-risk; the Digital Omnibus moved those obligations from 2 August 2026 to 2 December 2027, but did not remove them ([Ogletree](https://ogletree.com/insights-resources/blog-posts/eu-nears-approval-of-agreement-to-delay-rules-for-ai-use-in-employment-decisions/)). New York City's Local Law 144 already requires bias audits for automated hiring tools, and Illinois regulates AI video interviews (both from memory). Data protection and anti-discrimination law apply everywhere. Design for bias audits, human review of decisions, explanations of scores and explicit consent from the start; retrofitting is much harder.

**A5. "Loads of parameters" across every role is too broad to do well.** Depth costs effort per role. Interviewing backend engineers, data scientists, designers and sales reps well needs four different interview systems and four sets of expert interviewers. Credibility comes from being clearly the best at one role family first.

**A6. Who pays is unresolved.** The options each carry a known risk:

| Model | Who pays | Risk |
| --- | --- | --- |
| Placement fee per hire | Company | Cyclical; invites going around you (C4) |
| Subscription to browse the pool | Company | Hard to sell before the pool is good |
| Per interview, on the company's rubric (Karat model) | Company | Not portable; you become a service business |
| Practice and feedback | Candidate | Lower revenue per user, but funds supply |
| Contract or trial-to-hire with a markup (Toptal model) | Company | Needs payroll and compliance, but lowers the company's risk |

## Killers vs fixable

Three issues could kill the idea as stated; the rest are design work. All three have a plausible fix, but each fix changes the product.

| Issue | Severity | Fix |
| --- | --- | --- |
| C1. Companies keep their own loop | Could kill it | Don't ask them to trust a generic bar on day one. Interview against *their* rubric (Karat-style) for a few anchor companies, guarantee the result (free replacement or refund if the hire fails in 90 days), and earn the right to be portable with outcome data |
| K2. Best candidates won't sit long assessments | Could kill it | Make the assessment worth doing on its own: detailed feedback, a mock-interview-quality experience, shorter rounds, and a guaranteed number of company conversations for those who pass |
| A1. Cheating breaks a reusable score | Could kill it | Verified identity, follow-up probing on the candidate's own work, open-AI-allowed tasks, company final interview as spot-check, and revoking scores when fraud is found |
| Cold start of two sides (K1, C5) | Serious | Start with one narrow segment (one role family, one region or one buyer type) and recruit both sides by hand |
| C6. Cyclical budgets | Serious | Mix revenue: candidate-paid practice plus company fees; avoid relying only on placement fees |
| A4. Regulation | Serious, fixable | Human review of every score, bias audits, explainable scores, consent; build it in from version one |
| A3. Cost of deep interviews | Fixable | AI for early rounds, humans for the final deep round; charge the company per assessment once they trust you |
| C2, C3. Rejections beyond skills, generic score | Fixable | Score against each role's requirements and level, not one number; leave team fit and comparison to the company's single interview |
| C4. Going around you | Fixable | Anonymous profiles until a request is accepted; contract terms; subscription pricing |
| K3, K4, K5. Fear, one bad day, staleness | Fixable | Candidate owns the profile, chooses who sees it, can retake after a cooldown, old attempts hidden, scores expire after 6 to 12 months |
| A2. Unproven validity | Fixable, slow | Collect hire outcomes at 3, 6 and 12 months from day one; publish accuracy once you have it |
| A5. Too many roles | Fixable | Pick one role family first |

## Recommended shape and open decisions

Keep the vision, but earn it in stages. The single-interview hire is the destination, not the launch promise.

1. **Start candidate-first in one role family.** Offer a deep, realistic interview with a detailed feedback report. This is valuable on its own (K6), fixes the day-one problem (K1), and attracts strong candidates who want to know where they stand (K2).
2. **Sign 3 to 5 design-partner companies with a modest promise.** Candidates above the bar skip the company's technical *screen* and go straight to a final round. Where a partner wants it, Getter interviews against that company's rubric. This is the promise companies have already shown they accept.
3. **Measure the one number that matters:** the offer rate of Getter candidates after a single company interview, plus 3, 6 and 12 month performance of those hired. If it is clearly higher than the company's own pipeline, that is the evidence to ask companies to drop more rounds.
4. **Then make the profile portable and charge companies,** with a replacement guarantee to make skipping the loop feel safe to the hiring manager.

Throughout: candidates own their profile and choose who sees it, scores expire, identity is verified, and a human reviews every score.

**Open decisions for Sanket** (as of 22 October; see [goals-and-decisions.md](goals-and-decisions.md) for what was decided since):

- [ ] Which role family and region first? (Recommendation: one you can recruit expert interviewers for yourself, for example backend engineers.)
- [ ] Human interviewers, AI interviewer, or hybrid? (Recommendation: hybrid, AI early rounds and a human final round.)
- [ ] Who pays first: candidates for feedback, companies per assessment, or companies per hire?
- [ ] Launch promise to companies: "skip the technical screen" (achievable now) or "skip the whole technical loop" (the vision)?
- [ ] Full-time hiring only, or also contract and trial-to-hire, which companies accept more readily?

## Sources

Pages consulted on 22 October 2026: [TechCrunch on Karat buying Triplebyte](https://techcrunch.com/?p=2502886), [Karat FAQ for Triplebyte candidates](https://connect.karat.com/tb-candidates), [Triplebyte public profiles, 2020](https://mjtsai.com/blog/2020/05/26/public-triplebyte-profiles), [LHH on Hired](https://lhh.com/uk/en/hired), [CodeSignal score sharing](https://support.codesignal.com/hc/en-us/articles/1500008654661-How-can-I-share-my-past-assessment-result-with-companies), [Sacra on Turing](https://sacra.com/c/turing/), [CNBC via NBC on Mercor](https://www.nbcnewyork.com/news/business/money-report/ai-hiring-startup-mercor-now-valued-at-2-billion-after-strong-recent-growth/6157317/?amp=1), [eWeek on AI interview cheating](https://www.eweek.com/news/tech-hiring-interviews-ai-hacks/), [Ogletree on the EU AI Act delay](https://ogletree.com/insights-resources/blog-posts/eu-nears-approval-of-agreement-to-delay-rules-for-ai-use-in-employment-decisions/). Items marked "from memory" were not checked against a source.
