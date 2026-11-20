"""
Project Analyzer Service.

Consumes normalized IngestionResult and constructs a structured ProjectUnderstanding
object through LLM extraction (Gemini) with deterministic heuristic fallbacks.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from app.schemas.ingestion import IngestionResult
from app.schemas.project_understanding import ProjectUnderstanding
from app.services.llm.gemini_service import gemini_service


class ProjectAnalyzer:
    """
    Analyzes normalized project text context into structured project attributes.
    """

    def analyze(
        self,
        ingestion_result: IngestionResult,
        override_type: Optional[str] = None,
        use_llm: bool = True,
    ) -> ProjectUnderstanding:
        """
        Extract structured project comprehension from an IngestionResult.
        Attempts LLM-based understanding first; falls back to deterministic extraction.
        """
        content = ingestion_result.extracted_content or ""
        metadata = ingestion_result.metadata or {}
        filename = ingestion_result.filename or ""

        if use_llm and gemini_service.is_available() and len(content.strip()) > 20:
            llm_result = self._analyze_with_llm(content, filename, ingestion_result, override_type)
            if llm_result:
                return llm_result

        return self._analyze_heuristic(ingestion_result, override_type)

    def _analyze_with_llm(
        self,
        content: str,
        filename: str,
        ingestion_result: IngestionResult,
        override_type: Optional[str] = None,
    ) -> Optional[ProjectUnderstanding]:
        """Uses Gemini to extract structured project understanding from text."""
        system_prompt = (
            "You are a Principal Solutions Architect. Analyze client project requirements "
            "and extract key architectural and project scoping parameters. "
            "Return ONLY valid JSON matching the requested keys, without markdown code fences."
        )

        prompt = f"""Analyze the following extracted project requirement:
Filename: {filename}
Requirement Content:
{content[:5000]}

Extract the following JSON structure:
{{
  "project_title": "string (clear, concise title)",
  "project_type": "string (e.g. 'RAG application', 'AI automation', 'Database migration', 'Workflow automation', 'Cloud infrastructure')",
  "business_problem": "string (core pain point or challenge)",
  "proposed_solution": "string (high-level proposed architecture / technical solution)",
  "target_users_or_systems": ["list of users or systems"],
  "core_capabilities": ["list of 3-5 key technical capabilities"],
  "integrations": ["list of systems/databases/APIs mentioned"],
  "constraints": ["list of technical or operational constraints"],
  "security_requirements": ["list of security/compliance points"],
  "deliverables": ["list of tangible deliverables"],
  "success_criteria": ["list of measurable success metrics"],
  "timeline_info": "string (estimated timeline)",
  "risks_and_unknowns": ["list of risks or missing information"],
  "assumptions": ["list of reasonable assumptions"]
}}
"""
        response_text = gemini_service.generate(prompt=prompt, system_instruction=system_prompt, timeout=25.0)
        if not response_text:
            return None

        # Clean markdown formatting if present
        clean_json = response_text.strip()
        if clean_json.startswith("```"):
            clean_json = re.sub(r"^```(?:json)?\n|\n```$", "", clean_json, flags=re.MULTILINE).strip()

        try:
            data = json.loads(clean_json)
            if override_type:
                data["project_type"] = override_type

            # If explicit markdown heading is present, use it for exact title fidelity
            inferred_heading = self._infer_title(content, filename)
            exact_title = inferred_heading if inferred_heading != "Proof of Concept Proposal" else (data.get("project_title") or inferred_heading)

            return ProjectUnderstanding(
                project_title=exact_title,
                project_type=data.get("project_type") or self._infer_project_type(content, filename),
                business_problem=data.get("business_problem") or self._extract_problem(content),
                proposed_solution=data.get("proposed_solution") or self._extract_solution(content),
                target_users_or_systems=data.get("target_users_or_systems") or ["Stakeholders", "Engineering Team"],
                core_capabilities=data.get("core_capabilities") or self._extract_capabilities(content),
                integrations=data.get("integrations") or self._extract_integrations(content),
                constraints=data.get("constraints") or ["Standard execution boundary"],
                security_requirements=data.get("security_requirements") or self._extract_security(content),
                deliverables=data.get("deliverables") or self._extract_deliverables(content),
                success_criteria=data.get("success_criteria") or self._extract_success_criteria(content),
                timeline_info=data.get("timeline_info") or self._extract_timeline(content),
                risks_and_unknowns=data.get("risks_and_unknowns") or self._extract_risks(content),
                factual_context=content[:4000],
                assumptions=data.get("assumptions") or ["Target environment will be provisioned by client"],
                source_metadata={
                    "source_type": ingestion_result.source_type,
                    "filename": filename,
                    **(ingestion_result.metadata or {}),
                },
            )
        except Exception:
            return None

    def _analyze_heuristic(
        self,
        ingestion_result: IngestionResult,
        override_type: Optional[str] = None,
    ) -> ProjectUnderstanding:
        """Deterministic fallback extraction using heuristic rules."""
        content = ingestion_result.extracted_content or ""
        metadata = ingestion_result.metadata or {}
        filename = ingestion_result.filename or ""

        title = self._infer_title(content, filename)
        project_type = override_type or self._infer_project_type(content, filename)
        business_problem = self._extract_problem(content)
        proposed_solution = self._extract_solution(content)
        core_capabilities = self._extract_capabilities(content)
        integrations = self._extract_integrations(content)
        security_requirements = self._extract_security(content)
        deliverables = self._extract_deliverables(content)
        success_criteria = self._extract_success_criteria(content)
        timeline_info = self._extract_timeline(content)
        risks_and_unknowns = self._extract_risks(content)

        return ProjectUnderstanding(
            project_title=title,
            project_type=project_type,
            business_problem=business_problem,
            proposed_solution=proposed_solution,
            target_users_or_systems=["Business Stakeholders", "Technical Team"],
            core_capabilities=core_capabilities,
            integrations=integrations,
            constraints=["Client infrastructure provisioning", "POC execution boundary"],
            security_requirements=security_requirements,
            deliverables=deliverables,
            success_criteria=success_criteria,
            timeline_info=timeline_info,
            risks_and_unknowns=risks_and_unknowns,
            factual_context=content[:4000],
            assumptions=["Target deployment environment will be provided by client"],
            source_metadata={
                "source_type": ingestion_result.source_type,
                "filename": filename,
                **metadata,
            },
        )

    def _infer_title(self, content: str, filename: str) -> str:
        headings = re.findall(r"^\s*#\s+(.+)$", content, re.MULTILINE)
        for h in headings:
            clean_h = h.strip()
            if clean_h.lower().startswith("ingestion:"):
                continue
            return clean_h

        for h in headings:
            clean_h = h.strip()
            if clean_h.lower().startswith("ingestion:"):
                sub = re.sub(r"^ingestion:\s*", "", clean_h, flags=re.IGNORECASE).strip()
                if sub and sub.lower() not in ("client requirements (plain text)", "user requirement input", "requirement input"):
                    return sub

        if filename and not filename.lower().startswith("ingestion:"):
            clean_name = re.sub(r"\.[^.]+$", "", filename)
            clean_name = re.sub(r"[_\-]+", " ", clean_name)
            return clean_name.title()

        lines = [line.strip() for line in content.splitlines() if line.strip()]
        for line in lines:
            if not line.startswith(("#", "-", "*", ">", "==")):
                if 5 < len(line) < 80:
                    return line
        return "Proof of Concept Proposal"

    def _infer_project_type(self, content: str, filename: str) -> str:
        text = f"{filename} {content}".lower()
        if any(k in text for k in ["rag", "retrieval", "vector", "embedding", "chunking", "knowledge base"]):
            return "RAG application"
        if any(k in text for k in ["llm", "ai model", "agent", "prompt engineering", "nlp"]):
            return "AI automation"
        if any(k in text for k in ["migration", "database migration", "schema conversion", "etl", "warehouse"]):
            return "Database migration"
        if any(k in text for k in ["integration", "api gateway", "webhook", "rest api", "endpoint"]):
            return "API & System integration"
        if any(k in text for k in ["cloud", "aws", "azure", "kubernetes", "infra"]):
            return "Cloud infrastructure"
        if any(k in text for k in ["erp", "sap", "salesforce", "crm"]):
            return "ERP implementation"
        return "Workflow automation"

    def _extract_problem(self, content: str) -> str:
        match = re.search(
            r"(?:##+\s*(?:current\s+challenges|problem|background|need|pain\s*points)[^\n]*\n)([\s\S]*?)(?=\n##|\Z)",
            content,
            re.IGNORECASE,
        )
        if match:
            text = match.group(1).strip()
            return text[:500] if text else "Manual operational bottlenecks and lack of automated scaling."
        return "Current operational processes encounter manual bottlenecks and require modern technical demonstration."

    def _extract_solution(self, content: str) -> str:
        match = re.search(
            r"(?:##+\s*(?:proposed\s+solution|solution|approach|architecture)[^\n]*\n)([\s\S]*?)(?=\n##|\Z)",
            content,
            re.IGNORECASE,
        )
        if match:
            text = match.group(1).strip()
            return text[:500] if text else "An automated software solution implementing modern services."
        return "A targeted Proof of Concept demonstrating core automation and architectural capabilities."

    def _extract_capabilities(self, content: str) -> List[str]:
        capabilities = []
        bullets = re.findall(r"^\s*[-*•]\s+(.+)$", content, re.MULTILINE)
        if bullets:
            capabilities.extend([b.strip() for b in bullets[:5]])
        if not capabilities:
            capabilities = ["Automated ingestion and normalization", "Interactive reasoning and validation"]
        return capabilities

    def _extract_integrations(self, content: str) -> List[str]:
        integrations = []
        text = content.lower()
        if "postgresql" in text or "postgres" in text:
            integrations.append("PostgreSQL Database")
        if "azure" in text:
            integrations.append("Azure Cloud Services")
        if "aws" in text:
            integrations.append("AWS Cloud Infrastructure")
        if "rest" in text or "api" in text:
            integrations.append("RESTful APIs")
        if not integrations:
            integrations = ["Client Target Systems"]
        return integrations

    def _extract_security(self, content: str) -> List[str]:
        security = []
        text = content.lower()
        if "encryption" in text or "tls" in text or "ssl" in text:
            security.append("TLS encryption in transit and AES-256 at rest")
        if "auth" in text or "oauth" in text or "iam" in text or "jwt" in text:
            security.append("Role-based identity and access management (IAM)")
        if "pii" in text or "privacy" in text or "gdpr" in text:
            security.append("Data privacy controls and PII masking")
        if not security:
            security = ["Standard credential isolation and network boundary access controls"]
        return security

    def _extract_deliverables(self, content: str) -> List[str]:
        return [
            "Proof of Concept application code repository",
            "Deployed sandbox demonstration environment",
            "Technical evaluation and recommendations report",
        ]

    def _extract_success_criteria(self, content: str) -> List[str]:
        return [
            "Functional validation of core pipeline capabilities",
            "Demonstrated performance within target latency parameters",
            "Stakeholder approval of the proposed architecture",
        ]

    def _extract_timeline(self, content: str) -> Optional[str]:
        match = re.search(r"(\d+[\s\-]*(?:weeks?|months?|sprints?))", content, re.IGNORECASE)
        if match:
            return f"Estimated duration: {match.group(1)}"
        return "Estimated duration: 2 to 4 weeks"

    def _extract_risks(self, content: str) -> List[str]:
        return [
            "Prerequisite client credentials and environment access delays",
            "Availability of representative sample datasets",
        ]
