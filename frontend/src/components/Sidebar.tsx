import React from 'react';
import type { ChatSession } from '../types';

interface SidebarProps {
  sessions: ChatSession[];
  activeSessionId: string | null;
  onSelectSession: (id: string) => void;
  onNewChat: () => void;
  onTogglePin: (id: string, e: React.MouseEvent) => void;
  isCollapsed: boolean;
  onToggleCollapse: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  sessions,
  activeSessionId,
  onSelectSession,
  onNewChat,
  onTogglePin,
  isCollapsed,
  onToggleCollapse,
}) => {
  const pinnedSessions = sessions.filter((s) => s.isPinned);
  const recentSessions = sessions.filter((s) => !s.isPinned);

  const getSourceIcon = (session: ChatSession) => {
    if (!session.requirement) return '💬';
    switch (session.requirement.type) {
      case 'document':
        return '📄';
      case 'image':
        return '🖼️';
      case 'text':
        return '✍️';
      default:
        return '💬';
    }
  };

  return (
    <aside className={`chat-sidebar ${isCollapsed ? 'collapsed' : ''}`}>
      {/* Sidebar Header & Toggle */}
      <div className="sidebar-top">
        <button
          type="button"
          className="new-chat-btn"
          onClick={onNewChat}
          title="Start a new chat with requirement upload"
        >
          <span className="plus-icon">+</span>
          {!isCollapsed && <span>New Chat</span>}
        </button>

        <button
          type="button"
          className="collapse-toggle-btn"
          onClick={onToggleCollapse}
          title={isCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          {isCollapsed ? '▶' : '◀'}
        </button>
      </div>

      {!isCollapsed && (
        <div className="sidebar-content">
          {/* 1. Pinned Chats (Only appears if any chat is pinned) */}
          {pinnedSessions.length > 0 && (
            <div className="sidebar-section">
              <div className="section-title">
                <span>📌 PINNED</span>
                <span className="section-count">{pinnedSessions.length}</span>
              </div>
              <ul className="session-list">
                {pinnedSessions.map((session) => (
                  <li
                    key={session.id}
                    className={`session-item ${session.id === activeSessionId ? 'active' : ''}`}
                    onClick={() => onSelectSession(session.id)}
                  >
                    <span className="session-icon">{getSourceIcon(session)}</span>
                    <div className="session-info">
                      <div className="session-title">{session.title}</div>
                      <span className="session-date">{session.timestamp}</span>
                    </div>
                    <button
                      type="button"
                      className="pin-action-btn pinned"
                      onClick={(e) => onTogglePin(session.id, e)}
                      title="Unpin chat"
                    >
                      📌
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* 2. Recents Chats */}
          <div className="sidebar-section">
            <div className="section-title">
              <span>🕒 RECENTS</span>
              <span className="section-count">{recentSessions.length}</span>
            </div>
            {recentSessions.length === 0 ? (
              <div className="no-recents">No recent unpinned chats</div>
            ) : (
              <ul className="session-list">
                {recentSessions.map((session) => (
                  <li
                    key={session.id}
                    className={`session-item ${session.id === activeSessionId ? 'active' : ''}`}
                    onClick={() => onSelectSession(session.id)}
                  >
                    <span className="session-icon">{getSourceIcon(session)}</span>
                    <div className="session-info">
                      <div className="session-title">{session.title}</div>
                      <span className="session-date">{session.timestamp}</span>
                    </div>
                    <button
                      type="button"
                      className="pin-action-btn"
                      onClick={(e) => onTogglePin(session.id, e)}
                      title="Pin chat to top"
                    >
                      📌
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      )}

      {/* Footer / Status */}
      {!isCollapsed && (
        <div className="sidebar-footer">
          <span className="status-indicator"></span>
          <span>POC Generator v0.1</span>
        </div>
      )}
    </aside>
  );
};
