import { DOT_SHAPES } from './constants.js'

function qid(s) {
  return /^[a-zA-Z_]\w*$/.test(s) ? s : `"${s.replace(/\\/g, '\\\\').replace(/"/g, '\\"')}"`
}

function fmtAttrs(obj) {
  const pairs = Object.entries(obj)
    .map(([k, v]) => `${k}="${String(v).replace(/\\/g, '\\\\').replace(/"/g, '\\"')}"`)
    .join(', ')
  return `[${pairs}]`
}

export function generateDot({ name, goal, stylesheet, nodes, edges }) {
  const graphName = name || 'Pipeline'
  const lines = [`digraph ${qid(graphName)} {`]

  const ga = {}
  if (goal) ga.goal = goal
  if (stylesheet) ga.model_stylesheet = stylesheet
  if (Object.keys(ga).length) lines.push(`    graph ${fmtAttrs(ga)}`)
  lines.push('')

  nodes.forEach((d) => {
    const a = { shape: DOT_SHAPES[d.nodeType] || d.nodeType }
    if (d.label && d.label !== d.id) a.label = d.label
    if (d.prompt) a.prompt = d.prompt
    if (d.nodeType === 'manager') a.max_cycles = String(d.max_cycles != null ? d.max_cycles : 3)
    if (d.mcp_servers) a.mcp_servers = d.mcp_servers
    if (d.command) a.command = d.command
    if (d.http_url) a.url = d.http_url
    if (d.http_method && d.http_method !== 'GET') a.method = d.http_method
    if (d.http_body) a.body = d.http_body
    if (d.http_headers) a.headers = d.http_headers
    if (d.goal_gate) a.goal_gate = 'true'
    if (d.max_retries > 0) a.max_retries = String(d.max_retries)
    if (d.retry_target) a.retry_target = d.retry_target
    if (d.timeout) a.timeout = d.timeout
    if (d.llm_model) a.llm_model = d.llm_model
    lines.push(`    ${qid(d.id)} ${fmtAttrs(a)}`)
  })

  lines.push('')

  edges.forEach((d) => {
    const a = {}
    if (d.label) a.label = d.label
    if (d.condition) a.condition = d.condition
    if (d.weight > 0) a.weight = String(d.weight)
    if (d.fidelity) a.fidelity = d.fidelity
    if (d.loop_restart) a.loop_restart = 'true'
    const suffix = Object.keys(a).length ? ' ' + fmtAttrs(a) : ''
    lines.push(`    ${qid(d.source)} -> ${qid(d.target)}${suffix}`)
  })

  lines.push('}')
  return lines.join('\n')
}
