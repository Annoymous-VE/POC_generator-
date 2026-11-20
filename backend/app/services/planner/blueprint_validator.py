"""
Blueprint Validator Service.

Validates machine-generated DocumentBlueprint instances against:
1. Section Library definitions
2. Design System profiles and token registries
3. Ordering, sequence monotonicity, and dependency rules
4. Custom section constraints
"""

from __future__ import annotations

from typing import Dict, List, Optional
from pydantic import BaseModel, Field

from app.schemas.template.blueprint import DocumentBlueprint
from app.services.templates.design_loader import DesignSystemLoader
from app.services.templates.section_loader import SectionLibraryLoader


class BlueprintValidationResult(BaseModel):
    is_valid: bool = Field(..., description="True if no critical errors were detected")
    errors: List[str] = Field(default_factory=list, description="Critical errors that prevent rendering")
    warnings: List[str] = Field(default_factory=list, description="Non-fatal warnings regarding ordering or overlap")


class BlueprintValidator:
    """
    Validates DocumentBlueprint conformance against library definitions, design system,
    ordering rules, and dependency constraints.
    """

    def __init__(
        self,
        section_loader: Optional[SectionLibraryLoader] = None,
        design_loader: Optional[DesignSystemLoader] = None,
    ) -> None:
        self.section_loader = section_loader or SectionLibraryLoader()
        self.design_loader = design_loader or DesignSystemLoader()

    def validate(self, blueprint: DocumentBlueprint) -> BlueprintValidationResult:
        """
        Runs comprehensive validation across the blueprint.

        Args:
            blueprint: Validated DocumentBlueprint instance.

        Returns:
            BlueprintValidationResult containing is_valid, errors, and warnings.
        """
        errors: List[str] = []
        warnings: List[str] = []

        # 1. Validate Design Profile existence
        profile_id = blueprint.document.design_profile
        try:
            design_profile = self.design_loader.get_profile(profile_id)
        except Exception:
            errors.append(f"Design profile '{profile_id}' is not registered in the Design System.")
            design_profile = None

        # 2. Check for Unique IDs and strictly sorted order
        seen_ids = set()
        last_order = 0
        order_map: Dict[str, int] = {}

        for sec in blueprint.selected_sections:
            if sec.section_id in seen_ids:
                errors.append(f"Duplicate section_id '{sec.section_id}' detected in selected_sections.")
            seen_ids.add(sec.section_id)

            if sec.order <= last_order:
                errors.append(
                    f"Section '{sec.section_id}' has order {sec.order}, which is not strictly greater than previous order {last_order}."
                )
            last_order = sec.order
            order_map[sec.section_id] = sec.order

        # 3. Validate Sections against Section Library or Custom Definition
        for sec in blueprint.selected_sections:
            if sec.custom:
                if not sec.custom_definition:
                    errors.append(f"Custom section '{sec.section_id}' must provide 'custom_definition'.")
                    continue
                # Verify custom definition matches section_id
                if sec.custom_definition.section_id != sec.section_id:
                    errors.append(
                        f"Custom section '{sec.section_id}' does not match definition id '{sec.custom_definition.section_id}'."
                    )
                definition = sec.custom_definition
            else:
                definition = self.section_loader.get_section(sec.section_id)
                if not definition:
                    errors.append(
                        f"Section '{sec.section_id}' is neither in the Section Library nor marked as custom."
                    )
                    continue

            # 4. Check Style References against Design Profile
            if design_profile:
                for style_key, style_name in definition.style_reference.items():
                    if not design_profile.has_style(style_name):
                        errors.append(
                            f"Section '{sec.section_id}' references unknown style '{style_name}' for slot '{style_key}'."
                        )

            # 5. Check Dependencies
            for dep in definition.dependencies:
                if dep not in order_map:
                    errors.append(
                        f"Section '{sec.section_id}' requires dependency '{dep}', which is not in selected_sections."
                    )
                elif order_map[dep] >= sec.order:
                    warnings.append(
                        f"Section '{sec.section_id}' (order {sec.order}) appears before its dependency '{dep}' (order {order_map[dep]})."
                    )

            # 6. Check Preferred Ordering (Warnings)
            for after_id in definition.ordering.preferred_after:
                if after_id in order_map and order_map[after_id] > sec.order:
                    warnings.append(
                        f"Section '{sec.section_id}' prefers to appear after '{after_id}', but precedes it in the blueprint."
                    )

            for before_id in definition.ordering.preferred_before:
                if before_id in order_map and order_map[before_id] < sec.order:
                    warnings.append(
                        f"Section '{sec.section_id}' prefers to appear before '{before_id}', but follows it in the blueprint."
                    )

        # 7. Check Essential Proposal Coverage
        has_intro = any(s in order_map for s in ["executive_summary", "business_need"])
        has_solution = any(s in order_map for s in ["proposed_solution", "technical_architecture"])
        has_boundaries = any(s in order_map for s in ["poc_scope", "deliverables_success_criteria"])

        if not has_intro:
            warnings.append("Blueprint does not include an introductory or business context section.")
        if not has_solution:
            errors.append("Blueprint must include a solution or technical architecture section.")
        if not has_boundaries:
            warnings.append("Blueprint does not include a scope or deliverables section.")

        return BlueprintValidationResult(
            is_valid=(len(errors) == 0),
            errors=errors,
            warnings=warnings,
        )
