import React, { useState, useRef, useEffect } from 'react';
import type { ChatMessage, RequirementData } from '../types';

interface ChatAreaProps {
  messages: ChatMessage[];
  requirement: RequirementData | null;
  onSendMessage: (content: string) => void;
  isLoading: boolean;
}

export const ChatArea: React.FC<ChatAreaProps> = ({
  messages,
  requirement,
  onSendMessage,
  isLoading,
}) => {
  const [input, setInput] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  const handleSend = () => {
    if (!input.trim() || isLoading) return;
    onSendMessage(input.trim());
    setInput('');
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  // Helper to render markdown-like structures cleanly
  const renderFormattedText = (content: string) => {
    const lines = content.split('\n');
    const elements: React.ReactNode[] = [];
    let listBuffer: string[] = [];

    const flushList = (keyPrefix: string) => {
      if (listBuffer.length > 0) {
        elements.push(
          <ul key={`${keyPrefix}-list`}>
            {listBuffer.map((item, idx) => (
              <li key={idx}>{renderInlineMarkdown(item)}</li>
            ))}
          </ul>
        );
        listBuffer = [];
      }
    };

    lines.forEach((line, index) => {
      const trimmed = line.trim();
      if (trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
        listBuffer.push(trimmed.slice(2));
      } else {
        flushList(`flush-${index}`);
        if (trimmed.startsWith('> ')) {
          elements.push(
            <blockquote key={index}>
              {renderInlineMarkdown(trimmed.slice(2))}
            </blockquote>
          );
        } else if (trimmed) {
          elements.push(
            <p key={index}>
              {renderInlineMarkdown(trimmed)}
            </p>
          );
        }
      }
    });

    flushList('flush-final');
    return <div className="formatted-text">{elements}</div>;
  };

  // Inline markdown formatter for bold and code
  const renderInlineMarkdown = (text: string) => {
    // Regex splits by bold (**...**) or code (`...`)
    const parts = text.split(/(\*\*.*?\*\*|`.*?`)/g);
    return parts.map((part, i) => {
      if (part.startsWith('**') && part.endsWith('**')) {
        return <strong key={i}>{part.slice(2, -2)}</strong>;
      }
      if (part.startsWith('`') && part.endsWith('`')) {
        return <code key={i}>{part.slice(1, -1)}</code>;
      }
      return part;
    });
  };

  return (
    <div className="chat-area">
      {/* Requirement Context Banner */}
      {requirement && (
        <div className="requirement-banner">
          <span className="banner-icon">
            {requirement.type === 'document' ? '📄' : requirement.type === 'image' ? '🖼️' : '✍️'}
          </span>
          <div className="banner-content">
            <strong>Active Requirement:</strong>{' '}
            {requirement.type === 'text'
              ? `"${requirement.text?.slice(0, 70)}..."`
              : `${requirement.fileName} (${((requirement.fileSize || 0) / 1024).toFixed(1)} KB)`}
          </div>
          <span className="banner-tag">{requirement.type.toUpperCase()}</span>
        </div>
      )}

      {/* Message List */}
      <div className="messages-container">
        {messages.map((msg) => (
          <div key={msg.id} className={`message-row ${msg.sender}`}>
            <div className="message-avatar">
              {msg.sender === 'user' ? '👤' : msg.sender === 'ai' ? '🤖' : 'ℹ️'}
            </div>
            <div className="message-bubble">
              <div className="message-sender-title">
                {msg.sender === 'user' ? 'You' : msg.sender === 'ai' ? 'POC Assistant' : 'System'}
              </div>
              <div className="message-text">
                {renderFormattedText(msg.content)}
              </div>
              
              {/* Brainstorming Suggested Action Pills */}
              {msg.suggestedActions && msg.suggestedActions.length > 0 && (
                <div className="suggested-actions">
                  {msg.suggestedActions.map((action, idx) => (
                    <button
                      key={idx}
                      type="button"
                      className={`action-pill ${action === '/create' ? 'create-pill' : ''}`}
                      onClick={() => onSendMessage(action)}
                      disabled={isLoading}
                    >
                      {action === '/create' ? '⚡ /create (Generate POC)' : action}
                    </button>
                  ))}
                </div>
              )}

              <div className="message-time">{msg.timestamp}</div>
            </div>
          </div>
        ))}

        {isLoading && (
          <div className="message-row ai">
            <div className="message-avatar">🤖</div>
            <div className="message-bubble loading">
              <span className="typing-dot"></span>
              <span className="typing-dot"></span>
              <span className="typing-dot"></span>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input box */}
      <div className="chat-input-container">
        <textarea
          rows={2}
          placeholder="Ask questions, explore architecture, challenge assumptions... (or type /create)"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={isLoading}
        />
        <button
          type="button"
          className="send-button"
          onClick={handleSend}
          disabled={!input.trim() || isLoading}
        >
          Send
        </button>
      </div>
    </div>
  );
};
