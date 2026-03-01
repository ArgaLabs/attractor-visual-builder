import { useCallback, useEffect, useRef, useState } from 'react'

const MIN_HEIGHT = 80
const MAX_HEIGHT = 600
const DEFAULT_HEIGHT = 240

export default function DotPreview({ source, onCopy }) {
  const [height, setHeight] = useState(DEFAULT_HEIGHT)
  const dragStartY = useRef(null)
  const dragStartHeight = useRef(null)

  const onMouseDown = useCallback((e) => {
    e.preventDefault()
    dragStartY.current = e.clientY
    dragStartHeight.current = height
  }, [height])

  useEffect(() => {
    const onMove = (e) => {
      if (dragStartY.current === null) return
      // dragging up = bigger panel (clientY decreases)
      const delta = dragStartY.current - e.clientY
      const next = Math.min(MAX_HEIGHT, Math.max(MIN_HEIGHT, dragStartHeight.current + delta))
      setHeight(next)
    }
    const onUp = () => {
      dragStartY.current = null
      dragStartHeight.current = null
    }
    window.addEventListener('mousemove', onMove)
    window.addEventListener('mouseup', onUp)
    return () => {
      window.removeEventListener('mousemove', onMove)
      window.removeEventListener('mouseup', onUp)
    }
  }, [])

  return (
    <div className="panel-bottom" style={{ height }}>
      {/* drag handle */}
      <div className="panel-bottom-resize" onMouseDown={onMouseDown} title="Drag to resize" />

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
