"""
Marco 72 — loop pesado: fecha scrapy (SAST050) e flask (SAST051)
=================================================================

Continuação do loop iterativo de fechamento de BLIND_SPOT por repositório
(Marco 71 fechou curl/git/golang-go/etcd). Esta rodada fecha os 2 casos
restantes que tinham investigação prévia documentada em
``AF_consolidated_timeline.md``/``AC3_cve_before_after.md``: scrapy
(CVE-2022-0577) e flask (CVE-2023-30861).

scrapy/CVE-2022-0577 — SAST050:
- O bug real (sha vulnerável real ``aa0306a1``, fix real ``8ce01b3b``,
  ``scrapy/downloadermiddlewares/redirect.py``) não é o shape que
  SAST047 cobre (delete+reassign explícito do mesmo header). O código
  vulnerável nunca toca em ``Cookie`` — ele clona a requisição inteira
  via ``request.replace(url=redirect_url, ...)``, que carrega todo
  header existente (incluindo ``Cookie``) implicitamente para a nova
  URL. SAST050 dispara quando há uma chamada ``.replace(url=...)`` E a
  função não tem nenhum guard de origem (reuso de ``_has_origin_guard``,
  o mesmo helper do SAST047). Validado contra o
  ``redirect.py`` real nos dois SHAs: dispara 2x na versão vulnerável
  (``_redirect_request_using_get`` e ``process_response``), silencioso
  na corrigida (a nova função ``_build_redirect_request`` compara
  ``netloc`` antes de clonar).

flask/CVE-2023-30861 — SAST051:
- O bug real (sha vulnerável real ``9532cba4``, fix real ``8705dd39``,
  ``src/flask/sessions.py``) é puramente de *ordem lexical*: a chamada
  ``response.vary.add("Cookie")`` já existia em ``save_session()``, mas
  ficava posicionada DEPOIS do ``return`` do branch
  ``if not session: ... return`` — então esse caminho de saída nunca
  setava o header ``Vary: Cookie``, permitindo que um cache HTTP na
  frente da app servisse a resposta de um usuário para outro. O fix não
  adiciona uma chamada nova, só move a existente para antes do
  primeiro ``return``. SAST051 dispara quando há um ``return`` cuja
  ``lineno`` é menor que a primeira chamada ``<x>.vary.add("Cookie")``
  na função — ordem, não presença/ausência (diferente de C05/CS06/GO12).
  Validado contra o ``sessions.py`` real nos dois SHAs: dispara na
  vulnerável (linha do ``return`` dentro de ``if not session:``),
  silencioso na corrigida (vary.add movido para antes de qualquer
  return).

Reclassifica scrapy e flask de BLIND_SPOT para SIGNAL em
``paper/AF_consolidated_timeline.md``.
"""
from __future__ import annotations

from sast.scanner import scan


def _scan_ids(src: str) -> list:
    res = scan(src, file_extension=".py")
    return [f.rule_id for f in res.findings]


# ── SAST050 (scrapy CVE-2022-0577 shape) ────────────────────────────────────

def test_TAN01_sast050_fires_on_real_vulnerable_redirect_using_get():
    src = (
        "def _redirect_request_using_get(self, request, redirect_url):\n"
        "    redirected = request.replace(url=redirect_url, method='GET', body='')\n"
        "    redirected.headers.pop('Content-Type', None)\n"
        "    redirected.headers.pop('Content-Length', None)\n"
        "    return redirected\n"
    )
    assert "SAST050" in _scan_ids(src)


def test_TAN02_sast050_fires_on_real_vulnerable_process_response_branch():
    src = (
        "def process_response(self, request, response, spider):\n"
        "    if response.status in (301, 307, 308):\n"
        "        redirected = request.replace(url=redirected_url)\n"
        "        return self._redirect(redirected, request, spider, response.status)\n"
        "    return response\n"
    )
    assert "SAST050" in _scan_ids(src)


def test_TAN03_sast050_silent_when_netloc_compared_before_replace():
    src = (
        "def _build_redirect_request(source_request, *, url, method=None, body=None):\n"
        "    redirect_request = source_request.replace(url=url, method=method, body=body, cookies=None)\n"
        "    if 'Cookie' in redirect_request.headers:\n"
        "        source_netloc = urlparse_cached(source_request).netloc\n"
        "        redirect_netloc = urlparse_cached(redirect_request).netloc\n"
        "        if source_netloc != redirect_netloc:\n"
        "            del redirect_request.headers['Cookie']\n"
        "    return redirect_request\n"
    )
    assert "SAST050" not in _scan_ids(src)


def test_TAN04_sast050_silent_without_url_keyword():
    src = (
        "def clone(self, request):\n"
        "    return request.replace(method='GET', body='')\n"
    )
    assert "SAST050" not in _scan_ids(src)


def test_TAN05_sast050_silent_on_unrelated_replace_call():
    src = (
        "def normalize(name):\n"
        "    return name.replace('_', '-')\n"
    )
    assert "SAST050" not in _scan_ids(src)


# ── SAST051 (flask CVE-2023-30861 shape) ────────────────────────────────────

def test_TAN10_sast051_fires_on_real_vulnerable_save_session_shape():
    src = (
        "def save_session(self, app, session, response):\n"
        "    name = self.get_cookie_name(app)\n"
        "    if not session:\n"
        "        if session.modified:\n"
        "            response.delete_cookie(name)\n"
        "        return\n"
        "    if session.accessed:\n"
        "        response.vary.add('Cookie')\n"
        "    if not self.should_set_cookie(app, session):\n"
        "        return\n"
        "    response.set_cookie(name, 'val')\n"
    )
    assert "SAST051" in _scan_ids(src)


def test_TAN11_sast051_silent_when_vary_added_before_first_return():
    src = (
        "def save_session(self, app, session, response):\n"
        "    name = self.get_cookie_name(app)\n"
        "    if session.accessed:\n"
        "        response.vary.add('Cookie')\n"
        "    if not session:\n"
        "        if session.modified:\n"
        "            response.delete_cookie(name)\n"
        "            response.vary.add('Cookie')\n"
        "        return\n"
        "    if not self.should_set_cookie(app, session):\n"
        "        return\n"
        "    response.set_cookie(name, 'val')\n"
        "    response.vary.add('Cookie')\n"
    )
    assert "SAST051" not in _scan_ids(src)


def test_TAN12_sast051_silent_without_any_vary_cookie_call():
    src = (
        "def save_session(self, app, session, response):\n"
        "    if not session:\n"
        "        return\n"
        "    response.set_cookie('name', 'val')\n"
    )
    assert "SAST051" not in _scan_ids(src)


def test_TAN13_sast051_silent_when_only_return_is_after_vary():
    src = (
        "def save_session(self, app, session, response):\n"
        "    response.vary.add('Cookie')\n"
        "    if not session:\n"
        "        return\n"
        "    response.set_cookie('name', 'val')\n"
        "    return\n"
    )
    assert "SAST051" not in _scan_ids(src)


def test_TAN14_sast051_silent_on_unrelated_vary_header():
    src = (
        "def save_session(self, app, session, response):\n"
        "    if not session:\n"
        "        return\n"
        "    response.vary.add('Accept-Encoding')\n"
    )
    assert "SAST051" not in _scan_ids(src)
