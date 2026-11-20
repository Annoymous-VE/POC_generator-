"""
Document Planner Service.

Orchestrates the selection, ordering, exclusion, and custom section drafting
for a POC project using project context and the Section Library.
"""

from __future__ import annotations

import json
import re
from typing import Any, Callable, Dict, List, Optional

from app.schemas.ingestion import IngestionResult
from app.schemas.project_understanding import ProjectUnderstanding
from app.schemas.template.blueprint import (
    DocumentBlueprint,
    DocumentMetadata,
    ExcludedSection,
    PlanningSummary,
    SelectedSection,
)
from app.schemas.template.section import SectionCategory, SectionDefinition
from app.services.planner.blueprint_validator import BlueprintValidator
from app.services.planner.project_analyzer import ProjectAnalyzer
from app.services.templates.design_loader import DesignSystemLoader
from app.services.templates.section_loader import SectionLibraryLoader


class DocumentPlanningError(Exception):
    """Raised when blueprint generation or validation fails."""
    pass


class DocumentPlanner:
    """
    Plans tailored document blueprints using project context and the Section Library catalogue.
    """

    def __init__(
        self,
        section_loader: Optional[SectionLibraryLoader] = None,
        design_loader: Optional[DesignSystemLoader] = None,
        validator: Optional[BlueprintValidator] = None,
        analyzer: Optional[ProjectAnalyzer] = None,
    ) -> None:
        self.section_loader = section_loader or SectionLibraryLoader()
        self.design_loader = design_loader or DesignSystemLoader()
        self.validator = validator or BlueprintValidator(self.section_loader, self.design_loader)
        self.analyzer = analyzer or ProjectAnalyzer()

    def plan_document(
        self,
        context_input: ProjectUnderstanding | IngestionResult,
        design_profile_id: str = "corporate_blue",
        llm_client: Optional[Callable[[str], str]] = None,
    ) -> DocumentBlueprint:
        """
        Produce a validated DocumentBlueprint for the given project.

        Args:
            context_input: ProjectUnderstanding instance or raw IngestionResult.
            design_profile_id: Target design profile ID.
            llm_client: Optional LLM callable that takes a prompt and returns JSON.

        Returns:
            DocumentBlueprint: Validated document blueprint.
        """
        # Resolve project understanding
        if isinstance(context_input, IngestionResult):
            project = self.analyzer.analyze(context_input)
        else:
            project = context_input

        # Check design profile exists
        self.design_loader.get_profile(design_profile_id)

        # Generate blueprint via LLM if provided, else fallback to deterministic rule planner
        if llm_client:
            blueprint = self._plan_with_llm(project, design_profile_id, llm_client)
        else:
            blueprint = self._plan_with_heuristics(project, design_profile_id)

        # Validate blueprint
        val_result = self.validator.validate(blueprint)
        if not val_result.is_valid:
            raise DocumentPlanningError(
                f"Generated blueprint failed validation: {'; '.join(val_result.errors)}"
            )

        return blueprint

    def _has_positive_signal(self, text: str, keywords: List[str]) -> bool:
        """
        Returns True if any keyword is present and not immediately preceded by negation words (no, not, without).
        """
        for kw in keywords:
            pattern = rf"(?<!\bno\s)(?<!\bnot\s)(?<!\bwithout\s)\b{re.escape(kw)}"
            if re.search(pattern, text, re.IGNORECASE):
                return True
        return False

    def _plan_with_heuristics(
        self,
        project: ProjectUnderstanding,
        design_profile_id: str,
    ) -> DocumentBlueprint:
        """
        Deterministic, rule-based adaptive planning adhering to catalogue selection rules.
        """
        available_sections = self.section_loader.list_sections()
        available_map = {s.section_id: s for s in available_sections}

        selected_ids: List[str] = []
        excluded_map: Dict[str, str] = {}
        ptype = project.project_type.lower()
        context_text = f"{project.factual_context} {project.business_problem} {project.proposed_solution}".lower()

        # 1. Core Section Decisions
        core_ids = [
            "executive_summary",
            "business_need",
            "poc_objectives",
            "proposed_solution",
            "poc_scope",
            "deliverables_success_criteria",
            "conclusion",
        ]
        for cid in core_ids:
            if cid in available_map:
                selected_ids.append(cid)

        # 2. Conditional Section Evaluations
        # Technical Architecture
        if "technical_architecture" in available_map:
            if self._has_positive_signal(context_text, ["architecture", "component", "layer", "microservice", "infrastructure", "backend"]) or len(project.core_capabilities) > 1:
                selected_ids.append("technical_architecture")
            else:
                excluded_map["technical_architecture"] = "Project is an operational workflow with minimal architectural complexity."

        # Technology Stack
        if "technology_stack" in available_map:
            if self._has_positive_signal(context_text, ["technology", "framework", "database", "stack", "model"]):
                selected_ids.append("technology_stack")
            else:
                excluded_map["technology_stack"] = "Technology choices are standardized and do not require comparative rationale."

        # Data Flow
        if "data_flow" in available_map:
            if self._has_positive_signal(context_text, ["data flow", "pipeline", "etl", "ingestion", "transformation", "stream"]):
                selected_ids.append("data_flow")
            else:
                excluded_map["data_flow"] = "Solution does not involve complex multi-stage data transformations."

        # Security Considerations
        if "security_considerations" in available_map:
            if self._has_positive_signal(context_text, ["security", "auth", "encryption", "privacy", "pii", "iam", "compliance"]) or project.security_requirements:
                selected_ids.append("security_considerations")
            else:
                excluded_map["security_considerations"] = "Standard sandbox environment with no specialized regulatory or security constraints."

        # Risks & Dependencies
        if "risks_dependencies" in available_map:
            if project.risks_and_unknowns or project.constraints:
                selected_ids.append("risks_dependencies")
            else:
                excluded_map["risks_dependencies"] = "No material risks or prerequisite dependencies recorded."

        # Timeline
        if "timeline" in available_map:
            if project.timeline_info or self._has_positive_signal(context_text, ["timeline", "phase", "week", "sprint"]):
                selected_ids.append("timeline")
            else:
                excluded_map["timeline"] = "Timeline is to be determined in subsequent scheduling discussions."

        # 3. Project-Specific Custom Section Evaluations
        # RAG pipeline
        if "rag" in ptype or self._has_positive_signal(context_text, ["rag", "retrieval", "vector", "chunking", "embedding"]):
            if "rag_pipeline_design" in available_map:
                selected_ids.append("rag_pipeline_design")
        elif "rag_pipeline_design" in available_map:
            excluded_map["rag_pipeline_design"] = "Project does not implement Retrieval-Augmented Generation (RAG)."

        # Data migration
        if "migration" in ptype or self._has_positive_signal(context_text, ["database migration", "schema migration", "legacy data", "migrate legacy"]):
            if "data_migration" in available_map:
                selected_ids.append("data_migration")
        elif "data_migration" in available_map:
            excluded_map["data_migration"] = "No legacy database or schema migration is in scope."

        # Integration strategy
        if "integration" in ptype or self._has_positive_signal(context_text, ["integration", "webhook", "third-party api", "erp"]):
            if "integration_strategy" in available_map:
                selected_ids.append("integration_strategy")
        elif "integration_strategy" in available_map:
            excluded_map["integration_strategy"] = "No external system integration interfaces are required."

        # 4. Sequence and Order the Selected Sections
        ordered_ids = self._sort_sections(selected_ids, available_map)

        selected_sections: List[SelectedSection] = []
        for idx, sid in enumerate(ordered_ids, start=1):
            definition = available_map[sid]
            reason = f"Essential for validating {definition.purpose.lower()}."
            selected_sections.append(
                SelectedSection(
                    section_id=sid,
                    title=definition.title,
                    order=idx,
                    selection_reason=reason,
                    custom=(definition.category == SectionCategory.CUSTOM),
                    custom_definition=definition if definition.category == SectionCategory.CUSTOM else None,
                )
            )

        # Build Excluded Sections
        excluded_sections: List[ExcludedSection] = []
        for sid, defn in available_map.items():
            if sid not in ordered_ids:
                reason = excluded_map.get(sid, f"Omitted because {defn.purpose.lower()} is not relevant.")
                excluded_sections.append(ExcludedSection(section_id=sid, reason=reason))

        return DocumentBlueprint(
            schema_version="1.0.0",
            document=DocumentMetadata(
                title=project.project_title or "POC Proposal",
                subtitle="Proof of Concept Blueprint",
                client_name="Client Partner",
                prepared_by="AI POC Solution Engineering",
                version="1.0",
                language="en",
                design_profile=design_profile_id,
            ),
            planning_summary=PlanningSummary(
                project_type=project.project_type,
                selection_rationale=(
                    f"Selected {len(selected_sections)} targeted sections tailored for '{project.project_type}'."
                ),
            ),
            selected_sections=selected_sections,
            excluded_sections=excluded_sections,
            missing_information=project.risks_and_unknowns,
            assumptions=project.assumptions,
        )

    def _sort_sections(
        self,
        section_ids: List[str],
        available_map: Dict[str, SectionDefinition],
    ) -> List[str]:
        """
        Sorts section IDs adhering to narrative flow and ordering preferences:
        Overview -> Problem -> Objectives -> Solution -> Architecture -> Technical Details -> Scope -> Deliverables -> Governance/Timeline -> Conclusion.
        """
        rank_weights: Dict[str, int] = {
            "executive_summary": 10,
            "business_need": 20,
            "poc_objectives": 30,
            "proposed_solution": 40,
            "technical_architecture": 50,
            "rag_pipeline_design": 55,
            "data_migration": 56,
            "integration_strategy": 57,
            "technology_stack": 60,
            "data_flow": 70,
            "security_considerations": 80,
            "poc_scope": 90,
            "deliverables_success_criteria": 100,
            "risks_dependencies": 110,
            "timeline": 120,
            "conclusion": 200,
        }

        # Deduplicate and sort by weight (with fallback 95 for unknown custom sections)
        unique_ids = list(dict.fromkeys(section_ids))
        return sorted(unique_ids, key=lambda sid: rank_weights.get(sid, 95))

    def _plan_with_llm(
        self,
        project: ProjectUnderstanding,
        design_profile_id: str,
        llm_client: Callable[[str], str],
    ) -> DocumentBlueprint:
        """
        Constructs a structured prompt for the LLM and validates the output JSON.
        """
        available_sections = self.section_loader.list_sections()
        sections_brief = [
            {
                "section_id": s.section_id,
                "title": s.title,
                "category": s.category.value,
                "purpose": s.purpose,
                "selection_rules": s.selection_rules.model_dump(),
            }
            for s in available_sections
        ]

        prompt = (
            "You are an expert Solutions Architect. Plan a tailored POC document blueprint based on the provided project context.\n"
            f"Project Understanding:\n{project.model_dump_json(indent=2)}\n\n"
            f"Available Section Catalogue:\n{json.dumps(sections_brief, indent=2)}\n\n"
            f"Target Design Profile: {design_profile_id}\n\n"
            "Produce a JSON object strictly conforming to the DocumentBlueprint schema.\n"
            "Return valid JSON only without markdown code blocks."
        )

        try:
            response_str = llm_client(prompt)
            clean_json = response_str.strip()
            if clean_json.startswith("```"):
                clean_json = re.sub(r"^```(?:json)?\n|\n```$", "", clean_json, flags=re.MULTILINE).strip()

            data = json.loads(clean_json)
            return DocumentBlueprint.model_validate(data)
        except Exception:
            return self._plan_with_heuristics(project, design_profile_id)
