import json
import pytest

from app.schemas.ingestion import IngestionResult
from app.schemas.project_understanding import ProjectUnderstanding
from app.schemas.template.blueprint import DocumentBlueprint
from app.services.planner import (
    BlueprintValidator,
    DocumentPlanner,
    DocumentPlanningError,
    ProjectAnalyzer,
)


@pytest.fixture
def planner():
    return DocumentPlanner()


@pytest.fixture
def analyzer():
    return ProjectAnalyzer()


# ---------------------------------------------------------------------------
# Project Analyzer Tests
# ---------------------------------------------------------------------------

def test_project_analyzer_from_rag_ingestion(analyzer):
    ingest = IngestionResult(
        source_type="document",
        filename="AI_Customer_Support_RAG.pdf",
        extracted_content="""
# AI Customer Support with RAG Pipeline

## Current Challenges
Customer support agents spend 15 minutes searching disparate internal wikis. Resolution times are slow.

## Proposed Solution
An automated RAG retrieval system using vector embeddings in pgvector and LangChain to answer queries.

## Architecture
Includes Next.js frontend, FastAPI backend, Azure OpenAI embeddings, and PostgreSQL.
        """,
        metadata={"page_count": 3},
    )

    understanding = analyzer.analyze(ingest)
    assert understanding.project_title == "AI Customer Support with RAG Pipeline"
    assert understanding.project_type == "RAG application"
    assert "pgvector" in understanding.factual_context or "RAG" in understanding.factual_context
    assert len(understanding.core_capabilities) > 0


def test_project_analyzer_from_db_migration(analyzer):
    ingest = IngestionResult(
        source_type="text",
        filename="db_migration_notes.txt",
        extracted_content="""
Migrate legacy Oracle database schema to AWS Aurora PostgreSQL.
We need automated ETL schema conversion and validation reconciliation checks.
Target cutover window is over 3 weeks.
        """,
    )

    understanding = analyzer.analyze(ingest)
    assert understanding.project_type == "Database migration"
    assert "Database" in understanding.project_type
    assert "Aurora" in understanding.factual_context or "Oracle" in understanding.factual_context


# ---------------------------------------------------------------------------
# Planner Tests Across Different Project Archetypes
# ---------------------------------------------------------------------------

def test_planner_rag_application_selection(planner):
    project = ProjectUnderstanding(
        project_title="Support RAG Assistant",
        project_type="RAG application",
        business_problem="Disparate internal knowledge bases cause slow resolution.",
        proposed_solution="Implement vector search and RAG with embeddings.",
        core_capabilities=["Semantic search", "Context grounding"],
        integrations=["Vector DB", "LLM Gateway"],
        constraints=["Client AWS tenant"],
        security_requirements=["PII masking", "IAM role delegation"],
        deliverables=["Working RAG POC"],
        success_criteria=["Sub-second retrieval"],
        factual_context="RAG pipeline with vector indexing, semantic search, and document chunking.",
    )

    blueprint = planner.plan_document(project)

    selected_ids = [s.section_id for s in blueprint.selected_sections]

    # Must include core sections
    assert "executive_summary" in selected_ids
    assert "proposed_solution" in selected_ids
    assert "poc_scope" in selected_ids

    # Must include RAG custom section and architecture
    assert "rag_pipeline_design" in selected_ids
    assert "technical_architecture" in selected_ids
    assert "security_considerations" in selected_ids

    # Must exclude data migration
    assert "data_migration" not in selected_ids
    excluded_ids = [e.section_id for e in blueprint.excluded_sections]
    assert "data_migration" in excluded_ids


def test_planner_database_migration_selection(planner):
    project = ProjectUnderstanding(
        project_title="Core Banking DB Migration",
        project_type="Database migration",
        business_problem="Legacy Oracle database license expiration and performance bottleneck.",
        proposed_solution="Migrate to Amazon Aurora PostgreSQL with schema conversion.",
        core_capabilities=["Schema mapping", "Reconciliation checks"],
        integrations=["Oracle", "Aurora PostgreSQL"],
        constraints=["Downtime window under 4 hours"],
        security_requirements=["Encryption at rest", "VPC peering"],
        deliverables=["Migrated schema", "Reconciliation report"],
        success_criteria=["Zero data loss"],
        factual_context="Database migration of 50 tables, schema conversion, ETL pipeline.",
    )

    blueprint = planner.plan_document(project)

    selected_ids = [s.section_id for s in blueprint.selected_sections]

    # Must include data migration custom section
    assert "data_migration" in selected_ids
    # Must NOT include RAG section
    assert "rag_pipeline_design" not in selected_ids

    # Exclusions must document rationale
    excluded_rag = next(e for e in blueprint.excluded_sections if e.section_id == "rag_pipeline_design")
    assert "RAG" in excluded_rag.reason or "not implement" in excluded_rag.reason


def test_planner_simple_workflow_selection(planner):
    project = ProjectUnderstanding(
        project_title="Daily Report Email Automator",
        project_type="Workflow automation",
        business_problem="Team spends 30 minutes manually creating daily summary reports.",
        proposed_solution="Python cron job reading database and sending HTML summary.",
        core_capabilities=["Automated scheduled trigger", "Email dispatch"],
        integrations=["SMTP server"],
        constraints=["Minimal compute cost"],
        security_requirements=[],
        deliverables=["Script and scheduler"],
        success_criteria=["Automated daily delivery"],
        factual_context="Simple batch reporting workflow with no vector search, no DB migration.",
    )

    blueprint = planner.plan_document(project)

    selected_ids = [s.section_id for s in blueprint.selected_sections]

    # Neither RAG nor migration should be selected
    assert "rag_pipeline_design" not in selected_ids
    assert "data_migration" not in selected_ids

    # Core sections present
    assert "executive_summary" in selected_ids
    assert "poc_objectives" in selected_ids
    assert "conclusion" in selected_ids


# ---------------------------------------------------------------------------
# Planner with Mocked LLM Client
# ---------------------------------------------------------------------------

def test_planner_with_mocked_llm_client(planner):
    def mock_llm(prompt: str) -> str:
        mock_blueprint = {
            "schema_version": "1.0.0",
            "document": {
                "title": "LLM Generated POC Blueprint",
                "subtitle": "Generated via Mocked LLM",
                "language": "en",
                "design_profile": "corporate_blue",
            },
            "planning_summary": {
                "project_type": "AI automation",
                "selection_rationale": "Selected targeted sections for AI automation POC.",
            },
            "selected_sections": [
                {
                    "section_id": "executive_summary",
                    "title": "Executive Summary",
                    "order": 1,
                    "selection_reason": "Executive context.",
                },
                {
                    "section_id": "technical_architecture",
                    "title": "Technical Architecture",
                    "order": 2,
                    "selection_reason": "Technical stack.",
                },
            ],
            "excluded_sections": [
                {
                    "section_id": "data_migration",
                    "reason": "Not applicable to this AI POC.",
                }
            ],
            "missing_information": [],
            "assumptions": ["Client provisions API credentials."],
        }
        return json.dumps(mock_blueprint)

    project = ProjectUnderstanding(
        project_title="Mocked LLM Test",
        project_type="AI automation",
        business_problem="Need automated classification.",
        proposed_solution="LLM pipeline.",
        factual_context="AI automation with classification models.",
    )

    blueprint = planner.plan_document(project, llm_client=mock_llm)
    assert blueprint.document.title == "LLM Generated POC Blueprint"
    assert len(blueprint.selected_sections) == 2
    assert blueprint.selected_sections[0].section_id == "executive_summary"


# ---------------------------------------------------------------------------
# Blueprint Validator Failure Cases
# ---------------------------------------------------------------------------

def test_validator_detects_unknown_section(planner):
    project = ProjectUnderstanding(
        project_title="Invalid Test",
        project_type="Workflow automation",
        business_problem="Problem",
        proposed_solution="Solution",
        factual_context="Facts",
    )

    blueprint = planner.plan_document(project)
    # Inject unknown section
    blueprint.selected_sections.append(
        type(blueprint.selected_sections[0])(
            section_id="completely_unknown_fake_section",
            title="Fake",
            order=99,
            selection_reason="Testing validator failure",
            custom=False,
        )
    )

    validator = BlueprintValidator()
    result = validator.validate(blueprint)
    assert not result.is_valid
    assert any("neither in the Section Library nor marked as custom" in err for err in result.errors)


def test_validator_detects_invalid_design_profile(planner):
    project = ProjectUnderstanding(
        project_title="Invalid Profile Test",
        project_type="Workflow automation",
        business_problem="Problem",
        proposed_solution="Solution",
        factual_context="Facts",
    )
    blueprint = planner.plan_document(project)
    blueprint.document.design_profile = "non_existent_profile"

    validator = BlueprintValidator()
    result = validator.validate(blueprint)
    assert not result.is_valid
    assert any("not registered in the Design System" in err for err in result.errors)
