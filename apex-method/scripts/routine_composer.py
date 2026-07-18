#!/usr/bin/env python3
"""
routine_composer.py — a persona compõe a PRÓPRIA ROTINA: um fluxo encadeado de capacidades
complementares que se potencializam (o item 2 do autor, levado à execução).

WHY THIS EXISTS:
  Saber que uma ferramenta existe não basta — o agente precisa do COMO: "primeiro faço isso
  com essa ferramenta e recebo isso; mando para tal skill que retorna X; envio para outra que
  retorna Y". O exemplo canônico do autor: uma landing page NÃO-genérica precisa de UX/UI +
  psicologia das cores/gatilhos (marketing) + CSS/HTML5 (transições) + SQL (dados) +
  performance responsiva + auditoria — ferramentas que SE COMPLETAM. Este módulo compõe esse
  fluxo: estágios canônicos (pesquisa→design→marketing→frontend→backend→performance→verificação),
  candidatos vindos do capability_map (contratos de I/O) + attraction_graph (quem se atrai) +
  learning (o comprovado sobe, o rebaixado sai), cada passo com O QUE ENVIAR e O QUE RECEBER,
  encadeados (o output do passo N alimenta o passo N+1). A rotina é PERSISTIDA por persona
  (viaja no swap plug-and-play), e evolui: outcomes reais e FEEDBACK (auditorias de outros
  LLMs, feedback positivo do usuário) promovem/rebaixam a rotina e sugerem equipar/desequipar.

WHEN TO USE:
  - compose(challenge, agent_id): montar o fluxo para um desafio (o spawn injeta a rotina).
  - save_routine()/best_routine(): a persona guarda e reutiliza o que já funcionou.
  - record_routine_outcome(): resultado real -> promoção beta-binomial (kind 'routine').
  - record_feedback(): auditoria externa / feedback do usuário -> pontos fortes/fracos/gaps
    viram memória com proveniência + sugestões de equip/unequip (H5 decide).

WHAT IF IT FAILS:
  Motores ausentes degradam (fluxo só com os estágios resolvíveis, honesto sobre gaps);
  store de rotinas ilegível -> lista vazia. Nunca levanta exceção em uso normal.
"""
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))

HERE = os.path.dirname(__file__)


def _routines_path():
    base = os.environ.get("APEX_METHOD_HOME") or os.path.expanduser("~/.apex-method")
    os.makedirs(base, exist_ok=True)
    return os.path.join(base, "routines.json")


# ── estágios canônicos: a ordem em que ferramentas complementares se encadeiam ───────────────
# keywords bilíngues classificam cada capacidade num estágio; a ordem é o esqueleto do fluxo.
STAGES = [
    ("research", {"research", "pesquisa", "brainstorm", "requirements", "requisito", "zoom",
                  "discovery", "ideation", "diverge"}),
    ("design", {"design", "ux", "ui", "taste", "wireframe", "layout", "visual", "canvas",
                "polish", "extract-design"}),
    ("marketing", {"marketing", "seo", "copy", "psicolog", "gatilho", "conversion", "conversão",
                   "brand", "color", "cores", "growth", "content"}),
    ("frontend", {"frontend", "css", "html", "react", "component", "transition", "transição",
                  "next", "tailwind", "shadcn", "web-design"}),
    ("backend", {"backend", "sql", "database", "banco", "postgres", "api", "auth", "server",
                 "supabase", "firebase"}),
    ("performance", {"performance", "responsiv", "lighthouse", "speed", "desempenho", "optimize",
                     "otimiz", "cache"}),
    ("verify", {"audit", "auditoria", "test", "review", "qa", "verificação", "security",
                "acessibilidade", "accessibility", "verify"}),
]


def _stage_of(text):
    tl = (text or "").lower()
    for stage, kws in STAGES:
        if any(k in tl for k in kws):
            return stage
    return None


# o contrato de encadeamento por estágio: o que este estágio ENTREGA ao próximo
STAGE_HANDOFF = {
    "research": "briefing: objetivo, público, referências e restrições",
    "design": "direção visual: hierarquia, grid, componentes e mood (anti-genérico)",
    "marketing": "camada persuasiva: paleta por psicologia das cores, gatilhos, copy dos CTAs",
    "frontend": "implementação: HTML5/CSS/componentes com transições, tokens de design aplicados",
    "backend": "dados ligados: schema SQL, queries e endpoints que a página consome",
    "performance": "página otimizada: métricas responsivas/carregamento dentro do orçamento",
    "verify": "laudo: pontos fortes/fracos, gaps e correções — com evidência",
}


def _candidates(challenge):
    """Candidatos de TODAS as memórias: capability_map (contratos), attraction_graph (quem se
    completa), curated (melhores por domínio). learning filtra rebaixados e sobe comprovados."""
    cands = {}

    def add(cid, name, desc, io, source, score=1.0):
        # elegibilidade: ferramentas meta do runtime (tool:*) só disputam o estágio VERIFY
        # (uco_gate/verification_gate/skill_scout); templates são formato de saída, não passo.
        if cid.startswith("template:") or cid == "skill:apex-method":
            return                                 # templates são formato; nós não somos um passo
        stage = _stage_of(f"{cid} {name} {desc}")
        if not stage:
            return
        if cid.startswith("tool:") and stage != "verify":
            return
        cur = cands.get(cid)
        if cur is None or score > cur["score"]:
            cands[cid] = {"id": cid, "name": name, "stage": stage, "io": io,
                          "source": source, "score": round(score, 3),
                          "why": (desc or "")[:120]}
    try:
        import capability_map
        for c in capability_map.load()["capabilities"]:
            # skills INSTALADAS (experimentadas de verdade) valem mais que registro de catálogo
            base = 1.3 if c["kind"] == "installed-skill" else 1.0
            add(c["id"], c["name"], f"{c['description']} {c['triggers']}",
                c.get("io") or {}, "capability_map", score=base)
    except Exception:
        pass
    try:
        import attraction_graph
        exp = attraction_graph.equip_for(challenge, budget=14)
        for m in exp.get("members", []):
            add(m["id"], m["id"].split(":")[-1], m["id"], {}, "attraction_graph",
                score=1.1 + m.get("score", 0))
    except Exception:
        pass
    try:
        import curated
        for dom, skills in curated.load()["domains"].items():
            for s in skills:
                add(f"skill:{s['id']}", s["id"].split("/")[-1],
                    f"{dom} {s.get('use_when', '')}",
                    {"send": "a necessidade descrita em use_when",
                     "receive": "orientação/artefato da skill",
                     "apply_when": s.get("use_when", "")},
                    "curated", score=1.2)
    except Exception:
        pass
    # learning: o comprovado sobe, o rebaixado SAI (a persona aprende sua rotina)
    try:
        import learning
        for cid in list(cands):
            sc = learning.score("capability", cid, "routine")
            if sc["status"] == "DEMOTED":
                del cands[cid]
            elif sc["status"] == "PROMOTED":
                cands[cid]["score"] += 1.0
                cands[cid]["proven"] = f"{sc['mean']:.2f} (n={sc['n']})"
    except Exception:
        pass
    return list(cands.values())


def compose(challenge, agent_id=None, per_stage=1):
    """Monta o FLUXO: para cada estágio presente no desafio, a melhor capacidade candidata,
    com O QUE ENVIAR (recebendo o handoff do passo anterior) e O QUE RECEBER (o handoff que
    alimenta o próximo). MCPs relevantes anexados. Estágios sem candidato viram GAPS honestos
    (alimentam a cascata de descoberta, nunca inventam ferramenta)."""
    cands = _candidates(challenge)
    by_stage = {}
    for c in sorted(cands, key=lambda x: -x["score"]):
        by_stage.setdefault(c["stage"], []).append(c)
    steps, gaps, prev_handoff = [], [], "o desafio original do usuário"
    order = 0
    for stage, _ in STAGES:
        picks = by_stage.get(stage, [])[:per_stage]
        if not picks:
            # research/verify sempre têm dono nativo; os demais são gap honesto se vazios
            if stage in ("design", "marketing", "frontend", "backend", "performance"):
                gaps.append({"stage": stage,
                             "action": "descoberta em cascata (nativo -> skills.sh -> GitHub) + H5"})
            continue
        for p in picks:
            order += 1
            io = p.get("io") or {}
            steps.append({
                "order": order, "stage": stage, "capability": p["id"],
                "why": p.get("proven") and f"COMPROVADA {p['proven']} — {p['why']}" or p["why"],
                "send": f"{prev_handoff}" + (f" | formato: {io['send']}" if io.get("send") else ""),
                "receive": io.get("receive") or STAGE_HANDOFF[stage],
                "feeds_next": STAGE_HANDOFF[stage],
                "source": p["source"],
            })
            prev_handoff = STAGE_HANDOFF[stage]
    mcps = []
    try:
        import asset_manager
        mcps = [i for _, kind, i, _x in asset_manager.route(challenge, k=5) if kind == "mcp"][:3]
    except Exception:
        pass
    rid = f"routine-{abs(hash((agent_id or '*', challenge[:80]))) % 10**8:08d}"
    return {"id": rid, "agent_id": agent_id, "challenge": challenge[:200],
            "steps": steps, "gaps": gaps, "mcps": mcps,
            "how_to_run": ("execute os passos NA ORDEM; o `receive` de cada passo é o `send` "
                           "do seguinte; um passo que falhar 2x vira vacina + gap de descoberta"),
            "composed_at": time.time()}


# ── persistência por persona (viaja no swap plug-and-play) ───────────────────────────────────
def load_routines():
    try:
        with open(_routines_path(), encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except Exception:
        return []


def save_routine(routine):
    """Guarda a rotina da persona (id estável por persona+desafio; regravar atualiza)."""
    routines = [r for r in load_routines() if r.get("id") != routine.get("id")]
    routines.append(routine)
    try:
        with open(_routines_path(), "w", encoding="utf-8") as f:
            json.dump(routines, f, ensure_ascii=False, indent=1)
        return {"status": "OK", "count": len(routines)}
    except Exception as e:
        return {"status": "ERROR", "reason": str(e)[:120]}


def best_routine(agent_id, challenge):
    """A rotina salva mais parecida com o desafio (a persona REUTILIZA o que já funcionou);
    None quando nada casa — aí compose() cria uma nova."""
    words = set(re.findall(r"[a-zà-ÿ0-9]{3,}", (challenge or "").lower()))
    best, best_s = None, 0.0
    for r in load_routines():
        if agent_id and r.get("agent_id") not in (None, agent_id):
            continue
        rw = set(re.findall(r"[a-zà-ÿ0-9]{3,}", r.get("challenge", "").lower()))
        s = len(words & rw) / (len(words | rw) or 1)
        # rotinas comprovadas ganham prioridade
        try:
            import learning
            sc = learning.score("routine", r["id"], "general")
            if sc["status"] == "PROMOTED":
                s += 0.3
            elif sc["status"] == "DEMOTED":
                continue
        except Exception:
            pass
        if s > best_s:
            best, best_s = r, s
    return best if best_s >= 0.25 else None


def record_routine_outcome(routine_id, success, evidence=None):
    """Resultado REAL de rodar a rotina -> promoção/rebaixamento beta-binomial durável."""
    try:
        import learning
        return learning.record_outcome("routine", routine_id, "general", bool(success),
                                       evidence=evidence)
    except Exception as e:
        return {"status": "ERROR", "reason": str(e)[:80]}


def record_feedback(agent_id, feedback):
    """AUDITORIAS de outros LLMs e FEEDBACK do usuário potencializam a persona: pontos fortes
    confirmam capacidades (outcome positivo), fracos/gaps geram sugestões de unequip/descoberta
    (H5 decide — nada equipa/desequipa sozinho), e tudo vira memória com proveniência.
    feedback = {source, strengths[], weaknesses[], gaps[], improvements[], user_positive bool}."""
    out = {"remembered": 0, "confirmed": [], "suggest_unequip": [], "suggest_discover": []}
    try:
        import memory
        st = memory.MemoryStore()
        for k in ("strengths", "weaknesses", "gaps", "improvements"):
            for item in feedback.get(k, []):
                st.remember(f"[feedback:{k}] {agent_id}: {item} (fonte: {feedback.get('source','?')})",
                            "episodic")
                out["remembered"] += 1
        st.record_event("agent_feedback", agent_id,
                        "positive" if feedback.get("user_positive") else "review",
                        {"source": feedback.get("source", "?")})
    except Exception:
        pass
    try:
        import learning
        learning.record_outcome("persona", agent_id, feedback.get("domain", "general"),
                                bool(feedback.get("user_positive")))
    except Exception:
        pass
    for s in feedback.get("strengths", []):
        cap = _capability_in(s)
        if cap:
            try:
                import learning
                learning.record_outcome("capability", cap, "routine", True)
            except Exception:
                pass
            out["confirmed"].append(cap)
    for w in feedback.get("weaknesses", []):
        cap = _capability_in(w)
        if cap:
            out["suggest_unequip"].append({"capability": cap,
                                           "action": f"agent_spawn.unequip({agent_id!r}, {cap!r}) — após revisão (H5)"})
    for g in feedback.get("gaps", []):
        out["suggest_discover"].append({"gap": g,
                                        "action": "gravity.plan / skills_sh -> STAGED + aprovação H5"})
    return out


def _capability_in(text):
    """Acha uma capacidade citada num item de feedback — procura no capability_map (instaladas/
    ferramentas) E no catálogo curado (skills por domínio); vence o nome mais específico."""
    tl = (text or "").lower()
    best_id, best_len = None, 0

    def consider(name, cid):
        nonlocal best_id, best_len
        n = (name or "").lower()
        if len(n) >= 4 and n in tl and len(n) > best_len:
            best_id, best_len = cid, len(n)
    try:
        import capability_map
        for c in capability_map.load()["capabilities"]:
            consider(c["name"], c["id"])
    except Exception:
        pass
    try:
        import curated
        for dom, skills in curated.load()["domains"].items():
            for s in skills:
                consider(s["id"].split("/")[-1], f"skill:{s['id']}")
    except Exception:
        pass
    return best_id


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    ch = " ".join(sys.argv[1:]) or ("criar uma landing page de alta conversão, design não-genérico, "
                                    "com transições css, dados em sql e performance responsiva")
    r = compose(ch, agent_id="ui-designer")
    print(f"DESAFIO: {r['challenge']}\nFLUXO ({len(r['steps'])} passos):")
    for s in r["steps"]:
        print(f"  {s['order']}. [{s['stage']:11}] {s['capability']}")
        print(f"      envia : {s['send'][:100]}")
        print(f"      recebe: {s['receive'][:100]}")
    if r["gaps"]:
        print("GAPS (descoberta + H5):", [g["stage"] for g in r["gaps"]])
    if r["mcps"]:
        print("MCPs:", r["mcps"])
