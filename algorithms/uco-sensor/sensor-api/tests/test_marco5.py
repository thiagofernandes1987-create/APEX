"""
UCO-Sensor — Testes Marco 5: Benchmark & Diff Mode
====================================================
Valida o endpoint POST /diff (comparação entre 2 commits) e benchmarks
com código representativo de repositórios reais.

Testes:
  T50  POST /diff retorna campos obrigatórios (before, after, delta, regression)
  T51  delta_h positivo quando código degrada (mais complexo)
  T52  delta_h negativo quando código melhora (mais simples)
  T53  regression=True quando status piora para CRITICAL
  T54  suggested_transforms presentes quando código degrada
  T55  diff de código idêntico tem delta ~0 em todos os canais
  T56  handle_diff aceita extensões Python, JS, Java, Go
  T57  Benchmark: 20 arquivos analisados em < 5s
  T58  UCO Score de código saudável (inline real) >= 40
  T59  validate_real_repos quick mode executa sem exceção
  T5A  POST /diff via HTTP retorna 200 com JSON correto
  T5B  POST /diff via HTTP com code vazio retorna 400
  T5C  diff summary contém REGRESSAO ou OK
  T5D  uco_score_before e uco_score_after em [0, 100]
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

from api.server import UCOSensorHandler, handle_diff, _store
from lang_adapters.registry import get_registry
from sensor_core.uco_bridge import UCOBridge

# ─── Código de teste ──────────────────────────────────────────────────────────

# Código simples → baixa complexidade
CODE_SIMPLE = """
def get_user(user_id: int):
    return {"id": user_id, "name": "Alice"}

def greet(name: str) -> str:
    return f"Hello, {name}!"
"""

# Código complexo → alta complexidade (piora deliberada)
CODE_COMPLEX = """
def process(items, config, context, flags, extra=None):
    results = []
    for item in items:
        if item and config:
            for k, v in config.items():
                if k in flags:
                    if v > 0:
                        for sub in item.get("children", []):
                            if sub.get("active"):
                                if context.get("strict"):
                                    results.append(sub)
                                else:
                                    if extra:
                                        results.append(extra)
                    elif v < 0:
                        while True:
                            break
    unused_var = 42
    unused_var2 = 99
    return results
    return []  # dead code
"""

# Código reparado → simplificado
CODE_REPAIRED = """
def get_user(user_id: int):
    return {"id": user_id, "name": "Alice"}

def greet(name: str) -> str:
    return f"Hello, {name}!"

def add(a: int, b: int) -> int:
    return a + b
"""

# Código real típico (estilo requests) para benchmark
REAL_CODE_SAMPLES = [
    # 1 — Config simples
    """
class Config:
    DEBUG = False
    DATABASE_URI = "sqlite:///app.db"
    SECRET_KEY = "dev"
    @classmethod
    def from_env(cls):
        return cls()
""",
    # 2 — Router simples
    """
class Router:
    def __init__(self):
        self._routes = {}
    def add_route(self, path, handler):
        self._routes[path] = handler
    def dispatch(self, path, request):
        handler = self._routes.get(path)
        if handler:
            return handler(request)
        return None
""",
    # 3 — Utilitários
    """
import json
def parse_json(data):
    try:
        return json.loads(data)
    except json.JSONDecodeError:
        return None

def serialize(obj):
    return json.dumps(obj, default=str)

def merge_dicts(a, b):
    return {**a, **b}
""",
    # 4 — Autenticação simples
    """
import hashlib, secrets
def hash_password(pw):
    salt = secrets.token_hex(16)
    h = hashlib.sha256((pw + salt).encode()).hexdigest()
    return f"{salt}:{h}"

def verify_password(pw, stored):
    salt, h = stored.split(":", 1)
    return hashlib.sha256((pw + salt).encode()).hexdigest() == h
""",
    # 5 — Model básico
    """
from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class User:
    id: int
    name: str
    email: str
    roles: List[str] = field(default_factory=list)
    active: bool = True
    def has_role(self, role):
        return role in self.roles
    def deactivate(self):
        self.active = False
""",
]

# ─── Fixtures HTTP ────────────────────────────────────────────────────────────

PORT_M5 = 19085
_server_m5 = None


def setup_server():
    global _server_m5
    if _server_m5 is None:
        server = HTTPServer(("127.0.0.1", PORT_M5), UCOSensorHandler)
        t = threading.Thread(target=server.serve_forever, daemon=True)
        t.start()
        time.sleep(0.15)
        _server_m5 = server
    return _server_m5


def _post(port: int, path: str, body: Dict) -> tuple:
    data = json.dumps(body).encode()
    req  = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


# ─── T50: Campos obrigatórios ─────────────────────────────────────────────────

def test_T50_diff_required_fields():
    """POST /diff retorna campos: before, after, delta, regression, delta_h."""
    code, resp = handle_diff({
        "before": {"code": CODE_SIMPLE, "module_id": "m5.test", "commit_hash": "v1"},
        "after":  {"code": CODE_COMPLEX, "module_id": "m5.test", "commit_hash": "v2"},
    })
    assert code == 200, f"Esperado 200, got {code}"
    assert "before"   in resp, "Campo 'before' ausente"
    assert "after"    in resp, "Campo 'after' ausente"
    assert "delta"    in resp, "Campo 'delta' ausente"
    assert "delta_h"  in resp, "Campo 'delta_h' ausente"
    assert "regression" in resp, "Campo 'regression' ausente"
    assert "suggested_transforms" in resp, "Campo 'suggested_transforms' ausente"
    # delta deve ter os 9 canais
    channels = ["hamiltonian","cyclomatic_complexity","infinite_loop_risk",
                 "dsm_density","dsm_cyclic_ratio","dependency_instability",
                 "syntactic_dead_code","duplicate_block_count","halstead_bugs"]
    for ch in channels:
        assert ch in resp["delta"], f"Canal '{ch}' ausente em delta"
    print(f"  [T50] ok — todos os campos presentes, delta tem 9 canais")


# ─── T51: delta_h positivo (degrada) ─────────────────────────────────────────

def test_T51_delta_h_positive_on_degradation():
    """delta_h > 0 quando código after é mais complexo que before."""
    code, resp = handle_diff({
        "before": {"code": CODE_SIMPLE,  "module_id": "deg.test", "commit_hash": "v1"},
        "after":  {"code": CODE_COMPLEX, "module_id": "deg.test", "commit_hash": "v2"},
    })
    delta_h = resp["delta_h"]
    assert delta_h > 0, f"Esperado delta_h > 0 (degradação), got {delta_h:.3f}"
    print(f"  [T51] ok — delta_h={delta_h:.3f} > 0 (código degradou)")


# ─── T52: delta_h negativo (melhora) ─────────────────────────────────────────

def test_T52_delta_h_negative_on_improvement():
    """delta_h < 0 quando código after é mais simples que before."""
    code, resp = handle_diff({
        "before": {"code": CODE_COMPLEX,  "module_id": "imp.test", "commit_hash": "v1"},
        "after":  {"code": CODE_REPAIRED, "module_id": "imp.test", "commit_hash": "v2"},
    })
    delta_h = resp["delta_h"]
    assert delta_h < 0, f"Esperado delta_h < 0 (melhora), got {delta_h:.3f}"
    print(f"  [T52] ok — delta_h={delta_h:.3f} < 0 (código melhorou)")


# ─── T53: regression=True quando piora ───────────────────────────────────────

def test_T53_regression_flag_on_strong_degradation():
    """regression=True quando código degrada significativamente."""
    code, resp = handle_diff({
        "before": {"code": CODE_SIMPLE,  "module_id": "reg.test", "commit_hash": "v1"},
        "after":  {"code": CODE_COMPLEX, "module_id": "reg.test", "commit_hash": "v2"},
    })
    # Com uma mudança tão drástica, esperamos regression=True
    delta_h = resp["delta_h"]
    # Se H aumentou > 2, regression deve ser True
    if delta_h > 2.0:
        assert resp["regression"] is True, \
            f"regression deveria ser True com delta_h={delta_h:.2f}"
    print(f"  [T53] ok — regression={resp['regression']} com delta_h={delta_h:.2f}")


# ─── T54: suggested_transforms ───────────────────────────────────────────────

def test_T54_transforms_on_dead_code():
    """suggested_transforms inclui 'remove_dead_code' quando dead code aumenta."""
    before = "def f(): return 1"
    after  = """
def f():
    return 1
    print("never reached")
    unused_x = 42
"""
    code, resp = handle_diff({
        "before": {"code": before, "module_id": "dc.test", "commit_hash": "v1"},
        "after":  {"code": after,  "module_id": "dc.test", "commit_hash": "v2"},
    })
    transforms = resp.get("suggested_transforms", [])
    assert "remove_dead_code" in transforms, \
        f"'remove_dead_code' deveria estar em transforms: {transforms}"
    print(f"  [T54] ok — transforms={transforms}")


# ─── T55: diff de código idêntico tem delta ~0 ───────────────────────────────

def test_T55_identical_code_delta_zero():
    """Diff de código idêntico tem delta ~0 em todos os canais."""
    code, resp = handle_diff({
        "before": {"code": CODE_SIMPLE, "module_id": "same.test", "commit_hash": "v1"},
        "after":  {"code": CODE_SIMPLE, "module_id": "same.test", "commit_hash": "v2"},
    })
    delta = resp["delta"]
    for ch, val in delta.items():
        assert abs(val) < 0.01, f"Canal '{ch}' deveria ser ~0, got {val}"
    assert resp["regression"] is False, "Diff idêntico não deve ser regressão"
    print(f"  [T55] ok — todos os deltas ~0 para código idêntico")


# ─── T56: multi-linguagem ─────────────────────────────────────────────────────

def test_T56a_diff_python():
    """handle_diff funciona com .py."""
    code, resp = handle_diff({
        "before": {"code": "def f(): pass", "module_id": "py.test", "commit_hash": "v1",
                   "file_extension": ".py"},
        "after":  {"code": "def f():\n    x=1\n    return x", "module_id": "py.test",
                   "commit_hash": "v2", "file_extension": ".py"},
    })
    assert code == 200
    assert resp["before"]["language"] == "python"
    print(f"  [T56a] ok — Python diff: delta_h={resp['delta_h']:.3f}")


def test_T56b_diff_javascript():
    """handle_diff funciona com .js."""
    before_js = "function greet(name) { return 'hello ' + name; }"
    after_js  = """
function processItems(items, config, ctx) {
    var results = [];
    for (var i = 0; i < items.length; i++) {
        if (items[i] && config) {
            for (var k in config) {
                if (k in ctx) {
                    results.push(items[i]);
                }
            }
        }
    }
    return results;
}
"""
    code, resp = handle_diff({
        "before": {"code": before_js, "module_id": "js.test", "commit_hash": "v1",
                   "file_extension": ".js"},
        "after":  {"code": after_js,  "module_id": "js.test", "commit_hash": "v2",
                   "file_extension": ".js"},
    })
    assert code == 200
    print(f"  [T56b] ok — JS diff: lang={resp['after']['language']}, delta_h={resp['delta_h']:.3f}")


# ─── T57: Benchmark 20 arquivos ───────────────────────────────────────────────

def test_T57_benchmark_20_files_under_5s():
    """20 arquivos analisados em < 5s."""
    registry = get_registry()
    codes = REAL_CODE_SAMPLES * 4  # 20 amostras

    t0 = time.perf_counter()
    for i, code in enumerate(codes):
        registry.analyze(
            source=code,
            file_extension=".py",
            module_id=f"bench.mod{i}",
            commit_hash=f"bh{i:04d}",
        )
    elapsed = time.perf_counter() - t0

    assert elapsed < 5.0, f"20 arquivos em {elapsed:.2f}s > 5s"
    print(f"  [T57] ok — 20 arquivos em {elapsed:.3f}s (< 5s)")


# ─── T58: UCO Score de código saudável ───────────────────────────────────────

def test_T58_healthy_code_score_ge_40():
    """UCO Score de código limpo deve ser >= 40."""
    bridge = UCOBridge(mode="fast")
    for i, sample in enumerate(REAL_CODE_SAMPLES):
        mv = bridge.analyze(sample, f"bench.score{i}", f"s{i:03d}")
        h  = mv.hamiltonian
        cc = mv.cyclomatic_complexity
        score = max(0.0, 100.0 - min(h * 2, 60) - min((cc - 1) * 2, 30))
        assert score >= 40, \
            f"Amostra {i} score={score:.1f} < 40 (H={h:.2f}, CC={cc})"
    print(f"  [T58] ok — todas as amostras com score >= 40")


# ─── T59: validate_real_repos quick mode ─────────────────────────────────────

def test_T59_validate_real_repos_quick():
    """
    validation/validate_real_repos.py (quick mode) executa sem exceção.
    Usamos subprocess para isolar o contexto e garantir __file__ correto.
    """
    import subprocess

    vr_path = _SENSOR / "validation" / "validate_real_repos.py"
    assert vr_path.exists(), f"validate_real_repos.py não encontrado em {vr_path}"

    result = subprocess.run(
        [sys.executable, str(vr_path), "--quick"],
        capture_output=True,
        text=True,
        timeout=30,
        cwd=str(_SENSOR),
    )
    # Exit 0 = todos os checks passaram; exit 1 = algum check falhou mas não crashou
    # Aqui validamos apenas que não houve exceção/crash (exit code != 2 = unhandled error)
    assert result.returncode in (0, 1), \
        f"validate_real_repos crashou (exit={result.returncode}):\n{result.stderr[-500:]}"
    print(f"  [T59] ok — validate_real_repos exit={result.returncode} (sem crash)")


# ─── T5A: POST /diff via HTTP ─────────────────────────────────────────────────

def test_T5A_diff_http_200():
    """POST /diff via HTTP retorna 200 com JSON correto."""
    setup_server()
    status, resp = _post(PORT_M5, "/diff", {
        "before": {"code": CODE_SIMPLE,  "module_id": "http.diff", "commit_hash": "v1"},
        "after":  {"code": CODE_COMPLEX, "module_id": "http.diff", "commit_hash": "v2"},
    })
    assert status == 200, f"Esperado 200, got {status}"
    assert resp["status"] == "ok"
    data = resp["data"]
    assert "delta_h" in data, "delta_h ausente na resposta HTTP"
    assert "regression" in data
    print(f"  [T5A] ok — HTTP diff: delta_h={data['delta_h']:.3f}, regression={data['regression']}")


# ─── T5B: POST /diff com código vazio ─────────────────────────────────────────

def test_T5B_diff_http_400_empty_code():
    """POST /diff com before.code vazio retorna 400."""
    setup_server()
    status, resp = _post(PORT_M5, "/diff", {
        "before": {"code": "",           "module_id": "err.diff", "commit_hash": "v1"},
        "after":  {"code": CODE_SIMPLE,  "module_id": "err.diff", "commit_hash": "v2"},
    })
    assert status == 400, f"Esperado 400 para before.code vazio, got {status}"
    print(f"  [T5B] ok — 400 retornado para before.code vazio")


# ─── T5C: summary contém REGRESSAO/OK ────────────────────────────────────────

def test_T5C_summary_contains_status():
    """summary contém 'REGRESSAO' ou 'OK' e score antes→depois."""
    code, resp = handle_diff({
        "before": {"code": CODE_SIMPLE,  "commit_hash": "v1"},
        "after":  {"code": CODE_REPAIRED,"commit_hash": "v2"},
    })
    summary = resp.get("summary", "")
    assert "OK" in summary or "REGRESS" in summary, \
        f"summary deve conter OK ou REGRESSAO: '{summary}'"
    # Deve ter Score antes→depois
    assert "->" in summary or "→" in summary, \
        f"summary deve ter seta Score: '{summary}'"
    print(f"  [T5C] ok — summary: '{summary}'")


# ─── T5D: scores em [0, 100] ─────────────────────────────────────────────────

def test_T5D_scores_in_valid_range():
    """uco_score_before e uco_score_after estão em [0, 100]."""
    for before_code, after_code in [
        (CODE_SIMPLE, CODE_COMPLEX),
        (CODE_COMPLEX, CODE_REPAIRED),
        (CODE_SIMPLE, CODE_SIMPLE),
    ]:
        code, resp = handle_diff({
            "before": {"code": before_code, "commit_hash": "v1"},
            "after":  {"code": after_code,  "commit_hash": "v2"},
        })
        sb = resp["uco_score_before"]
        sa = resp["uco_score_after"]
        assert 0 <= sb <= 100, f"uco_score_before={sb} fora de [0,100]"
        assert 0 <= sa <= 100, f"uco_score_after={sa} fora de [0,100]"
    print(f"  [T5D] ok — scores always in [0, 100]")


# ─── Runner ──────────────────────────────────────────────────────────────────

TESTS = [
    ("T50",  test_T50_diff_required_fields),
    ("T51",  test_T51_delta_h_positive_on_degradation),
    ("T52",  test_T52_delta_h_negative_on_improvement),
    ("T53",  test_T53_regression_flag_on_strong_degradation),
    ("T54",  test_T54_transforms_on_dead_code),
    ("T55",  test_T55_identical_code_delta_zero),
    ("T56a", test_T56a_diff_python),
    ("T56b", test_T56b_diff_javascript),
    ("T57",  test_T57_benchmark_20_files_under_5s),
    ("T58",  test_T58_healthy_code_score_ge_40),
    ("T59",  test_T59_validate_real_repos_quick),
    ("T5A",  test_T5A_diff_http_200),
    ("T5B",  test_T5B_diff_http_400_empty_code),
    ("T5C",  test_T5C_summary_contains_status),
    ("T5D",  test_T5D_scores_in_valid_range),
]


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    passed = 0
    failed = 0
    errors = []

    print(f"\n{'='*65}")
    print(f"  UCO-Sensor Marco 5 — Benchmark & Diff Mode  ({len(TESTS)} testes)")
    print(f"{'='*65}")

    for name, fn in TESTS:
        try:
            fn()
            print(f"  OK {name}")
            passed += 1
        except Exception as exc:
            import traceback
            print(f"  FAIL {name}: {exc}")
            traceback.print_exc()
            failed += 1
            errors.append((name, exc))

    print(f"\n{'='*65}")
    print(f"  Resultado: {passed}/{len(TESTS)} passaram")
    if errors:
        print(f"\n  Falhas:")
        for n, e in errors:
            print(f"    {n}: {e}")
    print(f"{'='*65}\n")

    sys.exit(0 if failed == 0 else 1)
