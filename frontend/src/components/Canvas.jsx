import { forwardRef, useEffect, useImperativeHandle, useRef, useState } from 'react'
import cytoscape from 'cytoscape'
import { NODE_COLORS, NODE_SHAPES, NODE_LABELS, DEFAULT_NODE_DATA } from '../constants.js'

const CY_STYLE = [
  {
    selector: 'node',
    style: {
      label: 'data(label)',
      'text-valign': 'center',
      'text-halign': 'center',
      'font-family': 'Inter, system-ui, sans-serif',
      'font-size': '11px',
      'font-weight': 600,
      color: '#fff',
      'text-outline-color': 'data(color)',
      'text-outline-width': 2,
      'background-color': 'data(color)',
      shape: 'data(shape)',
      width: 72,
      height: 42,
      'border-width': 0,
      'overlay-opacity': 0,
      'transition-property': 'border-color, border-width, width, height',
      'transition-duration': '0.15s',
    },
  },
  {
    selector: 'node:selected',
    style: { 'border-width': 3, 'border-color': '#1e1b4b', width: 78, height: 46 },
  },
  {
    selector: 'node.edge-hover',
    style: { 'border-width': 3, 'border-color': '#4f46e5' },
  },
  {
    selector: 'edge',
    style: {
      width: 2,
      'line-color': '#c7d2fe',
      'target-arrow-color': '#818cf8',
      'target-arrow-shape': 'triangle',
      'arrow-scale': 1.1,
      'curve-style': 'bezier',
      label: 'data(displayLabel)',
      'font-family': 'Inter, system-ui, sans-serif',
      'font-size': '10px',
      color: '#6b7280',
      'text-rotation': 'autorotate',
      'text-margin-y': -10,
      'text-background-color': '#f8f9fb',
      'text-background-opacity': 0.9,
      'text-background-padding': '2px',
    },
  },
  {
    selector: 'edge:selected',
    style: { 'line-color': '#6366f1', 'target-arrow-color': '#6366f1', width: 3 },
  },
]

const Canvas = forwardRef(function Canvas({ onNodeSelect, onEdgeSelect, onDeselect, onGraphChange }, ref) {
  const containerRef = useRef(null)
  const cyRef = useRef(null)
  const nodeCounterRef = useRef(0)
  const edgeModeRef = useRef(false)
  const edgeModeSourceRef = useRef(null)
  const [edgeMode, setEdgeModeState] = useState(false)
  const [hasNodes, setHasNodes] = useState(false)
  const [edgeIndicatorText, setEdgeIndicatorText] = useState('Click source node, then target node')

  // Keep ref in sync with state for use inside event closures
  const syncEdgeMode = (val) => {
    edgeModeRef.current = val
    setEdgeModeState(val)
  }

  useEffect(() => {
    const cy = cytoscape({
      container: containerRef.current,
      style: CY_STYLE,
      layout: { name: 'preset' },
      minZoom: 0.3,
      maxZoom: 3,
    })
    cyRef.current = cy

    cy.on('tap', 'node', (evt) => {
      const node = evt.target
      if (edgeModeRef.current) {
        if (!edgeModeSourceRef.current) {
          edgeModeSourceRef.current = node.id()
          node.addClass('edge-hover')
          setEdgeIndicatorText(`${node.data('label')} → click target node`)
        } else {
          const sourceId = edgeModeSourceRef.current
          const targetId = node.id()
          if (targetId === sourceId) {
            cy.getElementById(sourceId).removeClass('edge-hover')
            edgeModeSourceRef.current = null
            setEdgeIndicatorText('Click source node, then target node')
            return
          }
          cy.add({
            group: 'edges',
            data: {
              id: `e_${sourceId}_${targetId}`,
              source: sourceId,
              target: targetId,
              label: '',
              condition: '',
              displayLabel: '',
              weight: 0,
              fidelity: '',
              loop_restart: false,
            },
          })
          cy.getElementById(sourceId).removeClass('edge-hover')
          edgeModeSourceRef.current = null
          setEdgeIndicatorText('Click source node, then target node')
          onGraphChange()
        }
      } else {
        onNodeSelect(node.data())
      }
    })

    cy.on('tap', 'edge', (evt) => {
      if (!edgeModeRef.current) {
        onEdgeSelect(evt.target.data())
      }
    })

    cy.on('tap', (evt) => {
      if (evt.target === cy) onDeselect()
    })

    cy.on('position', 'node', () => onGraphChange())
    cy.on('add remove', () => setHasNodes(cy.nodes().length > 0))

    return () => cy.destroy()
    // Callbacks are stable refs from App — no need to re-run
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useImperativeHandle(ref, () => ({
    addNode(type) {
      const cy = cyRef.current
      nodeCounterRef.current++
      const fixed = { start: 'start', exit: 'exit' }
      const id = fixed[type] ?? `${type}_${nodeCounterRef.current}`

      if (fixed[type] && cy.getElementById(id).length > 0) {
        return { error: `A ${id} node already exists` }
      }

      const vp = cy.extent()
      const x = vp.x1 + (vp.x2 - vp.x1) * (0.3 + Math.random() * 0.4)
      const y = vp.y1 + (vp.y2 - vp.y1) * (0.3 + Math.random() * 0.4)

      cy.add({
        group: 'nodes',
        data: {
          id,
          label: NODE_LABELS[type] || id,
          nodeType: type,
          color: NODE_COLORS[type],
          shape: NODE_SHAPES[type],
          ...DEFAULT_NODE_DATA,
        },
        position: { x, y },
      })
      return null
    },

    toggleEdgeMode() {
      const next = !edgeModeRef.current
      if (!next && edgeModeSourceRef.current) {
        cyRef.current.getElementById(edgeModeSourceRef.current).removeClass('edge-hover')
        edgeModeSourceRef.current = null
      }
      syncEdgeMode(next)
      setEdgeIndicatorText('Click source node, then target node')
    },

    updateElementData(id, key, val) {
      const el = cyRef.current.getElementById(id)
      el.data(key, val)
      if ((key === 'condition' || key === 'label') && el.isEdge()) {
        const label = el.data('label')
        const cond = el.data('condition')
        el.data('displayLabel', label || cond || '')
      }
    },

    changeNodeType(id, newType) {
      const node = cyRef.current.getElementById(id)
      node.data('nodeType', newType)
      node.data('color', NODE_COLORS[newType])
      node.data('shape', NODE_SHAPES[newType])
    },

    renameNode(oldId, newId) {
      if (oldId === newId || !newId.trim()) return null
      const cy = cyRef.current
      if (cy.getElementById(newId).length > 0) return { error: 'A node with that ID already exists' }

      const node = cy.getElementById(oldId)
      const data = { ...node.data(), id: newId }
      const pos = node.position()
      const edgeDataList = []
      node.connectedEdges().forEach((e) => {
        edgeDataList.push({
          ...e.data(),
          source: e.data('source') === oldId ? newId : e.data('source'),
          target: e.data('target') === oldId ? newId : e.data('target'),
        })
      })
      node.connectedEdges().remove()
      node.remove()
      cy.add({ group: 'nodes', data, position: pos })
      edgeDataList.forEach((ed) => {
        cy.add({ group: 'edges', data: { ...ed, id: `e_${ed.source}_${ed.target}` } })
      })
      return null
    },

    deleteElement(id) {
      cyRef.current.getElementById(id).remove()
    },

    autoLayout() {
      cyRef.current
        .layout({ name: 'breadthfirst', directed: true, spacingFactor: 1.6, animate: true, animationDuration: 400 })
        .run()
    },

    fit() {
      cyRef.current.fit(undefined, 50)
    },

    getGraphData() {
      return {
        nodes: cyRef.current.nodes().map((n) => n.data()),
        edges: cyRef.current.edges().map((e) => e.data()),
      }
    },

    getEdgesForNode(nodeId) {
      return cyRef.current
        .edges()
        .filter((e) => e.data('source') === nodeId)
        .map((e) => e.data())
    },

    getNodeData(id) {
      const el = cyRef.current.getElementById(id)
      return el.length ? el.data() : null
    },

    selectElement(id) {
      cyRef.current.elements().unselect()
      const el = cyRef.current.getElementById(id)
      if (el.length) {
        el.select()
        if (el.isNode()) onNodeSelect(el.data())
        else onEdgeSelect(el.data())
      }
    },

    loadPreset(preset) {
      const cy = cyRef.current
      cy.elements().remove()
      nodeCounterRef.current = 0

      preset.nodes.forEach(({ _x, _y, ...data }) => {
        cy.add({ group: 'nodes', data, position: { x: _x, y: _y } })
      })
      preset.edges.forEach((data) => {
        cy.add({ group: 'edges', data })
      })

      cy.fit(undefined, 60)
    },
  }))

  return (
    <div className="canvas-area">
      <div ref={containerRef} style={{ width: '100%', height: '100%' }} />

      {!hasNodes && (
        <div className="canvas-hint">
          <div className="canvas-hint-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="10" />
              <line x1="12" y1="8" x2="12" y2="16" />
              <line x1="8" y1="12" x2="16" y2="12" />
            </svg>
          </div>
          <h3>Build your pipeline</h3>
          <p>Add nodes from the left panel, then connect them to define the execution flow.</p>
        </div>
      )}

      {edgeMode && (
        <div className="edge-indicator active">{edgeIndicatorText}</div>
      )}

      <div className="canvas-toolbar">
        <button className="btn" onClick={() => cyRef.current?.fit(undefined, 50)}>
          Fit View
        </button>
        <button
          className="btn"
          onClick={() => {
            cyRef.current
              ?.layout({ name: 'breadthfirst', directed: true, spacingFactor: 1.6, animate: true, animationDuration: 400 })
              .run()
            setTimeout(onGraphChange, 500)
          }}
        >
          Auto Layout
        </button>
      </div>
    </div>
  )
})

export default Canvas
