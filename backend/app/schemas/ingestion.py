from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class IngestionResult(BaseModel):
    """
    Standardized ingestion result across all input sources (document, image, text).
    """
    source_type: str = Field(..., description="Type of source: 'document', 'image', or 'text'")
    filename: Optional[str] = Field(default=None, description="Original filename if applicable")
    extracted_content: str = Field(..., description="Normalized text content formatted for LLM understanding")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Metadata such as page count, tables, headings, warnings, etc.")
