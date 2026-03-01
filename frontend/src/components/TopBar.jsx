export default function TopBar({ dotPreviewOpen, onToggleDot, onValidate, onRun }) {
  return (
    <div className="topbar">
      <div className="topbar-brand">
        <img src="/arga.png" alt="Arga" style={{ height: 28, width: 'auto', display: 'block' }} />
      </div>
      <div className="topbar-actions">
        <button className={`btn${dotPreviewOpen ? ' btn-active' : ''}`} onClick={onToggleDot}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <polyline points="16 18 22 12 16 6" />
            <polyline points="8 6 2 12 8 18" />
          </svg>
          Source
        </button>
        <button className="btn" onClick={onValidate}>Validate</button>
        <button className="btn btn-primary" onClick={onRun}>Run Pipeline</button>
      </div>
    </div>
  )
}
