"""Audit a CV (.docx, plus the .pdf next to it) against the cv-design rules: ATS parsing, typography, colour, spacing.

Usage:
    python audit_cv.py <cv.docx> [--pdf cv.pdf] [--keywords "React,TypeScript,Docker"] [--lang fr|en] [--cv-json cv.json]

Names of organisations/projects found in cv.json (default: cv.json next to the .docx) are not
treated as acronyms (school or company names...).

Prints a Markdown report: one line per check with PASS / WARN / FAIL, then a score.
Rules: .claude/skills/cv-design/references/principles.md
"""
from __future__ import annotations

import argparse
import colorsys
import json
import re
import sys
from collections import Counter
from pathlib import Path

from docx import Document
from docx.oxml.ns import qn

ALLOWED_FONTS = {"Arial", "Calibri", "Garamond", "EB Garamond", "Georgia", "Inter", "Roboto", "Open Sans", "Helvetica"}
STANDARD_HEADINGS = {
    "fr": {"PROFIL", "RÉSUMÉ", "EXPÉRIENCE", "EXPÉRIENCES", "EXPÉRIENCES PROFESSIONNELLES", "EXPÉRIENCE PROFESSIONNELLE",
           "FORMATION", "FORMATIONS", "ÉDUCATION", "COMPÉTENCES", "COMPÉTENCES TECHNIQUES", "PROJETS", "LANGUES",
           "CENTRES D'INTÉRÊT", "CERTIFICATIONS"},
    "en": {"PROFILE", "SUMMARY", "EXPERIENCE", "WORK EXPERIENCE", "PROFESSIONAL EXPERIENCE", "EDUCATION", "SKILLS",
           "TECHNICAL SKILLS", "PROJECTS", "LANGUAGES", "INTERESTS", "CERTIFICATIONS"},
}
# Acronyms any tech recruiter / ATS knows: no need to spell them out.
COMMON_ACRONYMS = {"API", "REST", "SQL", "HTML", "HTML5", "CSS", "CSS3", "PHP", "CSV", "JSON", "PDF", "IT", "UI", "UX",
                   "CV", "IA", "AI", "ES6", "HTTP", "IP", "CMS", "SaaS", "GPT", "CI", "CD", "B2", "C1", "C2", "B1",
                   "A1", "A2", "MERN", "ORM", "JWT", "AWS", "GCP", "RSS", "GSAP", "LLM", "ATS", "DOCX"}

results: list[tuple[str, str, str]] = []


def add(status: str, check: str, detail: str):
    results.append((status, check, detail))


def hex_to_hsv(h: str):
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    return colorsys.rgb_to_hsv(r, g, b)


def luminance(h: str) -> float:
    def ch(c):
        c = c / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)


def contrast_on_white(h: str) -> float:
    return 1.05 / (luminance(h) + 0.05)


def run_props(run, style_font, style_size, style_color):
    rpr = run._r.rPr
    font = run.font.name or style_font
    size = run.font.size.pt if run.font.size else style_size
    color = None
    if rpr is not None and rpr.find(qn("w:color")) is not None:
        color = rpr.find(qn("w:color")).get(qn("w:val"))
    color = (color or style_color or "000000").upper()
    hidden = rpr is not None and rpr.find(qn("w:vanish")) is not None
    return font, size, color, hidden


def proper_nouns(cv_json: Path | None) -> set[str]:
    if not cv_json or not cv_json.exists():
        return set()
    data = json.loads(cv_json.read_text(encoding="utf-8"))
    words = set()
    for section in ("experience", "education", "projects"):
        for item in data.get(section, []):
            for key in ("org", "name"):
                words.update(re.findall(r"[A-Za-z0-9]+", item.get(key, "") or ""))
    return words


def audit_docx(path: Path, lang: str, keywords: list[str], ignore: set[str]):
    doc = Document(str(path))
    body = doc.element.body
    normal = doc.styles["Normal"]
    style_font = normal.font.name or "?"
    style_size = normal.font.size.pt if normal.font.size else 11.0
    style_color = str(normal.font.color.rgb) if normal.font.color and normal.font.color.rgb else "000000"

    # ---------- ATS structure ----------
    n_tables = len(doc.tables)
    add("PASS" if n_tables == 0 else "FAIL", "No tables", f"{n_tables} table(s)" if n_tables else "none")
    xml = body.xml
    graphics = sum(xml.count(t) for t in ("<w:drawing", "<w:pict", "<v:shape", "<wps:txbx", "<w:txbxContent"))
    add("PASS" if graphics == 0 else "FAIL", "No images / icons / text boxes", f"{graphics} graphic element(s)" if graphics else "none")
    cols = [c.get(qn("w:num")) for c in body.iter(qn("w:cols")) if c.get(qn("w:num"))]
    multi = [c for c in cols if int(c) > 1]
    add("PASS" if not multi else "FAIL", "Single column", f"{multi[0]} columns" if multi else "1 column")
    hf_text = []
    for sec in doc.sections:
        for part in (sec.header, sec.footer, sec.first_page_header, sec.first_page_footer):
            try:
                t = " ".join(p.text for p in part.paragraphs).strip()
            except Exception:
                t = ""
            if t:
                hf_text.append(t[:40])
    add("PASS" if not hf_text else "FAIL", "Nothing in header/footer", "; ".join(hf_text) if hf_text else "empty")

    # ---------- collect runs ----------
    fonts, sizes_by_chars, colors = Counter(), Counter(), Counter()
    hidden_runs, underlined, justified, centered = 0, 0, [], []
    paragraphs = [p for p in doc.paragraphs if p.text.strip()]
    for p in paragraphs:
        if p.alignment is not None and int(p.alignment) == 3:  # JUSTIFY
            justified.append(p.text[:40])
        if p.alignment is not None and int(p.alignment) == 1:  # CENTER
            centered.append(p.text[:40])
        for r in p.runs:
            if not r.text.strip():
                continue
            font, size, color, hidden = run_props(r, style_font, style_size, style_color)
            fonts[font] += len(r.text)
            sizes_by_chars[size] += len(r.text)
            colors[color] += len(r.text)
            hidden_runs += hidden or color in ("FFFFFF",)
            underlined += bool(r.underline)
    for rf in body.iter(qn("w:rFonts")):
        f = rf.get(qn("w:ascii"))
        if f:
            fonts.setdefault(f, 0)

    # ---------- typography ----------
    bad_fonts = [f for f in fonts if f not in ALLOWED_FONTS]
    add("PASS" if not bad_fonts else "WARN", "Standard fonts", ", ".join(fonts) + (f" (non-standard: {', '.join(bad_fonts)})" if bad_fonts else ""))
    body_size = sizes_by_chars.most_common(1)[0][0] if sizes_by_chars else style_size
    add("PASS" if 10 <= body_size <= 11 else ("FAIL" if body_size < 9.5 else "WARN"), "Body text 10 pt (10–11)", f"{body_size:g} pt")

    name_par = paragraphs[0] if paragraphs else None
    name_size = max((r.font.size.pt for r in name_par.runs if r.font.size), default=style_size) if name_par else 0
    add("PASS" if 14 <= name_size <= 16 else "WARN", "Name 14–16 pt", f"{name_size:g} pt" + (" (larger than the rule: OK for the 'sheets' look, not for 'ats-modern')" if name_size > 16 else ""))

    headings = [p for p in paragraphs if p._p.pPr is not None and p._p.pPr.find(qn("w:pBdr")) is not None and p.text.isupper()]
    h_sizes = {max((r.font.size.pt for r in h.runs if r.font.size), default=style_size) for h in headings}
    ok_h = all(11 <= s <= 12 for s in h_sizes)
    add("PASS" if ok_h else "WARN", "Section headings 11–12 pt", ", ".join(f"{s:g} pt" for s in sorted(h_sizes)) or "no headings found")
    std = STANDARD_HEADINGS[lang]
    odd = [h.text.strip() for h in headings if h.text.strip().upper() not in std]
    add("PASS" if not odd else "WARN", "Standard section headings", "non-standard: " + " / ".join(odd) if odd else ", ".join(h.text.strip() for h in headings))

    # ---------- colour (60-30-10) ----------
    non_gray = {c for c in colors if hex_to_hsv(c)[1] > 0.15}
    loud = [c for c in non_gray if hex_to_hsv(c)[1] > 0.75 and hex_to_hsv(c)[2] > 0.75]
    add("PASS" if not loud else "FAIL", "No loud / fluorescent colours", ", ".join("#" + c for c in loud) if loud else "none")
    add("PASS" if len(non_gray) <= 1 else "WARN", "One accent colour at most", ", ".join("#" + c for c in non_gray) or "monochrome")
    main_text = colors.most_common(1)[0][0] if colors else "000000"
    ratio = contrast_on_white(main_text)
    add("PASS" if ratio >= 7 else ("WARN" if ratio >= 4.5 else "FAIL"), "Text contrast on white ≥ 7:1", f"#{main_text} → {ratio:.1f}:1")
    total = sum(colors.values()) or 1
    accent_share = sum(colors[c] for c in non_gray) / total
    add("PASS" if accent_share <= 0.15 else "WARN", "Accent ≈ 10 % of the text", f"{accent_share:.0%} of characters in accent colour")
    add("PASS" if hidden_runs == 0 else "FAIL", "No hidden / white text (keyword stuffing)", f"{hidden_runs} hidden run(s)" if hidden_runs else "none")

    # ---------- space & alignment ----------
    sec = doc.sections[0]
    side = min(sec.left_margin.cm, sec.right_margin.cm)
    add("PASS" if 1.49 <= side <= 2.51 else "WARN", "Side margins 1.5–2 cm", f"{sec.left_margin.cm:.2f} / {sec.right_margin.cm:.2f} cm")
    add("PASS" if not justified and not centered else "WARN", "Text left-aligned",
        ("justified: " + " / ".join(justified) if justified else "") + (" centred: " + " / ".join(centered) if centered else "") or "all left (dates right-aligned)")
    entry_pars = [p for p in paragraphs if "\t" in p.text and any(r.bold for r in p.runs)]
    gaps = [p.paragraph_format.space_before.pt for p in entry_pars if p.paragraph_format.space_before is not None and p.paragraph_format.space_before.pt > 0]
    min_gap = min(gaps) if gaps else 0
    add("PASS" if min_gap >= 6 else "WARN", "Space between entries ≥ 6 pt", f"{min_gap:g} pt")
    add("PASS" if underlined == 0 else "WARN", "No underline for emphasis", f"{underlined} underlined run(s)" if underlined else "none (bold only)")

    # ---------- content-level ATS ----------
    heading_ids = {id(h._p) for h in headings}
    text = "\n".join(p.text for p in paragraphs if id(p._p) not in heading_ids)
    acronyms = sorted(set(re.findall(r"\b[A-Z][A-Za-z0-9]*[A-Z][A-Za-z0-9]*\b", text)))
    acronyms = [a for a in acronyms if re.fullmatch(r"[A-Z0-9]{2,6}|SaaS", a) and a not in COMMON_ACRONYMS and a not in ignore]
    unexplained = [a for a in acronyms if not re.search(r"\w[\w\s'’-]{3,}\(\s*" + re.escape(a) + r"\s*\)", text)]
    add("PASS" if not unexplained else "WARN", "Acronyms spelled out on first use",
        "consider expanding: " + ", ".join(unexplained) if unexplained else "ok")
    if keywords:
        missing = [k for k in keywords if k.lower() not in text.lower()]
        add("PASS" if not missing else "WARN", "Job keywords present", "missing: " + ", ".join(missing) if missing else f"all {len(keywords)} present")

    # Orphan words: a bullet whose last line holds 1–2 words cannot be measured from the DOCX; checked in the PDF review.
    return text


def audit_pdf(pdf: Path):
    data = pdf.read_bytes()
    pages = len(re.findall(rb"/Type\s*/Page[^s]", data))
    add("PASS" if pages == 1 else "WARN", "One page (student profile)", f"{pages} page(s)")
    fonts = set(re.findall(rb"/BaseFont\s*/([A-Za-z0-9+\-]+)", data))
    embedded = bool(re.search(rb"/FontFile2?|/FontFile3", data))
    add("PASS" if fonts and embedded else "FAIL", "Selectable text, embedded fonts", ", ".join(f.decode().split("+")[-1] for f in fonts) or "no fonts: scanned/image PDF?")
    images = len(re.findall(rb"/Subtype\s*/Image", data))
    add("PASS" if images == 0 else "FAIL", "PDF has no images", f"{images} image(s)" if images else "none")
    ok_name = re.fullmatch(r"[A-Z0-9_\-]+_CV(_[A-Za-z0-9_\-]+)?\.pdf", pdf.name, re.I) is not None
    add("PASS" if ok_name else "WARN", "Professional file name", pdf.name)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("docx", type=Path)
    ap.add_argument("--pdf", type=Path, help="default: same name as the .docx")
    ap.add_argument("--keywords", default="", help="comma-separated job keywords to look for")
    ap.add_argument("--lang", choices=["fr", "en"], default="fr")
    ap.add_argument("--cv-json", type=Path, help="default: cv.json next to the .docx")
    args = ap.parse_args()

    ignore = proper_nouns(args.cv_json or args.docx.parent / "cv.json")
    audit_docx(args.docx, args.lang, [k.strip() for k in args.keywords.split(",") if k.strip()], ignore)
    pdf = args.pdf or args.docx.with_suffix(".pdf")
    if pdf.exists():
        audit_pdf(pdf)
    else:
        add("WARN", "PDF present", "no PDF found: send a PDF unless the offer asks for .docx")

    icon = {"PASS": "✅", "WARN": "⚠️", "FAIL": "⛔"}
    print(f"# Design audit: {args.docx.name}\n")
    print("| | Check | Detail |\n|---|---|---|")
    for status, check, detail in results:
        print(f"| {icon[status]} | {check} | {detail} |")
    c = Counter(s for s, _, _ in results)
    score = round(100 * (c["PASS"] + 0.5 * c["WARN"]) / len(results))
    print(f"\n**Score: {score}/100** · {c['PASS']} pass · {c['WARN']} warn · {c['FAIL']} fail")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
