import { useState } from 'react'

function StatusBadge({ status }) {
  const map = {
    completed: { label: 'Completed', cls: 'status-completed' },
    failed:    { label: 'Failed',    cls: 'status-failed' },
    cancelled: { label: 'Cancelled', cls: 'status-cancelled' },
    running:   { label: 'Running',   cls: 'status-running' },
  }
  const { label, cls } = map[status] || { label: status, cls: '' }
  return <span className={`output-status-badge ${cls}`}>{label}</span>
}

function CollapsibleSection({ title, defaultOpen = false, children }) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <div className="output-section">
      <button className="output-section-header" onClick={() => setOpen((p) => !p)}>
        <span>{title}</span>
        <svg
          width="14" height="14" viewBox="0 0 24 24" fill="none"
          stroke="currentColor" strokeWidth="2"
          style={{ transform: open ? 'rotate(180deg)' : 'rotate(0deg)', transition: 'transform 0.15s' }}
        >
          <polyline points="6 9 12 15 18 9" />
        </svg>
      </button>
      {open && <div className="output-section-body">{children}</div>}
    </div>
  )
}

// Format a context value for display
function ContextValue({ val }) {
  if (val === null || val === undefined) return <span className="ctx-null">null</span>
  if (typeof val === 'object') {
    return (
      <pre className="ctx-json">{JSON.stringify(val, null, 2)}</pre>
    )
  }
  const str = String(val)
  // Multi-line or long → scrollable block
  if (str.includes('\n') || str.length > 120) {
    return <pre className="ctx-text">{str}</pre>
  }
  return <span className="ctx-scalar">{str}</span>
}

const SKIP_KEYS = new Set(['goal'])

export default function PipelineOutput({ result, onClose }) {
  if (!result) return null

  const { id, status, duration, error, context, execution_order, events } = result

  // Pull out the primary output — prefer last_response, fall back to last tool stdout
  const primaryOutput = context?.last_response ?? context?.['tool.stdout'] ?? null

  // All context entries except goal (shown separately) and internal keys
  const contextEntries = Object.entries(context || {}).filter(([k]) => !SKIP_KEYS.has(k))

  const durationStr = duration != null ? `${duration.toFixed(1)}s` : null

  const handleCopy = (text) => {
    navigator.clipboard.writeText(text).catch(() => {})
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div
        className="modal output-modal"
        onClick={(e) => e.stopPropagation()}
        style={{ maxWidth: 720, width: '90vw' }}
      >
        {/* Header */}
        <div className="output-modal-header">
          <div className="output-modal-title">
            <StatusBadge status={status} />
            <span className="output-pipeline-id">{id}</span>
            {durationStr && <span className="output-duration">{durationStr}</span>}
          </div>
          <button className="modal-close" onClick={onClose}>×</button>
        </div>

        <div className="output-modal-body">
          {/* Error banner */}
          {error && (
            <div className="output-error-banner">
              <strong>Error:</strong> {error}
            </div>
          )}

          {/* Primary output — most important, shown open */}
          {primaryOutput != null ? (
            <CollapsibleSection title="Final Output" defaultOpen>
              <div className="output-primary-wrapper">
                <button
                  className="output-copy-btn"
                  onClick={() => handleCopy(String(primaryOutput))}
                  title="Copy to clipboard"
                >
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
                    <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
                  </svg>
                  Copy
                </button>
                <pre className="output-primary">{String(primaryOutput)}</pre>
              </div>
            </CollapsibleSection>
          ) : (
            <div className="output-empty-hint">
              No LLM output captured — the pipeline may use only tool nodes or ran in simulation mode.
            </div>
          )}

          {/* Execution path */}
          {execution_order?.length > 0 && (
            <CollapsibleSection title={`Execution Path (${execution_order.length} nodes)`} defaultOpen>
              <div className="output-exec-path">
                {execution_order.map((nid, i) => (
                  <span key={i} className="output-exec-node">
                    {nid}
                    {i < execution_order.length - 1 && (
                      <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                        <polyline points="9 18 15 12 9 6" />
                      </svg>
                    )}
                  </span>
                ))}
              </div>
            </CollapsibleSection>
          )}

          {/* Full context */}
          {contextEntries.length > 0 && (
            <CollapsibleSection title={`Context (${contextEntries.length} keys)`}>
              <table className="output-ctx-table">
                <tbody>
                  {contextEntries.map(([k, v]) => (
                    <tr key={k}>
                      <td className="ctx-key">{k}</td>
                      <td className="ctx-val"><ContextValue val={v} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </CollapsibleSection>
          )}

          {/* Event log */}
          {events?.length > 0 && (
            <CollapsibleSection title={`Event Log (${events.length} events)`}>
              <div className="output-event-log">
                {events.map((ev, i) => (
                  <div key={i} className="output-event-row">
                    <span className={`output-event-type ${ev.type}`}>{ev.type}</span>
                    <span className="output-event-data">
                      {ev.data?.node_id && <strong>{ev.data.node_id}</strong>}
                      {ev.data?.status && <span className="output-event-status"> · {ev.data.status}</span>}
                    </span>
                  </div>
                ))}
              </div>
            </CollapsibleSection>
          )}
        </div>
      </div>
    </div>
  )
}
