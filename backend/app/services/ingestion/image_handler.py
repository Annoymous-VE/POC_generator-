"""
Image Ingestion Handler.

Parses, validates, and extracts content from image files
(e.g., screenshots of chat threads, photos of physical documents, diagrams, whiteboard notes).
Handles image normalization, optional OCR extraction (via pytesseract),
and prepares structured multimodal metadata (including base64 encoding and vision model hints)
for downstream LLM reasoning.
"""

from __future__ import annotations

import base64
import io
import os
import re
import shutil
from pathlib import Path
from typing import Any, BinaryIO, Callable, Dict, List, Optional, Tuple, Union

from PIL import Image, ImageOps

from app.schemas.ingestion import IngestionResult


class ImageExtractionError(Exception):
    """Custom exception raised when image processing or extraction fails."""
    pass


class ImageHandler:
    """
    Handler for validating, processing, and extracting text/context from images.
    """

    SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff", ".gif"}
    MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB
    MAX_IMAGE_DIMENSION = 8000  # Max width/height in px to avoid decompression bombs

    # Common Tesseract paths on Windows
    WINDOWS_TESSERACT_PATHS = [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        os.path.expanduser(r"~\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"),
    ]

    def __init__(
        self,
        max_file_size: int = MAX_FILE_SIZE_BYTES,
        vision_fn: Optional[Callable[[bytes, str], str]] = None,
    ) -> None:
        """
        Initialize ImageHandler.

        Args:
            max_file_size: Max allowed file size in bytes.
            vision_fn: Optional callable (bytes, mime_type) -> str for Vision LLM extraction.
        """
        self.max_file_size = max_file_size
        self.vision_fn = vision_fn
        self._tesseract_cmd = self._resolve_tesseract_cmd()

    def extract(
        self,
        file_input: Union[str, Path, bytes, BinaryIO],
        filename: Optional[str] = None,
        vision_fn: Optional[Callable[[bytes, str], str]] = None,
    ) -> IngestionResult:
        """
        Main extraction entrypoint for images.

        Args:
            file_input: File path (str/Path), file bytes, or file-like binary stream.
            filename: Original filename (used for extension detection).
            vision_fn: Optional per-call Vision LLM function.

        Returns:
            IngestionResult: Standardized schema containing extracted text, image context, and metadata.
        """
        stream, resolved_filename = self._to_binary_stream(file_input, filename)
        ext = Path(resolved_filename).suffix.lower() if resolved_filename else ""

        if ext not in self.SUPPORTED_EXTENSIONS:
            raise ImageExtractionError(
                f"Unsupported image format: '{ext}'. Supported formats: {', '.join(sorted(self.SUPPORTED_EXTENSIONS))}"
            )

        # Validate file size
        stream.seek(0, io.SEEK_END)
        size = stream.tell()
        stream.seek(0)

        if size == 0:
            raise ImageExtractionError(f"Image '{resolved_filename}' is empty (0 bytes).")
        if size > self.max_file_size:
            raise ImageExtractionError(
                f"Image size ({size / (1024 * 1024):.2f} MB) exceeds maximum allowed limit ({self.max_file_size / (1024 * 1024):.2f} MB)."
            )

        # Open and validate image with Pillow
        try:
            image = Image.open(stream)
            image.verify()  # Verifies file integrity
            stream.seek(0)
            image = Image.open(stream)  # Re-open after verify
            image.load()  # Ensure pixel data is loaded
        except Exception as exc:
            raise ImageExtractionError(f"Corrupt or invalid image file '{resolved_filename}': {str(exc)}") from exc

        width, height = image.size
        if width > self.MAX_IMAGE_DIMENSION or height > self.MAX_IMAGE_DIMENSION:
            raise ImageExtractionError(
                f"Image dimensions ({width}x{height}) exceed maximum allowed dimension ({self.MAX_IMAGE_DIMENSION}px)."
            )

        # Basic image statistics and MIME detection
        mime_type = self._get_mime_type(image.format or ext.lstrip("."))
        aspect_ratio = round(width / height, 2) if height > 0 else 1.0

        metadata: Dict[str, Any] = {
            "file_type": f"IMAGE ({image.format or ext.lstrip('.').upper()})",
            "format": image.format,
            "mime_type": mime_type,
            "dimensions": {"width": width, "height": height},
            "aspect_ratio": aspect_ratio,
            "color_mode": image.mode,
            "ocr_available": bool(self._tesseract_cmd),
            "is_scanned": True,  # Images are visual sources
        }

        # Determine visual category hint (screenshot vs diagram vs photo)
        metadata["visual_category_hint"] = self._infer_visual_category(width, height, aspect_ratio, image.mode)

        # Read full image bytes for base64 / vision processing
        stream.seek(0)
        image_bytes = stream.read()
        b64_data = base64.b64encode(image_bytes).decode("utf-8")
        metadata["base64_preview"] = f"data:{mime_type};base64,{b64_data[:60]}...[truncated]"
        metadata["image_data_uri"] = f"data:{mime_type};base64,{b64_data}"

        # Text extraction strategy:
        # 1. Custom Vision LLM function if provided
        # 2. Local Tesseract OCR if available
        # 3. Informative metadata placeholder guiding multimodal LLM ingestion
        extracted_text = ""
        extraction_method = "none"
        active_vision_fn = vision_fn or self.vision_fn

        if active_vision_fn:
            try:
                extracted_text = active_vision_fn(image_bytes, mime_type)
                extraction_method = "vision_model"
                metadata["requires_ocr"] = False
            except Exception as exc:
                metadata["vision_model_error"] = str(exc)

        if not extracted_text and self._tesseract_cmd:
            try:
                extracted_text = self._run_ocr(image)
                if extracted_text.strip():
                    extraction_method = "tesseract_ocr"
                    metadata["requires_ocr"] = False
            except Exception as exc:
                metadata["ocr_error"] = str(exc)

        if not extracted_text:
            extraction_method = "multimodal_pending"
            metadata["requires_ocr"] = True
            metadata["warning"] = (
                "No local OCR engine found or text could not be extracted directly. "
                "Base64 image data URI has been prepared for Vision LLM processing."
            )
            extracted_text = (
                "*(Visual image uploaded. Direct text was not extracted via local OCR. "
                "The image contains visual requirement data (chat, screenshot, document, or diagram) "
                "ready for Vision LLM interpretation.)*"
            )

        metadata["extraction_method"] = extraction_method

        # Detect chat or document patterns if text was found
        if extraction_method in ("tesseract_ocr", "vision_model"):
            chat_indicators = self._detect_chat_patterns(extracted_text)
            if chat_indicators:
                metadata["is_chat_screenshot"] = True
                metadata["chat_participants"] = chat_indicators

        # Format content with context header for LLM understanding
        formatted_content = self._format_for_llm(
            extracted_text=extracted_text,
            filename=resolved_filename,
            metadata=metadata,
        )

        return IngestionResult(
            source_type="image",
            filename=resolved_filename,
            extracted_content=formatted_content,
            metadata=metadata,
        )

    # ----------------------------------------------------------------------
    # OCR & Image Processing
    # ----------------------------------------------------------------------
    def _run_ocr(self, image: Image.Image) -> str:
        """Run OCR on preprocessed image using pytesseract."""
        import pytesseract

        if self._tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = self._tesseract_cmd

        # Preprocessing: convert to grayscale and contrast enhancement
        processed = ImageOps.grayscale(image)
        # Apply slight contrast adjustment
        processed = ImageOps.autocontrast(processed)

        text = pytesseract.image_to_string(processed)
        return self._clean_extracted_text(text)

    def _resolve_tesseract_cmd(self) -> Optional[str]:
        """Check if tesseract binary is available on PATH or common Windows locations."""
        which_path = shutil.which("tesseract")
        if which_path:
            return which_path

        for win_path in self.WINDOWS_TESSERACT_PATHS:
            if os.path.isfile(win_path):
                return win_path

        return None

    def _detect_chat_patterns(self, text: str) -> List[str]:
        """Detect chat thread patterns (e.g. timestamps, usernames, messaging markers)."""
        # Look for patterns like "Name [10:30 AM]:", "User: ...", "Yesterday at 4:15 PM"
        sender_pattern = re.compile(r"^[A-Z][a-zA-Z0-9_\s]{1,25}:", re.MULTILINE)
        matches = sender_pattern.findall(text)
        cleaned = [m.rstrip(":").strip() for m in matches if len(m.strip()) > 2]
        return list(dict.fromkeys(cleaned))[:10]

    def _infer_visual_category(
        self, width: int, height: int, aspect_ratio: float, mode: str
    ) -> str:
        """Heuristically infer image type (screenshot of chat/desktop vs document vs diagram)."""
        # Standard portrait document ratio (A4 is approx 0.7)
        if 0.65 <= aspect_ratio <= 0.75:
            return "scanned_document_or_page"
        # Standard landscape monitor screenshot (16:9 is 1.78, 16:10 is 1.6)
        if 1.5 <= aspect_ratio <= 1.85:
            return "desktop_screenshot_or_dashboard"
        # Mobile screenshot (tall portrait, e.g. 9:16 is 0.56, 9:19.5 is 0.46)
        if aspect_ratio < 0.6:
            return "mobile_chat_or_app_screenshot"
        return "diagram_or_general_image"

    def _get_mime_type(self, fmt: str) -> str:
        """Map format to MIME type."""
        fmt_lower = fmt.lower()
        if fmt_lower in ("jpg", "jpeg"):
            return "image/jpeg"
        if fmt_lower == "png":
            return "image/png"
        if fmt_lower == "webp":
            return "image/webp"
        if fmt_lower == "bmp":
            return "image/bmp"
        if fmt_lower == "tiff":
            return "image/tiff"
        if fmt_lower == "gif":
            return "image/gif"
        return "application/octet-stream"

    def _to_binary_stream(
        self,
        file_input: Union[str, Path, bytes, BinaryIO],
        filename: Optional[str],
    ) -> Tuple[BinaryIO, str]:
        """Convert various input formats into a seekable binary stream and resolved filename."""
        if isinstance(file_input, (str, Path)):
            path = Path(file_input)
            if not path.is_file():
                raise ImageExtractionError(f"Image file not found: {path}")
            resolved_filename = filename or path.name
            with open(path, "rb") as f:
                stream = io.BytesIO(f.read())
            return stream, resolved_filename

        elif isinstance(file_input, bytes):
            if not filename:
                raise ImageExtractionError("Filename is required when passing raw bytes.")
            return io.BytesIO(file_input), filename

        elif hasattr(file_input, "read"):
            resolved_filename = filename or getattr(file_input, "name", "image.png")
            content = file_input.read()
            if isinstance(content, str):
                content = content.encode("utf-8")
            return io.BytesIO(content), resolved_filename

        else:
            raise ImageExtractionError(
                f"Invalid file_input type: {type(file_input)}. Expected path, bytes, or file stream."
            )

    def _clean_extracted_text(self, text: str) -> str:
        """Clean OCR artifacts, standardize line breaks and spacing."""
        if not text:
            return ""
        text = text.replace("\x00", "").replace("\xa0", " ")
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        # Collapse excessive blank lines
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    def _format_for_llm(
        self,
        extracted_text: str,
        filename: str,
        metadata: Dict[str, Any],
    ) -> str:
        """
        Formats extracted image context and content with contextual scaffolding
        designed for LLM comprehension.
        """
        dims = metadata.get("dimensions", {})
        category = metadata.get("visual_category_hint", "image")
        method = metadata.get("extraction_method", "none")

        meta_lines = [
            f"# Image Ingestion: {filename}",
            f"- **Source File:** `{filename}`",
            f"- **Format:** {metadata.get('format', 'IMAGE')}",
            f"- **Dimensions:** {dims.get('width', 0)} x {dims.get('height', 0)} px",
            f"- **Inferred Category:** `{category}`",
            f"- **Extraction Method:** `{method}`",
        ]

        if metadata.get("is_chat_screenshot"):
            participants = metadata.get("chat_participants", [])
            if participants:
                meta_lines.append(f"- **Detected Chat Participants:** {', '.join(f'`{p}`' for p in participants)}")

        if metadata.get("warning"):
            meta_lines.append(f"> **Notice for LLM:** {metadata['warning']}")

        header = "\n".join(meta_lines)
        return f"{header}\n\n---\n\n## Extracted Visual & Text Content\n\n{extracted_text}"


# Standalone convenience function
def extract_image_content(
    file_input: Union[str, Path, bytes, BinaryIO],
    filename: Optional[str] = None,
    vision_fn: Optional[Callable[[bytes, str], str]] = None,
) -> IngestionResult:
    """
    Parse and extract content from an image (PNG, JPEG, WebP, etc.).

    Args:
        file_input: File path, raw bytes, or binary stream.
        filename: Optional filename (required if passing raw bytes).
        vision_fn: Optional Vision LLM callable for multimodal extraction.

    Returns:
        IngestionResult with normalized content and detailed metadata.
    """
    handler = ImageHandler(vision_fn=vision_fn)
    return handler.extract(file_input=file_input, filename=filename, vision_fn=vision_fn)
