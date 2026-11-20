import pytest
from app.schemas.template.section import SectionCategory
from app.services.templates import (
    DesignSystemLoader,
    DesignSystemLoadError,
    SectionLibraryLoader,
    SectionLibraryLoadError,
)


def test_design_system_loader_corporate_blue():
    loader = DesignSystemLoader()
    profile = loader.get_profile("corporate_blue")
    assert profile.profile_id == "corporate_blue"
    assert profile.name == "Corporate Blue"
    assert profile.palette.primary_navy == "#17365D"
    assert profile.has_style("heading_1")
    assert profile.has_style("body_default")
    assert profile.has_style("standard_table")
    assert profile.has_style("standard_diagram")


def test_design_system_loader_missing_profile():
    loader = DesignSystemLoader()
    with pytest.raises(DesignSystemLoadError) as exc_info:
        loader.get_profile("non_existent_profile")
    assert "not found" in str(exc_info.value)


def test_section_library_loader_all_categories():
    loader = SectionLibraryLoader()
    sections = loader.list_sections()
    assert len(sections) >= 16  # 7 core + 6 conditional + 3 project-specific

    # Test Core sections
    core_sections = loader.list_sections(category=SectionCategory.CORE)
    assert len(core_sections) == 7
    core_ids = {s.section_id for s in core_sections}
    expected_cores = {
        "executive_summary",
        "poc_objectives",
        "business_need",
        "proposed_solution",
        "poc_scope",
        "deliverables_success_criteria",
        "conclusion",
    }
    assert expected_cores.issubset(core_ids)

    # Test Conditional sections
    conditional_sections = loader.list_sections(category=SectionCategory.CONDITIONAL)
    assert len(conditional_sections) >= 6
    cond_ids = {s.section_id for s in conditional_sections}
    expected_conditionals = {
        "technical_architecture",
        "technology_stack",
        "data_flow",
        "security_considerations",
        "risks_dependencies",
        "timeline",
    }
    assert expected_conditionals.issubset(cond_ids)

    # Test Project-specific / Custom sections
    custom_sections = loader.list_sections(category=SectionCategory.CUSTOM)
    assert len(custom_sections) >= 3
    custom_ids = {s.section_id for s in custom_sections}
    expected_customs = {
        "rag_pipeline_design",
        "data_migration",
        "integration_strategy",
    }
    assert expected_customs.issubset(custom_ids)


def test_all_sections_reference_valid_styles_in_corporate_blue():
    design_loader = DesignSystemLoader()
    profile = design_loader.get_profile("corporate_blue")

    sec_loader = SectionLibraryLoader()
    unresolved_styles = sec_loader.validate_against_design_profile(profile)

    # Must be zero unresolved style references across all sections
    assert unresolved_styles == []
