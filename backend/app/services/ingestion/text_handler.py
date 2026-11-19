"""
Plain-Text Ingestion Handler.

Parses, validates, and normalizes plain-text requirement snippets
(e.g., copied from emails, chat threads, RFP excerpts, or meeting notes).
Prepares clean, structured Markdown content optimized for LLM reasoning
without invoking an LLM.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict, List, Optional

from app.schemas.ingestion import IngestionResult


class TextExtractionError(Exception):
    """Custom exception raised when plain-text validation or extraction fails."""
    pass


class TextHandler:
    """
    Handler for normalizing and structuring raw plain-text requirements for LLM ingestion.
    """

    DEFAULT_MAX_CHARS = 5_000_000  # 5 MB of plain text

    def __init__(self, max_chars: int = DEFAULT_MAX_CHARS) -> None:
        self.max_chars = max_chars

    def extract(
        self,
        text: str,
        title: Optional[str] = None,
        format_for_llm: bool = True,
    ) -> IngestionResult:
        """
        Validate and normalize raw text into a standardized IngestionResult.

        Args:
            text: Raw input text from the user (email, chat, notes, etc.).
            title: Optional title or source label (e.g., 'Email from Client CTO').
            format_for_llm: If True, wraps content with metadata header for LLM context.

        Returns:
            IngestionResult: Standardized ingestion schema with normalized content.
        """
        if not isinstance(text, str):
            raise TextExtractionError(f"Expected text input as string, got {type(text).__name__}.")

        # Validate non-empty content
        stripped = text.strip()
        if not stripped:
            raise TextExtractionError("Input text cannot be empty or solely whitespace.")

        if len(text) > self.max_chars:
            raise TextExtractionError(
                f"Input text exceeds maximum allowed limit of {self.max_chars:,} characters."
            )

        # Normalize text
        normalized_text = self._normalize_text(text)

        # Analyze structure deterministically
        metadata = self._compute_metadata(normalized_text, title)

        # Format content for LLM understanding if requested
        if format_for_llm:
            extracted_content = self._format_for_llm(normalized_text, title, metadata)
        else:
            extracted_content = normalized_text

        return IngestionResult(
            source_type="text",
            filename=title,
            extracted_content=extracted_content,
            metadata=metadata,
        )

    def _normalize_text(self, text: str) -> str:
        """
        Clean and normalize raw text:
        - Normalize unicode forms (NFKC).
        - Remove zero-width spaces and non-printable control characters.
        - Standardize newlines (\\r\\n, \\r -> \\n).
        - Normalize non-breaking spaces and smart quotes/dashes.
        - Normalize common bullet markers (•, ▪, -, *) to Markdown bullets.
        - Strip trailing whitespace while preserving line hierarchy.
        - Collapse 3+ consecutive blank lines to 2.
        """
        # Unicode normalization
        text = unicodedata.normalize("NFKC", text)

        # Remove zero-width characters and BOM
        text = re.sub(r"[\u200b\u200c\u200d\ufeff\u200e\u200f]", "", text)

        # Remove null characters
        text = text.replace("\x00", "")

        # Standardize spaces
        text = text.replace("\xa0", " ").replace("\u202f", " ")

        # Standardize line breaks
        text = text.replace("\r\n", "\n").replace("\r", "\n")

        # Standardize fancy bullets to markdown list item "- "
        # e.g., • Requirement 1 -> - Requirement 1
        text = re.sub(r"^[ \t]*[•▪►●‣][ \t]+", "- ", text, flags=re.MULTILINE)

        # Clean trailing spaces per line while preserving leading indentation
        cleaned_lines = [line.rstrip() for line in text.split("\n")]
        text = "\n".join(cleaned_lines)

        # Collapse excessive blank lines
        text = re.sub(r"\n{3,}", "\n\n", text)

        return text.strip()

    def _compute_metadata(self, text: str, title: Optional[str]) -> Dict[str, Any]:
        """Compute non-LLM statistical and structural metadata."""
        words = text.split()
        lines = text.splitlines()

        # Identify potential section titles or key requirement markers
        detected_sections: List[str] = []
        for line in lines:
            line_s = line.strip()
            # Markdown header (e.g., # Scope or ## Deliverables)
            if re.match(r"^#{1,4}\s+\S+", line_s):
                detected_sections.append(line_s.lstrip("#").strip())
            # Header-like lines ending in a colon (e.g., "Functional Requirements:")
            elif re.match(r"^[A-Z][A-Za-z0-9\s/_-]{2,50}:$", line_s):
                detected_sections.append(line_s.rstrip(":").strip())

        return {
            "source_type": "text",
            "title": title,
            "character_count": len(text),
            "word_count": len(words),
            "line_count": len(lines),
            "detected_sections": detected_sections[:15],
            "is_scanned": False,
            "requires_ocr": False,
        }

    def _format_for_llm(
        self,
        text: str,
        title: Optional[str],
        metadata: Dict[str, Any],
    ) -> str:
        """
        Wraps normalized plain text in a structured context header so an LLM immediately
        understands source boundaries, length, and key detected areas.
        """
        display_title = title or "Client Requirements (Plain Text)"
        meta_lines = [
            f"# Ingestion: {display_title}",
            "- **Source:** Direct Text / Notes",
            f"- **Word Count:** {metadata['word_count']}",
            f"- **Lines:** {metadata['line_count']}",
        ]

        if metadata.get("detected_sections"):
            sections_str = ", ".join(f"`{s}`" for s in metadata["detected_sections"][:8])
            meta_lines.append(f"- **Key Sections Identified:** {sections_str}")

        header = "\n".join(meta_lines)
        return f"{header}\n\n---\n\n## Content\n\n{text}"


# Standalone convenience function
def extract_text_content(
    text: str,
    title: Optional[str] = None,
    format_for_llm: bool = True,
) -> IngestionResult:
    """
    Normalize and prepare a raw text chunk for LLM ingestion.

    Args:
        text: Input raw text string.
        title: Optional label/title for the snippet.
        format_for_llm: If True, wraps content in an LLM context header.

    Returns:
        IngestionResult with normalized content and metadata.
    """
    handler = TextHandler()
    return handler.extract(text=text, title=title, format_for_llm=format_for_llm)
