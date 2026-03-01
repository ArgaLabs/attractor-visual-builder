function formatDuration(seconds) {
  if (seconds < 60) return `${seconds}s`
  if (seconds < 3600) return `${Math.round(seconds / 60)}m`
  if (seconds < 86400) return `${(seconds / 3600).toFixed(1)}h`
  return `${(seconds / 86400).toFixed(1)}d`
}

function formatRelativeTime(ts) {
  if (!ts) return '—'
  const diff = ts - Date.now() / 1000
  if (diff <= 0) return 'now'
  if (diff < 60) return `in ${Math.round(diff)}s`
  if (diff < 3600) return `in ${Math.round(diff / 60)}m`
  return `in ${(diff / 3600).toFixed(1)}h`
}

function timeRemaining(expiresAt) {
  const diff = expiresAt - Date.now() / 1000
  if (diff <= 0) return 'expired'
  return formatDuration(Math.round(diff)) + ' left'
}

const STATUS_COLORS = {
  active: 'var(--green)',
  completed: 'var(--text-tertiary)',
  cancelled: 'var(--red)',
}

function StatusBadge({ status }) {
  return (
    <span
      className="sched-status"
      style={{ color: STATUS_COLORS[status] ?? 'var(--text-secondary)' }}
    >
      {status === 'active' && (
        <span className="sched-pulse" />
      )}
      {status}
    </span>
  )
}

export default function SchedulePanel({ schedules, onCancel, onClose }) {
  if (schedules.length === 0) return null

  return (
    <div className="schedule-panel">
      <div className="schedule-panel-header">
        <span>Schedules</span>
        <button className="modal-close" onClick={onClose} title="Close">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <line x1="18" y1="6" x2="6" y2="18" />
            <line x1="6" y1="6" x2="18" y2="18" />
          </svg>
        </button>
      </div>

      {schedules.map((s) => (
        <div key={s.id} className="schedule-row">
          <div className="schedule-row-top">
            <StatusBadge status={s.status} />
            <span className="schedule-row-id">{s.id}</span>
            {s.status === 'active' && (
              <button
                className="btn btn-danger"
                style={{ fontSize: 11, padding: '3px 10px', marginLeft: 'auto' }}
                onClick={() => onCancel(s.id)}
              >
                Cancel
              </button>
            )}
          </div>

          <div className="schedule-row-meta">
            <span title="Interval">
              <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="12" cy="12" r="10" /><polyline points="12 6 12 12 16 14" />
              </svg>
              every {formatDuration(s.interval_seconds)}
            </span>
            <span title="Time remaining">
              {s.status === 'active' ? timeRemaining(s.expires_at) : formatDuration(s.duration_seconds)}
            </span>
            <span title="Context mode">
              {s.carry_context ? '↺ carry ctx' : '○ fresh ctx'}
            </span>
          </div>

          <div className="schedule-row-runs">
            <span className="schedule-runs-count">
              {s.run_count} run{s.run_count !== 1 ? 's' : ''}
            </span>
            {s.status === 'active' && s.next_run_at && (
              <span className="schedule-next-run">
                next {formatRelativeTime(s.next_run_at)}
              </span>
            )}
          </div>

          {s.run_ids.length > 0 && (
            <div className="schedule-run-ids">
              {s.run_ids.slice(-5).map((rid) => (
                <span key={rid} className="run-id-chip" title={rid}>
                  {rid.slice(0, 16)}…
                </span>
              ))}
              {s.run_ids.length > 5 && (
                <span className="run-id-chip run-id-more">+{s.run_ids.length - 5} more</span>
              )}
            </div>
          )}
        </div>
      ))}
    </div>
  )
}
