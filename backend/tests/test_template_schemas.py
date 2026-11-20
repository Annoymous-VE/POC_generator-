import json
from pathlib import Path
import pytest
from pydantic import ValidationError

from app.schemas.template import (
    BulletedListBlock,
    CalloutBlock,
    CalloutVariant,
    CodeBlock,
    ContentBlockType,
    DiagramBlock,
    DocumentBlueprint,
    DesignProfile,
    NumberedListBlock,
    ParagraphBlock,
    SectionCategory,
    SectionDefinition,
    SelectedSection,
    SubsectionBlock,
    TableBlock,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "templates"


# ---------------------------------------------------------------------------
# Section Definition Schema Tests
# ---------------------------------------------------------------------------

def test_valid_section_definition_fixture():
    with open(FIXTURES_DIR / "valid_section.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    section = SectionDefinition.model_validate(data)
    assert section.section_id == "technical_architecture"
    assert section.category == SectionCategory.CONDITIONAL
    assert len(section.content_structure) == 3
    assert section.content_structure[0].type == ContentBlockType.PARAGRAPH
    assert section.content_structure[2].type == ContentBlockType.TABLE
    assert section.content_structure[2].columns == ["Component", "Responsibility", "Technology"]


def test_section_definition_invalid_id():
    with pytest.raises(ValidationError) as exc_info:
        SectionDefinition(
            section_id="Invalid-ID-With-Hyphens",
            title="Invalid",
            category=SectionCategory.CORE,
            description="desc",
            purpose="purpose",
        )
    assert "section_id" in str(exc_info.value)


def test_section_definition_invalid_category():
    with pytest.raises(ValidationError) as exc_info:
        SectionDefinition(
            section_id="valid_id",
            title="Valid Title",
            category="unsupported_category",  # type: ignore
            description="desc",
            purpose="purpose",
        )
    assert "category" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Content Block Schemas Tests
# ---------------------------------------------------------------------------

def test_paragraph_block():
    p = ParagraphBlock(text="This is a test paragraph.", style_reference="body_default")
    assert p.type == "paragraph"
    assert p.text == "This is a test paragraph."
    assert p.style_reference == "body_default"

    with pytest.raises(ValidationError):
        ParagraphBlock(text="")  # Empty text rejected


def test_bulleted_and_numbered_lists():
    b = BulletedListBlock(items=["Item 1", "Item 2"])
    assert b.type == "bulleted_list"
    assert len(b.items) == 2

    n = NumberedListBlock(items=["Step 1", "Step 2"])
    assert n.type == "numbered_list"
    assert len(n.items) == 2

    with pytest.raises(ValidationError):
        BulletedListBlock(items=[])  # Empty items rejected


def test_table_block():
    tbl = TableBlock(
        columns=["Metric", "Target"],
        rows=[["Latency", "< 200ms"], ["Uptime", "99.9%"]],
        caption="SLA Table",
    )
    assert tbl.type == "table"
    assert len(tbl.columns) == 2
    assert len(tbl.rows) == 2
    assert tbl.caption == "SLA Table"


def test_diagram_block():
    diagram = DiagramBlock(
        diagram_type="architecture",
        description="Architecture diagram showing gateway and downstream services.",
        mermaid_code="graph TD; A[Client] --> B[API Gateway];",
    )
    assert diagram.type == "diagram"
    assert diagram.mermaid_code is not None


def test_callout_block():
    callout = CalloutBlock(
        variant=CalloutVariant.ASSUMPTION,
        title="Key Assumption",
        text="Target cloud subscription is managed by the client.",
    )
    assert callout.type == "callout"
    assert callout.variant == CalloutVariant.ASSUMPTION

    with pytest.raises(ValidationError):
        CalloutBlock(variant="invalid_variant", text="some text")  # type: ignore


def test_code_block():
    code = CodeBlock(code="kubectl apply -f manifest.yaml", language="bash")
    assert code.type == "code_block"
    assert code.language == "bash"


def test_subsection_recursive_block():
    sub = SubsectionBlock(
        title="Sub-component Details",
        content=[
            ParagraphBlock(text="Intro to subcomponent."),
            BulletedListBlock(items=["Detail A", "Detail B"]),
        ],
    )
    assert sub.type == "subsection"
    assert len(sub.content) == 2
    assert isinstance(sub.content[0], ParagraphBlock)
    assert isinstance(sub.content[1], BulletedListBlock)


# ---------------------------------------------------------------------------
# Design System Schema Tests
# ---------------------------------------------------------------------------

def test_valid_design_profile_fixture():
    with open(FIXTURES_DIR / "valid_design_profile.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    profile = DesignProfile.model_validate(data)
    assert profile.profile_id == "corporate_blue"
    assert profile.palette.primary_navy == "#17365D"
    assert profile.has_style("heading_1")
    assert profile.has_style("standard_table")
    assert not profile.has_style("non_existent_style")


def test_design_profile_invalid_hex_color():
    with open(FIXTURES_DIR / "valid_design_profile.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    data["palette"]["primary_navy"] = "not-a-hex"

    with pytest.raises(ValidationError) as exc_info:
        DesignProfile.model_validate(data)
    assert "Invalid hex color" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Document Blueprint Schema Tests
# ---------------------------------------------------------------------------

def test_valid_document_blueprint_fixture():
    with open(FIXTURES_DIR / "valid_blueprint.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    blueprint = DocumentBlueprint.model_validate(data)
    assert blueprint.document.title == "AI Customer Support Automation POC"
    assert len(blueprint.selected_sections) == 2
    assert blueprint.selected_sections[0].section_id == "executive_summary"
    assert blueprint.selected_sections[1].section_id == "technical_architecture"
    assert len(blueprint.excluded_sections) == 1
    assert blueprint.excluded_sections[0].section_id == "data_migration"


def test_blueprint_duplicate_sections_rejected():
    with open(FIXTURES_DIR / "valid_blueprint.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    # Add duplicate section
    data["selected_sections"].append({
        "section_id": "executive_summary",
        "order": 3,
        "selection_reason": "Duplicate section",
    })

    with pytest.raises(ValidationError) as exc_info:
        DocumentBlueprint.model_validate(data)
    assert "Duplicate section_id 'executive_summary'" in str(exc_info.value)


def test_blueprint_unsorted_orders_rejected():
    with open(FIXTURES_DIR / "valid_blueprint.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    data["selected_sections"][0]["order"] = 5
    data["selected_sections"][1]["order"] = 2

    with pytest.raises(ValidationError) as exc_info:
        DocumentBlueprint.model_validate(data)
    assert "must be ordered by the 'order' field" in str(exc_info.value)


def test_blueprint_custom_section_validation():
    # When custom is True, custom_definition is required
    with pytest.raises(ValidationError) as exc_info:
        SelectedSection(
            section_id="custom_rag",
            order=1,
            selection_reason="Need custom rag",
            custom=True,
            custom_definition=None,
        )
    assert "custom_definition must be provided when custom is True" in str(exc_info.value)

    # Valid custom section with custom_definition
    custom_def = SectionDefinition(
        section_id="custom_rag",
        title="Custom RAG Design",
        category=SectionCategory.CUSTOM,
        description="Detailed vector indexing and retrieval strategy",
        purpose="Explain RAG mechanics",
        custom=True,
    )
    selected = SelectedSection(
        section_id="custom_rag",
        order=1,
        selection_reason="Need custom rag",
        custom=True,
        custom_definition=custom_def,
    )
    assert selected.custom is True
    assert selected.custom_definition.section_id == "custom_rag"
