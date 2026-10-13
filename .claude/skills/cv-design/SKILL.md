---
name: cv-design
description: Design and audit the visual layout of the user's CV, following ATS-friendly formatting and design principles (fonts, 14–16/11–12/10 pt size hierarchy, 60-30-10 colours, 1.5–2 cm margins, left alignment, white space). Chooses or tweaks a design preset for build_cv.py, runs the design audit on a generated DOCX/PDF, and fixes the issues. Use when the user asks about the CV's look, layout, fonts, colours, spacing or ATS compatibility, or wants a design check before sending.
---

# CV Design

Controls *how the CV looks*, never *what it says* (content is the job of `cv-builder`).

Files:
- `references/principles.md`: the rules (ATS, typography, colour, white space), where each one is implemented, and how the presets compare. **Read it first.**
- `scripts/audit_cv.py`: checks a generated `.docx` (+ its `.pdf`) and prints a PASS/WARN/FAIL report with a score.
- Rendering: `.claude/skills/cv-builder/scripts/build_cv.py`, design presets in `DESIGN_PRESETS`.

## Design settings (in cv.json / master-profile.json)
```jsonc
"meta": {
  "design": {
    "preset": "ats-modern",        // "sheets" (SheetsResume, dense black) | "ats-modern" (these principles)
    // any of these override the preset:
    "font": "Arial", "body_size": 10, "name_size": 16, "headline_size": 11, "heading_size": 11.5,
    "margin_top_cm": 1.2, "margin_bottom_cm": 1.0, "margin_side_cm": 1.5,
    "text_color": "222222", "accent_color": "1F3A5F", "name_color": "1F3A5F",
    "entry_layout": "title_first",  // title_first = bold job title first | org_first
    "entry_gap": 7, "section_gap": 10, "heading_gap_after": 3, "bullet_gap": 1, "line_spacing": 1.05,
    "summary_align": "left", "link_underline": false, "skills_heading": "simple", "links_on_new_line": true,
    "date_format": "month_abbr",    // "numeric" = 01/2026, for ATS that parse the CV (SmartRecruiters, Workday, Taleo)
    "rule_under_header": false
  }
}
```
Precedence: preset < old top-level keys (`meta.font`, `meta.font_size`, `meta.name_size`, `meta.links_on_new_line`) < `meta.design`. When switching a CV to a preset, **remove the old top-level keys**, otherwise they silently override it.
Without `meta.design`, the preset is `sheets` (backward compatible).
Preview any preset without editing the JSON: `build_cv.py cv.json --design ats-modern --name APERCU_ats-modern`. With `--design`, the preset's own values are used and the old keys are ignored.

Accent colours that respect the rules: navy `1F3A5F` (default), forest green `2E5E4E`, burgundy `6D1F2F`, slate `37474F`. Never use saturated or fluorescent colours, and never more than one accent.

## Workflows

### A. Audit a CV ("is my CV ATS-friendly?", "check the design")
```bash
python .claude/skills/cv-design/scripts/audit_cv.py output/<folder>/<FILE>.docx --keywords "<must-have keywords from job-match.md>"
```
1. Read the PDF as well: the script can't see **orphan words** (a bullet whose last line holds 1–3 words) or visual balance.
2. Report what failed and what's at risk, in plain words, grouped as: ATS blockers (FAIL) → typography/colour/space (WARN) → content (acronyms, keywords).
3. For each item, propose the fix: a preset setting, or a wording change in `cv.json`.

### B. Apply or tweak a design
1. Set `meta.design` in the application's `cv.json` (or in `profile/master-profile.json` to change the default for future CVs, with the user's OK) and remove the old top-level design keys.
2. Re-render with `build_cv.py`, then audit.
3. Fit loop (one page): first shorten bullets that wrap by 1–3 words, then cut the least relevant bullet, then reduce `entry_gap`/`section_gap` by 1–2 pt, then `margin_side_cm` (minimum 1.5). **Never go below 10 pt body or 14 pt name.**
4. Show the user the result (read the PDF) along with the audit score before and after.

### C. Fix content-level design issues (in cv.json, truthfully)
- **Acronyms** flagged by the audit: spell them out on first use, e.g. "module CRM" → "module de gestion de la relation client (CRM)", "RBAC" → "contrôle d'accès par rôles (RBAC)", "POO" → "programmation orientée objet (POO)", "DEC" → "DEC (diplôme d'études collégiales, Québec)". Keep each one short, and only expand where space allows: one page wins.
- **Missing keywords**: add them only where they're true (cross-check with job-match). Never use a hidden block or white text.
- **Headings**: keep the standard ones (the generator's labels already are).

### D. New preset or look
Add an entry to `DESIGN_PRESETS` in `build_cv.py`, document it in the presets table of `references/principles.md`, then render and audit `examples/` CV with it as a regression check (one page, score ≥ 90).

## Hard rules
- No tables, columns, text boxes, images, icons, photos, or content in the page header/footer. Ever.
- One accent colour, muted. Text ≥ 7:1 contrast.
- Body ≥ 10 pt, name 14–16 pt (`ats-modern`), headings 11–12 pt.
- Send the PDF unless the offer explicitly asks for .docx.
- Design changes never alter facts. Wording changes for fit or acronyms must keep the meaning (cv-builder's truthfulness rules apply).
