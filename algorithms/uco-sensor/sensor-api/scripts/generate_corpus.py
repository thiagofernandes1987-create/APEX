#!/usr/bin/env python3
"""
UCO-Sensor Corpus Generator
===========================

Regenera `paper/corpus_runs/degradation_report_full.json` como fonte única de
verdade, com contadores SEMPRE calculados (nunca escritos à mão) — fecha o
achado 1.1/D6 da auditoria adversarial (cabeçalho dizia 14/9 com 53 registros
em disco).

Duas dimensões são reportadas SEPARADAMENTE (não conflar — achado 1.2):
  * `complete_4of4` — as 4 perguntas de metadado (quando/onde/como/qual-versão)
    têm resposta concreta (`answers_all_four`).
  * `validated`     — o painel de detectores produziu medida real before/after
    (`stopped_firing` conhecido).

Uso:
  python scripts/generate_corpus.py             # recalcula contadores
  python scripts/generate_corpus.py --backfill  # + preenche published/modified/
                                                #   severity via advisory real
                                                #   (rede: raw.githubusercontent)
"""

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from scan.corpus_expander import DegradationRecord  # noqa: E402


def _record_from_dict(r: dict) -> DegradationRecord:
    return DegradationRecord(
        cve=r["cve"], ghsa=r["ghsa"], package=r["package"],
        ecosystem=r["ecosystem"],
        when_broke=r["when_broke"], resolved_in=r["resolved_in"],
        fix_commit=r["fix_commit"], where_file=r["where_file"],
        published=r.get("published", ""), modified=r.get("modified", ""),
        severity=r.get("severity", ""), cvss_vector=r.get("cvss_vector", ""),
        where_lines=r.get("where_lines", []),
        how_constructs=r.get("how_constructs", []),
        cwe_ids=r.get("cwe_ids", []),
        localized=r.get("localized", False),
        stopped_firing=r.get("stopped_firing"),
        perpetuated=r.get("perpetuated"),
        findings_vuln=r.get("findings_vuln"),
        findings_fixed=r.get("findings_fixed"),
        status=r.get("status", "partial"),
    )


def _backfill_advisory_fields(raw: dict) -> dict:
    """Preenche published/modified/severity buscando o advisory REAL (M25).

    Só toca campos vazios; nunca sobrescreve dado existente.  Falha de rede em
    um registro não derruba o lote (fica vazio, honestamente).
    """
    if (raw.get("published") and raw.get("modified") and raw.get("severity")
            and raw.get("cvss_vector")):
        return raw
    ghsa = raw.get("ghsa", "")
    if not ghsa.startswith("GHSA-"):
        return raw  # registros NVD/C não têm advisory GHSA
    from scan.advisory_resolver import resolve_advisory
    adv = resolve_advisory(ghsa, cve_hint=raw.get("cve", ""))
    if adv is None:
        print(f"  [backfill] {raw.get('cve')}: advisory nao resolvido (fica vazio)")
        return raw
    raw = dict(raw)
    for k in ("published", "modified", "severity", "cvss_vector"):
        raw.setdefault(k, "")
        raw[k] = raw[k] or getattr(adv, k, "")
    print(f"  [backfill] {raw.get('cve')}: published={raw['published'][:10]} "
          f"severity={raw['severity']} cvss={raw['cvss_vector'][:24]}")
    return raw


def main() -> None:
    backfill = "--backfill" in sys.argv
    corpus_runs = _ROOT.parent / "paper" / "corpus_runs"
    in_file = corpus_runs / "degradation_report_full.json"
    if not in_file.exists():
        print(f"Erro: {in_file} nao encontrado.")
        sys.exit(1)

    data = json.loads(in_file.read_text(encoding="utf-8"))
    raw_records = data.get("records", [])

    records = []
    for r in raw_records:
        try:
            if backfill:
                r = _backfill_advisory_fields(r)
            records.append((_record_from_dict(r), r.get("status", "partial")))
        except Exception as e:  # noqa: BLE001 — registro ruim não derruba o lote
            print(f"Erro processando {r.get('cve')}: {e}")

    total = len(records)
    complete = sum(1 for rec, _ in records if rec.answers_all_four)
    validated = sum(1 for rec, _ in records if rec.validated)
    stopped = sum(1 for rec, _ in records if rec.stopped_firing)
    perpetuated = sum(1 for rec, _ in records if rec.perpetuated)

    out_records = []
    for rec, orig_status in records:
        d = rec.to_dict()
        # `metadata_only` é decisão do produtor do registro; preserva.
        # complete/partial derivam de answers_all_four (fonte única).
        if orig_status == "metadata_only":
            d["status"] = "metadata_only"
        else:
            d["status"] = "complete" if rec.answers_all_four else "partial"
        out_records.append(d)

    out_data = {
        "generated_by": "scripts/generate_corpus.py (contadores calculados, nunca manuais)",
        "total": total,
        "complete_4of4": complete,
        "validated": validated,
        "validated_stopped_firing": stopped,
        "validated_perpetuated": perpetuated,
        "partial": total - complete,
        "records": out_records,
    }

    in_file.write_text(json.dumps(out_data, indent=2, ensure_ascii=False) + "\n",
                       encoding="utf-8")
    print(f"Corpus atualizado: {total} total | {complete} completos 4/4 (metadado) | "
          f"{validated} validados dinamicamente (stopped_firing conhecido)")


if __name__ == "__main__":
    main()
