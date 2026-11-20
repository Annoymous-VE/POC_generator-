"""
Deterministic DOCX Document Renderer for Universal POC Template System.

Translates validated DocumentContent and tokenized DesignProfile specifications
into a professional, publication-quality DOCX document using python-docx.
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import docx
from docx.enum.table import WD_ALIGN_VERTICAL, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn
from docx.shared import Inches, Pt, RGBColor

from app.schemas.template.content_block import (
    BulletedListBlock,
    CalloutBlock,
    CodeBlock,
    ContentBlock,
    DiagramBlock,
    NumberedListBlock,
    ParagraphBlock,
    SubsectionBlock,
    TableBlock,
)
from app.schemas.template.design_system import DesignProfile, TypographyToken
from app.schemas.template.section_content import DocumentContent, SectionContent
from app.services.templates.design_loader import DesignSystemLoader


def hex_to_rgb(hex_code: str) -> RGBColor:
    """Converts a hex color (#RRGGBB) to a docx RGBColor."""
    clean = hex_code.lstrip("#")
    if len(clean) == 3:
        clean = "".join(c * 2 for c in clean)
    r = int(clean[0:2], 16)
    g = int(clean[2:4], 16)
    b = int(clean[4:6], 16)
    return RGBColor(r, g, b)


def clean_hex(hex_code: str) -> str:
    """Returns uppercase 6-char hex string without leading #."""
    clean = hex_code.lstrip("#")
    if len(clean) == 3:
        clean = "".join(c * 2 for c in clean)
    return clean.upper()


class DocxDocumentRenderer:
    """
    Renders structured DocumentContent to DOCX deterministically matching design tokens.
    """

    def __init__(self, design_loader: Optional[DesignSystemLoader] = None) -> None:
        self.design_loader = design_loader or DesignSystemLoader()

    def render(
        self,
        content: DocumentContent,
        output_path: Optional[Union[str, Path]] = None,
    ) -> bytes:
        """
        Renders DocumentContent into a DOCX binary stream.

        Args:
            content: Validated DocumentContent.
            output_path: Optional file path to persist the document.

        Returns:
            bytes: Binary content of the generated .docx file.
        """
        profile = self.design_loader.get_profile(content.design_profile)
        doc = docx.Document()

        # 1. Configure Page Layout & Margins
        section = doc.sections[0]
        if profile.page_layout.page_size == "A4":
            section.page_width = Inches(8.27)
            section.page_height = Inches(11.69)
        else:
            section.page_width = Inches(8.5)
            section.page_height = Inches(11.0)

        section.top_margin = Inches(profile.page_layout.top_margin_in)
        section.bottom_margin = Inches(profile.page_layout.bottom_margin_in)
        section.left_margin = Inches(profile.page_layout.left_margin_in)
        section.right_margin = Inches(profile.page_layout.right_margin_in)

        # 2. Render Cover Page
        self._render_cover_page(doc, content, profile)

        # 3. Add Page Break and Configure Running Headers & Footers
        doc.add_page_break()
        self._setup_header_footer(doc, content, profile)

        # 4. Render Body Sections in Blueprint Sequence
        for sec in content.sections:
            self._render_section(doc, sec, profile)

        # 5. Output to buffer or file
        buffer = io.BytesIO()
        doc.save(buffer)
        binary_data = buffer.getvalue()

        if output_path:
            p = Path(output_path)
            p.parent.mkdir(parents=True, exist_ok=True)
            with open(p, "wb") as f:
                f.write(binary_data)

        return binary_data

    def _render_cover_page(
        self,
        doc: docx.Document,
        content: DocumentContent,
        profile: DesignProfile,
    ) -> None:
        """Renders the formal cover page using profile cover typography."""
        # Top spacing
        p_space = doc.add_paragraph()
        p_space.paragraph_format.space_before = Pt(72)

        # Cover Title
        p_title = doc.add_paragraph()
        p_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
        title_token = profile.typography.get(
            "cover_title",
            TypographyToken(font="Aptos Display", size_pt=26.0, color="#17365D", weight="bold"),
        )
        run_title = p_title.add_run(content.title)
        self._apply_run_token(run_title, title_token)
        p_title.paragraph_format.space_after = Pt(title_token.space_after_pt or 14.0)

        # Cover Subtitle
        if content.subtitle:
            p_sub = doc.add_paragraph()
            p_sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
            sub_token = profile.typography.get(
                "cover_subtitle",
                TypographyToken(font="Aptos", size_pt=13.0, color="#2F75B5", weight="regular"),
            )
            run_sub = p_sub.add_run(content.subtitle)
            self._apply_run_token(run_sub, sub_token)
            p_sub.paragraph_format.space_after = Pt(48)

        # Metadata Card (Table)
        meta = content.metadata
        rows_data = []
        if meta.get("client_name"):
            rows_data.append(("Prepared For:", str(meta["client_name"])))
        if meta.get("prepared_by"):
            rows_data.append(("Prepared By:", str(meta["prepared_by"])))
        if meta.get("version"):
            rows_data.append(("Version:", str(meta["version"])))
        if meta.get("date"):
            rows_data.append(("Date:", str(meta["date"])))

        if rows_data:
            table = doc.add_table(rows=len(rows_data), cols=2)
            table.alignment = WD_TABLE_ALIGNMENT.CENTER
            for idx, (label, val) in enumerate(rows_data):
                row = table.rows[idx]
                r_lbl = row.cells[0].paragraphs[0].add_run(label)
                r_lbl.font.name = "Aptos"
                r_lbl.font.size = Pt(9.5)
                r_lbl.font.bold = True
                r_lbl.font.color.rgb = hex_to_rgb(profile.palette.primary_navy)

                r_val = row.cells[1].paragraphs[0].add_run(val)
                r_val.font.name = "Aptos"
                r_val.font.size = Pt(9.5)
                r_val.font.color.rgb = hex_to_rgb(profile.palette.body_text)

    def _setup_header_footer(
        self,
        doc: docx.Document,
        content: DocumentContent,
        profile: DesignProfile,
    ) -> None:
        """Sets up running headers and footers for body sections."""
        section = doc.sections[0]
        # Running Header
        header = section.header
        p_head = header.paragraphs[0]
        p_head.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        r_head = p_head.add_run(f"Proof of Concept | {content.title}")
        r_head.font.name = "Aptos"
        r_head.font.size = Pt(8.0)
        r_head.font.color.rgb = hex_to_rgb(profile.palette.muted_text)

        # Running Footer
        footer = section.footer
        p_foot = footer.paragraphs[0]
        p_foot.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r_foot = p_foot.add_run("Commercial in Confidence — For Client Evaluation Only")
        r_foot.font.name = "Aptos"
        r_foot.font.size = Pt(8.0)
        r_foot.font.color.rgb = hex_to_rgb(profile.palette.muted_text)

    def _render_section(
        self,
        doc: docx.Document,
        sec: SectionContent,
        profile: DesignProfile,
    ) -> None:
        """Renders an individual section and its content blocks."""
        # Section Heading 1
        p_heading = doc.add_paragraph()
        h1_token = profile.typography.get(
            "heading_1",
            TypographyToken(
                font="Aptos", size_pt=16.0, color="#17365D", weight="bold", space_before_pt=18.0, space_after_pt=8.0
            ),
        )
        run_h1 = p_heading.add_run(f"{sec.order}. {sec.title}")
        self._apply_run_token(run_h1, h1_token)
        p_heading.paragraph_format.space_before = Pt(h1_token.space_before_pt or 18.0)
        p_heading.paragraph_format.space_after = Pt(h1_token.space_after_pt or 8.0)
        p_heading.paragraph_format.keep_with_next = True

        # Render Content Blocks
        for block in sec.blocks:
            self._render_block(doc, block, profile)

    def _render_block(
        self,
        doc: docx.Document,
        block: ContentBlock,
        profile: DesignProfile,
    ) -> None:
        """Dispatches block rendering by concrete block type."""
        if isinstance(block, ParagraphBlock):
            self._render_paragraph(doc, block, profile)
        elif isinstance(block, BulletedListBlock):
            self._render_bullet_list(doc, block, profile)
        elif isinstance(block, NumberedListBlock):
            self._render_numbered_list(doc, block, profile)
        elif isinstance(block, TableBlock):
            self._render_table(doc, block, profile)
        elif isinstance(block, DiagramBlock):
            self._render_diagram(doc, block, profile)
        elif isinstance(block, CalloutBlock):
            self._render_callout(doc, block, profile)
        elif isinstance(block, CodeBlock):
            self._render_code(doc, block, profile)
        elif isinstance(block, SubsectionBlock):
            self._render_subsection(doc, block, profile)

    def _render_paragraph(
        self,
        doc: docx.Document,
        block: ParagraphBlock,
        profile: DesignProfile,
    ) -> None:
        token = profile.typography.get(
            "body_default",
            TypographyToken(font="Aptos", size_pt=10.0, color="#202B36", weight="regular", space_after_pt=6.0),
        )
        p = doc.add_paragraph()
        run = p.add_run(block.text)
        self._apply_run_token(run, token)
        p.paragraph_format.space_after = Pt(token.space_after_pt or 6.0)
        p.paragraph_format.line_spacing = token.line_spacing or 1.15

    def _render_bullet_list(
        self,
        doc: docx.Document,
        block: BulletedListBlock,
        profile: DesignProfile,
    ) -> None:
        token = profile.typography.get(
            "bullet_list",
            TypographyToken(font="Aptos", size_pt=10.0, color="#202B36", weight="regular"),
        )
        for item in block.items:
            p = doc.add_paragraph(style="List Bullet")
            run = p.add_run(item)
            self._apply_run_token(run, token)
            p.paragraph_format.space_after = Pt(3.0)
            p.paragraph_format.line_spacing = 1.15

    def _render_numbered_list(
        self,
        doc: docx.Document,
        block: NumberedListBlock,
        profile: DesignProfile,
    ) -> None:
        token = profile.typography.get(
            "numbered_list",
            TypographyToken(font="Aptos", size_pt=10.0, color="#202B36", weight="regular"),
        )
        for item in block.items:
            p = doc.add_paragraph(style="List Number")
            run = p.add_run(item)
            self._apply_run_token(run, token)
            p.paragraph_format.space_after = Pt(3.0)
            p.paragraph_format.line_spacing = 1.15

    def _render_table(
        self,
        doc: docx.Document,
        block: TableBlock,
        profile: DesignProfile,
    ) -> None:
        tbl_style = profile.table_styles.get("standard_table")
        num_rows = len(block.rows) + 1
        num_cols = len(block.columns)

        table = doc.add_table(rows=num_rows, cols=num_cols)
        table.alignment = WD_TABLE_ALIGNMENT.CENTER

        header_bg_hex = clean_hex(tbl_style.header_background_color if tbl_style else "#17365D")
        header_text_color = hex_to_rgb(tbl_style.header_text_color if tbl_style else "#FFFFFF")
        alt_row_hex = clean_hex(tbl_style.alternating_row_color if tbl_style and tbl_style.alternating_row_color else "#F9FAFB")

        # Header Row
        header_row = table.rows[0]
        for col_idx, col_name in enumerate(block.columns):
            cell = header_row.cells[col_idx]
            self._set_cell_background(cell, header_bg_hex)
            self._set_cell_padding(cell, 6.0)
            p = cell.paragraphs[0]
            p.paragraph_format.space_after = Pt(2.0)
            run = p.add_run(col_name)
            run.font.name = "Aptos"
            run.font.size = Pt(9.0)
            run.font.bold = True
            run.font.color.rgb = header_text_color

        # Data Rows
        for r_idx, row_data in enumerate(block.rows):
            row = table.rows[r_idx + 1]
            is_alt = (r_idx % 2 == 1)
            for c_idx, cell_value in enumerate(row_data):
                cell = row.cells[c_idx]
                if is_alt:
                    self._set_cell_background(cell, alt_row_hex)
                self._set_cell_padding(cell, 5.0)
                p = cell.paragraphs[0]
                p.paragraph_format.space_after = Pt(2.0)
                run = p.add_run(str(cell_value))
                run.font.name = "Aptos"
                run.font.size = Pt(9.0)
                run.font.color.rgb = hex_to_rgb(profile.palette.body_text)

        # Spacing after table
        p_after = doc.add_paragraph()
        p_after.paragraph_format.space_before = Pt(4.0)
        p_after.paragraph_format.space_after = Pt(6.0)

    def _render_diagram(
        self,
        doc: docx.Document,
        block: DiagramBlock,
        profile: DesignProfile,
    ) -> None:
        table = doc.add_table(rows=1, cols=1)
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        cell = table.rows[0].cells[0]

        # Light border and pale background
        border_hex = clean_hex(profile.palette.secondary_blue)
        self._set_cell_background(cell, "F8FAFC")
        self._set_cell_padding(cell, 10.0)

        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run_badge = p.add_run(f"[{block.diagram_type.upper()} DIAGRAM]\n")
        run_badge.font.name = "Aptos"
        run_badge.font.size = Pt(9.0)
        run_badge.font.bold = True
        run_badge.font.color.rgb = hex_to_rgb(profile.palette.teal_accent)

        run_desc = p.add_run(f"{block.description}\n")
        run_desc.font.name = "Aptos"
        run_desc.font.size = Pt(9.5)
        run_desc.font.color.rgb = hex_to_rgb(profile.palette.body_text)

        if block.mermaid_code:
            p_code = cell.add_paragraph()
            p_code.alignment = WD_ALIGN_PARAGRAPH.LEFT
            run_m = p_code.add_run(f"\n{block.mermaid_code}")
            run_m.font.name = "Consolas"
            run_m.font.size = Pt(8.0)
            run_m.font.color.rgb = hex_to_rgb("#475569")

        doc.add_paragraph().paragraph_format.space_after = Pt(6.0)

    def _render_callout(
        self,
        doc: docx.Document,
        block: CalloutBlock,
        profile: DesignProfile,
    ) -> None:
        table = doc.add_table(rows=1, cols=1)
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        cell = table.rows[0].cells[0]

        variant_hex = (
            profile.palette.teal_accent
            if block.variant.value == "note"
            else profile.palette.primary_navy
        )
        self._set_cell_background(cell, "F1F5F9")
        self._set_cell_padding(cell, 8.0)

        p = cell.paragraphs[0]
        if block.title:
            run_title = p.add_run(f"{block.title.upper()}: ")
            run_title.font.name = "Aptos"
            run_title.font.size = Pt(9.5)
            run_title.font.bold = True
            run_title.font.color.rgb = hex_to_rgb(variant_hex)

        run_text = p.add_run(block.text)
        run_text.font.name = "Aptos"
        run_text.font.size = Pt(9.5)
        run_text.font.color.rgb = hex_to_rgb(profile.palette.body_text)

        doc.add_paragraph().paragraph_format.space_after = Pt(4.0)

    def _render_code(
        self,
        doc: docx.Document,
        block: CodeBlock,
        profile: DesignProfile,
    ) -> None:
        table = doc.add_table(rows=1, cols=1)
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        cell = table.rows[0].cells[0]
        self._set_cell_background(cell, "0F172A")
        self._set_cell_padding(cell, 8.0)

        p = cell.paragraphs[0]
        run = p.add_run(block.code)
        run.font.name = "Consolas"
        run.font.size = Pt(8.5)
        run.font.color.rgb = RGBColor(241, 245, 249)

        doc.add_paragraph().paragraph_format.space_after = Pt(6.0)

    def _render_subsection(
        self,
        doc: docx.Document,
        block: SubsectionBlock,
        profile: DesignProfile,
    ) -> None:
        p_sub = doc.add_paragraph()
        h2_token = profile.typography.get(
            "heading_2",
            TypographyToken(
                font="Aptos", size_pt=12.0, color="#2F75B5", weight="bold", space_before_pt=12.0, space_after_pt=6.0
            ),
        )
        run_sub = p_sub.add_run(block.title)
        self._apply_run_token(run_sub, h2_token)
        p_sub.paragraph_format.space_before = Pt(h2_token.space_before_pt or 12.0)
        p_sub.paragraph_format.space_after = Pt(h2_token.space_after_pt or 6.0)
        p_sub.paragraph_format.keep_with_next = True

        for child in block.content:
            self._render_block(doc, child, profile)

    def _apply_run_token(self, run: Any, token: TypographyToken) -> None:
        run.font.name = token.font
        run.font.size = Pt(token.size_pt)
        run.font.color.rgb = hex_to_rgb(token.color)
        if token.weight == "bold":
            run.font.bold = True
        elif token.weight == "italic":
            run.font.italic = True
        elif token.weight == "bold_italic":
            run.font.bold = True
            run.font.italic = True

    def _set_cell_background(self, cell: Any, hex_color_no_hash: str) -> None:
        shading = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{hex_color_no_hash}"/>')
        cell._tc.get_or_add_tcPr().append(shading)

    def _set_cell_padding(self, cell: Any, padding_pt: float) -> None:
        dxa = int(padding_pt * 20)
        tc_mar = parse_xml(
            f'<w:tcMar {nsdecls("w")}>'
            f'<w:top w:w="{dxa}" w:type="dxa"/>'
            f'<w:bottom w:w="{dxa}" w:type="dxa"/>'
            f'<w:left w:w="{dxa}" w:type="dxa"/>'
            f'<w:right w:w="{dxa}" w:type="dxa"/>'
            f'</w:tcMar>'
        )
        cell._tc.get_or_add_tcPr().append(tc_mar)
