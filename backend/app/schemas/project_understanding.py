"""
Project Understanding Schema.

Represents the structured comprehension of the project extracted from normalized
IngestionResult, used by the Document Planner to select and order sections.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ProjectUnderstanding(BaseModel):
    """
    Structured extraction of project context synthesized from IngestionResult.
    """
    project_title: Optional[str] = Field(default=None, description="Inferred or stated project title")
    project_type: str = Field(..., description="Project category (e.g. 'AI automation', 'RAG application', 'Database migration')")
    business_problem: str = Field(..., description="The core business need or operational challenge")
    proposed_solution: str = Field(..., description="The proposed technical approach or capability")
    target_users_or_systems: List[str] = Field(default_factory=list, description="Target stakeholders, user personas, or client systems")
    core_capabilities: List[str] = Field(default_factory=list, description="Key features or functional capabilities")
    integrations: List[str] = Field(default_factory=list, description="Third-party systems, APIs, or data sources")
    constraints: List[str] = Field(default_factory=list, description="Known constraints (budget, timeline, security, environment)")
    security_requirements: List[str] = Field(default_factory=list, description="Explicit security, privacy, or compliance needs")
    deliverables: List[str] = Field(default_factory=list, description="Anticipated tangible deliverables")
    success_criteria: List[str] = Field(default_factory=list, description="Criteria for assessing POC acceptance")
    timeline_info: Optional[str] = Field(default=None, description="Timeline, phase duration, or deadline notes")
    risks_and_unknowns: List[str] = Field(default_factory=list, description="Identified risks, unknowns, or open questions")
    factual_context: str = Field(..., description="Source-grounded facts extracted from input")
    assumptions: List[str] = Field(default_factory=list, description="Inferred assumptions or prerequisites")
    source_metadata: Dict[str, Any] = Field(default_factory=dict, description="Metadata from the ingestion source")
