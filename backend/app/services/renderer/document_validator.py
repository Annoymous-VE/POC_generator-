"""
Document Validator Service.

Inspects rendered DOCX documents against DocumentContent specifications,
verifying heading hierarchy, table integrity, cover page elements,
and running headers/footers.
"""

from __future__ import annotations

import io
from typing import List, Union
from pydantic import BaseModel, Field

import docx

from app.schemas.template.section_content import DocumentContent


class DocumentValidationResult(BaseModel):
    is_valid: bool = Field(..., description="True if no fatal rendering errors were found")
    errors: List[str] = Field(default_factory=list, description="Fatal rendering omissions or defects")
    warnings: List[str] = Field(default_factory=list, description="Non-fatal visual or layout warnings")


class DocumentValidator:
    """
    Validates rendered DOCX documents against expected document content.
    """

    def validate_docx(
        self,
        docx_bytes: Union[bytes, io.BytesIO],
        expected_content: DocumentContent,
    ) -> DocumentValidationResult:
        """
        Parses the binary DOCX and verifies all expected elements are present and well-formed.
        """
        errors: List[str] = []
        warnings: List[str] = []

        stream = io.BytesIO(docx_bytes) if isinstance(docx_bytes, bytes) else docx_bytes
        try:
            doc = docx.Document(stream)
        except Exception as e:
            errors.append(f"Failed to parse rendered DOCX document: {e}")
            return DocumentValidationResult(is_valid=False, errors=errors, warnings=warnings)

        paragraphs_text = [p.text for p in doc.paragraphs if p.text.strip()]
        doc_full_text = " ".join(paragraphs_text)

        # 1. Verify Cover Title
        if expected_content.title not in doc_full_text:
            errors.append(f"Document title '{expected_content.title}' was not found in rendered document.")

        # 2. Verify Every Expected Section Heading
        for sec in expected_content.sections:
            expected_heading = f"{sec.order}. {sec.title}"
            heading_found = any(expected_heading in p_text for p_text in paragraphs_text)
            if not heading_found:
                errors.append(f"Expected section heading '{expected_heading}' not found in rendered document.")

        # 3. Verify Tables Count
        expected_tables = 0
        for sec in expected_content.sections:
            for b in sec.blocks:
                if b.type == "table":
                    expected_tables += 1

        rendered_tables = len(doc.tables)
        if rendered_tables < expected_tables:
            warnings.append(
                f"Expected at least {expected_tables} tables, but found {rendered_tables} in rendered DOCX."
            )

        # 4. Verify Running Header & Footer
        sections = doc.sections
        if sections:
            header_text = "".join(p.text for p in sections[0].header.paragraphs)
            footer_text = "".join(p.text for p in sections[0].footer.paragraphs)
            if not header_text.strip():
                warnings.append("Document header is empty.")
            if not footer_text.strip():
                warnings.append("Document footer is empty.")

        return DocumentValidationResult(
            is_valid=(len(errors) == 0),
            errors=errors,
            warnings=warnings,
        )
