import { useCallback, useEffect, useRef, useState } from 'react'
import TopBar from './components/TopBar.jsx'
import LeftPanel from './components/LeftPanel.jsx'
import Canvas from './components/Canvas.jsx'
import RightPanel from './components/RightPanel.jsx'
import DotPreview from './components/DotPreview.jsx'
import Toast from './components/Toast.jsx'
import ScheduleModal from './components/ScheduleModal.jsx'
import SchedulePanel from './components/SchedulePanel.jsx'
import PipelineOutput from './components/PipelineOutput.jsx'
import { generateDot } from './dotGenerator.js'

export default function App() {
  const canvasRef = useRef(null)

  const [graphName, setGraphName] = useState('Pipeline')
  const [graphGoal, setGraphGoal] = useState('')
  const [graphStylesheet, setGraphStylesheet] = useState('')

  const [selectedElement, setSelectedElement] = useState(null)
  const [outgoingEdges, setOutgoingEdges] = useState([])
  const [edgeMode, setEdgeMode] = useState(false)

  const [dotSource, setDotSource] = useState('')
  const [dotPreviewOpen, setDotPreviewOpen] = useState(false)

  const [uploadedFiles, setUploadedFiles] = useState([])
  const [pipelineResult, setPipelineResult] = useState(null)
  const [runStatus, setRunStatus] = useState(null) // 'running' | 'completed' | 'failed' | null
  const [showResult, setShowResult] = useState(false)

  const [scheduleModalOpen, setScheduleModalOpen] = useState(false)
  const [schedulePanelOpen, setSchedulePanelOpen] = useState(false)
  const [schedules, setSchedules] = useState([])
  const schedulePollRef = useRef(null)

  const [toast, setToast] = useState(null)

  const showToast = useCallback((message, type = '') => {
    setToast({ message, type })
    setTimeout(() => setToast(null), 3000)
  }, [])

  // Safe response parser: try JSON first, fall back to text so we always get something useful.
  const parseResponse = useCallback(async (r) => {
    const text = await r.text()
    if (!text) return { _empty: true, status: r.status }
    try {
      return JSON.parse(text)
    } catch {
      return { _raw: text, status: r.status }
    }
  }, [])

  const refreshDot = useCallback((name, goal, stylesheet) => {
    if (!canvasRef.current) return
    const { nodes, edges } = canvasRef.current.getGraphData()
    setDotSource(generateDot({ name, goal, stylesheet, nodes, edges }))
  }, [])

  // Re-generate DOT whenever graph metadata changes
  useEffect(() => {
    refreshDot(graphName, graphGoal, graphStylesheet)
  }, [graphName, graphGoal, graphStylesheet, refreshDot])

  const handleGraphChange = useCallback(() => {
    refreshDot(graphName, graphGoal, graphStylesheet)
    // Refresh outgoing edges if a node is selected
    setSelectedElement((prev) => {
      if (prev?.type === 'node' && canvasRef.current) {
        const edges = canvasRef.current.getEdgesForNode(prev.data.id)
        setOutgoingEdges(edges)
      }
      return prev
    })
  }, [graphName, graphGoal, graphStylesheet, refreshDot])

  const handleNodeSelect = useCallback((data) => {
    setSelectedElement({ type: 'node', data })
    if (canvasRef.current) {
      setOutgoingEdges(canvasRef.current.getEdgesForNode(data.id))
    }
  }, [])

  const handleEdgeSelect = useCallback((data) => {
    const sourceNode = canvasRef.current?.getNodeData(data.source)
    setSelectedElement({ type: 'edge', data, sourceNodeType: sourceNode?.nodeType })
    setOutgoingEdges([])
  }, [])

  const handleDeselect = useCallback(() => {
    setSelectedElement(null)
    setOutgoingEdges([])
  }, [])

  const handleUpdateNode = useCallback((id, key, val) => {
    canvasRef.current?.updateElementData(id, key, val)
    setSelectedElement((prev) =>
      prev?.type === 'node' && prev.data.id === id
        ? { ...prev, data: { ...prev.data, [key]: val } }
        : prev
    )
    refreshDot(graphName, graphGoal, graphStylesheet)
  }, [graphName, graphGoal, graphStylesheet, refreshDot])

  const handleUpdateEdge = useCallback((id, key, val) => {
    canvasRef.current?.updateElementData(id, key, val)
    setSelectedElement((prev) =>
      prev?.type === 'edge' && prev.data.id === id
        ? { ...prev, data: { ...prev.data, [key]: val } }
        : prev
    )
    // Also refresh edge list if a node is selected
    setOutgoingEdges((prev) => {
      if (!canvasRef.current) return prev
      const nodeId = selectedElement?.type === 'node' ? selectedElement.data.id : null
      if (!nodeId) return prev
      return canvasRef.current.getEdgesForNode(nodeId)
    })
    refreshDot(graphName, graphGoal, graphStylesheet)
  }, [graphName, graphGoal, graphStylesheet, refreshDot, selectedElement])

  const handleDeleteElement = useCallback((id) => {
    canvasRef.current?.deleteElement(id)
    setSelectedElement(null)
    setOutgoingEdges([])
    refreshDot(graphName, graphGoal, graphStylesheet)
  }, [graphName, graphGoal, graphStylesheet, refreshDot])

  const handleRenameNode = useCallback((oldId, newId) => {
    const result = canvasRef.current?.renameNode(oldId, newId)
    if (result?.error) {
      showToast(result.error, 'error')
      return
    }
    const newData = canvasRef.current?.getNodeData(newId)
    if (newData) {
      setSelectedElement({ type: 'node', data: newData })
      setOutgoingEdges(canvasRef.current?.getEdgesForNode(newId) || [])
    }
    refreshDot(graphName, graphGoal, graphStylesheet)
  }, [graphName, graphGoal, graphStylesheet, refreshDot, showToast])

  const handleChangeNodeType = useCallback((id, newType) => {
    canvasRef.current?.changeNodeType(id, newType)
    const newData = canvasRef.current?.getNodeData(id)
    if (newData) {
      setSelectedElement({ type: 'node', data: newData })
      setOutgoingEdges(canvasRef.current?.getEdgesForNode(id) || [])
    }
    refreshDot(graphName, graphGoal, graphStylesheet)
  }, [graphName, graphGoal, graphStylesheet, refreshDot])

  // ── File upload ──────────────────────────────────────────────────────
  const handleUploadFile = useCallback(async (file) => {
    const formData = new FormData()
    formData.append('file', file)
    try {
      const r = await fetch('/upload', { method: 'POST', body: formData })
      const d = await r.json()
      if (r.ok) {
        setUploadedFiles((prev) => [...prev, d])
        showToast(`Uploaded ${d.filename}`, 'success')
      } else {
        showToast(`Upload failed: ${d.error}`, 'error')
      }
    } catch (e) {
      showToast('Upload error: ' + e.message, 'error')
    }
  }, [showToast])

  const handleRemoveFile = useCallback(async (fileId) => {
    try {
      await fetch(`/upload/${fileId}`, { method: 'DELETE' })
    } catch (_) {}
    setUploadedFiles((prev) => prev.filter((f) => f.file_id !== fileId))
  }, [])

  // Build initial context from uploaded files: { context_key: path, ... }
  const buildInitialContext = useCallback(() => {
    if (uploadedFiles.length === 0) return undefined
    return Object.fromEntries(uploadedFiles.map((f) => [f.context_key, f.path]))
  }, [uploadedFiles])

  const handleLoadPreset = useCallback((preset) => {
    canvasRef.current?.loadPreset(preset)
    setGraphName(preset.graphName)
    setGraphGoal(preset.graphGoal)
    setGraphStylesheet(preset.graphStylesheet)
    setSelectedElement(null)
    setOutgoingEdges([])
    refreshDot(preset.graphName, preset.graphGoal, preset.graphStylesheet)
  }, [refreshDot])

  const handleAddNode = useCallback((type) => {
    const result = canvasRef.current?.addNode(type)
    if (result?.error) {
      showToast(result.error, 'error')
      return
    }
    refreshDot(graphName, graphGoal, graphStylesheet)
  }, [graphName, graphGoal, graphStylesheet, refreshDot, showToast])

  const handleToggleEdgeMode = useCallback(() => {
    canvasRef.current?.toggleEdgeMode()
    setEdgeMode((p) => !p)
  }, [])

  const handleSelectEdge = useCallback((edgeId) => {
    canvasRef.current?.selectElement(edgeId)
  }, [])

  const getCurrentDot = useCallback(() => {
    const { nodes, edges } = canvasRef.current?.getGraphData() ?? { nodes: [], edges: [] }
    if (nodes?.length && edges?.length) {
      return generateDot({
        name: graphName,
        goal: graphGoal,
        stylesheet: graphStylesheet,
        nodes,
        edges,
      })
    }
    return dotSource
  }, [graphName, graphGoal, graphStylesheet, dotSource])

  const handleValidate = useCallback(async () => {
    const toValidate = getCurrentDot()
    if (!toValidate.includes('->')) {
      showToast('Add nodes and connect them first', 'error')
      return
    }
    try {
      const r = await fetch('/validate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ dot_source: toValidate }),
      })
      const d = await parseResponse(r)
      if (d._empty) {
        showToast(`Server returned empty response (HTTP ${d.status}). Is the backend running?`, 'error')
        return
      }
      if (d._raw || d.error) {
        showToast(`Server error: ${d.error || d._raw?.slice(0, 120)}`, 'error')
        return
      }
      if (d.valid) {
        showToast('Pipeline is valid', 'success')
      } else {
        const msgs = d.diagnostics.map((x) => `[${x.severity}] ${x.message}`).join('\n')
        showToast('Validation failed', 'error')
        alert('Validation Issues:\n\n' + msgs)
      }
    } catch (e) {
      showToast('Network error: ' + e.message, 'error')
    }
  }, [getCurrentDot, showToast, parseResponse])

  const handleRun = useCallback(async () => {
    const runDot = getCurrentDot()
    if (!runDot.includes('->')) {
      showToast('Add nodes and connect them first', 'error')
      return
    }
    try {
      const body = { dot_source: runDot }
      const ctx = buildInitialContext()
      if (ctx) body.context = ctx
      const r = await fetch('/pipelines', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      const d = await parseResponse(r)
      if (d._empty) {
        showToast(`Server returned empty response (HTTP ${d.status}). Is the backend running?`, 'error')
        return
      }
      if (d._raw || d.error) {
        showToast(`Error: ${d.error || d._raw?.slice(0, 120)}`, 'error')
        return
      }
      showToast(`Pipeline started: ${d.id}`, 'success')
      setRunStatus('running')
      setPipelineResult(null)
      setShowResult(false)
      pollPipeline(d.id)
    } catch (e) {
      showToast('Network error: ' + e.message, 'error')
    }
  }, [getCurrentDot, showToast, buildInitialContext, parseResponse])

  const pollPipeline = useCallback((id) => {
    const check = async () => {
      try {
        const r = await fetch(`/pipelines/${id}`)
        const d = await parseResponse(r)
        const status = d?.status

        if (status === 'completed' || status === 'failed') {
          setRunStatus(status)
          const label = status === 'completed' ? 'Pipeline completed — click View Results' : `Pipeline failed: ${d.error || ''}`
          showToast(label, status === 'completed' ? 'success' : 'error')
          // Fetch the full result log
          try {
            const lr = await fetch(`/pipelines/${id}/log`)
            const log = await parseResponse(lr)
            if (log && !log._empty && !log._raw) {
              setPipelineResult(log)
              setShowResult(true)  // auto-open on first completion
            }
          } catch (_) {}
        } else if (status === 'running' || status === 'pending') {
          setTimeout(check, 1500)
        } else {
          // unknown status or parse failure — keep polling a few more times
          setTimeout(check, 2000)
        }
      } catch (_) {
        setTimeout(check, 2000)
      }
    }
    setTimeout(check, 1000)
  }, [showToast, parseResponse])

  // ── Schedule polling ──────────────────────────────────────────────────
  const fetchSchedules = useCallback(async () => {
    try {
      const r = await fetch('/schedules')
      if (r.ok) setSchedules(await r.json())
    } catch (_) {}
  }, [])

  // Start/stop polling based on whether any schedule is active
  useEffect(() => {
    const hasActive = schedules.some((s) => s.status === 'active')
    if (hasActive && !schedulePollRef.current) {
      schedulePollRef.current = setInterval(fetchSchedules, 5000)
    } else if (!hasActive && schedulePollRef.current) {
      clearInterval(schedulePollRef.current)
      schedulePollRef.current = null
    }
    return () => {
      if (schedulePollRef.current) {
        clearInterval(schedulePollRef.current)
        schedulePollRef.current = null
      }
    }
  }, [schedules, fetchSchedules])

  const handleCreateSchedule = useCallback(
    async ({ intervalSeconds, durationSeconds, carryContext }) => {
      const scheduleDot = getCurrentDot()
      if (!scheduleDot.includes('->')) {
        showToast('Add nodes and connect them first', 'error')
        return
      }
      try {
        const scheduleBody = {
          dot_source: scheduleDot,
          interval_seconds: intervalSeconds,
          duration_seconds: durationSeconds,
          carry_context: carryContext,
        }
        const ctx = buildInitialContext()
        if (ctx) scheduleBody.initial_context = ctx
        const r = await fetch('/schedules', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(scheduleBody),
        })
        const d = await parseResponse(r)
        if (d._empty || d._raw || d.error) {
          showToast(`Error: ${d.error || d._raw?.slice(0, 120) || `HTTP ${d.status}`}`, 'error')
          return
        }
        showToast('Schedule created', 'success')
        setScheduleModalOpen(false)
        setSchedulePanelOpen(true)
        await fetchSchedules()
      } catch (e) {
        showToast('Network error: ' + e.message, 'error')
      }
    },
    [getCurrentDot, showToast, fetchSchedules, buildInitialContext, parseResponse]
  )

  const handleCancelSchedule = useCallback(
    async (id) => {
      try {
        await fetch(`/schedules/${id}`, { method: 'DELETE' })
        showToast('Schedule cancelled', 'success')
        await fetchSchedules()
      } catch (e) {
        showToast('Request failed: ' + e.message, 'error')
      }
    },
    [showToast, fetchSchedules]
  )

  const activeScheduleCount = schedules.filter((s) => s.status === 'active').length

  return (
    <div className="app">
      <TopBar
        dotPreviewOpen={dotPreviewOpen}
        onToggleDot={() => setDotPreviewOpen((p) => !p)}
        onValidate={handleValidate}
        onRun={handleRun}
        onOpenSchedule={() => setScheduleModalOpen(true)}
        activeScheduleCount={activeScheduleCount}
        onToggleSchedulePanel={() => setSchedulePanelOpen((p) => !p)}
        runStatus={runStatus}
        hasResult={!!pipelineResult}
        onViewResult={() => setShowResult(true)}
      />

      <div className="main">
        <LeftPanel
          edgeMode={edgeMode}
          onAddNode={handleAddNode}
          onToggleEdgeMode={handleToggleEdgeMode}
          onLoadPreset={handleLoadPreset}
          graphName={graphName}
          onGraphNameChange={setGraphName}
          graphGoal={graphGoal}
          onGraphGoalChange={setGraphGoal}
          graphStylesheet={graphStylesheet}
          onGraphStylesheetChange={setGraphStylesheet}
          uploadedFiles={uploadedFiles}
          onUploadFile={handleUploadFile}
          onRemoveFile={handleRemoveFile}
        />

        <Canvas
          ref={canvasRef}
          onNodeSelect={handleNodeSelect}
          onEdgeSelect={handleEdgeSelect}
          onDeselect={handleDeselect}
          onGraphChange={handleGraphChange}
        />

        <RightPanel
          selectedElement={selectedElement}
          outgoingEdges={outgoingEdges}
          onUpdateNode={handleUpdateNode}
          onUpdateEdge={handleUpdateEdge}
          onRenameNode={handleRenameNode}
          onDeleteElement={handleDeleteElement}
          onSelectEdge={handleSelectEdge}
          onChangeNodeType={handleChangeNodeType}
        />
      </div>

      {dotPreviewOpen && (
        <DotPreview
          source={dotSource}
          onCopy={() =>
            navigator.clipboard.writeText(dotSource).then(() => showToast('Copied to clipboard', 'success'))
          }
        />
      )}

      {schedulePanelOpen && schedules.length > 0 && (
        <SchedulePanel
          schedules={schedules}
          onCancel={handleCancelSchedule}
          onClose={() => setSchedulePanelOpen(false)}
        />
      )}

      {scheduleModalOpen && (
        <ScheduleModal
          onClose={() => setScheduleModalOpen(false)}
          onCreate={handleCreateSchedule}
        />
      )}

      <Toast message={toast?.message} type={toast?.type} />

      {showResult && pipelineResult && (
        <PipelineOutput
          result={pipelineResult}
          onClose={() => setShowResult(false)}
        />
      )}
    </div>
  )
}
