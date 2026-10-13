---
name: cv-builder
description: Write and render the user's CV (DOCX + PDF, SheetsResume/Garamond style) from the JSON master profile, optionally tailored to a job offer, in French or English. Use when the user asks to make, tailor, translate or review a CV, or to rewrite CV bullets or the summary.
---

# CV Builder

Turns the master profile into a tailored, truthful, one-page CV. A Python script renders it as `.docx` + `.pdf` in a clean single-column style inspired by the SheetsResume.com template, **in Arial** by default: large bold name, sections with a rule under the heading, company and dates in bold on one line, title and location in italics on the next, `•`/`o` bullets.

Files:
- `profile/master-profile.json` (project root): **the single source of truth**. Schema described below.
- `references/guidelines.md`: CV writing rules (National Careers Service, modeles-de-cv.com, Andrew Lambert) and the pre-submission checklist.
- `scripts/build_cv.py`: JSON → DOCX → PDF (PDF via LibreOffice). Prints the page count and warns above one page.
- `scripts/install_fonts.ps1`: installs the bundled EB Garamond (the template's original look). Only needed if `meta.font` is set back to `"EB Garamond"`.

## Workflow

### 1. Inputs
- Read `profile/master-profile.json` and `references/guidelines.md`.
- Target offer: if `output/<folder>/job-match.md` exists (from the `job-match` skill), reuse its requirements table and tailoring plan. Otherwise extract the must-haves and keywords from the offer yourself. No offer means a generic CV.
- Language: the profile's `meta.lang` by default; use the offer's language if there is one.

### 2. Write `output/<YYYY-MM-DD>_<company>/cv.json` (`cv_en.json` for an English version, same folder)
Start from a copy of the master profile, then tailor it. **Only select, reorder and reword; never invent.**
- `basics.headline`: echo the target job title, while staying true to the profile.
- `summary`: 3–4 lines, written for the role: who you are, then your strongest relevant proof, then what you bring.
- `experience[].bullets`: put the most relevant bullets first and cut weak ones (2–6 per job, fewer for older jobs). Use the formula *action verb + task + context/tech + measurable result*. Rephrase with the offer's keywords only where they are true. Use at most 1–2 `**bold**` phrases per bullet.
- `skills`: put the offer's keywords first within each group; drop groups or items that are irrelevant to the role.
- `projects`: keep the 1–2 most relevant ones. Never render entries with `"include": false`.
- `meta.section_order`: for a student, `education` may go before `experience` if the offer is academic.
- `meta.filename`: `<FIRSTNAME_LASTNAME>_CV_<Company>` in capitals (add `_EN` for English), e.g. `ALEX_MARTIN_CV_Acme`.
- **English CV:** write the English text directly into the main fields of `cv.json` (title, bullets, summary, labels…) and set `meta.lang` to `"en"`. In the master profile, the `_en` fields are only used when rendering with `--lang en`.
- Remove `notes` and `_todo`/`_about` keys from `cv.json`; the renderer ignores them anyway.

### 3. Render
```bash
python .claude/skills/cv-builder/scripts/build_cv.py output/<folder>/cv.json
```
This writes `<filename>.docx` and `<filename>.pdf` next to `cv.json`. Requirements: `pip install python-docx` and LibreOffice for the PDF.

### 4. Verify
Read the PDF. It must be **exactly 1 page**, with nothing wrapping awkwardly (contact line, dates) and no leftover placeholders. If it runs over, cut the least relevant bullets first, then lower `meta.font_size` (Arial: 10 by default, the guideline minimum). Arial is wide, so shorten any bullet that wraps by only 1–3 words rather than leaving orphan words. If a lot of space is left, try 10.5, but keep it only if it doesn't create orphan words. A full master profile often runs to 2 pages; a tailored CV must cut it to 1. Run the checklist in `references/guidelines.md`, then the design audit from the `cv-design` skill (`scripts/audit_cv.py`). The look itself (fonts, sizes, colours, margins) is set by `meta.design`; see `cv-design`.

### 5. Hand-off
Give the PDF and DOCX paths, list the keywords covered, and list the open gaps and questions. If the user supplies new facts, offer to add them to `master-profile.json`.

## JSON schema (master-profile.json and cv.json)
```jsonc
{
  "meta": { "lang": "fr|en", "page": "A4|Letter", "font": "Arial", "font_size": 10, "name_size": 24, "links_on_new_line": true,
            "section_order": ["summary","experience","education","projects","skills"], "filename": "ALEX_MARTIN_CV" },
  "basics": { "name", "headline", "email", "phone", "location", "links": [{ "label", "url" }], "availability" },
  "summary": "…",
  "experience": [{ "org", "title", "start": "YYYY-MM", "end": "YYYY-MM|present", "location",
                   "bullets": ["text", { "text": "…", "sub": ["sub-bullet"] }], "include": true }],
  "education":  [{ "org", "degree", "start?", "end", "location", "details": ["…"] }],
  "projects":   [{ "name", "subtitle", "url?", "url_label?", "date", "bullets": [] , "include": true }],
  "certifications": ["…"],
  "skills":     [{ "label", "items": [] }],
  "languages":  [{ "name", "level" }],
  "interests":  ["…"],
  "notes": { }            // master profile only: open questions, unconfirmed repos (never rendered)
}
```
- Inline markup: `**bold**`, `*italic*`, `[label](url)`.
- Any field may have an `<field>_en` twin, which is used by `--lang en`.
- The skills, languages, interests and certifications all render in one final block. Its heading is built from whatever is present, e.g. "COMPÉTENCES, LANGUES & CENTRES D'INTÉRÊT".

## Other requests
- **Review a CV:** score it against the checklist and give prioritised fixes (quote the line, then propose a rewrite).
- **Bullets or summary only:** return the text; no rendering needed.

## Hard rules
- Truthfulness: use only facts from `master-profile.json` or that the user has stated. Ask for metrics rather than inventing them.
- No age, date of birth, marital status, nationality or photo unless the user asks.
- Edit `master-profile.json` only with the user's confirmation; tailoring happens in the per-application `cv.json`.
