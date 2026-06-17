# HR Evaluation Guide — What to Require from Applicants & How AI-Recruiter Supports It

*Internal reference for the AI-Recruiter product and HR users.*
*Compiled June 2026 from 2022–2025 sources.*

> **Verification caveat:** the legal/research content below was compiled from web-search
> result extractions and reputable secondary analyses (law firms, regulator summaries,
> peer-reviewed abstracts), **not** full reads of every primary text (full-page fetching
> was unavailable when this was compiled). Load-bearing legal specifics — exact statutory
> wording and current guidance status — must be confirmed against primary sources before
> any compliance decision. Legal items are jurisdiction-dependent and several were in flux
> as of 2025; these are flagged inline.

---

## Part A — How AI-Recruiter implements this guidance

This product is **decision-support, not a decision-maker.** It surfaces structured,
job-relevant signals for a human recruiter; it does not auto-reject or auto-rank on
audio/video. The design choices below follow the evidence in Part B.

### What we measure and surface
| Capability | Where | Treated as | Notes |
|---|---|---|---|
| 3-tier résumé score (rules / semantic / LLM) | Candidate score | Primary, job-related | Has a manual override |
| Goal-based interview assessment + transcript | Interview panel | Primary | Competency goals scored from answer evidence |
| **Speaking balance & pace** (talk-time, words/answer, approx wpm) | Interview panel | Objective communication signal | Word-share + duration; labelled as approximate |
| **Communication analysis** (talking style, fluency, clarity, fillers) | Interview panel | Advisory communication-clarity | LLM over transcript; filler counts from Deepgram |
| **Video evaluation** (presence, integrity flags, delivery summary) | Interview panel | **Advisory only — never scored** | Vision is deliberately kept out of the numeric score |
| **Evidence-linked observations** | Vision report | Verification aid | Each note jumps to its moment in the video |
| **Data-quality gating** | Vision report | Guardrail | Suppresses the subjective summary when footage is insufficient |
| Proctoring (people count, phone visible) | Vision report | Objective integrity flag | Local YOLO over the recording |

### What we deliberately do **not** do (and why)
- **No accent classification.** Accent is a near-direct proxy for national origin (Title VII
  risk). The "accent" field is an explicit text-only caveat, not a classifier.
- **No emotion/affect scoring.** Emotion recognition lacks scientific support and is
  **prohibited in workplace contexts under the EU AI Act (Art. 5, from 2 Feb 2025)**.
  "Engagement"/"delivery" cues are shown as advisory prompts, never folded into a score.
- **No auto-decisions on video/audio.** A human reviews; subjective cues stay advisory.
- **Data-quality gate** prevents a confident-sounding summary built on a few off-camera frames.

### How HR should read each tier
- **Objective / actionable:** proctoring flags, talk-time balance, filler counts. Use directly.
- **Advisory communication:** pace, fluency, clarity. Compare to the role's real demands.
- **Subjective inference:** engagement/expression/gestures. Lowest weight; always cross-check
  against *what the candidate said*. Use the evidence-link to watch the actual moment before
  letting any cue influence a decision.

> **Golden rule:** the AI points you to moments and patterns; *you* make the judgement, and
> you keep a record of the job-related reason.

---

## Part B — Researched reference: what HR requires from applicants

### 1. Core competencies HR assesses
The most defensible way to assess any competency is the **structured behavioral interview** —
same questions for all candidates, scored against fixed, job-relevant criteria (§3) [1][8].

- **Communication skills** — consistently the top soft skill sought (SHRM lists it as a core
  behavioral competency) [4][2]. *Signals:* clear, concise articulation; logically structured
  answers; audience-appropriate vocabulary; active listening (paraphrasing, clarifying, not
  interrupting) [11].
- **Role / technical competence** — best via work samples, simulations, behavioral evidence;
  cognitive ability + structured interview is a high-validity composite [10][8]. *Signals:*
  correct domain terminology, demonstrated outcomes, depth when probed, explaining *how/why*.
- **Problem-solving / critical thinking** — top-prioritized for 2024; behavioral/situational
  probes [4][1]. *Signals:* defining the problem before solving, trade-offs, measurable results.
- **Culture / values fit — treat with caution.** "Culture fit" as social similarity erodes
  diversity; reframe as **values alignment / "culture add"** with behavioral rubrics [3][12][13].
  *Avoid:* affinity from shared background or "feels like one of us."
- **Motivation / engagement** — researched knowledge of role/company, coherent reasons, genuine
  questions. *Uncertain & subjective* — easily confounded with polish/extraversion; assess via
  concrete examples, not "energy."
- **Professionalism** — punctuality, preparation, courtesy, following instructions [10].
- **Reliability / conscientiousness** — follow-through history, ownership; best confirmed via
  references. (Note: general cognitive ability is the strongest *single* predictor in I/O
  consensus [9]; conscientiousness is *a* strong dispositional predictor, not "the" predictor.)

### 2. What HR looks for in a video / recorded interview
- **Answer structure — the STAR method** is the dominant frame [5]: **S**ituation (brief),
  **T**ask (their responsibility), **A**ction (the bulk — what *they* did), **R**esult
  (measurable). Keep full answers under ~2 min [6][7].
  *(Do not cite a "STAR scores 25% higher" figure — not traceable to a primary source.)*
- **Active listening** — answering what was asked, restating/clarifying, not talking over [11].
- **Professionalism & setup** — lighting, clean background, attire, punctuality, framing, audio
  quality, as proxies for preparation [14][15].
- **Non-verbal cues — legitimate vs. risky.** A 70-year meta-analysis finds appearance, eye
  contact, and head movement correlate with ratings [16][17] — *but these are also the biggest
  bias vectors.*
  - *More defensible (still scored against fixed criteria):* coherent expression, responsiveness,
    composure, professional setup.
  - *Risky / discount or exclude:* stigmatized appearance (the one nonverbal cue *negatively*
    tied to hiring) [16]; accent/voice (national-origin risk) [17]; race/ethnicity & tech
    artifacts (documented async-video bias) [18]; cultural differences in expression [19];
    disability-linked cues — limited eye contact, fidgeting, no "ready smile" — which AI tools
    can amplify (ADA accommodation may be required; cf. a deaf candidate's complaint over denied
    captioning) [20][21][22].
- **Product takeaway:** anchor evaluation in *content* (STAR-structured answers, job-relevant
  competencies) with fixed rubrics; treat nonverbal/setup cues conservatively; provide
  accommodations.

### 3. Structured interviewing & scoring rubrics
- **Structure beats gut feel.** Schmidt & Hunter (1998): ~0.51 structured vs. 0.38 unstructured
  [1-S]. The more conservative state-of-the-art re-analysis — **Sackett, Zhang, Berry & Lievens
  (2022)** — ranks **structured interviews as the single top selection procedure**, ~0.42 vs.
  ~0.19 unstructured (roughly double) [2-S][3-S]. Direction (structured > unstructured) is
  uncontested; exact magnitude is methodology-dependent.
- **Google re:Work** equates its rubrics with **BARS** and reports ~four structured interviews
  predict a hire with ~86% confidence [4-S][5-S]. *(The "four/86%" figure is widely attributed
  to Google via secondary summaries — present as attributed, not independently verified.)*
- **BARS (Behaviorally Anchored Rating Scale):** each scale point is anchored with a concrete,
  observable behavioral example from real critical incidents; raters match the response to the
  best-fitting anchor, making each score traceable to observed behavior [6-S][7-S][8-S].
  Associated with higher validity, higher inter-rater reliability, and less bias [7-S][9-S].
- **Consistency & defensibility:** standardized questions + anchored criteria produce
  comparable, rankable responses and are easier to defend against adverse-impact claims [4-S][10-S].

### 4. Audio / communication signals
**Defensibly assessable** (validate against the target population, control confounds):
speaking rate/pace, fluency (articulation rate, pause patterns, repairs), filler-word
frequency, talk-time balance/turn-taking, clarity/intelligibility, response latency
[14-S][15-S][16-S]. These describe *what/how much* was said — a legitimate
**communication-clarity** construct.
- *Critical caveat:* **computable ≠ valid or fair.** Pace/pauses/"fluency" can be confounded by
  non-native speech, dialect, disability, anxiety, and connection quality — surface them as
  **descriptive feedback**, not scored selection criteria [15-S][17-S].

**Not defensible / risky:**
- **Accent / national origin** — Title VII risk; consider only where it *materially interferes*
  with the job [18-S][19-S].
- **Emotion / affect from voice or face** — Barrett et al. (2019, 1,000+ studies) found no
  reliable basis for inferring emotion from facial movement; the ACLU calls emotion recognition
  scientifically unfounded; speech-emotion models show demographic bias [20-S][21-S][22-S].
- **Vocal "engagement"/"enthusiasm"/personality inference** — confounded by accent, dialect,
  proficiency, anxiety [24-S].
- **EU red line:** **EU AI Act Art. 5(1)(f) prohibits inferring emotions in workplace/education**
  (narrow medical/safety exceptions), effective **2 Feb 2025**, explicitly covering voice-pattern
  emotion inference [25-S][26-S].
- **Industry precedent:** HireVue dropped facial-analysis screening in Jan 2021 after an EPIC FTC
  complaint [27-S][28-S].

### 5. Fairness, bias & legal/compliance (jurisdiction-dependent; verify primaries)
- **NYC Local Law 144 (AEDT):** independent **bias audit** (≤1 year old), **publish** a summary,
  **notice to candidates ≥10 business days** before use disclosing what's assessed. Effective
  Jan 1 2023; enforcement from Jul 5 2023; penalties ~$500–$1,500/violation [1-L][5-L]. *Confirm
  exact methodology/penalties with DCWP.*
- **EU AI Act:** recruitment/selection is **high-risk (Annex III §4)** → risk management, data
  governance, logging, transparency, **human oversight**, conformity assessment. **Art. 5(1)(f)**
  *prohibits* workplace emotion inference. In force 1 Aug 2024; prohibitions from 2 Feb 2025; most
  high-risk employment obligations from 2 Aug 2026 (some to 2027) [6-L][7-L][9-L]. *Verify dates
  vs. the official Commission timeline (possible "simplification").*
- **US EEOC / Title VII / ADA:** AI tools can cause adverse impact; the **four-fifths rule is a
  heuristic, not a safe harbor**; employers can be **liable for vendor tools** [11-L][12-L][13-L].
  ADA: provide accommodations, avoid "screening out" disabled candidates, no prohibited
  medical/disability inquiries [14-L][15-L]. **Status flag:** in 2025 the EEOC *removed* its
  May-2023 Title VII and May-2022 ADA AI guidance, but **Title VII and the ADA remain fully in
  force** — treat the removed docs as best-practice references [16-L].
- **GDPR (EU/UK):** lawful basis (consent is fragile in employment; faces/voices may be
  special-category biometric data); **Art. 22** right not to be subject to *solely* automated
  significant decisions, with rights to human intervention/contest; transparency about the logic
  (CJEU *SCHUFA*); data minimization & short retention for video [17-L][18-L].
- **Discrimination risks to avoid scoring:** accent (national origin); facial/appearance (race,
  gender, age, disability proxies); **eye-contact/gaze/affect** — penalizes autistic/ADHD/
  neurodivergent candidates and may be ADA "screening out" [22-L][23-L][24-L].

### 6. Best practices for human-in-the-loop AI screening
1. **AI as decision-support, not decision-maker** — humans retain discretion on livelihood
   decisions [25-L][26-L] (aligns with EU AI Act oversight and GDPR Art. 22).
2. **Transparency & disclosure** — tell candidates AI is used, what it assesses, and their rights.
3. **Validation & job-relatedness** — every scored signal job-related, validated, monitored for
   adverse impact; exclude signals lacking demonstrated validity (e.g., facial affect).
4. **Keep subjective video/audio cues advisory, never determinative**; offer alternative formats
   and ADA accommodations.
5. **Audit, monitor, accommodate** — independent bias audits (required in NYC), ongoing impact
   monitoring, accommodation pathways (incl. waiving the tool), vendor due diligence, and **human
   review of adverse outcomes** before rejection.

---

## Sources

**§1–2 (competencies & video):**
1. SHRM — Transform Interviewing into Strategic Talent Selection. https://www.shrm.org/topics-tools/tools/toolkits/transform-interviewing-into-strategic-talent-selection
2. SHRM — Body of Applied Skills and Knowledge (BASK). https://www.shrm.org/credentials/certification/exam-preparation/bask
3. SHRM — State of Global Workplace Culture 2024. https://www.shrm.org/topics-tools/research/the-state-of-global-workplace-culture-in-2024
4. Welcome to the Jungle — Soft skills employers look for in 2024. https://www.welcometothejungle.com/en/articles/soft-skills-employers-look-for-2024-guide
5. Indeed — STAR Interview Response Technique. https://www.indeed.com/career-advice/interviewing/how-to-use-the-star-interview-response-technique
6. BetterUp — STAR Method Interview Questions & Tips. https://www.betterup.com/blog/star-interview-method
7. The Muse — STAR Method. https://www.themuse.com/advice/star-interview-method
8. Criteria Corp — Latest Scientific Findings on Employee Selection. https://www.criteriacorp.com/blog/updates-employee-selection-science
9. Schmidt & Hunter (1998 / 2016 update). https://home.ubalt.edu/tmitch/645/session%204/Schmidt%20&%20Oh%20validity%20and%20util%20100%20yrs%20of%20research%20Wk%20PPR%202016.pdf
10. Test Partnership — Candidate assessments in hiring. https://www.testpartnership.com/blog/candidate-assessments.html
11. SelectSoftwareReviews — Active Listening Techniques. https://www.selectsoftwarereviews.com/blog/active-listening
12. HBR — Why Hiring for Cultural Fit Can Thwart Diversity (2016). https://hbr.org/2016/04/why-hiring-for-cultural-fit-can-thwart-your-diversity-efforts
13. Sapia.ai — Cultural fit assessment. https://sapia.ai/resources/blog/cultural-fit-assessment/
14. Riverside — Video Interview Background Best Practices. https://riverside.com/blog/video-interview-backgrounds
15. Spark Hire — What to Wear for a Virtual Interview. https://www.sparkhire.com/video-interviews/what-to-wear/
16. SPSP — Nonverbal Cues in the Employment Interview (Martín-Raugh). https://spsp.org/news/character-and-context-blog/mart%C3%ADn-raugh-job-interview-nonverbal-cues
17. Speaking without words: meta-analysis of 70+ years of nonverbal cues (J. Org. Behavior). https://onlinelibrary.wiley.com/doi/10.1002/job.2670
18. Arseneault et al. (2024), Applied Psychology — discrimination in async video interviews. https://iaap-journals.onlinelibrary.wiley.com/doi/10.1111/apps.12471
19. Cannata, O'Hora & Redfern (2024), SAGE — culture & nonverbal expression. https://journals.sagepub.com/doi/10.1177/14705958241244689
20. Understood.org — Inclusive ways to rethink interview strategy. https://www.understood.org/en/articles/8-inclusive-ways-to-rethink-your-interview-strategy-for-people-with-disabilities
21. ADA National Network — Pre-Employment: Interviews, Hiring, Examinations. https://adata.org/employment-resource-hub/pre-employment-interviews-hiring-and-examinations
22. Virginia Lawyers Weekly (2025) — Deaf woman alleges AI bias in video interview. https://valawyersweekly.com/2025/04/15/deaf-woman-alleges-ai-bias-in-video-interview-process/

**§3–4 (structure, rubrics, audio) — suffix -S:**
1-S. Validity of the Employment Interview: A Meta-Analysis. https://www.researchgate.net/publication/229904967_The_Validity_of_the_Employment_Interview_A_Meta-Analysis
2-S. Sackett et al. (2022), J. Applied Psychology (PubMed). https://pubmed.ncbi.nlm.nih.gov/34968080/
3-S. Insights from Sackett et al. (2022, 2023). https://www.master-hr.com/insights/insights-from-sackett-et-al-2023/
4-S. Google re:Work — Guide to Structured Interviewing. https://rework.withgoogle.com/intl/en/guides/a-guide-to-structured-interviewing-for-better-hiring-practices
5-S. Zivaro — Structured vs. Unstructured Interviews. https://www.zivaro.ai/blog/structured-vs-unstructured-interviews
6-S. eLeaP — BARS: A Complete Guide. https://performance.eleapsoftware.com/glossary/behaviorally-anchored-rating-scale-bars-a-complete-guide-for-modern-performance-management-systems/
7-S. Engagedly — Behaviourally Anchored Rating Scale Guide. https://engagedly.com/blog/behaviourally-anchored-rating-scale-a-complete-guide/
8-S. Kell et al. (2017), ETS Research Report — BARS for structured interviews. https://onlinelibrary.wiley.com/doi/full/10.1002/ets2.12152
9-S. Test Partnership — Structured vs Unstructured Interviews. https://www.testpartnership.com/blog/structured-vs-unstructured-interviews.html
10-S. Strategic HR — How Structured Interviews Reduce Bias. https://strategichrinc.com/how-structured-interviews-reduce-bias-in-recruiting/
11-S. VidCruiter — Remove Bias From Your Interview Rubric. https://vidcruiter.com/interview/structured/interview-rubric/
12-S. SHRM — 7 Practical Ways to Reduce Bias in Hiring. https://www.shrm.org/topics-tools/news/talent-acquisition/7-practical-ways-to-reduce-bias-hiring-process
13-S. SHRM Labs — Eliminating Biases in Hiring. https://www.shrm.org/labs/resources/eliminating-biases-in-hiring--structured-interviewing-and-ai-solutions
14-S. Leveraging Multimodal Behavioral Analytics for Automated Job Interview Assessment (arXiv). https://arxiv.org/pdf/2006.07909
15-S. PRAAT Scripts to Measure Speed/Breakdown Fluency (Taylor & Francis). https://www.tandfonline.com/doi/full/10.1080/0969594X.2021.1951162
16-S. Measures of Utterance Fluency in Automatic Speech Evaluation (2023). https://www.tandfonline.com/doi/full/10.1080/15434303.2023.2283839
17-S. ERIC — Interpretations of Spoken Utterance Fluency. https://files.eric.ed.gov/fulltext/EJ1295082.pdf
18-S. U.S. EEOC — National Origin Discrimination. https://www.eeoc.gov/national-origin-discrimination
19-S. Sanford Heisler Sharp — Accent Discrimination. https://sanfordheisler.com/employment-law/discrimination-harassment/accent-discrimination/
20-S. Barrett et al. (2019) — Emotional Expressions Reconsidered. https://www.semanticscholar.org/paper/Emotional-Expressions-Reconsidered:-Challenges-to-Barrett-Adolphs/c489b6787c5af8aca97f4761343a66f3f189b35d
21-S. ACLU — Experts Say 'Emotion Recognition' Lacks Scientific Foundation. https://www.aclu.org/news/privacy-technology/experts-say-emotion-recognition-lacks-scientific
22-S. A Review on Speech Emotion Recognition (2023), ScienceDirect. https://www.sciencedirect.com/science/article/abs/pii/S0925231223011384
23-S. Speech Emotion Recognition in Mental Health (2025), JMIR. https://mental.jmir.org/2025/1/e74260
24-S. Cogn-IQ — AI in Hiring Assessments: The Validity Evidence. https://www.cogn-iq.org/blog/ai-hiring-assessments/
25-S. FPF — Red Lines under EU AI Act: emotion recognition. https://fpf.org/blog/red-lines-under-eu-ai-act-unpacking-the-prohibition-of-emotion-recognition-in-the-workplace-and-education-institutions/
26-S. Wolters Kluwer — Prohibition of AI Emotion Recognition in the Workplace. https://legalblogs.wolterskluwer.com/global-workplace-law-and-policy/the-prohibition-of-ai-emotion-recognition-technologies-in-the-workplace-under-the-ai-act/
27-S. EPIC — HireVue Halts Use of Facial Recognition. https://epic.org/hirevue-facing-ftc-complaint-from-epic-halts-use-of-facial-recognition/
28-S. SHRM — HireVue Discontinues Facial Analysis Screening. https://www.shrm.org/topics-tools/news/talent-acquisition/hirevue-discontinues-facial-analysis-screening

**§5–6 (law & human-in-the-loop) — suffix -L:**
1-L. NYC DCWP — Automated Employment Decision Tools (AEDT). https://www.nyc.gov/site/dca/about/automated-employment-decision-tools.page
2-L. NYC Rules — AEDT final rule. https://rules.cityofnewyork.us/rule/automated-employment-decision-tools-2/
3-L. NYC DCWP — AEDT FAQ (PDF). https://www.nyc.gov/assets/dca/downloads/pdf/about/DCWP-AEDT-FAQ.pdf
4-L. NY State Comptroller (Dec 2025) — Enforcement of Local Law 144. https://www.osc.ny.gov/state-agencies/audits/2025/12/02/enforcement-local-law-144-automated-employment-decision-tools
5-L. Epstein Becker Green — Taking Stock of NYC's AEDT Law. https://www.workforcebulletin.com/taking-stock-of-new-york-citys-automated-employment-decision-tools-law
6-L. EU AI Act — Annex III: High-Risk AI Systems. https://artificialintelligenceact.eu/annex/3/
7-L. FPF — Red Lines under EU AI Act. https://fpf.org/blog/red-lines-under-eu-ai-act-unpacking-the-prohibition-of-emotion-recognition-in-the-workplace-and-education-institutions/
8-L. EU AI Act — Article 5: Prohibited AI Practices. https://artificialintelligenceact.eu/article/5/
9-L. EU AI Act — Implementation Timeline. https://artificialintelligenceact.eu/implementation-timeline/
10-L. European Commission — Regulatory framework on AI. https://digital-strategy.ec.europa.eu/en/policies/regulatory-framework-ai
11-L. Proskauer — EEOC Technical Document on AI and Title VII (May 2023). https://www.lawandtheworkplace.com/2023/05/eeoc-releases-technical-document-on-ai-and-title-vii/
12-L. Mayer Brown — EEOC Title VII Guidance on Employer Use of AI (Jul 2023). https://www.mayerbrown.com/en/insights/publications/2023/07/eeoc-issues-title-vii-guidance-on-employer-use-of-ai-other-algorithmic-decisionmaking-tools
13-L. Klehr Harrison — EEOC Guidance on AI in Selection Procedures. https://klehr.com/publications/eeoc-issues-guidance-further-cautioning-employers-about-the-use-of-artificial-intelligence-in-selection-procedures/
14-L. Morgan Lewis — EEOC Guidance on Algorithms, AI, and Disability Discrimination (May 2022). https://www.morganlewis.com/pubs/2022/05/eeoc-releases-guidance-on-algorithms-ai-and-disability-discrimination-in-hiring
15-L. Littler — EEOC Guidance on AI and the ADA. https://www.littler.com/news-analysis/asap/eeoc-issues-guidance-artificial-intelligence-and-americans-disabilities-act
16-L. Cooley LLP (Feb 2025) — Federal Laws Still Apply Despite AI Guidance Removal. https://www.cooley.com/news/insight/2025/2025-02-21-gone-but-not-forgotten-federal-laws-still-apply-despite-guidance-disappearance-act
17-L. UK ICO — Rights related to automated decision making including profiling. https://ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/individual-rights/individual-rights/rights-related-to-automated-decision-making-including-profiling/
18-L. GDPR-Text — Article 22 GDPR. https://gdpr-text.com/read/article-22/
19-L. EPIC — HireVue Halts Use of Facial Recognition. https://epic.org/hirevue-facing-ftc-complaint-from-epic-halts-use-of-facial-recognition/
20-L. SHRM — HireVue Discontinues Facial Analysis Screening. https://www.shrm.org/topics-tools/news/talent-acquisition/hirevue-discontinues-facial-analysis-screening
21-L. Fortune (Jan 2021) — HireVue stops using facial expressions. https://fortune.com/2021/01/19/hirevue-drops-facial-monitoring-amid-a-i-algorithm-audit/
22-L. Bloomberg Law — AI Hiring Tools Elevate Bias Danger for Autistic Applicants. https://news.bloomberglaw.com/daily-labor-report/ai-hiring-tools-elevate-bias-danger-for-autistic-job-applicants
23-L. IHRB — The hidden disability bias in AI-powered recruitment. https://www.ihrb.org/latest/the-hidden-disability-bias-in-ai-powered-recruitment
24-L. NC Civil Rights Law Review (2025) — AI and Hiring Discrimination. https://journals.law.unc.edu/nccivilrightslaw/2025/01/ai-and-hiring-discrimination-the-impact-artificial-intelligence-hiring-tools-will-have-on-companies/
25-L. SHRM — The State of AI in HR 2026 Report. https://www.shrm.org/topics-tools/research/state-of-ai-hr-2026/full-report
26-L. SHRM — Keep Humans in the Loop for Successful AI Adoption. https://www.shrm.org/topics-tools/news/keep-humans-in-the-loop-for-successful-ai-adoption

---

### Unresolved items to verify before relying on specifics
- Exact NYC DCWP bias-audit methodology and current penalties.
- EU AI Act dates against the official Commission timeline (possible "simplification"/delay).
- US EEOC AI guidance was **withdrawn in 2025**, though Title VII/ADA remain in force.
- The Google "four interviews / 86%" and any "STAR +25%" figures are **not** primary-verified — do not present as fact.
