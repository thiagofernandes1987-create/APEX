"""
UCO-Sensor — Multi-Language Taint-Lite  (M20)
==============================================
META B (restante): estende a detecção de injeção sem-âncora para as
linguagens web do corpus que o `TaintAnalyzer` (AST-Python) não cobre —
**PHP e JavaScript/TypeScript** — sem um port de AST completo.

Abordagem (leve, FP-controlada):
  * fontes e sinks por linguagem (regex de padrão canônico);
  * **fluxo por escopo de função**: reusa `scope.function_spans` (M14, AST
    tree-sitter) para delimitar cada função; dentro do escopo, se uma
    variável recebe uma FONTE e depois é passada a um SINK, é um caminho
    fonte→sink.  Exige a MESMA variável nos dois lados (corta FP de
    "tem fonte e tem sink soltos").
  * fonte→sink DIRETO (sink(source())) também conta.

Não substitui o taint AST do Python (mais preciso); complementa para
PHP/JS onde antes havia zero cobertura.

API
---
    findings = TaintLite().scan(source, ".php")   -> list[LiteFlow]
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

try:
    from .scope import FunctionScoper           # M14
except Exception:  # pragma: no cover
    FunctionScoper = None  # type: ignore


@dataclass(frozen=True)
class LiteFlow:
    rule_id: str
    severity: str
    cwe_id: str
    vuln_type: str
    source_line: int
    sink_line: int
    var: str
    snippet: str


# ── Fontes e sinks por linguagem ──────────────────────────────────────────────
# Cada entrada: regex com um grupo capturando a VARIÁVEL (quando aplicável).
_LANG: Dict[str, Dict[str, object]] = {
    "php": {
        "source": re.compile(r"(\$\w+)\s*=\s*.*\$_(?:GET|POST|REQUEST|COOKIE|SERVER|FILES)\b"),
        "source_expr": re.compile(r"\$_(?:GET|POST|REQUEST|COOKIE|FILES)\b"),
        "sinks": {
            "system": ("SAST041", "CRITICAL", "COMMAND_INJECTION", "CWE-78"),
            "exec": ("SAST041", "CRITICAL", "COMMAND_INJECTION", "CWE-78"),
            "shell_exec": ("SAST041", "CRITICAL", "COMMAND_INJECTION", "CWE-78"),
            "passthru": ("SAST041", "CRITICAL", "COMMAND_INJECTION", "CWE-78"),
            "popen": ("SAST041", "CRITICAL", "COMMAND_INJECTION", "CWE-78"),
            "eval": ("SAST043", "CRITICAL", "CODE_INJECTION", "CWE-95"),
            "assert": ("SAST043", "HIGH", "CODE_INJECTION", "CWE-95"),
            "unserialize": ("SAST046", "CRITICAL", "UNSAFE_DESERIALIZATION", "CWE-502"),
            "include": ("SAST044", "HIGH", "FILE_INCLUSION", "CWE-98"),
            "require": ("SAST044", "HIGH", "FILE_INCLUSION", "CWE-98"),
            "mysqli_query": ("SAST040", "CRITICAL", "SQL_INJECTION", "CWE-89"),
            "mysql_query": ("SAST040", "CRITICAL", "SQL_INJECTION", "CWE-89"),
        },
    },
    "javascript": {
        "source": re.compile(
            r"(?:let|var|const)\s+(\w+)\s*=\s*.*\b(?:req|request)\.(?:query|body|params|cookies|headers)\b"
            r"|(\w+)\s*=\s*.*\blocation\.(?:search|hash|href)\b"
        ),
        "source_expr": re.compile(r"\b(?:req|request)\.(?:query|body|params|cookies|headers)\b|\blocation\.(?:search|hash|href)\b"),
        "sinks": {
            "eval": ("SAST043", "CRITICAL", "CODE_INJECTION", "CWE-95"),
            "exec": ("SAST041", "CRITICAL", "COMMAND_INJECTION", "CWE-78"),
            "execSync": ("SAST041", "CRITICAL", "COMMAND_INJECTION", "CWE-78"),
            "Function": ("SAST043", "HIGH", "CODE_INJECTION", "CWE-95"),
        },
    },
}
_EXT_LANG = {
    ".php": "php", ".phtml": "php", ".php3": "php", ".php4": "php", ".php5": "php",
    ".js": "javascript", ".jsx": "javascript", ".mjs": "javascript", ".cjs": "javascript",
    ".ts": "javascript", ".tsx": "javascript",
}


class TaintLite:
    def __init__(self) -> None:
        self._scoper = FunctionScoper() if FunctionScoper is not None else None

    def scan(self, source: str, ext: str = "") -> List[LiteFlow]:
        lang = _EXT_LANG.get(ext.lower())
        if lang is None:
            return []
        cfg = _LANG[lang]
        lines = source.splitlines()
        spans = self._spans(source, ext, len(lines))

        out: List[LiteFlow] = []
        seen = set()
        for (s, e) in spans:
            block = lines[s - 1:e]
            tainted: Dict[str, int] = {}       # var -> source_line
            for off, ln in enumerate(block):
                lineno = s + off
                # fonte com atribuição a variável
                m = cfg["source"].search(ln)   # type: ignore
                if m:
                    var = next((g for g in m.groups() if g), None)
                    if var:
                        tainted[var] = lineno
                # sink: função de risco recebendo uma var tainted OU a fonte direta
                for sink, meta in cfg["sinks"].items():   # type: ignore
                    call = re.search(rf"\b{re.escape(sink)}\s*\(([^)]*)\)", ln)
                    if not call:
                        continue
                    args = call.group(1)
                    # arg direto da fonte  ex.: system($_GET['x'])
                    direct = cfg["source_expr"].search(args)   # type: ignore
                    hit_var = None
                    for var, sline in tainted.items():
                        if re.search(rf"(?<![\w${{}}]){re.escape(var)}\b", args):
                            hit_var = var
                            break
                    if hit_var or direct:
                        key = (sink, lineno, hit_var or "<direct>")
                        if key in seen:
                            continue
                        seen.add(key)
                        rid, sev, vt, cwe = meta  # type: ignore
                        out.append(LiteFlow(
                            rule_id=rid, severity=sev, cwe_id=cwe, vuln_type=vt,
                            source_line=tainted.get(hit_var, lineno) if hit_var else lineno,
                            sink_line=lineno, var=hit_var or "<direct>",
                            snippet=ln.strip()[:160]))
        out.sort(key=lambda f: (f.sink_line, f.rule_id))
        return out

    def _spans(self, source: str, ext: str, nlines: int) -> List[Tuple[int, int]]:
        if self._scoper is not None:
            try:
                sp = self._scoper.function_spans(source, ext)
                if sp:
                    return sp
            except Exception:
                pass
        return [(1, nlines)]   # fallback: arquivo inteiro como um escopo
