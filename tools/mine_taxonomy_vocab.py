#!/usr/bin/env python3
"""mine_taxonomy_vocab.py — gera apex-method/catalog/taxonomy_extra_seed.json.

Duas fontes:
1. MINERAÇÃO do scorecard OpenClaw (taxonomia de subsistemas de agent-infra): surfaces →
   categories → features + search_anchors viram vocabulário EN por facet (agent-infra,
   observability, automation, media, cli/devops, security).
2. PACOTE CURADO PT+EN para os gaps PROVADOS empiricamente na auditoria v1.62
   (exp_final.py): frontend/web ("landing page", "glassmorphism" → domain None),
   edições incrementais triviais (typo/cor → DEEP), e devops/docs cotidianos.

O seed é mesclado nas tabelas-base por taxonomy.py em import-time (determinístico,
stdlib-only, fallback silencioso). Regenerar: python3 tools/mine_taxonomy_vocab.py <scorecard.yaml>
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "apex-method", "catalog", "taxonomy_extra_seed.json")

# surface-id do OpenClaw → (axis, facet) do APEX
SURFACE_MAP = {
    "gateway-runtime": ("subdomain", "agent-infra"),
    "agent-runtime-and-provider-execution": ("subdomain", "agent-infra"),
    "session-memory-and-context-engine": ("subdomain", "agent-infra"),
    "channel-framework": ("subdomain", "agent-infra"),
    "plugin-sdk-and-bundled-plugin-architecture": ("subdomain", "agent-infra"),
    "browser-automation-and-exec-sandbox-tools": ("subdomain", "automation"),
    "automation-cron-hooks-tasks-polling": ("subdomain", "automation"),
    "telemetry-diagnostics-and-observability": ("subdomain", "observability"),
    "security-auth-pairing-and-secrets": ("domain", "security"),
    "cli-install-update-onboard-doctor": ("subdomain", "devops"),
    "media-understanding-and-media-generation": ("domain", "data-ai"),
    "browser-control-ui-and-webchat": ("subdomain", "frontend"),
}

STOP = {
    "and", "the", "for", "with", "from", "into", "over", "via", "when", "that", "this",
    "are", "can", "all", "its", "not", "between", "matrix", "feature", "features",
    "behavior", "controls", "control", "management", "handling", "support", "supported",
    "core", "basic", "general", "misc", "other", "path", "paths", "flow", "flows",
    "mode", "modes", "setup", "status", "note", "notes", "docs", "index",
}

# termos genéricos demais para virarem trigger de UM facet (colidiriam com tudo)
TOO_GENERIC = {
    "api", "apis", "http", "json", "yaml", "file", "files", "user", "users", "data",
    "model", "models", "message", "messages", "commands", "command", "actions", "action",
    "tool", "tools", "test", "tests", "testing", "config", "configuration", "state",
    "service", "services", "system", "runtime", "execution", "request", "response",
    "live", "local", "remote", "external", "internal", "policy", "access", "delivery",
    "history", "list", "lookup", "text", "web", "code", "errors", "error",
}

CURATED = {
    "domain": {
        # gap provado (Round 3 debug v1.62): "integrar sistema de EDOs com RK4" caía em
        # software porque "sistema" batia lá e nada batia mathematics no eixo DOMAIN — os
        # termos numéricos existiam só no subdomain. Elevados ao domain para vencer o eixo.
        "mathematics": [
            "rk4", "runge-kutta", "runge", "kutta", "euler", "edo", "edos", "ode", "odes",
            "oscilador", "oscillator", "harmônico", "harmonico", "harmonic", "integrador",
            "convergência", "convergencia", "convergence", "numérico", "numerico", "numerical",
            "equações", "equacoes", "diferenciais", "differential", "interpolação",
            "interpolacao", "interpolation", "matriz", "matrix", "autovalor", "eigenvalue",
        ],
        # gap provado: "criar landing page com glassmorphism" classificava domain=None
        "software": [
            "landing", "website", "webapp", "css", "html", "html5", "css3", "javascript",
            "typescript", "js", "página", "pagina", "page", "site", "botão", "botao",
            "button", "formulário", "formulario", "form", "menu", "navbar", "header",
            "footer", "animação", "animacao", "animation", "animações", "animacoes",
            "framework", "biblioteca", "library", "git", "repositório", "repositorio",
            "repository", "readme", "documentação", "documentacao", "documentation",
        ],
    },
    "subdomain": {
        "frontend": [
            "landing", "glassmorphism", "parallax", "svg", "gradiente", "gradient",
            "animação", "animacao", "animation", "animações", "animacoes", "transição",
            "transicao", "transition", "keyframes", "hover", "scroll", "hero", "cta",
            "botão", "botao", "button", "tailwind", "bootstrap", "flexbox", "grid",
            "tipografia", "typography", "fonte", "font", "cor", "cores", "color",
            "colors", "tema", "theme", "dark-mode", "página", "pagina", "webpage",
            "html", "html5", "css3", "sass", "styling", "estilo", "estilos",
        ],
        "agent-infra": [
            "agent", "agente", "agentes", "subagent", "subagente", "orchestrator",
            "orquestrador", "llm", "prompt", "prompts", "mcp", "skill", "skills",
            "persona", "roteador", "router", "spawn", "contexto", "context-window",
            "tokens", "token-budget", "tool-call", "tool-calling", "function-calling",
        ],
        "automation": [
            "automation", "automação", "automacao", "cron", "webhook", "webhooks",
            "hook", "hooks", "scheduler", "agendamento", "polling", "playwright",
            "selenium", "headless", "scraping", "raspagem", "bot", "rpa", "workflow",
        ],
        "observability": [
            "telemetry", "telemetria", "tracing", "trace", "span", "métricas",
            "metricas", "metrics", "logging", "logs", "monitoring", "monitoramento",
            "observability", "observabilidade", "opentelemetry", "otel", "dashboards",
            "alertas", "alerting", "diagnostics", "diagnóstico", "profiling",
        ],
        "devops": [
            "devops", "ci", "cd", "ci-cd", "docker", "dockerfile", "container",
            "kubernetes", "k8s", "helm", "terraform", "ansible", "deploy",
            "deployment", "release", "rollback", "installer", "instalação",
            "instalacao", "onboarding", "upgrade", "update", "versioning", "cli",
        ],
        "docs": [
            "readme", "changelog", "documentação", "documentacao", "documentation",
            "tutorial", "guia", "guide", "manual", "wiki", "comentário", "comentario",
            "docstring", "spec", "especificação", "especificacao",
        ],
    },
    "intent": {
        "audit": ["auditar", "audite", "audita"],
        "build": ["adicionar", "adicione", "add", "insira", "inserir", "incluir",
                  "inclua", "remover", "remova", "remove", "excluir", "exclua",
                  "delete", "integrar", "integre", "integrate", "montar", "monte"],
        # gap provado: "ajustar cor do botão" / "corrigir typo" → UNKNOWN_CLASS → DEEP
        "fix_small": [
            "typo", "ajustar", "ajuste", "corrigir", "correção", "correcao", "conserte",
            "conserta", "fix", "renomear", "renomeie", "rename", "trocar", "troque",
            "swap", "mudar", "mude", "change", "atualizar", "atualize", "tweak",
            "pequeno", "pequena", "small", "minor", "simples", "rápido", "rapido",
        ],
        "explain": [
            "explicar", "explique", "explain", "entender", "understand", "como",
            "how", "why", "porque", "por-que", "what", "resumir", "resuma",
            "summarize", "sumarize", "descreva", "describe",
        ],
    },
    "platform": {
        "web": ["landing", "webpage", "webapp", "frontend", "html", "css", "dom",
                "responsivo", "responsive", "seo"],
    },
}


# denylist final: sobreviveram aos filtros estatísticos mas são genéricos demais
# (uma colisão de trigger genérico contamina o TOP-facet do eixo)
FINAL_DENY = {
    "account", "check", "client", "codes", "abort", "assistant", "failure", "dynamic",
    "critical", "fields", "duplicate", "inputs", "reference", "analysis", "announce",
    "background", "availability", "automatic", "ambient", "activation", "admin",
    "challenge", "hygiene", "sender", "drift", "bundle", "activity", "audit",
    "backend", "backends", "canvas", "generation", "attachment", "outputs",
}

# -ing técnicos que sobrevivem ao filtro morfológico
ING_WHITELIST = {
    "streaming", "tracing", "logging", "polling", "onboarding", "pairing", "sandboxing",
    "scheduling", "routing", "caching", "scaling", "embedding", "prompting", "tooling",
    "provisioning", "monitoring", "profiling", "batching", "sharding", "chunking",
}


def _tokens(name):
    out = []
    for t in re.split(r"[^a-z0-9-]+", name.lower()):
        t = t.strip("-")
        if len(t) < 3 or t.isdigit() or t in STOP or t in TOO_GENERIC:
            continue
        # filtro morfológico: particípios/advérbios/gerúndios genéricos poluem a classificação
        if t.endswith(("ed", "ly")) or (t.endswith("ing") and t not in ING_WHITELIST):
            continue
        out.append(t)
    return out


def mine(scorecard_path):
    """Extract per-facet vocabulary from the OpenClaw maturity scorecard.

    Anti-ruído: (a) frequência mínima 2 dentro da surface (termo temático, não incidental);
    (b) filtro de DF no corpus — termo presente em >2 surfaces mapeadas é genérico demais
    para discriminar um facet e é descartado."""
    text = open(scorecard_path, encoding="utf-8", errors="ignore").read()
    per_surface = {}   # sid -> {token: count}
    surface_blocks = re.split(r"\n  - id: ", text)
    for block in surface_blocks[1:]:
        sid = block.split("\n", 1)[0].strip()
        if sid not in SURFACE_MAP:
            continue
        counts = per_surface.setdefault(sid, {})
        harvest = []
        for m in re.finditer(r"^\s+- name: (.+)$", block, re.M):
            harvest.append(m.group(1))
        for m in re.finditer(r"^\s+id: ([a-z0-9-]+)$", block, re.M):
            harvest.append(m.group(1))
        for m in re.finditer(r'^\s+- "?([a-z][a-z0-9 :\-]{4,80})"?$', block, re.M):
            harvest.append(m.group(1))
        for name in harvest:
            for t in _tokens(name):
                counts[t] = counts.get(t, 0) + 1
    # document frequency across mapped surfaces
    df = {}
    for counts in per_surface.values():
        for t in counts:
            df[t] = df.get(t, 0) + 1
    mined = {}
    for sid, counts in per_surface.items():
        axis, facet = SURFACE_MAP[sid]
        vocab = mined.setdefault(axis, {}).setdefault(facet, set())
        for t, c in counts.items():
            if c >= 2 and df[t] <= 2 and t not in FINAL_DENY:
                vocab.add(t)
    return mined


def main():
    seed = {axis: {facet: set(terms) for facet, terms in facets.items()}
            for axis, facets in CURATED.items()}
    if len(sys.argv) > 1 and os.path.exists(sys.argv[1]):
        mined = mine(sys.argv[1])
        for axis, facets in mined.items():
            for facet, terms in facets.items():
                seed.setdefault(axis, {}).setdefault(facet, set()).update(terms)
        src = os.path.basename(sys.argv[1])
    else:
        src = None
    out = {"_source": {"curated": "auditoria v1.62 (exp_final.py gaps)",
                       "mined": src or "not provided"},
           **{axis: {facet: sorted(terms) for facet, terms in sorted(facets.items())}
              for axis, facets in seed.items()}}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    n = sum(len(t) for facets in seed.values() for t in facets.values())
    print(f"[mine_taxonomy_vocab] {n} termos → {os.path.relpath(OUT, ROOT)}")
    for axis, facets in seed.items():
        print(f"  {axis}: " + ", ".join(f"{k}({len(v)})" for k, v in sorted(facets.items())))


if __name__ == "__main__":
    main()
