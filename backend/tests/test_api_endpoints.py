import io
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.ingestion import IngestionResult

client = TestClient(app)


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_get_sections_catalogue():
    response = client.get("/api/templates/sections")
    assert response.status_code == 200
    sections = response.json()
    assert isinstance(sections, list)
    assert len(sections) >= 16
    assert any(s["section_id"] == "executive_summary" for s in sections)


def test_get_design_profiles():
    response = client.get("/api/templates/design-profiles")
    assert response.status_code == 200
    profiles = response.json()
    assert "corporate_blue" in profiles
    assert profiles["corporate_blue"]["palette"]["primary_navy"] == "#17365D"


def test_ingest_text_endpoint():
    payload = {
        "text": "Client requires an automated RAG retrieval architecture with pgvector and FastAPI.",
        "title": "Email Requirement Snippet",
    }
    response = client.post("/api/ingest/text", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["source_type"] == "text"
    assert "pgvector" in data["extracted_content"]


def test_plan_document_endpoint():
    # Ingest then plan
    ingest_payload = {
        "text": """
# Customer Care Voice Bot

## Current Challenges
High call wait times of 20 minutes causing customer frustration.

## Proposed Solution
An AI automation voice bot handling tier 1 queries with RAG knowledge lookup.
        """,
        "title": "Voice Bot Spec",
    }
    ingest_res = client.post("/api/ingest/text", json=ingest_payload).json()

    plan_payload = {
        "ingestion_result": ingest_res,
        "design_profile": "corporate_blue",
    }
    response = client.post("/api/plan", json=plan_payload)
    assert response.status_code == 200
    plan_data = response.json()

    assert "blueprint" in plan_data
    assert "project_understanding" in plan_data
    assert plan_data["validation"]["is_valid"] is True

    selected_ids = [s["section_id"] for s in plan_data["blueprint"]["selected_sections"]]
    assert "executive_summary" in selected_ids
    assert "proposed_solution" in selected_ids


def test_full_generate_and_render_flow():
    # 1. Text Ingestion
    text_res = client.post(
        "/api/ingest/text",
        json={"text": "PostgreSQL database migration with automated schema validation checks."},
    ).json()

    # 2. Plan
    plan_data = client.post(
        "/api/plan",
        json={"ingestion_result": text_res, "design_profile": "corporate_blue"},
    ).json()

    # 3. Generate Content
    gen_payload = {
        "blueprint": plan_data["blueprint"],
        "project_understanding": plan_data["project_understanding"],
    }
    gen_res = client.post("/api/generate", json=gen_payload)
    assert gen_res.status_code == 200
    doc_content = gen_res.json()
    assert len(doc_content["sections"]) > 0

    # 4. Render DOCX
    render_res = client.post("/api/render/docx", json=doc_content)
    assert render_res.status_code == 200
    assert render_res.headers["content-type"] == (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    assert len(render_res.content) > 5000


def test_chat_brainstorm_endpoint():
    payload = {
        "message": "Can we include a section on disaster recovery and database backups?",
        "history": [],
    }
    response = client.post("/api/chat", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "reply" in data
    assert len(data["suggested_actions"]) > 0


def test_auto_process_text_endpoint():
    payload = {
        "text": """
# Automated Customer Support Agent

## Current Challenges
High volume of tier-1 support tickets overwhelming staff and increasing resolution time.

## Proposed Solution
An intelligent agent with vector knowledge base and automated escalation routing.
        """,
        "title": "Support Agent Spec",
    }
    response = client.post("/api/ingest/auto-process-text", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "ingestion_result" in data
    assert "project_understanding" in data
    assert "initial_message" in data
    assert "Automated Customer Support Agent" in data["project_understanding"]["project_title"]
    assert "/create" in data["initial_message"]


def test_auto_process_file_endpoint():
    import docx
    doc = docx.Document()
    doc.add_heading("Invoice Processing System", level=1)
    doc.add_paragraph("Automate invoice extraction with machine learning.")
    bio = io.BytesIO()
    doc.save(bio)
    bio.seek(0)

    files = {"file": ("invoice_spec.docx", bio, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
    response = client.post("/api/ingest/auto-process-file", files=files)
    assert response.status_code == 200
    data = response.json()
    assert "ingestion_result" in data
    assert "project_understanding" in data
    assert "initial_message" in data
    assert "/create" in data["initial_message"]



def test_create_endpoint_rejects_without_command():
    from app.schemas.project_understanding import ProjectUnderstanding
    u = ProjectUnderstanding(
        project_title="Cloud Migration POC",
        project_type="Database migration",
        business_problem="Slow queries",
        proposed_solution="PostgreSQL replication",
        factual_context="Context facts",
    )
    payload = {
        "project_understanding": u.model_dump(),
        "conversation_history": [{"sender": "user", "content": "Make sure we include SSL"}],
        "create_command": "Please build the POC",
    }
    response = client.post("/api/create", json=payload)
    assert response.status_code == 400
    assert "must be initiated with the '/create' command" in response.json()["detail"]


def test_create_endpoint_success():
    from app.schemas.project_understanding import ProjectUnderstanding
    u = ProjectUnderstanding(
        project_title="Cloud Migration POC",
        project_type="Database migration",
        business_problem="Slow legacy database queries causing latency",
        proposed_solution="Modern PostgreSQL schema with replication",
        factual_context="Client has Oracle database needing migration to AWS RDS PostgreSQL.",
        core_capabilities=["Schema migration", "Data verification", "Rollback plan"],
    )
    payload = {
        "project_understanding": u.model_dump(),
        "conversation_history": [
            {"sender": "user", "content": "We need encryption in transit and AES-256."},
            {"sender": "ai", "content": "Understood, we will include comprehensive security protocols."},
        ],
        "create_command": "/create prioritize zero-downtime cutover",
        "design_profile": "corporate_blue",
    }
    response = client.post("/api/create", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "blueprint" in data
    assert "document_content" in data
    assert "summary_message" in data
    assert len(data["document_content"]["sections"]) >= 4
    assert "Cloud Migration POC" in data["document_content"]["title"]


def test_edit_section_rejects_without_command():
    from app.schemas.template.section_content import DocumentContent, SectionContent
    doc = DocumentContent(
        title="Test Doc",
        design_profile="corporate_blue",
        sections=[SectionContent(section_id="technical_architecture", title="Technical Architecture", order=1, blocks=[])],
    )
    payload = {
        "document_content": doc.model_dump(),
        "edit_command": "Change section 1 to add caching",
    }
    response = client.post("/api/sections/edit", json=payload)
    assert response.status_code == 400
    assert "must be initiated with the '/edit' command" in response.json()["detail"]


def test_edit_section_unknown_fails():
    from app.schemas.template.section_content import DocumentContent, SectionContent
    doc = DocumentContent(
        title="Test Doc",
        design_profile="corporate_blue",
        sections=[SectionContent(section_id="technical_architecture", title="Technical Architecture", order=1, blocks=[])],
    )
    payload = {
        "document_content": doc.model_dump(),
        "edit_command": "/edit NonExistentSection Add something",
    }
    response = client.post("/api/sections/edit", json=payload)
    assert response.status_code == 400
    assert "Could not identify target section" in response.json()["detail"]


def test_edit_section_success():
    from app.schemas.template.section_content import DocumentContent, SectionContent
    from app.schemas.template.content_block import ParagraphBlock
    doc = DocumentContent(
        title="Test POC Document",
        design_profile="corporate_blue",
        sections=[
            SectionContent(
                section_id="executive_summary",
                title="Executive Summary",
                order=1,
                blocks=[ParagraphBlock(text="Initial executive summary text.")],
            ),
            SectionContent(
                section_id="technical_architecture",
                title="Technical Architecture",
                order=2,
                blocks=[ParagraphBlock(text="Initial technical architecture overview.")],
            ),
        ],
    )
    payload = {
        "document_content": doc.model_dump(),
        "edit_command": "/edit Technical Architecture Add Redis caching and PostgreSQL replica",
    }
    response = client.post("/api/sections/edit", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "document_content" in data
    assert data["section_id"] == "technical_architecture"
    assert data["section_title"] == "Technical Architecture"
    assert "Updated" in data["summary_message"]
    # Verify section updated in document
    arch_sec = next(s for s in data["document_content"]["sections"] if s["section_id"] == "technical_architecture")
    assert len(arch_sec["blocks"]) > 0
