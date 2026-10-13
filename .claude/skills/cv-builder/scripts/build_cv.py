"""Build a CV (.docx + .pdf) from a JSON file, in the style of the SheetsResume template.

Usage:
    python build_cv.py <cv.json> [--out-dir DIR] [--name FILE_STEM] [--lang fr|en] [--design PRESET] [--no-pdf]

Design comes from meta.design: {"preset": "sheets" | "ats-modern", ...overrides}.
See .claude/skills/cv-design for the presets and the design rules.

The JSON uses the schema of profile/master-profile.json. Text fields support
**bold**, *italic* and [label](url). Entries with "include": false are skipped.
When rendering in English, a field "<key>_en" is used instead of "<key>" if present.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

from docx import Document
from docx.enum.section import WD_ORIENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_TAB_ALIGNMENT
from docx.opc.constants import RELATIONSHIP_TYPE
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Inches, Pt, RGBColor

PAGES = {"A4": (Inches(8.27), Inches(11.69)), "Letter": (Inches(8.5), Inches(11))}

# Design presets. "sheets" = SheetsResume look (dense, black, big name).
# "ats-modern" = cv-design principles: 14-16 pt name, 11-12 pt headings, 10 pt body,
# 60-30-10 colours (white / dark-grey text / one muted accent), 1.5-2 cm margins,
# left-aligned text, bold job titles, airy spacing between entries.
DESIGN_PRESETS = {
    "sheets": {
        "font": "Arial", "body_size": 10.5, "name_size": 24, "headline_size": None, "heading_size": None,
        "margin_top_cm": 0.89, "margin_bottom_cm": 0.89, "margin_side_cm": 1.27,
        "text_color": "000000", "accent_color": "000000", "name_color": None,
        "entry_layout": "org_first", "entry_gap": 5, "section_gap": 7, "heading_gap_after": 2, "bullet_gap": 0.5,
        "line_spacing": 1.0, "summary_align": "justify", "link_underline": True, "skills_heading": "combined",
        "links_on_new_line": False, "rule_under_header": True, "date_format": "month_abbr",
    },
    "ats-modern": {
        "font": "Arial", "body_size": 10, "name_size": 16, "headline_size": 11, "heading_size": 11.5,
        "margin_top_cm": 1.2, "margin_bottom_cm": 1.0, "margin_side_cm": 1.5,
        "text_color": "222222", "accent_color": "1F3A5F", "name_color": "1F3A5F",
        "entry_layout": "title_first", "entry_gap": 7, "section_gap": 10, "heading_gap_after": 3, "bullet_gap": 1,
        "line_spacing": 1.05, "summary_align": "left", "link_underline": False, "skills_heading": "simple",
        "links_on_new_line": True, "rule_under_header": False, "date_format": "month_abbr",
    },
}
LEGACY_META_KEYS = {"font": "font", "font_size": "body_size", "name_size": "name_size", "links_on_new_line": "links_on_new_line"}


def resolve_design(meta: dict, preset_override: str | None = None) -> dict:
    """preset < legacy meta keys (font, font_size, name_size, links_on_new_line) < meta.design overrides.

    With --design, the preset's own values win over the legacy meta keys (a clean preview of the preset)."""
    overrides = dict(meta.get("design", {}))
    preset = preset_override or overrides.get("preset", "sheets")
    overrides.pop("preset", None)
    if preset not in DESIGN_PRESETS:
        raise SystemExit(f"Unknown design preset '{preset}'. Available: {', '.join(DESIGN_PRESETS)}")
    d = dict(DESIGN_PRESETS[preset], preset=preset)
    if not preset_override:
        for legacy, key in LEGACY_META_KEYS.items():
            if legacy in meta:
                d[key] = meta[legacy]
        d.update(overrides)
    return d


def rgb(hex_color: str) -> RGBColor:
    return RGBColor.from_string(hex_color.lstrip("#").upper())

LABELS = {
    "fr": {
        "summary": "PROFIL",
        "experience": "EXPÉRIENCES PROFESSIONNELLES",
        "education": "FORMATION",
        "projects": "PROJETS",
        "certifications": "Certifications",
        "skills_parts": {"certifications": "CERTIFICATIONS", "skills": "COMPÉTENCES", "languages": "LANGUES", "interests": "CENTRES D'INTÉRÊT"},
        "languages": "Langues",
        "interests": "Centres d'intérêt",
        "present": "Présent",
        "months": ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."],
    },
    "en": {
        "summary": "PROFILE",
        "experience": "WORK EXPERIENCE",
        "education": "EDUCATION",
        "projects": "PROJECTS",
        "certifications": "Certifications",
        "skills_parts": {"certifications": "CERTIFICATIONS", "skills": "SKILLS", "languages": "LANGUAGES", "interests": "INTERESTS"},
        "languages": "Languages",
        "interests": "Interests",
        "present": "Present",
        "months": ["Jan.", "Feb.", "Mar.", "Apr.", "May", "Jun.", "Jul.", "Aug.", "Sep.", "Oct.", "Nov.", "Dec."],
    },
}

INLINE = re.compile(r"\*\*(.+?)\*\*|\*(.+?)\*|\[(.+?)\]\((.+?)\)")


class CVBuilder:
    def __init__(self, data: dict, lang: str, design: str | None = None):
        self.data = data
        self.meta = data.get("meta", {})
        self.lang = lang
        self.L = LABELS[lang]
        self.D = resolve_design(self.meta, design)
        self.font = self.D["font"]
        self.size = Pt(self.D["body_size"])
        self.accent = self.D["accent_color"]
        self.doc = Document()
        self._setup_page()
        self._setup_styles()
        self.bullet_num_id = self._create_bullet_numbering()

    # ---------- helpers ----------
    def t(self, obj: dict, key: str, default=None):
        """Localised field: <key>_en wins in English when present."""
        if self.lang != "fr" and obj.get(f"{key}_{self.lang}") not in (None, "", []):
            return obj[f"{key}_{self.lang}"]
        return obj.get(key, default)

    def fmt_date(self, value: str | None) -> str:
        if not value:
            return ""
        if str(value).lower() in ("present", "présent", "now"):
            return self.L["present"]
        m = re.fullmatch(r"(\d{4})-(\d{1,2})", str(value))
        if m:
            if self.D.get("date_format") == "numeric":  # 01/2026: safest for ATS parsers (SmartRecruiters, Workday...)
                return f"{int(m.group(2)):02d}/{m.group(1)}"
            return f"{self.L['months'][int(m.group(2)) - 1]} {m.group(1)}"
        return str(value)

    def date_range(self, item: dict) -> str:
        start, end = self.fmt_date(item.get("start")), self.fmt_date(item.get("end") or item.get("date"))
        return f"{start} – {end}" if start and end else (start or end)

    @staticmethod
    def visible(items):
        return [i for i in (items or []) if not (isinstance(i, dict) and i.get("include") is False)]

    def _setup_page(self):
        sec = self.doc.sections[0]
        sec.orientation = WD_ORIENT.PORTRAIT
        sec.page_width, sec.page_height = PAGES[self.meta.get("page", "A4")]
        sec.top_margin, sec.bottom_margin = Cm(self.D["margin_top_cm"]), Cm(self.D["margin_bottom_cm"])
        sec.left_margin = sec.right_margin = Cm(self.D["margin_side_cm"])
        self.text_width = sec.page_width - 2 * sec.left_margin

    def _setup_styles(self):
        st = self.doc.styles["Normal"]
        st.font.name = self.font
        st.font.size = self.size
        st.font.color.rgb = rgb(self.D["text_color"])
        rfonts = st.element.get_or_add_rPr().get_or_add_rFonts()
        for attr in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
            rfonts.set(qn(attr), self.font)
        pf = st.paragraph_format
        pf.space_before = pf.space_after = Pt(0)
        pf.line_spacing = self.D["line_spacing"]

    def _create_bullet_numbering(self) -> int:
        """Level 0 '•' and level 1 'o', like the template."""
        numbering = self.doc.part.numbering_part.element
        abs_id = 90
        abstract = OxmlElement("w:abstractNum")
        abstract.set(qn("w:abstractNumId"), str(abs_id))
        for lvl, (char, font, left) in enumerate([("•", self.font, 360), ("o", "Courier New", 900)]):
            el = OxmlElement("w:lvl")
            el.set(qn("w:ilvl"), str(lvl))
            for tag, val in (("w:start", "1"), ("w:numFmt", "bullet"), ("w:lvlText", char), ("w:lvlJc", "left")):
                child = OxmlElement(tag)
                child.set(qn("w:val"), val)
                el.append(child)
            ppr = OxmlElement("w:pPr")
            ind = OxmlElement("w:ind")
            ind.set(qn("w:left"), str(left))
            ind.set(qn("w:hanging"), "270")
            ppr.append(ind)
            el.append(ppr)
            rpr = OxmlElement("w:rPr")
            rf = OxmlElement("w:rFonts")
            for attr in ("w:ascii", "w:hAnsi"):
                rf.set(qn(attr), font)
            rpr.append(rf)
            el.append(rpr)
            abstract.append(el)
        # abstractNum elements must precede num elements
        first_num = numbering.find(qn("w:num"))
        if first_num is not None:
            first_num.addprevious(abstract)
        else:
            numbering.append(abstract)
        num_id = 90
        num = OxmlElement("w:num")
        num.set(qn("w:numId"), str(num_id))
        ref = OxmlElement("w:abstractNumId")
        ref.set(qn("w:val"), str(abs_id))
        num.append(ref)
        numbering.append(num)
        return num_id

    def add_hyperlink(self, paragraph, text: str, url: str, bold=False, italic=False, size=None):
        r_id = paragraph.part.relate_to(url, RELATIONSHIP_TYPE.HYPERLINK, is_external=True)
        link = OxmlElement("w:hyperlink")
        link.set(qn("r:id"), r_id)
        run = OxmlElement("w:r")
        rpr = OxmlElement("w:rPr")
        props = [("w:color", self.D["text_color"])]
        if self.D["link_underline"]:
            props.append(("w:u", "single"))
        for tag, val in props:
            el = OxmlElement(tag)
            el.set(qn("w:val"), val)
            rpr.append(el)
        if bold:
            rpr.append(OxmlElement("w:b"))
        if italic:
            rpr.append(OxmlElement("w:i"))
        if size:
            sz = OxmlElement("w:sz")
            sz.set(qn("w:val"), str(int(size.pt * 2)))
            rpr.append(sz)
        run.append(rpr)
        t = OxmlElement("w:t")
        t.text = text
        t.set(qn("xml:space"), "preserve")
        run.append(t)
        link.append(run)
        paragraph._p.append(link)

    def add_rich(self, paragraph, text: str, bold=False, italic=False, size=None):
        """Append text with **bold**, *italic* and [label](url) markup."""
        pos = 0
        for m in INLINE.finditer(text):
            if m.start() > pos:
                self._run(paragraph, text[pos:m.start()], bold, italic, size)
            if m.group(1) is not None:
                self._run(paragraph, m.group(1), True, italic, size)
            elif m.group(2) is not None:
                self._run(paragraph, m.group(2), bold, True, size)
            else:
                self.add_hyperlink(paragraph, m.group(3), m.group(4), bold, italic, size)
            pos = m.end()
        if pos < len(text):
            self._run(paragraph, text[pos:], bold, italic, size)

    @staticmethod
    def _run(paragraph, text, bold=False, italic=False, size=None, color=None):
        run = paragraph.add_run(text)
        run.bold, run.italic = bold or None, italic or None
        if size:
            run.font.size = size
        if color:
            run.font.color.rgb = rgb(color)
        return run

    def bottom_border(self, paragraph):
        ppr = paragraph._p.get_or_add_pPr()
        bdr = OxmlElement("w:pBdr")
        bottom = OxmlElement("w:bottom")
        for k, v in (("w:val", "single"), ("w:sz", "6"), ("w:space", "1"), ("w:color", self.accent)):
            bottom.set(qn(k), v)
        bdr.append(bottom)
        ppr.append(bdr)

    def para(self, space_before=0, align=None):
        p = self.doc.add_paragraph()
        p.paragraph_format.space_before = Pt(space_before)
        if align is not None:
            p.alignment = align
        return p

    def two_sided(self, left: str, right: str, bold=False, italic=False, space_before=0):
        """Left text + right-aligned text on the same line (tab stop at the right margin)."""
        p = self.para(space_before)
        p.paragraph_format.tab_stops.add_tab_stop(self.text_width, WD_TAB_ALIGNMENT.RIGHT)
        p.paragraph_format.keep_with_next = True
        self.add_rich(p, left, bold, italic)
        if right:
            self._run(p, "\t" + right, bold, italic)
        return p

    def bullet(self, text: str, level=0):
        p = self.para()
        ppr = p._p.get_or_add_pPr()
        num_pr = OxmlElement("w:numPr")
        for tag, val in (("w:ilvl", str(level)), ("w:numId", str(self.bullet_num_id))):
            el = OxmlElement(tag)
            el.set(qn("w:val"), val)
            num_pr.append(el)
        ppr.insert(0, num_pr)
        p.paragraph_format.space_after = Pt(self.D["bullet_gap"])
        self.add_rich(p, text)

    def bullets(self, items):
        for b in items or []:
            if isinstance(b, dict):
                self.bullet(self.t(b, "text"), 0)
                for sub in self.t(b, "sub", []) or []:
                    self.bullet(sub, 1)
            else:
                self.bullet(b, 0)

    def heading(self, text: str):
        p = self.para(space_before=self.D["section_gap"])
        p.paragraph_format.space_after = Pt(self.D["heading_gap_after"])
        p.paragraph_format.keep_with_next = True
        size = Pt(self.D["heading_size"]) if self.D["heading_size"] else None
        self._run(p, text, bold=True, size=size, color=self.accent)
        self.bottom_border(p)

    def entry(self, org: str, title: str, dates: str, location: str, first: bool):
        """Two-line entry header. org_first: **Org** / *Title*. title_first: **Title** / *Org* (bold job title)."""
        gap = 0 if first else self.D["entry_gap"]
        if self.D["entry_layout"] == "title_first":
            self.two_sided(title, dates, bold=True, space_before=gap)
            self.two_sided(org, location, italic=True)
        else:
            self.two_sided(org, dates, bold=True, space_before=gap)
            self.two_sided(title, location, italic=True)

    # ---------- sections ----------
    def header(self):
        b = self.data["basics"]
        p = self.para()
        self._run(p, b["name"], bold=True, size=Pt(self.D["name_size"]), color=self.D["name_color"])
        headline = self.t(b, "headline")
        if headline:
            p = self.para()
            self._run(p, headline, italic=True, size=Pt(self.D["headline_size"] or self.size.pt + 2))
        p = self.para(space_before=2)
        contact_size = self.size
        parts = [x for x in (b.get("email"), b.get("phone"), self.t(b, "location")) if x]
        self._run(p, " | ".join(parts), size=contact_size)
        links_own_line = self.D["links_on_new_line"]
        for i, link in enumerate(b.get("links", [])):
            if i == 0 and links_own_line:
                p = self.para()
            else:
                self._run(p, " | ", size=contact_size)
            self.add_hyperlink(p, link["label"], link["url"], size=contact_size)
        last = p
        availability = self.t(b, "availability")
        if availability:
            last = self.para(space_before=1)
            self._run(last, availability, bold=True, italic=True)
        last.paragraph_format.space_after = Pt(2)
        if self.D["rule_under_header"]:
            self.bottom_border(last)

    def summary(self):
        text = self.t(self.data, "summary")
        if not text:
            return
        self.heading(self.L["summary"])
        p = self.para()
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY if self.D["summary_align"] == "justify" else WD_ALIGN_PARAGRAPH.LEFT
        self.add_rich(p, text)

    def experience(self):
        items = self.visible(self.data.get("experience"))
        if not items:
            return
        self.heading(self.L["experience"])
        for i, e in enumerate(items):
            self.entry(e["org"], self.t(e, "title"), self.date_range(e), self.t(e, "location", ""), i == 0)
            self.bullets(self.t(e, "bullets"))

    def education(self):
        items = self.visible(self.data.get("education"))
        if not items:
            return
        self.heading(self.L["education"])
        for i, e in enumerate(items):
            self.entry(e["org"], self.t(e, "degree"), self.date_range(e), self.t(e, "location", ""), i == 0)
            self.bullets(self.t(e, "details"))

    def projects(self):
        items = self.visible(self.data.get("projects"))
        if not items:
            return
        self.heading(self.L["projects"])
        for i, pr in enumerate(items):
            left = pr["name"]
            subtitle = self.t(pr, "subtitle")
            if subtitle:
                left += f" — {subtitle}"
            self.two_sided(left, self.date_range(pr), bold=True, space_before=0 if i == 0 else self.D["entry_gap"])
            if pr.get("url"):
                p = self.para()
                self.add_hyperlink(p, pr.get("url_label") or pr["url"], pr["url"], italic=True)
            self.bullets(self.t(pr, "bullets"))

    def skills(self):
        """'CERTIFICATIONS, SKILLS & INTERESTS' block: one bullet per line, 'Label: items'."""
        certs = self.visible(self.data.get("certifications"))
        skills = self.visible(self.data.get("skills"))
        langs = self.visible(self.data.get("languages"))
        interests = self.t(self.data, "interests") or []
        present = [k for k, v in (("certifications", certs), ("skills", skills), ("languages", langs), ("interests", interests)) if v]
        if not present:
            return
        names = [self.L["skills_parts"][k] for k in present]
        if self.D["skills_heading"] == "simple":  # one standard ATS heading
            title = self.L["skills_parts"]["skills"]
        else:
            title = names[0] if len(names) == 1 else ", ".join(names[:-1]) + " & " + names[-1]
        self.heading(title)
        colon = " :" if self.lang == "fr" else ":"  # French typography: space before the colon
        if certs:
            names = "; ".join(c if isinstance(c, str) else self.t(c, "name") for c in certs)
            self.bullet(f"**{self.L['certifications']}{colon}** {names}")
        for s in skills:
            self.bullet(f"**{self.t(s, 'label')}{colon}** " + ", ".join(s["items"]))
        if langs:
            text = ", ".join(f"{self.t(l, 'name')} – {self.t(l, 'level')}" for l in langs)
            self.bullet(f"**{self.L['languages']}{colon}** {text}")
        if interests:
            self.bullet(f"**{self.L['interests']}{colon}** " + ", ".join(interests))

    def build(self) -> Document:
        self.header()
        order = self.meta.get("section_order", ["summary", "experience", "education", "projects", "skills"])
        for name in order:
            getattr(self, name)()
        props = self.doc.core_properties
        props.title = f"CV — {self.data['basics']['name']}"
        props.author = self.data["basics"]["name"]
        return self.doc


def find_soffice() -> str | None:
    for c in (shutil.which("soffice"), r"C:\Program Files\LibreOffice\program\soffice.exe",
              r"C:\Program Files (x86)\LibreOffice\program\soffice.exe", "/Applications/LibreOffice.app/Contents/MacOS/soffice"):
        if c and Path(c).exists():
            return c
    return None


def to_pdf(docx_path: Path) -> Path | None:
    soffice = find_soffice()
    if not soffice:
        print("LibreOffice not found: PDF skipped (open the .docx in Word and export it).", file=sys.stderr)
        return None
    subprocess.run([soffice, "--headless", "--convert-to", "pdf", "--outdir", str(docx_path.parent), str(docx_path)],
                   check=True, capture_output=True, timeout=180)
    pdf = docx_path.with_suffix(".pdf")
    return pdf if pdf.exists() else None


def count_pdf_pages(pdf: Path) -> int:
    return len(re.findall(rb"/Type\s*/Page[^s]", pdf.read_bytes()))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("json", type=Path)
    ap.add_argument("--out-dir", type=Path)
    ap.add_argument("--name", help="output file stem (default: meta.filename)")
    ap.add_argument("--lang", choices=list(LABELS), help="default: meta.lang")
    ap.add_argument("--design", choices=list(DESIGN_PRESETS), help="override meta.design.preset")
    ap.add_argument("--no-pdf", action="store_true")
    args = ap.parse_args()

    data = json.loads(args.json.read_text(encoding="utf-8"))
    meta = data.get("meta", {})
    lang = args.lang or meta.get("lang", "fr")
    out_dir = args.out_dir or args.json.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = args.name or meta.get("filename") or data["basics"]["name"].upper().replace(" ", "_") + "_CV"

    docx_path = out_dir / f"{stem}.docx"
    builder = CVBuilder(data, lang, args.design)
    builder.build().save(docx_path)
    print(f"DOCX: {docx_path}  (design: {builder.D['preset']})")

    if not args.no_pdf:
        pdf = to_pdf(docx_path)
        if pdf:
            pages = count_pdf_pages(pdf)
            print(f"PDF:  {pdf}  ({pages} page{'s' if pages != 1 else ''})")
            if pages > 1:
                print("WARNING: more than one page. Cut bullets or lower meta.font_size (min 10).", file=sys.stderr)


if __name__ == "__main__":
    main()
