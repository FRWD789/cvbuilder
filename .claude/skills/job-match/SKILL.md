---
name: job-match
description: Assess a job description or internship offer against the user's master profile. Produces a fit score, a requirement-by-requirement evidence table, ATS keyword coverage, eligibility checks (dates, duration, location, language), gaps, and an apply / tailor / skip recommendation with a tailoring plan for cv-builder. Use when the user shares a job posting (text, URL or file) and asks whether it fits, how well they match, what's missing, or whether to apply.
---

# Job Match — job description vs master profile

Compares an offer against the user's real profile and reports how well it fits. Analysis only: it never changes the CV or the profile. Generating the CV is the `cv-builder` skill's job.

**Profile (single source of truth):** `profile/master-profile.json` (project root). Read it fully every time; it changes often.

## 1. Get the job description
- **Pasted text**: use as is.
- **URL**: fetch it with WebFetch. LinkedIn, Indeed and Welcome to the Jungle pages often fail or come back truncated; if the content is missing or partial, ask the user to paste the text instead of guessing.
- **File** (PDF/DOCX/TXT in the project folder): read it.
- If several offers are given, assess each one and finish with a short comparison table ranking them.

## 2. Extract the offer
Write down, in the offer's language:
- Company, job title, contract type (stage / alternance / CDI / CDD), **start date, duration**, location, remote policy, salary or stipend if given.
- **Must-have requirements** (“requis”, “indispensable”, “maîtrise de”, “required”, “must”).
- **Nice-to-have requirements** (“un plus”, “apprécié”, “idéalement”, “bonus”, “preferred”).
- Required level: school year (e.g. Bac+3/4/5), years of experience.
- Languages required, with level.
- Main responsibilities (the verbs: développer, concevoir, maintenir, analyser…).
- **Application platform**: Welcome to the Jungle, SmartRecruiters, Workday, Taleo, Greenhouse, Lever, email… An ATS that **parses the CV** (SmartRecruiters, Workday, Taleo) means: use numeric dates (`meta.design.date_format: "numeric"`), check the auto-filled fields by hand, and there's no direct contact with the recruiter (go through LinkedIn).
- **Application requirements**: what the form asks for. Is a cover letter mandatory or optional? Are a portfolio, links or screening questions required? Is there a deadline (`validThrough`), and what's the interview process? On Welcome to the Jungle, look for the FAQ ("Une lettre de motivation est-elle obligatoire…") and the `application_fields` in the page source (`mandatory` / `optional` / `disabled`).
- **ATS keywords**: tools, frameworks, methods and domain terms as written in the offer (keep their exact spelling, e.g. “Node.js”, “CI/CD”, “PostgreSQL”).

If a requirement is ambiguous, say so instead of choosing the reading that suits the profile better.

## 3. Match each requirement against the profile
For every requirement, find evidence in the master profile and give it a status:

| Status | Meaning | Points |
|---|---|---|
| ✅ Proven | Shown in an experience or project bullet (real usage) | 1 |
| 🟡 Partial | Only listed in skills, only from coursework, or a close equivalent (e.g. MySQL for PostgreSQL, React for Vue, Express for NestJS) | 0.5 |
| ❌ Gap | No evidence | 0 |

Rules:
- Quote the evidence briefly (“Acme: REST API with 20 endpoints”). No evidence, no ✅.
- Equivalents are only 🟡, and the note says what the actual skill is.
- Entries with `"include": false` (drafts) and `notes.unconfirmed_github_repos` are not evidence. You may flag them as *possible evidence to confirm* in “Questions for the user”.
- Soft skills (“autonome”, “esprit d'équipe”) count as ✅ only if a bullet shows them (e.g. sprints, code reviews, documentation for a team).

## 4. Check eligibility (these can override the score)
- **Dates**: compare with `basics.availability` (and any confirmed flexibility in `notes`). Flag any mismatch in start date or duration (e.g. a 6-month internship when the profile offers 3).
- **Contract type**: an internship profile applying to a CDI or alternance is a mismatch.
- **Level**: the required school year or years of experience vs the profile's education and experience.
- **Location / remote**: vs `basics.location`; flag relocation.
- **Languages**: vs the profile's `languages`.
- **Work authorisation / clearance** if the offer mentions it. Don't assume; ask the user.

A **blocker** is a hard mismatch, such as the wrong contract type, impossible dates or a mandatory language level the profile doesn't have. Any blocker caps the verdict at “Skip, or contact the recruiter first”.

## 5. Score
```
must_score  = points on must-haves  / number of must-haves
nice_score  = points on nice-to-haves / number of nice-to-haves   (1.0 if there are none)
resp_score  = share of responsibilities already done in experience/projects (0, 0.5 or 1 each)
fit = round(100 × (0.60 × must_score + 0.15 × nice_score + 0.25 × resp_score))
```
Verdict:
- **≥ 75: Apply.** A strong match; tailor the CV.
- **55–74: Apply with tailoring.** Make the transferable skills stand out and address the gaps.
- **40–54: Long shot.** Apply only if motivated; address the gaps in the cover letter.
- **< 40, or any blocker: Skip, or contact the recruiter first.**

Show the arithmetic so the user can check it. The score is a guide; say so whenever a single critical gap matters more than the number suggests.

## 6. Report
Answer in the user's language. Use this structure:

```markdown
# <Job title> — <Company>
**Fit: NN/100 · <Verdict>** · <contract> · <start/duration> · <location>
**To apply**: CV ✅ · cover letter <mandatory / optional / not requested> · <other fields> · deadline <date>

## Verdict
2–3 sentences: why, the biggest strength, the biggest risk.

## Eligibility
✅/⚠️/⛔ Dates · Contract · Level · Location · Languages

## Requirements
| # | Requirement | Type | Status | Evidence / note |
|---|---|---|---|---|
| 1 | NestJS | Must | ✅ | Acme: CRM module in NestJS/Next.js |

## ATS keywords
Present in profile: …
Missing but true (to add to the CV wording): …   ← synonyms the profile does have
Missing (real gaps): …

## Gaps & how to address them
- <gap>: is it a quick win (a weekend tutorial or project), something to present as a transferable skill, or something to leave alone? Never suggest claiming it.

## Tailoring plan (for cv-builder)
- Headline: …
- Summary angle: …
- Experience/bullets to put first: …
- Bullets to cut: …
- Skills to put first: …
- Project to feature: …

## Questions for the user
Facts that would raise the score if true (e.g. “Have you used Docker in any project?”).
```

Then save the report to `output/<YYYY-MM-DD>_<company>/job-match.md` (create the folder; cv-builder uses the same folder) and give the path.

## 7. Next step
Offer to run `cv-builder` with the tailoring plan. If the user answers the “Questions for the user” with new facts, offer to add them to the master profile and then re-score.

## Hard rules
- Never inflate a match: a skill the profile doesn't show is a gap, even if it would be easy to learn.
- Never edit `master-profile.json` without the user confirming the new facts.
- Base the score on the offer's text, not on assumptions about the company.
