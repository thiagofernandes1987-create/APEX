"""
UCO-Sensor — Corpus Before/After Validator  (M12)
==================================================
Roda o pipeline de validação de degradação sobre pares CVE
(vulnerável = commit-pai, corrigido = commit-fix) e produz um artefato
estruturado por repositório respondendo, com **dado real**:

  * onde/como/qual-versão  → via M10 FixDiffLocalizer (linha + classe do fix)
  * parou de disparar?     → via M11 GuardAwareScanner: dispara na versão
                             vulnerável e (idealmente) silencia na corrigida
  * algo perpetuou?        → findings do M11 que persistem na versão corrigida

Fonte dos dois lados é o conteúdo real do arquivo em cada commit (fetch
injetável — em produção usa raw.githubusercontent.com; nos testes, um dict).
Puro exceto pelo fetch.  Nenhuma heurística inventa dado: se o fetch falha, o
par vira ``status='fetch_error'``.

API
---
    v = CorpusValidator(fetcher=my_fetch)          # my_fetch(repo, sha, path)->str
    rec = v.validate_pair(repo, parent, fix, path, cve)   -> dict
    recs = v.validate_all(pairs)                   -> list[dict]
"""
from __future__ import annotations

from dataclasses import asdict
from typing import Callable, Dict, List, Optional

from sast.fix_localizer import FixDiffLocalizer
from sast.guard_aware import GuardAwareScanner

_EXT = {'.py','.rb','.rs','.c','.h','.cpp','.cc','.cxx','.hpp','.java','.js','.ts','.go','.php'}

_UCO_LANG = {'.py':'python','.rb':'ruby','.rs':'rust','.c':'c','.h':'c','.cpp':'cpp',
             '.cc':'cpp','.cxx':'cpp','.hpp':'cpp','.java':'java','.js':'javascript',
             '.go':'go','.php':'php'}


def _cfg_delta(vuln: str, fixed: str, ext: str) -> dict:
    """Sinais de CFG do V4 (M15) — dead-code e loop-infinito — antes/depois."""
    try:
        from metrics.cfg_signals import cfg_signals
    except Exception:
        return {}
    lang = _UCO_LANG.get(ext, 'generic')
    v = cfg_signals(vuln, lang); f = cfg_signals(fixed, lang)
    if v.get('status') != 'ok' or f.get('status') != 'ok':
        return {}
    return {
        "reachable_ratio_vuln": round(v['reachable_ratio'], 3),
        "reachable_ratio_fix": round(f['reachable_ratio'], 3),
        "infinite_loop_risk_vuln": round(v['infinite_loop_risk'], 3),
        "infinite_loop_risk_fix": round(f['infinite_loop_risk'], 3),
        "dead_code_vuln": v['syntactic_dead_code'],
        "dead_code_fix": f['syntactic_dead_code'],
        "cyclomatic_delta": f['cyclomatic'] - v['cyclomatic'],
    }


def _ext_of(path: str) -> str:
    return ('.' + path.rsplit('.', 1)[-1]) if '.' in path else ''


class CorpusValidator:
    def __init__(self, fetcher: Callable[[str, str, str], str]) -> None:
        self._fetch = fetcher
        self._loc = FixDiffLocalizer()
        self._m11 = GuardAwareScanner()

    def validate_pair(self, repo: str, parent: str, fix: str, path: str, cve: str) -> Dict:
        ext = _ext_of(path)
        rec: Dict = {"repo": repo, "cve": cve, "file": path, "ext": ext,
                     "parent": parent, "fix": fix}
        try:
            vuln = self._fetch(repo, parent, path)
            fixed = self._fetch(repo, fix, path)
        except Exception as e:  # noqa: BLE001
            rec["status"] = "fetch_error"
            rec["error"] = str(e)[:80]
            return rec

        # M10 — onde/como/qual-versão (âncora no diff do fix)
        loc = self._loc.localize(vuln, fixed, filename=path)
        rec["fix_localized"] = loc.guard_present_in_fix_absent_in_vuln
        rec["fix_guards"] = [asdict(g) for g in loc.added_guards[:5]]
        rec["vuln_classes"] = sorted(loc.vuln_classes)

        # M11 — detecção sem âncora: disparou no vuln? parou no fix?
        v_find = self._m11.scan(vuln, ext)
        f_find = self._m11.scan(fixed, ext)
        v_keys = {(g.rule_id, g.needs_guard_on) for g in v_find}
        f_keys = {(g.rule_id, g.needs_guard_on) for g in f_find}
        stopped = [g for g in v_find if (g.rule_id, g.needs_guard_on) not in f_keys]
        persisted = [g for g in f_find if (g.rule_id, g.needs_guard_on) in v_keys]

        rec["m11_vuln_findings"] = len(v_find)
        rec["m11_fix_findings"] = len(f_find)
        rec["m11_stopped_firing"] = len(stopped) > 0
        rec["m11_stopped"] = [{"line": g.line, "rule": g.rule_id,
                                "guard_on": list(g.needs_guard_on),
                                "snippet": g.snippet[:120]} for g in stopped[:5]]
        rec["m11_persisted_count"] = len(persisted)

        # Sinais de CFG do UCO V4 (M15) antes×depois — reachability, risco de
        # loop-infinito, dead-code e delta de complexidade. Enriquece o registro
        # com a leitura de degradação estrutural do V4, complementar ao guard.
        # (BZ v3.49.0: a chamada a _cfg_delta estava definida mas nunca era
        #  invocada — o sinal do V4 ficava de fora do artefato. Cabeada aqui.)
        rec["cfg_delta"] = _cfg_delta(vuln, fixed, ext)

        # veredito de degradação
        if loc.guard_present_in_fix_absent_in_vuln or stopped:
            rec["status"] = "tracked"          # rastreamos onde/como e/ou o dispara-para
        else:
            rec["status"] = "not_tracked"      # fix sem guard reconhecível (ex.: race)
        return rec

    def validate_all(self, pairs: List[Dict]) -> List[Dict]:
        out: List[Dict] = []
        for p in pairs:
            out.append(self.validate_pair(p["repo"], p["parent"], p["fix"], p["path"], p["cve"]))
        return out


def summarize(records: List[Dict]) -> Dict:
    """Agrega os registros num sumário navegável."""
    tracked = [r for r in records if r.get("status") == "tracked"]
    stopped = [r for r in records if r.get("m11_stopped_firing")]
    localized = [r for r in records if r.get("fix_localized")]
    return {
        "total": len(records),
        "tracked": len(tracked),
        "m10_localized": len(localized),
        "m11_stopped_firing": len(stopped),
        "not_tracked": len([r for r in records if r.get("status") == "not_tracked"]),
        "fetch_error": len([r for r in records if r.get("status") == "fetch_error"]),
    }
