"""
UCO-Sensor — HTML Report Generator
=====================================
Gera um relatório HTML standalone (zero dependências externas) a partir
de ScanResult (snapshot) ou GitHistoryScanResult (temporal).

Uso:
  from report.html_report import generate_html_report
  html = generate_html_report(scan_result, title="Meu Projeto")
  Path("uco-report.html").write_text(html)
"""
from __future__ import annotations

import json
import time
from datetime import datetime
from typing import Union, Any

from .badge import badge_color


# ─── CSS inline ──────────────────────────────────────────────────────────────

_CSS = """
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Segoe UI',system-ui,sans-serif;background:#0f1117;color:#e2e8f0;line-height:1.5}
a{color:#7dd3fc;text-decoration:none}
.container{max-width:1200px;margin:0 auto;padding:24px}
/* Header */
.header{display:flex;align-items:center;justify-content:space-between;
  padding:20px 24px;background:#1e2130;border-radius:12px;margin-bottom:24px;
  border:1px solid #2d3352}
.header h1{font-size:1.4rem;font-weight:700;color:#f1f5f9}
.header .meta{font-size:.8rem;color:#64748b}
.badge-row{display:flex;gap:12px;align-items:center;flex-wrap:wrap}
/* Score gauge */
.gauge-card{background:#1e2130;border:1px solid #2d3352;border-radius:12px;
  padding:20px;text-align:center;min-width:160px}
.gauge-score{font-size:3rem;font-weight:800;line-height:1}
.gauge-label{font-size:.75rem;color:#64748b;margin-top:4px;text-transform:uppercase;letter-spacing:.05em}
/* Stats grid */
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:12px;margin-bottom:24px}
.stat{background:#1e2130;border:1px solid #2d3352;border-radius:10px;padding:14px 16px}
.stat .val{font-size:1.6rem;font-weight:700}
.stat .lbl{font-size:.75rem;color:#64748b;margin-top:2px}
/* Status colors */
.critical{color:#f87171}.warning{color:#fbbf24}.stable{color:#4ade80}.info{color:#94a3b8}
.bg-critical{background:#450a0a;border-color:#7f1d1d}
.bg-warning{background:#451a03;border-color:#78350f}
.bg-stable{background:#052e16;border-color:#14532d}
/* Tables */
.section{background:#1e2130;border:1px solid #2d3352;border-radius:12px;
  padding:20px;margin-bottom:20px}
.section h2{font-size:1rem;font-weight:600;margin-bottom:14px;color:#cbd5e1;
  padding-bottom:8px;border-bottom:1px solid #2d3352}
table{width:100%;border-collapse:collapse;font-size:.85rem}
th{text-align:left;padding:8px 12px;color:#64748b;font-weight:500;
  border-bottom:1px solid #2d3352;white-space:nowrap}
td{padding:8px 12px;border-bottom:1px solid #1a1f35;vertical-align:middle}
tr:last-child td{border-bottom:none}
tr:hover td{background:#252a3f}
.tag{display:inline-block;padding:1px 8px;border-radius:4px;font-size:.72rem;
  font-weight:600;letter-spacing:.03em}
.tag-critical{background:#7f1d1d;color:#fca5a5}
.tag-warning{background:#78350f;color:#fde68a}
.tag-stable{background:#14532d;color:#86efac}
.tag-info{background:#1e3a5f;color:#93c5fd}
.tag-lang{background:#1e293b;color:#94a3b8;font-weight:400}
/* Bars */
.bar{height:6px;border-radius:3px;display:inline-block;vertical-align:middle}
/* Lang chart */
.lang-row{display:flex;align-items:center;gap:10px;margin-bottom:6px}
.lang-name{width:80px;font-size:.8rem;color:#94a3b8}
.lang-bar{height:8px;border-radius:4px;background:#3b82f6}
.lang-count{font-size:.8rem;color:#64748b;min-width:30px}
/* Sparkline placeholder */
.spark{display:inline-block;width:80px;height:20px;vertical-align:middle}
/* Apex event box */
.apex-box{background:#0c1a2e;border:1px solid #1d4ed8;border-radius:8px;
  padding:12px 16px;margin-bottom:20px;font-size:.8rem;color:#93c5fd}
.apex-box strong{color:#60a5fa}
/* Footer */
.footer{text-align:center;padding:20px;font-size:.75rem;color:#475569}
/* Sortable */
th.sort{cursor:pointer;user-select:none}
th.sort:hover{color:#e2e8f0}
th.sort::after{content:' ⇅';opacity:.4}
/* Responsive */
@media(max-width:640px){
  .stats{grid-template-columns:repeat(2,1fr)}
  table{font-size:.78rem}
  td,th{padding:6px 8px}
}
"""

# ─── JS inline (sort de tabela) ───────────────────────────────────────────────

_JS = """
function sortTable(tbl, col, numeric) {
  const tbody = tbl.querySelector('tbody');
  const rows  = Array.from(tbody.querySelectorAll('tr'));
  const dir   = tbl.dataset.sortCol == col && tbl.dataset.sortDir == '1' ? -1 : 1;
  tbl.dataset.sortCol = col; tbl.dataset.sortDir = dir;
  rows.sort((a,b) => {
    const av = a.cells[col]?.dataset.val ?? a.cells[col]?.textContent ?? '';
    const bv = b.cells[col]?.dataset.val ?? b.cells[col]?.textContent ?? '';
    if (numeric) return dir * (parseFloat(av)||0 - (parseFloat(bv)||0));
    return dir * av.localeCompare(bv);
  });
  rows.forEach(r => tbody.appendChild(r));
}
document.querySelectorAll('th.sort').forEach(th => {
  th.addEventListener('click', () => {
    const tbl = th.closest('table');
    const col = th.cellIndex;
    sortTable(tbl, col, th.dataset.num === '1');
  });
});
"""


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _esc(s: str) -> str:
    return (str(s)
            .replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def _status_tag(status: str) -> str:
    cls = {"CRITICAL": "tag-critical", "WARNING": "tag-warning",
           "STABLE": "tag-stable", "INFO": "tag-info"}.get(status, "tag-info")
    return f'<span class="tag {cls}">{_esc(status)}</span>'


def _gauge_svg(score: float, size: int = 120) -> str:
    """SVG de semicírculo para o UCO Score."""
    fill, _ = badge_color(score)
    r   = 48
    cx  = size // 2
    cy  = size // 2 + 10
    arc = min(score / 100, 0.9999) * 180   # graus
    import math
    rad = math.radians(180 - arc)
    ex  = cx + r * math.cos(rad)
    ey  = cy - r * math.sin(rad)
    large = 1 if arc > 180 else 0

    return f"""<svg width="{size}" height="{size//2+20}" viewBox="0 0 {size} {size//2+20}">
  <path d="M{cx-r},{cy} A{r},{r} 0 0 1 {cx+r},{cy}" fill="none" stroke="#2d3352" stroke-width="8"/>
  <path d="M{cx-r},{cy} A{r},{r} 0 0 1 {ex:.2f},{ey:.2f}" fill="none"
        stroke="{fill}" stroke-width="8" stroke-linecap="round"/>
  <text x="{cx}" y="{cy-4}" text-anchor="middle" fill="{fill}"
        font-size="22" font-weight="800" font-family="system-ui">{int(score)}</text>
  <text x="{cx}" y="{cy+14}" text-anchor="middle" fill="#64748b"
        font-size="9" font-family="system-ui">/ 100</text>
</svg>"""


def _mini_bar(value: float, max_val: float, color: str = "#3b82f6", width: int = 60) -> str:
    pct = min(100, (value / max_val * 100)) if max_val > 0 else 0
    w   = int(pct / 100 * width)
    return (f'<span class="bar" style="width:{w}px;background:{color}"></span> '
            f'<span style="font-size:.8rem">{value:.2f}</span>')


def _sparkline_svg(values: list[float], width: int = 80, height: int = 20) -> str:
    """SVG sparkline simples para série temporal."""
    if not values or len(values) < 2:
        return ""
    mn, mx = min(values), max(values)
    rng    = mx - mn or 1
    n      = len(values)
    pts    = []
    for i, v in enumerate(values):
        x = int(i / (n - 1) * width)
        y = int((1 - (v - mn) / rng) * (height - 2)) + 1
        pts.append(f"{x},{y}")
    polyline = " ".join(pts)
    # Cor baseada na tendência
    color = "#f87171" if values[-1] > values[0] else "#4ade80"
    return (f'<svg class="spark" width="{width}" height="{height}" '
            f'viewBox="0 0 {width} {height}">'
            f'<polyline points="{polyline}" fill="none" stroke="{color}" '
            f'stroke-width="1.5" stroke-linejoin="round"/></svg>')


# ─── Generator principal ──────────────────────────────────────────────────────

def generate_html_report(
    result: Any,
    title:  str = "UCO-Sensor Report",
    repo:   str = "",
    commit: str = "",
) -> str:
    """
    Gera HTML report standalone a partir de ScanResult ou GitHistoryScanResult.

    Args:
        result: ScanResult (snapshot) ou GitHistoryScanResult (temporal)
        title:  Título do relatório
        repo:   Nome/URL do repositório
        commit: Hash do commit analisado

    Returns:
        String HTML completo e self-contained.
    """
    # Detectar tipo de result
    is_temporal = hasattr(result, "n_commits") and hasattr(result, "file_results") \
                  and hasattr(result, "critical_files")

    if is_temporal:
        return _render_temporal(result, title, repo, commit)
    else:
        return _render_snapshot(result, title, repo, commit)


# ─── Snapshot report ──────────────────────────────────────────────────────────

def _render_snapshot(result, title: str, repo: str, commit: str) -> str:
    score        = result.uco_score
    status       = result.project_status
    fill, _      = badge_color(score)
    now          = datetime.now().strftime("%Y-%m-%d %H:%M")
    top_n        = 50

    # ── Stats ──────────────────────────────────────────────────────────────
    stats_html = f"""
<div class="stats">
  <div class="stat {'bg-critical' if status=='CRITICAL' else 'bg-warning' if status=='WARNING' else 'bg-stable'}">
    <div class="val {'critical' if status=='CRITICAL' else 'warning' if status=='WARNING' else 'stable'}">{_esc(status)}</div>
    <div class="lbl">Status do Projeto</div>
  </div>
  <div class="stat"><div class="val" style="color:{fill}">{int(score)}/100</div><div class="lbl">UCO Score</div></div>
  <div class="stat"><div class="val">{result.files_scanned:,}</div><div class="lbl">Arquivos</div></div>
  <div class="stat"><div class="val">{result.total_loc:,}</div><div class="lbl">Linhas de Código</div></div>
  <div class="stat"><div class="val critical">{result.critical_count}</div><div class="lbl">CRITICAL</div></div>
  <div class="stat"><div class="val warning">{result.warning_count}</div><div class="lbl">WARNING</div></div>
  <div class="stat"><div class="val stable">{result.stable_count}</div><div class="lbl">STABLE</div></div>
  <div class="stat"><div class="val">{result.avg_hamiltonian:.2f}</div><div class="lbl">H̄ Médio</div></div>
</div>"""

    # ── Linguagens ─────────────────────────────────────────────────────────
    lang_rows = ""
    max_count = max(result.by_language.values(), default=1)
    for lang, count in sorted(result.by_language.items(), key=lambda x: -x[1]):
        w = int(count / max_count * 200)
        lang_rows += f"""<div class="lang-row">
  <span class="lang-name">{_esc(lang)}</span>
  <span class="lang-bar" style="width:{w}px"></span>
  <span class="lang-count">{count}</span>
</div>"""

    # ── Tabela de arquivos ─────────────────────────────────────────────────
    rows = ""
    max_h = max((fr.metrics.get("hamiltonian", 0) for fr in result.file_results if fr.ok), default=1)
    for fr in result.file_results[:top_n]:
        if not fr.ok:
            continue
        m   = fr.metrics
        h   = m.get("hamiltonian", 0)
        cc  = m.get("cyclomatic_complexity", 1)
        ilr = m.get("infinite_loop_risk", 0)
        dead= m.get("syntactic_dead_code", 0)
        dups= m.get("duplicate_block_count", 0)
        bar_color = "#f87171" if fr.status == "CRITICAL" else "#fbbf24" if fr.status == "WARNING" else "#4ade80"
        rows += f"""<tr>
  <td style="max-width:320px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap"
      title="{_esc(fr.path)}">{_esc(fr.path)}</td>
  <td>{_status_tag(fr.status)}</td>
  <td><span class="tag tag-lang">{_esc(fr.language)}</span></td>
  <td data-val="{h:.4f}">{_mini_bar(h, max_h, bar_color, 50)}</td>
  <td data-val="{cc}">{cc}</td>
  <td data-val="{ilr:.4f}">{"🔴" if ilr > 0.5 else "🟡" if ilr > 0 else "🟢"} {ilr:.2f}</td>
  <td data-val="{dead}">{dead}</td>
  <td data-val="{dups}">{dups}</td>
</tr>"""

    files_table = f"""
<section class="section">
  <h2>Arquivos analisados ({min(len(result.file_results), top_n)} de {result.files_scanned})</h2>
  <table>
    <thead><tr>
      <th class="sort">Arquivo</th>
      <th class="sort">Status</th>
      <th class="sort">Linguagem</th>
      <th class="sort" data-num="1">H (Hamiltoniano)</th>
      <th class="sort" data-num="1">CC</th>
      <th class="sort" data-num="1">ILR</th>
      <th class="sort" data-num="1">Dead</th>
      <th class="sort" data-num="1">Dups</th>
    </tr></thead>
    <tbody>{rows}</tbody>
  </table>
</section>"""

    return _wrap_html(
        title=title, repo=repo, commit=commit, now=now,
        mode="Snapshot", status=status, score=score,
        gauge_svg=_gauge_svg(score),
        stats_html=stats_html,
        lang_html=f'<section class="section"><h2>Linguagens</h2>{lang_rows}</section>',
        main_table=files_table,
        extra_html="",
    )


# ─── Temporal report ──────────────────────────────────────────────────────────

def _render_temporal(result, title: str, repo: str, commit: str) -> str:
    score   = max(0.0, 100 - len(result.critical_files)*10 - len(result.warning_files)*3)
    status  = result.project_status
    fill, _ = badge_color(score)
    now     = datetime.now().strftime("%Y-%m-%d %H:%M")

    stats_html = f"""
<div class="stats">
  <div class="stat {'bg-critical' if status=='CRITICAL' else 'bg-warning' if status=='WARNING' else 'bg-stable'}">
    <div class="val {'critical' if status=='CRITICAL' else 'warning' if status=='WARNING' else 'stable'}">{_esc(status)}</div>
    <div class="lbl">Status Temporal</div>
  </div>
  <div class="stat"><div class="val" style="color:{fill}">{int(score)}/100</div><div class="lbl">UCO Score</div></div>
  <div class="stat"><div class="val">{result.n_commits}</div><div class="lbl">Commits analisados</div></div>
  <div class="stat"><div class="val">{result.n_files}</div><div class="lbl">Arquivos com histórico</div></div>
  <div class="stat"><div class="val critical">{len(result.critical_files)}</div><div class="lbl">CRITICAL</div></div>
  <div class="stat"><div class="val warning">{len(result.warning_files)}</div><div class="lbl">WARNING</div></div>
  <div class="stat"><div class="val">{result.elapsed_s:.1f}s</div><div class="lbl">Tempo de análise</div></div>
</div>"""

    # ── Tabela temporal ────────────────────────────────────────────────────
    rows = ""
    for fr in result.file_results:
        if not fr.ok and fr.error and "insufficient" in fr.error:
            continue
        conf        = getattr(fr.classification, "primary_confidence", 0) if fr.ok else 0
        onset_str   = fr.onset_commit[:8] if fr.onset_commit else "—"
        cure_pct    = f"{fr.self_cure_probability*100:.0f}%" if fr.ok else "—"
        hurst_str   = f"{fr.hurst:.3f}" if fr.ok else "—"
        # Sparkline de H ao longo do tempo
        h_series    = [mv.hamiltonian for mv in fr.history]
        spark       = _sparkline_svg(h_series)
        pattern     = _esc(fr.primary_error) if fr.ok else _esc(fr.error or "?")

        hurst_color = "#f87171" if fr.hurst > 0.8 else "#fbbf24" if fr.hurst > 0.6 else "#4ade80"

        rows += f"""<tr>
  <td style="max-width:280px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap"
      title="{_esc(fr.path)}">{_esc(fr.path)}</td>
  <td>{_status_tag(fr.severity)}</td>
  <td><code style="font-size:.78rem;color:#94a3b8">{pattern}</code></td>
  <td data-val="{fr.hurst:.4f}"><span style="color:{hurst_color}">{hurst_str}</span></td>
  <td data-val="{fr.self_cure_probability:.4f}">{cure_pct}</td>
  <td data-val="{conf:.4f}">{f"{conf:.2f}" if fr.ok else "—"}</td>
  <td data-val="{fr.n_commits}">{fr.n_commits}</td>
  <td><code style="font-size:.78rem;color:#7dd3fc">{onset_str}</code></td>
  <td>{spark}</td>
</tr>"""

    main_table = f"""
<section class="section">
  <h2>Análise temporal por arquivo ({result.n_files} arquivos)</h2>
  <table>
    <thead><tr>
      <th class="sort">Arquivo</th>
      <th class="sort">Severity</th>
      <th class="sort">Padrão Detectado</th>
      <th class="sort" data-num="1">Hurst</th>
      <th class="sort" data-num="1">Auto-cura</th>
      <th class="sort" data-num="1">Confiança</th>
      <th class="sort" data-num="1">Commits</th>
      <th class="sort">Onset</th>
      <th>H ao longo do tempo</th>
    </tr></thead>
    <tbody>{rows}</tbody>
  </table>
</section>"""

    # Explicação dos padrões
    patterns_html = """
<section class="section">
  <h2>Legenda — Padrões UCO</h2>
  <table>
    <thead><tr><th>Padrão</th><th>Descrição</th><th>Hurst típico</th><th>Reversível?</th></tr></thead>
    <tbody>
      <tr><td><code>AI_CODE_BOMB</code></td><td>Spike simultâneo em dead+dups+ILR (código AI-generated)</td><td>&gt;0.8</td><td class="warning">Difícil</td></tr>
      <tr><td><code>TECH_DEBT_ACCUMULATION</code></td><td>H crescendo em ULF/LF — dívida técnica crônica</td><td>0.7–0.95</td><td class="critical">Irreversível sem refactoring</td></tr>
      <tr><td><code>GOD_CLASS_FORMATION</code></td><td>DI dominante — classe acumulando responsabilidades</td><td>0.6–0.85</td><td class="warning">Moderado</td></tr>
      <tr><td><code>COGNITIVE_COMPLEXITY_EXPLOSION</code></td><td>CC burst agudo — função monstro introduzida</td><td>0.3–0.6</td><td class="stable">Reversível com split</td></tr>
      <tr><td><code>DEPENDENCY_CYCLE_INTRODUCTION</code></td><td>DSM_c &gt; 0.5 — ciclo de dependências criado</td><td>0.5–0.8</td><td class="warning">Requer arquitetura</td></tr>
      <tr><td><code>LOOP_RISK_INTRODUCTION</code></td><td>ILR isolado — while True sem guard</td><td>0.4–0.7</td><td class="stable">Fix pontual</td></tr>
      <tr><td><code>DEAD_CODE_DRIFT</code></td><td>dead acumulando — código morto persistente</td><td>&gt;0.9</td><td class="critical">Alta persistência</td></tr>
      <tr><td><code>REFACTORING_OPPORTUNITY</code></td><td>Correlação DSM_d+CC — candidato a extração</td><td>0.4–0.6</td><td class="stable">Alta chance de melhora</td></tr>
    </tbody>
  </table>
</section>"""

    return _wrap_html(
        title=title, repo=repo, commit=commit, now=now,
        mode=f"Temporal ({result.n_commits} commits)",
        status=status, score=score,
        gauge_svg=_gauge_svg(score),
        stats_html=stats_html,
        lang_html="",
        main_table=main_table,
        extra_html=patterns_html,
    )


# ─── Wrapper HTML final ───────────────────────────────────────────────────────

def _wrap_html(
    title: str, repo: str, commit: str, now: str,
    mode: str, status: str, score: float,
    gauge_svg: str, stats_html: str,
    lang_html: str, main_table: str, extra_html: str,
) -> str:
    fill, _ = badge_color(score)
    repo_html = f'<a href="{_esc(repo)}" target="_blank">{_esc(repo)}</a>' if repo.startswith("http") else _esc(repo)
    commit_html = f'<code>{_esc(commit[:12])}</code>' if commit else ""

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1"/>
  <title>{_esc(title)}</title>
  <style>{_CSS}</style>
</head>
<body>
<div class="container">

  <!-- Header -->
  <div class="header">
    <div>
      <h1>🔬 {_esc(title)}</h1>
      <div class="meta">
        {"Repositório: " + repo_html + " &nbsp;|&nbsp;" if repo else ""}
        {"Commit: " + commit_html + " &nbsp;|&nbsp;" if commit else ""}
        Modo: {_esc(mode)} &nbsp;|&nbsp; Gerado: {now}
      </div>
    </div>
    <div class="gauge-card">
      {gauge_svg}
      <div class="gauge-label">UCO Score</div>
    </div>
  </div>

  <!-- Stats -->
  {stats_html}

  <!-- Linguagens (se disponível) -->
  {lang_html}

  <!-- Tabela principal -->
  {main_table}

  <!-- Extra (padrões, etc.) -->
  {extra_html}

  <!-- Footer APEX -->
  <div class="apex-box">
    <strong>APEX Integration:</strong> Arquivos com severity CRITICAL publicam
    <code>UCO_ANOMALY_DETECTED</code> no APEX EventBus.
    Hurst &gt; 0.8 indica padrão <strong>irreversível sem intervenção ativa</strong>.
    Self-cure &lt; 5% = refactoring obrigatório.
  </div>

  <div class="footer">
    Powered by <strong>UCO-Sensor v0.3.0</strong> — Spectral Code Quality Analysis |
    <a href="https://github.com/thiagofernandes1987-create/APEX/tree/main/algorithms/uco-sensor">GitHub</a>
  </div>

</div>
<script>{_JS}</script>
</body>
</html>"""
