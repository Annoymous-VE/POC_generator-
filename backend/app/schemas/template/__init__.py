"""
Template and adaptive planning schemas package.
"""

from app.schemas.template.content_block import (
    BaseContentBlock,
    BulletedListBlock,
    CalloutBlock,
    CalloutVariant,
    CodeBlock,
    ContentBlock,
    ContentBlockType,
    DiagramBlock,
    ImageBlock,
    NumberedListBlock,
    ParagraphBlock,
    SubsectionBlock,
    TableBlock,
)
from app.schemas.template.design_system import (
    ColorPalette,
    DesignProfile,
    PageLayout,
    TableStyleToken,
    TypographyToken,
)
from app.schemas.template.section import (
    ContentStructureBlock,
    SectionCategory,
    SectionDefinition,
    SectionOrdering,
    SelectionPriority,
    SelectionRules,
    WritingGuidelines,
)
from app.schemas.template.blueprint import (
    DocumentBlueprint,
    DocumentMetadata,
    ExcludedSection,
    PlanningSummary,
    SelectedSection,
)
from app.schemas.template.section_content import (
    DocumentContent,
    SectionContent,
)

__all__ = [
    # Content Blocks
    "BaseContentBlock",
    "BulletedListBlock",
    "CalloutBlock",
    "CalloutVariant",
    "CodeBlock",
    "ContentBlock",
    "ContentBlockType",
    "DiagramBlock",
    "ImageBlock",
    "NumberedListBlock",
    "ParagraphBlock",
    "SubsectionBlock",
    "TableBlock",
    # Design System
    "ColorPalette",
    "DesignProfile",
    "PageLayout",
    "TableStyleToken",
    "TypographyToken",
    # Section
    "ContentStructureBlock",
    "SectionCategory",
    "SectionDefinition",
    "SectionOrdering",
    "SelectionPriority",
    "SelectionRules",
    "WritingGuidelines",
    # Blueprint
    "DocumentBlueprint",
    "DocumentMetadata",
    "ExcludedSection",
    "PlanningSummary",
    "SelectedSection",
    # Content
    "DocumentContent",
    "SectionContent",
]
