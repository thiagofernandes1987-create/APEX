"""
UCO-Sensor — Web Dashboard HTML Generator (M4.1)
=================================================
Generates a self-contained HTML page with:
  • Temporal line charts for H, CC, Cognitive CC per module (Chart.js 4.x CDN)
  • Module health cards with status icons and trend arrows
  • SQALE debt budget progress bar with velocity forecast
  • SAST security rating badges per module
  • Top-issues table sorted by severity
  • Auto-refresh via setInterval + fetch('/dashboard')

Design constraints:
  • Zero Python dependencies beyond stdlib
  • Zero npm/build step — Chart.js loaded from jsDelivr CDN
  • Works standalone when dashboard_data is pre-embedded as JSON
  • Responsive layout via CSS grid; dark theme matching existing HTML report

Usage:
    from report.webui import generate_dashboard_html
    html = generate_dashboard_html(dashboard_data=data_dict, title="My Project")
    Path("dashboard.html").write_text(html, encoding="utf-8")
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

# ── Constants ─────────────────────────────────────────────────────────────────

_CHARTJS_CDN = (
    "https://cdn.jsdelivr.net/npm/chart.js@4.4.2/dist/chart.umd.min.js"
)

_RATING_COLOR_MAP = {
    "A": "#4ade80",
    "B": "#86efac",
    "C": "#fbbf24",
    "D": "#f97316",
    "E": "#ef4444",
}

_STATUS_CSS = {
    "CRITICAL": "color:#f87171",
    "WARNING":  "color:#fbbf24",
    "STABLE":   "color:#4ade80",
}

_TREND_LABEL = {
    "DEGRADING":         "↗ DEGRADING",
    "IMPROVING":         "↘ IMPROVING",
    "STABLE":            "→ STABLE",
    "VOLATILE":          "⚡ VOLATILE",
    "INSUFFICIENT_DATA": "— N/A",
}

_TREND_CSS = {
    "DEGRADING":         "color:#f87171",
    "IMPROVING":         "color:#4ade80",
    "STABLE":            "color:#64748b",
    "VOLATILE":          "color:#fbbf24",
    "INSUFFICIENT_DATA": "color:#64748b",
}

# ── Public API ────────────────────────────────────────────────────────────────

def generate_dashboard_html(
    dashboard_data:  Optional[Dict[str, Any]] = None,
    title:           str = "UCO-Sensor Dashboard",
    refresh_seconds: int = 30,
    api_base:        str = "",
    tool_version:    str = "1.0.0",
) -> str:
    """
    Generate a self-contained HTML dashboard page.

    Parameters
    ----------
    dashboard_data : dict | None
        Pre-populated data from handle_dashboard() / GET /dashboard.
        When provided, it is embedded as JSON so the page renders immediately
        without a round-trip HTTP fetch.  When None the page performs a
        ``fetch('/dashboard')`` on load.
    title : str
        Browser tab and ``<title>`` content.
    refresh_seconds : int
        setInterval period for auto-refresh (default 30 s).
    api_base : str
        Base URL prepended to API calls.  Empty = same origin.
    tool_version : str
        Displayed in the header version badge.

    Returns
    -------
    str
        Complete, self-contained HTML document (UTF-8 safe).
    """
    # ── Embed initial data ────────────────────────────────────────────────────
    if dashboard_data is not None:
        # json.dumps with default=str handles datetime / non-serialisable values
        initial_data_js = (
            "const INITIAL_DATA = "
            + json.dumps(dashboard_data, default=str)
            + ";"
        )
    else:
        initial_data_js = "const INITIAL_DATA = null;"

    # Pre-render module cards for no-JS fallback (progressive enhancement)
    modules: List[Dict[str, Any]] = (dashboard_data or {}).get("modules", [])
    counts  = (dashboard_data or {}).get("status_counts", {})
    trends  = (dashboard_data or {}).get("trend_counts", {})
    budget  = (dashboard_data or {}).get("debt_budget", {})

    noop_fallback_cards = _render_module_cards_html(modules) if modules else (
        "<p style='color:#64748b;font-size:.85rem'>"
        "No modules tracked yet. POST /analyze to add a module.</p>"
    )

    # ── Assemble HTML ─────────────────────────────────────────────────────────
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{_esc(title)}</title>
<script src="{_CHARTJS_CDN}"></script>
<style>
{_CSS}
</style>
</head>
<body>
<div class="container" id="app">

  <!-- ── Header ───────────────────────────────────────────────────── -->
  <div class="header">
    <h1>
      <svg width="26" height="26" viewBox="0 0 26 26" fill="none" aria-hidden="true">
        <circle cx="13" cy="13" r="12" stroke="#3b82f6" stroke-width="2"/>
        <path d="M7 19 L13 7 L19 19" stroke="#3b82f6" stroke-width="2"
              stroke-linecap="round" stroke-linejoin="round"/>
        <circle cx="13" cy="13" r="2" fill="#3b82f6"/>
      </svg>
      UCO-Sensor
      <span class="version-badge">v{_esc(tool_version)}</span>
    </h1>
    <div id="refresh-info" class="refresh-info">
      Refreshing every {refresh_seconds}&nbsp;s
    </div>
  </div>

  <!-- ── Summary cards ─────────────────────────────────────────────── -->
  <div class="summary-grid" id="summary-grid">
    <div class="summary-card">
      <div class="count" style="{_STATUS_CSS['CRITICAL']}"
           id="cnt-critical">{counts.get('critical', 0)}</div>
      <div class="label">Critical</div>
    </div>
    <div class="summary-card">
      <div class="count" style="{_STATUS_CSS['WARNING']}"
           id="cnt-warning">{counts.get('warning', 0)}</div>
      <div class="label">Warning</div>
    </div>
    <div class="summary-card">
      <div class="count" style="{_STATUS_CSS['STABLE']}"
           id="cnt-stable">{counts.get('stable', 0)}</div>
      <div class="label">Stable</div>
    </div>
    <div class="summary-card">
      <div class="count" style="{_TREND_CSS['DEGRADING']}"
           id="cnt-degrading">{trends.get('degrading', 0)}</div>
      <div class="label">Degrading</div>
    </div>
    <div class="summary-card">
      <div class="count" style="{_TREND_CSS['IMPROVING']}"
           id="cnt-improving">{trends.get('improving', 0)}</div>
      <div class="label">Improving</div>
    </div>
    <div class="summary-card">
      <div class="count" id="cnt-total">{len(modules)}</div>
      <div class="label">Total Modules</div>
    </div>
  </div>

  <!-- ── Temporal charts ───────────────────────────────────────────── -->
  <div class="chart-grid" id="chart-grid">
    <div class="chart-card">
      <h3>Hamiltonian Energy — History</h3>
      <div class="chart-wrapper">
        <canvas id="chart-hamiltonian" aria-label="Hamiltonian trend"></canvas>
      </div>
    </div>
    <div class="chart-card">
      <h3>Cyclomatic Complexity — History</h3>
      <div class="chart-wrapper">
        <canvas id="chart-cc" aria-label="Cyclomatic complexity trend"></canvas>
      </div>
    </div>
    <div class="chart-card">
      <h3>Cognitive Complexity (per module)</h3>
      <div class="chart-wrapper">
        <canvas id="chart-cog" aria-label="Cognitive complexity per module"></canvas>
      </div>
    </div>
    <div class="chart-card">
      <h3>SQALE Debt — minutes (per module)</h3>
      <div class="chart-wrapper">
        <canvas id="chart-debt" aria-label="SQALE debt per module"></canvas>
      </div>
    </div>
  </div>

  <!-- ── Module health ─────────────────────────────────────────────── -->
  <div class="section" id="module-health-section">
    <h2>⬛ Module Health</h2>
    <div class="module-grid" id="module-grid">
      {noop_fallback_cards}
    </div>
  </div>

  <!-- ── Top issues table ──────────────────────────────────────────── -->
  <div class="section">
    <h2>🔴 Top Issues</h2>
    <table id="issues-table">
      <thead><tr>
        <th>Module</th>
        <th>Status</th>
        <th>H</th>
        <th>CC</th>
        <th>SQALE</th>
        <th>Trend</th>
        <th>Snapshots</th>
      </tr></thead>
      <tbody id="issues-tbody">
        <tr><td colspan="7" style="text-align:center;color:#64748b">
          Loading…
        </td></tr>
      </tbody>
    </table>
  </div>

  <!-- ── Debt budget ───────────────────────────────────────────────── -->
  <div class="section">
    <h2>💳 SQALE Debt Budget</h2>
    <div id="debt-budget-content">
      {_render_debt_budget_html(budget)}
    </div>
  </div>

</div><!-- /container -->

<script>
/* ── Constants ──────────────────────────────────────────────────────────── */
{initial_data_js}
const API_BASE      = {json.dumps(api_base)};
const REFRESH_MS    = {refresh_seconds * 1000};
const PALETTE       = [
  '#3b82f6','#f87171','#4ade80','#fbbf24','#a78bfa',
  '#34d399','#f472b6','#60a5fa','#fb923c','#818cf8',
];
const RATING_COLOR  = {json.dumps(_RATING_COLOR_MAP)};
const TREND_LABEL   = {json.dumps(_TREND_LABEL)};
const TREND_CSS_MAP = {json.dumps(_TREND_CSS)};

/* ── Chart instances ─────────────────────────────────────────────────────── */
let charts = {{}};
let moduleHistoryCache = {{}};

const COMMON_CHART_OPTS = {{
  responsive: true,
  maintainAspectRatio: false,
  interaction: {{ intersect: false, mode: 'index' }},
  animation: {{ duration: 400 }},
  plugins: {{
    legend: {{ labels: {{ color: '#94a3b8', font: {{ size: 11 }} }} }},
  }},
  scales: {{
    x: {{ ticks: {{ color:'#64748b', font:{{size:10}} }}, grid:{{ color:'#1a1f35' }} }},
    y: {{ ticks: {{ color:'#64748b', font:{{size:10}} }}, grid:{{ color:'#1a1f35' }} }},
  }},
}};

function initCharts() {{
  ['chart-hamiltonian','chart-cc','chart-cog','chart-debt'].forEach(id => {{
    const canvas = document.getElementById(id);
    if (!canvas) return;
    if (charts[id]) charts[id].destroy();
    charts[id] = new Chart(canvas.getContext('2d'), {{
      type: 'line',
      data: {{ labels: [], datasets: [] }},
      options: {{ ...COMMON_CHART_OPTS }},
    }});
  }});
}}

function setChart(id, labels, datasets) {{
  const c = charts[id];
  if (!c) return;
  c.data.labels   = labels;
  c.data.datasets = datasets;
  c.update('none');
}}

/* ── Fetch module history ────────────────────────────────────────────────── */
async function fetchHistory(moduleId, window = 20) {{
  if (moduleHistoryCache[moduleId]) return moduleHistoryCache[moduleId];
  try {{
    const r = await fetch(
      `${{API_BASE}}/history?module=${{encodeURIComponent(moduleId)}}&window=${{window}}`
    );
    const j = await r.json();
    const snaps = (j.data || j).snapshots || [];
    moduleHistoryCache[moduleId] = snaps;
    return snaps;
  }} catch {{ return []; }}
}}

/* ── Render helpers ──────────────────────────────────────────────────────── */
function ratingBadge(r) {{
  if (!r) return '—';
  const bg = RATING_COLOR[r] || '#64748b';
  return `<span class="rating" style="background:${{bg}}">${{r}}</span>`;
}}

function statusStyle(s) {{
  return s === 'CRITICAL' ? 'color:#f87171'
       : s === 'WARNING'  ? 'color:#fbbf24'
       : 'color:#4ade80';
}}

function dotClass(s) {{
  return s === 'CRITICAL' ? 'dot-critical'
       : s === 'WARNING'  ? 'dot-warning'
       : 'dot-stable';
}}

/* ── Render dashboard ────────────────────────────────────────────────────── */
async function renderDashboard(data) {{
  const modules = data.modules        || [];
  const counts  = data.status_counts  || {{}};
  const trends  = data.trend_counts   || {{}};
  const budget  = data.debt_budget    || {{}};

  /* Summary counts */
  document.getElementById('cnt-critical').textContent = counts.critical  || 0;
  document.getElementById('cnt-warning' ).textContent = counts.warning   || 0;
  document.getElementById('cnt-stable'  ).textContent = counts.stable    || 0;
  document.getElementById('cnt-degrading').textContent= trends.degrading || 0;
  document.getElementById('cnt-improving').textContent= trends.improving || 0;
  document.getElementById('cnt-total'   ).textContent = modules.length;

  /* Module cards */
  const mgrid = document.getElementById('module-grid');
  if (modules.length === 0) {{
    mgrid.innerHTML =
      '<p style="color:#64748b;font-size:.85rem">No modules tracked yet. POST /analyze to add one.</p>';
  }} else {{
    mgrid.innerHTML = modules.map(m => {{
      const tLabel = TREND_LABEL[m.trend_direction] || '—';
      const tStyle = TREND_CSS_MAP[m.trend_direction] || '';
      return `
        <div class="module-card">
          <div class="name">
            <span class="status-dot ${{dotClass(m.status)}}"></span>
            ${{escHtml(m.module_id)}}
          </div>
          <div class="metrics">
            <span>H</span>
            <span class="metric-val" style="${{statusStyle(m.status)}}">
              ${{(m.hamiltonian||0).toFixed(2)}}
            </span>
            <span>CC</span>
            <span class="metric-val">${{m.cyclomatic_complexity||0}}</span>
            <span>CogCC</span>
            <span class="metric-val">${{m.cognitive_complexity != null ? m.cognitive_complexity : '—'}}</span>
            <span>SQALE</span>
            <span class="metric-val">${{ratingBadge(m.sqale_rating)}}</span>
            <span>Trend</span>
            <span class="metric-val" style="${{tStyle}}">${{tLabel}}</span>
            <span>Snaps</span>
            <span class="metric-val">${{m.snapshots_count||0}}</span>
          </div>
        </div>`;
    }}).join('');
  }}

  /* Issues table */
  const tbody  = document.getElementById('issues-tbody');
  const issues = modules.filter(m => m.status !== 'STABLE').slice(0, 10);
  if (issues.length === 0) {{
    tbody.innerHTML =
      '<tr><td colspan="7" style="text-align:center;color:#4ade80">✅ No issues</td></tr>';
  }} else {{
    tbody.innerHTML = issues.map(m => {{
      const tLabel = TREND_LABEL[m.trend_direction] || '—';
      const tStyle = TREND_CSS_MAP[m.trend_direction] || '';
      return `<tr>
        <td style="max-width:220px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap"
            title="${{escHtml(m.module_id)}}">${{escHtml(m.module_id)}}</td>
        <td style="${{statusStyle(m.status)}}">${{m.status}}</td>
        <td>${{(m.hamiltonian||0).toFixed(2)}}</td>
        <td>${{m.cyclomatic_complexity||0}}</td>
        <td>${{ratingBadge(m.sqale_rating)}}</td>
        <td style="${{tStyle}}">${{tLabel}}</td>
        <td>${{m.snapshots_count||0}}</td>
      </tr>`;
    }}).join('');
  }}

  /* Debt budget */
  const totalDebt   = budget.total_debt_minutes || 0;
  const budgetLimit = budget.budget_minutes || 480;
  const usedPct     = Math.min(100, (totalDebt / Math.max(budgetLimit, 1)) * 100).toFixed(1);
  const barClass    = usedPct >= 100 ? 'debt-over' : usedPct >= 75 ? 'debt-warn' : 'debt-ok';
  const daysLeft    = budget.days_until_exhausted != null ? budget.days_until_exhausted : '∞';
  document.getElementById('debt-budget-content').innerHTML = `
    <div style="display:flex;justify-content:space-between;font-size:.83rem;margin-bottom:6px;flex-wrap:wrap;gap:8px">
      <span>Total debt: <strong>${{totalDebt}} min</strong></span>
      <span>Budget: <strong>${{budgetLimit}} min</strong></span>
      <span>Used: <strong>${{usedPct}}%</strong></span>
      <span>Days until exhausted: <strong>${{daysLeft}}</strong></span>
    </div>
    <div class="debt-bar">
      <div class="debt-fill ${{barClass}}" style="width:${{usedPct}}%"></div>
    </div>`;

  /* Temporal charts */
  await renderTemporalCharts(modules.slice(0, 6));
}}

async function renderTemporalCharts(modules) {{
  if (!modules.length) return;

  /* Fetch histories in parallel */
  const histories = await Promise.all(
    modules.map(m => fetchHistory(m.module_id, 20))
  );

  /* Build merged label set (timestamps) */
  const tsSet = new Set();
  histories.forEach(snaps => snaps.forEach(s => tsSet.add(s.timestamp || s.commit_hash)));
  const sortedTs = Array.from(tsSet).sort();
  const labels   = sortedTs.map(t => {{
    if (typeof t === 'number') {{
      return new Date(t * 1000).toLocaleDateString('en', {{month:'short', day:'numeric'}});
    }}
    return String(t).slice(0, 7);
  }});

  /* H and CC temporal charts */
  [['chart-hamiltonian','hamiltonian'],['chart-cc','cc']].forEach(([id, key]) => {{
    const datasets = modules.map((m, i) => {{
      const snaps  = histories[i];
      const byTs   = {{}};
      snaps.forEach(s => {{ byTs[s.timestamp || s.commit_hash] = s[key]; }});
      return {{
        label:           m.module_id.split('/').pop(),
        data:            sortedTs.map(t => byTs[t] ?? null),
        borderColor:     PALETTE[i % PALETTE.length],
        backgroundColor: PALETTE[i % PALETTE.length] + '22',
        tension:         0.35,
        pointRadius:     3,
        spanGaps:        true,
      }};
    }});
    setChart(id, labels, datasets);
  }});

  /* Cognitive CC + SQALE debt — snapshot from dashboard (no history endpoint) */
  const cogLabels  = modules.map(m => m.module_id.split('/').pop());
  const cogData    = modules.map(m => m.cognitive_complexity || 0);
  const debtData   = modules.map(m => m.sqale_debt_minutes  || 0);

  setChart('chart-cog', cogLabels, [{{
    label: 'Cognitive CC', data: cogData, type: 'bar',
    backgroundColor: modules.map((_, i) => PALETTE[i % PALETTE.length] + 'aa'),
    borderColor:     modules.map((_, i) => PALETTE[i % PALETTE.length]),
    borderWidth: 1,
  }}]);

  setChart('chart-debt', cogLabels, [{{
    label: 'Debt (min)', data: debtData, type: 'bar',
    backgroundColor: modules.map((_, i) => PALETTE[i % PALETTE.length] + '99'),
    borderColor:     modules.map((_, i) => PALETTE[i % PALETTE.length]),
    borderWidth: 1,
  }}]);
}}

/* ── Fetch + render loop ─────────────────────────────────────────────────── */
async function fetchAndRender() {{
  try {{
    const r = await fetch(`${{API_BASE}}/dashboard`);
    const j = await r.json();
    moduleHistoryCache = {{}};
    await renderDashboard(j.data || j);
    document.getElementById('refresh-info').textContent =
      `Last updated: ${{new Date().toLocaleTimeString()}} · every ${{REFRESH_MS/1000}}s`;
  }} catch (e) {{
    document.getElementById('refresh-info').textContent =
      '⚠ Server unreachable — ' + new Date().toLocaleTimeString();
  }}
}}

function escHtml(s) {{
  return String(s)
    .replace(/&/g,'&amp;').replace(/</g,'&lt;')
    .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}}

/* ── Init ────────────────────────────────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', async () => {{
  initCharts();
  if (INITIAL_DATA) {{
    await renderDashboard(INITIAL_DATA);
  }} else {{
    await fetchAndRender();
  }}
  setInterval(fetchAndRender, REFRESH_MS);
}});
</script>
</body>
</html>"""


# ── Private helpers ───────────────────────────────────────────────────────────

def _esc(s: str) -> str:
    """Minimal HTML escaping for static Python template insertions."""
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _render_module_cards_html(modules: List[Dict[str, Any]]) -> str:
    """Server-side progressive-enhancement fallback for module cards."""
    cards = []
    for m in modules:
        status = m.get("status", "STABLE")
        dot = (
            "dot-critical" if status == "CRITICAL" else
            "dot-warning"  if status == "WARNING"  else
            "dot-stable"
        )
        sqale_r = m.get("sqale_rating")
        sqale_badge = ""
        if sqale_r:
            bg = _RATING_COLOR_MAP.get(sqale_r, "#64748b")
            sqale_badge = f'<span class="rating" style="background:{bg}">{sqale_r}</span>'

        trend_d = m.get("trend_direction", "INSUFFICIENT_DATA")
        trend_l = _TREND_LABEL.get(trend_d, "—")
        trend_s = _TREND_CSS.get(trend_d, "")
        cog_val = m.get("cognitive_complexity")
        cog_str = str(cog_val) if cog_val is not None else "—"

        cards.append(
            f'<div class="module-card">'
            f'<div class="name"><span class="status-dot {dot}"></span>{_esc(m.get("module_id",""))}</div>'
            f'<div class="metrics">'
            f'<span>H</span><span class="metric-val">{m.get("hamiltonian",0):.2f}</span>'
            f'<span>CC</span><span class="metric-val">{m.get("cyclomatic_complexity",0)}</span>'
            f'<span>CogCC</span><span class="metric-val">{cog_str}</span>'
            f'<span>SQALE</span><span class="metric-val">{sqale_badge or "—"}</span>'
            f'<span>Trend</span><span class="metric-val" style="{trend_s}">{trend_l}</span>'
            f'<span>Snaps</span><span class="metric-val">{m.get("snapshots_count",0)}</span>'
            f'</div></div>'
        )
    return "\n".join(cards)


def _render_debt_budget_html(budget: Dict[str, Any]) -> str:
    total     = budget.get("total_debt_minutes", 0)
    limit     = budget.get("budget_minutes", 480)
    pct       = min(100.0, total / max(limit, 1) * 100)
    bar_class = "debt-over" if pct >= 100 else "debt-warn" if pct >= 75 else "debt-ok"
    days      = budget.get("days_until_exhausted")
    days_str  = str(days) if days is not None else "∞"
    return (
        f'<div style="display:flex;justify-content:space-between;font-size:.83rem;'
        f'margin-bottom:6px;flex-wrap:wrap;gap:8px">'
        f'<span>Total debt: <strong>{total} min</strong></span>'
        f'<span>Budget: <strong>{limit} min</strong></span>'
        f'<span>Used: <strong>{pct:.1f}%</strong></span>'
        f'<span>Days until exhausted: <strong>{days_str}</strong></span>'
        f'</div>'
        f'<div class="debt-bar">'
        f'<div class="debt-fill {bar_class}" style="width:{pct:.1f}%"></div>'
        f'</div>'
    )


# ── CSS ───────────────────────────────────────────────────────────────────────

_CSS = """
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Segoe UI',system-ui,sans-serif;background:#0f1117;
     color:#e2e8f0;line-height:1.5}
a{color:#7dd3fc;text-decoration:none}
.container{max-width:1400px;margin:0 auto;padding:24px}

/* Header */
.header{display:flex;align-items:center;justify-content:space-between;
  padding:20px 24px;background:#1e2130;border-radius:12px;
  margin-bottom:24px;border:1px solid #2d3352;flex-wrap:wrap;gap:12px}
.header h1{font-size:1.4rem;font-weight:700;color:#f1f5f9;
  display:flex;align-items:center;gap:10px}
.version-badge{font-size:.68rem;background:#3b82f6;color:#fff;
  padding:2px 8px;border-radius:9999px;font-weight:700}
.refresh-info{font-size:.75rem;color:#64748b}

/* Summary */
.summary-grid{display:grid;
  grid-template-columns:repeat(auto-fit,minmax(140px,1fr));
  gap:12px;margin-bottom:24px}
.summary-card{background:#1e2130;border:1px solid #2d3352;
  border-radius:12px;padding:16px 20px;text-align:center}
.summary-card .count{font-size:2.4rem;font-weight:800;line-height:1}
.summary-card .label{font-size:.72rem;color:#64748b;margin-top:4px;
  text-transform:uppercase;letter-spacing:.06em}

/* Charts */
.chart-grid{display:grid;
  grid-template-columns:repeat(auto-fit,minmax(380px,1fr));
  gap:20px;margin-bottom:24px}
.chart-card{background:#1e2130;border:1px solid #2d3352;
  border-radius:12px;padding:20px}
.chart-card h3{font-size:.82rem;font-weight:600;color:#94a3b8;margin-bottom:12px}
.chart-wrapper{position:relative;height:200px}

/* Section */
.section{background:#1e2130;border:1px solid #2d3352;
  border-radius:12px;padding:20px;margin-bottom:20px}
.section h2{font-size:.95rem;font-weight:600;margin-bottom:16px;
  color:#cbd5e1;padding-bottom:8px;border-bottom:1px solid #2d3352}

/* Module cards */
.module-grid{display:grid;
  grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:12px}
.module-card{background:#0f1117;border:1px solid #2d3352;
  border-radius:10px;padding:14px 16px;transition:border-color .15s}
.module-card:hover{border-color:#3b82f6}
.module-card .name{font-size:.83rem;font-weight:600;color:#e2e8f0;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis;margin-bottom:8px;
  display:flex;align-items:center;gap:6px}
.module-card .metrics{display:grid;grid-template-columns:auto 1fr;
  gap:2px 12px;font-size:.72rem;color:#94a3b8}
.metric-val{color:#e2e8f0;font-weight:600}

/* Status dots */
.status-dot{width:8px;height:8px;border-radius:50%;
  display:inline-block;flex-shrink:0}
.dot-critical{background:#f87171}
.dot-warning{background:#fbbf24}
.dot-stable{background:#4ade80}

/* Rating badge */
.rating{display:inline-block;width:22px;height:22px;border-radius:5px;
  text-align:center;line-height:22px;font-size:.72rem;font-weight:700;
  color:#0f1117}

/* Table */
table{width:100%;border-collapse:collapse;font-size:.82rem}
th{text-align:left;padding:8px 12px;color:#64748b;font-weight:500;
   border-bottom:1px solid #2d3352;white-space:nowrap}
td{padding:8px 12px;border-bottom:1px solid #1a1f35;vertical-align:middle}
tr:last-child td{border-bottom:none}
tr:hover td{background:#1a1f35}

/* Debt bar */
.debt-bar{height:8px;background:#1a1f35;border-radius:4px;overflow:hidden}
.debt-fill{height:100%;border-radius:4px;transition:width .5s ease}
.debt-ok{background:#4ade80}
.debt-warn{background:#fbbf24}
.debt-over{background:#f87171}
"""
