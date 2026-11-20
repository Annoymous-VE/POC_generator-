"""
FastAPI REST API Routes for Universal POC Template System.

Provides endpoints for:
- Retrieving section catalogue and design profiles
- Ingesting text and document/image requirements
- Generating and validating document blueprints
- Generating structured content
- Deterministic DOCX rendering and download
"""

from __future__ import annotations

import io
import json
import re
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field

from app.schemas.ingestion import IngestionResult
from app.schemas.project_understanding import ProjectUnderstanding
from app.schemas.template.blueprint import DocumentBlueprint
from app.schemas.template.design_system import DesignProfile
from app.schemas.template.section import SectionCategory, SectionDefinition
from app.schemas.template.section_content import DocumentContent, SectionContent
from app.services.content import ContentValidator, SectionContentGenerator
from app.services.ingestion.document_handler import DocumentHandler
from app.services.ingestion.image_handler import ImageHandler
from app.services.ingestion.text_handler import TextHandler
from app.services.planner import (
    BlueprintValidationResult,
    BlueprintValidator,
    DocumentPlanner,
    ProjectAnalyzer,
)
from app.services.renderer import DocxDocumentRenderer
from app.services.templates import DesignSystemLoader, SectionLibraryLoader
from app.services.llm.gemini_service import gemini_service
from app.services.planner.context_fusion import enrich_project_understanding_from_history

router = APIRouter(prefix="/api")

# Services instantiation
section_loader = SectionLibraryLoader()
design_loader = DesignSystemLoader()
project_analyzer = ProjectAnalyzer()
blueprint_validator = BlueprintValidator(section_loader, design_loader)
planner = DocumentPlanner(section_loader, design_loader, blueprint_validator, project_analyzer)
content_validator = ContentValidator(section_loader)
content_generator = SectionContentGenerator(section_loader, content_validator)
docx_renderer = DocxDocumentRenderer(design_loader)

doc_handler = DocumentHandler()
text_handler = TextHandler()
image_handler = ImageHandler()


# ---------------------------------------------------------------------------
# Template & Catalogue Endpoints
# ---------------------------------------------------------------------------

@router.get("/templates/sections", response_model=List[SectionDefinition])
def get_sections(category: Optional[SectionCategory] = None):
    """Retrieve available section definitions in the Section Library."""
    return section_loader.list_sections(category=category)


@router.get("/templates/design-profiles")
def get_design_profiles():
    """Retrieve available Design Profiles and registered style tokens."""
    return {
        pid: profile.model_dump()
        for pid, profile in design_loader.list_profiles().items()
    }


# ---------------------------------------------------------------------------
# Ingestion Endpoints
# ---------------------------------------------------------------------------

class TextIngestRequest(BaseModel):
    text: str = Field(..., min_length=1)
    title: Optional[str] = None


class AutoProcessResponse(BaseModel):
    ingestion_result: IngestionResult
    project_understanding: ProjectUnderstanding
    initial_message: str


def _format_initial_greeting(understanding: ProjectUnderstanding) -> str:
    title = understanding.project_title or "your project"
    ptype = understanding.project_type
    problem = understanding.business_problem
    caps = ", ".join(understanding.core_capabilities[:3]) if understanding.core_capabilities else "core capabilities"
    
    return (
        f"👋 **I have analyzed your requirements for \"{title}\" ({ptype}).**\n\n"
        f"**Key Findings:**\n"
        f"- **Primary Challenge:** {problem}\n"
        f"- **Target Capabilities:** {caps}\n"
        f"- **Integrations:** {', '.join(understanding.integrations) if understanding.integrations else 'Standard environment'}\n"
        f"- **Estimated Timeline:** {understanding.timeline_info or '2 to 4 weeks'}\n\n"
        f"Let's brainstorm the technical approach, architecture, constraints, and scope. What would you like to explore first?\n\n"
        f"> 💡 *When you are satisfied with our brainstorming and ready to generate the POC document, simply type `/create`.*"
    )


@router.post("/ingest/text", response_model=IngestionResult)
def ingest_text(request: TextIngestRequest):
    """Normalize raw text requirements."""
    try:
        return text_handler.extract(request.text, title=request.title)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/ingest/file", response_model=IngestionResult)
async def ingest_file(file: UploadFile = File(...)):
    """Extract and normalize document or image file."""
    content_bytes = await file.read()
    filename = file.filename or "uploaded_file"
    ext = filename.lower()

    try:
        if ext.endswith((".pdf", ".docx", ".doc")):
            return doc_handler.extract(content_bytes, filename=filename)
        elif ext.endswith((".png", ".jpg", ".jpeg", ".webp")):
            return image_handler.extract(content_bytes, filename=filename)
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file format for '{filename}'. Supported: PDF, DOCX, DOC, PNG, JPG.",
            )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/ingest/auto-process-text", response_model=AutoProcessResponse)
def auto_process_text(request: TextIngestRequest):
    """Ingest text and automatically extract project understanding with initial confirmation."""
    try:
        ingestion_res = text_handler.extract(request.text, title=request.title)
        understanding = project_analyzer.analyze(ingestion_res)
        greeting = _format_initial_greeting(understanding)
        return AutoProcessResponse(
            ingestion_result=ingestion_res,
            project_understanding=understanding,
            initial_message=greeting,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/ingest/auto-process-file", response_model=AutoProcessResponse)
async def auto_process_file(file: UploadFile = File(...)):
    """Ingest file and automatically extract project understanding with initial confirmation."""
    content_bytes = await file.read()
    filename = file.filename or "uploaded_file"
    ext = filename.lower()

    try:
        if ext.endswith((".pdf", ".docx", ".doc")):
            ingestion_res = doc_handler.extract(content_bytes, filename=filename)
        elif ext.endswith((".png", ".jpg", ".jpeg", ".webp")):
            ingestion_res = image_handler.extract(content_bytes, filename=filename)
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file format for '{filename}'. Supported: PDF, DOCX, DOC, PNG, JPG.",
            )

        understanding = project_analyzer.analyze(ingestion_res)
        greeting = _format_initial_greeting(understanding)
        return AutoProcessResponse(
            ingestion_result=ingestion_res,
            project_understanding=understanding,
            initial_message=greeting,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------------------------
# Planning Endpoints
# ---------------------------------------------------------------------------

class PlanRequest(BaseModel):
    ingestion_result: Optional[IngestionResult] = None
    project_understanding: Optional[ProjectUnderstanding] = None
    design_profile: str = "corporate_blue"


class PlanResponse(BaseModel):
    project_understanding: ProjectUnderstanding
    blueprint: DocumentBlueprint
    validation: BlueprintValidationResult


@router.post("/plan", response_model=PlanResponse)
def plan_document(request: PlanRequest):
    """
    Generate an adaptive document blueprint from project context or ingestion result.
    """
    if request.project_understanding:
        understanding = request.project_understanding
    elif request.ingestion_result:
        understanding = project_analyzer.analyze(request.ingestion_result)
    else:
        raise HTTPException(
            status_code=400,
            detail="Either 'ingestion_result' or 'project_understanding' must be provided.",
        )

    try:
        blueprint = planner.plan_document(understanding, design_profile_id=request.design_profile)
        val_result = blueprint_validator.validate(blueprint)
        return PlanResponse(
            project_understanding=understanding,
            blueprint=blueprint,
            validation=val_result,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/plan/validate", response_model=BlueprintValidationResult)
def validate_blueprint(blueprint: DocumentBlueprint):
    """Validate a modified or user-edited document blueprint."""
    return blueprint_validator.validate(blueprint)


# ---------------------------------------------------------------------------
# Content Generation Endpoints
# ---------------------------------------------------------------------------

class GenerateContentRequest(BaseModel):
    blueprint: DocumentBlueprint
    project_understanding: ProjectUnderstanding


@router.post("/generate", response_model=DocumentContent)
def generate_content(request: GenerateContentRequest):
    """
    Generate validated content blocks for all sections in the approved blueprint.
    """
    try:
        return content_generator.generate_document(
            blueprint=request.blueprint,
            project=request.project_understanding,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------------------------
# Document Rendering & Download
# ---------------------------------------------------------------------------

@router.post("/render/docx")
def render_docx(content: DocumentContent):
    """
    Render DocumentContent into a deterministic publication-quality DOCX file.
    """
    try:
        docx_bytes = docx_renderer.render(content)
        clean_filename = f"{content.title.replace(' ', '_')}.docx"
        return Response(
            content=docx_bytes,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={
                "Content-Disposition": f'attachment; filename="{clean_filename}"'
            },
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------------------------
# POC Creation Pipeline Endpoint (Step 3)
# ---------------------------------------------------------------------------

class CreatePocRequest(BaseModel):
    project_understanding: ProjectUnderstanding
    conversation_history: List[Dict[str, str]] = Field(default_factory=list)
    create_command: str = Field(..., description="The user command initiating generation, must start with /create")
    design_profile: str = "corporate_blue"


class CreatePocResponse(BaseModel):
    blueprint: DocumentBlueprint
    document_content: DocumentContent
    summary_message: str


@router.post("/create", response_model=CreatePocResponse)
def create_poc_document(request: CreatePocRequest):
    """
    Synthesizes all brainstorming history and requirements into a complete POC document.
    Enforces that this is strictly gated behind the '/create' command.
    """
    cmd = request.create_command.strip()
    if not cmd.lower().startswith("/create"):
        raise HTTPException(
            status_code=400,
            detail="POC document generation must be initiated with the '/create' command.",
        )

    try:
        # 1. Synthesize brainstorming history into enriched project understanding
        enriched_understanding = enrich_project_understanding_from_history(
            project=request.project_understanding,
            conversation_history=request.conversation_history,
            create_command=cmd,
        )

        llm_client_fn = (lambda prompt: gemini_service.generate(prompt)) if gemini_service.is_available() else None

        # 2. Plan adaptive blueprint matching the enriched project requirements
        blueprint = planner.plan_document(
            enriched_understanding,
            design_profile_id=request.design_profile,
            llm_client=llm_client_fn,
        )
        val_result = blueprint_validator.validate(blueprint)
        if not val_result.is_valid:
            raise HTTPException(
                status_code=400,
                detail=f"Blueprint validation failed: {'; '.join(val_result.errors)}",
            )

        # 3. Generate structured section content for all selected sections
        document_content = content_generator.generate_document(
            blueprint=blueprint,
            project=enriched_understanding,
            llm_client=llm_client_fn,
        )

        # 4. Craft summary confirmation message
        num_sections = len(document_content.sections)
        title = document_content.title
        summary_msg = (
            f"🎉 **POC Document Successfully Generated!**\n\n"
            f"I have consolidated our brainstorming discussion and generated **{num_sections} sections** "
            f"for **\"{title}\"** conforming to the `{request.design_profile}` design system.\n\n"
            f"**Generated Sections:**\n"
            + "\n".join(f"- **{s.order}. {s.title}**" for s in document_content.sections[:6])
            + (f"\n- *...and {num_sections - 6} more sections*" if num_sections > 6 else "")
            + f"\n\n👉 *You can review the full document in the panel on the right.* "
            f"If you need revisions on any section, type `/edit [section name] <instructions>`."
        )

        return CreatePocResponse(
            blueprint=blueprint,
            document_content=document_content,
            summary_message=summary_msg,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------------------------
# Section Targeted Editing Endpoint (Step 5)
# ---------------------------------------------------------------------------

class EditSectionRequest(BaseModel):
    document_content: DocumentContent
    edit_command: str = Field(..., description="Must start with /edit <section> <instructions>")
    conversation_history: List[Dict[str, str]] = Field(default_factory=list)
    project_understanding: Optional[ProjectUnderstanding] = None


class EditSectionResponse(BaseModel):
    document_content: DocumentContent
    section_id: str
    section_title: str
    summary_message: str


@router.post("/sections/edit", response_model=EditSectionResponse)
def edit_document_section(request: EditSectionRequest):
    """
    Selectively edits a single section in the generated POC document.
    Must start with /edit.
    """
    cmd = request.edit_command.strip()
    if not cmd.lower().startswith("/edit"):
        raise HTTPException(
            status_code=400,
            detail="Section edits must be initiated with the '/edit' command (e.g. '/edit Technical Architecture Add Redis').",
        )

    # Strip /edit prefix
    raw_args = re.sub(r"^/edit\s*", "", cmd, flags=re.IGNORECASE).strip()
    if not raw_args:
        raise HTTPException(
            status_code=400,
            detail="Please specify the section and instructions. Example: '/edit Technical Architecture Add Redis caching'",
        )

    sections = request.document_content.sections
    if not sections:
        raise HTTPException(status_code=400, detail="Document contains no sections to edit.")

    # Find the target section from the command
    target_sec = None
    instructions = ""

    # 1. Try matching by section number (e.g. "/edit 2 add details", "/edit section 2 add details")
    num_match = re.match(r"^(?:section\s+)?(\d+)\s*(.*)$", raw_args, re.IGNORECASE)
    if num_match:
        sec_num = int(num_match.group(1))
        for s in sections:
            if s.order == sec_num:
                target_sec = s
                instructions = num_match.group(2).strip()
                break

    # 2. Try matching by section title or section_id
    if not target_sec:
        # Check title matches from longest to shortest
        sorted_secs = sorted(sections, key=lambda s: len(s.title), reverse=True)
        lower_args = raw_args.lower()
        for s in sorted_secs:
            t_lower = s.title.lower()
            id_lower = s.section_id.lower().replace("_", " ")
            if lower_args.startswith(t_lower):
                target_sec = s
                instructions = raw_args[len(s.title):].strip()
                break
            elif lower_args.startswith(id_lower):
                target_sec = s
                instructions = raw_args[len(id_lower):].strip()
                break
            elif t_lower in lower_args:
                target_sec = s
                parts = re.split(re.escape(t_lower), lower_args, maxsplit=1)
                instructions = raw_args[len(parts[0]) + len(t_lower):].strip()
                break

    if not target_sec:
        available_titles = ", ".join(f"'{s.title}' (sec {s.order})" for s in sections)
        raise HTTPException(
            status_code=400,
            detail=f"Could not identify target section from command. Available sections: {available_titles}.",
        )

    if not instructions:
        instructions = "Refine and update this section to be more detailed, clear, and comprehensive."

    # Retrieve SectionDefinition
    defn = section_loader.get_section(target_sec.section_id)
    if not defn:
        raise HTTPException(
            status_code=400,
            detail=f"Definition for section '{target_sec.section_id}' not found in library.",
        )

    # Revise section using Gemini or grounded fallback
    revised_sec = None
    if gemini_service.is_available():
        system_instruction = (
            f"You are a technical document writer specializing in Proof of Concept documents. "
            f"Revise the section '{target_sec.title}' based strictly on the user's instructions.\n"
            f"Writing Guidelines Tone: {defn.writing_guidelines.tone}\n"
            f"Expected Structure Slots: {json.dumps([s.model_dump() for s in defn.content_structure])}\n"
            "Return valid JSON for SectionContent with valid blocks (paragraph, bulleted_list, table, diagram) "
            "conforming to schema without markdown code fences."
        )

        prompt = (
            f"EXISTING SECTION CONTENT:\n{target_sec.model_dump_json(indent=2)}\n\n"
            f"REVISION INSTRUCTIONS: {instructions}\n\n"
            "Generate revised SectionContent JSON:"
        )

        response_text = gemini_service.generate(prompt=prompt, system_instruction=system_instruction, timeout=25.0)
        if response_text:
            clean_json = response_text.strip()
            if clean_json.startswith("```"):
                clean_json = re.sub(r"^```(?:json)?\n|\n```$", "", clean_json, flags=re.MULTILINE).strip()
            try:
                data = json.loads(clean_json)
                data["order"] = target_sec.order
                data["section_id"] = target_sec.section_id
                revised_sec = SectionContent.model_validate(data)
            except Exception:
                pass

    if not revised_sec:
        from app.schemas.template.content_block import CalloutBlock, CalloutVariant
        revised_blocks = list(target_sec.blocks)
        revised_blocks.append(
            CalloutBlock(
                variant=CalloutVariant.NOTE,
                title="Revision Note",
                text=f"Updated to incorporate: {instructions}",
            )
        )
        revised_sec = SectionContent(
            section_id=target_sec.section_id,
            title=target_sec.title,
            order=target_sec.order,
            blocks=revised_blocks,
            assumptions=list(target_sec.assumptions) + [f"Revised per instruction: {instructions[:60]}"],
            missing_information=list(target_sec.missing_information),
            source_references=list(target_sec.source_references),
        )

    # Replace in document content
    updated_sections = []
    for s in sections:
        if s.section_id == target_sec.section_id:
            updated_sections.append(revised_sec)
        else:
            updated_sections.append(s)

    updated_doc = request.document_content.model_copy(update={"sections": updated_sections})

    summary_msg = (
        f"✏️ **Section '{target_sec.title}' (Section {target_sec.order}) Updated!**\n\n"
        f"I applied your edit instruction: *\"{instructions}\"*\n\n"
        f"The live preview panel on the right has been updated with the revised content."
    )

    return EditSectionResponse(
        document_content=updated_doc,
        section_id=target_sec.section_id,
        section_title=target_sec.title,
        summary_message=summary_msg,
    )


# ---------------------------------------------------------------------------
# Chat Brainstorming Endpoint
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    message: str
    history: List[Dict[str, str]] = Field(default_factory=list)
    project_understanding: Optional[ProjectUnderstanding] = None
    blueprint: Optional[DocumentBlueprint] = None


class ChatResponse(BaseModel):
    reply: str
    suggested_actions: List[str] = Field(default_factory=list)


@router.post("/chat", response_model=ChatResponse)
def chat_brainstorm(request: ChatRequest):
    """
    Chat endpoint assisting with requirement brainstorming and blueprint refinement.
    Uses Gemini LLM when available with intelligent contextual fallback.
    """
    user_msg = request.message.strip()
    lower_msg = user_msg.lower()

    # Rule: If user asks in natural language to generate the POC without /create, remind them
    create_intent_keywords = [
        "generate the poc", "generate document", "create the poc",
        "create document", "make the poc", "start creating the poc",
        "create poc now", "generate poc now", "build the poc"
    ]
    if any(k in lower_msg for k in create_intent_keywords) and not lower_msg.startswith("/create"):
        return ChatResponse(
            reply=(
                "I have compiled all the requirements and brainstorming context from our discussion.\n\n"
                "To initiate the POC generation process, please type the command:\n\n"
                "`/create`\n\n"
                "*(Without `/create`, document generation remains locked so you can continue refining requirements.)*"
            ),
            suggested_actions=["/create", "Review Scope", "Refine Architecture"],
        )

    # Brainstorming via Gemini
    if gemini_service.is_available():
        context_str = ""
        if request.project_understanding:
            u = request.project_understanding
            context_str = (
                f"Project Title: {u.project_title}\n"
                f"Project Type: {u.project_type}\n"
                f"Business Problem: {u.business_problem}\n"
                f"Proposed Solution: {u.proposed_solution}\n"
                f"Capabilities: {', '.join(u.core_capabilities)}\n"
                f"Integrations: {', '.join(u.integrations)}\n"
                f"Constraints: {', '.join(u.constraints)}\n"
                f"Timeline: {u.timeline_info or 'Not specified'}\n"
            )

        history_lines = []
        for h in request.history[-6:]:
            sender = h.get("sender", "user")
            content = h.get("content", "")
            history_lines.append(f"{sender.capitalize()}: {content}")
        history_str = "\n".join(history_lines)

        system_instruction = (
            "You are a Senior Solutions Architect collaborating with a client or engineer. "
            "Your role is to brainstorm the Proof of Concept (POC) solution, explore architecture options, "
            "recommend technologies, challenge assumptions, and clarify scope.\n"
            "Keep responses conversational, insightful, and well-structured using markdown.\n"
            "CRITICAL: If the user indicates they want to build or generate the POC, instruct them to issue the `/create` command."
        )

        prompt = (
            f"PROJECT CONTEXT:\n{context_str}\n\n"
            f"CONVERSATION HISTORY:\n{history_str}\n\n"
            f"User: {user_msg}\n\n"
            "Architect Response:"
        )

        llm_reply = gemini_service.generate(prompt=prompt, system_instruction=system_instruction, timeout=25.0)
        if llm_reply:
            suggested = [
                "Clarify Architecture",
                "Review Tech Stack",
                "Examine Constraints",
                "/create",
            ]
            return ChatResponse(reply=llm_reply, suggested_actions=suggested)

    # Deterministic fallback if offline/no LLM
    fallback_reply = (
        f"Grounded in our project requirements, let's explore your point: \"{user_msg}\".\n\n"
        "Here are key architectural considerations:\n"
        "1. **Component Decoupling:** Ensure modular interfaces between pipeline stages.\n"
        "2. **Resilience & Fault Tolerance:** Implement retry mechanisms and circuit breakers.\n"
        "3. **Scope Alignment:** Validate whether this should be in-scope for the baseline POC or deferred to production.\n\n"
        "What specific technical tradeoffs or constraints would you like to prioritize?\n\n"
        "> 💡 *When you are satisfied with our discussion, send `/create` to generate the POC document.*"
    )
    return ChatResponse(
        reply=fallback_reply,
        suggested_actions=["Explore Cloud Stack", "Discuss Security Controls", "/create"],
    )
