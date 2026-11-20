"""
Design System Loader for Universal POC Template System.

Loads, validates, and manages DesignProfile configurations.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Optional, Union

from app.schemas.template.design_system import DesignProfile


class DesignSystemLoadError(Exception):
    """Raised when loading or validating a design profile fails."""
    pass


class DesignSystemLoader:
    """
    Service responsible for loading and resolving named design profiles.
    """

    DEFAULT_DESIGN_DIR = Path(__file__).resolve().parent.parent.parent.parent / "templates" / "design-system"

    def __init__(self, design_dir: Optional[Union[str, Path]] = None) -> None:
        self.design_dir = Path(design_dir) if design_dir else self.DEFAULT_DESIGN_DIR
        self._profiles: Dict[str, DesignProfile] = {}
        self._load_all()

    def _load_all(self) -> None:
        """Loads all JSON design profiles located in the target directory."""
        if not self.design_dir.exists():
            return

        for file_path in self.design_dir.glob("*.json"):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                profile = DesignProfile.model_validate(data)
                self._profiles[profile.profile_id] = profile
            except Exception as e:
                raise DesignSystemLoadError(
                    f"Failed to load design profile from '{file_path.name}': {e}"
                ) from e

    def get_profile(self, profile_id: str) -> DesignProfile:
        """
        Retrieves a loaded design profile by ID.

        Args:
            profile_id: Identifier of the profile (e.g. 'corporate_blue').

        Returns:
            DesignProfile: Validated design profile.

        Raises:
            DesignSystemLoadError: If profile_id is not registered.
        """
        if profile_id not in self._profiles:
            available = list(self._profiles.keys())
            raise DesignSystemLoadError(
                f"Design profile '{profile_id}' not found. Available profiles: {available}"
            )
        return self._profiles[profile_id]

    def register_profile(self, profile: DesignProfile) -> None:
        """Registers or replaces an in-memory profile."""
        self._profiles[profile.profile_id] = profile

    def list_profiles(self) -> Dict[str, DesignProfile]:
        """Returns all registered design profiles."""
        return dict(self._profiles)
