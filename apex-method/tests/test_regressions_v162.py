#!/usr/bin/env python3
"""Regressões empíricas v1.62 — cada teste reproduz um GAP provado na auditoria de
2026-07-21 (exp_final.py) e trava o comportamento corrigido:

  R1  Taxonomy enriquecida: tarefas frontend/web PT+EN classificam (v1.61: domain=None).
  R2  Cache híbrido: paráfrases do MESMO problema short-circuitam (v1.61: 3/7);
      tarefas NÃO relacionadas nunca short-circuitam (falso positivo = bug crítico).
  R3  Triage: edição incremental trivial NÃO escala para DEEP (v1.61: "corrigir typo
      no README" → DEEP ~8k tokens); floors de audit/security PERMANECEM DEEP+.
  R4  Event bus: orchestrator.run auto-instrumenta (trace completo + evaluate).

Roda isolado (APEX_METHOD_HOME temporário). Uso: python3 tests/test_regressions_v162.py
"""
import os
import sys
import tempfile

os.environ["APEX_METHOD_HOME"] = tempfile.mkdtemp(prefix="apexreg_")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))

FAILURES = []


def check(name, cond, detail=""):
    status = "PASS" if cond else "FAIL"
    print(f"  {status}  {name}  {detail}")
    if not cond:
        FAILURES.append(name)


def t_r1_taxonomy():
    import taxonomy
    print("R1 — taxonomy enriquecida (frontend PT/EN + fix_small + OpenClaw vocab)")
    c = taxonomy.classify("criar landing page com animações 3D e glassmorphism")
    check("landing PT -> software/frontend/web",
          c["domain"] == "software" and c["subdomain"] == "frontend" and c["platform"] == "web", c)
    c = taxonomy.classify("build a landing page with 3D transforms and glassmorphism")
    check("landing EN -> software/frontend", c["domain"] == "software" and c["subdomain"] == "frontend", c)
    c = taxonomy.classify("corrigir typo no README")
    check("typo README -> intent fix_small", c["intent"] == "fix_small" and c["domain"] == "software", c)
    c = taxonomy.classify("configurar webhook com telemetria OTEL")
    check("webhook/OTEL -> observability|automation",
          c["subdomain"] in ("observability", "automation"), c)
    c = taxonomy.classify("receita de bolo de cenoura com cobertura de chocolate")
    check("bolo de cenoura -> nenhum domínio (sem chute)", c["domain"] is None, c)


def t_r2_hybrid_cache():
    import skill_ledger, orchestrator
    print("R2 — cache de resolução híbrido (recall + facet gate)")
    solved = [
        ("criar landing page com animações 3D e glassmorphism", "css3-advanced"),
        ("integrar oscilador 2D com RK4 e verificar conservação de energia", "numeric-rk4"),
        ("auditar contrato de aluguel quanto a cláusulas abusivas LGPD", "legal-contract-review"),
    ]
    for prob, sk in solved:
        for _ in range(2):
            skill_ledger.record(prob, sk, agent="specialist", solved=True)
    positives = [
        "criar landing page com animações 3D e glassmorphism",
        "página de vendas com efeitos 3D e vidro fosco animado",
        "build a landing page with 3D transforms and glassmorphism effects",
        "adicionar seção de depoimentos na landing page 3D existente",
        "simular oscilador harmônico bidimensional com Runge-Kutta 4a ordem",
        "solve a 2D oscillator ODE with RK4 and check energy drift",
        "revisar cláusulas abusivas em contrato de locação (LGPD)",
    ]
    hits = sum(1 for q in positives if orchestrator.resolution_check(q))
    check(f"paráfrases reconhecidas {hits}/7 (>=6; v1.61 dava 3)", hits >= 6)
    negatives = [
        "receita de bolo de cenoura com cobertura de chocolate",
        "otimizar consulta SQL lenta com índice composto no Postgres",
        "escrever poema sobre o outono em Lisboa",
        "configurar cluster kubernetes com autoscaling",
        "traduzir documento de inglês para japonês",
    ]
    fps = [q for q in negatives if orchestrator.resolution_check(q)]
    check("0 falsos positivos em não-relacionadas (obrigatório)", not fps, fps)
    rc = orchestrator.resolution_check("página de vendas com efeitos 3D e vidro fosco animado")
    check("tier 'facet' na banda 0.5-0.6 + reverify obrigatório",
          rc and rc.get("tier") in ("facet", "prior") and rc.get("reverify_required") is True,
          rc and rc.get("tier"))


def t_r3_triage():
    import execution_policy
    print("R3 — triage taxonomy-informed (fim do UNKNOWN_CLASS->DEEP indiscriminado)")
    order = ["EXPRESS", "STANDARD", "FOGGY", "DEEP", "SCIENTIFIC", "RESEARCH"]
    def rank(m): return order.index(m) if m in order else 99
    t = execution_policy.triage("ajustar a cor do botão CTA da landing page")
    check("edição trivial <= STANDARD (v1.61: DEEP)", rank(t["mode"]) <= rank("STANDARD"), t["mode"])
    t = execution_policy.triage("corrigir typo no README")
    check("typo README <= STANDARD (v1.61: DEEP)", rank(t["mode"]) <= rank("STANDARD"), t["mode"])
    t = execution_policy.triage("criar landing page com animações 3D e glassmorphism")
    check("tarefa reconhecida -> STANDARD + dissect personas",
          t["mode"] == "STANDARD" and t.get("require_dissect_personas"), t["mode"])
    t = execution_policy.triage("auditoria de segurança completa do backend")
    check("floor audit/security PERMANECE >= DEEP", rank(t["mode"]) >= rank("DEEP"), t["mode"])
    t = execution_policy.triage("qual o sentido da vida em marte considerando xenobiologia especulativa")
    check("irreconhecível PERMANECE DEEP (conservador)", rank(t["mode"]) >= rank("DEEP"), t["mode"])
    t = execution_policy.triage("2+2")
    check("aritmética pura PERMANECE EXPRESS skip", t.get("skip_pipeline") is True, t["mode"])


def t_r4_event_bus():
    import orchestrator, event_bus
    print("R4 — event bus auto-instrumentado")
    r = orchestrator.run("dimensionar viga de concreto armado biapoiada vão 6m NBR 6118")
    tid = r.get("trace_id")
    check("run devolve trace_id", bool(tid), tid)
    ev = event_bus.evaluate(tid)
    check("evaluate encontra o trace completo", ev.get("found") and ev.get("completed"), ev.get("events"))
    check("triage + mode_decision no trace",
          {"execution_policy", "orchestrator"} <= set(ev.get("modules", [])), ev.get("modules"))
    check("cache_miss registrado (sem histórico)", ev["cache"]["misses"] >= 1, ev["cache"])
    ex = event_bus.export_jsonl(os.path.join(os.environ["APEX_METHOD_HOME"], "events.jsonl"))
    check("export_jsonl determinístico", ex.get("exported", 0) >= 4, ex)


if __name__ == "__main__":
    for t in (t_r1_taxonomy, t_r2_hybrid_cache, t_r3_triage, t_r4_event_bus):
        t()
    total = 19
    print(f"\n{'FAIL: ' + ', '.join(FAILURES) if FAILURES else 'REGRESSÕES v1.62: TODAS PASS'}")
    sys.exit(1 if FAILURES else 0)
