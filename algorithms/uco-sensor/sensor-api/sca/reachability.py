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
