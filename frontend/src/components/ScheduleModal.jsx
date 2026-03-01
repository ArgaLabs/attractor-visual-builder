import { useState } from 'react'

const INTERVAL_UNITS = [
  { label: 'minutes', factor: 60 },
  { label: 'hours', factor: 3600 },
]
const DURATION_UNITS = [
  { label: 'hours', factor: 3600 },
  { label: 'days', factor: 86400 },
]

function unitFactor(units, unitLabel) {
  return units.find((u) => u.label === unitLabel)?.factor ?? 60
}

export default function ScheduleModal({ onClose, onCreate }) {
  const [intervalValue, setIntervalValue] = useState(30)
  const [intervalUnit, setIntervalUnit] = useState('minutes')
  const [durationValue, setDurationValue] = useState(2)
  const [durationUnit, setDurationUnit] = useState('days')
  const [carryContext, setCarryContext] = useState(false)
  const [error, setError] = useState('')

  const intervalSeconds = intervalValue * unitFactor(INTERVAL_UNITS, intervalUnit)
  const durationSeconds = durationValue * unitFactor(DURATION_UNITS, durationUnit)

  const runCount = durationSeconds > 0 && intervalSeconds > 0
    ? Math.floor(durationSeconds / intervalSeconds)
    : 0

  function validate() {
    if (intervalSeconds < 30) return 'Minimum interval is 30 seconds.'
    if (durationSeconds < intervalSeconds) return 'Duration must be at least one interval long.'
    if (durationSeconds > 7 * 86400) return 'Maximum duration is 7 days.'
    return ''
  }

  function handleSubmit() {
    const err = validate()
    if (err) { setError(err); return }
    setError('')
    onCreate({ intervalSeconds, durationSeconds, carryContext })
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div className="modal-title">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="10" />
              <polyline points="12 6 12 12 16 14" />
            </svg>
            Schedule Recurring Run
          </div>
          <button className="modal-close" onClick={onClose}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>

        <div className="modal-body">
          {/* Interval */}
          <div className="field">
            <label className="field-label">Run every</label>
            <div className="input-row">
              <input
                className="field-input"
                type="number"
                min="1"
                value={intervalValue}
                onChange={(e) => setIntervalValue(Math.max(1, parseInt(e.target.value) || 1))}
              />
              <select
                className="field-select"
                value={intervalUnit}
                onChange={(e) => setIntervalUnit(e.target.value)}
              >
                {INTERVAL_UNITS.map((u) => (
                  <option key={u.label} value={u.label}>{u.label}</option>
                ))}
              </select>
            </div>
          </div>

          {/* Duration */}
          <div className="field">
            <label className="field-label">For</label>
            <div className="input-row">
              <input
                className="field-input"
                type="number"
                min="1"
                value={durationValue}
                onChange={(e) => setDurationValue(Math.max(1, parseInt(e.target.value) || 1))}
              />
              <select
                className="field-select"
                value={durationUnit}
                onChange={(e) => setDurationUnit(e.target.value)}
              >
                {DURATION_UNITS.map((u) => (
                  <option key={u.label} value={u.label}>{u.label}</option>
                ))}
              </select>
            </div>
            {runCount > 0 && (
              <div className="field-hint">≈ {runCount} run{runCount !== 1 ? 's' : ''} total</div>
            )}
          </div>

          {/* Carry context toggle */}
          <div className="field">
            <label className="field-label">Context</label>
            <div
              className="toggle-row"
              onClick={() => setCarryContext((p) => !p)}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => e.key === ' ' && setCarryContext((p) => !p)}
            >
              <div className={`toggle-switch${carryContext ? ' on' : ''}`}>
                <div className="toggle-knob" />
              </div>
              <div className="toggle-label">
                <span className="toggle-title">Carry forward context</span>
                <span className="toggle-desc">
                  {carryContext
                    ? 'Each run inherits the previous run\'s output context.'
                    : 'Each run starts with a fresh, independent context.'}
                </span>
              </div>
            </div>
          </div>

          {error && <div className="modal-error">{error}</div>}
        </div>

        <div className="modal-footer">
          <button className="btn" onClick={onClose}>Cancel</button>
          <button className="btn btn-primary" onClick={handleSubmit}>
            Start Schedule
          </button>
        </div>
      </div>
    </div>
  )
}
