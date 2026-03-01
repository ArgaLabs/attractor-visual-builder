import { useRef } from 'react'
import { PALETTE, NODE_COLORS } from '../constants.js'
import { PRESETS } from '../presets.js'

function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1048576) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1048576).toFixed(1)} MB`
}

export default function LeftPanel({
  edgeMode,
  onAddNode,
  onToggleEdgeMode,
  onLoadPreset,
  graphName,
  onGraphNameChange,
  graphGoal,
  onGraphGoalChange,
  graphStylesheet,
  onGraphStylesheetChange,
  uploadedFiles,
  onUploadFile,
  onRemoveFile,
}) {
  const fileInputRef = useRef(null)

  const handleDrop = (e) => {
    e.preventDefault()
    e.currentTarget.classList.remove('drag-over')
    const files = Array.from(e.dataTransfer.files)
    files.forEach(onUploadFile)
  }

  const handleDragOver = (e) => {
    e.preventDefault()
    e.currentTarget.classList.add('drag-over')
  }

  const handleDragLeave = (e) => {
    e.currentTarget.classList.remove('drag-over')
  }
  return (
    <div className="panel-left">
      <div className="panel-section">
        <div className="panel-title">Nodes</div>
        <div className="node-list">
          {PALETTE.map((item) => (
            <div key={item.type} className="node-item" onClick={() => onAddNode(item.type)}>
              <div className="node-icon" style={{ background: NODE_COLORS[item.type] }}>
                {item.icon}
              </div>
              <div className="node-info">
                <div className="node-name">{item.name}</div>
                <div className="node-desc">{item.desc}</div>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="panel-section">
        <div className="panel-title">Use Cases</div>
        <div className="preset-list">
          {PRESETS.map((preset, i) => {
            const prevCategory = i > 0 ? PRESETS[i - 1].category : null
            const showCategory = preset.category !== prevCategory
            return (
              <div key={preset.id}>
                {showCategory && (
                  <div className="preset-category">{preset.category}</div>
                )}
                <div className="preset-item" onClick={() => onLoadPreset(preset)}>
                  <span className="preset-icon">{preset.icon}</span>
                  <div className="preset-info">
                    <div className="preset-name">{preset.name}</div>
                    <div className="preset-desc">{preset.description}</div>
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      </div>

      <div className="panel-section">
        <div className="panel-title">Connections</div>
        <button
          className={`btn${edgeMode ? ' btn-primary' : ''}`}
          onClick={onToggleEdgeMode}
          style={{ width: '100%', justifyContent: 'center' }}
        >
          {edgeMode ? (
            <>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <line x1="18" y1="6" x2="6" y2="18" />
                <line x1="6" y1="6" x2="18" y2="18" />
              </svg>
              Cancel
            </>
          ) : (
            <>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
                <polyline points="15 3 21 3 21 9" />
                <line x1="10" y1="14" x2="21" y2="3" />
              </svg>
              Connect Nodes
            </>
          )}
        </button>
        <p style={{ fontSize: 11, color: 'var(--text-tertiary)', marginTop: 8, lineHeight: 1.5 }}>
          Click a source node, then click a target node to draw an edge between them.
        </p>
      </div>

      <div className="panel-section">
        <div className="panel-title">Data Files</div>
        <p style={{ fontSize: 11, color: 'var(--text-tertiary)', marginBottom: 8, lineHeight: 1.5 }}>
          Upload CSV, JSON, or text files. Each file's path is injected into the pipeline context
          so your agents can read and process it.
        </p>

        {/* Drop zone */}
        <div
          className="upload-dropzone"
          onDrop={handleDrop}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onClick={() => fileInputRef.current?.click()}
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
            <polyline points="17 8 12 3 7 8" />
            <line x1="12" y1="3" x2="12" y2="15" />
          </svg>
          <span>Drop files here or click to browse</span>
          <input
            ref={fileInputRef}
            type="file"
            multiple
            style={{ display: 'none' }}
            onChange={(e) => Array.from(e.target.files).forEach(onUploadFile)}
          />
        </div>

        {/* Uploaded files list */}
        {uploadedFiles.length > 0 && (
          <div className="upload-file-list">
            {uploadedFiles.map((f) => (
              <div key={f.file_id} className="upload-file-row">
                <div className="upload-file-info">
                  <span className="upload-file-name" title={f.path}>{f.filename}</span>
                  <span className="upload-file-meta">{formatBytes(f.size)} · key: <code>{f.context_key}</code></span>
                </div>
                <button
                  className="upload-file-remove"
                  title="Remove file"
                  onClick={() => onRemoveFile(f.file_id)}
                >
                  ×
                </button>
              </div>
            ))}
          </div>
        )}

        {uploadedFiles.length > 0 && (
          <p style={{ fontSize: 11, color: 'var(--text-tertiary)', marginTop: 6, lineHeight: 1.5 }}>
            Reference files in your prompts using their context key, e.g.{' '}
            <code style={{ fontSize: 11 }}>{`{{${uploadedFiles[0].context_key}}}`}</code>.
          </p>
        )}
      </div>

      <div className="panel-section">
        <div className="panel-title">Pipeline Settings</div>
        <div className="field">
          <label className="field-label">Name</label>
          <input
            className="field-input"
            type="text"
            value={graphName}
            onChange={(e) => onGraphNameChange(e.target.value)}
          />
        </div>
        <div className="field">
          <label className="field-label">Goal</label>
          <textarea
            className="field-textarea"
            value={graphGoal}
            placeholder="What should this pipeline accomplish?"
            onChange={(e) => onGraphGoalChange(e.target.value)}
          />
        </div>
        <div className="field">
          <label className="field-label">Model Stylesheet</label>
          <textarea
            className="field-textarea mono"
            value={graphStylesheet}
            placeholder={'* { llm_model: claude-sonnet-4-5; }\n.heavy { llm_model: claude-opus-4-6; }'}
            onChange={(e) => onGraphStylesheetChange(e.target.value)}
          />
        </div>
      </div>
    </div>
  )
}
