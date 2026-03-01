import { useState } from 'react'
import { NODE_LABELS, LLM_MODELS } from '../constants.js'

function ModelSelect({ value, onChange }) {
  return (
    <select className="field-select" value={value || ''} onChange={(e) => onChange(e.target.value)}>
      <option value="">Select model…</option>
      {LLM_MODELS.map((grp) => (
        <optgroup key={grp.group} label={grp.group}>
          {grp.options.map((m) => (
            <option key={m.id} value={m.id}>{m.label}</option>
          ))}
        </optgroup>
      ))}
    </select>
  )
}

function EdgeListItem({ edge, onSelect }) {
  const condText = edge.condition || 'no condition'
  return (
    <div className="edge-list-item" onClick={() => onSelect(edge.id)} title="Click to edit this edge">
      <span className="edge-list-label">→ {edge.target}</span>
      <span className="edge-list-condition">{condText}</span>
    </div>
  )
}

function EdgeList({ nodeId, edges, onSelectEdge, context }) {
  if (edges.length === 0) {
    return (
      <>
        <div className="edge-list-empty">No outgoing edges yet.</div>
        <div className="edge-list-add-hint">
          Use "Connect Nodes" in the left panel to draw edges from this node, then click each edge to set its condition.
        </div>
      </>
    )
  }
  return (
    <>
      <div className="edge-list">
        {edges.map((e) => (
          <EdgeListItem key={e.id} edge={e} onSelect={onSelectEdge} />
        ))}
      </div>
      {context === 'conditional' && (
        <div className="edge-list-add-hint">
          Click any edge above to set its condition. The engine evaluates conditions top-to-bottom and takes the first match.
        </div>
      )}
    </>
  )
}

function NodeProps({ data, onUpdate, onRename, onDelete, onSelectEdge, outgoingEdges, onChangeType }) {
  const [pendingId, setPendingId] = useState(data.id)

  const field = (label, key, type = 'text', extra = {}) => (
    <div className="field">
      <label className="field-label">{label}</label>
      <input
        className="field-input"
        type={type}
        value={data[key] ?? ''}
        onChange={(e) => onUpdate(data.id, key, type === 'number' ? (parseFloat(e.target.value) || 0) : e.target.value)}
        {...extra}
      />
    </div>
  )

  const textarea = (label, key, props = {}) => (
    <div className="field">
      <label className="field-label">{label}</label>
      <textarea
        className={`field-textarea${props.mono ? ' mono' : ''}`}
        value={data[key] ?? ''}
        onChange={(e) => onUpdate(data.id, key, e.target.value)}
        {...props}
      />
    </div>
  )

  return (
    <>
      {/* Identity */}
      <div className="prop-group">
        <div className="field">
          <label className="field-label">Node ID</label>
          <input
            className="field-input"
            type="text"
            value={pendingId}
            onChange={(e) => setPendingId(e.target.value)}
            onBlur={() => {
              if (pendingId !== data.id) onRename(data.id, pendingId)
            }}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                e.target.blur()
              }
            }}
          />
        </div>
        {field('Display Label', 'label')}
        <div className="field">
          <label className="field-label">Node Type</label>
          <select
            className="field-select"
            value={data.nodeType}
            onChange={(e) => onChangeType(data.id, e.target.value)}
          >
            {['start', 'codergen', 'conditional', 'human', 'tool', 'http', 'parallel', 'fan_in', 'manager', 'exit'].map(
              (t) => (
                <option key={t} value={t}>{NODE_LABELS[t] || t}</option>
              )
            )}
          </select>
        </div>
      </div>

      {/* Conditional routing */}
      {data.nodeType === 'conditional' && (
        <div className="prop-group">
          <div className="info-box">
            <p>
              <strong>How conditions work:</strong> This node routes the flow based on conditions you set on each
              outgoing edge. Draw edges to the possible next nodes, then click each edge to write a condition like{' '}
              <code style={{ fontSize: 11, background: '#fff', padding: '1px 4px', borderRadius: 3 }}>
                outcome=success
              </code>
              .
            </p>
          </div>
          <label className="field-label">Outgoing Edges</label>
          <EdgeList edges={outgoingEdges} onSelectEdge={onSelectEdge} context="conditional" />
        </div>
      )}

      {/* LLM / Manager prompt + MCP */}
      {(data.nodeType === 'codergen' || data.nodeType === 'manager') && (
        <div className="prop-group">
          {textarea('Prompt', 'prompt', {
            placeholder: 'The instruction sent to the LLM. Use $goal for variable expansion.',
          })}
          {data.nodeType === 'manager' && (
            <div className="field">
              <label className="field-label">Max Cycles</label>
              <input
                className="field-input"
                type="number"
                min="1"
                value={data.max_cycles ?? 3}
                onChange={(e) => onUpdate(data.id, 'max_cycles', parseInt(e.target.value) || 3)}
              />
              <div style={{ fontSize: 11, color: 'var(--text-tertiary)', marginTop: 5, lineHeight: 1.5 }}>
                How many observe → guard → steer passes to run. The guard hook can exit early at any cycle.
              </div>
            </div>
          )}
          {textarea('MCP Servers', 'mcp_servers', {
            mono: true,
            rows: 3,
            placeholder: 'One MCP server per line:\nnpx -y @modelcontextprotocol/server-filesystem /workspace\nhttp://localhost:3001',
          })}
          <div style={{ fontSize: 11, color: 'var(--text-tertiary)', marginTop: -8, marginBottom: 8, lineHeight: 1.5 }}>
            stdio: full command &nbsp;·&nbsp; HTTP: base URL
          </div>
        </div>
      )}

      {/* Tool / Shell */}
      {data.nodeType === 'tool' && (
        <div className="prop-group">
          {field('Shell Command', 'command', 'text', { placeholder: 'e.g. npm run build' })}
        </div>
      )}

      {/* HTTP Request */}
      {data.nodeType === 'http' && (
        <div className="prop-group">
          <div className="info-box">
            <p>
              <strong>HTTP Request</strong> calls an external URL and stores the response as{' '}
              <code style={{ fontSize: 11, background: '#fff', padding: '1px 4px', borderRadius: 3 }}>http.status_code</code>,{' '}
              <code style={{ fontSize: 11, background: '#fff', padding: '1px 4px', borderRadius: 3 }}>http.body</code>, and{' '}
              <code style={{ fontSize: 11, background: '#fff', padding: '1px 4px', borderRadius: 3 }}>http.json</code>.
              Use <code style={{ fontSize: 11, background: '#fff', padding: '1px 4px', borderRadius: 3 }}>{'${key}'}</code> to interpolate context.
            </p>
          </div>
          {field('URL', 'http_url', 'text', { placeholder: 'https://api.example.com/run' })}
          <div className="field">
            <label className="field-label">Method</label>
            <select
              className="field-select"
              value={data.http_method || 'GET'}
              onChange={(e) => onUpdate(data.id, 'http_method', e.target.value)}
            >
              {['GET', 'POST', 'PUT', 'PATCH', 'DELETE'].map((m) => (
                <option key={m} value={m}>{m}</option>
              ))}
            </select>
          </div>
          {textarea('Request Body (JSON)', 'http_body', {
            mono: true,
            placeholder: '{"prompt": "${goal}", "task": "validate"}',
          })}
          {textarea('Headers (JSON)', 'http_headers', {
            mono: true,
            placeholder: '{"Authorization": "Bearer ${API_TOKEN}"}',
          })}
        </div>
      )}

      {/* Outgoing edges (non-conditional) */}
      {data.nodeType !== 'conditional' && outgoingEdges.length > 0 && (
        <div className="prop-group">
          <label className="field-label">Outgoing Edges</label>
          <EdgeList edges={outgoingEdges} onSelectEdge={onSelectEdge} context="general" />
        </div>
      )}

      {/* Common settings */}
      <div className="prop-group">
        <div className="field">
          <label className="field-label">LLM Model Override</label>
          <ModelSelect value={data.llm_model} onChange={(v) => onUpdate(data.id, 'llm_model', v)} />
        </div>
        {field('Timeout', 'timeout', 'text', { placeholder: 'e.g. 900s, 15m' })}
        <div className="field">
          <label className="field-label">Max Retries</label>
          <input
            className="field-input"
            type="number"
            min="0"
            value={data.max_retries ?? 0}
            onChange={(e) => onUpdate(data.id, 'max_retries', parseInt(e.target.value) || 0)}
          />
        </div>
        {field('Retry Target Node', 'retry_target', 'text', { placeholder: 'Node ID to jump to on failure' })}
        <div className="checkbox-row">
          <input
            type="checkbox"
            id={`gg-${data.id}`}
            checked={!!data.goal_gate}
            onChange={(e) => onUpdate(data.id, 'goal_gate', e.target.checked)}
          />
          <label htmlFor={`gg-${data.id}`}>Goal Gate (blocks exit until satisfied)</label>
        </div>
      </div>

      <div className="prop-group">
        <button
          className="btn btn-danger"
          style={{ width: '100%', justifyContent: 'center' }}
          onClick={() => onDelete(data.id)}
        >
          Delete Node
        </button>
      </div>
    </>
  )
}

function EdgeProps({ data, sourceNodeType, onUpdate, onDelete }) {
  const isFromConditional = sourceNodeType === 'conditional'

  return (
    <>
      <div className="prop-group">
        <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text)', marginBottom: 4 }}>
          {data.source} → {data.target}
        </div>
        {isFromConditional && (
          <div style={{ fontSize: 11, color: 'var(--accent)', marginBottom: 'var(--spacing-sm)' }}>
            This edge leaves a Conditional node — set the condition below to control when this path is taken.
          </div>
        )}
        <div className="field">
          <label className="field-label">Label</label>
          <input
            className="field-input"
            type="text"
            value={data.label || ''}
            placeholder="Display name on the edge"
            onChange={(e) => onUpdate(data.id, 'label', e.target.value)}
          />
        </div>
        <div className="field">
          <label className="field-label">Condition</label>
          <input
            className="field-input"
            type="text"
            value={data.condition || ''}
            placeholder="e.g. outcome=success"
            onChange={(e) => onUpdate(data.id, 'condition', e.target.value)}
            style={isFromConditional ? { borderColor: 'var(--accent)', boxShadow: '0 0 0 3px rgba(79,70,229,0.08)' } : {}}
          />
          <div className="syntax-help">
            <div className="syntax-help-title">Condition syntax</div>
            <div className="syntax-example"><code>key=value</code> <span>Equals check</span></div>
            <div className="syntax-example"><code>key!=value</code> <span>Not-equals</span></div>
            <div className="syntax-example"><code>a=1 &amp;&amp; b=2</code> <span>AND checks</span></div>
            <div className="syntax-example"><code>outcome=success</code> <span>Node succeeded</span></div>
            <div className="syntax-example"><code>outcome=failure</code> <span>Node failed</span></div>
          </div>
        </div>
        <div className="field">
          <label className="field-label">Weight</label>
          <input
            className="field-input"
            type="number"
            min="0"
            value={data.weight || 0}
            onChange={(e) => onUpdate(data.id, 'weight', parseFloat(e.target.value) || 0)}
          />
        </div>
        <div className="field">
          <label className="field-label">Fidelity</label>
          <select
            className="field-select"
            value={data.fidelity || ''}
            onChange={(e) => onUpdate(data.id, 'fidelity', e.target.value)}
          >
            <option value="">Default (full history)</option>
            <option value="full">Full</option>
            <option value="truncate">Truncate</option>
            <option value="compact">Compact</option>
          </select>
        </div>
        <div className="checkbox-row">
          <input
            type="checkbox"
            id={`lr-${data.id}`}
            checked={!!data.loop_restart}
            onChange={(e) => onUpdate(data.id, 'loop_restart', e.target.checked)}
          />
          <label htmlFor={`lr-${data.id}`}>Loop Restart (re-run from start)</label>
        </div>
      </div>
      <div className="prop-group">
        <button
          className="btn btn-danger"
          style={{ width: '100%', justifyContent: 'center' }}
          onClick={() => onDelete(data.id)}
        >
          Delete Edge
        </button>
      </div>
    </>
  )
}

export default function RightPanel({
  selectedElement,
  onUpdateNode,
  onUpdateEdge,
  onRenameNode,
  onDeleteElement,
  onSelectEdge,
  outgoingEdges,
  onChangeNodeType,
}) {
  return (
    <div className="panel-right">
      <div className="panel-section" style={{ borderBottom: '1px solid var(--border-light)' }}>
        <div className="panel-title">Properties</div>
      </div>

      {!selectedElement ? (
        <div className="props-empty">
          <div className="props-empty-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
            </svg>
          </div>
          <p>Select a node or edge on the canvas to configure its properties.</p>
        </div>
      ) : selectedElement.type === 'node' ? (
        <NodeProps
          data={selectedElement.data}
          onUpdate={onUpdateNode}
          onRename={onRenameNode}
          onDelete={onDeleteElement}
          onSelectEdge={onSelectEdge}
          outgoingEdges={outgoingEdges}
          onChangeType={onChangeNodeType}
        />
      ) : (
        <EdgeProps
          data={selectedElement.data}
          sourceNodeType={selectedElement.sourceNodeType}
          onUpdate={onUpdateEdge}
          onDelete={onDeleteElement}
        />
      )}
    </div>
  )
}
