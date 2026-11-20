"""
Section Definition Schemas for the Universal POC Template System.

Defines the structure, selection rules, writing guidelines, content block constraints,
and ordering preferences for reusable and custom POC sections.
"""

from __future__ import annotations

import re
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator

from app.schemas.template.content_block import ContentBlockType


class SectionCategory(str, Enum):
    CORE = "core"
    CONDITIONAL = "conditional"
    CUSTOM = "custom"


class SelectionPriority(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class SelectionRules(BaseModel):
    include_when: List[str] = Field(default_factory=list, description="Criteria triggers for including this section")
    exclude_when: List[str] = Field(default_factory=list, description="Criteria triggers for excluding this section")
    priority: SelectionPriority = Field(default=SelectionPriority.MEDIUM, description="Default selection priority")


class WritingGuidelines(BaseModel):
    tone: str = Field(default="professional and technically precise", description="Expected tone for drafting")
    detail_level: str = Field(default="detailed", description="Depth of coverage expected (concise, detailed, exhaustive)")
    instructions: List[str] = Field(default_factory=list, description="Explicit bulleted instructions for LLM content generation")


class ContentStructureBlock(BaseModel):
    """
    Defines an expected content block slot in a section definition.
    """
    block_id: str = Field(..., description="Unique ID for this block slot")
    type: ContentBlockType = Field(..., description="Allowed content block type")
    required: bool = Field(default=True, description="Whether this block must be present")
    purpose: Optional[str] = Field(default=None, description="What this block is intended to communicate")
    columns: Optional[List[str]] = Field(default=None, description="Expected table columns if type is table")
    diagram_type: Optional[str] = Field(default=None, description="Expected diagram type if type is diagram")


class SectionOrdering(BaseModel):
    preferred_after: List[str] = Field(default_factory=list, description="Section IDs this section should follow")
    preferred_before: List[str] = Field(default_factory=list, description="Section IDs this section should precede")


class SectionDefinition(BaseModel):
    """
    Standard definition schema for a reusable or custom POC section.
    """
    section_id: str = Field(..., min_length=2, description="Unique snake_case identifier")
    title: str = Field(..., min_length=2, description="Display title of the section")
    category: SectionCategory = Field(..., description="Section category: core, conditional, or custom")
    description: str = Field(..., description="Concise explanation of the section")
    purpose: str = Field(..., description="Business or technical purpose served by the section")
    selection_rules: SelectionRules = Field(default_factory=SelectionRules)
    required_information: List[str] = Field(default_factory=list, description="Context variables needed to draft this section")
    optional_information: List[str] = Field(default_factory=list, description="Optional context variables")
    writing_guidelines: WritingGuidelines = Field(default_factory=WritingGuidelines)
    content_structure: List[ContentStructureBlock] = Field(default_factory=list, description="Expected blocks layout")
    style_reference: Dict[str, str] = Field(default_factory=dict, description="Named design system style mappings")
    ordering: SectionOrdering = Field(default_factory=SectionOrdering)
    dependencies: List[str] = Field(default_factory=list, description="Section IDs required by this section")
    overlap_with: List[str] = Field(default_factory=list, description="Sections with potentially duplicate content")
    tags: List[str] = Field(default_factory=list, description="Taxonomy tags for categorization and search")
    custom: bool = Field(default=False, description="Flag indicating if this is a custom one-off section")
    custom_rationale: Optional[str] = Field(default=None, description="Rationale for why a custom section was necessary")

    @field_validator("section_id")
    @classmethod
    def validate_section_id(cls, v: str) -> str:
        if not re.match(r"^[a-z0-9_]+$", v):
            raise ValueError(f"section_id '{v}' must be lowercase alphanumeric with underscores only (snake_case).")
        return v
