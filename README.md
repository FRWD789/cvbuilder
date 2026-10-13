# cvBuilder

**An agentic job-application pipeline for [Claude Code](https://claude.com/claude-code).** Give it a job offer (URL, text or file) and it produces:

1. a **fit assessment**: requirement-by-requirement evidence table, eligibility checks (dates, duration, location, language), fit score and verdict;
2. a **tailored one-page CV** as DOCX + PDF, ATS-friendly, built only from facts in your profile;
3. a **cover letter** (Markdown + PDF) and **recruiter messages** (LinkedIn note, message, follow-up);
4. a row in an **Excel tracker** (status, link, dates, domain, fit).

Every step has a check: the CV must fit on one page, pass a 24-point ATS and design audit, and every claim must trace back to your profile. Facts that can't be verified are flagged as questions, never written.

> Built for internship and junior applications in France (French by default, English supported), but it works for any CV in either language.

## How it works

```
job offer ─► job-match ─► gate ─► cv-builder ─► verify (1 page + audit) ─► application pack + tracker
                                       ▲
                     profile/master-profile.json (your single source of truth)
```

| Skill (`.claude/skills/`) | What it does |
|---|---|
| `apply` | Orchestrates the whole flow; writes the cover letter, recruiter messages and README; updates the tracker |
| `job-match` | Assesses an offer against your profile: evidence table, eligibility, score, tailoring plan |
| `cv-builder` | Writes the tailored `cv.json` and renders DOCX + PDF (`scripts/build_cv.py`), plus the letter (`scripts/build_letter.py`) |
| `cv-design` | Design presets and the ATS/design audit (`scripts/audit_cv.py`) |

## Setup

Requirements: [Claude Code](https://claude.com/claude-code), Python 3.10+, and [LibreOffice](https://www.libreoffice.org/) for the PDF export (without it you get the DOCX only).

```bash
git clone https://github.com/<you>/cvbuilder.git
cd cvbuilder
pip install -r requirements.txt
cp profile/master-profile.example.json profile/master-profile.json
```

Then fill `profile/master-profile.json` with your own data, or let Claude do it:

```
> Create my master profile from my CV: ./my-cv.pdf
```

**Your profile, your applications and the tracker are git-ignored**, so they never leave your machine.

## Usage

Open Claude Code in the folder and talk to it:

```
> Assess and create a CV for this offer: https://...
> Here's the offer text: ...
> Make a generic CV for data engineering roles
> Make the cover letter in English
> I applied to Acme / Acme rejected me        (updates the tracker)
> Where am I?                                  (lists the tracker)
```

Each application gets its own folder, `output/<date>_<company>/`:

```
job-match.md                fit report and tailoring plan
cv.json                     the tailored CV data
<NAME>_CV_<Company>.pdf     the CV (+ .docx)
lettre-de-motivation.md     cover letter (+ <NAME>_Lettre_<Company>.pdf)
message-recruteur.md        LinkedIn note, message, follow-up
README.md                   how to apply, talking points, next actions
```

See [`examples/2027-01-10_acme-robotics/`](examples/2027-01-10_acme-robotics/) for a full example built from the fictional profile.

You can also run the scripts directly:

```bash
python .claude/skills/cv-builder/scripts/build_cv.py output/<folder>/cv.json [--lang en] [--design ats-modern]
python .claude/skills/cv-builder/scripts/build_letter.py output/<folder>/lettre-de-motivation.md --company "Acme" --subject "..." [--lang en]
python .claude/skills/cv-design/scripts/audit_cv.py output/<folder>/<FILE>.docx --keywords "Python,React"
python .claude/skills/apply/scripts/tracker.py list
```

## The profile

`profile/master-profile.json` holds everything about you: contact details, experience, education, projects, skills, languages. The schema is documented in [`.claude/skills/cv-builder/SKILL.md`](.claude/skills/cv-builder/SKILL.md). Useful conventions:

- `"include": false` on an entry keeps it as a draft: never rendered, never used as evidence.
- Any field can have an `_en` twin (`headline_en`, `bullets_en`…) for English CVs.
- `notes.open_questions` lists facts to confirm; the pipeline asks about them when they matter for an offer.
- Text supports `**bold**`, `*italic*` and `[label](url)`.

## Rules the agent follows

- **Truthfulness first**: it never adds a skill, metric or experience that isn't in your profile or confirmed by you. Gaps are reported as gaps, with honest ways to address them.
- The profile only changes with your confirmation; tailoring happens in each application's `cv.json`.
- It never sends or submits anything on your behalf.

## Design

Two presets in `build_cv.py`: `ats-modern` (default: Arial, 16 pt name, navy accent, 10 pt body, 1.5 cm margins) and `sheets` (dense, black). The rules behind them (ATS formatting, size hierarchy, 60-30-10 colour, white space) are in [`.claude/skills/cv-design/references/principles.md`](.claude/skills/cv-design/references/principles.md). The CV writing rules are in [`.claude/skills/cv-builder/references/guidelines.md`](.claude/skills/cv-builder/references/guidelines.md).

## License

MIT. The bundled EB Garamond fonts are under the SIL Open Font License (`.claude/skills/cv-builder/assets/fonts/OFL.txt`).
