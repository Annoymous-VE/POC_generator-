import type {
  RequirementData,
  ChatMessage,
  AutoProcessResponse,
  ProjectUnderstanding,
  CreatePocResponse,
  EditSectionResponse,
  DocumentContent,
} from '../types';

/**
 * Submits requirement to the backend auto-processing ingestion pipeline.
 * Extracts content, analyzes project requirements with LLM, and produces the initial confirmation greeting.
 */
export async function autoProcessRequirement(data: RequirementData): Promise<AutoProcessResponse> {
  if (data.type === 'text') {
    const response = await fetch('/api/ingest/auto-process-text', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        text: data.text || '',
        title: 'User Requirement Input',
      }),
    });

    if (!response.ok) {
      const errData = await response.json().catch(() => ({ detail: 'Text processing failed.' }));
      throw new Error(errData.detail || 'Failed to process text requirement.');
    }
    return response.json();
  } else {
    if (!data.file) {
      throw new Error('No file provided for upload.');
    }
    const formData = new FormData();
    formData.append('file', data.file);

    const response = await fetch('/api/ingest/auto-process-file', {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      const errData = await response.json().catch(() => ({ detail: 'File upload and processing failed.' }));
      throw new Error(errData.detail || 'Failed to upload and process file.');
    }
    return response.json();
  }
}

export interface ChatServiceResponse {
  reply: string;
  suggestedActions: string[];
}

/**
 * Sends chat message to backend chat endpoint for interactive brainstorming.
 */
export async function sendChatMessage(
  messages: ChatMessage[],
  projectUnderstanding?: ProjectUnderstanding | null
): Promise<ChatServiceResponse> {
  const lastUserMsg = messages[messages.length - 1]?.content || '';

  try {
    const historyPayload = messages.slice(0, -1).map((m) => ({
      sender: m.sender,
      content: m.content,
    }));

    const response = await fetch('/api/chat', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        message: lastUserMsg,
        history: historyPayload,
        project_understanding: projectUnderstanding || undefined,
      }),
    });

    if (response.ok) {
      const data = await response.json();
      return {
        reply: data.reply,
        suggestedActions: data.suggested_actions || [],
      };
    }
  } catch (err) {
    console.warn('Backend chat error, using local fallback:', err);
  }

  // Graceful fallback if backend is momentarily unreachable
  return {
    reply: `I have noted: "${lastUserMsg}". What specific technical constraints or architectural components should we establish next?\n\n*(Remember: type \`/create\` when you are ready to produce the POC)*`,
    suggestedActions: ['Clarify Architecture', 'Review Tech Stack', '/create'],
  };
}


/**
 * Initiates complete POC document creation based on brainstorming context and /create command.
 */
export async function createPoc(
  projectUnderstanding: ProjectUnderstanding,
  messages: ChatMessage[],
  command: string
): Promise<CreatePocResponse> {
  const historyPayload = messages.map((m) => ({
    sender: m.sender,
    content: m.content,
  }));

  const response = await fetch('/api/create', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      project_understanding: projectUnderstanding,
      conversation_history: historyPayload,
      create_command: command,
      design_profile: 'corporate_blue',
    }),
  });

  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: 'Failed to generate POC document.' }));
    throw new Error(err.detail || 'Failed to generate POC document.');
  }

  return response.json();
}


/**
 * Renders and triggers a browser download for the generated DOCX document.
 */
export async function downloadDocx(documentContent: DocumentContent): Promise<void> {
  const response = await fetch('/api/render/docx', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(documentContent),
  });

  if (!response.ok) {
    throw new Error('Failed to render DOCX document.');
  }

  const blob = await response.blob();
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `${documentContent.title.replace(/\s+/g, '_')}.docx`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  window.URL.revokeObjectURL(url);
}


/**
 * Edits a specific section in the document content via the /edit command.
 */
export async function editSection(
  documentContent: DocumentContent,
  command: string,
  messages: ChatMessage[],
  projectUnderstanding?: ProjectUnderstanding | null
): Promise<EditSectionResponse> {
  const historyPayload = messages.map((m) => ({
    sender: m.sender,
    content: m.content,
  }));

  const response = await fetch('/api/sections/edit', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      document_content: documentContent,
      edit_command: command,
      conversation_history: historyPayload,
      project_understanding: projectUnderstanding || undefined,
    }),
  });

  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: 'Failed to edit section.' }));
    throw new Error(err.detail || 'Failed to edit section.');
  }

  return response.json();
}
