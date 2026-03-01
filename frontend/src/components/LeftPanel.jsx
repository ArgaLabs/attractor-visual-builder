import { PALETTE, NODE_COLORS } from '../constants.js'
import { PRESETS } from '../presets.js'

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
}) {
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
