#!/usr/bin/env python3
"""
UCO-Sensor — Analisador de Histórico Real
==========================================
Recebe o JSON gerado por extract_repo_history.py e executa
o pipeline completo do FrequencyEngine sobre dados reais.

Uso (roda AQUI, no servidor com FrequencyEngine):
    python3 analyze_real_history.py --input flask_history.json
    python3 analyze_real_history.py --input requests_history.json
    python3 analyze_real_history.py --input django_history.json --ground-truth django

Métricas reportadas:
  • Tipo de erro detectado por módulo
  • Confiança da classificação
  • Hurst, PCI, Burst, HF/LF, self_cure
  • Onset (commit onde a degradação começou)
  • fw_shift (detecção de degradação espectral)
  • Comparação com ground truth (se fornecido)
"""
import sys, json, time, argparse
from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import dataclass

sys.path.insert(0, "/home/claude/uco-sensor-api")
sys.path.insert(0, "/home/claude/uco-frequency-engine")

from core.data_structures import MetricVector
from pipeline.frequency_engine import FrequencyEngine
from router.signal_output_router import SignalOutputRouter, OutputFormat
from datetime import datetime as _datetime


# ─── Ground Truth (anotações manuais de problemas conhecidos) ─────────────────

GROUND_TRUTH = {
    "requests": {
        "requests.sessions": {
            "expected_type": "GOD_CLASS_FORMATION",
            "notes": "sessions.py é a god class documentada do requests — PreparedRequest, "
                     "Session, merge_environment_settings acumulam responsabilidades"
        },
        "requests.adapters": {
            "expected_type": "COGNITIVE_COMPLEXITY_EXPLOSION",
            "notes": "HTTPAdapter.send() tem CC historicamente alto"
        },
        "requests.models": {
            "expected_type": "GOD_CLASS_FORMATION",
            "notes": "PreparedRequest e Response acumulam estado e comportamento"
        },
    },
    "flask": {
        "src.flask.app": {
            "expected_type": "GOD_CLASS_FORMATION",
            "notes": "Flask class acumula responsabilidades desde 0.x"
        },
        "flask.app": {
            "expected_type": "GOD_CLASS_FORMATION",
            "notes": "Flask class (path alternativo)"
        },
        "src.flask.wrappers": {
            "expected_type": "TECH_DEBT_ACCUMULATION",
            "notes": "Wrappers acumulam compat layers"
        },
    },
    "django": {
        "django.db.models.base": {
            "expected_type": "TECH_DEBT_ACCUMULATION",
            "notes": "Model base class com decades de tech debt documentado"
        },
        "django.db.models.query": {
            "expected_type": "GOD_CLASS_FORMATION",
            "notes": "QuerySet acumula centenas de métodos"
        },
        "django.core.handlers.base": {
            "expected_type": "COGNITIVE_COMPLEXITY_EXPLOSION",
            "notes": "BaseHandler.load_middleware() muito complexo"
        },
    },
    "scrapy": {
        "scrapy.crawler": {
            "expected_type": "DEPENDENCY_CYCLE_INTRODUCTION",
            "notes": "scrapy 2.0 introduziu acoplamento circular crawler↔spidermw"
        },
        "scrapy.core.engine": {
            "expected_type": "GOD_CLASS_FORMATION",
            "notes": "ExecutionEngine tem muitas responsabilidades"
        },
    },
}


# ─── Conversor JSON → MetricVector ───────────────────────────────────────────

def json_to_metric_vectors(snapshots: List[Dict],
                            module_id: str) -> List[MetricVector]:
    """
    Converte snapshots do JSON extrator em MetricVectors.
    v2.0: ordena por timestamp e deduplica timestamps idênticos
    (commits de rebase/cherry-pick causam divide-by-zero na interpolação).
    """
    # Filtrar erros de parse, ordenar cronologicamente, deduplicar por timestamp
    valid = [s for s in snapshots if not s.get("parse_error", False)]
    valid.sort(key=lambda s: float(s.get("timestamp", 0)))
    seen_ts: set = set()
    deduped = []
    for s in valid:
        ts_key = float(s.get("timestamp", 0))
        if ts_key not in seen_ts:
            seen_ts.add(ts_key)
            deduped.append(s)
    snapshots = deduped

    vectors = []
    n_total = len(snapshots)
    for idx, s in enumerate(snapshots):
        if s.get("parse_error", False):
            continue
        try:
            mv = MetricVector(
                module_id=module_id,
                commit_hash=s["commit_hash"],
                timestamp=float(s["timestamp"]),
                hamiltonian=max(0.1, float(s["hamiltonian"])),
                cyclomatic_complexity=max(1, int(s["cyclomatic_complexity"])),
                infinite_loop_risk=float(s["infinite_loop_risk"]),
                dsm_density=float(s["dsm_density"]),
                dsm_cyclic_ratio=float(s["dsm_cyclic_ratio"]),
                dependency_instability=float(s["dependency_instability"]),
                syntactic_dead_code=max(0, int(s["syntactic_dead_code"])),
                duplicate_block_count=max(0, int(s["duplicate_block_count"])),
                halstead_bugs=max(0.0, float(s["halstead_bugs"])),
                window_position=float(s.get("window_position",
                                            idx / max(1, n_total - 1))),  # BUG-R4
            )
            vectors.append(mv)
        except (KeyError, ValueError, TypeError) as e:
            pass  # snapshot incompleto — pular
    return vectors


# ─── Analisador principal ─────────────────────────────────────────────────────

def analyze_history(
    input_path: str,
    ground_truth_repo: Optional[str] = None,
    min_snapshots: int = 20,
) -> None:
    """
    Carrega o JSON e executa o FrequencyEngine em cada módulo.
    """
    with open(input_path, encoding="utf-8") as f:
        data = json.load(f)

    repo_name    = data.get("repo", Path(input_path).stem)
    modules      = data.get("modules", {})
    total_snaps  = data.get("total_snapshots", 0)
    extracted_at = data.get("extracted_at", 0)

    gt = GROUND_TRUTH.get(ground_truth_repo or repo_name.split("-")[0], {})

    engine = FrequencyEngine(verbose=False)
    router = SignalOutputRouter()

    print(f"\n{'═'*72}")
    print(f"  UCO-Sensor — Análise de Repositório Real")
    print(f"{'═'*72}")
    print(f"  Repositório:    {repo_name}")
    print(f"  Módulos:        {len(modules)}")
    print(f"  Total snapshots:{total_snaps}")
    if extracted_at:
        dt = _datetime.fromtimestamp(extracted_at).strftime("%Y-%m-%d %H:%M")
        print(f"  Extraído em:    {dt}")
    print(f"{'─'*72}")

    results = []
    n_with_gt = 0
    n_gt_correct = 0

    for module_id, snapshots in modules.items():
        vectors = json_to_metric_vectors(snapshots, module_id)

        if len(vectors) < min_snapshots:
            print(f"\n  ⚠ {module_id}: apenas {len(vectors)} snapshots válidos "
                  f"(mínimo: {min_snapshots}) — pulando")
            continue

        t0 = time.perf_counter()
        result = engine.analyze(vectors)
        ms = (time.perf_counter() - t0) * 1000

        if result is None:
            print(f"\n  ? {module_id}: FrequencyEngine retornou None")
            continue

        # Ground truth
        gt_entry = gt.get(module_id, {})
        expected = gt_entry.get("expected_type", "")
        gt_match = None
        if expected:
            n_with_gt += 1
            gt_match = result.primary_error == expected
            if gt_match:
                n_gt_correct += 1

        # Output
        print(f"\n  {'─'*68}")
        print(f"  Módulo: {module_id}")
        print(f"  Commits analisados: {len(vectors)}  |  Latência: {ms:.0f}ms")

        col_type = "\033[92m" if gt_match else ("\033[91m" if gt_match is False else "")
        rst = "\033[0m"
        print(f"  Tipo detectado:  {col_type}{result.primary_error}{rst}  "
              f"[{result.severity}]  confiança={result.primary_confidence:.1%}")
        if expected:
            tick = "✓" if gt_match else "✗"
            col  = "\033[92m" if gt_match else "\033[91m"
            print(f"  Ground truth:    {col}{tick}{rst} esperado={expected}")
            if gt_entry.get("notes"):
                print(f"  Nota:            {gt_entry['notes']}")

        if result.change_point:
            cp = result.change_point
            print(f"  Onset detectado: commit idx {cp.commit_idx}  "
                  f"(confiança={cp.confidence:.1%})")

        print(f"\n  Métricas de persistência:")
        print(f"    Hurst(H):       {result.hurst_H:.4f}  "
              f"{'← CRÔNICO (intervenção obrigatória)' if result.hurst_H > 0.85 else '← transitório'}")
        print(f"    PCI(CC,H):      {result.phase_coupling_CC_H:.4f}  "
              f"{'← CC e H sincronizados' if result.phase_coupling_CC_H > 0.80 else '← H dominado por outros canais'}")
        print(f"    Burst(CC):      {result.burst_index_H:.4f}  "
              f"{'← evento AGUDO' if result.burst_index_H > 0.70 else '← degradação gradual'}")
        print(f"    HF/LF(H):       {result.hflf_ratio_H:.4f}")
        print(f"    Onset revers:   {result.onset_reversibility:.4f}")
        print(f"    Self-cure:      {result.self_cure_probability:.1f}%  "
              f"{'← NÃO vai melhorar sozinho' if result.self_cure_probability < 5 else '← pode estabilizar'}")

        # fw_shift dos canais primários
        fw_evidence = {k: v for k, v in result.spectral_evidence.items()
                       if k.endswith("_fw_shift")}
        if fw_evidence:
            print(f"\n  CSL fw_shift (deslocamento espectral):")
            for ch, fw in fw_evidence.items():
                anomalous = fw > 0.20
                col_fw = "\033[93m" if anomalous else "\033[92m"
                print(f"    {ch:<25} {col_fw}{fw:.4f}{rst}  "
                      f"{'⚠ degradação detectada' if anomalous else '✓ normal'}")

        # Top-3 hipóteses
        print(f"\n  Top-3 hipóteses:")
        for i, hyp in enumerate(result.hypotheses[:3]):
            print(f"    {i+1}. {hyp.error_type:<42} conf={hyp.confidence:.1%}")

        results.append({
            "module_id":     module_id,
            "detected_type": result.primary_error,
            "severity":      result.severity,
            "confidence":    result.primary_confidence,
            "hurst_H":       result.hurst_H,
            "pci":           result.phase_coupling_CC_H,
            "burst":         result.burst_index_H,
            "hflf":          result.hflf_ratio_H,
            "onset_rev":     result.onset_reversibility,
            "self_cure":     result.self_cure_probability,
            "n_commits":     len(vectors),
            "latency_ms":    ms,
            "expected_type": expected,
            "gt_correct":    gt_match,
        })

    _print_analysis_summary(
        results, repo_name, n_with_gt, n_gt_correct, out_path)

def _print_analysis_summary(
    results: list,
    repo_name: str,
    n_with_gt: int,
    n_gt_correct: int,
    out_path) -> None:
    """Print + save analysis summary — extracted from analyze_history() OPT-04."""
    # ── Resumo ────────────────────────────────────────────────────────────
    print(f"\n{'═'*72}")
    print(f"  RESUMO — {repo_name}")
    print(f"{'─'*72}")
    print(f"  Módulos analisados: {len(results)}")
    if n_with_gt > 0:
        pct = n_gt_correct / n_with_gt
        col = "\033[92m" if pct >= 0.70 else "\033[91m"
        print(f"  Precisão (ground truth): {col}{n_gt_correct}/{n_with_gt} [{pct:.0%}]{'\033[0m'}")

    # Distribuição de tipos
    from collections import Counter
    types_dist = Counter(r["detected_type"] for r in results)
    print(f"\n  Tipos detectados:")
    for t, count in types_dist.most_common():
        print(f"    {t:<42} {count}×")

    # Métricas de persistência agregadas
    if results:
        avg_hurst    = sum(r["hurst_H"] for r in results) / len(results)
        chronic_ct   = sum(1 for r in results if r["hurst_H"] > 0.85)
        interv_ct    = sum(1 for r in results if r["self_cure"] < 5.0)
        fw_anomalies = sum(1 for r in results
                           if r.get("fw_anomaly_detected", False))

        print(f"\n  Hurst médio:       {avg_hurst:.3f}")
        print(f"  Módulos crônicos:  {chronic_ct}/{len(results)}  "
              f"(Hurst > 0.85 → intervenção obrigatória)")
        print(f"  Intervenção imdt:  {interv_ct}/{len(results)}  "
              f"(self_cure < 5%)")

    # Salvar relatório
    out_path = Path(input_path).with_suffix(".analysis.json")
    report = {
        "repo":             repo_name,
        "analyzed_at":      time.time(),
        "n_modules":        len(results),
        "ground_truth_pct": n_gt_correct / n_with_gt if n_with_gt > 0 else None,
        "modules":          results,
    }
    with open(str(out_path), "w") as f:
        json.dump(report, f, indent=2, default=str)
    print(f"\n  Relatório salvo: {out_path}")
    print(f"{'═'*72}\n")


    # ─── CLI ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="UCO-Sensor — Análise de histórico real extraído",
    )
    parser.add_argument("--input",        required=True,
                        help="JSON gerado por extract_repo_history.py")
    parser.add_argument("--ground-truth", default=None,
                        help="Repositório para ground truth: requests|flask|django|scrapy")
    parser.add_argument("--min-snapshots",type=int, default=20,
                        help="Mínimo de commits válidos por módulo (default: 20)")
    args = parser.parse_args()

    analyze_history(
        input_path=args.input,
        ground_truth_repo=args.ground_truth,
        min_snapshots=args.min_snapshots,
    )


if __name__ == "__main__":
    main()
