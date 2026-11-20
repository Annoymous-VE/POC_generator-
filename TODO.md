# POC Generator Implementation Roadmap & Checklist

> **Current Progress:** 100% complete of core workflow (Steps 1 through 5 fully implemented, connected, and verified).  
> **Target:** Interactive, human-in-the-loop POC generation workflow.

---

## Target Workflow Specification

1. **Ingest & Auto-Process:** User uploads a document (PDF/DOCX), image, or pastes text. The system automatically ingests and processes the content using the LLM to extract project understanding.
2. **Confirmation & Brainstorming Kickoff:** System posts an initial AI confirmation message into the chat summarizing key takeaways and inviting interactive brainstorming.
3. **Brainstorming & Gated Creation (`/create`):** User and LLM brainstorm technical stack, constraints, architecture, and scope. **Crucial rule:** The system will *never* start generating the POC document until the user explicitly issues the `/create` command. When `/create` is sent, it synthesizes the full conversation history + requirements into the document blueprint and generates the POC.
4. **Document Viewer Display:** The generated POC document is immediately displayed in the right-side viewer panel (rendered with structure, typography, diagrams, tables, and callouts, plus a download button for DOCX).
5. **Targeted Revision (`/edit`):** When the user wants changes in specific sections, they issue `/edit [section_name or description] <instructions>`. The system uses dedicated section editing tools to rewrite or refine only those target sections without regenerating the whole document.

---

## Implementation Phases & Checklist

### Phase 1: Frontend-Backend Connectivity & API Client (Remaining: 20%)
Establish live communication between the React frontend and FastAPI backend.

- [x] **1.1 Vite API Proxy Configuration**
  - Updated `frontend/vite.config.ts` to configure a dev proxy routing `/api` to `http://127.0.0.1:8000`.
- [x] **1.2 Real HTTP API Client Layer**
  - Implemented real API calls in `frontend/src/services/chatService.ts`:
    - `POST /api/ingest/auto-process-file` (multipart `FormData`)
    - `POST /api/ingest/auto-process-text` (JSON payload)
    - `POST /api/chat` (message, history, project understanding)
- [x] **1.3 Session & Document State Management**
  - Updated `frontend/src/types.ts` and `frontend/src/pages/ChatPage.tsx` with `projectUnderstanding`, `ingestionResult`, formatted messages, and action pills.

---

### Phase 2: Live LLM Integration (Gemini / LangChain) (Remaining: 30%)
Hook up the LLM (`GEMINI_API_KEY`) to power analysis, brainstorming, and structured synthesis.

- [x] **2.1 LLM Client Factory / Wrapper**
  - Implemented `GeminiService` in `backend/app/services/llm/gemini_service.py` with multi-model fallback (`gemini-flash-lite-latest`, `gemini-flash-latest`, `gemini-pro-latest`) and offline fast-fail.
- [x] **2.2 LLM-Powered Project Analyzer**
  - Upgraded `backend/app/services/planner/project_analyzer.py` with LLM structured JSON extraction and robust heuristic fallback.
- [ ] **2.3 LLM-Powered Section Content Generator**
  - Connect the LLM client to `SectionContentGenerator.generate_section` in `backend/app/services/content/section_content_generator.py` to dynamically produce grounded, high-quality section content following Section Definition guidelines.

---

### Phase 3: Auto-Ingestion & Chat Confirmation (Step 1 & Step 2) (Remaining: 0% - COMPLETE)
Connect the upload UI to the backend ingestion pipeline and trigger the brainstorming greeting.

- [x] **3.1 Wire Upload Form to Ingestion API**
  - `RequirementUpload.tsx` and `handleRequirementSubmit` in `ChatPage.tsx` post files or text chunks to `/api/ingest/auto-process-file` and `/api/ingest/auto-process-text`.
- [x] **3.2 Automatic LLM Analysis on Upload**
  - On upload, backend runs `project_analyzer.analyze()` to extract structured `ProjectUnderstanding`.
- [x] **3.3 AI Confirmation Greeting Generation**
  - Backend produces a structured confirmation greeting highlighting key project requirements and instructing the user to brainstorm and use `/create`.
  - Frontend renders this message with clean typography and clickable quick-prompt pills.

---

### Phase 4: Brainstorming & Strict `/create` Gated Generation (Step 3) (Remaining: 0% - COMPLETE)
Enable multi-turn brainstorming and enforce the rule that POC generation is strictly locked until `/create`.

- [x] **4.1 Interactive Brainstorming Endpoint (`/api/chat`)**
  - Upgraded `/api/chat` with Gemini LLM: contextual Senior Solutions Architect conversation, history awareness, and guardrails locking generation until `/create`.
- [x] **4.2 Slash Command Router & Gatekeeper**
  - Implemented command detection in frontend `ChatPage.tsx` and backend `routes.py`:
    - Checks if message starts with `/create`.
    - Natural language attempts to generate without `/create` are firmly rejected with an instruction to use `/create`.
- [x] **4.3 Context Fusion & Document Generation Pipeline**
  - Built `backend/app/services/planner/context_fusion.py` to synthesize all multi-turn brainstorming decisions into enriched `ProjectUnderstanding`.
  - Implemented `POST /api/create` endpoint: plans adaptive blueprint, validates rules, generates all sections, and returns structured `DocumentContent`.
  - Connected `createPoc` API call in frontend `chatService.ts` and `ChatPage.tsx`.

---

### Phase 5: Right-Side Document Viewer (Step 4) (Remaining: 0% - COMPLETE)
Replace the static PDF placeholder with a rich, interactive document viewer.

- [x] **5.1 Rich Document Viewer Component**
  - Upgraded `frontend/src/components/PdfViewerPanel.tsx` to a full interactive Document Viewer.
  - Renders:
    - Document header (Title, Subtitle, Client Name, Version, Date).
    - Table of Contents with jump-to-section navigation.
    - Content blocks: Paragraphs, Bulleted and Numbered lists, Callouts (Note, Warning, Tip, Important), Tables with styled borders and headers, and Mermaid Architecture/Data-flow diagrams.
- [x] **5.2 Synchronize Chat & Viewer State**
  - Populates document viewer as soon as `/create` finishes, and provides an inline `/edit` button on each section card.
- [x] **5.3 Export / Download Action**
  - Implemented `downloadDocx` calling `/api/render/docx` for one-click publication-quality DOCX download.

---

### Phase 6: Targeted Section Editing Tooling via `/edit` (Step 5) (Remaining: 0% - COMPLETE)
Implement pinpoint section rewriting via `/edit`.

- [x] **6.1 Command Parser for `/edit`**
  - Detects inputs starting with `/edit` (by section number, section ID, or title, e.g. `/edit Technical Architecture Add Redis caching`).
  - Rejects premature edits if the document has not yet been generated via `/create`.
- [x] **6.2 Backend Section Revision Service & Tool**
  - Implemented `POST /api/sections/edit` with section definition constraints, Gemini structured regeneration, and grounded fallback.
- [x] **6.3 Live Document Hot-Reload in Viewer**
  - Seamlessly updates the target section in `activeSession.documentContent` without regenerating the entire document.
  - AI confirms update in chat and suggests follow-up actions.

---

### Phase 7: Verification, Hardening & End-to-End Testing (Remaining: 80%)

- [ ] **7.1 Unit & Integration Tests**
  - Test command parsing (`/create`, `/edit`).
  - Test LLM fallback mechanisms when API key is missing or rate-limited.
  - Test section editor endpoint with invalid section IDs and malformed inputs.
- [ ] **7.2 End-to-End Manual Workflow Validation**
  - Ingest PDF requirement -> Verify LLM greeting.
  - Chat for 3 turns -> Verify document does NOT generate prematurely.
  - Send `/create` -> Verify POC renders in right panel with all sections and diagrams.
  - Send `/edit Scope Add mobile app out of scope` -> Verify only Scope section updates.
  - Click Download DOCX -> Verify formatted Word document downloads properly.
