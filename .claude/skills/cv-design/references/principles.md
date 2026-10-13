# CV design principles

The rules the `cv-design` skill enforces. Each rule says where it's implemented: **preset** = a `DESIGN_PRESETS` value in `cv-builder/scripts/build_cv.py`, **audit** = a check in `scripts/audit_cv.py`, **content** = wording in `cv.json`.

## 1. ATS-friendly formatting
Applicant tracking systems (ATS) parse a CV before a human reads it. The parser reads left to right, top to bottom.

| Rule | Why | Where |
|---|---|---|
| Standard section headings: "Expériences professionnelles", "Formation", "Compétences" / "Experience", "Education", "Skills". No creative titles ("Where I've Made an Impact") | The ATS maps headings to fields | preset `skills_heading: simple` · audit |
| No tables, columns or text boxes | Columns get interleaved and boxes skipped | Generator uses tab stops only · audit |
| Nothing in the page header or footer | Often ignored entirely | The contact block is in the body · audit |
| No images, icons, graphics or photo | Can't be parsed; icons carry no text | audit (DOCX + PDF) |
| Standard font: Arial, Calibri, Garamond or Georgia (Inter, Roboto, Open Sans are OK in the PDF, where fonts are embedded) | Avoids substituted fonts and garbled text | preset `font` · audit |
| PDF, unless the offer asks for .docx | Fixed layout, embedded fonts | cv-builder outputs both · audit (selectable text) |
| Job keywords used naturally, in context. Never a hidden block or white text | Stuffing gets detected and penalised | content · audit (keywords, hidden text) |
| Acronyms spelled out on first use, then abbreviated: "Search Engine Optimisation (SEO)", "gestion de la relation client (CRM)" | ATS and recruiters search for both forms | content · audit (lists the acronyms to expand) |

## 2. Typography
| Rule | Value | Where |
|---|---|---|
| Professional fonts | Sans-serif: Inter, Roboto, Open Sans, Arial, Calibri. Serif: Georgia, Garamond | preset `font` |
| Name | **14–16 pt** | preset `name_size` (ats-modern: 16) |
| Section headings | **11–12 pt** | preset `heading_size` (ats-modern: 11.5) |
| Body text | **10 pt** (11 if space allows) | preset `body_size` |
| Weight, not decoration | Use **bold** for job titles and degrees. Don't multiply colours or underlining | preset `entry_layout: title_first`, `link_underline: false` · audit |

## 3. Colour harmony: the 60-30-10 rule
- **60 %** white or light grey: background and breathing room.
- **30 %** dark grey or black: main text (ats-modern: `#222222`, contrast 15.9:1).
- **10 %** one muted accent (navy `#1F3A5F`, forest green `#2E5E4E`, burgundy `#6D1F2F`): name, section headings, separator lines only.
- **Contrast**: dark text on a light background, ≥ 7:1 (audit).
- **No loud colours**: fluorescent or highly saturated colours tire the eye (audit FAIL).

## 4. White space
| Rule | Value | Where |
|---|---|---|
| Generous side margins | **1.5–2 cm** | preset `margin_side_cm` (ats-modern: 1.5) |
| Air between blocks | ≥ 6 pt before each experience; more before each section | preset `entry_gap` 7, `section_gap` 10 |
| Strict alignment | All text left-aligned; only the dates (and locations) right-aligned via a tab. No justified or centred text | preset `summary_align: left` · audit |
| No orphan words | A bullet whose last line holds 1–3 words wastes a line: shorten it | Manual check of the PDF |

## Presets
| | `sheets` | `ats-modern` |
|---|---|---|
| Origin | SheetsResume.com template (dense, black) | These principles |
| Name / headings / body | 24 / body size / 10–10.5 pt | 16 / 11.5 / 10 pt |
| Colours | black only | #222 text + navy #1F3A5F accent |
| Side margins | 1.27 cm | 1.5 cm |
| Entry header | **Company** + dates / *Title* + location | **Title** + dates / *Company* + location |
| Skills heading | "COMPÉTENCES, LANGUES & CENTRES D'INTÉRÊT" | "COMPÉTENCES" |
| Audit score (example CV) | 83 | 96 |

## Where the sources disagree
- **Name size**: SheetsResume uses 28 pt; these principles say 14–16 pt. `ats-modern` follows the principles.
- **Margins vs one page**: 2 cm sides cost about 6 % of the width. Use 1.5 cm and shorten bullets before going below 10 pt.
- **Acronyms in a tech CV**: universal ones (API, SQL, HTML, CSS, JSON, UX…) don't need expanding (see the audit's `COMMON_ACRONYMS`). Domain- or school-specific ones do (CRM, RBAC, DEC, POO).
