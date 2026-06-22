# What HR Requires from an Applicant — Video, Words & Audio

*Internal reference for the AI-Recruiter product and HR users. Compiled June 2026 from 2023–2025 sources.*

> **Verification caveat:** compiled from web-search result summaries and reputable secondary
> analyses (regulators, law firms, practitioner guides), **not** full reads of every primary
> text. Legal provisions were checked against primary sources (EEOC, ADA.gov, gdpr-info.eu,
> NYC Rules) where possible. Practitioner guidelines (WPM "sweet spot", 80/20 talk-time, the
> "1 in 3 hiring managers" survey figure) are **rules of thumb, not validated cutoffs** — flagged
> inline. Legal items are jurisdiction-dependent. Verify primaries before any compliance decision.

---

## How this maps to AI-Recruiter

The product evaluates the three modalities with **deliberately different weight** — exactly the
order the research recommends (content first, audio advisory, video most cautious):

| Modality | In the product | Weight | Principle |
|---|---|---|---|
| **WORDS** (answer content) | Transcript, goal/competency assessment, communication analysis (talking style, structure, fillers) | **Primary** | Where job-relevant competence is demonstrated |
| **AUDIO** (vocal delivery) | Speaking balance & pace (talk-time, WPM, fillers from Deepgram) | **Advisory** | Communication-clarity feedback, validated per population |
| **VIDEO** (on camera) | Presence/engagement, integrity flags, gesture/expression notes — **advisory, never scored**; evidence-linked + data-quality gated | **Most cautious** | Engagement/integrity only; no appearance/affect/accent scoring |

Guardrails already built in: **no accent classification**, **no emotion/affect scoring** (EU AI Act
Art. 5), **no auto-decisions on video/audio**, a **data-quality gate** that suppresses the
subjective video summary when footage is insufficient, and **evidence links** so a reviewer
watches the actual moment before any cue influences a decision. **A human decides.**

---

## 1. VIDEO — what the candidate shows on camera (visual / non-verbal)

The **most cautious** modality. Non-verbal cues are weakly predictive of performance, heavily
culture-bound, and a documented bias vector — ~**1 in 3 hiring managers** report body-language-based
rejections (a survey figure, not validated), and nonverbal/first-impression/halo/similarity biases
cluster here [8][7]. Non-verbal expression and its interpretation **differ across cultures**,
creating bias when assessor and candidate cultures diverge [6].

### ✅ Green flags (legitimate — engagement & professionalism, not personality)
- Punctual join; tested setup; minimal avoidable technical disruption.
- Adequate, neutral setup: face reasonably lit/framed, audible, no major distractions.
- Attentiveness — listening, answering the question asked, not visibly reading off-screen scripts
  (a legitimate integrity/proctoring signal).
- Composure under a hard question (re-orients and answers rather than disengaging).

### 🚩 Red flags (note cautiously — confirm with content, never decide alone)
- Repeated lateness/no-shows without notice (reliability — behavioral, defensible).
- Apparent reliance on undisclosed off-screen help when the format prohibits it (integrity — as an
  *observation* with a chance to explain, not a verdict).
- Setup so poor that communication actually fails — and even then, see "evaluate fairly".

### Defensible vs. risky
| Defensible to consider | Risky / biased — do **not** score |
|---|---|
| Punctuality, role-appropriate professionalism | Physical appearance, attractiveness, attire beyond role norms |
| Whether the candidate is engaged with *this* conversation | Gaze/eye-contact as a proxy for confidence or honesty |
| Integrity/proctoring (undisclosed help, when prohibited) | Facial **affect/emotion** as a trait/competency signal |
| | Posture/gestures as personality (extraversion, etc.) inferences |

> Research that smiling/head-movement can statistically *estimate* traits [5] is **descriptive, not
> a hiring endorsement** — scoring such cues raises the disability and emotion-recognition risks below.

### Evaluate fairly
- **Decouple setup from substance** — cheap webcams, poor lighting, and noisy homes track
  socioeconomic status, not ability.
- **Eye contact, flat affect, limited gesturing, atypical expression are core features of autism
  and other neurodivergence.** EEOC autism-related ADA charges rose sharply (**488 in FY2023 vs. 53
  a decade earlier**); tools/judgments weighing eye contact and demeanor are flagged ADA risks
  [14][15]. Offer accommodations (e.g., camera-off) and never penalize demeanor.
- **Legitimate** automated use = confirming a real, engaged person / proctoring prohibited help.
  **Illegitimate** = inferring emotion/affect from face or scoring appearance (EU-prohibited, §4).
- Use standardized questions + structured rubrics + multiple raters; flag cross-culture assessment [6][7].

---

## 2. WORDS — the verbal content of answers (the transcript)

The **primary** modality and most defensible — where job-relevant competencies are actually
demonstrated. The dominant frame is the **STAR method** (Situation, Task, Action, Result) [1][3].

### ✅ Green flags (strong candidate)
- **Complete STAR**: sets context, names their specific task, details the *actions they personally
  took*, closes with a **measurable result** [2].
- **Concrete, verifiable specifics** over generalities — checkable detail grounds claims [1].
- **Relevance** — directly answers the question asked.
- **Ownership** — distinguishes "I did" from "the team did" while crediting others.
- **Role/technical depth** for the level; **structured reasoning** when problem-solving.
- **Self-awareness & honesty** — consistent details; acknowledges trade-offs/failures and learning.
- **Motivation & values alignment** with specifics about *this* role/company.

### 🚩 Red flags (concerning)
- **Vague/generic** answers about past experience — a primary documented red flag [1][4].
- No specifics / no measurable results; rehearsed, boilerplate answers.
- Rambling, evasiveness, dodged questions, off-topic.
- Contradictions across the conversation, or a "tone that feels slightly off" — real red flags "are
  rarely dramatic"; follow up, don't snap-judge [4].
- Persistent negativity about past employers; unexplained pattern of very short tenures.

### Evaluate fairly
- **Probe, don't assume** — a weak red flag (a dodge, a contradiction) is a cue for a clarifying
  follow-up before scoring.
- **"We" vs. "I" is cultural** as well as substantive — collectivist backgrounds may default to team
  framing; ask "what was *your* part?" rather than penalizing pronouns.
- **Don't conflate polish with competence** — vague-but-smooth should score *lower* than
  rough-but-specific.
- **Score content against role-specific behavioral anchors (BARS)**, not a global impression (§4).

---

## 3. AUDIO — how the candidate sounds (vocal delivery / paralinguistics)

**Advisory only**: useful as communication-clarity *feedback*, dangerous as a selection score.

### Defensibly assessable (communication-clarity signals, ideally advisory)
- **Speaking rate (WPM)** — conversational English ≈ **130 WPM**; an interview "sweet spot" of
  **120–160 WPM** is *cited* for perceived credibility [9][10]. *Rough guideline, not a validated cutoff.*
- **Fluency** — articulation, pacing, purposeful pauses.
- **Filler-word frequency** ("um," "like," "just") as a clarity signal [9].
- **Clarity / intelligibility** — can the listener follow the answer.
- **Talk-time balance** — candidate should carry most of it; the **80/20 rule** (candidate ~80%) is a
  widely-cited *heuristic*, real ratios vary [11].
- **Response latency** — note generously (see below).

### ✅ Green flags
- Pace within a comfortable, intelligible range; clear articulation; purposeful pauses.
- Candidate carries the majority of talk-time with substantive content.
- Generally low filler density; recovers smoothly from stumbles.

### 🚩 Red flags (clarity issues only — never trait judgments)
- Pace so fast/slow the listener can't follow; chronically unintelligible delivery that would impede
  the actual job.
- Talk-time so low the candidate volunteers little (probe rather than penalize).

### ❌ NOT defensible — and why
- **Accent / national origin** — do not score. Accent-based decisions are **national-origin
  discrimination under Title VII**; an accent may be considered only where it *materially interferes*
  with job performance [12][13].
- **Emotion / affect from voice** — low validity; **EU-prohibited in the workplace** (§4).
- **"Enthusiasm/personality/confidence" from voice** — confounds with disability and anxiety
  (stutters, ADHD/autism speech patterns, situational nerves); flagged as an **ADA risk** [14].

### Evaluate fairly
- Use audio as **advisory communication-clarity feedback**, separate from the competency score, and
  only for roles where verbal communication is a genuine documented requirement.
- **Validate per population** before any threshold — WPM, filler rate, and latency vary by language
  background, age, and disability; a single cutoff produces adverse impact.
- **Latency/pauses** can reflect thoughtful processing, second-language effort, or disability — not
  disengagement.

---

## 4. Cross-cutting: weighting, rubrics & legal guardrails

**Weighting:** WORDS/content = **primary** (drives the decision); AUDIO = **advisory** (role-justified,
population-validated); VIDEO = **most cautious** (engagement/integrity only — no appearance, gaze,
affect, or emotion scoring).

**Structured rubrics (BARS):** structured interviews with Behaviorally Anchored Rating Scales score
candidates against predefined behavioral indicators and are associated with **higher reliability,
stronger validity, and lower bias** than global impressions [25][26]. Pair with standardized
questions, multiple raters, and clear criteria to suppress first-impression/halo/similarity/nonverbal
bias [7].

**Legal guardrails (jurisdiction-dependent — verify primaries):**
- **NYC Local Law 144** — AEDTs require an **annual independent bias audit**, **public posting**, and
  **advance candidate notice**; DCWP-enforced (effective Jan 1 2023; enforcement Jul 5 2023; penalties
  ~$500–$1,500/violation) [21][22].
- **EU AI Act Art. 5(1)(f)** — **prohibits AI inferring emotions in the workplace** (medical/safety
  exceptions); applicable since **Feb 2025**; fines up to **7% of global turnover**. HR video tools
  inferring candidate emotion are cited as prohibited [19][20].
- **EEOC — Title VII** — accent/national origin can't drive decisions unless an accent *materially*
  interferes with the job [12][13].
- **EEOC/DOJ — ADA (2022)** — liability where AI **screens out** disabled candidates or denies
  **reasonable accommodation**; tools weighing eye contact/demeanor/voice traits are specific risks
  [16][17][18].
- **GDPR Art. 22** — right not to be subject to decisions based **solely** on automated processing
  with significant effects; a rubber-stamp review doesn't count — meaningful human review, notice, and
  the right to contest are required [23][24].

**Practical guardrail:** content-led decision · BARS rubric · standardized questions · multiple human
raters · audio advisory-only & population-validated · video limited to engagement/integrity ·
documented accommodations · genuine human-in-the-loop with notice and contestability.

---

## Sources
1. STAR method for recruiters — Testlify. https://testlify.com/star-interview-method/
2. STAR Method for Recruiters — Agendrix. https://www.agendrix.com/blog/star-method
3. 30 STAR method interview questions — BetterUp. https://www.betterup.com/blog/star-interview-method
4. Interview Red Flags — Performance Reviews Software. https://www.performancereviewssoftware.com/interview-red-flags/
5. Personality Traits Estimation from Job Interview Video — MDPI (2024). https://www.mdpi.com/2504-2289/8/12/173
6. Candidate & assessor culture on nonverbal expression — Cannata et al. (Sage, 2024). https://journals.sagepub.com/doi/10.1177/14705958241244689
7. What is Interview Bias and How to Avoid It — Thomas.co. https://www.thomas.co/resources/type/hr-blog/what-interview-bias-and-how-avoid-it
8. 1 in 3 hiring managers reject candidates on body language — Career.io. https://career.io/career-advice/body-language-interviews
9. Average Speaking Rate and Words per Minute — VirtualSpeech. https://virtualspeech.com/blog/average-speaking-rate-words-per-minute
10. Speech Rate Calculator (interview range) — InstantInterview. https://instantinterview.app/tools/speech-rate-calculator
11. The 80/20 Rule applied to interviews — HighMatch. https://www.highmatch.com/blog/what-is-the-80-20-rule-and-how-it-applies-to-interviews/
12. National Origin Discrimination — U.S. EEOC. https://www.eeoc.gov/national-origin-discrimination
13. EEOC Enforcement Guidance on National Origin Discrimination. https://www.eeoc.gov/laws/guidance/eeoc-enforcement-guidance-national-origin-discrimination
14. AI Hiring Tools Elevate Bias Danger for Autistic Applicants — Bloomberg Law. https://news.bloomberglaw.com/daily-labor-report/ai-hiring-tools-elevate-bias-danger-for-autistic-job-applicants
15. Neurodivergence ADA charges rising (EEOC data) — Ogletree. https://ogletree.com/insights-resources/blog-posts/disability-discrimination-charges-involving-neurodivergence-are-rising-according-to-eeoc-data/
16. Artificial Intelligence and the ADA — U.S. EEOC. https://www.eeoc.gov/eeoc-disability-related-resources/artificial-intelligence-and-ada
17. Algorithms, AI, and Disability Discrimination in Hiring — ADA.gov. https://www.ada.gov/assets/pdfs/ai-guidance.pdf
18. EEOC Issues Guidance on AI and the ADA — Littler. https://www.littler.com/news-analysis/asap/eeoc-issues-guidance-artificial-intelligence-and-americans-disabilities-act
19. Red Lines under EU AI Act: emotion recognition in the workplace — FPF. https://fpf.org/blog/red-lines-under-eu-ai-act-unpacking-the-prohibition-of-emotion-recognition-in-the-workplace-and-education-institutions/
20. Prohibition of AI Emotion Recognition in the Workplace — Wolters Kluwer. https://legalblogs.wolterskluwer.com/global-workplace-law-and-policy/the-prohibition-of-ai-emotion-recognition-technologies-in-the-workplace-under-the-ai-act/
21. NYC Local Law 144-21 and Algorithmic Bias — Deloitte. https://www.deloitte.com/us/en/services/audit-assurance/articles/nyc-local-law-144-algorithmic-bias.html
22. Automated Employment Decision Tools — NYC Rules. https://rules.cityofnewyork.us/rule/automated-employment-decision-tools-2/
23. Art. 22 GDPR — Automated individual decision-making. https://gdpr-info.eu/art-22-gdpr/
24. AI in Recruitment in the EU and UK (GDPR Art. 22) — Ropes & Gray. https://www.ropesgray.com/en/insights/viewpoints/102mpug/helping-hand-or-complete-control-ai-in-recruitment-in-the-eu-and-uk
25. BARS: A Practical Guide — HackerEarth. https://www.hackerearth.com/blog/behaviorally-anchored-rating-scales-bars
26. Developing BARS for Structured Interviews — ETS RR-17-28 (Wiley). https://onlinelibrary.wiley.com/doi/full/10.1002/ets2.12152

**Verification notes:** Legal provisions confirmed against primary sources (EEOC, ADA.gov,
gdpr-info.eu, NYC Rules) or established legal-analysis secondaries. The **WPM 120–160 sweet spot,
80/20 talk-time rule, and "1 in 3 hiring managers" figure are practitioner/survey claims, not
peer-reviewed validated thresholds** — do not code them as hard scoring cutoffs. Full primary texts
could not be fetched directly; finer EU AI Act scope nuances rest on the FPF / Wolters Kluwer analyses.
