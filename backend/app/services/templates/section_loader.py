"""
Section Library Loader for Universal POC Template System.

Loads, validates, and indexes reusable and project-specific section definitions
from the central catalogue. Verifies style references against registered design profiles.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional, Union

from app.schemas.template.design_system import DesignProfile
from app.schemas.template.section import SectionCategory, SectionDefinition


class SectionLibraryLoadError(Exception):
    """Raised when loading or validating section definitions fails."""
    pass


class SectionLibraryLoader:
    """
    Service responsible for loading, validating, and searching SectionLibrary definitions.
    """

    DEFAULT_LIBRARY_DIR = Path(__file__).resolve().parent.parent.parent.parent / "templates" / "section-library"

    def __init__(self, library_dir: Optional[Union[str, Path]] = None) -> None:
        self.library_dir = Path(library_dir) if library_dir else self.DEFAULT_LIBRARY_DIR
        self._sections: Dict[str, SectionDefinition] = {}
        self._load_all()

    def _load_all(self) -> None:
        """Loads and validates all section JSON files from the library directory."""
        if not self.library_dir.exists():
            return

        for file_path in self.library_dir.glob("*.json"):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    raw_data = json.load(f)

                items = raw_data if isinstance(raw_data, list) else [raw_data]
                for item in items:
                    sec = SectionDefinition.model_validate(item)
                    if sec.section_id in self._sections:
                        raise SectionLibraryLoadError(
                            f"Duplicate section_id '{sec.section_id}' detected in '{file_path.name}'."
                        )
                    self._sections[sec.section_id] = sec

            except Exception as e:
                raise SectionLibraryLoadError(
                    f"Error loading section library from '{file_path.name}': {e}"
                ) from e

    def get_section(self, section_id: str) -> Optional[SectionDefinition]:
        """Retrieves a section definition by ID."""
        return self._sections.get(section_id)

    def list_sections(self, category: Optional[SectionCategory] = None) -> List[SectionDefinition]:
        """
        Lists registered sections, optionally filtered by category.
        """
        if category:
            return [s for s in self._sections.values() if s.category == category]
        return list(self._sections.values())

    def register_section(self, section: SectionDefinition) -> None:
        """Registers or updates a section definition in memory."""
        self._sections[section.section_id] = section

    def validate_against_design_profile(self, profile: DesignProfile) -> List[str]:
        """
        Validates that all style references in loaded sections resolve to registered
        tokens in the supplied DesignProfile.

        Returns:
            List[str]: List of validation warning or error messages (empty if all valid).
        """
        issues: List[str] = []
        for sec in self._sections.values():
            for style_key, style_name in sec.style_reference.items():
                if not profile.has_style(style_name):
                    issues.append(
                        f"Section '{sec.section_id}' references unregistered style '{style_name}' for slot '{style_key}'."
                    )
        return issues
