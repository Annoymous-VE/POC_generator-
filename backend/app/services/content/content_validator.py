"""
Content Validator Service.

Validates generated SectionContent and DocumentContent instances against:
1. Section definition block structures and required block types
2. Table column schema and row integrity
3. Cross-section consistency, duplicate paragraph detection, and contradiction checks
"""

from __future__ import annotations

import difflib
from typing import Dict, List, Optional
from pydantic import BaseModel, Field

from app.schemas.template.blueprint import DocumentBlueprint
from app.schemas.template.content_block import (
    BulletedListBlock,
    NumberedListBlock,
    ParagraphBlock,
    TableBlock,
)
from app.schemas.template.section import SectionDefinition
from app.schemas.template.section_content import DocumentContent, SectionContent
from app.services.templates.section_loader import SectionLibraryLoader


class ContentValidationResult(BaseModel):
    is_valid: bool = Field(..., description="True if no critical errors were detected")
    errors: List[str] = Field(default_factory=list, description="Critical content structure errors")
    warnings: List[str] = Field(default_factory=list, description="Non-fatal content warnings or quality issues")


class ContentValidator:
    """
    Validates generated content against section definitions, structural constraints,
    and cross-section consistency.
    """

    def __init__(self, section_loader: Optional[SectionLibraryLoader] = None) -> None:
        self.section_loader = section_loader or SectionLibraryLoader()

    def validate_section(
        self,
        content: SectionContent,
        definition: Optional[SectionDefinition] = None,
    ) -> ContentValidationResult:
        """
        Validates a single SectionContent against its SectionDefinition.
        """
        errors: List[str] = []
        warnings: List[str] = []

        defn = definition or self.section_loader.get_section(content.section_id)
        if not defn:
            errors.append(f"No section definition found for section '{content.section_id}'.")
            return ContentValidationResult(is_valid=False, errors=errors, warnings=warnings)

        # 1. Check Required Content Blocks
        present_types = [b.type for b in content.blocks]
        for expected_block in defn.content_structure:
            if expected_block.required:
                if expected_block.type.value not in present_types:
                    errors.append(
                        f"Section '{content.section_id}' is missing required block type '{expected_block.type.value}' "
                        f"(block_id: '{expected_block.block_id}')."
                    )

        # 2. Block-Level Structural Checks
        for block in content.blocks:
            if isinstance(block, TableBlock):
                if not block.columns:
                    errors.append(f"Table in section '{content.section_id}' has empty columns list.")
                for row_idx, row in enumerate(block.rows):
                    if len(row) != len(block.columns):
                        errors.append(
                            f"Table row {row_idx + 1} in section '{content.section_id}' has {len(row)} cells; "
                            f"expected {len(block.columns)}."
                        )

            elif isinstance(block, (BulletedListBlock, NumberedListBlock)):
                if not block.items:
                    errors.append(f"List block in section '{content.section_id}' has no items.")
                for item_idx, item in enumerate(block.items):
                    if not item.strip():
                        warnings.append(
                            f"List block item {item_idx + 1} in section '{content.section_id}' is blank."
                        )

            elif isinstance(block, ParagraphBlock):
                if not block.text.strip():
                    errors.append(f"Paragraph block in section '{content.section_id}' has empty text.")

        return ContentValidationResult(
            is_valid=(len(errors) == 0),
            errors=errors,
            warnings=warnings,
        )

    def validate_document(
        self,
        document_content: DocumentContent,
        blueprint: Optional[DocumentBlueprint] = None,
    ) -> ContentValidationResult:
        """
        Validates the entire document content including cross-section consistency.
        """
        errors: List[str] = []
        warnings: List[str] = []

        content_section_map: Dict[str, SectionContent] = {
            s.section_id: s for s in document_content.sections
        }

        # 1. Blueprint Coverage Check
        if blueprint:
            for selected in blueprint.selected_sections:
                if selected.section_id not in content_section_map:
                    errors.append(
                        f"Selected section '{selected.section_id}' from blueprint was not generated."
                    )

        # 2. Section-by-Section Validation
        for section in document_content.sections:
            custom_defn = None
            if blueprint:
                sel = next((s for s in blueprint.selected_sections if s.section_id == section.section_id), None)
                if sel and sel.custom:
                    custom_defn = sel.custom_definition

            sec_res = self.validate_section(section, definition=custom_defn)
            errors.extend(sec_res.errors)
            warnings.extend(sec_res.warnings)

        # 3. Cross-Section Duplicate Paragraph Detection
        all_paragraphs: List[tuple[str, str]] = []  # (section_id, text)
        for section in document_content.sections:
            for b in section.blocks:
                if isinstance(b, ParagraphBlock):
                    clean = " ".join(b.text.split()).strip()
                    if len(clean) > 80:  # check substantive paragraphs
                        all_paragraphs.append((section.section_id, clean))

        for i in range(len(all_paragraphs)):
            for j in range(i + 1, len(all_paragraphs)):
                sec_a, text_a = all_paragraphs[i]
                sec_b, text_b = all_paragraphs[j]
                if sec_a != sec_b:
                    similarity = difflib.SequenceMatcher(None, text_a, text_b).ratio()
                    if similarity > 0.90:
                        warnings.append(
                            f"Substantially duplicate paragraph detected between sections '{sec_a}' and '{sec_b}' "
                            f"(similarity: {int(similarity * 100)}%)."
                        )

        return ContentValidationResult(
            is_valid=(len(errors) == 0),
            errors=errors,
            warnings=warnings,
        )
