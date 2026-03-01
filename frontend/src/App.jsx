import { useCallback, useEffect, useRef, useState } from 'react'
import TopBar from './components/TopBar.jsx'
import LeftPanel from './components/LeftPanel.jsx'
import Canvas from './components/Canvas.jsx'
import RightPanel from './components/RightPanel.jsx'
import DotPreview from './components/DotPreview.jsx'
import Toast from './components/Toast.jsx'
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

  const [toast, setToast] = useState(null)

  const showToast = useCallback((message, type = '') => {
    setToast({ message, type })
    setTimeout(() => setToast(null), 3000)
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

  const handleValidate = useCallback(async () => {
    if (!dotSource.includes('->')) {
      showToast('Add nodes and connect them first', 'error')
      return
    }
    try {
      const r = await fetch('/validate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ dot_source: dotSource }),
      })
      const d = await r.json()
      if (d.valid) {
        showToast('Pipeline is valid', 'success')
      } else {
        const msgs = d.diagnostics.map((x) => `[${x.severity}] ${x.message}`).join('\n')
        showToast('Validation failed', 'error')
        alert('Validation Issues:\n\n' + msgs)
      }
    } catch (e) {
      showToast('Request failed: ' + e.message, 'error')
    }
  }, [dotSource, showToast])

  const handleRun = useCallback(async () => {
    if (!dotSource.includes('->')) {
      showToast('Add nodes and connect them first', 'error')
      return
    }
    try {
      const r = await fetch('/pipelines', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ dot_source: dotSource }),
      })
      const d = await r.json()
      if (r.ok) {
        showToast(`Pipeline started: ${d.id}`, 'success')
        pollPipeline(d.id)
      } else {
        showToast(`Error: ${d.error}`, 'error')
      }
    } catch (e) {
      showToast('Request failed: ' + e.message, 'error')
    }
  }, [dotSource, showToast])

  const pollPipeline = useCallback((id) => {
    const check = async () => {
      try {
        const r = await fetch(`/pipelines/${id}`)
        const d = await r.json()
        if (d.status === 'completed') showToast('Pipeline completed', 'success')
        else if (d.status === 'failed') showToast(`Pipeline failed: ${d.error || ''}`, 'error')
        else if (d.status === 'running') setTimeout(check, 1000)
      } catch (_) {}
    }
    setTimeout(check, 500)
  }, [showToast])

  return (
    <div className="app">
      <TopBar
        dotPreviewOpen={dotPreviewOpen}
        onToggleDot={() => setDotPreviewOpen((p) => !p)}
        onValidate={handleValidate}
        onRun={handleRun}
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

      <Toast message={toast?.message} type={toast?.type} />
    </div>
  )
}
