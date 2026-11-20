"""
Section Content Generator Service.

Generates structured content section-by-section using the DocumentBlueprint,
SectionDefinition constraints, writing guidelines, and project understanding.
"""

from __future__ import annotations

import json
import re
from typing import Any, Callable, Dict, List, Optional

from app.schemas.project_understanding import ProjectUnderstanding
from app.schemas.template.blueprint import DocumentBlueprint, SelectedSection
from app.schemas.template.content_block import (
    BulletedListBlock,
    CalloutBlock,
    CalloutVariant,
    ContentBlock,
    DiagramBlock,
    NumberedListBlock,
    ParagraphBlock,
    TableBlock,
)
from app.schemas.template.section import ContentStructureBlock, SectionDefinition
from app.schemas.template.section_content import DocumentContent, SectionContent
from app.services.content.content_validator import ContentValidator
from app.services.templates.section_loader import SectionLibraryLoader


class ContentGenerationError(Exception):
    """Raised when section content generation or validation fails."""
    pass


class SectionContentGenerator:
    """
    Generates structured, validated content blocks for each section in a document blueprint.
    """

    def __init__(
        self,
        section_loader: Optional[SectionLibraryLoader] = None,
        validator: Optional[ContentValidator] = None,
    ) -> None:
        self.section_loader = section_loader or SectionLibraryLoader()
        self.validator = validator or ContentValidator(self.section_loader)

    def generate_document(
        self,
        blueprint: DocumentBlueprint,
        project: ProjectUnderstanding,
        llm_client: Optional[Callable[[str], str]] = None,
    ) -> DocumentContent:
        """
        Generates full DocumentContent containing all sections in the blueprint.

        Args:
            blueprint: The approved document blueprint.
            project: Structured project understanding.
            llm_client: Optional LLM callable for generation.

        Returns:
            DocumentContent: Validated structured document content.
        """
        sections: List[SectionContent] = []
        doc_assumptions: List[str] = list(blueprint.assumptions)
        doc_unknowns: List[str] = list(blueprint.missing_information)

        for selected in blueprint.selected_sections:
            definition = (
                selected.custom_definition
                if selected.custom and selected.custom_definition
                else self.section_loader.get_section(selected.section_id)
            )

            if not definition:
                raise ContentGenerationError(
                    f"Cannot generate section '{selected.section_id}': Definition not found."
                )

            section_content = self.generate_section(
                selected=selected,
                definition=definition,
                project=project,
                llm_client=llm_client,
            )
            sections.append(section_content)
            doc_assumptions.extend(section_content.assumptions)
            doc_unknowns.extend(section_content.missing_information)

        doc_content = DocumentContent(
            title=blueprint.document.title,
            subtitle=blueprint.document.subtitle,
            design_profile=blueprint.document.design_profile,
            sections=sections,
            metadata={
                "client_name": blueprint.document.client_name,
                "prepared_by": blueprint.document.prepared_by,
                "version": blueprint.document.version,
                "date": blueprint.document.date,
            },
            global_assumptions=list(dict.fromkeys(doc_assumptions)),
            global_unknowns=list(dict.fromkeys(doc_unknowns)),
        )

        # Validate whole document
        val_result = self.validator.validate_document(doc_content, blueprint)
        if not val_result.is_valid:
            raise ContentGenerationError(
                f"Generated document failed content validation: {'; '.join(val_result.errors)}"
            )

        return doc_content

    def generate_section(
        self,
        selected: SelectedSection,
        definition: SectionDefinition,
        project: ProjectUnderstanding,
        llm_client: Optional[Callable[[str], str]] = None,
    ) -> SectionContent:
        """
        Generates content for a single section conforming to its definition and guidelines.
        """
        if llm_client:
            return self._generate_section_with_llm(selected, definition, project, llm_client)
        return self._generate_section_deterministic(selected, definition, project)

    def _generate_section_deterministic(
        self,
        selected: SelectedSection,
        definition: SectionDefinition,
        project: ProjectUnderstanding,
    ) -> SectionContent:
        """
        Deterministic, grounded synthesis generating valid content blocks matching definition.
        """
        blocks: List[ContentBlock] = []
        assumptions: List[str] = []
        missing: List[str] = []

        sid = selected.section_id
        title = selected.title or definition.title

        # Map block slots defined in content_structure
        for slot in definition.content_structure:
            block = self._synthesize_block_for_slot(slot, sid, project)
            if block:
                blocks.append(block)

        # Ensure at least a fallback paragraph if empty
        if not blocks:
            blocks.append(
                ParagraphBlock(
                    text=f"The {title} addresses core project objectives and technical capabilities grounded in context."
                )
            )

        # Flag assumptions or unknowns if present in section
        if sid == "security_considerations" and not project.security_requirements:
            assumptions.append("Standard credential and network isolation assumed.")
        if sid == "timeline" and not project.timeline_info:
            missing.append("Exact calendar start dates pending client approval.")

        return SectionContent(
            section_id=sid,
            title=title,
            order=selected.order,
            blocks=blocks,
            assumptions=assumptions,
            missing_information=missing,
            source_references=[f"Context slice for {sid}"],
        )

    def _synthesize_block_for_slot(
        self,
        slot: ContentStructureBlock,
        section_id: str,
        project: ProjectUnderstanding,
    ) -> Optional[ContentBlock]:
        """
        Synthesizes a concrete ContentBlock conforming to slot specifications.
        """
        btype = slot.type.value

        if btype == "paragraph":
            text = self._synthesize_paragraph_text(section_id, project)
            return ParagraphBlock(block_id=slot.block_id, text=text)

        elif btype == "bulleted_list":
            items = self._synthesize_list_items(section_id, project)
            return BulletedListBlock(block_id=slot.block_id, items=items)

        elif btype == "numbered_list":
            items = self._synthesize_numbered_items(section_id, project)
            return NumberedListBlock(block_id=slot.block_id, items=items)

        elif btype == "table":
            columns = slot.columns or ["Item", "Description", "Status"]
            rows = self._synthesize_table_rows(section_id, columns, project)
            return TableBlock(block_id=slot.block_id, columns=columns, rows=rows)

        elif btype == "diagram":
            dtype = slot.diagram_type or "architecture"
            return DiagramBlock(
                block_id=slot.block_id,
                diagram_type=dtype,
                description=f"Visual workflow and architectural components for {project.project_title or 'the POC'}.",
                mermaid_code="graph TD;\n  Client[User Interface] --> API[FastAPI Gateway];\n  API --> Service[Processing Pipeline];\n  Service --> Store[(Persistent Store)];",
            )

        elif btype == "callout":
            return CalloutBlock(
                block_id=slot.block_id,
                variant=CalloutVariant.NOTE,
                title="Implementation Note",
                text=f"This section reflects requirements grounded in {project.project_type}.",
            )

        return None

    def _synthesize_paragraph_text(self, section_id: str, project: ProjectUnderstanding) -> str:
        if section_id == "executive_summary":
            return (
                f"This document presents a comprehensive Proof of Concept (POC) proposal for '{project.project_title or 'the project'}'. "
                f"The engagement addresses critical business needs: {project.business_problem} "
                f"The proposed solution delivers {project.proposed_solution}."
            )
        elif section_id == "business_need":
            return (
                f"Current operational workflows encounter significant manual challenges: {project.business_problem} "
                "These bottlenecks impede scalability and require a modernized technical framework."
            )
        elif section_id == "poc_objectives":
            return (
                "The primary mission of this Proof of Concept is to validate technical feasibility, "
                "de-risk architecture decisions, and prove concrete capabilities within an isolated sandbox."
            )
        elif section_id == "proposed_solution":
            return (
                f"The proposed architecture implements {project.proposed_solution}. "
                "Key capabilities include modular pipeline processing, deterministic validation, and decoupled integration."
            )
        elif section_id == "technical_architecture":
            return (
                "The architecture is organized into decoupled layers separating presentation, API routing, "
                "business services, and persistent data tiers to guarantee high availability and maintainability."
            )
        elif section_id == "rag_pipeline_design":
            return (
                "The Retrieval-Augmented Generation (RAG) pipeline ingests source documents, applies semantic chunking, "
                "generates dense embeddings, and indexes them in a vector database for low-latency similarity retrieval."
            )
        elif section_id == "data_migration":
            return (
                "The data migration framework establishes an automated extraction, transformation, and verification pipeline "
                "to transition legacy data into the modern schema without data corruption or extended downtime."
            )
        elif section_id == "conclusion":
            return (
                "In conclusion, the proposed Proof of Concept provides a low-risk, high-impact demonstration "
                "confirming architectural viability and operational value prior to full production rollout."
            )
        return (
            f"The {section_id.replace('_', ' ')} establishes foundational requirements for {project.project_title or 'the POC'}, "
            f"ensuring technical alignment across stakeholders."
        )

    def _synthesize_list_items(self, section_id: str, project: ProjectUnderstanding) -> List[str]:
        if section_id == "executive_summary":
            return [
                f"Demonstrate {project.proposed_solution[:70]}...",
                "Validate system performance against acceptance criteria",
                "Produce a production roadmap and architecture report",
            ]
        elif section_id == "business_need":
            return [
                "Disparate data sources causing high latency in retrieval",
                "Manual operational overhead and potential for human error",
                "Lack of standardized automated validation controls",
            ]
        return project.core_capabilities or ["Core capability verification", "Architectural governance"]

    def _synthesize_numbered_items(self, section_id: str, project: ProjectUnderstanding) -> List[str]:
        if section_id == "poc_objectives":
            return [
                "Validate end-to-end ingestion and normalization pipelines",
                "Measure processing latency and accuracy under representative loads",
                "Confirm stakeholder satisfaction with generated outputs",
            ]
        elif section_id == "conclusion":
            return [
                "Formal stakeholder approval of this POC Blueprint",
                "Provisioning of client sandbox access and credentials",
                "Sprint kickoff and baseline environment deployment",
            ]
        return ["Initial discovery and setup", "Implementation and testing", "Review and handoff"]

    def _synthesize_table_rows(
        self,
        section_id: str,
        columns: List[str],
        project: ProjectUnderstanding,
    ) -> List[List[str]]:
        num_cols = len(columns)

        if section_id == "poc_scope":
            return [
                self._pad_row(["Core Pipeline", "Automated ingestion & processing", "Legacy system overhaul"], num_cols),
                self._pad_row(["AI Models", "Model integration & evaluation", "Custom model fine-tuning"], num_cols),
                self._pad_row(["Deployment", "Isolated sandbox demonstration", "Full enterprise multi-region HA"], num_cols),
            ]
        elif section_id == "deliverables_success_criteria":
            return [
                self._pad_row(["POC Source Code", "Git Repository", "Clean test pass and documentation"], num_cols),
                self._pad_row(["Working Sandbox", "Hosted Environment", "Live interactive demonstration"], num_cols),
                self._pad_row(["Evaluation Report", "PDF / DOCX Document", "Stakeholder signoff"], num_cols),
            ]
        elif section_id == "technical_architecture":
            return [
                self._pad_row(["Presentation Layer", "Frontend UI", "User interaction and document preview", "React / Vite"], num_cols),
                self._pad_row(["API Gateway", "Backend Routing", "REST endpoints and request validation", "FastAPI / Python"], num_cols),
                self._pad_row(["Pipeline Engine", "Processing Core", "Normalization and LLM reasoning", "LangChain / LangGraph"], num_cols),
                self._pad_row(["Storage Layer", "Persistence", "State and artifact storage", "PostgreSQL / SQLite"], num_cols),
            ]
        elif section_id == "technology_stack":
            return [
                self._pad_row(["Backend Framework", "FastAPI (Python 3.12)", "High-performance async REST endpoints"], num_cols),
                self._pad_row(["Frontend Framework", "React 19 + TypeScript", "Type-safe interactive interface"], num_cols),
                self._pad_row(["Orchestration", "LangChain & LangGraph", "Structured stateful agent workflows"], num_cols),
            ]
        elif section_id == "security_considerations":
            return [
                self._pad_row(["Data In Transit", "TLS 1.3 encryption across all network calls", "Mandatory TLS certificates"], num_cols),
                self._pad_row(["Authentication", "JWT bearer token authorization", "SSO integration (OIDC/SAML)"], num_cols),
                self._pad_row(["Data Storage", "AES-256 encrypted volumes", "Automated backup snapshots"], num_cols),
            ]
        elif section_id == "risks_dependencies":
            return [
                self._pad_row(["Client Environment Access", "High", "Request tenant provisioning prior to kickoff", "Client Sponsor"], num_cols),
                self._pad_row(["Sample Data Availability", "Medium", "Use synthetic anonymized records as fallback", "Solution Team"], num_cols),
            ]
        elif section_id == "timeline":
            return [
                self._pad_row(["Phase 1: Kickoff", "Week 1", "Environment setup and baseline deployment", "Configured sandbox"], num_cols),
                self._pad_row(["Phase 2: Core Dev", "Weeks 2-3", "Pipeline implementation and model integration", "Working prototype"], num_cols),
                self._pad_row(["Phase 3: Validation", "Week 4", "Evaluation testing and report generation", "Final POC handoff"], num_cols),
            ]
        elif section_id == "rag_pipeline_design":
            return [
                self._pad_row(["Document Chunking", "Recursive Character Splitter", "Chunk size 1000, Overlap 150"], num_cols),
                self._pad_row(["Embeddings", "Dense Vector Embeddings", "Azure OpenAI / Vertex text-embedding"], num_cols),
                self._pad_row(["Vector Store", "pgvector Indexing", "HNSW cosine distance index"], num_cols),
            ]

        # Generic fallback row matching column count
        return [self._pad_row([f"Detail {i+1}" for i in range(num_cols)], num_cols)]

    def _pad_row(self, items: List[str], expected_len: int) -> List[str]:
        if len(items) >= expected_len:
            return items[:expected_len]
        return items + ["N/A"] * (expected_len - len(items))

    def _generate_section_with_llm(
        self,
        selected: SelectedSection,
        definition: SectionDefinition,
        project: ProjectUnderstanding,
        llm_client: Callable[[str], str],
    ) -> SectionContent:
        """
        Uses LLM with structured prompting to generate section blocks.
        """
        prompt = (
            f"You are a technical document writer. Generate structured content blocks for the section '{definition.title}'.\n"
            f"Project Context:\n{project.model_dump_json(indent=2)}\n\n"
            f"Writing Guidelines:\nTone: {definition.writing_guidelines.tone}\n"
            f"Instructions:\n{json.dumps(definition.writing_guidelines.instructions, indent=2)}\n\n"
            f"Expected Structure Slots:\n{json.dumps([s.model_dump() for s in definition.content_structure], indent=2)}\n\n"
            "Return valid JSON for SectionContent conforming strictly to schema.\n"
            "Include valid blocks (paragraph, bulleted_list, table, diagram) without inventing ungrounded metrics.\n"
            "Return valid JSON only without markdown code fences."
        )

        try:
            response_str = llm_client(prompt).strip()
            if response_str.startswith("```"):
                response_str = re.sub(r"^```(?:json)?\n|\n```$", "", response_str, flags=re.MULTILINE).strip()

            data = json.loads(response_str)
            return SectionContent.model_validate(data)
        except Exception:
            # Fall back safely to grounded deterministic synthesis
            return self._generate_section_deterministic(selected, definition, project)
