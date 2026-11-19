import io
from PIL import Image
import pytest
from app.services.ingestion.image_handler import (
    ImageHandler,
    ImageExtractionError,
    extract_image_content,
)


def _create_test_image(format="PNG", size=(400, 300), color=(255, 255, 255)) -> bytes:
    img = Image.new("RGB", size, color=color)
    bio = io.BytesIO()
    img.save(bio, format=format)
    return bio.getvalue()


def test_valid_image_extraction():
    img_bytes = _create_test_image(format="PNG", size=(800, 600))
    result = extract_image_content(img_bytes, filename="architecture_diagram.png")

    assert result.source_type == "image"
    assert result.filename == "architecture_diagram.png"
    assert result.metadata["format"] == "PNG"
    assert result.metadata["dimensions"] == {"width": 800, "height": 600}
    assert result.metadata["mime_type"] == "image/png"
    assert "image_data_uri" in result.metadata
    assert result.metadata["image_data_uri"].startswith("data:image/png;base64,")


def test_vision_fn_hook_with_chat_screenshot():
    img_bytes = _create_test_image(format="JPEG", size=(360, 780))  # Mobile screenshot ratio

    def mock_vision_model(raw_bytes: bytes, mime_type: str) -> str:
        assert mime_type == "image/jpeg"
        return (
            "Alice: Can we ensure the API responds within 200ms?\n"
            "Bob: Yes, and we must also support OAuth2 with Azure AD.\n"
            "Alice: Perfect, let's include that in the POC."
        )

    result = extract_image_content(
        img_bytes,
        filename="teams_chat.jpg",
        vision_fn=mock_vision_model,
    )

    assert result.source_type == "image"
    assert result.metadata["extraction_method"] == "vision_model"
    assert result.metadata["visual_category_hint"] == "mobile_chat_or_app_screenshot"
    assert result.metadata.get("is_chat_screenshot") is True
    assert "Alice" in result.metadata.get("chat_participants", [])
    assert "Bob" in result.metadata.get("chat_participants", [])
    assert "OAuth2 with Azure AD" in result.extracted_content


def test_empty_image_raises_error():
    with pytest.raises(ImageExtractionError, match="empty"):
        extract_image_content(b"", filename="empty.png")


def test_unsupported_image_extension():
    with pytest.raises(ImageExtractionError, match="Unsupported image format"):
        extract_image_content(b"some content", filename="photo.exe")


def test_corrupt_image_raises_error():
    with pytest.raises(ImageExtractionError, match="Corrupt or invalid image"):
        extract_image_content(b"not an image file at all", filename="fake.png")
