import React, { useState } from 'react';
import type { RequirementData, ChatMessage, ChatSession } from '../types';
import { RequirementUpload } from '../components/RequirementUpload';
import { ChatArea } from '../components/ChatArea';
import { PdfViewerPanel } from '../components/PdfViewerPanel';
import { Sidebar } from '../components/Sidebar';
import { autoProcessRequirement, sendChatMessage, createPoc, editSection } from '../services/chatService';
import { INITIAL_DEMO_CHATS } from '../services/mockData';

export const ChatPage: React.FC = () => {
  const [sessions, setSessions] = useState<ChatSession[]>(INITIAL_DEMO_CHATS);
  // activeSessionId: null means we are in the "New Chat" creation mode
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState<boolean>(false);
  const [isPdfOpen, setIsPdfOpen] = useState<boolean>(true);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Derive active session
  const activeSession = sessions.find((s) => s.id === activeSessionId) || null;

  // Handler for starting a new chat
  const handleNewChat = () => {
    setActiveSessionId(null);
    setErrorMessage(null);
  };

  // Handler for selecting an existing chat
  const handleSelectSession = (id: string) => {
    setActiveSessionId(id);
    setErrorMessage(null);
  };

  // Handler for toggling pin status
  const handleTogglePin = (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setSessions((prev) =>
      prev.map((s) => (s.id === id ? { ...s, isPinned: !s.isPinned } : s))
    );
  };

  // Handler for submitting a requirement in New Chat mode
  const handleRequirementSubmit = async (data: RequirementData) => {
    setIsLoading(true);
    setErrorMessage(null);

    try {
      // Step 1: LLM automatically starts processing the requirement upon upload
      const result = await autoProcessRequirement(data);

      const title =
        result.project_understanding?.project_title ||
        (data.fileName
          ? data.fileName.replace(/\.[^/.]+$/, '').replace(/[_-]/g, ' ')
          : 'New POC Project');

      const newId = `chat-${Date.now()}`;
      // Step 2: Confirmation message provided in chat interface to start brainstorming
      const initialAiMessage: ChatMessage = {
        id: Date.now().toString(),
        sender: 'ai',
        content: result.initial_message,
        suggestedActions: [
          'Clarify Tech Stack',
          'Explore Cloud Architecture',
          'Review Constraints',
          '/create',
        ],
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };

      const newSession: ChatSession = {
        id: newId,
        title,
        timestamp: 'Just now',
        isPinned: false,
        requirement: data,
        ingestionResult: result.ingestion_result,
        projectUnderstanding: result.project_understanding,
        messages: [initialAiMessage],
      };

      setSessions((prev) => [newSession, ...prev]);
      setActiveSessionId(newId);
    } catch (err: any) {
      console.error('Requirement processing error:', err);
      setErrorMessage(err?.message || 'Error processing requirements with backend.');
    } finally {
      setIsLoading(false);
    }
  };

  // Handler for sending a message in the active chat
  const handleSendMessage = async (content: string) => {
    if (!activeSession) return;

    const userMsg: ChatMessage = {
      id: Date.now().toString(),
      sender: 'user',
      content,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };

    const updatedMessages = [...activeSession.messages, userMsg];

    // Optimistically update message in state
    setSessions((prev) =>
      prev.map((s) => (s.id === activeSession.id ? { ...s, messages: updatedMessages } : s))
    );
    setIsLoading(true);

    // Step 3: Check if the user issued the /create command
    if (content.trim().toLowerCase().startsWith('/create')) {
      if (!activeSession.projectUnderstanding) {
        const errorReply: ChatMessage = {
          id: (Date.now() + 1).toString(),
          sender: 'ai',
          content: '⚠️ Please provide requirements first before creating a POC.',
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        };
        setSessions((prev) =>
          prev.map((s) =>
            s.id === activeSession.id ? { ...s, messages: [...updatedMessages, errorReply] } : s
          )
        );
        setIsLoading(false);
        return;
      }

      try {
        const response = await createPoc(
          activeSession.projectUnderstanding,
          updatedMessages,
          content.trim()
        );

        const aiReply: ChatMessage = {
          id: (Date.now() + 1).toString(),
          sender: 'ai',
          content: response.summary_message,
          suggestedActions: [
            '/edit Executive Summary',
            '/edit Technical Architecture',
            '/edit POC Scope',
          ],
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        };

        setSessions((prev) =>
          prev.map((s) =>
            s.id === activeSession.id
              ? {
                  ...s,
                  blueprint: response.blueprint,
                  documentContent: response.document_content,
                  messages: [...updatedMessages, aiReply],
                }
              : s
          )
        );
        setIsPdfOpen(true);
      } catch (err: any) {
        console.error('POC creation error:', err);
        const errReply: ChatMessage = {
          id: (Date.now() + 1).toString(),
          sender: 'ai',
          content: `⚠️ Error generating POC document: ${err?.message || 'Server error'}`,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        };
        setSessions((prev) =>
          prev.map((s) =>
            s.id === activeSession.id ? { ...s, messages: [...updatedMessages, errReply] } : s
          )
        );
      } finally {
        setIsLoading(false);
      }
      return;
    }

    // Step 5: Check if the user issued the /edit command
    if (content.trim().toLowerCase().startsWith('/edit')) {
      if (!activeSession.documentContent) {
        const errorReply: ChatMessage = {
          id: (Date.now() + 1).toString(),
          sender: 'ai',
          content: '⚠️ Please generate the POC document first using `/create` before editing specific sections.',
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        };
        setSessions((prev) =>
          prev.map((s) =>
            s.id === activeSession.id ? { ...s, messages: [...updatedMessages, errorReply] } : s
          )
        );
        setIsLoading(false);
        return;
      }

      try {
        const response = await editSection(
          activeSession.documentContent,
          content.trim(),
          updatedMessages,
          activeSession.projectUnderstanding
        );

        const aiReply: ChatMessage = {
          id: (Date.now() + 1).toString(),
          sender: 'ai',
          content: response.summary_message,
          suggestedActions: [
            `/edit ${response.section_title}`,
            'Download DOCX',
          ],
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        };

        setSessions((prev) =>
          prev.map((s) =>
            s.id === activeSession.id
              ? {
                  ...s,
                  documentContent: response.document_content,
                  messages: [...updatedMessages, aiReply],
                }
              : s
          )
        );
        setIsPdfOpen(true);
      } catch (err: any) {
        console.error('Section edit error:', err);
        const errReply: ChatMessage = {
          id: (Date.now() + 1).toString(),
          sender: 'ai',
          content: `⚠️ Error editing section: ${err?.message || 'Server error'}`,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        };
        setSessions((prev) =>
          prev.map((s) =>
            s.id === activeSession.id ? { ...s, messages: [...updatedMessages, errReply] } : s
          )
        );
      } finally {
        setIsLoading(false);
      }
      return;
    }

    // Normal brainstorming conversation turn
    try {
      const response = await sendChatMessage(updatedMessages, activeSession.projectUnderstanding);
      const aiReply: ChatMessage = {
        id: (Date.now() + 1).toString(),
        sender: 'ai',
        content: response.reply,
        suggestedActions: response.suggestedActions,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };

      setSessions((prev) =>
        prev.map((s) =>
          s.id === activeSession.id ? { ...s, messages: [...updatedMessages, aiReply] } : s
        )
      );
    } catch (err) {
      console.error('Chat error:', err);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="app-shell">
      {/* Top Header */}
      <header className="app-header">
        <div className="header-left">
          <div className="logo-badge">POC</div>
          <div className="app-title">
            <h1>AI POC Generator</h1>
            <span className="app-subtitle">Requirements & Solutions Assistant</span>
          </div>
        </div>

        <div className="header-actions">
          {activeSession && (
            <>
              <button
                type="button"
                className={`header-btn ${isPdfOpen ? 'active' : ''}`}
                onClick={() => setIsPdfOpen((prev) => !prev)}
                title="Toggle PDF viewer panel"
              >
                📑 {isPdfOpen ? 'Hide PDF View' : 'Open PDF View'}
              </button>
              <button
                type="button"
                className="header-btn secondary"
                onClick={handleNewChat}
                title="Create a new chat"
              >
                + New Chat
              </button>
            </>
          )}
        </div>
      </header>

      {/* Main Layout: Sidebar on Left, Content on Right */}
      <div className="app-body">
        <Sidebar
          sessions={sessions}
          activeSessionId={activeSessionId}
          onSelectSession={handleSelectSession}
          onNewChat={handleNewChat}
          onTogglePin={handleTogglePin}
          isCollapsed={isSidebarCollapsed}
          onToggleCollapse={() => setIsSidebarCollapsed((prev) => !prev)}
        />

        <main className="app-main">
          {!activeSession ? (
            <div style={{ width: '100%' }}>
              {errorMessage && (
                <div style={{ maxWidth: '640px', margin: '20px auto 0', padding: '12px 16px', background: '#fef2f2', color: '#b91c1c', borderRadius: '8px', border: '1px solid #fecaca', fontSize: '14px' }}>
                  ⚠️ {errorMessage}
                </div>
              )}
              <RequirementUpload onSubmit={handleRequirementSubmit} />
            </div>
          ) : (
            <div className={`workspace-split ${isPdfOpen ? 'with-pdf' : 'full-chat'}`}>
              <ChatArea
                messages={activeSession.messages}
                requirement={activeSession.requirement}
                onSendMessage={handleSendMessage}
                isLoading={isLoading}
              />
              <PdfViewerPanel
                isOpen={isPdfOpen}
                onClose={() => setIsPdfOpen(false)}
                documentContent={activeSession.documentContent}
              />
            </div>
          )}
        </main>
      </div>
    </div>
  );
};
