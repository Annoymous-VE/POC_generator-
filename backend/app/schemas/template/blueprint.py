"""
Document Blueprint Schemas for the Universal POC Template System.

Defines the structured output produced by the Document Planner LLM,
capturing selected sections, exclusions, ordering, custom definitions,
missing information, and assumptions.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator

from app.schemas.template.section import SectionDefinition


class DocumentMetadata(BaseModel):
    title: str = Field(..., min_length=1, description="POC document title")
    subtitle: Optional[str] = Field(default=None, description="POC document subtitle")
    client_name: Optional[str] = Field(default=None, description="Client or company name if known")
    prepared_by: Optional[str] = Field(default=None, description="Author or team name if known")
    version: Optional[str] = Field(default="1.0", description="Document version number")
    date: Optional[str] = Field(default=None, description="Document date string")
    language: str = Field(default="en", description="Language code")
    design_profile: str = Field(default="corporate_blue", description="Referenced design profile ID")


class PlanningSummary(BaseModel):
    project_type: str = Field(..., description="Inferred or stated project type (e.g. 'AI automation', 'RAG application')")
    selection_rationale: str = Field(..., description="High-level reasoning explaining the selection of sections")


class SelectedSection(BaseModel):
    section_id: str = Field(..., description="Target section ID from Section Library or custom section ID")
    title: Optional[str] = Field(default=None, description="Optional override title for the section")
    order: int = Field(..., ge=1, description="1-based sequence position in the document")
    selection_reason: str = Field(..., description="Why this section is necessary for this specific project")
    custom: bool = Field(default=False, description="Whether this is a project-specific custom section")
    custom_definition: Optional[SectionDefinition] = Field(
        default=None,
        description="Full section definition required if custom is True"
    )
    section_overrides: Dict[str, Any] = Field(
        default_factory=dict,
        description="Section-specific adjustments or focal points"
    )

    @field_validator("custom_definition")
    @classmethod
    def check_custom_definition_present(cls, v: Optional[SectionDefinition], info) -> Optional[SectionDefinition]:
        if info.data.get("custom") is True and v is None:
            raise ValueError("custom_definition must be provided when custom is True.")
        return v


class ExcludedSection(BaseModel):
    section_id: str = Field(..., description="Section ID from the Section Library that was considered but omitted")
    reason: str = Field(..., description="Explicit rationale for why this section was omitted")


class DocumentBlueprint(BaseModel):
    """
    Complete machine-validated blueprint output by the Document Planner.
    """
    schema_version: str = Field(default="1.0.0", description="Blueprint schema version")
    document: DocumentMetadata
    planning_summary: PlanningSummary
    selected_sections: List[SelectedSection] = Field(..., min_length=1, description="Ordered list of selected sections")
    excluded_sections: List[ExcludedSection] = Field(default_factory=list, description="List of omitted sections with reasons")
    missing_information: List[str] = Field(default_factory=list, description="Recorded gaps or required inputs that were not supplied")
    assumptions: List[str] = Field(default_factory=list, description="Assumptions made by the planner to bridge gaps")

    @field_validator("selected_sections")
    @classmethod
    def validate_orders_and_ids(cls, sections: List[SelectedSection]) -> List[SelectedSection]:
        # Validate unique section IDs
        seen_ids = set()
        for sec in sections:
            if sec.section_id in seen_ids:
                raise ValueError(f"Duplicate section_id '{sec.section_id}' found in selected_sections.")
            seen_ids.add(sec.section_id)

        # Validate order sequencing (must be sorted by order)
        orders = [sec.order for sec in sections]
        if orders != sorted(orders):
            raise ValueError("selected_sections must be ordered by the 'order' field.")
        return sections
