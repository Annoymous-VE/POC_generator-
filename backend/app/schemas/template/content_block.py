"""
Content Block Schemas for the Universal POC Template System.

Defines the controlled catalogue of content blocks allowed in POC sections:
paragraph, bulleted_list, numbered_list, table, diagram, image, callout,
code_block, and subsection.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Union
from pydantic import BaseModel, Field


class ContentBlockType(str, Enum):
    PARAGRAPH = "paragraph"
    BULLETED_LIST = "bulleted_list"
    NUMBERED_LIST = "numbered_list"
    TABLE = "table"
    DIAGRAM = "diagram"
    IMAGE = "image"
    CALLOUT = "callout"
    SUBSECTION = "subsection"
    CODE_BLOCK = "code_block"


class BaseContentBlock(BaseModel):
    """Base model for all section content blocks."""
    block_id: Optional[str] = Field(default=None, description="Optional unique identifier for the block instance")
    style_reference: Optional[str] = Field(default=None, description="Named style reference from the Design System")


class ParagraphBlock(BaseContentBlock):
    type: Literal["paragraph"] = "paragraph"
    text: str = Field(..., min_length=1, description="Paragraph text content")


class BulletedListBlock(BaseContentBlock):
    type: Literal["bulleted_list"] = "bulleted_list"
    items: List[str] = Field(..., min_length=1, description="List of bulleted items")


class NumberedListBlock(BaseContentBlock):
    type: Literal["numbered_list"] = "numbered_list"
    items: List[str] = Field(..., min_length=1, description="Ordered list items")


class TableBlock(BaseContentBlock):
    type: Literal["table"] = "table"
    columns: List[str] = Field(..., min_length=1, description="Column header titles")
    rows: List[List[str]] = Field(default_factory=list, description="Table rows (matrix of cell string values)")
    caption: Optional[str] = Field(default=None, description="Optional table caption or title")


class DiagramBlock(BaseContentBlock):
    type: Literal["diagram"] = "diagram"
    diagram_type: str = Field(..., description="Type of diagram (e.g. 'architecture', 'workflow', 'data_flow')")
    description: str = Field(..., description="High-level description of what the diagram conveys")
    mermaid_code: Optional[str] = Field(default=None, description="Optional Mermaid.js diagram specification")
    nodes: List[Dict[str, Any]] = Field(default_factory=list, description="Structured nodes (if diagram is rendered deterministically)")
    edges: List[Dict[str, Any]] = Field(default_factory=list, description="Structured edges between nodes")


class ImageBlock(BaseContentBlock):
    type: Literal["image"] = "image"
    source: str = Field(..., description="File path, URL, or asset key for the image")
    caption: Optional[str] = Field(default=None, description="Optional image caption")
    alt_text: Optional[str] = Field(default=None, description="Accessibility alt text")


class CalloutVariant(str, Enum):
    NOTE = "note"
    WARNING = "warning"
    ASSUMPTION = "assumption"
    DECISION = "decision"


class CalloutBlock(BaseContentBlock):
    type: Literal["callout"] = "callout"
    variant: CalloutVariant = Field(default=CalloutVariant.NOTE, description="Visual/logical variant of callout")
    title: Optional[str] = Field(default=None, description="Callout title (e.g., 'Key Assumption')")
    text: str = Field(..., min_length=1, description="Callout body text")


class CodeBlock(BaseContentBlock):
    type: Literal["code_block"] = "code_block"
    code: str = Field(..., min_length=1, description="Source code or technical configuration")
    language: Optional[str] = Field(default=None, description="Programming or markup language")


class SubsectionBlock(BaseContentBlock):
    type: Literal["subsection"] = "subsection"
    title: str = Field(..., min_length=1, description="Subsection heading")
    content: List[ContentBlock] = Field(default_factory=list, description="Nested content blocks")


# Discriminated union of all concrete content blocks
ContentBlock = Union[
    ParagraphBlock,
    BulletedListBlock,
    NumberedListBlock,
    TableBlock,
    DiagramBlock,
    ImageBlock,
    CalloutBlock,
    CodeBlock,
    SubsectionBlock,
]

# Update forward references for recursive SubsectionBlock
SubsectionBlock.model_rebuild()
