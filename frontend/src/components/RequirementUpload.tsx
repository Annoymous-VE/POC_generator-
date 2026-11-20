import React, { useState } from 'react';
import type { RequirementData, RequirementType } from '../types';

interface RequirementUploadProps {
  onSubmit: (data: RequirementData) => void;
}

export const RequirementUpload: React.FC<RequirementUploadProps> = ({ onSubmit }) => {
  const [selectedType, setSelectedType] = useState<RequirementType>('document');
  const [textInput, setTextInput] = useState('');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setSelectedFile(e.target.files[0]);
      setError(null);
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (selectedType === 'text') {
      if (!textInput.trim()) {
        setError('Please enter your requirement text.');
        return;
      }
      onSubmit({
        type: 'text',
        text: textInput.trim(),
      });
    } else {
      if (!selectedFile) {
        setError(`Please select a ${selectedType === 'document' ? 'document (PDF, DOC, DOCX)' : 'image'} file.`);
        return;
      }
      onSubmit({
        type: selectedType,
        file: selectedFile,
        fileName: selectedFile.name,
        fileSize: selectedFile.size,
      });
    }
  };

  return (
    <div className="upload-container">
      <div className="upload-card">
        <div className="upload-header">
          <span className="badge">Step 1</span>
          <h2>Provide Requirements</h2>
          <p className="subtitle">
            Upload or paste the client requirements to begin the POC generation workflow.
          </p>
        </div>

        {/* Tab selection */}
        <div className="format-tabs">
          <button
            type="button"
            className={`tab-btn ${selectedType === 'document' ? 'active' : ''}`}
            onClick={() => { setSelectedType('document'); setSelectedFile(null); setError(null); }}
          >
            📄 Document (.pdf, .doc, .docx)
          </button>
          <button
            type="button"
            className={`tab-btn ${selectedType === 'image' ? 'active' : ''}`}
            onClick={() => { setSelectedType('image'); setSelectedFile(null); setError(null); }}
          >
            🖼️ Image (.png, .jpg, etc.)
          </button>
          <button
            type="button"
            className={`tab-btn ${selectedType === 'text' ? 'active' : ''}`}
            onClick={() => { setSelectedType('text'); setSelectedFile(null); setError(null); }}
          >
            ✍️ Text Chunk
          </button>
        </div>

        <form onSubmit={handleSubmit} className="upload-form">
          {selectedType === 'text' ? (
            <div className="input-group">
              <label htmlFor="requirement-text">Paste requirement notes or email text:</label>
              <textarea
                id="requirement-text"
                rows={8}
                placeholder="Example: We need a scalable document processing pipeline with OCR, vector search, and a summary dashboard..."
                value={textInput}
                onChange={(e) => setTextInput(e.target.value)}
              />
            </div>
          ) : (
            <div className="input-group">
              <label htmlFor="file-input">
                {selectedType === 'document' ? 'Choose Document File' : 'Choose Image File'}:
              </label>
              <div className="dropzone">
                <input
                  id="file-input"
                  type="file"
                  accept={
                    selectedType === 'document'
                      ? '.pdf,.doc,.docx,application/pdf,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document'
                      : 'image/png,image/jpeg,image/webp'
                  }
                  onChange={handleFileChange}
                />
                <div className="dropzone-label">
                  <div className="dropzone-icon">
                    {selectedType === 'document' ? '📁' : '📸'}
                  </div>
                  {selectedFile ? (
                    <div className="file-preview-info">
                      <strong>{selectedFile.name}</strong>
                      <span>({(selectedFile.size / 1024).toFixed(1)} KB)</span>
                    </div>
                  ) : (
                    <div>
                      <span>Click to browse or drop file here</span>
                      <small>
                        {selectedType === 'document'
                          ? 'Supported: PDF, DOC, DOCX'
                          : 'Supported: PNG, JPG, JPEG, WEBP'}
                      </small>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          {error && <div className="error-message">{error}</div>}

          <button type="submit" className="submit-btn">
            Proceed to Chat &rarr;
          </button>
        </form>
      </div>
    </div>
  );
};
