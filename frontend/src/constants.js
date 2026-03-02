export const NODE_COLORS = {
  start: '#6366f1',
  codergen: '#3b82f6',
  conditional: '#eab308',
  human: '#10b981',
  tool: '#f97316',
  parallel: '#ec4899',
  fan_in: '#a855f7',
  manager: '#8b5cf6',
  http: '#0ea5e9',
  exit: '#6b7280',
}

export const NODE_SHAPES = {
  start: 'diamond',
  codergen: 'round-rectangle',
  conditional: 'diamond',
  human: 'round-rectangle',
  tool: 'round-rectangle',
  parallel: 'hexagon',
  fan_in: 'octagon',
  manager: 'hexagon',
  http: 'round-rectangle',
  exit: 'round-rectangle',
}

export const NODE_LABELS = {
  start: 'Start',
  codergen: 'LLM Call',
  conditional: 'Condition',
  human: 'Human Gate',
  tool: 'Tool',
  parallel: 'Parallel',
  fan_in: 'Fan-In',
  manager: 'Manager',
  http: 'HTTP Request',
  exit: 'Exit',
}

export const DOT_SHAPES = {
  start: 'Mdiamond',
  codergen: 'box',
  conditional: 'diamond',
  human: 'house',
  tool: 'parallelogram',
  parallel: 'component',
  fan_in: 'tripleoctagon',
  manager: 'hexagon',
  http: 'cds',
  exit: 'Msquare',
}

export const PALETTE = [
  { type: 'start',       icon: 'S',  name: 'Start',          desc: 'Entry point of the pipeline. Every pipeline needs one.' },
  { type: 'codergen',    icon: 'L',  name: 'LLM Call',       desc: 'Sends a prompt to an LLM and captures the response.' },
  { type: 'conditional', icon: '?',  name: 'Conditional',    desc: 'Branches the flow based on conditions on each edge.' },
  { type: 'human',       icon: 'H',  name: 'Human Gate',     desc: 'Pauses for human approval before continuing.' },
  { type: 'tool',        icon: 'T',  name: 'Tool / Shell',   desc: 'Runs a shell command and captures output.' },
  { type: 'parallel',    icon: '//', name: 'Parallel Fork',  desc: 'Fans out to run multiple branches concurrently.' },
  { type: 'fan_in',      icon: 'J',  name: 'Fan-In Join',    desc: 'Collects results from parallel branches back together.' },
  { type: 'manager',     icon: 'M',  name: 'Manager Loop',   desc: 'Supervisor that observes, guards, and steers a sub-pipeline.' },
  { type: 'http',        icon: '↗',  name: 'HTTP Request',   desc: 'Calls an external URL (GET/POST/PUT). Use for external skills, webhooks, or browser APIs.' },
  { type: 'exit',        icon: 'X',  name: 'Exit',           desc: 'Terminal node. The pipeline ends here.' },
]

export const LLM_MODELS = [
  {
    group: 'Anthropic',
    options: [
      { id: 'claude-opus-4-5',   label: 'Claude Opus 4.5' },
      { id: 'claude-sonnet-4-5', label: 'Claude Sonnet 4.5 (Default)' },
      { id: 'claude-3-haiku-20240307', label: 'Claude 3 Haiku (Fast)' },
    ],
  },
  {
    group: 'OpenAI',
    options: [
      { id: 'gpt-4o',       label: 'GPT-4o' },
      { id: 'gpt-4o-mini',  label: 'GPT-4o Mini' },
      { id: 'o3-mini',      label: 'o3 Mini' },
    ],
  },
  {
    group: 'Google',
    options: [
      { id: 'gemini-2.0-flash', label: 'Gemini 2.0 Flash' },
      { id: 'gemini-1.5-pro',   label: 'Gemini 1.5 Pro' },
    ],
  },
]

export const DEFAULT_NODE_DATA = {
  prompt: '',
  condition: '',
  command: '',
  http_url: '',
  http_method: 'GET',
  http_body: '',
  http_headers: '',
  mcp_servers: '',
  max_cycles: 3,
  goal_gate: false,
  max_retries: 0,
  retry_target: '',
  timeout: '',
  llm_model: '',
}
