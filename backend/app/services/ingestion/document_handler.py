"""
Document Ingestion Handler.

Parses and extracts content from PDF, DOCX, and DOC files.
Normalizes and formats extracted content specifically for LLM reasoning,
preserving document hierarchy, headers, bullet points, page contexts,
and structured tables (as Markdown).
"""

from __future__ import annotations

import io
import re
from pathlib import Path
from typing import Any, BinaryIO, Dict, List, Optional, Tuple, Union

import docx
import olefile
import pypdf

from app.schemas.ingestion import IngestionResult


class DocumentExtractionError(Exception):
    """Custom exception raised when document extraction fails."""
    pass


class DocumentHandler:
    """
    Handler for extracting and structuring content from PDF, DOCX, and DOC files.
    """

    SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".doc"}
    MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB

    def __init__(self, max_file_size: int = MAX_FILE_SIZE_BYTES) -> None:
        self.max_file_size = max_file_size

    def extract(
        self,
        file_input: Union[str, Path, bytes, BinaryIO],
        filename: Optional[str] = None,
    ) -> IngestionResult:
        """
        Main extraction entrypoint. Accepts a file path, raw bytes, or a binary stream.

        Args:
            file_input: File path (str/Path), file bytes, or file-like binary stream.
            filename: Original filename (used for extension detection when passing bytes/stream).

        Returns:
            IngestionResult: Standardized schema containing normalized content and metadata.
        """
        stream, resolved_filename = self._to_binary_stream(file_input, filename)
        ext = Path(resolved_filename).suffix.lower() if resolved_filename else ""

        if ext not in self.SUPPORTED_EXTENSIONS:
            raise DocumentExtractionError(
                f"Unsupported document format: '{ext}'. Supported formats: {', '.join(sorted(self.SUPPORTED_EXTENSIONS))}"
            )

        # Validate file size
        stream.seek(0, io.SEEK_END)
        size = stream.tell()
        stream.seek(0)

        if size == 0:
            raise DocumentExtractionError(f"Document '{resolved_filename}' is empty (0 bytes).")
        if size > self.max_file_size:
            raise DocumentExtractionError(
                f"File size ({size / (1024 * 1024):.2f} MB) exceeds maximum allowed limit ({self.max_file_size / (1024 * 1024):.2f} MB)."
            )

        try:
            if ext == ".pdf":
                content, metadata = self._extract_pdf(stream, resolved_filename)
            elif ext == ".docx":
                content, metadata = self._extract_docx(stream, resolved_filename)
            elif ext == ".doc":
                content, metadata = self._extract_doc(stream, resolved_filename)
            else:
                raise DocumentExtractionError(f"Handler not configured for extension: {ext}")
        except DocumentExtractionError:
            raise
        except Exception as exc:
            raise DocumentExtractionError(
                f"Failed to extract content from '{resolved_filename}': {str(exc)}"
            ) from exc

        # Format content with context header for LLM comprehension
        formatted_content = self._format_for_llm(
            content=content,
            filename=resolved_filename,
            file_type=ext.lstrip(".").upper(),
            metadata=metadata,
        )

        return IngestionResult(
            source_type="document",
            filename=resolved_filename,
            extracted_content=formatted_content,
            metadata=metadata,
        )

    # ----------------------------------------------------------------------
    # PDF Extraction
    # ----------------------------------------------------------------------
    def _extract_pdf(
        self, stream: BinaryIO, filename: str
    ) -> Tuple[str, Dict[str, Any]]:
        reader = pypdf.PdfReader(stream)
        total_pages = len(reader.pages)

        if total_pages == 0:
            raise DocumentExtractionError(f"PDF '{filename}' has no pages.")

        page_texts: List[str] = []
        char_counts: List[int] = []
        detected_sections: List[str] = []

        # Read document outline / bookmarks if present
        try:
            outline = reader.outline
            if outline:
                detected_sections = self._parse_pdf_outline(outline)
        except Exception:
            detected_sections = []

        for idx, page in enumerate(reader.pages, start=1):
            try:
                raw_text = page.extract_text() or ""
            except Exception:
                raw_text = ""

            cleaned_page = self._clean_text(raw_text)
            char_counts.append(len(cleaned_page))

            if cleaned_page:
                page_texts.append(f"### [Page {idx}]\n{cleaned_page}")
            else:
                page_texts.append(f"### [Page {idx}]\n*(No selectable text found on this page)*")

        total_characters = sum(char_counts)
        avg_chars_per_page = total_characters / total_pages if total_pages > 0 else 0
        is_scanned = avg_chars_per_page < 60  # Typical indicator of scanned / image-only PDF

        pdf_meta = reader.metadata or {}
        metadata: Dict[str, Any] = {
            "file_type": "PDF",
            "page_count": total_pages,
            "total_character_count": total_characters,
            "is_scanned": is_scanned,
            "requires_ocr": is_scanned,
            "title": str(pdf_meta.get("/Title", "")).strip() or None,
            "author": str(pdf_meta.get("/Author", "")).strip() or None,
            "detected_sections": detected_sections,
        }

        if is_scanned:
            metadata["warning"] = (
                "Document appears to be scanned or contains image-only pages. "
                "Optical Character Recognition (OCR) or Vision model processing is recommended."
            )

        full_content = "\n\n".join(page_texts)
        return full_content, metadata

    def _parse_pdf_outline(self, outline: list) -> List[str]:
        """Extract outline / table-of-contents titles from PDF."""
        sections = []
        for item in outline:
            if isinstance(item, list):
                sections.extend(self._parse_pdf_outline(item))
            elif hasattr(item, "title"):
                sections.append(str(item.title).strip())
        return [s for s in sections if s][:25]

    # ----------------------------------------------------------------------
    # DOCX Extraction
    # ----------------------------------------------------------------------
    def _extract_docx(
        self, stream: BinaryIO, filename: str
    ) -> Tuple[str, Dict[str, Any]]:
        doc = docx.Document(stream)
        body_elements: List[str] = []
        detected_headings: List[str] = []
        table_count = 0
        total_paragraphs = 0

        # Iterate over child elements in document order (paragraphs and tables)
        for element in doc.element.body:
            tag = element.tag.split("}")[-1] if "}" in element.tag else element.tag

            if tag == "p":
                total_paragraphs += 1
                p = docx.text.paragraph.Paragraph(element, doc)
                text = p.text.strip()
                if not text:
                    continue

                style_name = (p.style.name or "").lower() if p.style else ""
                formatted_para = self._format_docx_paragraph(text, style_name)

                if "heading" in style_name:
                    detected_headings.append(text)

                body_elements.append(formatted_para)

            elif tag == "tbl":
                table_count += 1
                tbl = docx.table.Table(element, doc)
                table_md = self._docx_table_to_markdown(tbl)
                if table_md:
                    body_elements.append(f"\n#### [Table {table_count}]\n" + table_md + "\n")

        full_content = "\n\n".join(body_elements).strip()
        if not full_content:
            full_content = "*(Document contains no readable text or supported elements)*"

        metadata: Dict[str, Any] = {
            "file_type": "DOCX",
            "paragraph_count": total_paragraphs,
            "table_count": table_count,
            "detected_headings": detected_headings[:30],
            "is_scanned": False,
            "requires_ocr": False,
        }

        # Check core properties if available
        try:
            core_props = doc.core_properties
            if core_props.title:
                metadata["title"] = core_props.title.strip()
            if core_props.author:
                metadata["author"] = core_props.author.strip()
        except Exception:
            pass

        return full_content, metadata

    def _format_docx_paragraph(self, text: str, style_name: str) -> str:
        """Format paragraph based on Word style to preserve Markdown hierarchy."""
        if "heading 1" in style_name:
            return f"# {text}"
        if "heading 2" in style_name:
            return f"## {text}"
        if "heading 3" in style_name:
            return f"### {text}"
        if "heading 4" in style_name:
            return f"#### {text}"
        if "heading" in style_name:
            return f"### {text}"
        if "list bullet" in style_name or "bullet" in style_name:
            return f"- {text}"
        if "list number" in style_name:
            return f"1. {text}"
        return text

    def _docx_table_to_markdown(self, table: docx.table.Table) -> str:
        """Convert a python-docx Table into clean Markdown table format."""
        rows_data: List[List[str]] = []
        for row in table.rows:
            # Extract cell text, collapsing inner newlines to spaces so table cells remain on one line
            row_cells = [
                re.sub(r"\s+", " ", cell.text).strip().replace("|", "\\|")
                for cell in row.cells
            ]
            # Avoid empty duplicate cells from merged columns
            rows_data.append(row_cells)

        if not rows_data or not any(any(c for c in r) for r in rows_data):
            return ""

        col_count = max(len(r) for r in rows_data)
        normalized_rows = [r + [""] * (col_count - len(r)) for r in rows_data]

        header = normalized_rows[0]
        separator = ["---"] * col_count

        lines = [
            "| " + " | ".join(header) + " |",
            "| " + " | ".join(separator) + " |",
        ]

        for row in normalized_rows[1:]:
            lines.append("| " + " | ".join(row) + " |")

        return "\n".join(lines)

    # ----------------------------------------------------------------------
    # DOC Extraction (Word 97-2003 / Legacy Binary / OLE)
    # ----------------------------------------------------------------------
    def _extract_doc(
        self, stream: BinaryIO, filename: str
    ) -> Tuple[str, Dict[str, Any]]:
        # 1. First attempt: check if it is actually a DOCX renamed to .doc
        stream.seek(0)
        try:
            content, meta = self._extract_docx(stream, filename)
            meta["file_type"] = "DOC (DOCX-compatible)"
            return content, meta
        except Exception:
            stream.seek(0)

        # 2. Check if it's plain text or RTF with .doc extension
        sample = stream.read(512)
        stream.seek(0)
        if sample.startswith(b"{\\rtf"):
            text = self._extract_rtf_text(stream.read().decode("latin1", errors="ignore"))
            return text, {"file_type": "DOC (RTF-format)", "is_scanned": False, "requires_ocr": False}

        # 3. Legacy OLE Compound Document extraction
        if olefile.isOleFile(stream):
            stream.seek(0)
            ole = olefile.OleFileIO(stream)
            extracted_text = ""
            warnings: List[str] = []

            # Extract WordDocument stream if present
            if ole.exists("WordDocument"):
                word_stream = ole.openstream("WordDocument").read()
                extracted_text = self._extract_strings_from_ole_stream(word_stream)

            # Check for metadata in SummaryInformation stream
            doc_meta: Dict[str, Any] = {
                "file_type": "DOC (Legacy Binary OLE)",
                "is_scanned": False,
                "requires_ocr": False,
            }
            try:
                meta = ole.get_metadata()
                if meta.title:
                    doc_meta["title"] = meta.title.decode("utf-8", errors="ignore") if isinstance(meta.title, bytes) else str(meta.title)
                if meta.author:
                    doc_meta["author"] = meta.author.decode("utf-8", errors="ignore") if isinstance(meta.author, bytes) else str(meta.author)
            except Exception:
                pass

            ole.close()

            if not extracted_text.strip():
                warnings.append("Could not extract clean text from legacy .doc binary stream.")
                extracted_text = "*(Unable to extract readable text from binary .doc file. Please consider converting to .docx)*"

            if warnings:
                doc_meta["warnings"] = warnings

            return extracted_text, doc_meta

        # Fallback raw string extraction
        stream.seek(0)
        raw_bytes = stream.read()
        extracted_text = self._extract_strings_from_ole_stream(raw_bytes)
        return extracted_text, {
            "file_type": "DOC (Binary Raw Fallback)",
            "warning": "Extracted via raw string extraction; complex formatting may be lost.",
            "is_scanned": False,
            "requires_ocr": False,
        }

    def _extract_rtf_text(self, rtf: str) -> str:
        """Strip basic RTF markup to extract readable text."""
        # Simple RTF tag stripping
        text = re.sub(r"\\[a-z]+(-?\d+)? ?|[{}\\]", "", rtf)
        return self._clean_text(text)

    def _extract_strings_from_ole_stream(self, data: bytes) -> str:
        """
        Extract readable unicode and ascii text fragments from binary Word streams.
        Filters out control characters and short garbage tokens.
        """
        # Try finding sequences of ASCII or UTF-16LE characters
        found_chunks: List[str] = []

        # UTF-16LE strings (common in Word 97-2003)
        try:
            # Match sequences of printable characters in UTF-16LE
            utf16_pattern = re.compile(b"(?:[\x20-\x7e\x0a\x0d]\x00){4,}")
            for match in utf16_pattern.finditer(data):
                chunk = match.group().decode("utf-16le", errors="ignore").strip()
                if len(chunk) > 3:
                    found_chunks.append(chunk)
        except Exception:
            pass

        # If UTF-16 didn't yield much, try printable ASCII sequences
        if sum(len(c) for c in found_chunks) < 100:
            ascii_pattern = re.compile(b"[\x20-\x7e\x0a\x0d]{5,}")
            for match in ascii_pattern.finditer(data):
                chunk = match.group().decode("latin1", errors="ignore").strip()
                # filter out obvious binary clutter
                if len(chunk) > 5 and any(c.isalpha() for c in chunk):
                    found_chunks.append(chunk)

        result = "\n".join(found_chunks)
        return self._clean_text(result)

    # ----------------------------------------------------------------------
    # Helper & Formatting Methods
    # ----------------------------------------------------------------------
    def _to_binary_stream(
        self,
        file_input: Union[str, Path, bytes, BinaryIO],
        filename: Optional[str],
    ) -> Tuple[BinaryIO, str]:
        """Convert various input formats into a seekable binary stream and resolved filename."""
        if isinstance(file_input, (str, Path)):
            path = Path(file_input)
            if not path.is_file():
                raise DocumentExtractionError(f"File not found: {path}")
            resolved_filename = filename or path.name
            with open(path, "rb") as f:
                stream = io.BytesIO(f.read())
            return stream, resolved_filename

        elif isinstance(file_input, bytes):
            if not filename:
                raise DocumentExtractionError("Filename is required when passing raw bytes.")
            return io.BytesIO(file_input), filename

        elif hasattr(file_input, "read"):
            resolved_filename = filename or getattr(file_input, "name", "document")
            # If not seekable or a SpooledTemporaryFile, read into BytesIO
            content = file_input.read()
            if isinstance(content, str):
                content = content.encode("utf-8")
            return io.BytesIO(content), resolved_filename

        else:
            raise DocumentExtractionError(
                f"Invalid file_input type: {type(file_input)}. Expected path, bytes, or file stream."
            )

    def _clean_text(self, text: str) -> str:
        """Normalize line endings, whitespace, and null characters."""
        if not text:
            return ""
        # Remove null characters
        text = text.replace("\x00", "")
        # Replace non-breaking spaces with standard spaces
        text = text.replace("\xa0", " ")
        # Standardize newlines
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        # Collapse 3 or more consecutive newlines into 2
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    def _format_for_llm(
        self,
        content: str,
        filename: str,
        file_type: str,
        metadata: Dict[str, Any],
    ) -> str:
        """
        Formats extracted document text with contextual scaffolding.
        This structured prompt header immediately tells the LLM the document context,
        structure, and potential caveats (e.g. scanned content or detected sections).
        """
        meta_lines = [
            f"# Document Analysis: {filename}",
            f"- **Source File:** `{filename}`",
            f"- **File Type:** {file_type}",
        ]

        if "page_count" in metadata:
            meta_lines.append(f"- **Total Pages:** {metadata['page_count']}")
        if "table_count" in metadata and metadata["table_count"] > 0:
            meta_lines.append(f"- **Extracted Tables:** {metadata['table_count']}")
        if metadata.get("title"):
            meta_lines.append(f"- **Document Title:** {metadata['title']}")
        if metadata.get("author"):
            meta_lines.append(f"- **Author:** {metadata['author']}")
        if metadata.get("detected_sections"):
            sections_str = ", ".join(f"`{s}`" for s in metadata["detected_sections"][:10])
            meta_lines.append(f"- **Key Sections Detected:** {sections_str}")
        if metadata.get("is_scanned"):
            meta_lines.append(
                "> **Note for LLM:** This document appears to be scanned or contains low-density text. "
                "Portions of the content may require OCR verification."
            )

        header = "\n".join(meta_lines)
        return f"{header}\n\n---\n\n## Extracted Document Content\n\n{content}"


# Standalone convenience function
def extract_document_content(
    file_input: Union[str, Path, bytes, BinaryIO],
    filename: Optional[str] = None,
) -> IngestionResult:
    """
    Parse and extract content from a PDF, DOCX, or DOC document.

    Args:
        file_input: File path, raw bytes, or binary stream.
        filename: Optional filename (required if passing raw bytes).

    Returns:
        IngestionResult with normalized content and detailed metadata.
    """
    handler = DocumentHandler()
    return handler.extract(file_input=file_input, filename=filename)
