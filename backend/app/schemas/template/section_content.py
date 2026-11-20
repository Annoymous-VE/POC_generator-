"""
Section and Document Content Schemas for the Universal POC Template System.

Defines the structured representation of generated section content containing
validated content blocks, tracked assumptions, unknowns, and source references.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.schemas.template.content_block import ContentBlock


class SectionContent(BaseModel):
    """
    Generated and structured content for a single POC section.
    """
    section_id: str = Field(..., description="Target section identifier matching blueprint")
    title: str = Field(..., description="Display title for the section")
    order: int = Field(..., ge=1, description="Sequence order in the document")
    blocks: List[ContentBlock] = Field(default_factory=list, description="Ordered content blocks")
    assumptions: List[str] = Field(default_factory=list, description="Assumptions specific to this section")
    missing_information: List[str] = Field(default_factory=list, description="Information gaps flagged during drafting")
    source_references: List[str] = Field(default_factory=list, description="Source context grounding references")


class DocumentContent(BaseModel):
    """
    Full structured document content comprising all generated sections ready for rendering.
    """
    title: str = Field(..., description="POC document title")
    subtitle: Optional[str] = Field(default=None, description="POC document subtitle")
    design_profile: str = Field(default="corporate_blue", description="Referenced design profile ID")
    sections: List[SectionContent] = Field(default_factory=list, description="Ordered generated section contents")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Document metadata")
    global_assumptions: List[str] = Field(default_factory=list, description="Consolidated document-level assumptions")
    global_unknowns: List[str] = Field(default_factory=list, description="Consolidated document-level information gaps")
