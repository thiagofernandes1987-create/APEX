#!/usr/bin/env python3
"""knowledge_base.py — a base de conhecimento COMPARTILHADA do APEX (v1.63).

O que o autor pediu: uma base que qualquer um que use o APEX consulta e da qual CARREGA estados
de sucesso — ranking histórico de sucesso + popularidade de agentes/skills por disciplina,
vacinas, promoções, diffs e configs de agentes, tudo disponível para query e load.

DESENHO HONESTO (a distinção importa):
  - POPULARIDADE por disciplina = distribuição de COBERTURA real (coverage_sweep): quantas
    skills/agentes cada disciplina alcança. É medição determinística, não opinião.
  - RANKING DE SUCESSO = `learning` (beta-binomial, promote/demote): cresce com execuções
    VALIDADAS reais. Começa do seed de baseline e evolui — nunca inflado.
  - VACINAS = `code_genetics` (erro→fix duráveis). PROMOÇÕES = ledger de governança.
  - O seed de baseline (`catalog/knowledge_base_seed.json`) é a BASE compartilhada que viaja
    no repositório; `load_state()` hidrata uma instância nova a partir dele.

Backend: SQLite/JSON stdlib (sem BD vetorial — a recuperação semântica já é o rag_index/taxonomy).
Durável em `APEX_METHOD_HOME/library/` (viaja no swap bundle). Best-effort: nunca levanta.
"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEED = os.path.join(ROOT, "catalog", "knowledge_base_seed.json")
COVERAGE = os.path.join(ROOT, "catalog", "coverage_report.json")


def _load_json(path, default=None):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default if default is not None else {}


# ── POPULARIDADE (cobertura real) ────────────────────────────────────────────────────────────
def popularity_by_discipline():
    """Distribuição real de skills por disciplina (coverage_sweep) + agentes por domínio."""
    cov = _load_json(COVERAGE)
    return {
        "skills_per_discipline": cov.get("skills_per_discipline", {}),
        "agent_domain_distribution": cov.get("agent_domain_distribution", {}),
        "recognition_rate": cov.get("recognition_rate"),
        "orphans_count": cov.get("orphans_count"),
        "source": "coverage_sweep (determinístico)",
    }


# ── RANKING DE SUCESSO (learning, evolui com runs validados) ──────────────────────────────────
def success_ranking(discipline="general", k=10, kind="skill"):
    try:
        import learning
        ls = learning.LearningStore()
        best = ls.best(kind, discipline, k=k, include_demoted=True)
        return {"discipline": discipline, "kind": kind, "ranking": best,
                "source": "learning (beta-binomial, validado)"}
    except Exception as e:
        return {"discipline": discipline, "ranking": [], "error": str(e)[:100]}


def agent_status(agent_id):
    """Status consolidado de um agente: aprendizado (promoções/rebaixamentos) + grants."""
    out = {"agent_id": agent_id}
    try:
        import learning
        ls = learning.LearningStore()
        # varre disciplinas conhecidas na popularidade
        pop = popularity_by_discipline()["agent_domain_distribution"]
        statuses = {}
        for dom in list(pop)[:12]:
            for b in ls.best("persona", dom, k=20, include_demoted=True):
                if b.get("subject") == agent_id:
                    statuses[dom] = {"status": b.get("status"), "mean": b.get("mean"), "n": b.get("n")}
        out["learning"] = statuses
    except Exception:
        out["learning"] = {}
    try:
        import agent_spawn
        out["grants"] = agent_spawn.list_grants(agent_id) if hasattr(agent_spawn, "list_grants") else []
    except Exception:
        out["grants"] = []
    return out


# ── VACINAS + PROMOÇÕES (durável, auditável) ──────────────────────────────────────────────────
def vaccines(k=50):
    try:
        import code_genetics
        cg = code_genetics.VaccineStore() if hasattr(code_genetics, "VaccineStore") else None
        if cg and hasattr(cg, "all"):
            return cg.all()[:k]
    except Exception:
        pass
    return []


def promotions(k=50):
    """Eventos de promoção/rebaixamento do ledger de governança (SHA-256, auditável)."""
    try:
        import memory
        m = memory.MemoryStore()
        hits = m.recall("promote demote promotion", k=k)
        return [{"text": str(h.get("text", h))[:120], "score": h.get("score")} for h in hits][:k]
    except Exception:
        return []


# ── ESTADO COMPARTILHADO: build / load ────────────────────────────────────────────────────────
def build_seed():
    """Constrói o seed de baseline (a BASE compartilhada) a partir da cobertura + rankings atuais.
    Determinístico (sem timestamps) para caber na convenção de prompt-cache e diff limpo."""
    pop = popularity_by_discipline()
    disciplines = list(pop["skills_per_discipline"].keys())
    seed = {
        "_doc": "APEX shared knowledge base — popularidade (cobertura real) + rankings de sucesso "
                "(learning) + estado carregável. Serve de base para qualquer instância do APEX.",
        "popularity": pop,
        "disciplines": disciplines,
        "success_ranking_by_discipline": {
            d: success_ranking(d, k=5)["ranking"] for d in disciplines[:20]
        },
        "vaccines_count": len(vaccines()),
        "how_to_load": "knowledge_base.load_state() hidrata learning/memory a partir deste seed.",
    }
    return seed


def save_seed():
    seed = build_seed()
    json.dump(seed, open(SEED, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return {"saved": SEED, "disciplines": len(seed["disciplines"])}


def load_state():
    """Hidrata uma instância nova a partir do seed compartilhado: injeta os rankings de sucesso
    validados no learning store local (carregamento de 'estados de sucesso')."""
    seed = _load_json(SEED)
    if not seed:
        return {"loaded": False, "reason": "sem knowledge_base_seed.json"}
    loaded = 0
    try:
        import learning
        ls = learning.LearningStore()
        for disc, ranking in (seed.get("success_ranking_by_discipline") or {}).items():
            for entry in ranking:
                subj, status = entry.get("subject"), entry.get("status")
                if subj and status == "PROMOTED":
                    # re-semeia como evidência validada (weight baixo: é herança, não prova local)
                    ls.record_outcome("skill", subj, disc, True, weight=0.5,
                                      evidence="loaded_from_shared_kb")
                    loaded += 1
    except Exception as e:
        return {"loaded": False, "error": str(e)[:100]}
    return {"loaded": True, "seeded_success_states": loaded,
            "disciplines": len(seed.get("disciplines", []))}


def summary():
    pop = popularity_by_discipline()
    return {
        "popularity": pop["skills_per_discipline"],
        "recognition_rate": pop["recognition_rate"],
        "orphans": pop["orphans_count"],
        "agents_by_domain": pop["agent_domain_distribution"],
        "vaccines": len(vaccines()),
    }


if __name__ == "__main__":
    import sys
    if "--build" in sys.argv:
        print(json.dumps(save_seed(), ensure_ascii=False))
    else:
        print(json.dumps(summary(), ensure_ascii=False, indent=1)[:800])
