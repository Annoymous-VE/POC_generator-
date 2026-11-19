import io
import docx
import pypdf
import pytest
from app.services.ingestion.document_handler import (
    DocumentHandler,
    DocumentExtractionError,
    extract_document_content,
)


def test_docx_extraction_with_headings_and_tables():
    doc = docx.Document()
    doc.add_heading("Project Overview", level=1)
    doc.add_paragraph("Client requires a cloud-native analytics platform.")
    doc.add_heading("Key Requirements", level=2)
    doc.add_paragraph("Automated ingestion", style="List Bullet")
    doc.add_paragraph("Sub-second querying", style="List Bullet")

    table = doc.add_table(rows=2, cols=2)
    table.rows[0].cells[0].text = "Requirement"
    table.rows[0].cells[1].text = "Priority"
    table.rows[1].cells[0].text = "SOC2 Type II"
    table.rows[1].cells[1].text = "Critical"

    bio = io.BytesIO()
    doc.save(bio)
    bio.seek(0)

    result = extract_document_content(bio.getvalue(), filename="client_requirements.docx")

    assert result.source_type == "document"
    assert result.filename == "client_requirements.docx"
    assert "Project Overview" in result.extracted_content
    assert "# Project Overview" in result.extracted_content
    assert "## Key Requirements" in result.extracted_content
    assert "- Automated ingestion" in result.extracted_content
    assert "| Requirement | Priority |" in result.extracted_content
    assert "| SOC2 Type II | Critical |" in result.extracted_content
    assert result.metadata["table_count"] == 1
    assert result.metadata["is_scanned"] is False


def test_pdf_scanned_detection():
    writer = pypdf.PdfWriter()
    writer.add_blank_page(width=612, height=792)

    bio = io.BytesIO()
    writer.write(bio)
    bio.seek(0)

    result = extract_document_content(bio.getvalue(), filename="scanned_notes.pdf")

    assert result.source_type == "document"
    assert result.filename == "scanned_notes.pdf"
    assert result.metadata["page_count"] == 1
    assert result.metadata["is_scanned"] is True
    assert result.metadata["requires_ocr"] is True
    assert "warning" in result.metadata


def test_unsupported_file_extension():
    bio = io.BytesIO(b"dummy data")
    with pytest.raises(DocumentExtractionError, match="Unsupported document format"):
        extract_document_content(bio.getvalue(), filename="requirements.xyz")


def test_empty_file():
    bio = io.BytesIO(b"")
    with pytest.raises(DocumentExtractionError, match="empty"):
        extract_document_content(bio.getvalue(), filename="empty.pdf")
