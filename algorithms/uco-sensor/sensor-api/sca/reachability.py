"""
UCO-Sensor — SCA Reachability (Nível 1: import-presence)  (M9.5)
================================================================
O SALTO da auditoria SCA/OSV (Sprint DV): hoje um finding de dependência
vulnerável é reportado SÓ por faixa de versão — sem checar se o pacote é
sequer *importado* no código. ~70-95% dos alertas de SCA puro-versão são ruído
por isso. Esta camada cruza cada finding com os imports REAIS do repositório e
emite um veredito de alcançabilidade estilo VEX:

  * ``imported``      — o pacote É importado no código → mantém prioridade.
  * ``not_imported``  — o pacote NÃO aparece em nenhum import → provavelmente
                        não-alcançável (``vulnerable_code_not_reachable``);
                        rebaixa confiança/severidade e anota.
  * ``unknown``       — sem fonte para analisar → não altera (honesto).

Nível 1 é *presença de import* — barato, alto valor, zero falso-rebaixamento
perigoso (só rebaixa quando o pacote comprovadamente não é importado). Nível 2
(alcançar a FUNÇÃO vulnerável via o call-graph do M17) fica para a próxima fase.

Puro e testável offline; nenhuma rede.
"""
from __future__ import annotations

import ast
import re
from typing import Dict, Iterable, List, Optional, Set

# Pacotes cujo NOME DE DISTRIBUIÇÃO difere do NOME DE IMPORT (os mais comuns).
# Sem isto, `PyYAML` (import `yaml`) seria marcado "not_imported" por engano.
_DIST_TO_IMPORT: Dict[str, Set[str]] = {
    "pyyaml": {"yaml"},
    "beautifulsoup4": {"bs4"},
    "pillow": {"pil"},
    "scikit-learn": {"sklearn"},
    "opencv-python": {"cv2"},
    "python-dateutil": {"dateutil"},
    "msgpack-python": {"msgpack"},
    "protobuf": {"google"},
    "setuptools": {"setuptools", "pkg_resources"},
    "attrs": {"attr", "attrs"},
    "typing-extensions": {"typing_extensions"},
}


def _canon_import(name: str) -> str:
    """Normaliza um nome de módulo/pacote para comparação (lower, '-'→'_')."""
    return name.strip().lower().replace("-", "_")


def import_names_for_package(pkg_name: str, ecosystem: str = "") -> Set[str]:
    """Nomes de import PLAUSÍVEIS para um pacote de dependência.

    Para a maioria dos pacotes o nome de import == nome de distribuição
    (normalizado). Alguns ecossistemas/pacotes divergem — tabela explícita.
    Para Maven (``group:artifact``) usa o último segmento do artifact.
    """
    p = _canon_import(pkg_name)
    names = {p}
    if p in _DIST_TO_IMPORT:
        names |= {_canon_import(x) for x in _DIST_TO_IMPORT[p]}
    # Maven: com.fasterxml.jackson.core:jackson-databind → {jackson_databind, databind}
    if ":" in pkg_name:
        artifact = pkg_name.split(":")[-1]
        names.add(_canon_import(artifact))
        if "-" in artifact:
            names.add(_canon_import(artifact.split("-")[-1]))
    return {n for n in names if n}


# ── extração de imports do código-fonte ──────────────────────────────────────

_JS_REQUIRE_RE = re.compile(r"""require\(\s*['"]([^'"]+)['"]\s*\)""")
_JS_IMPORT_RE = re.compile(r"""import\s+(?:[^'"]+\s+from\s+)?['"]([^'"]+)['"]""")
_GO_IMPORT_RE = re.compile(r"""['"]([a-zA-Z0-9_./\-]+)['"]""")


def _py_imports(source: str) -> Set[str]:
    out: Set[str] = set()
    try:
        tree = ast.parse(source)
    except SyntaxError:
        # fallback regex quando o arquivo não parseia (Py2, fragmento)
        for m in re.finditer(r"^\s*(?:import|from)\s+([a-zA-Z0-9_.]+)", source, re.MULTILINE):
            out.add(_canon_import(m.group(1).split(".")[0]))
        return out
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                out.add(_canon_import(a.name.split(".")[0]))
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.level == 0:      # ignora imports relativos
                out.add(_canon_import(node.module.split(".")[0]))
    return out


def _js_imports(source: str) -> Set[str]:
    out: Set[str] = set()
    for rx in (_JS_REQUIRE_RE, _JS_IMPORT_RE):
        for m in rx.finditer(source):
            mod = m.group(1)
            if mod.startswith("."):               # import relativo → não é dep
                continue
            # '@scope/pkg/sub' → '@scope/pkg'; 'pkg/sub' → 'pkg'
            if mod.startswith("@"):
                out.add(_canon_import("/".join(mod.split("/")[:2])))
            else:
                out.add(_canon_import(mod.split("/")[0]))
    return out


def extract_imported_modules(source_files: Dict[str, str]) -> Set[str]:
    """Conjunto de módulos importados no repo (Python + JS/TS), normalizados."""
    imported: Set[str] = set()
    for path, src in source_files.items():
        low = path.lower()
        if low.endswith(".py"):
            imported |= _py_imports(src)
        elif low.endswith((".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs")):
            imported |= _js_imports(src)
    return imported


# ── veredito ──────────────────────────────────────────────────────────────────

def reachability_verdict(pkg_name: str, ecosystem: str,
                         imported_modules: Optional[Set[str]]) -> str:
    """``imported`` | ``not_imported`` | ``unknown``.

    ``unknown`` quando não há fonte (imported_modules is None) — nunca rebaixa
    às cegas. Sem intersecção entre os nomes de import do pacote e os imports do
    repo → ``not_imported``.
    """
    if not imported_modules:            # None ou vazio (sem fonte analisável)
        return "unknown" if imported_modules is None else "not_imported"
    cand = import_names_for_package(pkg_name, ecosystem)
    return "imported" if (cand & imported_modules) else "not_imported"


def annotate_findings(findings: Iterable, source_files: Optional[Dict[str, str]]):
    """Anota cada finding SCA com alcançabilidade e REBAIXA os não-importados.

    Espera objetos com atributos `code_snippet`/`explanation`/`confidence`/
    `severity` (ex.: SASTFinding ou VulnerabilityFinding). Muta e devolve a lista.
    Rebaixamento (só quando ``not_imported`` com fonte real):
      * confiança × 0.4;
      * severidade CRITICAL/HIGH → MEDIUM (não-alcançável reduz exposição);
      * anexa veredito VEX ``vulnerable_code_not_reachable`` na explicação.
    """
    imported = extract_imported_modules(source_files) if source_files else None
    out = list(findings)
    for f in out:
        pkg = _pkg_name_of(f)
        eco = getattr(f, "ecosystem", "") or ""
        verdict = reachability_verdict(pkg, eco, imported)
        note = f" [reachability={verdict}]"
        if verdict == "not_imported":
            note += " VEX: vulnerable_code_not_reachable (pacote não importado no código analisado)."
            if hasattr(f, "confidence") and isinstance(f.confidence, (int, float)):
                f.confidence = round(float(f.confidence) * 0.4, 3)
            if getattr(f, "severity", "") in ("CRITICAL", "HIGH"):
                f.severity = "MEDIUM"
        if hasattr(f, "explanation"):
            f.explanation = (getattr(f, "explanation", "") or "") + note
        setattr(f, "reachability", verdict)
    return out


def _pkg_name_of(finding) -> str:
    """Extrai o nome do pacote de um finding (heurística tolerante)."""
    for attr in ("package", "package_name", "pkg_name", "name"):
        v = getattr(finding, attr, None)
        if isinstance(v, str) and v:
            return v
    # SASTFinding do OSV bridge: code_snippet = "<manifest>: pkg==ver" ou "pkg==ver"
    snip = getattr(finding, "code_snippet", "") or ""
    snip = snip.split(": ", 1)[-1]
    m = re.match(r"([A-Za-z0-9_.\-:@/]+)\s*[=<>@]", snip)
    return m.group(1) if m else ""


# ═══════════════════════════════════════════════════════════════════════════
# NÍVEL 2 — alcançar a FUNÇÃO vulnerável via o call-graph (Python)
# ═══════════════════════════════════════════════════════════════════════════
# Nível 1 responde "o pacote é importado?". Nível 2 responde a pergunta que o
# OSV-Scanner V2 gasta esforço enorme para responder: "um SÍMBOLO do pacote é de
# fato CHAMADO, e o site da chamada é ALCANÇÁVEL a partir de um ponto de entrada
# pelo grafo de chamadas?". Usa os mesmos primitivos do M17 (defs de função +
# arestas de chamada). Vereditos (do mais forte ao mais fraco):
#   reachable_vulnerable_symbol — o símbolo NOMEADO no advisory é chamado (alcançável)
#   reachable                   — algum símbolo do pacote é chamado num site alcançável
#   called_unreachable          — símbolo chamado só em função nunca invocada (dead)
#   imported_unused             — importado, mas nenhum símbolo é chamado/usado
#   not_imported                — nível 1
#   unknown                     — sem fonte Python analisável


class _ImportBinding:
    """Um nome local ligado a (pacote_raiz, símbolo|None). símbolo None = handle
    de módulo (uso via `nome.attr`)."""
    __slots__ = ("pkg", "symbol")

    def __init__(self, pkg: str, symbol: Optional[str]):
        self.pkg = pkg
        self.symbol = symbol


def _resolve_imports(tree: ast.AST) -> Dict[str, _ImportBinding]:
    """local_name → binding, para `import`/`import as`/`from ... import`."""
    binds: Dict[str, _ImportBinding] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                root = a.name.split(".")[0]
                local = (a.asname or a.name).split(".")[0]
                binds[local] = _ImportBinding(_canon_import(root), None)
        elif isinstance(node, ast.ImportFrom):
            if node.module is None or node.level != 0:
                continue                       # ignora relativos
            root = node.module.split(".")[0]
            for a in node.names:
                if a.name == "*":
                    continue
                local = a.asname or a.name
                binds[local] = _ImportBinding(_canon_import(root), a.name)
    return binds


def _call_symbol_for_package(call: ast.Call, binds: Dict[str, _ImportBinding],
                             pkg_names: Set[str]):
    """Se `call` invoca um símbolo de um pacote-alvo, devolve (pkg, symbol); senão None."""
    fn = call.func
    # `local.attr(...)` — local é handle de módulo do pacote → símbolo = attr
    if isinstance(fn, ast.Attribute):
        root = fn.value
        while isinstance(root, ast.Attribute):
            root = root.value
        if isinstance(root, ast.Name):
            b = binds.get(root.id)
            if b and b.symbol is None and b.pkg in pkg_names:
                return (b.pkg, fn.attr)
    # `local(...)` — local ligado via `from pkg import symbol`
    elif isinstance(fn, ast.Name):
        b = binds.get(fn.id)
        if b and b.symbol is not None and b.pkg in pkg_names:
            return (b.pkg, b.symbol)
    return None


def _enclosing_funcs(tree: ast.AST) -> Dict[int, Optional[str]]:
    """Mapa id(node)→nome-da-função-que-o-contém (None = nível de módulo)."""
    owner: Dict[int, Optional[str]] = {}

    def walk(node, current):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                owner[id(child)] = current
                walk(child, child.name)
            else:
                owner[id(child)] = current
                walk(child, current)
    walk(tree, None)
    return owner


def analyze_symbol_reachability(source_files: Dict[str, str],
                                pkg_import_names: Set[str],
                                vuln_symbols: Optional[Set[str]] = None) -> str:
    """Veredito de nível 2 para um pacote (ver docstring de seção).

    `pkg_import_names` — nomes de import canônicos do pacote (de
    `import_names_for_package`). `vuln_symbols` — símbolos nomeados pelo advisory
    (ex.: {"get","request"}), opcional.
    """
    py = {p: s for p, s in (source_files or {}).items() if p.lower().endswith(".py")}
    if not py:
        return "unknown"

    imported_anywhere = False
    # arestas de chamada agregadas entre funções de usuário (nome→nomes chamados)
    call_edges: Dict[str, Set[str]] = {}
    module_called: Set[str] = set()          # funções chamadas em nível de módulo
    all_func_names: Set[str] = set()
    # sites de chamada de símbolo do pacote: lista de (owner_func|None, symbol)
    symbol_sites: List = []

    # Pass 1 — parse cada arquivo, resolve imports/owners e ACUMULA o conjunto
    # GLOBAL de nomes de função (cross-file: `f` def em a.py, chamada em b.py).
    parsed: List = []
    for _path, src in py.items():
        try:
            tree = ast.parse(src)
        except SyntaxError:
            continue
        binds = _resolve_imports(tree)
        if any(b.pkg in pkg_import_names for b in binds.values()):
            imported_anywhere = True
        owner = _enclosing_funcs(tree)
        all_func_names |= {n.name for n in ast.walk(tree)
                           if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
        parsed.append((tree, binds, owner))

    # Pass 2 — arestas de chamada e sites de símbolo, usando o conjunto GLOBAL.
    for tree, binds, owner in parsed:
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            own = owner.get(id(node))
            callee = _call_user_fn_name_local(node)
            if callee and callee in all_func_names:
                call_edges.setdefault(own or "<module>", set()).add(callee)
                if own is None:
                    module_called.add(callee)
            hit = _call_symbol_for_package(node, binds, pkg_import_names)
            if hit:
                symbol_sites.append((own, hit[1]))

    if not imported_anywhere:
        return "not_imported"
    if not symbol_sites:
        return "imported_unused"

    # reachability: fecho a partir do nível de módulo
    reachable = set(module_called)
    frontier = list(module_called)
    while frontier:
        cur = frontier.pop()
        for nxt in call_edges.get(cur, ()):  # noqa: B007
            if nxt not in reachable:
                reachable.add(nxt)
                frontier.append(nxt)

    def _site_reachable(owner_fn) -> bool:
        return owner_fn is None or owner_fn in reachable

    vs = {s.lower() for s in (vuln_symbols or set())}
    any_reachable = False
    for owner_fn, sym in symbol_sites:
        if _site_reachable(owner_fn):
            any_reachable = True
            if vs and sym.lower() in vs:
                return "reachable_vulnerable_symbol"
    if any_reachable:
        return "reachable"
    return "called_unreachable"


def _call_user_fn_name_local(call: ast.Call) -> Optional[str]:
    """Cópia local do resolvedor de nome-de-chamada do M17 (evita dep de import)."""
    if isinstance(call.func, ast.Name):
        return call.func.id
    if isinstance(call.func, ast.Attribute):
        return call.func.attr
    return None


# tiers de rebaixamento por veredito (fator de confiança, rebaixa severidade?)
_V2_DOWNGRADE = {
    "not_imported":      (0.4, True),
    "imported_unused":   (0.4, True),
    "called_unreachable": (0.7, False),   # incerto (fileset pode ser parcial) → brando
}
_V2_NOTE = {
    "not_imported":       "pacote não importado",
    "imported_unused":    "importado mas nenhum símbolo é chamado (import morto)",
    "called_unreachable": "símbolo chamado só em função aparentemente não-invocada",
    "reachable":          "símbolo do pacote é chamado em site alcançável",
    "reachable_vulnerable_symbol": "SÍMBOLO VULNERÁVEL do advisory é chamado (alcançável)",
}


def annotate_findings_v2(findings: Iterable, source_files: Optional[Dict[str, str]],
                         vuln_symbols_map: Optional[Dict[str, Set[str]]] = None):
    """Nível 2: anota/rebaixa por alcançabilidade de SÍMBOLO via call-graph.

    `vuln_symbols_map` — {cve_id: {símbolos vulneráveis}} do advisory (opcional).
    Rebaixa `not_imported`/`imported_unused` (forte) e `called_unreachable`
    (brando); mantém `reachable`; dá BOOST de confiança a
    `reachable_vulnerable_symbol`. Sem fonte → `unknown`, nunca rebaixa.
    """
    out = list(findings)
    for f in out:
        pkg = _pkg_name_of(f)
        eco = getattr(f, "ecosystem", "") or ""
        cve = _cve_of_finding(f)
        vuln_syms = (vuln_symbols_map or {}).get(cve) if vuln_symbols_map else None
        if source_files:
            verdict = analyze_symbol_reachability(
                source_files, import_names_for_package(pkg, eco), vuln_syms)
        else:
            verdict = "unknown"
        note = f" [reachability2={verdict}: {_V2_NOTE.get(verdict, verdict)}]"
        if verdict in _V2_DOWNGRADE:
            factor, drop_sev = _V2_DOWNGRADE[verdict]
            note = " VEX: vulnerable_code_not_reachable —" + note
            if hasattr(f, "confidence") and isinstance(f.confidence, (int, float)):
                f.confidence = round(float(f.confidence) * factor, 3)
            if drop_sev and getattr(f, "severity", "") in ("CRITICAL", "HIGH"):
                f.severity = "MEDIUM"
        elif verdict == "reachable_vulnerable_symbol":
            if hasattr(f, "confidence") and isinstance(f.confidence, (int, float)):
                f.confidence = round(min(0.99, float(f.confidence) * 1.05), 3)
        if hasattr(f, "explanation"):
            f.explanation = (getattr(f, "explanation", "") or "") + note
        setattr(f, "reachability2", verdict)
    return out


def _cve_of_finding(finding) -> str:
    for attr in ("cve_id", "cve", "rule_id", "title", "explanation"):
        v = getattr(finding, attr, "") or ""
        m = re.search(r"CVE-\d{4}-\d{4,}", str(v), re.IGNORECASE)
        if m:
            return m.group(0).upper()
    return ""
