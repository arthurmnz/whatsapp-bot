import os
from pathlib import Path
import re
from typing import Any

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor
from fpdf import FPDF

_LABELS: dict[str, dict[str, str]] = {
    "pt-BR": {
        "summary": "Resumo Profissional",
        "skills": "Competências Técnicas",
        "experience": "Experiência Profissional",
        "education": "Formação Acadêmica",
        "projects": "Projetos Relevantes",
        "certifications": "Certificações",
        "languages": "Idiomas",
    },
    "en": {
        "summary": "Professional Summary",
        "skills": "Technical Skills",
        "experience": "Professional Experience",
        "education": "Education",
        "projects": "Key Projects",
        "certifications": "Certifications",
        "languages": "Languages",
    },
}

_FONT_CANDIDATES: list[tuple[str, str, str]] = [
    (
        "/usr/share/fonts/TTF/DejaVuSans.ttf",
        "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/TTF/DejaVuSans-Oblique.ttf",
    ),
    (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf",
    ),
    (
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Italic.ttf",
    ),
]


def get_generated_cvs_base_dir() -> Path:
    raw = os.environ.get("GENERATED_CVS_DIR", "data/generated_cvs").strip() or "data/generated_cvs"
    base = Path(raw).resolve()
    base.mkdir(parents=True, exist_ok=True)
    return base


def get_user_cv_dir(user_id: int) -> Path:
    base = get_generated_cvs_base_dir()
    user_dir = (base / f"user_{int(user_id)}").resolve()
    if not user_dir.is_relative_to(base):
        raise ValueError("Caminho inválido para diretório do usuário.")
    user_dir.mkdir(parents=True, exist_ok=True)
    return user_dir


def resolve_safe_cv_path(user_id: int, file_path: str) -> Path:
    """Valida contra path traversal garantindo que o arquivo pertença ao diretório do usuário."""
    user_dir = get_user_cv_dir(user_id)
    candidate = Path(file_path).resolve()
    if not candidate.is_relative_to(user_dir):
        raise ValueError("Acesso negado ao caminho de arquivo solicitado.")
    return candidate


def _labels_for(lang: str) -> dict[str, str]:
    return _LABELS["en"] if str(lang).lower().startswith("en") else _LABELS["pt-BR"]


def _format_contact_line(contact: dict[str, Any]) -> str:
    parts = [
        str(contact.get("email") or "").strip(),
        str(contact.get("phone") or "").strip(),
        str(contact.get("location") or "").strip(),
        str(contact.get("linkedin") or "").strip(),
        str(contact.get("github") or "").strip(),
        str(contact.get("portfolio") or "").strip(),
    ]
    return " | ".join(p for p in parts if p)


def render_cv_markdown(tailored_data: dict[str, Any], target_language: str = "pt-BR") -> str:
    """Renderiza currículo estruturado em Markdown limpo ATS-friendly de coluna única."""
    labels = _labels_for(target_language)
    contact = tailored_data.get("contact") or {}
    name = str(contact.get("name") or "").strip() or "Candidato"
    headline = str(tailored_data.get("headline") or "").strip()
    contact_line = _format_contact_line(contact)

    lines: list[str] = [f"# {name}"]
    if headline:
        lines.append(f"**{headline}**")
    if contact_line:
        lines.append(contact_line)
    lines.append("")

    summary = str(tailored_data.get("summary") or "").strip()
    if summary:
        lines.append(f"## {labels['summary']}")
        lines.append(summary)
        lines.append("")

    skills = [str(s).strip() for s in (tailored_data.get("skills") or []) if str(s).strip()]
    if skills:
        lines.append(f"## {labels['skills']}")
        lines.append(" • ".join(skills))
        lines.append("")

    experiences = tailored_data.get("experiences") or []
    if experiences:
        lines.append(f"## {labels['experience']}")
        for exp in experiences:
            if not isinstance(exp, dict):
                continue
            role = str(exp.get("role") or "").strip()
            company = str(exp.get("company") or "").strip()
            period = str(exp.get("period") or "").strip()
            loc = str(exp.get("location") or "").strip()
            header_parts = [p for p in [role, company] if p]
            title_line = " — ".join(header_parts) if header_parts else "Experiência"
            meta = " | ".join(p for p in [period, loc] if p)
            lines.append(f"### {title_line}")
            if meta:
                lines.append(f"*{meta}*")
            for bullet in exp.get("bullets") or []:
                b_txt = str(bullet).strip()
                if b_txt:
                    lines.append(f"- {b_txt}")
            lines.append("")

    projects = tailored_data.get("projects") or []
    if projects:
        lines.append(f"## {labels['projects']}")
        for proj in projects:
            if not isinstance(proj, dict):
                continue
            pname = str(proj.get("name") or "").strip()
            pdesc = str(proj.get("description") or "").strip()
            ptechs = ", ".join(str(t) for t in (proj.get("technologies") or []) if str(t).strip())
            if pname or pdesc:
                suffix = f" ({ptechs})" if ptechs else ""
                lines.append(f"- **{pname or 'Projeto'}**: {pdesc}{suffix}")
        lines.append("")

    education = tailored_data.get("education") or []
    if education:
        lines.append(f"## {labels['education']}")
        for edu in education:
            if not isinstance(edu, dict):
                continue
            degree = str(edu.get("degree") or "").strip()
            inst = str(edu.get("institution") or "").strip()
            period = str(edu.get("period") or "").strip()
            edu_line = " — ".join(p for p in [degree, inst, period] if p)
            if edu_line:
                lines.append(f"- {edu_line}")
        lines.append("")

    certs = [str(c).strip() for c in (tailored_data.get("certifications") or []) if str(c).strip()]
    if certs:
        lines.append(f"## {labels['certifications']}")
        for cert in certs:
            lines.append(f"- {cert}")
        lines.append("")

    langs = tailored_data.get("languages") or []
    if langs:
        lines.append(f"## {labels['languages']}")
        for lg in langs:
            if isinstance(lg, dict):
                lname = str(lg.get("name") or lg.get("language") or "").strip()
                llevel = str(lg.get("level") or "").strip()
                if lname:
                    lines.append(f"- {lname}" + (f": {llevel}" if llevel else ""))
            elif str(lg).strip():
                lines.append(f"- {str(lg).strip()}")
        lines.append("")

    return "\n".join(lines).strip() + "\n"


def _add_docx_section_heading(doc: Document, title: str) -> None:
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(10)
    p.paragraph_format.space_after = Pt(4)
    p.paragraph_format.keep_with_next = True
    run = p.add_run(title.upper())
    run.bold = True
    run.font.size = Pt(10.5)
    run.font.color.rgb = RGBColor(15, 76, 129)

    p_pr = p._p.get_or_add_pPr()
    p_bdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), "6")
    bottom.set(qn("w:space"), "2")
    bottom.set(qn("w:color"), "CBD5E1")
    p_bdr.append(bottom)
    p_pr.append(p_bdr)


def render_cv_docx(
    tailored_data: dict[str, Any],
    output_path: Path,
    target_language: str = "pt-BR",
) -> Path:
    """Gera currículo ATS-friendly em formato DOCX (coluna única, tipografia limpa)."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    labels = _labels_for(target_language)
    doc = Document()

    for section in doc.sections:
        section.top_margin = Inches(0.55)
        section.bottom_margin = Inches(0.55)
        section.left_margin = Inches(0.65)
        section.right_margin = Inches(0.65)

    style = doc.styles["Normal"]
    style.font.name = "Calibri"
    style.font.size = Pt(10)
    style.font.color.rgb = RGBColor(30, 41, 59)

    contact = tailored_data.get("contact") or {}
    name = str(contact.get("name") or "").strip() or "Candidato"
    headline = str(tailored_data.get("headline") or "").strip()
    contact_line = _format_contact_line(contact)

    name_p = doc.add_paragraph()
    name_p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    name_p.paragraph_format.space_after = Pt(2)
    name_run = name_p.add_run(name)
    name_run.bold = True
    name_run.font.size = Pt(18)
    name_run.font.color.rgb = RGBColor(15, 23, 42)

    if headline:
        hl_p = doc.add_paragraph()
        hl_p.paragraph_format.space_after = Pt(2)
        hl_run = hl_p.add_run(headline)
        hl_run.bold = True
        hl_run.font.size = Pt(10.5)
        hl_run.font.color.rgb = RGBColor(51, 65, 85)

    if contact_line:
        ct_p = doc.add_paragraph()
        ct_p.paragraph_format.space_after = Pt(6)
        ct_run = ct_p.add_run(contact_line)
        ct_run.font.size = Pt(9)
        ct_run.font.color.rgb = RGBColor(71, 85, 105)

    summary = str(tailored_data.get("summary") or "").strip()
    if summary:
        _add_docx_section_heading(doc, labels["summary"])
        sp = doc.add_paragraph(summary)
        sp.paragraph_format.space_after = Pt(4)

    skills = [str(s).strip() for s in (tailored_data.get("skills") or []) if str(s).strip()]
    if skills:
        _add_docx_section_heading(doc, labels["skills"])
        skp = doc.add_paragraph(" • ".join(skills))
        skp.paragraph_format.space_after = Pt(4)

    experiences = tailored_data.get("experiences") or []
    if experiences:
        _add_docx_section_heading(doc, labels["experience"])
        for exp in experiences:
            if not isinstance(exp, dict):
                continue
            role = str(exp.get("role") or "").strip()
            company = str(exp.get("company") or "").strip()
            period = str(exp.get("period") or "").strip()
            loc = str(exp.get("location") or "").strip()

            ep = doc.add_paragraph()
            ep.paragraph_format.space_before = Pt(4)
            ep.paragraph_format.space_after = Pt(1)
            ep.paragraph_format.keep_with_next = True
            title_txt = " — ".join(p for p in [role, company] if p) or "Experiência"
            r_title = ep.add_run(title_txt)
            r_title.bold = True
            r_title.font.size = Pt(10.5)

            meta = " | ".join(p for p in [period, loc] if p)
            if meta:
                mp = doc.add_paragraph()
                mp.paragraph_format.space_after = Pt(2)
                mp.paragraph_format.keep_with_next = True
                r_meta = mp.add_run(meta)
                r_meta.italic = True
                r_meta.font.size = Pt(9)
                r_meta.font.color.rgb = RGBColor(100, 116, 139)

            for bullet in exp.get("bullets") or []:
                b_txt = str(bullet).strip()
                if b_txt:
                    bp = doc.add_paragraph(b_txt, style="List Bullet")
                    bp.paragraph_format.space_after = Pt(1.5)

    projects = tailored_data.get("projects") or []
    if projects:
        _add_docx_section_heading(doc, labels["projects"])
        for proj in projects:
            if not isinstance(proj, dict):
                continue
            pname = str(proj.get("name") or "").strip()
            pdesc = str(proj.get("description") or "").strip()
            ptechs = ", ".join(str(t) for t in (proj.get("technologies") or []) if str(t).strip())
            if pname or pdesc:
                pp = doc.add_paragraph(style="List Bullet")
                pp.paragraph_format.space_after = Pt(2)
                if pname:
                    rn = pp.add_run(f"{pname}: ")
                    rn.bold = True
                pp.add_run(pdesc + (f" ({ptechs})" if ptechs else ""))

    education = tailored_data.get("education") or []
    if education:
        _add_docx_section_heading(doc, labels["education"])
        for edu in education:
            if not isinstance(edu, dict):
                continue
            line = " — ".join(
                p
                for p in [
                    str(edu.get("degree") or "").strip(),
                    str(edu.get("institution") or "").strip(),
                    str(edu.get("period") or "").strip(),
                ]
                if p
            )
            if line:
                ep = doc.add_paragraph(line, style="List Bullet")
                ep.paragraph_format.space_after = Pt(2)

    certs = [str(c).strip() for c in (tailored_data.get("certifications") or []) if str(c).strip()]
    if certs:
        _add_docx_section_heading(doc, labels["certifications"])
        for cert in certs:
            doc.add_paragraph(cert, style="List Bullet")

    langs = tailored_data.get("languages") or []
    if langs:
        _add_docx_section_heading(doc, labels["languages"])
        for lg in langs:
            if isinstance(lg, dict):
                lname = str(lg.get("name") or lg.get("language") or "").strip()
                llevel = str(lg.get("level") or "").strip()
                if lname:
                    doc.add_paragraph(
                        lname + (f": {llevel}" if llevel else ""),
                        style="List Bullet",
                    )
            elif str(lg).strip():
                doc.add_paragraph(str(lg).strip(), style="List Bullet")

    doc.save(str(output_path))
    return output_path


def _configure_pdf_font(pdf: FPDF) -> tuple[str, bool]:
    """Configura fonte UTF-8 TrueType quando disponível, com fallback seguro para Helvetica."""
    for reg, bold, italic in _FONT_CANDIDATES:
        if os.path.exists(reg):
            pdf.add_font("CVSans", "", reg)
            pdf.add_font("CVSans", "B", bold if os.path.exists(bold) else reg)
            pdf.add_font("CVSans", "I", italic if os.path.exists(italic) else reg)
            return "CVSans", True
    return "Helvetica", False


def _sanitize_for_pdf(text: str, unicode_enabled: bool) -> str:
    if not text:
        return ""
    if unicode_enabled:
        return text
    replacements = {
        "—": "-",
        "–": "-",
        "•": "*",
        "▪": "-",
        "“": '"',
        "”": '"',
        "‘": "'",
        "’": "'",
        "…": "...",
        "\u00a0": " ",
    }
    out = text
    for src, dst in replacements.items():
        out = out.replace(src, dst)
    return out.encode("latin-1", errors="replace").decode("latin-1")


class _ATSResumePDF(FPDF):
    def __init__(self) -> None:
        super().__init__(orientation="P", unit="mm", format="A4")
        self.set_margins(15, 14, 15)
        self.set_auto_page_break(auto=True, margin=14)
        self.font_family_name, self.unicode_enabled = _configure_pdf_font(self)

    def safe(self, text: str) -> str:
        return _sanitize_for_pdf(text, self.unicode_enabled)

    def section_heading(self, title: str) -> None:
        self.ln(2.5)
        self.set_font(self.font_family_name, "B", 10.5)
        self.set_text_color(15, 76, 129)
        self.cell(0, 6, self.safe(title.upper()), new_x="LMARGIN", new_y="NEXT")
        y = self.get_y()
        self.set_draw_color(203, 213, 225)
        self.line(self.l_margin, y, self.w - self.r_margin, y)
        self.ln(2)
        self.set_text_color(30, 41, 59)


def render_cv_pdf(
    tailored_data: dict[str, Any],
    output_path: Path,
    target_language: str = "pt-BR",
) -> Path:
    """Gera currículo ATS-friendly em PDF (layout editorial coluna única, suporte UTF-8 PT-BR/EN)."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    labels = _labels_for(target_language)
    pdf = _ATSResumePDF()
    pdf.add_page()

    contact = tailored_data.get("contact") or {}
    name = str(contact.get("name") or "").strip() or "Candidato"
    headline = str(tailored_data.get("headline") or "").strip()
    contact_line = _format_contact_line(contact)

    pdf.set_font(pdf.font_family_name, "B", 17)
    pdf.set_text_color(15, 23, 42)
    pdf.multi_cell(pdf.epw, 7.5, pdf.safe(name), new_x="LMARGIN", new_y="NEXT")

    if headline:
        pdf.set_font(pdf.font_family_name, "B", 10.5)
        pdf.set_text_color(51, 65, 85)
        pdf.multi_cell(pdf.epw, 5.2, pdf.safe(headline), new_x="LMARGIN", new_y="NEXT")

    if contact_line:
        pdf.set_font(pdf.font_family_name, "", 8.8)
        pdf.set_text_color(71, 85, 105)
        pdf.multi_cell(pdf.epw, 4.8, pdf.safe(contact_line), new_x="LMARGIN", new_y="NEXT")

    summary = str(tailored_data.get("summary") or "").strip()
    if summary:
        pdf.section_heading(labels["summary"])
        pdf.set_font(pdf.font_family_name, "", 9.5)
        pdf.multi_cell(pdf.epw, 4.8, pdf.safe(summary), new_x="LMARGIN", new_y="NEXT")

    skills = [str(s).strip() for s in (tailored_data.get("skills") or []) if str(s).strip()]
    if skills:
        pdf.section_heading(labels["skills"])
        pdf.set_font(pdf.font_family_name, "", 9.3)
        sep = " • " if pdf.unicode_enabled else " | "
        pdf.multi_cell(pdf.epw, 4.8, pdf.safe(sep.join(skills)), new_x="LMARGIN", new_y="NEXT")

    experiences = tailored_data.get("experiences") or []
    if experiences:
        pdf.section_heading(labels["experience"])
        for exp in experiences:
            if not isinstance(exp, dict):
                continue
            role = str(exp.get("role") or "").strip()
            company = str(exp.get("company") or "").strip()
            period = str(exp.get("period") or "").strip()
            loc = str(exp.get("location") or "").strip()
            title_txt = " — ".join(p for p in [role, company] if p) or "Experiência"
            meta = " | ".join(p for p in [period, loc] if p)

            pdf.ln(1.2)
            pdf.set_font(pdf.font_family_name, "B", 10)
            pdf.set_text_color(15, 23, 42)
            pdf.multi_cell(pdf.epw, 5.0, pdf.safe(title_txt), new_x="LMARGIN", new_y="NEXT")

            if meta:
                pdf.set_font(pdf.font_family_name, "I", 8.8)
                pdf.set_text_color(100, 116, 139)
                pdf.multi_cell(pdf.epw, 4.4, pdf.safe(meta), new_x="LMARGIN", new_y="NEXT")

            pdf.set_font(pdf.font_family_name, "", 9.3)
            pdf.set_text_color(30, 41, 59)
            bullet_prefix = "• " if pdf.unicode_enabled else "- "
            for bullet in exp.get("bullets") or []:
                b_txt = str(bullet).strip()
                if b_txt:
                    pdf.set_x(pdf.l_margin + 2)
                    pdf.multi_cell(
                        pdf.epw - 2,
                        4.6,
                        pdf.safe(f"{bullet_prefix}{b_txt}"),
                        new_x="LMARGIN",
                        new_y="NEXT",
                    )

    projects = tailored_data.get("projects") or []
    if projects:
        pdf.section_heading(labels["projects"])
        pdf.set_font(pdf.font_family_name, "", 9.3)
        bullet_prefix = "• " if pdf.unicode_enabled else "- "
        for proj in projects:
            if not isinstance(proj, dict):
                continue
            pname = str(proj.get("name") or "").strip()
            pdesc = str(proj.get("description") or "").strip()
            ptechs = ", ".join(str(t) for t in (proj.get("technologies") or []) if str(t).strip())
            if pname or pdesc:
                line = f"{bullet_prefix}{pname}: {pdesc}" if pname else f"{bullet_prefix}{pdesc}"
                if ptechs:
                    line += f" ({ptechs})"
                pdf.multi_cell(pdf.epw, 4.6, pdf.safe(line), new_x="LMARGIN", new_y="NEXT")

    education = tailored_data.get("education") or []
    if education:
        pdf.section_heading(labels["education"])
        pdf.set_font(pdf.font_family_name, "", 9.3)
        bullet_prefix = "• " if pdf.unicode_enabled else "- "
        for edu in education:
            if not isinstance(edu, dict):
                continue
            line = " — ".join(
                p
                for p in [
                    str(edu.get("degree") or "").strip(),
                    str(edu.get("institution") or "").strip(),
                    str(edu.get("period") or "").strip(),
                ]
                if p
            )
            if line:
                pdf.multi_cell(pdf.epw, 4.6, pdf.safe(f"{bullet_prefix}{line}"), new_x="LMARGIN", new_y="NEXT")

    certs = [str(c).strip() for c in (tailored_data.get("certifications") or []) if str(c).strip()]
    if certs:
        pdf.section_heading(labels["certifications"])
        pdf.set_font(pdf.font_family_name, "", 9.3)
        bullet_prefix = "• " if pdf.unicode_enabled else "- "
        for cert in certs:
            pdf.multi_cell(pdf.epw, 4.6, pdf.safe(f"{bullet_prefix}{cert}"), new_x="LMARGIN", new_y="NEXT")

    langs = tailored_data.get("languages") or []
    if langs:
        pdf.section_heading(labels["languages"])
        pdf.set_font(pdf.font_family_name, "", 9.3)
        bullet_prefix = "• " if pdf.unicode_enabled else "- "
        for lg in langs:
            if isinstance(lg, dict):
                lname = str(lg.get("name") or lg.get("language") or "").strip()
                llevel = str(lg.get("level") or "").strip()
                if lname:
                    pdf.multi_cell(
                        pdf.epw,
                        4.6,
                        pdf.safe(f"{bullet_prefix}{lname}" + (f": {llevel}" if llevel else "")),
                        new_x="LMARGIN",
                        new_y="NEXT",
                    )
            elif str(lg).strip():
                pdf.multi_cell(
                    pdf.epw,
                    4.6,
                    pdf.safe(f"{bullet_prefix}{str(lg).strip()}"),
                    new_x="LMARGIN",
                    new_y="NEXT",
                )

    pdf.output(str(output_path))
    return output_path


def _strip_md_inline(text: str) -> str:
    cleaned = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    cleaned = re.sub(r"\*(.*?)\*", r"\1", cleaned)
    return cleaned.strip()


def render_markdown_to_pdf(markdown_text: str, output_path: Path) -> Path:
    """Regenera PDF limpo diretamente a partir de Markdown editado pelo usuário."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pdf = _ATSResumePDF()
    pdf.add_page()

    for raw_line in (markdown_text or "").splitlines():
        line = raw_line.strip()
        if not line:
            pdf.ln(1.8)
            continue
        if line.startswith("# "):
            pdf.set_font(pdf.font_family_name, "B", 16)
            pdf.set_text_color(15, 23, 42)
            pdf.multi_cell(pdf.epw, 7, pdf.safe(_strip_md_inline(line[2:])), new_x="LMARGIN", new_y="NEXT")
        elif line.startswith("## "):
            pdf.section_heading(_strip_md_inline(line[3:]))
        elif line.startswith("### "):
            pdf.ln(1)
            pdf.set_font(pdf.font_family_name, "B", 10)
            pdf.set_text_color(15, 23, 42)
            pdf.multi_cell(pdf.epw, 5, pdf.safe(_strip_md_inline(line[4:])), new_x="LMARGIN", new_y="NEXT")
        elif line.startswith(("- ", "* ")):
            pdf.set_font(pdf.font_family_name, "", 9.3)
            pdf.set_text_color(30, 41, 59)
            bullet_prefix = "• " if pdf.unicode_enabled else "- "
            pdf.set_x(pdf.l_margin + 2)
            pdf.multi_cell(
                pdf.epw - 2,
                4.6,
                pdf.safe(f"{bullet_prefix}{_strip_md_inline(line[2:])}"),
                new_x="LMARGIN",
                new_y="NEXT",
            )
        else:
            pdf.set_font(pdf.font_family_name, "", 9.5)
            pdf.set_text_color(30, 41, 59)
            pdf.multi_cell(pdf.epw, 4.8, pdf.safe(_strip_md_inline(line)), new_x="LMARGIN", new_y="NEXT")

    pdf.output(str(output_path))
    return output_path


def render_markdown_to_docx(markdown_text: str, output_path: Path) -> Path:
    """Regenera DOCX limpo diretamente a partir de Markdown editado pelo usuário."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc = Document()
    for section in doc.sections:
        section.top_margin = Inches(0.55)
        section.bottom_margin = Inches(0.55)
        section.left_margin = Inches(0.65)
        section.right_margin = Inches(0.65)

    style = doc.styles["Normal"]
    style.font.name = "Calibri"
    style.font.size = Pt(10)

    for raw_line in (markdown_text or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("# "):
            p = doc.add_paragraph()
            r = p.add_run(_strip_md_inline(line[2:]))
            r.bold = True
            r.font.size = Pt(18)
        elif line.startswith("## "):
            _add_docx_section_heading(doc, _strip_md_inline(line[3:]))
        elif line.startswith("### "):
            p = doc.add_paragraph()
            r = p.add_run(_strip_md_inline(line[4:]))
            r.bold = True
            r.font.size = Pt(10.5)
        elif line.startswith(("- ", "* ")):
            doc.add_paragraph(_strip_md_inline(line[2:]), style="List Bullet")
        else:
            doc.add_paragraph(_strip_md_inline(line))

    doc.save(str(output_path))
    return output_path
