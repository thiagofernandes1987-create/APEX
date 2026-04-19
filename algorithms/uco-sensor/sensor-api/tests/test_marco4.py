"""
UCO-Sensor — Testes Marco 4: Report & Visualization
=====================================================
Valida a camada de geração de relatórios HTML e badges SVG.

Testes:
  T40  badge_color — paleta correta por faixa de score
  T41  generate_badge_svg — SVG válido com score no texto
  T42  generate_status_badge_svg — SVG para STABLE/WARNING/CRITICAL
  T43  Badge contém valor score correto e clampado [0,100]
  T44  generate_html_report(ScanResult) retorna HTML com <!DOCTYPE
  T45  HTML report contém UCO Score no conteúdo
  T46  HTML report contém project status (CRITICAL/WARNING/STABLE)
  T47  HTML report contém colunas da tabela de arquivos
  T48  GET /report?module=<id> retorna Content-Type text/html
  T49  GET /badge?score=87 retorna SVG com 200
"""
from __future__ import annotations
import sys
import time
import json
import threading
import urllib.request
import urllib.error
from pathlib import Path
from http.server import HTTPServer
from typing import List, Dict, Any

# ── Path setup ────────────────────────────────────────────────────────────────
_SENSOR = Path(__file__).resolve().parent.parent
_ENGINE = _SENSOR.parent / "frequency-engine"
for _p in (str(_ENGINE), str(_SENSOR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from report.badge import badge_color, generate_badge_svg, generate_status_badge_svg
from report.html_report import generate_html_report
from scan.repo_scanner import ScanResult, FileScanResult
from api.server import UCOSensorHandler, handle_report, handle_badge, _store


# ─── Fixtures ─────────────────────────────────────────────────────────────────

def _make_scan_result(
    n_critical: int = 1,
    n_warning:  int = 2,
    n_stable:   int = 7,
    uco_score:  float = 72.5,
) -> ScanResult:
    """Cria ScanResult mínimo para testes de report."""
    file_results: List[FileScanResult] = []

    for i in range(n_critical):
        file_results.append(FileScanResult(
            path=f"src/critical_{i}.py",
            language="python",
            status="CRITICAL",
            loc=120,
            metrics={
                "hamiltonian": 22.0 + i,
                "cyclomatic_complexity": 18,
                "infinite_loop_risk": 0.7,
                "dsm_density": 0.8,
                "dsm_cyclic_ratio": 0.3,
                "dependency_instability": 0.9,
                "syntactic_dead_code": 5,
                "duplicate_block_count": 3,
                "halstead_bugs": 0.85,
            },
        ))

    for i in range(n_warning):
        file_results.append(FileScanResult(
            path=f"src/warning_{i}.py",
            language="python",
            status="WARNING",
            loc=80,
            metrics={
                "hamiltonian": 12.0 + i,
                "cyclomatic_complexity": 10,
                "infinite_loop_risk": 0.2,
                "dsm_density": 0.4,
                "dsm_cyclic_ratio": 0.1,
                "dependency_instability": 0.5,
                "syntactic_dead_code": 1,
                "duplicate_block_count": 1,
                "halstead_bugs": 0.25,
            },
        ))

    for i in range(n_stable):
        file_results.append(FileScanResult(
            path=f"src/stable_{i}.py",
            language="python",
            status="STABLE",
            loc=30,
            metrics={
                "hamiltonian": 3.0 + i * 0.5,
                "cyclomatic_complexity": 3,
                "infinite_loop_risk": 0.0,
                "dsm_density": 0.1,
                "dsm_cyclic_ratio": 0.0,
                "dependency_instability": 0.2,
                "syntactic_dead_code": 0,
                "duplicate_block_count": 0,
                "halstead_bugs": 0.05,
            },
        ))

    return ScanResult(
        root="/tmp/test_project",
        commit_hash="abc1234567",
        timestamp=time.time(),
        scan_duration_s=0.42,
        files_found=n_critical + n_warning + n_stable,
        files_scanned=n_critical + n_warning + n_stable,
        files_skipped=0,
        files_error=0,
        critical_count=n_critical,
        warning_count=n_warning,
        stable_count=n_stable,
        avg_hamiltonian=8.3,
        avg_cyclomatic_complexity=6.2,
        avg_infinite_loop_risk=0.05,
        avg_dsm_density=0.22,
        avg_dependency_instability=0.35,
        avg_halstead_bugs=0.18,
        total_loc=sum(f.loc for f in file_results),
        total_dead=6,
        total_dups=5,
        uco_score=uco_score,
        top_critical=[f for f in file_results if f.status == "CRITICAL"],
        top_warning=[f for f in file_results if f.status == "WARNING"][:3],
        by_language={"python": n_critical + n_warning + n_stable},
        file_results=file_results,
    )


# ─── T40: badge_color ─────────────────────────────────────────────────────────

def test_T40a_badge_color_verde():
    """Score ≥ 80 → verde (#4c1)."""
    fill, text = badge_color(85)
    assert fill == "#4c1",    f"Esperado #4c1, got {fill}"
    assert text == "#fff",    f"Esperado #fff, got {text}"
    print(f"  [T40a] ok — score=85 → fill={fill}")


def test_T40b_badge_color_verde_amarelo():
    """Score 65–79 → verde-amarelo (#97ca00)."""
    fill, text = badge_color(70)
    assert fill == "#97ca00", f"Esperado #97ca00, got {fill}"
    print(f"  [T40b] ok — score=70 → fill={fill}")


def test_T40c_badge_color_amarelo():
    """Score 50–64 → amarelo (#dfb317)."""
    fill, text = badge_color(55)
    assert fill == "#dfb317", f"Esperado #dfb317, got {fill}"
    print(f"  [T40c] ok — score=55 → fill={fill}")


def test_T40d_badge_color_laranja():
    """Score 35–49 → laranja (#fe7d37)."""
    fill, text = badge_color(40)
    assert fill == "#fe7d37", f"Esperado #fe7d37, got {fill}"
    print(f"  [T40d] ok — score=40 → fill={fill}")


def test_T40e_badge_color_vermelho():
    """Score < 35 → vermelho (#e05d44)."""
    fill, text = badge_color(20)
    assert fill == "#e05d44", f"Esperado #e05d44, got {fill}"
    print(f"  [T40e] ok — score=20 → fill={fill}")


# ─── T41: generate_badge_svg ──────────────────────────────────────────────────

def test_T41a_badge_svg_is_string():
    """generate_badge_svg retorna string."""
    svg = generate_badge_svg(score=87, status="STABLE", label="UCO Score")
    assert isinstance(svg, str), f"Esperado str, got {type(svg)}"
    print(f"  [T41a] ok — SVG é string com {len(svg)} chars")


def test_T41b_badge_svg_starts_with_svg_tag():
    """SVG começa com <svg ..."""
    svg = generate_badge_svg(score=87)
    assert svg.strip().startswith("<svg"), f"SVG não começa com <svg: {svg[:50]}"
    print(f"  [T41b] ok — SVG começa com <svg")


def test_T41c_badge_svg_closes_properly():
    """SVG fecha com </svg>."""
    svg = generate_badge_svg(score=65, status="WARNING")
    assert svg.strip().endswith("</svg>"), f"SVG não fecha com </svg>"
    print(f"  [T41c] ok — SVG fecha com </svg>")


def test_T41d_badge_svg_contains_xmlns():
    """SVG tem namespace xmlns para compatibilidade."""
    svg = generate_badge_svg(score=50)
    assert 'xmlns="http://www.w3.org/2000/svg"' in svg, "xmlns ausente no SVG"
    print(f"  [T41d] ok — xmlns presente")


# ─── T42: generate_status_badge_svg ──────────────────────────────────────────

def test_T42a_status_badge_stable():
    """Badge STABLE retorna SVG válido."""
    svg = generate_status_badge_svg("STABLE")
    assert svg.strip().startswith("<svg"), "STABLE badge não é SVG"
    assert "STABLE" in svg, "STABLE badge não contém texto STABLE"
    print(f"  [T42a] ok — STABLE badge gerado ({len(svg)} chars)")


def test_T42b_status_badge_warning():
    """Badge WARNING retorna SVG com cor correta."""
    svg = generate_status_badge_svg("WARNING")
    assert "WARNING" in svg, "WARNING badge não contém texto WARNING"
    assert "#dfb317" in svg, "WARNING deve ter cor amarela #dfb317"
    print(f"  [T42b] ok — WARNING badge com cor correta")


def test_T42c_status_badge_critical():
    """Badge CRITICAL retorna SVG com cor vermelha."""
    svg = generate_status_badge_svg("CRITICAL")
    assert "CRITICAL" in svg, "CRITICAL badge não contém texto CRITICAL"
    assert "#e05d44" in svg, "CRITICAL deve ter cor vermelha #e05d44"
    print(f"  [T42c] ok — CRITICAL badge com cor correta")


# ─── T43: Score correto e clampado ───────────────────────────────────────────

def test_T43a_badge_score_correct_value():
    """Badge contém o valor de score correto no SVG."""
    svg = generate_badge_svg(score=87, label="UCO Score")
    # O texto "87/100" deve aparecer no SVG
    assert "87/100" in svg, f"Score 87/100 não encontrado no SVG:\n{svg[:300]}"
    print(f"  [T43a] ok — '87/100' presente no SVG")


def test_T43b_badge_score_clamped_max():
    """Score acima de 100 é clampado para 100."""
    svg = generate_badge_svg(score=150)
    assert "100/100" in svg, f"Score deveria ser clampado a 100: {svg[:200]}"
    print(f"  [T43b] ok — score 150 clampado para 100/100")


def test_T43c_badge_score_clamped_min():
    """Score abaixo de 0 é clampado para 0."""
    svg = generate_badge_svg(score=-50)
    assert "0/100" in svg, f"Score deveria ser clampado a 0: {svg[:200]}"
    print(f"  [T43c] ok — score -50 clampado para 0/100")


def test_T43d_badge_score_rounded():
    """Score float é arredondado para int."""
    svg = generate_badge_svg(score=72.7)
    assert "73/100" in svg, f"Score 72.7 deveria arredondar para 73: {svg[:200]}"
    print(f"  [T43d] ok — 72.7 arredondado para 73/100")


# ─── T44: generate_html_report — estrutura básica ────────────────────────────

def test_T44a_html_report_returns_string():
    """generate_html_report retorna string."""
    result = _make_scan_result()
    html = generate_html_report(result, title="Test Report")
    assert isinstance(html, str), f"Esperado str, got {type(html)}"
    assert len(html) > 100, "HTML muito curto"
    print(f"  [T44a] ok — HTML gerado com {len(html)} chars")


def test_T44b_html_report_has_doctype():
    """HTML report começa com <!DOCTYPE html> ou <html."""
    result = _make_scan_result()
    html = generate_html_report(result)
    html_lower = html.lower().strip()
    assert html_lower.startswith("<!doctype") or html_lower.startswith("<html") or html_lower.startswith("<svg"), \
        f"HTML não começa com DOCTYPE/html: {html[:80]}"
    print(f"  [T44b] ok — HTML inicia com tag válida")


def test_T44c_html_report_closes_html():
    """HTML report termina com </html>."""
    result = _make_scan_result()
    html = generate_html_report(result)
    assert html.strip().endswith("</html>"), f"HTML não fecha com </html>"
    print(f"  [T44c] ok — HTML fecha com </html>")


# ─── T45: UCO Score no HTML ───────────────────────────────────────────────────

def test_T45a_html_contains_uco_score():
    """HTML report contém o valor do UCO Score."""
    result = _make_scan_result(uco_score=72.5)
    html = generate_html_report(result)
    # Score arredondado = 72 ou 73 deve aparecer no HTML
    score_int = int(round(72.5))
    assert str(score_int) in html, f"Score {score_int} não encontrado no HTML"
    print(f"  [T45a] ok — UCO Score {score_int} presente no HTML")


def test_T45b_html_contains_score_gauge():
    """HTML report contém gauge SVG do score."""
    result = _make_scan_result(uco_score=80.0)
    html = generate_html_report(result)
    # gauge é um SVG inline
    assert "<svg" in html, "Gauge SVG não encontrado no HTML"
    print(f"  [T45b] ok — gauge SVG presente no HTML")


# ─── T46: Project status no HTML ─────────────────────────────────────────────

def test_T46a_html_contains_critical_status():
    """HTML report com arquivos críticos contém 'CRITICAL'."""
    result = _make_scan_result(n_critical=3, n_warning=1, n_stable=6)
    html = generate_html_report(result)
    assert "CRITICAL" in html, "CRITICAL não encontrado no HTML"
    print(f"  [T46a] ok — status CRITICAL presente no HTML")


def test_T46b_html_contains_warning_status():
    """HTML report com arquivos em warning contém 'WARNING'."""
    result = _make_scan_result(n_critical=0, n_warning=5, n_stable=5)
    html = generate_html_report(result)
    assert "WARNING" in html, "WARNING não encontrado no HTML"
    print(f"  [T46b] ok — status WARNING presente no HTML")


def test_T46c_html_stable_project():
    """HTML report de projeto limpo contém 'STABLE'."""
    result = _make_scan_result(n_critical=0, n_warning=0, n_stable=10, uco_score=95.0)
    html = generate_html_report(result)
    assert "STABLE" in html, "STABLE não encontrado no HTML"
    print(f"  [T46c] ok — status STABLE presente no HTML")


# ─── T47: Tabela de arquivos no HTML ─────────────────────────────────────────

def test_T47a_html_has_file_table():
    """HTML report contém elemento <table>."""
    result = _make_scan_result()
    html = generate_html_report(result)
    assert "<table" in html, "Tabela não encontrada no HTML"
    print(f"  [T47a] ok — <table> presente no HTML")


def test_T47b_html_has_file_paths():
    """HTML report lista caminhos dos arquivos."""
    result = _make_scan_result(n_critical=1)
    html = generate_html_report(result)
    assert "critical_0.py" in html, "Caminho do arquivo não encontrado no HTML"
    print(f"  [T47b] ok — caminho de arquivo presente no HTML")


def test_T47c_html_has_hamiltonian_column():
    """HTML report menciona Hamiltoniano na tabela."""
    result = _make_scan_result()
    html = generate_html_report(result)
    assert "Hamiltoniano" in html or "H (" in html or "hamiltonian" in html.lower(), \
        "Coluna Hamiltoniano não encontrada"
    print(f"  [T47c] ok — coluna Hamiltoniano presente")


def test_T47d_html_has_language_breakdown():
    """HTML report contém breakdown por linguagem."""
    result = _make_scan_result()
    html = generate_html_report(result)
    assert "python" in html.lower(), "Linguagem 'python' não encontrada no HTML"
    print(f"  [T47d] ok — linguagem presente no breakdown")


# ─── T48: GET /report HTTP endpoint ──────────────────────────────────────────

PORT_M4 = 19084

_server_m4 = None


def setup_server():
    global _server_m4
    if _server_m4 is None:
        # Pré-popular o store com histórico de um módulo
        from core.data_structures import MetricVector
        for i in range(10):
            mv = MetricVector(
                module_id="report.test.module",
                commit_hash=f"r4test{i:03d}",
                timestamp=float(1700000000 + i * 3600),
                hamiltonian=5.0 + i * 0.5,
                cyclomatic_complexity=3 + i % 4,
                infinite_loop_risk=0.0 if i % 3 else 0.1,
                dsm_density=0.2,
                dsm_cyclic_ratio=0.0,
                dependency_instability=0.3,
                syntactic_dead_code=0,
                duplicate_block_count=0,
                halstead_bugs=0.1,
            )
            _store.insert(mv)

        server = HTTPServer(("127.0.0.1", PORT_M4), UCOSensorHandler)
        t = threading.Thread(target=server.serve_forever, daemon=True)
        t.start()
        time.sleep(0.15)
        _server_m4 = server
    return _server_m4


def _get_raw(port: int, path: str):
    """Faz GET e retorna (status_code, headers, body_bytes)."""
    url = f"http://127.0.0.1:{port}{path}"
    req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, dict(resp.headers), resp.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read()


def test_T48a_report_endpoint_returns_html():
    """GET /report?module=<id> retorna Content-Type text/html."""
    setup_server()
    status, headers, body = _get_raw(PORT_M4, "/report?module=report.test.module")
    ct = headers.get("Content-Type", "")
    assert status == 200, f"Esperado 200, got {status}"
    assert "text/html" in ct, f"Content-Type deve ser text/html, got '{ct}'"
    print(f"  [T48a] ok — /report retornou HTML ({len(body)} bytes)")


def test_T48b_report_endpoint_html_content():
    """GET /report retorna HTML com conteúdo válido (tem <html ou <!DOCTYPE)."""
    setup_server()
    _, _, body = _get_raw(PORT_M4, "/report?module=report.test.module")
    html = body.decode("utf-8").lower()
    assert "<html" in html or "<!doctype" in html, \
        f"Body não parece HTML válido: {html[:200]}"
    print(f"  [T48b] ok — body é HTML válido")


def test_T48c_report_endpoint_404_unknown_module():
    """GET /report?module=nao_existe retorna 404."""
    setup_server()
    status, _, _ = _get_raw(PORT_M4, "/report?module=modulo_inexistente_xyz")
    assert status == 404, f"Esperado 404 para módulo desconhecido, got {status}"
    print(f"  [T48c] ok — módulo inexistente retorna 404")


# ─── T49: GET /badge HTTP endpoint ───────────────────────────────────────────

def test_T49a_badge_endpoint_by_score():
    """GET /badge?score=87 retorna SVG com 200."""
    setup_server()
    status, headers, body = _get_raw(PORT_M4, "/badge?score=87&status=STABLE")
    ct = headers.get("Content-Type", "")
    assert status == 200, f"Esperado 200, got {status}"
    assert "svg" in ct or body.decode("utf-8").strip().startswith("<svg"), \
        f"Resposta não é SVG: ct={ct}, body[:80]={body[:80]}"
    print(f"  [T49a] ok — /badge?score=87 retornou SVG")


def test_T49b_badge_endpoint_contains_score():
    """GET /badge?score=73 contém '73/100' no body SVG."""
    setup_server()
    _, _, body = _get_raw(PORT_M4, "/badge?score=73")
    svg = body.decode("utf-8")
    assert "73/100" in svg, f"'73/100' não encontrado no SVG: {svg[:300]}"
    print(f"  [T49b] ok — '73/100' presente no SVG do badge")


def test_T49c_badge_endpoint_by_module():
    """GET /badge?module=<id> gera badge a partir do histórico do módulo."""
    setup_server()
    status, headers, body = _get_raw(PORT_M4, "/badge?module=report.test.module")
    assert status == 200, f"Esperado 200, got {status}"
    svg = body.decode("utf-8")
    assert "<svg" in svg, "Resposta não é SVG"
    assert "/100" in svg, "Score não encontrado no SVG do módulo"
    print(f"  [T49c] ok — badge de módulo gerado com score presente")


def test_T49d_handle_report_unit():
    """handle_report retorna (200, html) para módulo existente."""
    from core.data_structures import MetricVector

    # Inserir dados mínimos
    mv = MetricVector(
        module_id="unit.report.test",
        commit_hash="unit001",
        timestamp=float(1700000000),
        hamiltonian=4.0,
        cyclomatic_complexity=3,
        infinite_loop_risk=0.0,
        dsm_density=0.1,
        dsm_cyclic_ratio=0.0,
        dependency_instability=0.2,
        syntactic_dead_code=0,
        duplicate_block_count=0,
        halstead_bugs=0.05,
    )
    _store.insert(mv)

    code, html = handle_report("unit.report.test")
    assert code == 200, f"Esperado 200, got {code}"
    assert isinstance(html, str) and len(html) > 50, "HTML vazio ou inválido"
    assert "<html" in html.lower() or "<svg" in html.lower(), "Não parece HTML/SVG"
    print(f"  [T49d] ok — handle_report retornou {len(html)} chars de HTML")


# ─── Runner ──────────────────────────────────────────────────────────────────

TESTS = [
    ("T40a", test_T40a_badge_color_verde),
    ("T40b", test_T40b_badge_color_verde_amarelo),
    ("T40c", test_T40c_badge_color_amarelo),
    ("T40d", test_T40d_badge_color_laranja),
    ("T40e", test_T40e_badge_color_vermelho),
    ("T41a", test_T41a_badge_svg_is_string),
    ("T41b", test_T41b_badge_svg_starts_with_svg_tag),
    ("T41c", test_T41c_badge_svg_closes_properly),
    ("T41d", test_T41d_badge_svg_contains_xmlns),
    ("T42a", test_T42a_status_badge_stable),
    ("T42b", test_T42b_status_badge_warning),
    ("T42c", test_T42c_status_badge_critical),
    ("T43a", test_T43a_badge_score_correct_value),
    ("T43b", test_T43b_badge_score_clamped_max),
    ("T43c", test_T43c_badge_score_clamped_min),
    ("T43d", test_T43d_badge_score_rounded),
    ("T44a", test_T44a_html_report_returns_string),
    ("T44b", test_T44b_html_report_has_doctype),
    ("T44c", test_T44c_html_report_closes_html),
    ("T45a", test_T45a_html_contains_uco_score),
    ("T45b", test_T45b_html_contains_score_gauge),
    ("T46a", test_T46a_html_contains_critical_status),
    ("T46b", test_T46b_html_contains_warning_status),
    ("T46c", test_T46c_html_stable_project),
    ("T47a", test_T47a_html_has_file_table),
    ("T47b", test_T47b_html_has_file_paths),
    ("T47c", test_T47c_html_has_hamiltonian_column),
    ("T47d", test_T47d_html_has_language_breakdown),
    ("T48a", test_T48a_report_endpoint_returns_html),
    ("T48b", test_T48b_report_endpoint_html_content),
    ("T48c", test_T48c_report_endpoint_404_unknown_module),
    ("T49a", test_T49a_badge_endpoint_by_score),
    ("T49b", test_T49b_badge_endpoint_contains_score),
    ("T49c", test_T49c_badge_endpoint_by_module),
    ("T49d", test_T49d_handle_report_unit),
]


if __name__ == "__main__":
    import os as _os
    # Windows: forçar UTF-8 para emojis e caracteres especiais
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    passed = 0
    failed = 0
    errors = []

    print(f"\n{'='*65}")
    print(f"  UCO-Sensor Marco 4 — Report & Visualization  ({len(TESTS)} testes)")
    print(f"{'='*65}")

    for name, fn in TESTS:
        try:
            fn()
            print(f"  ✅ {name}")
            passed += 1
        except Exception as exc:
            print(f"  ❌ {name}: {exc}")
            failed += 1
            errors.append((name, exc))

    print(f"\n{'='*65}")
    print(f"  Resultado: {passed}/{len(TESTS)} passaram")
    if errors:
        print(f"\n  Falhas:")
        for n, e in errors:
            print(f"    {n}: {e}")
    print(f"{'='*65}\n")

    import sys as _sys
    _sys.exit(0 if failed == 0 else 1)
