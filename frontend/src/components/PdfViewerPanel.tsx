import React, { useState } from 'react';
import type { DocumentContent, SectionContent } from '../types';
import { downloadDocx } from '../services/chatService';

interface PdfViewerPanelProps {
  isOpen: boolean;
  onClose: () => void;
  documentContent?: DocumentContent | null;
  onSelectSectionForEdit?: (sectionTitle: string) => void;
}

export const PdfViewerPanel: React.FC<PdfViewerPanelProps> = ({
  isOpen,
  onClose,
  documentContent,
  onSelectSectionForEdit,
}) => {
  const [isDownloading, setIsDownloading] = useState(false);

  if (!isOpen) return null;

  const handleDownload = async () => {
    if (!documentContent) return;
    setIsDownloading(true);
    try {
      await downloadDocx(documentContent);
    } catch (err) {
      console.error('Download error:', err);
      alert('Failed to download DOCX document. Please check backend connection.');
    } finally {
      setIsDownloading(false);
    }
  };

  const renderBlock = (block: any, idx: number) => {
    const btype = block.block_type || block.type;

    if (btype === 'paragraph') {
      return (
        <p key={idx} className="block-paragraph">
          {block.text}
        </p>
      );
    } else if (btype === 'bulleted_list') {
      return (
        <ul key={idx} className="block-list">
          {(block.items || []).map((item: string, i: number) => (
            <li key={i}>{item}</li>
          ))}
        </ul>
      );
    } else if (btype === 'numbered_list') {
      return (
        <ol key={idx} className="block-list">
          {(block.items || []).map((item: string, i: number) => (
            <li key={i}>{item}</li>
          ))}
        </ol>
      );
    } else if (btype === 'table') {
      const columns: string[] = block.columns || [];
      const rows: string[][] = block.rows || [];
      return (
        <table key={idx} className="block-table">
          <thead>
            <tr>
              {columns.map((col, cIdx) => (
                <th key={cIdx}>{col}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, rIdx) => (
              <tr key={rIdx}>
                {row.map((cell, cIdx) => (
                  <td key={cIdx}>{cell}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      );
    } else if (btype === 'callout') {
      const variant = (block.variant || 'note').toLowerCase();
      return (
        <div key={idx} className={`block-callout ${variant}`}>
          <div className="callout-header">
            <span>{variant === 'warning' ? '⚠️' : variant === 'tip' ? '💡' : 'ℹ️'}</span>
            <strong>{block.title || 'Note'}</strong>
          </div>
          <p>{block.text}</p>
        </div>
      );
    } else if (btype === 'diagram') {
      return (
        <div key={idx} className="block-diagram">
          <div className="diagram-header">
            📐 <strong>Diagram:</strong> {block.description || block.diagram_type}
          </div>
          {block.mermaid_code && (
            <pre className="diagram-code">{block.mermaid_code}</pre>
          )}
        </div>
      );
    }

    return null;
  };

  return (
    <aside className="pdf-viewer-panel">
      <div className="pdf-viewer-header">
        <div className="pdf-header-title">
          <span className="pdf-icon">📑</span>
          <h3>{documentContent ? 'POC Document Preview' : 'Document Viewer'}</h3>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          {documentContent && (
            <button
              type="button"
              className="download-docx-btn"
              onClick={handleDownload}
              disabled={isDownloading}
              title="Download publication-quality DOCX"
            >
              {isDownloading ? '⏳ Rendering DOCX...' : '⬇️ Download DOCX'}
            </button>
          )}
          <button
            type="button"
            className="close-panel-btn"
            onClick={onClose}
            title="Close viewer"
          >
            ✕
          </button>
        </div>
      </div>

      <div className="pdf-viewer-body" style={{ padding: 0 }}>
        {!documentContent ? (
          <div className="pdf-placeholder">
            <div className="placeholder-icon">📄</div>
            <p className="placeholder-text">POC Document Viewer</p>
            <span className="placeholder-subtext">
              Brainstorm in the chat with your AI Solutions Architect, then type{' '}
              <strong style={{ color: '#38bdf8' }}>/create</strong> to generate and preview your complete POC here.
            </span>
          </div>
        ) : (
          <div className="doc-view-container">
            <div className="doc-paper">
              {/* Document Banner */}
              <div className="doc-meta-banner">
                <div className="doc-title-row">
                  <div>
                    <h2>{documentContent.title}</h2>
                    {documentContent.subtitle && (
                      <p className="doc-subtitle">{documentContent.subtitle}</p>
                    )}
                  </div>
                </div>

                <div className="doc-meta-tags">
                  <span className="doc-meta-tag">
                    🎨 Design Profile: <strong>{documentContent.design_profile}</strong>
                  </span>
                  <span className="doc-meta-tag">
                    🏷️ Version: <strong>{documentContent.metadata?.version || '1.0'}</strong>
                  </span>
                  <span className="doc-meta-tag">
                    📅 Date: <strong>{documentContent.metadata?.date || new Date().toLocaleDateString()}</strong>
                  </span>
                  {documentContent.metadata?.client_name && (
                    <span className="doc-meta-tag">
                      🏢 Client: <strong>{documentContent.metadata.client_name}</strong>
                    </span>
                  )}
                </div>
              </div>

              {/* Table of Contents */}
              <div className="doc-toc">
                <h4>Table of Contents</h4>
                <div className="toc-pills">
                  {documentContent.sections.map((section) => (
                    <a
                      key={section.section_id}
                      href={`#sec-${section.section_id}`}
                      className="toc-pill"
                    >
                      {section.order}. {section.title}
                    </a>
                  ))}
                </div>
              </div>

              {/* Section List */}
              {documentContent.sections.map((section: SectionContent) => (
                <div
                  key={section.section_id}
                  id={`sec-${section.section_id}`}
                  className="doc-section-card"
                >
                  <div className="doc-section-header">
                    <h3>
                      {section.order}. {section.title}
                    </h3>
                    {onSelectSectionForEdit && (
                      <button
                        type="button"
                        className="section-edit-btn"
                        onClick={() => onSelectSectionForEdit(section.title)}
                        title="Click to prompt editing this section in chat"
                      >
                        ✏️ /edit this section
                      </button>
                    )}
                  </div>

                  <div className="section-blocks">
                    {section.blocks.map((block, bIdx) => renderBlock(block, bIdx))}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </aside>
  );
};
