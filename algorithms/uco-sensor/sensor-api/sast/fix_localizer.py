"""
UCO-Sensor — Fix-Diff Vulnerability Localizer  (M10)
=====================================================
Given the *vulnerable* and *fixed* revisions of a file (the before/after of
a known CVE fix commit), this module answers the questions the corpus
validation asks of every repository:

    * **where** did the bug live  → file + exact line(s) the fix touched
    * **how** was it fixed        → the security construct the fix ADDED
                                     (bounds check, null-guard, type widening,
                                     signedness fix, added `if`, …)
    * **what class**              → inferred CWE-ish class from the construct
    * **validation**              → is that guard PRESENT in the fixed revision
                                     and ABSENT in the vulnerable one?
                                     (i.e. did the tool's evidence line up with
                                     the real fix, and would a re-scan of the
                                     fixed file no longer show the missing guard)

Why a diff-anchored approach
----------------------------
Sprint BG established empirically that the sensor's pattern SAST does **not**
fire on the memory-safety CVE classes (integer-underflow, OOB, use-after-free)
— it reports rating A on the vulnerable file, or fires a generic rule that
*persists identically* across the fix, so it cannot tell "fired before /
stopped after".  The honest, real-data way to localize a *known* CVE is to
anchor on its fix commit: the diff itself is ground truth for where/how the
bug was, and comparing the guard's presence across the two revisions is a
faithful before/after validation with zero fabrication.

This does NOT claim to detect unknown bugs — that is the pattern/taint
engines' job (tracked separately).  It makes the *known-CVE corpus
validation* precise and localized instead of a coarse "something changed".

Public API
----------
    loc = FixDiffLocalizer()
    res = loc.localize(vuln_src, fixed_src, filename="mm/gup.c")
    res.added_guards        -> list[GuardHit]  (line, text, kind)
    res.vuln_classes        -> set[str]
    res.guard_present_in_fix_absent_in_vuln -> bool   (the validation)
    res.summary()           -> one-line human summary
"""
from __future__ import annotations

import difflib
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import List, Optional, Set, Tuple

# Security-relevant construct signatures.  Each mapeia um regex (casado numa
# linha ADICIONADA pelo fix) a (kind, cwe_class).  Ordem: mais-específico
# primeiro.  Dois grupos:
#   • memory-safety (C/C++/Rust) — bounds/null/widening/overflow/copy;
#   • injeção/escaping (Python/JS/PHP/Java) — sanitização e validação de
#     entrada.  (CB v3.51.0: adicionado o 2º grupo para o M10 localizar fixes
#     de XSS/injeção/SSTI, não só memory-safety.  Ex.: jinja CVE-2024-22195
#     adiciona `escape(key)` + `raise ValueError` para chave com espaço.)
_GUARD_SIGNATURES: List[Tuple["re.Pattern[str]", str, str]] = [
    # ── memory-safety ────────────────────────────────────────────────────────
    (re.compile(r"\b(\w+)\s*[><]=?\s*(\w+).*\?"), "bounds-check-ternary", "CWE-190/125"),
    (re.compile(r"\bif\s*\([^)]*\b(len|size|count|n|idx|index|off|offset|pos)\b[^)]*[<>]"), "bounds-check-if", "CWE-125/787"),
    (re.compile(r"[!=]=\s*NULL|NULL\s*[!=]=|\b(\w+)\s*&&"), "null-guard", "CWE-476"),
    (re.compile(r"\b(uint32_t|uint64_t|size_t|int64_t|long long)\b"), "type-widening", "CWE-190"),
    (re.compile(r"\bunsafe\b"), "unsafe-contract", "RUST-soundness"),
    (re.compile(r"\b(overflow|underflow|bounds?|clamp|saturat)\w*\b", re.I), "overflow-guard", "CWE-190"),
    # chamada a um helper de verificação de limites/overflow — inclusive em
    # CamelCase (`ArrayCheckBounds(...)`), que a regra overflow-guard acima
    # PERDE porque o seu `\b` não casa "Bounds" embutido no meio do identificador.
    # Esta casa a FORMA-DE-CHAMADA independentemente de caixa; baixo-FP porque
    # exige verbo (check/valid/verif/guard) adjacente ao substantivo
    # (bound/overflow/range/limit) + parêntese de chamada.  Onde entra: `_classify`
    # a testa em cada linha ADICIONADA pelo fix.  (CE v3.54.0 — destrava
    # postgres CVE-2021-32027, cujo fix insere `ArrayCheckBounds()` em 8 sites.)
    (re.compile(r"(?i)\b\w*(?:check\w*(?:bound|overflow|range|limit)|"
                r"(?:bound|overflow|range|limit)\w*check|"
                r"(?:valid|verif|guard|assert)\w*(?:bound|overflow|range|limit))"
                r"\w*\s*\("),
     "bounds-check-call", "CWE-190/125"),
    (re.compile(r"\b(memcpy|memmove|strncpy|snprintf)\b"), "safe-copy", "CWE-120"),
    # ── injeção / escaping / validação de entrada (CB) ───────────────────────
    # output-encoding: escapar antes de emitir → XSS/SSTI/log/command injection.
    (re.compile(r"\b(escape|escapejs|html\.escape|html_escape|markupsafe|escape_html|"
                r"shlex\.quote|pipes\.quote|urllib\.parse\.quote|quote_plus|"
                r"escape_string|real_escape|htmlspecialchars|encodeURIComponent)\s*\("),
     "output-encoding", "CWE-79/116/78"),
    # (CX) hardening de parser XML contra XXE (CWE-611): desabilitar resolução
    # de entidades / rede externa / usar defusedxml.  Baixo-FP: idiomas
    # específicos de segurança XML.  Ex.: fonttools CVE-2023-45139 adiciona
    # `resolve_entities=False` no XMLParser do subset SVG.
    (re.compile(r"resolve_entities\s*=\s*False|\bno_network\s*=\s*True|"
                r"\bdefusedxml\b|forbid_(?:dtd|entities|external)|"
                r"\bXMLParser\([^)]*resolve_entities"),
     "xxe-hardening", "CWE-611"),
    # validação de entrada que aborta (raise/return) em valor perigoso.
    # (DD) +Invalid\w* (ex.: `raise InvalidHeader` do gunicorn CVE-2024-1135) —
    # `raise Invalid...` é sempre validação de entrada (baixo-FP).
    (re.compile(r"\braise\s+(?:\w*(?:Error|Exception|TooLarge|Denied|Forbidden)|(?:Invalid|Bad)\w*)\b"), "input-validation-raise", "CWE-20"),
    (re.compile(r"\breturn\b.*\b(EINVAL|ERANGE|-1|error|Err)\b", re.I), "early-return-guard", "CWE-20"),
    # (DB) terminação de laço contra loop infinito (CWE-835): o fix adiciona um
    # terminador vazio/EOF (`b""`/`""`) a uma condição `while ... not in (...)`.
    # Ex.: pypdf CVE-2023-36464 — `while peek not in (b"\r", b"\n")` vira
    # `... (b"\r", b"\n", b"")` (para no EOF).  Baixo-FP: while+not-in+literal-vazio.
    (re.compile(r"\bwhile\b.*\bnot\s+in\b.*b?['\"]['\"]"), "loop-termination-guard", "CWE-835"),
    # guard condicional de SEGURANÇA (Python/JS/PHP usam `and`/`or`, não `&&`):
    # um `if`/condição numa linha ADICIONADA que referencia um termo sensível
    # (scheme/https/auth/senha/token/permissão/origem…).  Baixo-FP porque exige
    # o termo de segurança + ser adição do fix.  (CC v3.52.0 — ex.: requests
    # CVE-2023-32681 adiciona `if not scheme.startswith('https') and username
    # and password:` para não vazar Proxy-Authorization em http.)
    # (CU) `redirect`→`redirect\w*` (casa `redirect_request_netloc`) + netloc/
    # domain/host adicionados: destrava scrapy CVE-2022-0577 (dropa Cookie em
    # redirect cross-domain comparando netloc).  O `\bredirect\b` antigo perdia
    # `redirect_request` porque `_` é word-char (sem fronteira).
    # (CX) `\w*trust\w*` casa `check_host_trust`/`trusted_hosts`/`host_is_trusted`
    # (host/trust embutidos em snake_case, que `\bhost\b` perdia): destrava
    # werkzeug CVE-2024-34069 (debugger valida Host contra trusted_hosts).
    (re.compile(r"\b(if|elif|while|assert|and|or|unless)\b.*\b(https?|scheme|"
                r"auth\w*|authoriz\w*|password|passwd|token|secret|credential|"
                r"cred|permission|allow\w*|is_safe|verif\w*|valid\w*|sanitiz\w*|"
                r"escap\w*|origin|csrf|referer|hostname|host|redirect\w*|"
                r"netloc|domain|\w*trust\w*)\b", re.I),
     "security-conditional-guard", "CWE-287/863/200"),
    # limite de recurso contra DoS/exaustão (CWE-400): max_* de partes/tamanho/
    # profundidade, ou exceções de limite excedido.  (CC — ex.: werkzeug
    # CVE-2023-25577 introduz `max_form_parts` → RequestEntityTooLarge.)
    (re.compile(r"\b(max_\w*(parts|size|count|length|len|depth|iter\w*|form)|"
                r"RequestEntityTooLarge|LimitExceeded|too_large|recursion_limit)\b", re.I),
     "resource-limit", "CWE-400"),
    # guard de cache-poisoning: adicionar `Vary: Cookie` (ou vary.add("Cookie"))
    # sinaliza ao cache que a resposta depende do cookie — impede que uma resposta
    # com sessão vaze para outro usuário.  Baixo-FP: exige `vary` + (`.add(` ou
    # `cookie`).  (CN v3.63.0 — ex.: Flask CVE-2023-30861, CWE-525/539.)
    (re.compile(r"\bvary\b[^\n]*(?:\.add\s*\(|cookie)", re.I),
     "cache-vary-guard", "CWE-525/539"),
    # guard de path-traversal (CWE-22): confinar um caminho normalizado à raiz.
    # `.relative_to(root)` / `.is_relative_to(root)` levantam/testam se o caminho
    # escapou do diretório; `os.path.commonpath([...])` idem.  Baixo-FP: são APIs
    # específicas de caminho.  (CO v3.64.0 — ex.: aiohttp CVE-2024-23334, cujo fix
    # adiciona `normalized_path.relative_to(self._directory)`.)
    # (DE) +os.path.commonprefix: idioma de contenção usado p/ barrar traversal
    # (ex.: streamlit CVE-2022-35918 — `commonprefix([root, abspath]) != root`).
    # (DI) +os.path.samefile: contenção comparando o dir resolvido com a base
    # (pymdown-extensions CVE-2023-32309 — `samefile(base, dirname(abspath))`).
    (re.compile(r"\.\s*(?:is_relative_to|relative_to)\s*\(|"
                r"\bos\.path\.(?:common(?:path|prefix)|samefile)\s*\("),
     "path-containment-guard", "CWE-22"),
]

# Conjunto de tokens que marca uma linha como "candidata a guard" (evita
# contar edições só de comentário/formatação).  (CB: +escape/raise/quote para
# habilitar o grupo de injeção/escaping.)
_SECURITY_TOKENS = re.compile(
    r"[<>]=?|[!=]=|&&|\|\||\bNULL\b|\bif\b|\belif\b|\bwhile\b|\bassert\b|"
    r"\breturn\b|\band\b|\bor\b|\buint\d+_t\b|\bsize_t\b|\bunsafe\b|"
    r"\bescape\w*\(|\braise\b|\bquote\w*\(|htmlspecialchars|encodeURI|max_\w+|"
    # (CX) idiomas de hardening XXE — passam o gate mesmo sem `==`/`<>`.
    r"resolve_entities|no_network|defusedxml|XMLParser|forbid_(?:dtd|entities)|"
    r"\bvary\b|"  # (CN) habilita cache-vary-guard (ex.: response.vary.add("Cookie"))
    r"relative_to\s*\(|common(?:path|prefix)\s*\(|"  # (CO/DE) habilita path-containment-guard
    # (CE v3.54.0) chamada a helper de bounds/overflow-check em CamelCase ou
    # snake_case — habilita o gate para a assinatura `bounds-check-call` (a
    # linha `ArrayCheckBounds(...)` não tem if/return/<>, então sem este token
    # seria descartada antes de chegar ao _classify).
    r"(?i:\w*(?:check\w*(?:bound|overflow|range|limit)|"
    r"(?:bound|overflow|range|limit)\w*check|"
    r"(?:valid|verif|guard)\w*(?:bound|overflow|range|limit))\w*\s*\()",
)


@dataclass(frozen=True)
class GuardHit:
    """One security-relevant line the fix added."""
    line: int          # 1-based line number in the FIXED revision
    text: str
    kind: str
    cwe_class: str


@dataclass
class LocalizeResult:
    filename: str
    added_guards: List[GuardHit] = field(default_factory=list)
    removed_security_lines: List[str] = field(default_factory=list)
    added_lines: int = 0
    removed_lines: int = 0

    @property
    def vuln_classes(self) -> Set[str]:
        return {g.cwe_class for g in self.added_guards}

    @property
    def guard_present_in_fix_absent_in_vuln(self) -> bool:
        """
        The core validation: the fix ADDED at least one security guard that
        was not present in the vulnerable revision.  True ⇒ the before/after
        evidence is consistent with a real security fix and a re-scan of the
        fixed file would find the guard the vulnerable one lacked.
        """
        return len(self.added_guards) > 0

    @property
    def first_guard(self) -> Optional[GuardHit]:
        return self.added_guards[0] if self.added_guards else None

    def summary(self) -> str:
        if not self.added_guards:
            return f"{self.filename}: nenhum guard de segurança adicionado detectado no diff (+{self.added_lines}/-{self.removed_lines})"
        g = self.added_guards[0]
        classes = ",".join(sorted(self.vuln_classes))
        return (f"{self.filename}: fix adicionou {len(self.added_guards)} guard(s) "
                f"[{classes}] — 1º em L{g.line} ({g.kind}): {g.text.strip()[:70]}")


class FixDiffLocalizer:
    """Localizes a known-CVE fix by diffing the vulnerable vs fixed source."""

    def localize(self, vuln_src: str, fixed_src: str, filename: str = "") -> LocalizeResult:
        vuln_lines = vuln_src.splitlines()
        fixed_lines = fixed_src.splitlines()
        sm = difflib.SequenceMatcher(a=vuln_lines, b=fixed_lines, autojunk=False)

        # Anti-relocação POR CONTAGEM (não por presença).  Quando o fix insere
        # linhas acima, o difflib desloca a numeração e reporta uma linha
        # idêntica como "insert".  Distinguir relocação de adição real:
        #   • relocação preserva a CONTAGEM daquela linha (vuln==fix);
        #   • adição genuína INCREMENTA a contagem (fix > vuln).
        # Comparar por presença global (o conjunto antigo) descartava um guard
        # legítimo sempre que seu texto — tipicamente um idioma comum como
        # `return AVERROR(EINVAL);` — também aparecesse em qualquer outro ponto
        # do arquivo.  (CE v3.54.0: corrige o FN do ffmpeg CVE-2020-22015, cujo
        # `return AVERROR(EINVAL);` do fix era descartado por existir 22× no
        # arquivo [vuln] → 23× [fix]; AINDA preserva o anti-FP do sqlite
        # CVE-2019-19646, cujo clamp relocado mantém contagem constante 1→1.)
        vuln_counts = Counter(ln.strip() for ln in vuln_lines if ln.strip())
        fixed_counts = Counter(ln.strip() for ln in fixed_lines if ln.strip())

        res = LocalizeResult(filename=filename)
        # Acumuladores p/ análise DIFF-level (não só linha-a-linha): o fix de
        # ReDoS caracteriza-se por REMOVER uma regex vulnerável e ADICIONAR
        # parsing por string — só visível olhando removidas + adicionadas juntas.
        added_all: List[Tuple[int, str]] = []
        removed_all: List[str] = []
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag in ("replace", "insert"):
                # added lines are fixed_lines[j1:j2], 1-based line numbers j+1
                for off, text in enumerate(fixed_lines[j1:j2]):
                    lineno = j1 + off + 1
                    res.added_lines += 1
                    added_all.append((lineno, text))
                    if not _SECURITY_TOKENS.search(text):
                        continue
                    # anti-FP de relocação: só é adição REAL se o fix aumentou a
                    # contagem daquela linha; contagem preservada = relocação.
                    s = text.strip()
                    if fixed_counts[s] <= vuln_counts[s]:
                        continue
                    kind, cwe = _classify(text)
                    if kind is None:
                        continue
                    res.added_guards.append(GuardHit(line=lineno, text=text, kind=kind, cwe_class=cwe))
            if tag in ("replace", "delete"):
                for text in vuln_lines[i1:i2]:
                    res.removed_lines += 1
                    removed_all.append(text)
                    if _SECURITY_TOKENS.search(text):
                        res.removed_security_lines.append(text.strip())

        # ── mitigação de ReDoS (CL v3.61.0): canal já captado (removidas +
        # adicionadas) que não processávamos.  Baixo-FP: exige AMBOS — remoção de
        # uma regex com construção propensa a backtracking (`.*`/alternação +
        # `.match`/`.search`/`re.compile`) E adição de parsing por string
        # (rpartition/rsplit/partition/split).  Ex.: urllib3 CVE-2021-33503,
        # cujo fix troca `SUBAUTHORITY_RE.match(authority)` por
        # `authority.rpartition("@")` (CWE-1333/400).  Não localizado pelas
        # assinaturas de guard-adicionado porque o sinal está na REMOÇÃO. ──────
        redos = _detect_redos_mitigation(removed_all, added_all)
        if redos is not None:
            res.added_guards.append(redos)

        # ── remoção de sink perigoso (CY v3.74.0): fallback só se NENHUM guard
        # adicionado explicou o fix.  Fixes de RCE por eval/exec dinâmico removem
        # a chamada perigosa (o sinal está na REMOÇÃO, não numa adição).  Baixo-FP:
        # a linha removida tem eval/exec/os.system/pickle.loads E sumiu por
        # completo do fix (fixed_counts==0).  Ancora na 1ª linha adicionada (onde
        # entrou o parsing seguro).  Ex.: tqdm CVE-2024-34062 (CWE-95/94).
        if not res.added_guards:
            for text in removed_all:
                s = text.strip()
                if _DANGEROUS_SINK_RE.search(text) and fixed_counts[s] == 0:
                    anchor = added_all[0][0] if added_all else 1
                    res.added_guards.append(GuardHit(
                        line=anchor, text=s[:120],
                        kind="dangerous-sink-removed", cwe_class="CWE-95/94"))
                    break

        # ── M31 (DK v3.86.0): sinais diff-semânticos finos — fallbacks só se
        # NENHUM guard textual explicou o fix.  Cobrem 2 dos 5 padrões de teto:
        #  (a) DEFAULT-FLIP de kwarg de SEGURANÇA (`scripting=False→True` bleach;
        #      `allow_private_network=True→False` flask-cors) — endurecimento por
        #      inversão de default;
        #  (b) RAISE-INDIRETO (`exc = BadHttpMessage(...)` + `raise exc`
        #      aiohttp CVE-2024-52304) — erro construído numa var e levantado,
        #      que o input-validation-raise (raise <Erro> direto) não pega.
        if not res.added_guards:
            flip = _detect_default_flip(removed_all, added_all)
            if flip is not None:
                res.added_guards.append(flip)
        if not res.added_guards:
            ind = _detect_raise_indirect(added_all)
            if ind is not None:
                res.added_guards.append(ind)

        # ── M29 (DL v3.87.0): detector de RACE — o fix adiciona um LOCK
        # (`with <lock>:` / `.acquire()`) guardando uma checagem de estado/close
        # (will_close/close_when_flushed/return).  Abre a classe de race
        # conditions (CWE-362), 100% teto até aqui.  Ex.: waitress CVE-2024-49768
        # (`with self.requests_lock: if self.will_close or ...: return False`).
        # Fallback + baixo-FP: exige AMBOS lock E termo de estado/close.
        if not res.added_guards:
            race = _detect_race_lock_guard(added_all)
            if race is not None:
                res.added_guards.append(race)
        return res


def _classify(line: str) -> Tuple[Optional[str], Optional[str]]:
    for rx, kind, cwe in _GUARD_SIGNATURES:
        if rx.search(line):
            return kind, cwe
    return None, None


# ── M31 (DK): sinais diff-semânticos finos ───────────────────────────────────
# (a) DEFAULT-FLIP: kwarg cujo NOME é de segurança e cujo default inverte
#     True↔False entre vuln e fix.  Baixo-FP: exige nome de segurança E inversão.
_SEC_KWARG_RE = re.compile(
    r"\b(\w*(?:allow|autoescape|scripting|verify|dangerous|shell|secure|"
    r"strict|resolve_entities|trust|sanitize|escape)\w*)\s*=\s*(True|False)\b")


def _detect_default_flip(
    removed_lines: List[str], added_lines: List[Tuple[int, str]]
) -> Optional["GuardHit"]:
    """Kwarg de segurança cujo default foi INVERTIDO (endurecimento). CWE-1188."""
    rem: dict = {}
    for ln in removed_lines:
        for m in _SEC_KWARG_RE.finditer(ln):
            rem[m.group(1)] = m.group(2)
    for lineno, text in added_lines:
        for m in _SEC_KWARG_RE.finditer(text):
            k, v = m.group(1), m.group(2)
            if k in rem and rem[k] != v:          # inverteu True↔False
                return GuardHit(line=lineno, text=text.strip()[:120],
                                kind="security-default-flip", cwe_class="CWE-1188/16")
    return None


# (b) RAISE-INDIRETO: um erro é CONSTRUÍDO numa variável e depois levantado
#     (`exc = BadHttpMessage(...)` … `raise exc`) — o input-validation-raise só
#     pega `raise <Erro>(...)` direto.  Baixo-FP: exige construção de exceção de
#     erro E um `raise <var>`/`set_exception` nas linhas adicionadas.
_ERR_CONSTRUCT_RE = re.compile(
    r"=\s*\w*(?:Error|Exception|TooLarge|Bad\w*|Invalid\w*|Message|Denied|Forbidden)\s*\(")
_RAISE_VAR_RE = re.compile(r"\braise\s+\w+\s*$|\braise\s+\w+\s*#|\bset_exception\s*\(")


def _detect_raise_indirect(
    added_lines: List[Tuple[int, str]]
) -> Optional["GuardHit"]:
    """Exceção de erro construída e levantada indiretamente. CWE-20."""
    has_construct = any(_ERR_CONSTRUCT_RE.search(t) for _, t in added_lines)
    if not has_construct:
        return None
    for lineno, text in added_lines:
        if _RAISE_VAR_RE.search(text):
            return GuardHit(line=lineno, text=text.strip()[:120],
                            kind="raise-indirect", cwe_class="CWE-20")
    return None


# ── M29 (DL): detector de RACE (lock + guard de estado) ──────────────────────
# aquisição de LOCK adicionada (`with <lock>:` ou `.acquire()`) — o núcleo de um
# fix de race condition.
_LOCK_ACQUIRE_RE = re.compile(
    r"\bwith\s+[\w.]*(?:lock|mutex|semaphore|rlock)\b|"
    r"\b[\w.]*(?:lock|mutex|rlock)\s*\.\s*acquire\s*\(")
# termo de ESTADO/close que o lock passa a proteger (a condição de corrida).
_RACE_STATE_RE = re.compile(
    r"\bwill_close\b|\bclose_when\w*\b|\bis_closing\b|\bclosed\b|\bclosing\b|"
    r"\bshutdown\b|\bflush\w*\b|\breturn\s+(?:False|None)\b|\bdisconnect\w*\b")
# guard de CLOSE-STATE: `if <estado de conexão fechando>` — o padrão real de fix
# de race sobre conexão (waitress CVE-2024-49768) mesmo SEM adicionar lock novo
# (o lock já existia; o fix adiciona o CHECK dentro da seção crítica).
_RACE_CLOSE_GUARD_RE = re.compile(
    r"\b(?:if|elif|while)\b.*\b(?:will_close|close_when\w+|is_closing|is_closed|"
    r"shutdown|disconnect\w*)\b")


def _detect_race_lock_guard(
    added_lines: List[Tuple[int, str]]
) -> Optional["GuardHit"]:
    """
    Fix de RACE (CWE-362): (1) adiciona um LOCK guardando uma checagem de estado,
    OU (2) adiciona um GUARD de close-state (`if will_close/is_closing: return`)
    dentro de uma seção crítica já existente.  Baixo-FP: termos de ciclo-de-vida
    de conexão (will_close/close_when_flushed/is_closing) são específicos.
    Ex.: waitress CVE-2024-49768 (padrão 2 — o lock já existia).
    """
    # (1) lock NOVO + estado
    has_lock = any(_LOCK_ACQUIRE_RE.search(t) for _, t in added_lines)
    has_state = any(_RACE_STATE_RE.search(t) for _, t in added_lines)
    if has_lock and has_state:
        for lineno, text in added_lines:
            if _LOCK_ACQUIRE_RE.search(text):
                return GuardHit(line=lineno, text=text.strip()[:120],
                                kind="race-lock-guard", cwe_class="CWE-362")
    # (2) guard de close-state (if will_close/is_closing/...)
    for lineno, text in added_lines:
        if _RACE_CLOSE_GUARD_RE.search(text):
            return GuardHit(line=lineno, text=text.strip()[:120],
                            kind="race-close-guard", cwe_class="CWE-362")
    return None


# ── ReDoS mitigation (diff-level) ────────────────────────────────────────────
# regex REMOVIDA com risco de backtracking: uma aplicação de regex
# (.match/.search/fullmatch) OU um re.compile de um padrão com `.*`/`.+`/
# alternância — os construtos que causam catastrophic backtracking.
_REDOS_REMOVED_RE = re.compile(
    r"\b\w*(?:_RE|_re|regex|pat|PAT)\w*\s*\.\s*(?:match|search|fullmatch)\s*\(|"
    r"\bre\.(?:match|search|fullmatch)\s*\(|"
    r"\bre\.compile\s*\(")
# parsing por STRING ADICIONADO no lugar (sem regex → sem backtracking).
_REDOS_ADDED_RE = re.compile(
    r"\.\s*(?:rpartition|rsplit|partition|split|find|rfind|index)\s*\(")

# (CT v3.69.0) 2º padrão canônico de mitigação ReDoS: MANTÉM o regex mas LIMITA
# o quantificador (`\s*` → `\s{0,10}`), cortando o backtracking catastrófico.
# Ex.: setuptools CVE-2022-40897 (REL regex em package_index.py).  Baixo-FP:
# exige linha regex (re.compile / raw-string) nos DOIS lados, com quantificador
# ILIMITADO no removido e LIMITADO `{m,n}` no adicionado.
# (DA) +classe-de-caractere-com-quantificador (`[...]+`/`[...]{m,n}`) para casar
# regex SEM backslash (ex.: oauthlib IPv6 `([A-Fa-f0-9:]+:+)+` → `{1,4}`).
_REGEXISH_RE = re.compile(
    r"re\.compile\s*\(|r(?:'''|\"\"\"|['\"]).*\\|\[[^\]]+\][*+?{]")
_BOUNDED_QUANT_RE = re.compile(r"\{\d*,\s*\d+\}")
_UNBOUNDED_QUANT_RE = re.compile(r"(?:\\[swdSWD]|\.|\]|\))[*+]")

# (CT v3.69.0) 3º padrão canônico de mitigação ReDoS: SIMPLIFICA o regex,
# removendo o segmento de backtracking catastrófico — whitespace quantificado
# adjacente a `.*`/`.+` (`\s+.*\s+`, `.*\s+`), a assinatura clássica do
# catastrophic backtracking.  Ex.: Pygments CVE-2022-40896 (templates.py remove
# `\s+.*\s+\{%...endmacro` + re.S).  Baixo-FP: o marcador catastrófico é
# específico e o fix mantém uma chamada de regex (simplificada).
_REDOS_CATASTROPHIC_RE = re.compile(r"\\s[*+]\.[*+]|\.[*+]\\s[*+]|\.[*+].*\.[*+]")

# (CY v3.74.0) sink dinâmico perigoso (RCE/CWE-95/94).  Fixes de code-injection
# frequentemente REMOVEM a chamada perigosa e a substituem por parsing seguro —
# o guard não é ADICIONADO, é a AUSÊNCIA do eval no fix.  Ex.: tqdm CVE-2024-34062
# remove `eval(typ+'("'+val+'")')`.  Detectado como remoção completa (sumiu do fix).
_DANGEROUS_SINK_RE = re.compile(
    r"\b(?:eval|exec)\s*\(|\bos\.system\s*\(|"
    r"\b(?:pickle|cPickle)\.loads?\s*\(|\b__import__\s*\(|"
    r"subprocess\.\w+\([^)]*shell\s*=\s*True")
# linha que É um regex — chamada `re.` OU um pedaço de padrão com metacaracteres
# típicos (`(?:`, `[^`, `\s`, `\w`, `\d`).  (CU: relaxado para casar o fix do
# mako CVE-2022-40023, cujo regex é multi-linha e a linha do fix não contém
# `re.compile(` — é só o corpo do padrão.)
_REGEXCALL_RE = re.compile(
    r"re\.(?:search|compile|match|fullmatch)\s*\(|\(\?:|\[\^|\\[swd]")


def _detect_redos_mitigation(
    removed_lines: List[str], added_lines: List[Tuple[int, str]]
) -> Optional["GuardHit"]:
    """
    Detecta o padrão canônico de correção de ReDoS: o fix REMOVE uma regex
    propensa a backtracking e ADICIONA parsing por string.  Retorna um GuardHit
    sintético (kind='redos-mitigation', CWE-1333/400) ancorado na 1ª linha de
    string-parse adicionada, ou None.  Baixo-FP: exige os DOIS sinais juntos.
    """
    # Padrão A — remove regex, adiciona parsing por string (ex.: urllib3).
    removed_regex = any(_REDOS_REMOVED_RE.search(ln) for ln in removed_lines)
    if removed_regex:
        for lineno, text in added_lines:
            if _REDOS_ADDED_RE.search(text):
                return GuardHit(line=lineno, text=text.strip()[:120],
                                kind="redos-mitigation", cwe_class="CWE-1333/400")

    # Padrão B — mantém o regex mas LIMITA o quantificador (ex.: setuptools
    # CVE-2022-40897: `\s*` → `\s{0,10}`).  Exige regex ilimitado no removido e
    # regex com quantificador limitado `{m,n}` no adicionado (baixo-FP).
    removed_unbounded = any(
        _REGEXISH_RE.search(ln) and _UNBOUNDED_QUANT_RE.search(ln)
        for ln in removed_lines)
    if removed_unbounded:
        for lineno, text in added_lines:
            if _REGEXISH_RE.search(text) and _BOUNDED_QUANT_RE.search(text):
                return GuardHit(line=lineno, text=text.strip()[:120],
                                kind="redos-mitigation", cwe_class="CWE-1333/400")

    # Padrão C — simplifica o regex removendo o segmento catastrófico
    # (`\s+.*\s+`), mantendo uma chamada de regex (ex.: Pygments CVE-2022-40896).
    removed_catastrophic = any(
        _REDOS_CATASTROPHIC_RE.search(ln) for ln in removed_lines)
    if removed_catastrophic:
        for lineno, text in added_lines:
            if _REGEXCALL_RE.search(text):
                return GuardHit(line=lineno, text=text.strip()[:120],
                                kind="redos-mitigation", cwe_class="CWE-1333/400")
    return None
