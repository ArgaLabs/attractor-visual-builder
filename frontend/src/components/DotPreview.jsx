export default function DotPreview({ source, onCopy }) {
  return (
    <div className="panel-bottom open">
      <div className="panel-bottom-header">
        <span>Generated DOT Source</span>
        <button className="btn" style={{ fontSize: 12, padding: '5px 12px' }} onClick={onCopy}>
          Copy
        </button>
      </div>
      <textarea className="dot-preview" readOnly value={source} />
    </div>
  )
}
