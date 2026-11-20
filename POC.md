# Implementation Brief: Universal POC Template Schema and Adaptive Document Planning

## 1. Project context

This project is a Proof of Concept (POC) generation system.

The existing input pipeline accepts different source formats, including:
- PDF and DOC/DOCX documents
- Images
- Plain-text chunks

The extraction layer converts those inputs into a uniform project-context representation. That normalized context is intended to give the AI a consistent understanding of the project regardless of the original input format.

The next implementation objective is to build a reusable document-planning foundation. The system must be able to generate different POC documents for different project types without forcing every project into the same fixed list of sections.

Examples of project types may include:
- AI automation
- RAG applications
- Database migration
- ERP implementation
- Data engineering and analytics
- Cloud infrastructure
- API and system integration

The output should remain visually consistent while its structure and content adapt to the project.

## 2. Main objective

Implement a **Universal POC Template System**.

The system must provide a central catalogue of reusable section definitions. Each definition must explain:
- What the section is for
- When it should be selected
- When it should be omitted
- What information it requires
- How the section should be written
- Which content blocks it may contain
- Which visual styles it should use
- Where it may sensibly appear in the document
- Which other sections it depends on or overlaps with

The LLM must inspect the normalized project context and the section catalogue, then produce a document blueprint containing only the relevant sections in a sensible order.

The backend must resolve the blueprint against the catalogue, generate or validate section content, and pass structured content to a deterministic document renderer.

**Do not implement one rigid template containing every section.** The catalogue is comprehensive; each generated document is selective.

## 3. Critical architectural principles

Keep these responsibilities separate.

### 3.1 Section Library

Defines the sections that the system knows how to use.

It contains reusable section definitions, selection guidance, writing guidance, content-block definitions, and references to styles.

### 3.2 Design System

Defines the visual rules centrally:
- Page dimensions and margins
- Fonts and font sizes
- Text colours and background colours
- Heading hierarchy
- Paragraph spacing and line spacing
- Lists and indentation
- Tables and cell padding
- Image and diagram placement
- Headers, footers, and page numbering
- Page-break behaviour

Section definitions should reference named styles rather than repeat raw formatting values.

### 3.3 Document Planner

Uses project context and the Section Library to decide:
- Which sections to include
- Which sections to exclude
- Which subsections are relevant
- Which sections should be merged to avoid repetition
- Whether a custom section is required
- The order of selected sections
- What project information each section needs

The planner produces a structured blueprint. It does not render a DOCX or invent visual formatting.

### 3.4 Content Generation

Generates content for the selected sections using:
- Normalized project context
- The selected section definition
- The blueprint's section-specific instructions
- Any relevant outputs from other sections

It must not invent facts to fill gaps. It should identify missing information, qualify assumptions, or request clarification where necessary.

### 3.5 Rendering

Converts validated structured content into a formatted document.

The renderer, not the LLM, is responsible for enforcing fonts, colours, spacing, table styling, margins, headers, footers, and page layout.

## 4. Required workflow

Implement the following workflow, adapting names to the repository's existing architecture rather than duplicating existing functionality.

1. **Inspect existing implementation**
   - Review the repository structure and current extraction/context pipeline.
   - Find the actual normalized context schema and existing interfaces.
   - Identify existing LLM provider/client abstractions, configuration, logging, error handling, and document-generation code.
   - Reuse existing components where appropriate.
   - Do not replace or redesign the existing extraction pipeline as part of this task.
   - Do not assume a framework, database, or package that is not present in the repository.

2. **Load the Universal POC Schema**
   - Load the Section Library and Design System from versioned configuration files.
   - Validate the configuration at application startup or when it is loaded.
   - Return actionable validation errors for malformed definitions.

3. **Analyze project context**
   - Consume the existing normalized context through its actual interface.
   - Produce a structured project-understanding object if the current context does not already provide equivalent information.
   - Capture project type, objectives, business problem, proposed solution, users, systems, data, integrations, constraints, security requirements, deliverables, success measures, timeline, risks, and unknowns where present.
   - Preserve source-grounded facts and distinguish them from assumptions or inferred information.

4. **Plan the document**
   - Give the planner the normalized project context and relevant Section Library definitions.
   - Ask it to select, exclude, order, merge, or propose sections.
   - Require machine-valid structured output conforming to the blueprint schema.
   - Validate every selected section ID and every referenced style.
   - Reject or repair invalid output through a bounded retry/repair mechanism.
   - Do not silently accept unknown section IDs or unsupported content-block types.

5. **Validate the plan**
   - Check required core coverage.
   - Check for irrelevant sections.
   - Detect duplicate or substantially overlapping sections.
   - Check dependencies and ordering constraints.
   - Check that the plan does not omit an important project-specific topic.
   - Permit a custom section only when the catalogue cannot adequately represent a real project requirement.
   - Record the reason for each selection and exclusion.

6. **Generate section content**
   - Generate each section using its definition and the project context.
   - Use the specified content-block types and required fields.
   - Preserve factual traceability to the provided context where possible.
   - Do not fabricate metrics, dates, technology choices, costs, compliance claims, or acceptance thresholds.
   - Mark missing inputs and assumptions explicitly.

7. **Validate generated content**
   - Validate the content structure against the selected section's allowed block types.
   - Check required fields, table columns, list items, diagram specifications, and references.
   - Check for contradictions and unnecessary repetition across sections.
   - Check that claims are supported by the project context or clearly labelled as assumptions.
   - Return validation issues in a structured form.

8. **Render the document**
   - Resolve named styles from the Design System.
   - Render the cover page and selected sections in blueprint order.
   - Support paragraphs, bullets, numbered lists, tables, images, diagrams, callouts, and other explicitly supported blocks.
   - Keep rendering deterministic: the same validated content and design configuration should produce materially consistent output.

9. **Final document validation**
   - Check that all selected sections were rendered.
   - Check heading hierarchy, page breaks, tables, image placement, headers, footers, and page numbering.
   - Report rendering warnings rather than silently dropping unsupported content.

## 5. Section classification

The Section Library must support three categories.

### 5.1 Core sections

These are common candidates for most POCs, but should not be treated as unconditionally mandatory. The planner may omit or rename one when it is genuinely irrelevant or when another section covers the same purpose.

Recommended initial core catalogue:

| Section ID | Suggested title | Purpose |
|---|---|---|
| `executive_summary` | Executive Summary | Concise overview of the project, proposed POC, and expected outcome |
| `poc_objectives` | POC Objectives | What the POC is intended to demonstrate or validate |
| `business_need` | Current Challenges / Business Need | Why the POC is needed and what problem it addresses |
| `proposed_solution` | Proposed Solution | The proposed approach at an appropriate level of detail |
| `poc_scope` | POC Scope | In-scope and out-of-scope boundaries |
| `deliverables_success_criteria` | Deliverables & Success Criteria | Expected outputs and how acceptance will be assessed |
| `conclusion` | Conclusion | Summary and logical next steps |

### 5.2 Conditional reusable sections

Include these when the project context supports them.

| Section ID | Suggested title | Typical selection signal |
|---|---|---|
| `technical_architecture` | Technical Architecture | Multiple components, infrastructure, or system boundaries |
| `technology_stack` | Technology Stack and Rationale | Technologies need to be identified and justified |
| `user_workflow` | User Workflow | Human users interact with the solution |
| `solution_workflow` | Solution Workflow | The solution has a meaningful sequence of processing steps |
| `data_flow` | Data Flow | Data moves between components or systems |
| `data_migration` | Data Migration Strategy | Existing data must be moved or transformed |
| `integration_strategy` | Integration Strategy | External systems, APIs, or platforms must connect |
| `security_considerations` | Security Considerations | Security, privacy, identity, or access controls are relevant |
| `validation_testing` | Validation & Testing | The POC needs defined tests or evaluation |
| `risks_dependencies` | Risks & Dependencies | Material risks, assumptions, or dependencies exist |
| `delivery_approach` | Delivery Approach | Work needs to be divided into phases or workstreams |
| `timeline` | Indicative Timeline | Dates, duration, or sequencing are sufficiently known |
| `resource_allocation` | Resource Allocation | Roles or effort allocation are relevant and known |
| `expected_benefits` | Expected Benefits | Expected business or operational value needs explanation |
| `future_enhancements` | Future Enhancements | There is a meaningful post-POC roadmap |
| `environment_deployment` | Environment & Deployment Model | Environments, deployment, hosting, or release approach matter |
| `functional_scope` | Functional Scope | The solution has several distinct capabilities to specify |
| `non_functional_requirements` | Non-Functional Requirements | Performance, availability, scalability, or reliability requirements matter |
| `cost_benefit` | Cost-Benefit Analysis | Costs and benefits are part of the decision |

### 5.3 Project-specific sections

The planner must be able to propose a custom section when no reusable section adequately covers an important project requirement.

Possible examples:
- `rag_pipeline_design`
- `ai_model_evaluation`
- `prompt_engineering_strategy`
- `database_schema_design`
- `erp_implementation_strategy`
- `cloud_infrastructure_design`
- `api_specification`
- `compliance_assessment`
- `model_monitoring`
- `data_quality_framework`

These are examples, not a hard-coded exhaustive list.

A custom section must:
- Have a unique ID with a safe, predictable naming convention.
- Include a clear title and purpose.
- Explain why existing sections are insufficient.
- Define selection rationale and required information.
- Define writing instructions.
- Use only supported content-block types.
- Reference existing Design System styles by default.
- Pass the same validation as a reusable section.
- Not introduce arbitrary fonts, colours, or spacing.

If a custom section becomes useful across multiple projects, it can later be promoted into the reusable Section Library through a deliberate review process.

## 6. Section definition schema

Create a formal, versioned schema for section definitions. Use JSON Schema or the project's existing validation approach. The following is a conceptual example; refine it into a valid schema and implementation.

```json
{
  "section_id": "technical_architecture",
  "title": "Technical Architecture",
  "category": "conditional",
  "description": "Explains the proposed solution's major technical components and their relationships.",
  "purpose": "Give stakeholders a clear understanding of the architecture.",
  "selection_rules": {
    "include_when": [
      "The solution has multiple technical components.",
      "System integration or infrastructure design is relevant."
    ],
    "exclude_when": [
      "The project is a simple process-only POC with no meaningful technical architecture."
    ],
    "priority": "high"
  },
  "required_information": [
    "proposed_components",
    "component_responsibilities",
    "system_relationships"
  ],
  "optional_information": [
    "hosting_model",
    "network_boundaries",
    "technology_choices"
  ],
  "writing_guidelines": {
    "tone": "professional and technically precise",
    "detail_level": "detailed",
    "instructions": [
      "Explain each major component and its responsibility.",
      "Describe how components interact.",
      "Explain technology choices only when supported by the project context.",
      "Do not invent infrastructure or implementation decisions."
    ]
  },
  "content_structure": [
    {
      "block_id": "architecture_overview",
      "type": "paragraph",
      "required": true,
      "purpose": "Introduce the architecture and its main design principles."
    },
    {
      "block_id": "architecture_diagram",
      "type": "diagram",
      "required": false,
      "purpose": "Show major components and their relationships."
    },
    {
      "block_id": "component_table",
      "type": "table",
      "required": true,
      "columns": [
        "Component",
        "Responsibility",
        "Technology"
      ],
      "purpose": "Describe the architecture components."
    }
  ],
  "style_reference": {
    "heading": "heading_1",
    "body": "body_default",
    "table": "standard_table",
    "diagram": "standard_diagram"
  },
  "ordering": {
    "preferred_after": [
      "proposed_solution"
    ],
    "preferred_before": [
      "poc_scope"
    ]
  },
  "dependencies": [],
  "overlap_with": [
    "technology_stack",
    "data_flow"
  ],
  "tags": [
    "technical",
    "architecture",
    "systems"
  ]
}
```

Important implementation notes:
- Define enums for category, priority, and content-block type.
- Make required and optional properties explicit.
- Define how unknown properties are handled.
- Define whether a section can contain nested subsections.
- Do not rely on free-form prompt instructions alone for structural validation.
- Keep section IDs stable even if display titles change.

## 7. Content-block types

Define a controlled catalogue of content-block types that the AI may use. Start with:

| Type | Use |
|---|---|
| `paragraph` | Explanatory prose |
| `bulleted_list` | Unordered points |
| `numbered_list` | Ordered steps |
| `table` | Structured comparisons, specifications, mappings, or criteria |
| `diagram` | Architecture, workflow, process, or relationship visual |
| `image` | Supplied or generated visual asset |
| `callout` | Important note, assumption, warning, or decision |
| `subsection` | Nested heading and its content |
| `code_block` | Technical configuration or code where appropriate |

Each type must have its own payload schema and renderer support.

Examples:

### Paragraph block

```json
{
  "type": "paragraph",
  "text": "The proposed solution will..."
}
```

### Bulleted list block

```json
{
  "type": "bulleted_list",
  "items": [
    "First point",
    "Second point"
  ]
}
```

### Table block

```json
{
  "type": "table",
  "columns": [
    "Feature",
    "Description"
  ],
  "rows": [
    ["Automated ingestion", "Accepts supported source files."],
    ["Context extraction", "Creates normalized project context."]
  ],
  "style_reference": "standard_table"
}
```

### Callout block

```json
{
  "type": "callout",
  "variant": "assumption",
  "title": "Assumption",
  "text": "The target environment will be provided by the client."
}
```

### Diagram block

```json
{
  "type": "diagram",
  "diagram_type": "architecture",
  "description": "Show the user interface, API, processing service, model provider, and storage components.",
  "nodes": [],
  "edges": [],
  "style_reference": "standard_diagram"
}
```

The diagram representation must be defined and validated. Do not let the renderer execute arbitrary markup or code produced by the LLM.

## 8. Document blueprint schema

The planner must return a document blueprint, not the final formatted document.

A conceptual example:

```json
{
  "schema_version": "1.0.0",
  "document": {
    "title": "AI Customer Support Automation POC",
    "subtitle": "Proof of Concept Proposal",
    "language": "en",
    "design_profile": "corporate_blue"
  },
  "planning_summary": {
    "project_type": "AI automation",
    "selection_rationale": "The project requires a support workflow, retrieval pipeline, model evaluation, and security controls."
  },
  "selected_sections": [
    {
      "section_id": "executive_summary",
      "order": 1,
      "selection_reason": "Provides the overview expected in a POC proposal.",
      "section_overrides": {}
    },
    {
      "section_id": "poc_objectives",
      "order": 2,
      "selection_reason": "The project has explicit outcomes to validate.",
      "section_overrides": {}
    },
    {
      "section_id": "technical_architecture",
      "order": 3,
      "selection_reason": "The solution has multiple technical components.",
      "section_overrides": {}
    },
    {
      "section_id": "rag_pipeline_design",
      "order": 4,
      "custom": true,
      "selection_reason": "The retrieval and grounding design is central and is not sufficiently covered by a generic architecture section.",
      "custom_definition": {}
    }
  ],
  "excluded_sections": [
    {
      "section_id": "data_migration",
      "reason": "The project does not involve migrating an existing dataset."
    }
  ],
  "missing_information": [],
  "assumptions": []
}
```

The final implementation must define a strict schema for this structure.

The planner should not return font sizes, raw colour values, page margins, or arbitrary style definitions. It should only reference an approved design profile and registered style names.

## 9. Design System specification

Create a central Design System configuration. The values below are proposed initial defaults based on the visual patterns observed in the three reference POC documents. They are not universal requirements and should be configurable through named design profiles.

### 9.1 Initial corporate-blue profile

| Element | Font | Size | Colour | Weight |
|---|---|---:|---|---|
| Cover title | Aptos Display | 26 pt | `#17365D` | Bold |
| Cover subtitle | Aptos | 13 pt | `#2F75B5` | Regular |
| Heading 1 | Aptos | 16 pt | `#17365D` | Bold |
| Heading 2 | Aptos | 12 pt | `#2F75B5` | Bold |
| Heading 3 | Aptos | 10.5 pt | `#0F6B78` | Bold |
| Body | Aptos | 10 pt | `#202B36` | Regular |
| Table header | Aptos | 9 pt | `#FFFFFF` | Bold |
| Table body | Aptos | 9 pt | `#202B36` | Regular |
| Footer | Aptos | 8 pt | `#666666` | Regular |

Suggested palette:
- Primary navy: `#17365D`
- Corporate blue: `#365F91`
- Secondary blue: `#2F75B5`
- Light blue: `#4F81BD`
- Teal accent: `#0F6B78`
- Body text: `#202B36`
- Muted text: `#666666`
- Page background: `#FFFFFF`

### 9.2 Page layout defaults

| Property | Initial value |
|---|---|
| Page size | A4 |
| Orientation | Portrait |
| Top margin | 0.65 in |
| Bottom margin | 0.65 in |
| Left margin | 0.65 in |
| Right margin | 0.65 in |
| Body alignment | Left |
| Cover title alignment | Center |
| Section heading alignment | Left |
| Diagram alignment | Center |
| Table width | Available content width |
| Page background | White |

### 9.3 Spacing defaults

Use a consistent measurement unit internally. Convert it explicitly in the renderer.

Suggested initial values:
- Heading 1: 18 pt before, 8 pt after
- Heading 2: 12 pt before, 6 pt after
- Heading 3: 10 pt before, 4 pt after
- Body paragraph: 1.15 line spacing, 6 pt after
- Table cell padding: 6 pt
- Lists: consistent hanging indent and spacing
- Diagrams: 8–12 pt spacing before and after

These values are starting defaults. Ensure they can be changed centrally without editing section definitions.

### 9.4 Named style references

At minimum, define:
- `cover_title`
- `cover_subtitle`
- `heading_1`
- `heading_2`
- `heading_3`
- `body_default`
- `body_emphasis`
- `bullet_list`
- `numbered_list`
- `standard_table`
- `standard_diagram`
- `callout_note`
- `callout_warning`
- `footer_default`

Define table header fill, border colour, border width, cell margins, row behaviour, and text alignment in the table style configuration.

### 9.5 Cover page

Support a configurable cover page containing:
- Document title
- Subtitle
- Client or project name, when known
- Prepared for, when known
- Prepared by, when known
- Version, when known
- Date, when known
- Optional relevant visual

Do not fabricate metadata. Omit unknown fields or mark them as pending according to product requirements.

### 9.6 Headers and footers

Support configurable:
- Header text or logo
- Footer text
- Page number
- Document title or project name
- First-page header/footer differences

Do not force decorative elements if they reduce readability.

## 10. Writing guidance

Every section definition should contain section-specific writing guidance. Avoid a single generic instruction for all sections.

Examples:

- **Executive Summary:** concise, stakeholder-friendly overview; describe the problem, proposed approach, expected outcome, and important caveats.
- **POC Objectives:** use measurable or verifiable objectives where the source provides enough information; do not invent targets.
- **Current Challenges:** describe the current state and its problems; distinguish confirmed facts from inferred pain points.
- **Proposed Solution:** explain the approach in logical stages; connect the solution to the identified challenges.
- **Technical Architecture:** explain components, responsibilities, boundaries, and interactions.
- **Technology Stack:** use a table with technology area, proposed technology, and rationale; do not assume a technology has been approved.
- **Security Considerations:** cover only relevant identity, access, data protection, privacy, and security controls supported by the context; identify unresolved controls.
- **POC Scope:** separate in-scope and out-of-scope items.
- **Deliverables & Success Criteria:** distinguish deliverables from acceptance criteria; use measurable criteria only when grounded.
- **Risks & Dependencies:** describe risk, impact, likelihood if known, mitigation, owner if known, and unresolved dependencies.
- **Timeline:** use phases, durations, dependencies, and outputs only where supported by the input.
- **Conclusion:** concise summary and next step; do not introduce new technical claims.

Use professional, clear, direct language. Avoid filler, exaggerated claims, repetitive conclusions, and unsupported certainty.

## 11. Selection and planning rules

Implement these rules in the planner prompt and enforce what can be enforced in code.

1. Core sections are default candidates, not blindly mandatory.
2. Include a conditional section only when the project context provides a meaningful reason.
3. Do not include a section merely because it exists in the library.
4. Do not omit a material project requirement just because no matching reusable section exists.
5. Create a custom section when needed, but prefer reusing or configuring an existing section.
6. Avoid duplicate coverage. Merge sections when their purposes substantially overlap.
7. Preserve a logical narrative: context and problem, objectives, solution, implementation detail, scope, validation, delivery, and conclusion as appropriate.
8. Apply section ordering preferences, but allow justified project-specific ordering.
9. Do not add sections solely to make the document longer.
10. Do not invent information to complete a section.
11. A missing detail should become a recorded gap, an explicit assumption, or a clarification request—not fabricated content.
12. Keep terminology consistent across the document.
13. Use only registered styles and supported content-block types.
14. Ensure the final blueprint is valid before content generation begins.

## 12. Overlap and dependency handling

Section definitions should optionally include:
- `preferred_after`
- `preferred_before`
- `dependencies`
- `overlap_with`
- `merge_guidance`

Examples:
- `technical_architecture` may overlap with `data_flow`.
- `technology_stack` may overlap with technology details in `technical_architecture`.
- `solution_workflow` may overlap with `user_workflow`, but one describes system processing while the other describes user actions.
- `validation_testing` may overlap with `deliverables_success_criteria`, but testing methods and acceptance outcomes should remain distinguishable.

The planner should decide whether to keep, merge, or cross-reference overlapping sections based on their actual purpose in the project.

Do not implement a simplistic fixed ordering that prevents legitimate variation. Use ordering preferences and validate the resulting sequence for consistency.

## 13. Suggested configuration layout

Adapt this to the repository's conventions. Avoid creating duplicate configuration files if equivalent structures already exist.

```text
templates/
├── schema/
│   ├── section-definition.schema.json
│   ├── document-blueprint.schema.json
│   ├── section-content.schema.json
│   └── design-system.schema.json
│
├── section-library/
│   ├── core-sections.json
│   ├── technical-sections.json
│   ├── data-sections.json
│   ├── ai-sections.json
│   ├── delivery-sections.json
│   └── business-sections.json
│
├── design-system/
│   ├── corporate-blue.json
│   ├── typography.json
│   ├── spacing.json
│   ├── page-layout.json
│   ├── tables.json
│   └── components.json
│
└── rules/
    ├── section-selection-rules.json
    └── ordering-rules.json
```

Keep a schema version and configuration version. Validate compatibility when loading configurations.

## 14. Backend module responsibilities

Use the repository's existing language, framework, and conventions. The following are logical responsibilities, not a requirement to use these exact filenames.

- `section_library_loader`: loads and validates section definitions.
- `design_system_loader`: loads and validates design profiles and style tokens.
- `project_analyzer`: converts normalized context into a structured project understanding, if needed.
- `document_planner`: asks the LLM to produce a blueprint.
- `blueprint_validator`: validates IDs, ordering, dependencies, categories, and style references.
- `section_content_generator`: generates content for each selected section.
- `content_validator`: validates blocks and checks for gaps or contradictions.
- `document_renderer`: renders validated content using the selected design profile.
- `document_validator`: checks the final document and returns warnings/errors.

Avoid putting all responsibilities into one large service or prompt.

## 15. LLM integration requirements

- Use the project's existing LLM abstraction/provider integration.
- Use structured output or function/schema-constrained output if supported by the existing provider.
- Validate model output server-side even when constrained output is enabled.
- Keep prompts and schema definitions versioned.
- Do not put the entire library into every prompt if it becomes large. Retrieve relevant section definitions based on project understanding, while ensuring the planner can discover custom-section needs.
- Keep a record of the selected sections and selection reasons for debugging and explainability.
- Use bounded retries for malformed output.
- Do not expose secrets, API keys, or sensitive source content in logs.
- Make model failures and validation failures explicit and recoverable.

## 16. Frontend integration

The existing frontend is being developed with React. Inspect the actual UI implementation before changing it.

The UI should eventually support:
- Viewing the project understanding generated from input sources.
- Viewing the proposed document outline.
- Seeing why sections were selected or excluded.
- Adding or removing sections before generation.
- Reordering sections.
- Editing section titles where permitted.
- Reviewing missing information and assumptions.
- Selecting an approved design profile.
- Previewing the generated document.
- Regenerating a section without regenerating the entire document, where supported.

Do not build an elaborate UI as a substitute for the backend schema and planner. First establish stable backend contracts. Then connect the UI to those contracts.

## 17. API and data-contract expectations

Inspect existing API conventions first. If endpoints are needed, keep the contracts explicit and versionable.

Potential operations:
- Retrieve available section definitions.
- Retrieve available design profiles.
- Submit project context for planning.
- Retrieve a document blueprint.
- Update/approve a blueprint.
- Generate section content.
- Validate section content.
- Render the document.
- Retrieve generation and validation status.

Use the existing authentication, error-response, and persistence patterns. Do not introduce a new database or API style without a clear need.

## 18. Validation and testing requirements

Add automated tests for at least the following.

### Configuration tests
- Valid section definitions load successfully.
- Missing required fields are rejected.
- Unknown content-block types are rejected.
- Unknown style references are rejected.
- Duplicate section IDs are rejected.
- Invalid category values are rejected.
- Invalid design tokens are rejected.

### Planner tests
Use representative project contexts:
1. AI support assistant with a RAG pipeline.
2. Database migration and reporting project.
3. ERP implementation and integration project.
4. Simple workflow automation project.

Verify that:
- Different projects produce different relevant outlines.
- Core sections are treated as candidates rather than unconditional output.
- Conditional sections are included only when justified.
- Project-specific sections can be proposed.
- Duplicate or overlapping sections are detected.
- Ordering is valid.
- Unknown section IDs are rejected or handled through the custom-section validation path.
- Missing information is recorded rather than invented.

Use deterministic mocked LLM outputs for unit tests. Do not make automated tests depend on live model responses.

### Content tests
- Each block conforms to its schema.
- Tables have valid columns and rows.
- Required content blocks are present.
- Unsupported blocks are rejected.
- Assumptions and unknowns remain explicit.
- Cross-section contradictions can be detected or flagged.

### Rendering tests
- Registered styles are applied.
- Heading hierarchy is correct.
- Page margins and page size match the selected design profile.
- Tables use the configured styles.
- Headers, footers, and page numbering render correctly.
- Long tables and headings behave sensibly across page breaks.
- Missing optional metadata does not break the cover page.
- The renderer handles empty optional sections and unsupported content safely.

## 19. Non-goals for this implementation

Unless the existing project already requires them, do not:
- Rebuild document, image, or text extraction.
- Hard-code one universal section sequence.
- Allow the LLM to control arbitrary Word formatting.
- Create a separate visual theme for every section.
- Force every possible section into every POC.
- Invent client names, dates, timelines, budgets, metrics, technology decisions, or security certifications.
- Add unnecessary infrastructure or services.
- Rewrite unrelated backend or frontend modules.
- Treat a generated document as valid merely because a DOCX/PDF file was successfully created.

## 20. Implementation sequence

Work in small, verifiable steps.

### Phase 1 — Repository assessment
1. Inspect the existing project structure.
2. Identify the normalized context schema and its source.
3. Identify current LLM and document-generation integrations.
4. Report the relevant existing modules and integration points.
5. Propose the smallest implementation plan that fits the current codebase.

Do not modify files until this assessment is complete.

### Phase 2 — Schema foundation
1. Define the Section Definition schema.
2. Define the Content Block schemas.
3. Define the Design System schema.
4. Define the Document Blueprint schema.
5. Add representative sample configurations.
6. Add schema validation and tests.

### Phase 3 — Initial section library and design profile
1. Add the recommended core sections.
2. Add the initial conditional sections.
3. Add a small initial set of project-specific examples for AI, data, and integration projects.
4. Add the corporate-blue design profile.
5. Ensure all section definitions reference registered styles.

Do not attempt to write an exhaustive library before proving the schema works.

### Phase 4 — Planner
1. Integrate the normalized project context.
2. Implement project understanding if required.
3. Implement LLM-based section selection and ordering.
4. Validate planner output.
5. Add custom-section handling.
6. Add representative mocked tests.

### Phase 5 — Content generation and validation
1. Generate content section by section.
2. Validate each content block.
3. Track unknowns, assumptions, and source support.
4. Add cross-section consistency checks.

### Phase 6 — Rendering
1. Connect the design profile to the existing renderer or implement the renderer if none exists.
2. Render cover page, headings, paragraphs, lists, tables, diagrams, headers, and footers.
3. Add output validation and rendering tests.

### Phase 7 — Frontend connection
1. Expose the blueprint and validation results through the existing API.
2. Display the outline and selection rationale in React.
3. Allow review and editing before rendering.
4. Connect generation and preview flows.

## 21. Acceptance criteria

The implementation is complete when:

- [ ] The existing normalized input context is consumed without breaking the extraction pipeline.
- [ ] A versioned Universal POC Template Schema exists.
- [ ] Section definitions are validated against a formal schema.
- [ ] The Section Library supports core, conditional, and project-specific sections.
- [ ] The Design System is centralised and versioned.
- [ ] Sections reference named styles rather than embedding arbitrary visual values.
- [ ] The planner produces a valid, ordered document blueprint.
- [ ] The planner can exclude irrelevant sections.
- [ ] The planner can propose and validate custom sections.
- [ ] Overlapping sections can be merged or cross-referenced.
- [ ] Content generation follows each section's writing and block instructions.
- [ ] Unsupported content structures and style references are rejected.
- [ ] Missing information and assumptions are represented explicitly.
- [ ] The renderer applies the selected design profile deterministically.
- [ ] Automated tests cover configuration, planning, content, and rendering.
- [ ] Existing application functionality remains intact.

## 22. Instructions to the coding agent

Before implementation:
1. Read the existing repository and identify the current architecture.
2. Find and understand the actual normalized context schema already produced by the extraction pipeline.
3. Identify existing conventions and reuse them.
4. Present a concise implementation plan with the files/modules to be added or changed.

During implementation:
1. Work incrementally.
2. Do not overwrite existing functionality without justification.
3. Keep schemas strict and versioned.
4. Keep LLM decisions separate from deterministic validation and rendering.
5. Add tests alongside each major component.
6. Keep configuration examples realistic and internally consistent.
7. Document assumptions and decisions.
8. Run the relevant tests and report their results.

At completion, report:
- What was implemented.
- Which files were created or modified.
- The schemas and configuration formats.
- How the planner uses the normalized context.
- How custom sections work.
- How styling is resolved.
- Which tests were run and their results.
- Any remaining limitations or decisions requiring human input.

**Do not stop after creating sample JSON files.** Implement the validated schema foundation and the working planner integration appropriate to the current repository. Do not claim the full pipeline is complete if content generation or rendering has not been implemented.
