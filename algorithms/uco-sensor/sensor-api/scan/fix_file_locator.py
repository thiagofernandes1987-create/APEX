"""
UCO-Sensor — Fix File Locator & Auto-Pair Builder  (M27)
=========================================================
Fecha o último gargalo da AUTOMAÇÃO do corpus: identificar, sem a API de commits
(403), QUAL arquivo-fonte o commit de fix alterou e montar o par before/after por
tag — para a esteira M23/M25→M24 responder as 4 perguntas SEM conhecimento manual
por CVE.

Os três passos automatizáveis (canais provados nesta sessão)
------------------------------------------------------------
1. `pick_source_file(changed_files)` — dada a LISTA de arquivos do commit de fix
   (obtida fora do módulo — ex.: WebFetch da página do commit, que o harness LÊ),
   escolhe o arquivo-fonte mais provável (descarta testes/docs/CI; prioriza
   extensão de código e menor profundidade).
2. `prior_version(fixed)` — deriva a versão ANTERIOR (vulnerável) decrementando o
   componente de patch/minor (3.1.3→3.1.2, 2.31.0→2.30.0, 2.2.3→2.2.2), para
   buscar o lado "vuln" por tag.  Heurística validada nos 5 CVEs PyPI reais.
3. `tag_candidates(version)` — tags candidatas ("v"+version e version), pois os
   repos divergem (jinja usa "3.1.3", requests usa "v2.31.0").

`build_pair(...)` orquestra tudo com fetchers INJETÁVEIS (`commit_files_fn`,
`raw_fetch_fn`) — testável offline e desacoplado da rede.  Em produção os
fetchers batem no GitHub; neste ambiente o `commit_files_fn` usa WebFetch e o
`raw_fetch_fn` usa raw.githubusercontent.

Versão: introduzido em v3.63.0 (Sprint CN).
"""
from __future__ import annotations

import re
from typing import Callable, List, Optional, Tuple

# extensões de código-fonte que nos interessam (o scanner cobre estas).
_CODE_EXTS = (".py", ".c", ".h", ".cc", ".cpp", ".cxx", ".js", ".ts", ".jsx",
              ".tsx", ".go", ".java", ".rb", ".php", ".rs", ".kt", ".cs")
# caminhos a descartar na escolha do arquivo-fonte (ruído p/ localização de fix).
_SKIP_RE = re.compile(
    r"(^|/)(tests?|test|docs?|examples?|benchmarks?|\.github|ci)/|"
    r"(^|/)(changes|changelog|changes\.rst|news)\b|"
    r"\.(md|rst|txt|cfg|ini|toml|yaml|yml|json|lock)$", re.I)
_VER_RE = re.compile(r"^(\d+)\.(\d+)(?:\.(\d+))?(.*)$")


def pick_source_file(changed_files: List[str]) -> Optional[str]:
    """
    Escolhe o arquivo-fonte mais provável dentre os alterados pelo fix.
    Prioriza: extensão de código > não-teste/doc > menor profundidade de path.
    Retorna o caminho ou None se nada plausível.
    """
    cands = [f.strip() for f in (changed_files or []) if f and f.strip()]
    # 1º passe: código-fonte que NÃO é teste/doc; senão qualquer código-fonte.
    # Se NÃO houver código-fonte, devolve None (nunca escolhe doc/changelog como
    # "arquivo do fix" — isso levaria o M10 a não localizar nada, corretamente).
    primary = [f for f in cands
               if f.lower().endswith(_CODE_EXTS) and not _SKIP_RE.search(f)]
    pool = primary or [f for f in cands if f.lower().endswith(_CODE_EXTS)]
    if not pool:
        return None
    # menor profundidade (arquivos de topo do pacote costumam ser o alvo), depois
    # ordem alfabética para determinismo.
    pool.sort(key=lambda f: (f.count("/"), f))
    return pool[0]


def prior_version(fixed: str) -> str:
    """
    Deriva a versão anterior à corrigida (o lado vulnerável) decrementando o
    último componente não-zero.  Ex.: 3.1.3→3.1.2, 2.31.0→2.30.0, 1.0.0→0.x?
    Se o patch>0: patch-1.  Senão se minor>0: minor-1 (patch fica alto? não —
    devolvemos minor-1 com patch 0, o par ainda é o release imediatamente
    anterior na prática dos repos).  Devolve "" se não há anterior derivável.
    """
    m = _VER_RE.match((fixed or "").strip())
    if not m:
        return ""
    major, minor = int(m.group(1)), int(m.group(2))
    patch = int(m.group(3)) if m.group(3) is not None else 0
    has_patch = m.group(3) is not None
    if patch > 0:
        return f"{major}.{minor}.{patch - 1}" if has_patch else f"{major}.{minor - 1}"
    if minor > 0:
        # x.minor.0 → x.(minor-1).0  (release minor anterior; mantém o .0 p/ casar
        # a tag real, ex.: requests 2.31.0 → 2.30.0).
        return f"{major}.{minor - 1}.0" if has_patch else f"{major}.{minor - 1}"
    if major > 0:
        return f"{major - 1}.0"
    return ""


def tag_candidates(version: str) -> List[str]:
    """Tags candidatas para uma versão (repos divergem no prefixo 'v')."""
    v = (version or "").strip()
    if not v:
        return []
    return [v, f"v{v}"]


def build_pair(
    repo: str,
    fixed_version: str,
    fix_commit: str,
    source_file: str,
    raw_fetch_fn: Callable[[str, str, str], Optional[str]],
    prior_version_hint: str = "",
) -> Optional[Tuple[str, str, str]]:
    """
    Monta o par (vuln_src, fixed_src, filename) buscando `source_file` na tag
    corrigida e na anterior.  `raw_fetch_fn(repo, ref, path) -> conteúdo|None`
    é injetável (raw.githubusercontent em produção).  Tenta tags com/sem 'v'.
    Retorna None se não conseguir os dois lados.
    """
    prior = prior_version_hint or prior_version(fixed_version)
    if not prior or not source_file:
        return None

    # tags candidatas incluem o prefixo do NOME do repo (alguns projetos usam
    # `<nome>-<versão>`, ex.: lxml → `lxml-4.6.5`), além de `X` e `vX`.
    repo_name = repo.rsplit("/", 1)[-1]
    def _cands(v: str) -> List[str]:
        return tag_candidates(v) + ([f"{repo_name}-{v}"] if v else [])

    fixed_src = _first_ok(raw_fetch_fn, repo, _cands(fixed_version), source_file)
    if fixed_src is None:
        return None
    vuln_src = _first_ok(raw_fetch_fn, repo, _cands(prior), source_file)
    if vuln_src is None:
        return None
    filename = source_file.rsplit("/", 1)[-1]
    return (vuln_src, fixed_src, filename)


def _first_ok(raw_fetch_fn, repo: str, refs: List[str], path: str) -> Optional[str]:
    """Primeira ref que devolve conteúdo não-vazio."""
    for ref in refs:
        try:
            data = raw_fetch_fn(repo, ref, path)
        except Exception:  # noqa: BLE001 — fetch é best-effort
            data = None
        if data:
            return data
    return None
