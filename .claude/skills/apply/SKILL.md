---
name: apply
description: End-to-end job application pipeline. Takes a job offer (text, URL or file), assesses the fit against the master profile (job-match), tailors and renders a one-page CV as DOCX + PDF (cv-builder), and produces an application pack, with a review gate between steps. Also handles updating the master profile from a CV file, GitHub or new facts. Use when the user says "apply to this", "prepare my application", "make a CV for this offer", or wants the whole flow rather than a single step.
---

# Apply: orchestrates the CV pipeline

```
job offer ──► 1. job-match ──► gate ──► 2. cv-builder (cv.json ─► build_cv.py ─► DOCX/PDF) ──► 3. verify ──► 4. pack
                    ▲                                                                              │
                    └──────────── profile/master-profile.json  ◄── 0. profile updates ◄────────────┘ (new facts, with the user's OK)
```

Components (don't duplicate their logic; follow their SKILL.md files):
| Step | Skill / file | Output |
|---|---|---|
| Profile | `profile/master-profile.json` | single source of truth |
| Assess | `.claude/skills/job-match/SKILL.md` | `output/<folder>/job-match.md` |
| Write + render | `.claude/skills/cv-builder/SKILL.md`, `scripts/build_cv.py` | `cv.json`, `<NAME>_CV_<Company>.docx/.pdf` |
| Rules | `.claude/skills/cv-builder/references/guidelines.md` | checklist |
| Design | `.claude/skills/cv-design/SKILL.md`, `scripts/audit_cv.py` | `meta.design` preset, design audit |
| Tracking | `scripts/tracker.py` | `suivi-candidatures.xlsx` (status, link, dates, domain) |

`<folder>` = `output/<YYYY-MM-DD>_<company-slug>/` (lowercase, hyphens). Every artifact for one application lives there.

## Step 0: Preflight (run once per session, quickly)
- `python -c "import docx"`: if it fails, run `pip install python-docx`.
- Check that LibreOffice exists (`soffice` on the PATH, or `C:\Program Files\LibreOffice\program\soffice.exe` on Windows). Without it, deliver the DOCX only and say so.
- The default font is Arial. Only if `meta.font` is `"EB Garamond"`: run `.claude/skills/cv-builder/scripts/install_fonts.ps1` when it isn't installed.
- Read `profile/master-profile.json` and note its `notes.open_questions`. Don't ask them all now; only the ones that matter for this offer.

## Step 1: Assess (job-match)
Follow the job-match skill: fetch or parse the offer, build the requirements table, run the eligibility checks, score it, and save `job-match.md`.
Show the user a **short** summary: score and verdict, eligibility flags, top 3 strengths, top gaps, and the questions whose answers would raise the score.

### Gate
- **Blocker found** (contract type, dates, mandatory language) or score < 40: stop and ask whether to continue anyway.
- **Questions pending**: ask them now in one batch (AskUserQuestion when they are multiple-choice). Add confirmed facts to `master-profile.json` (show the diff), then update the score.
- Otherwise continue without waiting, unless the user asked to review between steps.

## Step 2: Write and render (cv-builder)
Follow the cv-builder skill, using the job-match tailoring plan:
1. Write `<folder>/cv.json` (a tailored copy of the master profile; select, reorder and reword, never invent).
2. `python .claude/skills/cv-builder/scripts/build_cv.py <folder>/cv.json`
3. If the script warns about more than one page: trim bullets, re-render, repeat.

## Step 3: Verify
Read the PDF and check:
- Exactly 1 page, no awkward wraps, no `{{` placeholders, no `_todo`.
- Every bullet traces back to `master-profile.json` (diff the facts, not the wording).
- The offer's must-have keywords that are ✅ or 🟡 in job-match appear somewhere in the CV.
- The `guidelines.md` checklist passes (dates, contact details, spelling, accents, file name).
- Design audit (`cv-design` skill): `python .claude/skills/cv-design/scripts/audit_cv.py <folder>/<FILE>.docx --keywords "<must-haves>"`. No FAIL allowed; fix WARNs that are cheap (acronyms, keywords, orphan words).
If any check fails, fix it and re-render.

## Step 4: Application pack
Create `<folder>/README.md`:
- Offer: title, company, link, date assessed, score and verdict.
- Files: PDF, DOCX, cv.json, job-match.md.
- 3–5 talking points for an interview (strength ↔ requirement).
- Gaps and how to address them honestly (cover letter, interview).
- Status: `Prepared`, plus the exact tracker command for marking it `Applied`.

Then log it in the **tracker** (`suivi-candidatures.xlsx` at the project root; one row per offer, matched by URL):
```bash
python .claude/skills/apply/scripts/tracker.py upsert --company "<Company>" --position "<Job title>" \n  --domain "<field / industry, e.g. IA agentique / EdTech>" --location <City> --contract "<Stage N mois>" \n  --url "<offer URL>" --status Prepared --fit <score> --folder "output/<folder>" --notes "<deadline, blockers, next step>"
```
Columns: #, Company, Position, Domain, Location, Contract, Link, Status (drop-down, colour-coded), Date added, Date applied, Fit, Folder, Notes.
Statuses: To apply · Prepared · Applied · Interview · Offer · Rejected · Withdrawn. If the file is open in Excel the script asks the user to close it.

Always also produce, in the offer's language and using only facts from the profile:
- **`lettre-de-motivation.md`** whenever job-match finds the cover letter is **mandatory or optional**. About 1,500–2,000 characters, structured vous → moi → nous → availability, ready to paste, plus which value goes in each optional form field (LinkedIn, website…).
- **`message-recruteur.md`** every time: a LinkedIn connection note (≤ 300 characters), a fuller message or email, and a follow-up for 7–10 days later. Address it to a named person from the offer page when there is one (and ask the user to check the name), and be upfront about any blocker such as duration.
Render the letter to PDF (same style as the CV, 1 page) so it can be attached:
```bash
python .claude/skills/cv-builder/scripts/build_letter.py <folder>/lettre-de-motivation.md --company "<Company>" --subject "Candidature — <Job title> (<ref>)" [--lang en]
# English offer: write the letter in English and add --lang en (labels "Subject:", "Kind regards,", file <NAME>_Cover_Letter_<Company>)
```
→ `<NAME>_Lettre_<Company>.pdf`. Read it to check it fits on one page.
List both in the README and in the tracker notes.

**Application platform**: when job-match finds a parsing ATS (SmartRecruiters, Workday, Taleo…), render with `"date_format": "numeric"`, add a "How to apply" checklist to the README (upload the PDF, check the auto-filled fields, where the letter goes, answer screening questions truthfully), and word the recruiter message as "j'ai déposé ma candidature sur <platform>" (the message goes through LinkedIn, sent after applying).

Final message to the user: the score/verdict line, the PDF path, the keywords covered, the gaps, and the next actions.

## Other entry points
- **"Update my profile"** from new facts, a CV file (PDF/DOCX) or GitHub (the profile's GitHub link, `notes.unconfirmed_github_repos`): extract the facts, show the proposed JSON changes, write them only after the user confirms, and resolve the matching `notes.open_questions`.
- **"Generic CV"**: skip step 1 and render the master profile directly into `output/<date>_generic/`.
- **"English version"** of an existing application: write `<folder>/cv_en.json` translated from `cv.json` (`meta.lang: "en"`, filename `…_EN`), then render.
- **Several offers**: run step 1 for each, show a ranking table, and ask which ones to continue with.
- **"Where am I?"** / **"I applied to X"** / **"X rejected me"**: `tracker.py list`, or `tracker.py status --url <url> --status Applied --applied today` (or `Interview`, `Rejected`… with `--notes`). Also update the README status line.
- **Offers to keep for later**: `tracker.py upsert ... --status "To apply"` without generating a CV.

## Hard rules
- Truthfulness over score: never add a skill, metric or experience that isn't in the master profile or confirmed by the user.
- The master profile changes only with explicit confirmation; tailoring lives in each application's `cv.json`.
- Never send or submit anything on the user's behalf.
