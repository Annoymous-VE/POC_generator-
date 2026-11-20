"""
Design System Schemas for the Universal POC Template System.

Defines the central, tokenized visual specifications for POC documents:
color palettes, page layout, typography hierarchy, spacing, and table formatting.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Literal, Optional
from pydantic import BaseModel, Field, field_validator


def validate_hex_color(color: str) -> str:
    """Validates that a string is a 6-digit hex color with leading #."""
    if not re.match(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$", color):
        raise ValueError(f"Invalid hex color '{color}'. Must be format #RRGGBB or #RGB.")
    return color.upper()


class ColorPalette(BaseModel):
    primary_navy: str = Field(default="#17365D", description="Primary brand navy")
    corporate_blue: str = Field(default="#365F91", description="Corporate deep blue")
    secondary_blue: str = Field(default="#2F75B5", description="Secondary accent blue")
    light_blue: str = Field(default="#4F81BD", description="Light blue accent")
    teal_accent: str = Field(default="#0F6B78", description="Teal highlight accent")
    body_text: str = Field(default="#202B36", description="Standard body text color")
    muted_text: str = Field(default="#666666", description="Muted secondary text/footer")
    page_background: str = Field(default="#FFFFFF", description="Document page background")
    custom_colors: Dict[str, str] = Field(default_factory=dict, description="Additional project color tokens")

    @field_validator(
        "primary_navy",
        "corporate_blue",
        "secondary_blue",
        "light_blue",
        "teal_accent",
        "body_text",
        "muted_text",
        "page_background",
    )
    @classmethod
    def check_colors(cls, v: str) -> str:
        return validate_hex_color(v)


class PageLayout(BaseModel):
    page_size: Literal["A4", "Letter"] = "A4"
    orientation: Literal["portrait", "landscape"] = "portrait"
    top_margin_in: float = Field(default=0.65, ge=0.2, le=3.0)
    bottom_margin_in: float = Field(default=0.65, ge=0.2, le=3.0)
    left_margin_in: float = Field(default=0.65, ge=0.2, le=3.0)
    right_margin_in: float = Field(default=0.65, ge=0.2, le=3.0)


class TypographyToken(BaseModel):
    font: str = Field(default="Aptos", description="Font family name")
    size_pt: float = Field(..., gt=4.0, lt=72.0, description="Font size in points")
    color: str = Field(..., description="Hex color value")
    weight: Literal["regular", "bold", "italic", "bold_italic"] = "regular"
    line_spacing: Optional[float] = Field(default=1.15, gt=0.5, lt=3.0)
    space_before_pt: Optional[float] = Field(default=0.0, ge=0.0)
    space_after_pt: Optional[float] = Field(default=6.0, ge=0.0)

    @field_validator("color")
    @classmethod
    def check_token_color(cls, v: str) -> str:
        return validate_hex_color(v)


class TableStyleToken(BaseModel):
    header_background_color: str = Field(default="#17365D")
    header_text_color: str = Field(default="#FFFFFF")
    header_font_weight: Literal["regular", "bold"] = "bold"
    border_color: str = Field(default="#D3D3D3")
    border_width_pt: float = Field(default=0.5, ge=0.1, le=5.0)
    cell_padding_pt: float = Field(default=6.0, ge=0.0, le=24.0)
    alternating_row_color: Optional[str] = Field(default="#F9FAFB")

    @field_validator("header_background_color", "header_text_color", "border_color")
    @classmethod
    def check_table_colors(cls, v: str) -> str:
        return validate_hex_color(v)

    @field_validator("alternating_row_color")
    @classmethod
    def check_alt_color(cls, v: Optional[str]) -> Optional[str]:
        return validate_hex_color(v) if v else None


class DesignProfile(BaseModel):
    """
    Central design profile capturing visual styles for deterministic rendering.
    """
    profile_id: str = Field(..., min_length=2, description="Unique profile identifier, e.g. 'corporate_blue'")
    name: str = Field(..., min_length=2, description="Display name of the design profile")
    version: str = Field(default="1.0.0", description="Semantic version of the design system")
    palette: ColorPalette = Field(default_factory=ColorPalette)
    page_layout: PageLayout = Field(default_factory=PageLayout)
    typography: Dict[str, TypographyToken] = Field(
        default_factory=dict,
        description="Registered typography tokens: heading_1, body_default, etc."
    )
    table_styles: Dict[str, TableStyleToken] = Field(
        default_factory=dict,
        description="Registered table tokens: standard_table, etc."
    )
    custom_tokens: Dict[str, Any] = Field(default_factory=dict, description="Additional custom visual tokens")

    def has_style(self, style_name: str) -> bool:
        """Checks if a named style exists in typography, table_styles, or custom tokens."""
        return (
            style_name in self.typography
            or style_name in self.table_styles
            or style_name in self.custom_tokens
        )
