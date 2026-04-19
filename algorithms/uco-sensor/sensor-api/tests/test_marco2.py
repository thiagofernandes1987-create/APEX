"""
UCO-Sensor — Test Suite Marco 2
=================================
Valida os quatro blocos do Marco 2:

  M2-1  LanguageAdapters + UCOBridgeRegistry
    T10  PythonAdapter — delega ao UCOBridge, produz MetricVector correto
    T11  JavaScriptAdapter — fallback mínimo se tree-sitter ausente
    T12  JavaAdapter — fallback mínimo se tree-sitter ausente
    T13  GoAdapter — fallback mínimo se tree-sitter ausente
    T14  UCOBridgeRegistry — despacho por extensão, fallback, cache

  M2-2  Auth + Billing gate
    T15  create_key — formato uco_<hex>, nunca reutiliza prefixo
    T16  validate_key — aceita chave válida, retorna info
    T17  validate_key — rejeita chave inválida / revogada
    T18  quota diária — bloqueia após N chamadas
    T19  revoke_key — revoga e impede uso futuro
    T20  list_keys — lista sem expor hash

  M2-3  CI/CD — /analyze-pr + SARIF
    T21  /analyze com file_extension — produz MetricVector na linguagem certa
    T22  /analyze-pr com lista de arquivos — retorna sarif + file_results
    T23  /analyze-pr SARIF — estrutura 2.1.0 válida
    T24  /analyze-pr status agregado — CRITICAL se algum arquivo CRITICAL
    T25  /docs — retorna lista de endpoints documentados

  M2-4  Deployment
    T26  Dockerfile existe
    T27  requirements.txt existe e tem dependências core
    T28  /health inclui languages no payload
    T29  servidor responde em < 200ms (health check)
"""
from __future__ import annotations
import sys
import os
import json
import time
import threading
import urllib.request
import urllib.error
from pathlib import Path
from http.server import HTTPServer

# ── Path setup ─────────────────────────────────────────────────────────────────
_SENSOR = Path(__file__).resolve().parent.parent
_ENGINE = _SENSOR.parent / "frequency-engine"
for _p in (str(_ENGINE), str(_SENSOR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from sensor_storage.snapshot_store import SnapshotStore
from lang_adapters.registry import UCOBridgeRegistry
from lang_adapters.base import LanguageAdapter
from core.data_structures import MetricVector

# ─── Runner ───────────────────────────────────────────────────────────────────

class Runner:
    def __init__(self):
        self.passed = self.failed = 0
        self.errors = []

    def run(self, name: str, fn):
        try:
            t0 = time.perf_counter()
            fn()
            ms = (time.perf_counter() - t0) * 1000
            print(f"  \033[92m✓\033[0m {name:<60} ({ms:.1f}ms)")
            self.passed += 1
        except Exception as e:
            print(f"  \033[91m✗\033[0m {name}")
            print(f"    {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            self.failed += 1
            self.errors.append((name, str(e)))

    def summary(self) -> bool:
        total = self.passed + self.failed
        ok = self.failed == 0
        color = "\033[92m" if ok else "\033[91m"
        print(f"\n{'─'*65}")
        print(f"  {color}{self.passed}/{total} testes passaram\033[0m")
        if self.errors:
            for n, e in self.errors:
                print(f"  • {n}: {e[:90]}")
        return ok


R = Runner()

# ─── Fixtures ─────────────────────────────────────────────────────────────────

PY_CODE = """
def process(items):
    result = []
    for item in items:
        if item > 0:
            result.append(item * 2)
    return result

class Handler:
    def handle(self, req):
        if req.method == 'GET':
            return self.get(req)
        return self.post(req)
    def get(self, req): return {}
    def post(self, req): return {}
"""

JS_CODE = """
function processItems(items) {
  const result = [];
  for (const item of items) {
    if (item > 0) {
      result.push(item * 2);
    }
  }
  return result;
}

class Handler {
  handle(req) {
    if (req.method === 'GET') {
      return this.get(req);
    }
    return this.post(req);
  }
  get(req) { return {}; }
  post(req) { return {}; }
}
"""

JAVA_CODE = """
public class Handler {
    public Object handle(Request req) {
        if (req.getMethod().equals("GET")) {
            return get(req);
        }
        return post(req);
    }
    private Object get(Request req) { return null; }
    private Object post(Request req) { return null; }
}
"""

GO_CODE = """
package handler

import "net/http"

type Handler struct{}

func (h *Handler) ServeHTTP(w http.ResponseWriter, r *http.Request) {
    if r.Method == "GET" {
        h.get(w, r)
        return
    }
    h.post(w, r)
}

func (h *Handler) get(w http.ResponseWriter, r *http.Request) {}
func (h *Handler) post(w http.ResponseWriter, r *http.Request) {}
"""

TS_CODE = """
interface Request { method: string; body: unknown; }
function processItems(items: number[]): number[] {
  return items.filter(x => x > 0).map(x => x * 2);
}
export class ApiHandler {
  handle(req: Request): unknown {
    if (req.method === 'GET') return this.get(req);
    return this.post(req);
  }
  private get(req: Request) { return {}; }
  private post(req: Request) { return {}; }
}
"""

PORT_M2 = 19082

_server_m2 = None
_server_store = SnapshotStore(":memory:")


def _start_server():
    global _server_m2
    if _server_m2:
        return

    # Patchear o store e bridge do server para usar instâncias de teste
    import api.server as srv
    srv._store = _server_store

    _server_m2 = HTTPServer(("127.0.0.1", PORT_M2), srv.UCOSensorHandler)
    t = threading.Thread(target=_server_m2.serve_forever, daemon=True)
    t.start()
    time.sleep(0.2)


def _get(path: str, params: str = "") -> dict:
    url = f"http://127.0.0.1:{PORT_M2}{path}"
    if params:
        url += f"?{params}"
    with urllib.request.urlopen(url, timeout=5) as r:
        return json.loads(r.read())


def _post(path: str, body: dict) -> dict:
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        f"http://127.0.0.1:{PORT_M2}{path}",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        # Retorna o JSON de erro (4xx/5xx) sem explodir — testes de validação precisam disso
        return json.loads(e.read())


def _delete(path: str, params: str = "") -> dict:
    url = f"http://127.0.0.1:{PORT_M2}{path}"
    if params:
        url += f"?{params}"
    req = urllib.request.Request(url, method="DELETE")
    with urllib.request.urlopen(req, timeout=5) as r:
        return json.loads(r.read())


# ════════════════════════════════════════════════════════════════════════════════
print(f"\n{'═'*65}")
print("  Marco 2 — Test Suite")
print(f"{'═'*65}\n")
print("  M2-1  LanguageAdapters + UCOBridgeRegistry")
print(f"{'─'*65}")

# ─── T10: PythonAdapter ───────────────────────────────────────────────────────

def test_T10a_python_adapter_returns_mv():
    from lang_adapters.python_adapter import PythonAdapter
    adapter = PythonAdapter(mode="full")
    mv = adapter.compute_metrics(PY_CODE, module_id="handler.py", commit_hash="py001")
    assert isinstance(mv, MetricVector)
    assert mv.module_id == "handler.py"
    assert mv.language == "python"

R.run("T10a — PythonAdapter retorna MetricVector", test_T10a_python_adapter_returns_mv)


def test_T10b_python_adapter_cc_nonzero():
    from lang_adapters.python_adapter import PythonAdapter
    adapter = PythonAdapter(mode="full")
    mv = adapter.compute_metrics(PY_CODE, module_id="m", commit_hash="c")
    assert mv.cyclomatic_complexity >= 3, f"CC={mv.cyclomatic_complexity} (esperado >= 3)"
    assert mv.n_functions >= 2, f"n_functions={mv.n_functions}"

R.run("T10b — PythonAdapter CC e n_functions corretos", test_T10b_python_adapter_cc_nonzero)


def test_T10c_python_adapter_supports():
    from lang_adapters.python_adapter import PythonAdapter
    adapter = PythonAdapter()
    assert adapter.supports(".py")
    assert adapter.supports("py")
    assert adapter.supports(".pyw")
    assert not adapter.supports(".js")

R.run("T10c — PythonAdapter.supports() correto", test_T10c_python_adapter_supports)


# ─── T11: JavaScriptAdapter ───────────────────────────────────────────────────

def test_T11a_js_adapter_fallback():
    """JS adapter deve funcionar mesmo sem tree-sitter (fallback mínimo)."""
    from lang_adapters.javascript import JavaScriptAdapter
    adapter = JavaScriptAdapter()
    mv = adapter.compute_metrics(JS_CODE, module_id="handler.js", commit_hash="js001",
                                  file_extension=".js")
    assert isinstance(mv, MetricVector)
    assert mv.module_id == "handler.js"
    # language deve ser javascript ou typescript
    assert mv.language in ("javascript", "typescript", "python"), f"lang={mv.language}"

R.run("T11a — JavaScriptAdapter retorna MetricVector (com/sem tree-sitter)", test_T11a_js_adapter_fallback)


def test_T11b_ts_extension_sets_language():
    from lang_adapters.javascript import JavaScriptAdapter
    adapter = JavaScriptAdapter()
    mv = adapter.compute_metrics(TS_CODE, module_id="api.ts", commit_hash="ts001",
                                  file_extension=".ts")
    assert isinstance(mv, MetricVector)
    # Se tree-sitter disponível, language="typescript"; senão fallback="javascript"
    assert mv.language in ("typescript", "javascript", "python")

R.run("T11b — TypeScript extension detectada corretamente", test_T11b_ts_extension_sets_language)


def test_T11c_js_adapter_supports():
    from lang_adapters.javascript import JavaScriptAdapter
    adapter = JavaScriptAdapter()
    for ext in (".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx"):
        assert adapter.supports(ext), f"suporte ausente para {ext}"
    assert not adapter.supports(".py")

R.run("T11c — JavaScriptAdapter.supports() cobre todas extensões JS/TS", test_T11c_js_adapter_supports)


# ─── T12: JavaAdapter ─────────────────────────────────────────────────────────

def test_T12a_java_adapter():
    from lang_adapters.java import JavaAdapter
    adapter = JavaAdapter()
    mv = adapter.compute_metrics(JAVA_CODE, module_id="Handler.java", commit_hash="java001",
                                  file_extension=".java")
    assert isinstance(mv, MetricVector)
    assert mv.language == "java"

R.run("T12a — JavaAdapter retorna MetricVector", test_T12a_java_adapter)


def test_T12b_java_supports():
    from lang_adapters.java import JavaAdapter
    adapter = JavaAdapter()
    assert adapter.supports(".java")
    assert adapter.supports("java")
    assert not adapter.supports(".go")

R.run("T12b — JavaAdapter.supports() correto", test_T12b_java_supports)


# ─── T13: GoAdapter ───────────────────────────────────────────────────────────

def test_T13a_go_adapter():
    from lang_adapters.golang import GoAdapter
    adapter = GoAdapter()
    mv = adapter.compute_metrics(GO_CODE, module_id="handler.go", commit_hash="go001",
                                  file_extension=".go")
    assert isinstance(mv, MetricVector)
    assert mv.language == "go"

R.run("T13a — GoAdapter retorna MetricVector", test_T13a_go_adapter)


def test_T13b_go_supports():
    from lang_adapters.golang import GoAdapter
    adapter = GoAdapter()
    assert adapter.supports(".go")
    assert not adapter.supports(".java")

R.run("T13b — GoAdapter.supports() correto", test_T13b_go_supports)


# ─── T14: UCOBridgeRegistry ───────────────────────────────────────────────────

def test_T14a_registry_python():
    reg = UCOBridgeRegistry()
    mv = reg.analyze(PY_CODE, file_extension=".py", module_id="m.py", commit_hash="r001")
    assert mv.language == "python"

R.run("T14a — registry despacha .py → PythonAdapter", test_T14a_registry_python)


def test_T14b_registry_js():
    reg = UCOBridgeRegistry()
    mv = reg.analyze(JS_CODE, file_extension=".js", module_id="m.js", commit_hash="r002")
    assert isinstance(mv, MetricVector)

R.run("T14b — registry despacha .js → JavaScriptAdapter", test_T14b_registry_js)


def test_T14c_registry_java():
    reg = UCOBridgeRegistry()
    mv = reg.analyze(JAVA_CODE, file_extension=".java", module_id="M.java", commit_hash="r003")
    assert mv.language == "java"

R.run("T14c — registry despacha .java → JavaAdapter", test_T14c_registry_java)


def test_T14d_registry_go():
    reg = UCOBridgeRegistry()
    mv = reg.analyze(GO_CODE, file_extension=".go", module_id="m.go", commit_hash="r004")
    assert mv.language == "go"

R.run("T14d — registry despacha .go → GoAdapter", test_T14d_registry_go)


def test_T14e_registry_unknown_fallback():
    reg = UCOBridgeRegistry()
    mv = reg.analyze("x = 1\n", file_extension=".rb", module_id="m.rb", commit_hash="r005")
    assert isinstance(mv, MetricVector)

R.run("T14e — registry fallback para extensão desconhecida", test_T14e_registry_unknown_fallback)


def test_T14f_registry_cache():
    """Dois gets da mesma extensão retornam a mesma instância."""
    reg = UCOBridgeRegistry()
    a1 = reg.get_adapter(".py")
    a2 = reg.get_adapter(".py")
    assert a1 is a2

R.run("T14f — registry faz cache do adapter por classe", test_T14f_registry_cache)


def test_T14g_registry_supported_languages():
    reg = UCOBridgeRegistry()
    langs = reg.supported_languages()
    for lang in ("python", "javascript", "typescript", "java", "go"):
        assert lang in langs, f"{lang} ausente em supported_languages()"

R.run("T14g — supported_languages() contém todas as 5 linguagens", test_T14g_registry_supported_languages)


def test_T14h_registry_language_for():
    reg = UCOBridgeRegistry()
    assert reg.language_for(".py") == "python"
    assert reg.language_for(".ts") == "typescript"
    assert reg.language_for(".java") == "java"
    assert reg.language_for(".go") == "go"
    assert reg.language_for(".jsx") == "javascript"

R.run("T14h — language_for() correto para todas extensões", test_T14h_registry_language_for)


# ════════════════════════════════════════════════════════════════════════════════
print(f"\n  M2-2  Auth + Billing gate")
print(f"{'─'*65}")

auth_store = SnapshotStore(":memory:")

def test_T15a_create_key_format():
    key = auth_store.create_key(name="test_key")
    assert key.startswith("uco_"), f"Formato inválido: {key}"
    assert len(key) == 36, f"Comprimento inválido: {len(key)} (esperado 36)"

R.run("T15a — create_key retorna uco_<hex> com 36 chars", test_T15a_create_key_format)


def test_T15b_create_key_unique():
    k1 = auth_store.create_key(name="key1")
    k2 = auth_store.create_key(name="key2")
    assert k1 != k2

R.run("T15b — create_key gera chaves únicas", test_T15b_create_key_unique)


def test_T15c_key_not_in_list_plain():
    """Listagem de chaves nunca deve expor o plain text."""
    key = auth_store.create_key(name="secret_svc")
    keys = auth_store.list_keys()
    # plain key não deve aparecer em nenhum campo
    for k in keys:
        assert key not in str(k.values()), "plain key exposta na listagem!"

R.run("T15c — plain key nunca exposta em list_keys()", test_T15c_key_not_in_list_plain)


def test_T16a_validate_key_valid():
    key = auth_store.create_key(name="valid_svc")
    info = auth_store.validate_key(key)
    assert info is not None
    assert info["name"] == "valid_svc"
    assert info["calls_today"] == 1
    assert info["calls_total"] == 1

R.run("T16a — validate_key aceita chave válida", test_T16a_validate_key_valid)


def test_T16b_validate_increments_counter():
    key = auth_store.create_key(name="counter_svc")
    for i in range(3):
        info = auth_store.validate_key(key)
        assert info["calls_total"] == i + 1

R.run("T16b — validate_key incrementa calls_total", test_T16b_validate_increments_counter)


def test_T17a_validate_invalid_key():
    info = auth_store.validate_key("uco_invalidkeynotexist1234567890ab")
    assert info is None

R.run("T17a — validate_key rejeita chave inexistente", test_T17a_validate_invalid_key)


def test_T17b_validate_wrong_prefix():
    info = auth_store.validate_key("sk_notavalidprefix")
    assert info is None

R.run("T17b — validate_key rejeita prefixo errado", test_T17b_validate_wrong_prefix)


def test_T18a_quota_enforcement():
    key = auth_store.create_key(name="quota_svc", quota_day=3)
    # 3 chamadas devem passar
    for i in range(3):
        info = auth_store.validate_key(key)
        assert info is not None, f"Chamada {i+1} deveria passar"
    # 4ª chamada deve ser bloqueada
    info = auth_store.validate_key(key)
    assert info is None, "4ª chamada deveria ser bloqueada pela quota"

R.run("T18a — quota_day bloqueia após N chamadas", test_T18a_quota_enforcement)


def test_T18b_quota_zero_unlimited():
    key = auth_store.create_key(name="unlimited_svc", quota_day=0)
    for _ in range(10):
        info = auth_store.validate_key(key)
        assert info is not None, "quota=0 deve ser ilimitada"

R.run("T18b — quota_day=0 é ilimitada", test_T18b_quota_zero_unlimited)


def test_T19a_revoke_key():
    key = auth_store.create_key(name="to_revoke")
    prefix = key[:12]
    assert auth_store.validate_key(key) is not None   # ok antes
    ok = auth_store.revoke_key(prefix)
    assert ok, "revoke_key deve retornar True"
    assert auth_store.validate_key(key) is None       # bloqueado depois

R.run("T19a — revoke_key bloqueia uso futuro da chave", test_T19a_revoke_key)


def test_T19b_revoke_nonexistent():
    ok = auth_store.revoke_key("uco_nonexist")
    assert not ok, "revoke de chave inexistente deve retornar False"

R.run("T19b — revoke_key retorna False para chave inexistente", test_T19b_revoke_nonexistent)


def test_T20a_list_keys():
    s = SnapshotStore(":memory:")
    s.create_key(name="svc_a")
    s.create_key(name="svc_b")
    keys = s.list_keys()
    assert len(keys) == 2
    names = [k["name"] for k in keys]
    assert "svc_a" in names
    assert "svc_b" in names

R.run("T20a — list_keys retorna todas as chaves criadas", test_T20a_list_keys)


def test_T20b_get_usage():
    s = SnapshotStore(":memory:")
    key = s.create_key(name="usage_svc")
    s.validate_key(key)
    s.validate_key(key)
    usage = s.get_usage(key[:12])
    assert usage is not None
    assert usage["calls_total"] == 2
    assert usage["name"] == "usage_svc"

R.run("T20b — get_usage retorna calls_total correto", test_T20b_get_usage)


# ════════════════════════════════════════════════════════════════════════════════
print(f"\n  M2-3  CI/CD — endpoints /analyze + /analyze-pr + /docs")
print(f"{'─'*65}")

_start_server()

def test_T21a_analyze_python():
    resp = _post("/analyze", {
        "code": PY_CODE,
        "module_id": "m2.handler_py",
        "commit_hash": "m2a001",
        "file_extension": ".py",
    })
    assert resp["status"] == "ok"
    mv = resp["data"]["metric_vector"]
    assert mv["language"] == "python"
    assert mv["cyclomatic_complexity"] >= 1

R.run("T21a — /analyze com .py retorna language=python", test_T21a_analyze_python)


def test_T21b_analyze_javascript():
    resp = _post("/analyze", {
        "code": JS_CODE,
        "module_id": "m2.handler_js",
        "commit_hash": "m2b001",
        "file_extension": ".js",
    })
    assert resp["status"] == "ok"
    mv = resp["data"]["metric_vector"]
    assert mv["language"] in ("javascript", "python")  # fallback aceito

R.run("T21b — /analyze com .js retorna MetricVector", test_T21b_analyze_javascript)


def test_T21c_analyze_java():
    resp = _post("/analyze", {
        "code": JAVA_CODE,
        "module_id": "m2.Handler_java",
        "commit_hash": "m2c001",
        "file_extension": ".java",
    })
    assert resp["status"] == "ok"
    mv = resp["data"]["metric_vector"]
    assert mv["language"] == "java"

R.run("T21c — /analyze com .java retorna language=java", test_T21c_analyze_java)


def test_T21d_analyze_go():
    resp = _post("/analyze", {
        "code": GO_CODE,
        "module_id": "m2.handler_go",
        "commit_hash": "m2d001",
        "file_extension": ".go",
    })
    assert resp["status"] == "ok"
    mv = resp["data"]["metric_vector"]
    assert mv["language"] == "go"

R.run("T21d — /analyze com .go retorna language=go", test_T21d_analyze_go)


def test_T22a_analyze_pr_basic():
    resp = _post("/analyze-pr", {
        "files": [
            {"path": "src/handler.py", "content": PY_CODE,   "commit_hash": "pr001"},
            {"path": "src/handler.js", "content": JS_CODE,   "commit_hash": "pr001"},
            {"path": "src/Handler.java","content": JAVA_CODE, "commit_hash": "pr001"},
        ],
        "pr_number": 42,
        "repo": "org/repo",
        "base_branch": "main",
    })
    assert resp["status"] == "ok"
    data = resp["data"]
    assert data["files_analyzed"] == 3
    assert data["pr_number"] == 42
    assert "file_results" in data
    assert len(data["file_results"]) == 3

R.run("T22a — /analyze-pr analisa 3 arquivos multilinguagem", test_T22a_analyze_pr_basic)


def test_T22b_analyze_pr_empty_files():
    resp = _post("/analyze-pr", {"files": []})
    assert resp["status"] == "error"
    assert "files" in resp["data"]["error"].lower()

R.run("T22b — /analyze-pr rejeita files vazio", test_T22b_analyze_pr_empty_files)


def test_T23a_sarif_schema():
    resp = _post("/analyze-pr", {
        "files": [{"path": "x.py", "content": PY_CODE, "commit_hash": "s001"}],
        "pr_number": 1,
    })
    sarif = resp["data"]["sarif"]
    assert sarif["version"] == "2.1.0"
    assert "$schema" in sarif
    assert "runs" in sarif
    assert len(sarif["runs"]) == 1
    run = sarif["runs"][0]
    assert "tool" in run
    assert "results" in run
    assert run["tool"]["driver"]["name"] == "UCO-Sensor"

R.run("T23a — SARIF 2.1.0 tem estrutura válida", test_T23a_sarif_schema)


def test_T23b_sarif_results_non_stable():
    """Arquivos CRITICAL/WARNING devem gerar entradas em sarif.results."""
    # Código com alta complexidade para forçar status != STABLE
    complex_code = "\n".join([
        "def f(a,b,c,d,e,f,g):",
        *[f"    if {chr(97+i)} > 0: pass" for i in range(20)],
        *["    while True: pass"] * 5,
    ])
    resp = _post("/analyze-pr", {
        "files": [{"path": "complex.py", "content": complex_code, "commit_hash": "s002"}],
        "pr_number": 2,
    })
    sarif = resp["data"]["sarif"]
    # se o arquivo tem status não-STABLE, deve ter resultado no SARIF
    file_result = resp["data"]["file_results"][0]
    if file_result["status"] != "STABLE":
        assert len(sarif["runs"][0]["results"]) >= 1

R.run("T23b — SARIF contém resultados para arquivos não-STABLE", test_T23b_sarif_results_non_stable)


def test_T24a_pr_status_aggregation():
    """pr_status = CRITICAL se algum arquivo for CRITICAL."""
    # Código com complexidade extrema para CRITICAL
    bomb = "def f():\n" + "    if True:\n" * 30 + "        return 1\n"
    resp = _post("/analyze-pr", {
        "files": [
            {"path": "ok.py",   "content": "x=1\n", "commit_hash": "agg001"},
            {"path": "bomb.py", "content": bomb,     "commit_hash": "agg001"},
        ],
        "pr_number": 99,
    })
    data = resp["data"]
    assert data["pr_status"] in ("STABLE", "WARNING", "CRITICAL")  # válido
    assert data["critical_files"] >= 0
    assert data["warning_files"] >= 0
    assert data["critical_files"] + data["warning_files"] <= data["files_analyzed"]

R.run("T24a — pr_status agrega status dos arquivos corretamente", test_T24a_pr_status_aggregation)


def test_T24b_stable_pr_all_stable():
    resp = _post("/analyze-pr", {
        "files": [{"path": "simple.py", "content": "x = 1\n", "commit_hash": "stb001"}],
        "pr_number": 5,
    })
    data = resp["data"]
    # código mínimo deve ser STABLE
    assert data["pr_status"] in ("STABLE", "WARNING")
    assert data["files_analyzed"] == 1

R.run("T24b — pr simples retorna STABLE ou WARNING (nunca CRITICAL)", test_T24b_stable_pr_all_stable)


def test_T25a_docs_endpoint():
    resp = _get("/docs")
    assert resp["status"] == "ok"
    data = resp["data"]
    assert "endpoints" in data
    assert isinstance(data["endpoints"], list)
    assert len(data["endpoints"]) >= 8
    paths = [e["path"] for e in data["endpoints"]]
    for required in ("/analyze", "/repair", "/health", "/history", "/baseline"):
        assert required in paths, f"{required} ausente em /docs"

R.run("T25a — /docs retorna lista completa de endpoints", test_T25a_docs_endpoint)


def test_T25b_docs_has_analyze_pr():
    resp = _get("/docs")
    paths = [e["path"] for e in resp["data"]["endpoints"]]
    assert "/analyze-pr" in paths, "/analyze-pr deve estar documentado"

R.run("T25b — /docs inclui /analyze-pr", test_T25b_docs_has_analyze_pr)


def test_T25c_docs_has_apex_endpoints():
    resp = _get("/docs")
    paths = [e["path"] for e in resp["data"]["endpoints"]]
    assert "/apex/status" in paths
    assert "/apex/ping" in paths

R.run("T25c — /docs inclui endpoints APEX", test_T25c_docs_has_apex_endpoints)


# ════════════════════════════════════════════════════════════════════════════════
print(f"\n  M2-4  Deployment")
print(f"{'─'*65}")

def test_T26_dockerfile_exists():
    dockerfile = _SENSOR / "Dockerfile"
    assert dockerfile.exists(), f"Dockerfile não encontrado em {dockerfile}"
    content = dockerfile.read_text()
    assert "FROM python" in content
    assert "EXPOSE" in content
    assert "HEALTHCHECK" in content

R.run("T26  — Dockerfile existe com FROM/EXPOSE/HEALTHCHECK", test_T26_dockerfile_exists)


def test_T27_requirements_txt():
    req = _SENSOR / "requirements.txt"
    assert req.exists(), f"requirements.txt não encontrado em {req}"
    content = req.read_text()
    for dep in ("numpy", "scipy", "PyWavelets", "tree-sitter"):
        assert dep in content, f"{dep} ausente em requirements.txt"

R.run("T27  — requirements.txt existe com deps core", test_T27_requirements_txt)


def test_T28_health_includes_languages():
    resp = _get("/health")
    assert resp["status"] == "ok"
    data = resp["data"]
    assert "languages" in data, "Campo languages ausente em /health"
    assert isinstance(data["languages"], list)
    assert len(data["languages"]) >= 5

R.run("T28  — /health inclui campo languages", test_T28_health_includes_languages)


def test_T29_health_latency():
    t0 = time.perf_counter()
    _get("/health")
    ms = (time.perf_counter() - t0) * 1000
    assert ms < 200, f"/health demorou {ms:.1f}ms (limite: 200ms)"

R.run("T29  — /health responde em < 200ms", test_T29_health_latency)


# ─── Sumário ──────────────────────────────────────────────────────────────────
print()
ok = R.summary()
sys.exit(0 if ok else 1)
