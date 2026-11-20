import io
import tempfile
from pathlib import Path
import pytest
import docx
from docx.shared import Inches

from app.schemas.project_understanding import ProjectUnderstanding
from app.services.content import SectionContentGenerator
from app.services.planner import DocumentPlanner
from app.services.renderer import DocumentValidator, DocxDocumentRenderer


@pytest.fixture
def sample_project():
    return ProjectUnderstanding(
        project_title="Cloud Migration & Ingestion POC",
        project_type="Database migration",
        business_problem="Legacy Oracle database license expiration and performance bottleneck.",
        proposed_solution="Migrate to Amazon Aurora PostgreSQL with schema conversion and automated reconciliation.",
        core_capabilities=["Schema mapping", "Reconciliation verification"],
        integrations=["Oracle", "Aurora PostgreSQL"],
        constraints=["Downtime under 4 hours"],
        security_requirements=["Encryption at rest and TLS 1.3 in transit"],
        deliverables=["Working migration script", "Reconciliation report"],
        success_criteria=["Zero data loss", "100% schema match"],
        factual_context="Database migration and reconciliation pipeline for 50 relational tables.",
    )


@pytest.fixture
def document_content(sample_project):
    planner = DocumentPlanner()
    blueprint = planner.plan_document(sample_project)

    content_generator = SectionContentGenerator()
    return content_generator.generate_document(blueprint, sample_project)


def test_docx_renderer_generates_valid_bytes(document_content):
    renderer = DocxDocumentRenderer()
    docx_bytes = renderer.render(document_content)

    assert isinstance(docx_bytes, bytes)
    assert len(docx_bytes) > 5000  # Non-trivial docx size

    # Verify readable by python-docx
    doc = docx.Document(io.BytesIO(docx_bytes))
    section = doc.sections[0]

    # Verify A4 dimensions
    assert round(section.page_width.inches, 2) == 8.27
    assert round(section.page_height.inches, 2) == 11.69

    # Verify margins (0.65 in)
    assert round(section.top_margin.inches, 2) == 0.65
    assert round(section.bottom_margin.inches, 2) == 0.65
    assert round(section.left_margin.inches, 2) == 0.65
    assert round(section.right_margin.inches, 2) == 0.65


def test_docx_renderer_saves_to_file(document_content):
    renderer = DocxDocumentRenderer()
    with tempfile.TemporaryDirectory() as tmp_dir:
        out_path = Path(tmp_dir) / "test_poc_document.docx"
        renderer.render(document_content, output_path=out_path)

        assert out_path.exists()
        assert out_path.stat().st_size > 5000


def test_document_validator_on_rendered_docx(document_content):
    renderer = DocxDocumentRenderer()
    docx_bytes = renderer.render(document_content)

    validator = DocumentValidator()
    result = validator.validate_docx(docx_bytes, document_content)

    assert result.is_valid
    assert len(result.errors) == 0
