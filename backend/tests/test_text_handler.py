import pytest
from app.services.ingestion.text_handler import (
    TextHandler,
    TextExtractionError,
    extract_text_content,
)


def test_valid_text_extraction():
    raw_text = """
    Project Overview:
    The client requires a high-performance vector search engine.

    Key Requirements:
    • Latency under 50ms
    • Multi-tenant data isolation
    • Automated backup
    """
    result = extract_text_content(raw_text, title="Email from Solution Architect")

    assert result.source_type == "text"
    assert result.filename == "Email from Solution Architect"
    assert "Vector search engine" in result.extracted_content or "vector search engine" in result.extracted_content
    # Bullet conversion check: • converted to -
    assert "- Latency under 50ms" in result.extracted_content
    assert "- Multi-tenant data isolation" in result.extracted_content
    # Metadata check
    assert result.metadata["word_count"] > 10
    assert "Project Overview" in result.metadata["detected_sections"]
    assert "Key Requirements" in result.metadata["detected_sections"]


def test_empty_text_raises_error():
    with pytest.raises(TextExtractionError, match="empty or solely whitespace"):
        extract_text_content("   \n\t  ")


def test_whitespace_and_unicode_normalization():
    # Contains non-breaking space, \r\n, and multiple blank lines
    raw_text = "Line 1\xa0has\xa0non-breaking\xa0spaces.\r\n\r\n\r\n\r\nLine 2 after gaps."
    result = extract_text_content(raw_text, format_for_llm=False)

    assert "\xa0" not in result.extracted_content
    assert "\r" not in result.extracted_content
    assert "\n\n\n" not in result.extracted_content
    assert result.extracted_content == "Line 1 has non-breaking spaces.\n\nLine 2 after gaps."


def test_invalid_type_raises_error():
    with pytest.raises(TextExtractionError, match="Expected text input as string"):
        extract_text_content(12345)  # type: ignore
