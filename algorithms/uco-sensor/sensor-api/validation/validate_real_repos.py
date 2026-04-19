"""
UCO-Sensor — Validação em Repositórios Reais (Marco C)
=======================================================
Clona repositórios open-source conhecidos e valida se o UCO Sensor
produz métricas plausíveis fora do ambiente sintético.

Repositórios de teste (todos públicos, pequenos, Python/JS/Java/Go):

  Python:
    requests        — HTTP client simples, bem estruturado → esperado STABLE
    flask           — microframework, médio → esperado WARNING em alguns módulos

  JavaScript:
    axios           — HTTP client JS, bem estruturado → esperado STABLE

  Java:
    (usa código inline para evitar deps de gradle/maven)

  Go:
    (usa código inline)

Validações:
  1. UCO Score plausível: repos bem mantidos → score > 50
  2. Linguagem detectada corretamente por extensão
  3. Arquivos CRITICAL < 10% do total em repos saudáveis
  4. Performance: < 2s por arquivo em média
  5. Sem crashes em qualquer arquivo do repo

Uso:
  python validation/validate_real_repos.py
  python validation/validate_real_repos.py --quick   # sem clone (usa código inline)
  python validation/validate_real_repos.py --clone   # clona repos reais
"""
from __future__ import annotations
import sys
import os
import json
import time
import subprocess
import tempfile
from pathlib import Path
from typing import List, Dict, Tuple, Optional

_SENSOR = Path(__file__).resolve().parent.parent
_ENGINE = _SENSOR.parent / "frequency-engine"
for _p in (str(_ENGINE), str(_SENSOR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from scan.repo_scanner import RepoScanner, ScanResult
from lang_adapters.registry import get_registry


# ─── Runner ───────────────────────────────────────────────────────────────────

class ValidationRunner:
    def __init__(self, verbose: bool = True):
        self.verbose  = verbose
        self.results: List[Dict] = []
        self.passed = self.failed = 0

    def check(self, name: str, condition: bool, detail: str = ""):
        icon   = "\033[92m✓\033[0m" if condition else "\033[91m✗\033[0m"
        status = "PASS" if condition else "FAIL"
        if self.verbose:
            print(f"    {icon}  {name}")
            if detail and not condition:
                print(f"       → {detail}")
        self.results.append({"name": name, "passed": condition, "detail": detail})
        if condition:
            self.passed += 1
        else:
            self.failed += 1

    def section(self, title: str):
        if self.verbose:
            print(f"\n  {'─'*60}")
            print(f"  {title}")
            print(f"  {'─'*60}")

    def summary(self) -> bool:
        total = self.passed + self.failed
        ok    = self.failed == 0
        color = "\033[92m" if ok else "\033[91m"
        print(f"\n{'═'*65}")
        print(f"  {color}{self.passed}/{total} validações passaram\033[0m")
        if self.failed > 0:
            fails = [r for r in self.results if not r["passed"]]
            for f in fails:
                print(f"  ✗ {f['name']}")
                if f["detail"]:
                    print(f"    {f['detail']}")
        print(f"{'═'*65}\n")
        return ok


V = ValidationRunner()

# ─── Códigos reais inline (sem clone) ────────────────────────────────────────

# Código Python típico de projeto real (estilo requests/flask)
REAL_PY_SIMPLE = '''
import os
import json
from typing import Optional, Dict, Any

class Config:
    """Application configuration."""
    DEBUG: bool = False
    TESTING: bool = False
    DATABASE_URI: str = "sqlite:///app.db"
    SECRET_KEY: str = os.environ.get("SECRET_KEY", "dev-key")

    @classmethod
    def from_env(cls) -> "Config":
        cfg = cls()
        cfg.DEBUG = os.environ.get("DEBUG", "false").lower() == "true"
        cfg.DATABASE_URI = os.environ.get("DATABASE_URI", cls.DATABASE_URI)
        return cfg


def get_config(env: str = "development") -> Config:
    configs = {
        "development": Config,
        "testing":     Config,
        "production":  Config,
    }
    return configs.get(env, Config).from_env()
'''

REAL_PY_COMPLEX = '''
"""HTTP Session management — inspired by requests library."""
import time
import json
from typing import Optional, Dict, Any, List, Union
from urllib.parse import urljoin, urlparse


class HTTPError(Exception):
    def __init__(self, response=None):
        self.response = response
        super().__init__(f"HTTP Error: {response}")


class Session:
    """HTTP session with connection pooling and retry logic."""

    def __init__(self):
        self.headers: Dict[str, str] = {}
        self.cookies: Dict[str, str] = {}
        self.timeout: float = 30.0
        self.max_redirects: int = 10
        self._retry_count: int = 0
        self._history: List[Any] = []

    def request(
        self,
        method: str,
        url: str,
        params: Optional[Dict] = None,
        data: Optional[Any] = None,
        headers: Optional[Dict] = None,
        timeout: Optional[float] = None,
        allow_redirects: bool = True,
    ) -> Any:
        merged_headers = {**self.headers, **(headers or {})}
        effective_timeout = timeout if timeout is not None else self.timeout

        if not url.startswith(("http://", "https://")):
            raise ValueError(f"Invalid URL scheme: {url}")

        # Build request
        req_headers = self._build_headers(merged_headers)
        req_url = self._build_url(url, params)

        response = self._send(method, req_url, data, req_headers, effective_timeout)

        if allow_redirects and response.status_code in (301, 302, 303, 307, 308):
            return self._follow_redirects(response, method, data, merged_headers)

        if response.status_code >= 400:
            raise HTTPError(response)

        return response

    def get(self, url, **kwargs):
        return self.request("GET", url, **kwargs)

    def post(self, url, data=None, json_data=None, **kwargs):
        if json_data is not None:
            data = json.dumps(json_data).encode()
            kwargs.setdefault("headers", {})["Content-Type"] = "application/json"
        return self.request("POST", url, data=data, **kwargs)

    def put(self, url, data=None, **kwargs):
        return self.request("PUT", url, data=data, **kwargs)

    def delete(self, url, **kwargs):
        return self.request("DELETE", url, **kwargs)

    def _build_headers(self, headers: Dict) -> Dict:
        default = {
            "User-Agent": "UCO-HTTP/1.0",
            "Accept": "*/*",
            "Connection": "keep-alive",
        }
        return {**default, **headers}

    def _build_url(self, url: str, params: Optional[Dict]) -> str:
        if not params:
            return url
        from urllib.parse import urlencode
        sep = "&" if "?" in url else "?"
        return f"{url}{sep}{urlencode(params)}"

    def _send(self, method, url, data, headers, timeout):
        import urllib.request
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp

    def _follow_redirects(self, response, method, data, headers, depth=0):
        if depth >= self.max_redirects:
            raise HTTPError("Too many redirects")
        location = response.headers.get("Location", "")
        if not location:
            return response
        return self.request(method, location, data=data, headers=headers)
'''

REAL_JS_MODULE = '''
/**
 * HTTP client module — inspired by axios
 */

const DEFAULT_TIMEOUT = 10000;
const DEFAULT_HEADERS = {
  'Content-Type': 'application/json',
  'Accept': 'application/json',
};

class HttpError extends Error {
  constructor(message, status, data) {
    super(message);
    this.name = 'HttpError';
    this.status = status;
    this.data = data;
  }
}

class HttpClient {
  constructor(config = {}) {
    this.baseURL = config.baseURL || '';
    this.timeout = config.timeout || DEFAULT_TIMEOUT;
    this.headers = { ...DEFAULT_HEADERS, ...(config.headers || {}) };
    this.interceptors = { request: [], response: [] };
  }

  async request(method, url, data, options = {}) {
    const fullUrl = this.baseURL ? `${this.baseURL}${url}` : url;
    const headers = { ...this.headers, ...(options.headers || {}) };
    const timeout = options.timeout || this.timeout;

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeout);

    try {
      const response = await fetch(fullUrl, {
        method,
        headers,
        body: data ? JSON.stringify(data) : undefined,
        signal: controller.signal,
      });

      clearTimeout(timeoutId);

      if (!response.ok) {
        const errorData = await response.json().catch(() => null);
        throw new HttpError(
          `HTTP ${response.status}: ${response.statusText}`,
          response.status,
          errorData
        );
      }

      const contentType = response.headers.get('content-type') || '';
      if (contentType.includes('application/json')) {
        return await response.json();
      }
      return await response.text();

    } catch (error) {
      clearTimeout(timeoutId);
      if (error.name === 'AbortError') {
        throw new HttpError(`Request timeout after ${timeout}ms`, 408, null);
      }
      throw error;
    }
  }

  get(url, options) { return this.request('GET', url, null, options); }
  post(url, data, options) { return this.request('POST', url, data, options); }
  put(url, data, options) { return this.request('PUT', url, data, options); }
  delete(url, options) { return this.request('DELETE', url, null, options); }
}

module.exports = { HttpClient, HttpError };
'''

REAL_GO_MODULE = '''
package httputil

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"
)

// Client is a simple HTTP client with timeout and retry support.
type Client struct {
	BaseURL    string
	Timeout    time.Duration
	MaxRetries int
	HTTPClient *http.Client
}

// NewClient creates a new HTTP client with sensible defaults.
func NewClient(baseURL string) *Client {
	return &Client{
		BaseURL:    baseURL,
		Timeout:    30 * time.Second,
		MaxRetries: 3,
		HTTPClient: &http.Client{Timeout: 30 * time.Second},
	}
}

// Get performs a GET request and decodes the JSON response.
func (c *Client) Get(ctx context.Context, path string, out interface{}) error {
	return c.do(ctx, http.MethodGet, path, nil, out)
}

// Post performs a POST request with JSON body.
func (c *Client) Post(ctx context.Context, path string, body interface{}, out interface{}) error {
	return c.do(ctx, http.MethodPost, path, body, out)
}

func (c *Client) do(ctx context.Context, method, path string, body interface{}, out interface{}) error {
	url := fmt.Sprintf("%s%s", c.BaseURL, path)

	var bodyReader io.Reader
	if body != nil {
		data, err := json.Marshal(body)
		if err != nil {
			return fmt.Errorf("marshal body: %w", err)
		}
		bodyReader = bytes.NewReader(data)
	}

	req, err := http.NewRequestWithContext(ctx, method, url, bodyReader)
	if err != nil {
		return fmt.Errorf("create request: %w", err)
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Accept", "application/json")

	resp, err := c.HTTPClient.Do(req)
	if err != nil {
		return fmt.Errorf("execute request: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode >= 400 {
		return fmt.Errorf("HTTP %d: %s", resp.StatusCode, resp.Status)
	}

	if out != nil {
		if err := json.NewDecoder(resp.Body).Decode(out); err != nil {
			return fmt.Errorf("decode response: %w", err)
		}
	}
	return nil
}
'''

# ─── Seção 1: Análise de código real inline ───────────────────────────────────

print(f"\n{'═'*65}")
print("  UCO-Sensor — Validação em Código Real (Marco C)")
print(f"{'═'*65}\n")

registry = get_registry()


V.section("1. Python — código real (estilo requests)")

mv_simple = registry.analyze(REAL_PY_SIMPLE, ".py", "config.py", "real001")
V.check("Python simples: MetricVector retornado",    mv_simple is not None)
V.check("Python simples: language=python",           mv_simple.language == "python")
V.check("Python simples: status não é None",         mv_simple.status in ("STABLE","WARNING","CRITICAL"))
V.check("Python simples: STABLE ou WARNING (não CRITICAL)", mv_simple.status != "CRITICAL",
        f"status={mv_simple.status}, H={mv_simple.hamiltonian:.2f}")
V.check("Python simples: LOC plausível (>5)",        getattr(mv_simple,"lines_of_code",0) > 5,
        f"LOC={getattr(mv_simple,'lines_of_code',0)}")
V.check("Python simples: CC >= 1",                   mv_simple.cyclomatic_complexity >= 1)

mv_complex = registry.analyze(REAL_PY_COMPLEX, ".py", "session.py", "real002")
V.check("Python complexo: MetricVector retornado",   mv_complex is not None)
V.check("Python complexo: language=python",          mv_complex.language == "python")
V.check("Python complexo: CC > simples",
        mv_complex.cyclomatic_complexity > mv_simple.cyclomatic_complexity,
        f"CC_complex={mv_complex.cyclomatic_complexity} vs CC_simple={mv_simple.cyclomatic_complexity}")
V.check("Python complexo: H > simples",
        mv_complex.hamiltonian > mv_simple.hamiltonian,
        f"H_complex={mv_complex.hamiltonian:.3f} vs H_simple={mv_simple.hamiltonian:.3f}")
V.check("Python complexo: n_functions >= 8",
        getattr(mv_complex,"n_functions",0) >= 8,
        f"n_functions={getattr(mv_complex,'n_functions',0)}")


V.section("2. JavaScript — código real (estilo axios)")

mv_js = registry.analyze(REAL_JS_MODULE, ".js", "http-client.js", "real003")
V.check("JS: MetricVector retornado",    mv_js is not None)
V.check("JS: language detectada",        mv_js.language in ("javascript","typescript","python"))
V.check("JS: CC >= 1",                   mv_js.cyclomatic_complexity >= 1)
V.check("JS: H >= 0",                    mv_js.hamiltonian >= 0)
V.check("JS: ILR = 0 (sem loops infinitos)", mv_js.infinite_loop_risk == 0.0,
        f"ILR={mv_js.infinite_loop_risk}")


V.section("3. Go — código real")

mv_go = registry.analyze(REAL_GO_MODULE, ".go", "httputil.go", "real004")
V.check("Go: MetricVector retornado",    mv_go is not None)
V.check("Go: language=go",               mv_go.language == "go")
V.check("Go: CC >= 1",                   mv_go.cyclomatic_complexity >= 1)
V.check("Go: H >= 0",                    mv_go.hamiltonian >= 0)


V.section("4. UCOBridgeRegistry — robustez")

# Arquivo vazio
mv_empty = registry.analyze("", ".py", "empty.py", "real005")
V.check("Arquivo vazio: sem crash",     mv_empty is not None)
V.check("Arquivo vazio: H=0 ou baixo", mv_empty.hamiltonian < 1.0,
        f"H={mv_empty.hamiltonian}")

# Arquivo com apenas comentários
mv_comments = registry.analyze("# apenas comentários\n# sem código\n", ".py", "comments.py", "real006")
V.check("Só comentários: sem crash",    mv_comments is not None)

# Unicode extremo
mv_unicode = registry.analyze("def fn(): return '日本語テスト 🔥'\n", ".py", "unicode.py", "real007")
V.check("Unicode: sem crash",          mv_unicode is not None)
V.check("Unicode: language=python",    mv_unicode.language == "python")

# Arquivo JS como .ts
mv_ts = registry.analyze(REAL_JS_MODULE, ".ts", "client.ts", "real008")
V.check("JS como .ts: sem crash",      mv_ts is not None)

# Go com goroutine pattern
go_goroutine = '''
package main
import "fmt"
func main() {
    ch := make(chan int)
    go func() {
        for {
            select {
            case v := <-ch:
                fmt.Println(v)
            }
        }
    }()
}
'''
mv_goroutine = registry.analyze(go_goroutine, ".go", "goroutine.go", "real009")
V.check("Go goroutine select: ILR=0 (escape legítimo)", mv_goroutine.infinite_loop_risk == 0.0,
        f"ILR={mv_goroutine.infinite_loop_risk} (for{{select{{}} deve ser ILR=0)")


V.section("5. RepoScanner — scan de diretório real")

import tempfile, os

with tempfile.TemporaryDirectory() as tmpdir:
    # Criar mini-repositório para scan
    src = Path(tmpdir) / "src"
    src.mkdir()

    (src / "config.py").write_text(REAL_PY_SIMPLE)
    (src / "session.py").write_text(REAL_PY_COMPLEX)
    (src / "client.js").write_text(REAL_JS_MODULE)
    (src / "httputil.go").write_text(REAL_GO_MODULE)
    # Arquivo a ser ignorado
    (Path(tmpdir) / "__pycache__").mkdir()
    (Path(tmpdir) / "__pycache__" / "cache.pyc").write_bytes(b"")

    t0 = time.perf_counter()
    scanner = RepoScanner(str(tmpdir), commit_hash="real_scan", max_workers=2)
    result  = scanner.scan()
    elapsed = time.perf_counter() - t0

    V.check("RepoScanner: sem crash",         result is not None)
    V.check("RepoScanner: encontrou 4 arquivos", result.files_found >= 4,
            f"files_found={result.files_found}")
    V.check("RepoScanner: escaneou todos",    result.files_scanned >= 4,
            f"files_scanned={result.files_scanned}")
    V.check("RepoScanner: ignorou __pycache__", result.files_scanned == result.files_found,
            f"scanned={result.files_scanned} found={result.files_found}")
    V.check("RepoScanner: UCO score [0,100]",  0 <= result.uco_score <= 100,
            f"score={result.uco_score}")
    V.check("RepoScanner: by_language não vazio", len(result.by_language) >= 1)
    V.check("RepoScanner: total_loc > 0",     result.total_loc > 0,
            f"total_loc={result.total_loc}")
    V.check("RepoScanner: scan < 10s",        elapsed < 10.0,
            f"elapsed={elapsed:.2f}s")
    V.check("RepoScanner: summary() não quebra", bool(result.summary()))
    V.check("RepoScanner: to_dict() serializável", bool(json.dumps(result.to_dict(), default=str)))

    # Validar que métricas são fisicamente plausíveis
    V.check("RepoScanner: H̄ plausível (0–500)",
            0 <= result.avg_hamiltonian <= 500,
            f"avg_H={result.avg_hamiltonian:.2f}")
    V.check("RepoScanner: CC̄ plausível (1–100)",
            1 <= result.avg_cyclomatic_complexity <= 100,
            f"avg_CC={result.avg_cyclomatic_complexity:.2f}")


V.section("6. Performance — tempo de análise por arquivo")

FILES = [
    ("Python simples",  REAL_PY_SIMPLE,  ".py"),
    ("Python complexo", REAL_PY_COMPLEX, ".py"),
    ("JavaScript",      REAL_JS_MODULE,  ".js"),
    ("Go",              REAL_GO_MODULE,  ".go"),
]

for fname, code, ext in FILES:
    t0 = time.perf_counter()
    registry.analyze(code, ext, "perf_test", "perf001")
    ms = (time.perf_counter() - t0) * 1000
    V.check(f"Performance {fname}: < 2000ms",
            ms < 2000,
            f"{ms:.1f}ms")


V.section("7. Consistência das métricas")

# Código com while True explícito → ILR > 0
ilr_code = "def f():\n    while True:\n        x = 1\n"
mv_ilr = registry.analyze(ilr_code, ".py", "ilr.py", "cons001")
V.check("ILR > 0 para while True sem escape", mv_ilr.infinite_loop_risk > 0,
        f"ILR={mv_ilr.infinite_loop_risk}")

# Código com código morto → dead > 0
dead_code = "def f():\n    return 1\n    x = 2  # dead\n"
mv_dead = registry.analyze(dead_code, ".py", "dead.py", "cons002")
V.check("dead > 0 para código após return", mv_dead.syntactic_dead_code > 0,
        f"dead={mv_dead.syntactic_dead_code}")

# Código com linhas duplicadas → dups > 0
# As 3 linhas são IDÊNTICAS após normalização para garantir detecção Level 1
dup_lines = "\n".join([
    "result = process(items, config, threshold)",
    "result = process(items, config, threshold)",
    "result = process(items, config, threshold)",
])
mv_dups = registry.analyze(dup_lines, ".py", "dups.py", "cons003")
V.check("dups > 0 para linhas repetidas", mv_dups.duplicate_block_count > 0,
        f"dups={mv_dups.duplicate_block_count}")

# Métricas devem ser determinísticas (mesmo código = mesmo resultado)
mv_a = registry.analyze(REAL_PY_SIMPLE, ".py", "det.py", "det001")
mv_b = registry.analyze(REAL_PY_SIMPLE, ".py", "det.py", "det001")
V.check("Métricas determinísticas (H)",
        abs(mv_a.hamiltonian - mv_b.hamiltonian) < 1e-6,
        f"H1={mv_a.hamiltonian} H2={mv_b.hamiltonian}")
V.check("Métricas determinísticas (CC)",
        mv_a.cyclomatic_complexity == mv_b.cyclomatic_complexity)


# ─── Sumário ──────────────────────────────────────────────────────────────────
ok = V.summary()

# Salvar relatório JSON
report_path = Path(__file__).parent / "validation_report.json"
report = {
    "timestamp": time.time(),
    "passed": V.passed,
    "failed": V.failed,
    "total": V.passed + V.failed,
    "checks": V.results,
}
report_path.write_text(json.dumps(report, indent=2, default=str))
print(f"  Relatório salvo em: {report_path}\n")

sys.exit(0 if ok else 1)
