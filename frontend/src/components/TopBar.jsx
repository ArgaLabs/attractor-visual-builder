export default function TopBar({
  dotPreviewOpen,
  onToggleDot,
  onValidate,
  onRun,
  onOpenSchedule,
  activeScheduleCount,
  onToggleSchedulePanel,
}) {
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

        {/* Schedule button with active-count badge */}
        <button
          className="btn btn-schedule"
          onClick={activeScheduleCount > 0 ? onToggleSchedulePanel : onOpenSchedule}
          title={activeScheduleCount > 0 ? 'View active schedules' : 'Schedule recurring run'}
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="12" cy="12" r="10" />
            <polyline points="12 6 12 12 16 14" />
          </svg>
          Schedule
          {activeScheduleCount > 0 && (
            <span className="schedule-badge">{activeScheduleCount}</span>
          )}
        </button>

        <button className="btn btn-primary" onClick={onRun}>Run Pipeline</button>
      </div>
    </div>
  )
}
