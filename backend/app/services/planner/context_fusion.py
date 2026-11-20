"""
Context Fusion Service.

Synthesizes multi-turn brainstorming conversation history and explicit user /create instructions
with the initial ProjectUnderstanding into an enriched project understanding model.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from app.schemas.project_understanding import ProjectUnderstanding
from app.services.llm.gemini_service import gemini_service


def enrich_project_understanding_from_history(
    project: ProjectUnderstanding,
    conversation_history: List[Dict[str, str]],
    create_command: str,
) -> ProjectUnderstanding:
    """
    Enriches ProjectUnderstanding using all brainstorming decisions and the /create command.
    """
    if not conversation_history and not create_command.strip():
        return project

    history_text = "\n".join(
        f"{turn.get('sender', 'user').capitalize()}: {turn.get('content', '')}"
        for turn in conversation_history[-10:]
        if turn.get('content')
    )

    if gemini_service.is_available() and len(history_text) > 20:
        system_instruction = (
            "You are a Senior Enterprise Architect. Update and enrich the base project understanding "
            "incorporating all clarifications, decisions, constraints, and architecture options "
            "agreed upon during the brainstorming conversation, as well as specific instructions in the /create command.\n"
            "Return ONLY valid JSON matching the ProjectUnderstanding schema without markdown formatting."
        )

        prompt = f"""BASE PROJECT UNDERSTANDING:
{project.model_dump_json(indent=2)}

BRAINSTORMING CONVERSATION HISTORY:
{history_text}

FINAL CREATION COMMAND:
{create_command}

Return updated JSON with the following structure:
{{
  "project_title": "string",
  "project_type": "string",
  "business_problem": "string",
  "proposed_solution": "string",
  "target_users_or_systems": ["list of users or systems"],
  "core_capabilities": ["list of key technical capabilities"],
  "integrations": ["list of systems/databases/APIs"],
  "constraints": ["list of constraints"],
  "security_requirements": ["list of security/compliance points"],
  "deliverables": ["list of tangible deliverables"],
  "success_criteria": ["list of measurable success metrics"],
  "timeline_info": "string",
  "risks_and_unknowns": ["list of risks or unknowns"],
  "assumptions": ["list of key assumptions"]
}}
"""
        response_text = gemini_service.generate(prompt=prompt, system_instruction=system_instruction, timeout=25.0)
        if response_text:
            clean_json = response_text.strip()
            if clean_json.startswith("```"):
                clean_json = re.sub(r"^```(?:json)?\n|\n```$", "", clean_json, flags=re.MULTILINE).strip()
            try:
                data = json.loads(clean_json)
                return ProjectUnderstanding(
                    project_title=data.get("project_title") or project.project_title,
                    project_type=data.get("project_type") or project.project_type,
                    business_problem=data.get("business_problem") or project.business_problem,
                    proposed_solution=data.get("proposed_solution") or project.proposed_solution,
                    target_users_or_systems=data.get("target_users_or_systems") or project.target_users_or_systems,
                    core_capabilities=data.get("core_capabilities") or project.core_capabilities,
                    integrations=data.get("integrations") or project.integrations,
                    constraints=data.get("constraints") or project.constraints,
                    security_requirements=data.get("security_requirements") or project.security_requirements,
                    deliverables=data.get("deliverables") or project.deliverables,
                    success_criteria=data.get("success_criteria") or project.success_criteria,
                    timeline_info=data.get("timeline_info") or project.timeline_info,
                    risks_and_unknowns=data.get("risks_and_unknowns") or project.risks_and_unknowns,
                    factual_context=project.factual_context + f"\n\n[Brainstorming Context]:\n{history_text[:2000]}",
                    assumptions=data.get("assumptions") or project.assumptions,
                    source_metadata=project.source_metadata,
                )
            except Exception:
                pass

    # Heuristic fallback enrichment
    enriched = project.model_copy(deep=True)
    clean_cmd = re.sub(r"^/create\s*", "", create_command, flags=re.IGNORECASE).strip()
    if clean_cmd:
        enriched.assumptions.append(f"Directive from creation command: {clean_cmd}")
        enriched.factual_context += f"\nDirective: {clean_cmd}"
    return enriched
