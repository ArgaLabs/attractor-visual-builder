import { NODE_COLORS, NODE_SHAPES, NODE_LABELS, DEFAULT_NODE_DATA } from './constants.js'

function node(id, type, x, y, overrides = {}) {
  return {
    id,
    label: overrides.label ?? NODE_LABELS[type] ?? id,
    nodeType: type,
    color: NODE_COLORS[type],
    shape: NODE_SHAPES[type],
    ...DEFAULT_NODE_DATA,
    ...overrides,
    _x: x,
    _y: y,
  }
}

function edge(source, target, overrides = {}) {
  return {
    id: `e_${source}_${target}`,
    source,
    target,
    label: '',
    condition: '',
    displayLabel: overrides.condition ?? '',
    weight: 0,
    fidelity: '',
    loop_restart: false,
    ...overrides,
  }
}

export const PRESETS = [
  // ── 1. Starter ──────────────────────────────────────────────────────
  {
    id: 'starter',
    name: 'Simple Q&A',
    description: 'Bare minimum: ask an LLM a question and get an answer.',
    icon: '✦',
    category: 'Getting Started',
    graphName: 'Simple QA',
    graphGoal: 'Answer a user question concisely and accurately.',
    graphStylesheet: '* { llm_model: claude-sonnet-4-5; }',
    nodes: [
      node('start', 'start', 300, 120),
      node('answer', 'codergen', 300, 260, {
        label: 'Answer',
        prompt: 'Answer the following question concisely:\n$goal',
      }),
      node('exit', 'exit', 300, 400),
    ],
    edges: [
      edge('start', 'answer'),
      edge('answer', 'exit'),
    ],
  },

  // ── 2. Content production with human review ─────────────────────────
  {
    id: 'content-review',
    name: 'Blog Post with Review',
    description: 'Draft a blog post, pause for human review, revise or publish.',
    icon: '✍',
    category: 'Content',
    graphName: 'Blog Post Pipeline',
    graphGoal: 'Write a polished 800-word blog post about the given topic.',
    graphStylesheet: '* { llm_model: claude-sonnet-4-5; }',
    nodes: [
      node('start', 'start', 300, 80),
      node('outline', 'codergen', 300, 210, {
        label: 'Outline',
        prompt: 'Create a detailed outline for an 800-word blog post about: $goal\nReturn the outline with clear section headings.',
      }),
      node('draft', 'codergen', 300, 340, {
        label: 'Write Draft',
        prompt: 'Using the outline, write a full 800-word blog post. Write in a professional but approachable tone.',
      }),
      node('review', 'human', 300, 470, { label: 'Editor Review' }),
      node('decision', 'conditional', 300, 600, { label: 'Approved?' }),
      node('revise', 'codergen', 100, 740, {
        label: 'Revise',
        prompt: 'The editor requested changes. Revise the draft based on their feedback while maintaining the original structure.',
      }),
      node('publish', 'codergen', 500, 740, {
        label: 'Format & Publish',
        prompt: 'Polish the approved draft: fix any remaining grammar issues, add a meta description, and format as final Markdown.',
      }),
      node('exit', 'exit', 500, 870),
    ],
    edges: [
      edge('start', 'outline'),
      edge('outline', 'draft'),
      edge('draft', 'review'),
      edge('review', 'decision'),
      edge('decision', 'publish', { condition: 'outcome=approved', displayLabel: 'approved' }),
      edge('decision', 'revise', { condition: 'outcome=rejected', displayLabel: 'rejected' }),
      edge('revise', 'review'),
      edge('publish', 'exit'),
    ],
  },

  // ── 3. CI pipeline: build, lint, browser test ───────────────────────
  {
    id: 'ci-pipeline',
    name: 'CI: Build → Lint → Test',
    description: 'Run build, lint check, and browser validation with auto-fix loops.',
    icon: '⚙',
    category: 'Engineering',
    graphName: 'CI Pipeline',
    graphGoal: 'Build the project, fix any lint errors, and verify the rendered output.',
    graphStylesheet: '',
    nodes: [
      node('start', 'start', 350, 60),
      node('build', 'tool', 350, 190, {
        label: 'npm build',
        command: 'npm run build 2>&1',
      }),
      node('build_ok', 'conditional', 350, 320, { label: 'Build OK?' }),
      node('fix_build', 'codergen', 130, 450, {
        label: 'Fix Build',
        prompt: 'The build failed:\n$tool.output\n\nDiagnose the errors and output the exact file changes needed to fix them.',
      }),
      node('lint', 'tool', 560, 450, {
        label: 'Lint',
        command: 'npm run lint 2>&1',
      }),
      node('lint_ok', 'conditional', 560, 580, { label: 'Lint Clean?' }),
      node('fix_lint', 'codergen', 350, 700, {
        label: 'Fix Lint',
        prompt: 'Lint errors:\n$tool.output\n\nOutput the minimal changes to fix every lint issue.',
      }),
      node('browser', 'http', 760, 700, {
        label: 'Browser Check',
        http_url: 'http://localhost:4000/validate',
        http_method: 'POST',
        http_body: '{"url": "http://localhost:3000", "checks": ["renders", "no console errors"]}',
      }),
      node('exit', 'exit', 760, 830),
    ],
    edges: [
      edge('start', 'build'),
      edge('build', 'build_ok'),
      edge('build_ok', 'lint', { condition: 'outcome=success', displayLabel: 'pass' }),
      edge('build_ok', 'fix_build', { condition: 'outcome=failure', displayLabel: 'fail' }),
      edge('fix_build', 'build'),
      edge('lint', 'lint_ok'),
      edge('lint_ok', 'browser', { condition: 'outcome=success', displayLabel: 'clean' }),
      edge('lint_ok', 'fix_lint', { condition: 'outcome=failure', displayLabel: 'errors' }),
      edge('fix_lint', 'lint'),
      edge('browser', 'exit'),
    ],
  },

  // ── 4. Competitive research with parallel branches ──────────────────
  {
    id: 'market-research',
    name: 'Competitor Analysis',
    description: 'Research 3 competitors in parallel, then synthesise into a strategy memo.',
    icon: '📊',
    category: 'Research',
    graphName: 'Competitor Analysis',
    graphGoal: 'Analyse top 3 competitors and produce a strategic recommendations memo.',
    graphStylesheet: '* { llm_model: claude-sonnet-4-5; }\n.synthesis { llm_model: claude-opus-4-6; }',
    nodes: [
      node('start', 'start', 400, 60),
      node('identify', 'codergen', 400, 190, {
        label: 'Identify Competitors',
        prompt: 'For the market described by "$goal", identify the top 3 competitors. Return their names and brief descriptions.',
      }),
      node('fork', 'parallel', 400, 320, { label: 'Research All' }),
      node('comp_a', 'codergen', 150, 470, {
        label: 'Competitor A',
        prompt: 'Deep-dive on Competitor A: pricing, features, market share, strengths, weaknesses. Be specific with numbers where possible.',
      }),
      node('comp_b', 'codergen', 400, 470, {
        label: 'Competitor B',
        prompt: 'Deep-dive on Competitor B: pricing, features, market share, strengths, weaknesses. Be specific with numbers where possible.',
      }),
      node('comp_c', 'codergen', 650, 470, {
        label: 'Competitor C',
        prompt: 'Deep-dive on Competitor C: pricing, features, market share, strengths, weaknesses. Be specific with numbers where possible.',
      }),
      node('join', 'fan_in', 400, 620, { label: 'Collect' }),
      node('synthesis', 'codergen', 400, 750, {
        label: 'Strategy Memo',
        prompt: 'Using all three competitor analyses, write a strategic recommendations memo:\n1. Competitive landscape summary\n2. Our differentiation opportunities\n3. Pricing strategy suggestion\n4. Feature gaps to close\n5. Recommended next actions',
      }),
      node('exit', 'exit', 400, 880),
    ],
    edges: [
      edge('start', 'identify'),
      edge('identify', 'fork'),
      edge('fork', 'comp_a'),
      edge('fork', 'comp_b'),
      edge('fork', 'comp_c'),
      edge('comp_a', 'join'),
      edge('comp_b', 'join'),
      edge('comp_c', 'join'),
      edge('join', 'synthesis'),
      edge('synthesis', 'exit'),
    ],
  },

  // ── 5. Customer support ticket triage ───────────────────────────────
  {
    id: 'support-triage',
    name: 'Support Ticket Triage',
    description: 'Classify a support ticket, route to the right handler, draft a response.',
    icon: '🎫',
    category: 'Operations',
    graphName: 'Support Triage',
    graphGoal: 'Classify and respond to an incoming customer support ticket.',
    graphStylesheet: '* { llm_model: claude-sonnet-4-5; }',
    nodes: [
      node('start', 'start', 350, 60),
      node('classify', 'codergen', 350, 190, {
        label: 'Classify Ticket',
        prompt: 'Classify this support ticket into exactly one category:\n- billing\n- technical\n- feature_request\n- account\n\nTicket: $goal\n\nReturn JSON: {"category": "...", "urgency": "low|medium|high", "summary": "..."}',
      }),
      node('route', 'conditional', 350, 330, { label: 'Category?' }),
      node('billing', 'codergen', 100, 470, {
        label: 'Billing Response',
        prompt: 'Draft a helpful response for this billing issue. Include refund/credit policy links if relevant.\nTicket: $goal',
      }),
      node('technical', 'codergen', 350, 470, {
        label: 'Technical Response',
        prompt: 'Draft a technical troubleshooting response. Include step-by-step instructions.\nTicket: $goal',
      }),
      node('other', 'codergen', 600, 470, {
        label: 'General Response',
        prompt: 'Draft a helpful response for this feature request or account inquiry. Set expectations clearly.\nTicket: $goal',
      }),
      node('review', 'human', 350, 610, { label: 'Agent Review' }),
      node('exit', 'exit', 350, 740),
    ],
    edges: [
      edge('start', 'classify'),
      edge('classify', 'route'),
      edge('route', 'billing', { condition: 'category=billing', displayLabel: 'billing' }),
      edge('route', 'technical', { condition: 'category=technical', displayLabel: 'technical' }),
      edge('route', 'other', { condition: 'category!=billing && category!=technical', displayLabel: 'other' }),
      edge('billing', 'review'),
      edge('technical', 'review'),
      edge('other', 'review'),
      edge('review', 'exit'),
    ],
  },

  // ── 6. CSV data pipeline with manager + retry (the complex one) ─────
  {
    id: 'csv-data-pipeline',
    name: 'CSV Data Pipeline',
    description: 'Ingest a large CSV, extract insights, answer questions — with a manager that retries bad answers.',
    icon: '🗂',
    category: 'Data',
    graphName: 'CSV Data Pipeline',
    graphGoal: 'Ingest the provided CSV dataset, run data extraction, and produce high-quality answers to analytical questions.',
    graphStylesheet: '* { llm_model: claude-sonnet-4-5; }\n.quality { llm_model: claude-opus-4-6; }',
    nodes: [
      // Row 1: start
      node('start', 'start', 400, 50),

      // Row 2: ingest the CSV
      node('ingest', 'tool', 400, 170, {
        label: 'Load CSV',
        command: 'python3 -c "\nimport csv, json, sys\nwith open(\'data.csv\') as f:\n    rows = list(csv.DictReader(f))\nprint(json.dumps({\'row_count\': len(rows), \'columns\': list(rows[0].keys()) if rows else [], \'sample\': rows[:5]}))\n"',
      }),

      // Row 3: profile the data
      node('profile', 'codergen', 400, 310, {
        label: 'Profile Data',
        prompt: 'You received a CSV dataset with these columns: $tool.output\n\nAnalyse the structure:\n1. Column types (numeric, categorical, date, text)\n2. Any obvious data quality issues (nulls, outliers)\n3. Key statistical summaries\n4. What kinds of questions this data can answer\n\nReturn a structured data profile as JSON.',
      }),

      // Row 4: fork — run analyses in parallel
      node('fork', 'parallel', 400, 450, { label: 'Parallel Analysis' }),

      node('trends', 'codergen', 150, 600, {
        label: 'Trend Analysis',
        prompt: 'Using the data profile and raw sample data, identify the top 5 trends, patterns, or anomalies in this dataset. Support each finding with specific numbers.',
      }),
      node('aggregates', 'tool', 400, 600, {
        label: 'Run Aggregations',
        command: 'python3 -c "\nimport csv, json\nfrom collections import Counter, defaultdict\nwith open(\'data.csv\') as f:\n    rows = list(csv.DictReader(f))\ncols = list(rows[0].keys())\nstats = {}\nfor c in cols:\n    vals = [r[c] for r in rows if r[c]]\n    try:\n        nums = [float(v) for v in vals]\n        stats[c] = {\'min\': min(nums), \'max\': max(nums), \'mean\': round(sum(nums)/len(nums),2), \'count\': len(nums)}\n    except ValueError:\n        stats[c] = dict(Counter(vals).most_common(10))\nprint(json.dumps(stats, indent=2))\n"',
      }),
      node('questions', 'codergen', 650, 600, {
        label: 'Generate Questions',
        prompt: 'Based on the data profile, generate 5 high-value analytical questions that a business analyst would ask about this dataset. Return as a JSON array of strings.',
      }),

      // Row 5: join
      node('join', 'fan_in', 400, 750, { label: 'Collect Results' }),

      // Row 6: answer the questions — this is managed
      node('answer', 'codergen', 400, 890, {
        label: 'Answer Questions',
        prompt: 'You have:\n- Data profile and statistics from the aggregation step\n- Trend analysis findings\n- A list of analytical questions\n\nAnswer each question thoroughly with specific numbers, percentages, and comparisons. For each answer, include:\n1. The finding\n2. Supporting data points\n3. Business implication\n\nReturn as JSON: [{"question": "...", "answer": "...", "confidence": 0.0-1.0}]',
      }),

      // Row 7: manager evaluates quality and can force a retry
      node('manager', 'manager', 400, 1040, {
        label: 'Quality Manager',
        prompt: 'Evaluate every answer for quality:\n- Is it actually supported by the data?\n- Does it include specific numbers?\n- Is the confidence score reasonable?\n- Would a business analyst find this useful?\n\nIf any answer scores below 0.7 confidence or lacks supporting data, set outcome=retry and explain what needs improving. Otherwise set outcome=pass.',
        max_cycles: 4,
      }),

      // Row 8: conditional on manager outcome
      node('quality_check', 'conditional', 400, 1180, { label: 'Quality OK?' }),

      // Row 8 branches
      node('retry_answers', 'codergen', 150, 1320, {
        label: 'Improve Answers',
        prompt: 'The quality manager flagged issues with your answers:\n$manager.feedback\n\nRe-answer the flagged questions with more specific data and better supporting evidence. Raise your confidence only if warranted.',
      }),

      node('report', 'codergen', 600, 1320, {
        label: 'Generate Report',
        prompt: 'Compile a final executive report:\n\n## Dataset Overview\nSummarise the dataset.\n\n## Key Findings\nTop 5 findings from trend analysis.\n\n## Detailed Q&A\nAll questions and verified answers.\n\n## Recommendations\n3 actionable recommendations based on the data.\n\nFormat as clean Markdown.',
      }),

      // Row 9: exit
      node('exit', 'exit', 600, 1460),
    ],
    edges: [
      edge('start', 'ingest'),
      edge('ingest', 'profile'),
      edge('profile', 'fork'),

      edge('fork', 'trends'),
      edge('fork', 'aggregates'),
      edge('fork', 'questions'),

      edge('trends', 'join'),
      edge('aggregates', 'join'),
      edge('questions', 'join'),

      edge('join', 'answer'),
      edge('answer', 'manager'),
      edge('manager', 'quality_check'),

      edge('quality_check', 'report', { condition: 'outcome=pass', displayLabel: 'pass' }),
      edge('quality_check', 'retry_answers', { condition: 'outcome=retry', displayLabel: 'retry' }),
      edge('retry_answers', 'manager'),

      edge('report', 'exit'),
    ],
  },
]
