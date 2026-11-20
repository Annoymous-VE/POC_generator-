import json
import pytest

from app.schemas.project_understanding import ProjectUnderstanding
from app.schemas.template.blueprint import DocumentBlueprint
from app.schemas.template.content_block import (
    BulletedListBlock,
    ParagraphBlock,
    TableBlock,
)
from app.schemas.template.section_content import DocumentContent, SectionContent
from app.services.content import (
    ContentGenerationError,
    ContentValidator,
    SectionContentGenerator,
)
from app.services.planner import DocumentPlanner


@pytest.fixture
def sample_project():
    return ProjectUnderstanding(
        project_title="Cloud Migration & Ingestion POC",
        project_type="Database migration",
        business_problem="Manual ETL routines cause slow ingestion and frequent data reconciliation errors.",
        proposed_solution="Automated schema migration and real-time validation pipeline with FastAPI and Aurora PostgreSQL.",
        core_capabilities=["Automated schema mapping", "Reconciliation verification"],
        integrations=["Oracle", "Aurora PostgreSQL"],
        constraints=["Downtime under 4 hours"],
        security_requirements=["Encryption at rest and TLS 1.3 in transit"],
        deliverables=["Working migration script", "Reconciliation report"],
        success_criteria=["Zero data loss", "100% schema match"],
        factual_context="Database migration and reconciliation pipeline for 50 relational tables.",
    )


@pytest.fixture
def sample_blueprint(sample_project):
    planner = DocumentPlanner()
    return planner.plan_document(sample_project)


# ---------------------------------------------------------------------------
# Section Content Generator Tests
# ---------------------------------------------------------------------------

def test_generate_single_section(sample_project, sample_blueprint):
    generator = SectionContentGenerator()
    selected_sec = sample_blueprint.selected_sections[0]  # executive_summary

    section_content = generator.generate_section(
        selected=selected_sec,
        definition=generator.section_loader.get_section(selected_sec.section_id),
        project=sample_project,
    )

    assert section_content.section_id == "executive_summary"
    assert len(section_content.blocks) >= 2
    # Check paragraph and bulleted list exist
    types = [b.type for b in section_content.blocks]
    assert "paragraph" in types
    assert "bulleted_list" in types


def test_generate_full_document(sample_project, sample_blueprint):
    generator = SectionContentGenerator()
    doc_content = generator.generate_document(sample_blueprint, sample_project)

    assert doc_content.title == sample_blueprint.document.title
    assert len(doc_content.sections) == len(sample_blueprint.selected_sections)
    # Check that each section matches the blueprint order
    for idx, sec in enumerate(doc_content.sections):
        assert sec.section_id == sample_blueprint.selected_sections[idx].section_id
        assert sec.order == sample_blueprint.selected_sections[idx].order
        assert len(sec.blocks) > 0


def test_generate_section_with_mocked_llm(sample_project, sample_blueprint):
    generator = SectionContentGenerator()
    selected_sec = sample_blueprint.selected_sections[0]

    def mock_llm(prompt: str) -> str:
        mock_data = {
            "section_id": "executive_summary",
            "title": "Executive Summary",
            "order": 1,
            "blocks": [
                {
                    "type": "paragraph",
                    "text": "This is an LLM generated executive summary paragraph.",
                },
                {
                    "type": "bulleted_list",
                    "items": ["Point 1", "Point 2"],
                },
            ],
            "assumptions": ["Mock assumption"],
            "missing_information": [],
            "source_references": ["Context prompt"],
        }
        return json.dumps(mock_data)

    sec_content = generator.generate_section(
        selected=selected_sec,
        definition=generator.section_loader.get_section(selected_sec.section_id),
        project=sample_project,
        llm_client=mock_llm,
    )
    assert sec_content.section_id == "executive_summary"
    assert sec_content.blocks[0].text == "This is an LLM generated executive summary paragraph."


# ---------------------------------------------------------------------------
# Content Validator Tests
# ---------------------------------------------------------------------------

def test_validator_detects_missing_required_block():
    validator = ContentValidator()
    # poc_scope requires a paragraph and a table
    invalid_scope_section = SectionContent(
        section_id="poc_scope",
        title="POC Scope",
        order=1,
        blocks=[
            ParagraphBlock(text="Introductory paragraph for scope."),
            # Missing required table!
        ],
    )

    result = validator.validate_section(invalid_scope_section)
    assert not result.is_valid
    assert any("missing required block type 'table'" in err for err in result.errors)


def test_validator_detects_table_row_mismatch():
    validator = ContentValidator()
    invalid_table_section = SectionContent(
        section_id="poc_scope",
        title="POC Scope",
        order=1,
        blocks=[
            ParagraphBlock(text="Scope overview."),
            TableBlock(
                columns=["Area", "In Scope", "Out of Scope"],  # 3 columns
                rows=[
                    ["Core", "Pipeline only"],  # Only 2 cells -> mismatch!
                ],
            ),
        ],
    )

    result = validator.validate_section(invalid_table_section)
    assert not result.is_valid
    assert any("has 2 cells; expected 3" in err for err in result.errors)


def test_validator_detects_empty_paragraph():
    validator = ContentValidator()
    invalid_section = SectionContent(
        section_id="conclusion",
        title="Conclusion",
        order=1,
        blocks=[
            ParagraphBlock(text="   "),  # Empty whitespace text
        ],
    )

    result = validator.validate_section(invalid_section)
    assert not result.is_valid
    assert any("empty text" in err for err in result.errors)


def test_validator_detects_duplicate_paragraphs():
    validator = ContentValidator()
    shared_text = (
        "The proposed architecture implements automated ingestion, normalization, and validation "
        "to ensure that all requirements are met without manual intervention or excessive latency."
    )

    doc = DocumentContent(
        title="Test Document",
        sections=[
            SectionContent(
                section_id="executive_summary",
                title="Executive Summary",
                order=1,
                blocks=[ParagraphBlock(text=shared_text), BulletedListBlock(items=["A", "B"])],
            ),
            SectionContent(
                section_id="business_need",
                title="Business Need",
                order=2,
                blocks=[ParagraphBlock(text=shared_text), BulletedListBlock(items=["C", "D"])],
            ),
        ],
    )

    result = validator.validate_document(doc)
    assert any("Substantially duplicate paragraph detected" in w for w in result.warnings)


def test_validator_detects_missing_blueprint_section(sample_blueprint):
    validator = ContentValidator()
    # Create document with one missing section from blueprint
    partial_doc = DocumentContent(
        title="Partial Document",
        sections=[
            SectionContent(
                section_id="executive_summary",
                title="Executive Summary",
                order=1,
                blocks=[ParagraphBlock(text="Summary text"), BulletedListBlock(items=["A"])],
            )
        ],
    )

    result = validator.validate_document(partial_doc, blueprint=sample_blueprint)
    assert not result.is_valid
    assert any("was not generated" in err for err in result.errors)
