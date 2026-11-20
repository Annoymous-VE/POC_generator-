export type RequirementType = 'text' | 'image' | 'document';

export interface RequirementData {
  type: RequirementType;
  text?: string;
  file?: File;
  fileName?: string;
  fileSize?: number;
}

export interface IngestionResult {
  source_type: string;
  filename?: string | null;
  extracted_content: string;
  metadata: Record<string, any>;
}

export interface ProjectUnderstanding {
  project_title?: string | null;
  project_type: string;
  business_problem: string;
  proposed_solution: string;
  target_users_or_systems: string[];
  core_capabilities: string[];
  integrations: string[];
  constraints: string[];
  security_requirements: string[];
  deliverables: string[];
  success_criteria: string[];
  timeline_info?: string | null;
  risks_and_unknowns: string[];
  factual_context: string;
  assumptions: string[];
  source_metadata: Record<string, any>;
}

export interface AutoProcessResponse {
  ingestion_result: IngestionResult;
  project_understanding: ProjectUnderstanding;
  initial_message: string;
}

export interface SelectedSection {
  section_id: string;
  title?: string | null;
  order: number;
  selection_reason: string;
  custom: boolean;
}

export interface DocumentBlueprint {
  document: {
    title: string;
    subtitle?: string | null;
    design_profile: string;
  };
  selected_sections: SelectedSection[];
  assumptions: string[];
  missing_information: string[];
}

export interface SectionContent {
  section_id: string;
  title: string;
  order: number;
  blocks: any[];
  assumptions: string[];
  missing_information: string[];
  source_references: string[];
}

export interface DocumentContent {
  title: string;
  subtitle?: string | null;
  design_profile: string;
  sections: SectionContent[];
  metadata: Record<string, any>;
  global_assumptions: string[];
  global_unknowns: string[];
}

export interface CreatePocResponse {
  blueprint: DocumentBlueprint;
  document_content: DocumentContent;
  summary_message: string;
}

export interface EditSectionResponse {
  document_content: DocumentContent;
  section_id: string;
  section_title: string;
  summary_message: string;
}

export interface ChatMessage {
  id: string;
  sender: 'user' | 'ai' | 'system';
  content: string;
  timestamp: string;
  suggestedActions?: string[];
}

export interface ChatSession {
  id: string;
  title: string;
  timestamp: string;
  isPinned: boolean;
  requirement: RequirementData | null;
  ingestionResult?: IngestionResult | null;
  projectUnderstanding?: ProjectUnderstanding | null;
  blueprint?: DocumentBlueprint | null;
  documentContent?: DocumentContent | null;
  messages: ChatMessage[];
}
