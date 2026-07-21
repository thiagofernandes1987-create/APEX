#!/usr/bin/env python3
"""APEX MCP Server — expõe o kernel APEX como ferramentas MCP (stdio, stdlib-only).

A visão: o MCP torna as skills "parte do corpo" do APEX — qualquer cliente MCP
(Claude Code, IDEs, outros agentes) consulta memória/taxonomia/cache e EQUIPA ou
DESEQUIPA skills nos agentes, com a mesma governança de dentro do kernel.

Protocolo: MCP 2024-11-05 sobre stdio (JSON-RPC 2.0, Content-Length framing NÃO é
usado — newline-delimited JSON, o formato do transporte stdio do MCP).

Governança (H5 preservada): ferramentas de LEITURA são livres; ferramentas que MUTAM
estado (equip/unequip/record) exigem `approved: true` explícito na chamada — a
aprovação humana continua sendo a fronteira real, exatamente como dentro do kernel
(`agent_registry.grant_skill` retorna BLOCKED sem aprovação).

Uso (Claude Code):
  claude mcp add apex -- python3 /caminho/para/APEX/integrations/apex-mcp-server/server.py
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.normpath(os.path.join(HERE, "..", "..", "apex-method", "scripts"))
sys.path.insert(0, SCRIPTS)

PROTOCOL = "2024-11-05"
SERVER_INFO = {"name": "apex-mcp-server", "version": "1.62.0"}

TOOLS = [
    {"name": "apex_classify",
     "description": "Classifica uma tarefa nos facets canônicos do APEX (domain/subdomain/intent/platform, PT+EN). Use antes de rotear ou cachear.",
     "inputSchema": {"type": "object", "properties": {"task": {"type": "string"}},
                     "required": ["task"]}},
    {"name": "apex_triage",
     "description": "Triage do APEX: decide o modo de operação mais leve que serve (EXPRESS/STANDARD/DEEP...) com razões. Token economy + escalação.",
     "inputSchema": {"type": "object", "properties": {"task": {"type": "string"}},
                     "required": ["task"]}},
    {"name": "apex_resolution_check",
     "description": "Cache de resolução híbrido: verifica se um problema similar já foi resolvido e validado (short-circuit com re-verify). Tier 'prior' ou 'facet'.",
     "inputSchema": {"type": "object", "properties": {"task": {"type": "string"}},
                     "required": ["task"]}},
    {"name": "apex_recall",
     "description": "Busca semântica na memória persistente do APEX (episódica+semântica, cross-session).",
     "inputSchema": {"type": "object", "properties": {"query": {"type": "string"},
                                                      "k": {"type": "integer", "default": 5}},
                     "required": ["query"]}},
    {"name": "apex_worked_for",
     "description": "Skills que JÁ resolveram problema similar (prior de atração com taxa de sucesso validada).",
     "inputSchema": {"type": "object", "properties": {"task": {"type": "string"},
                                                      "k": {"type": "integer", "default": 5}},
                     "required": ["task"]}},
    {"name": "apex_route",
     "description": "Roteia a tarefa para o melhor agente do roster APEX (213 personas) por relevância.",
     "inputSchema": {"type": "object", "properties": {"task": {"type": "string"}},
                     "required": ["task"]}},
    {"name": "apex_equip",
     "description": "EQUIPA uma skill em um agente (grant durável). MUTAÇÃO: exige approved=true (gate H5) — sem aprovação retorna BLOCKED.",
     "inputSchema": {"type": "object", "properties": {"skill": {"type": "string"},
                                                      "agents": {"type": "array", "items": {"type": "string"}},
                                                      "approved": {"type": "boolean", "default": False}},
                     "required": ["skill", "agents"]}},
    {"name": "apex_unequip",
     "description": "DESEQUIPA uma skill de um agente (revoga o grant durável). MUTAÇÃO: exige approved=true (gate H5).",
     "inputSchema": {"type": "object", "properties": {"skill": {"type": "string"},
                                                      "agent": {"type": "string"},
                                                      "approved": {"type": "boolean", "default": False}},
                     "required": ["skill", "agent"]}},
    {"name": "apex_learning_best",
     "description": "Melhores personas/skills validadas por domínio segundo o aprendizado durável (beta-binomial, PROMOTED/DEMOTED).",
     "inputSchema": {"type": "object", "properties": {"kind": {"type": "string", "default": "skill"},
                                                      "domain": {"type": "string", "default": "general"},
                                                      "k": {"type": "integer", "default": 5}},
                     "required": []}},
    {"name": "apex_trace_evaluate",
     "description": "Avaliação de uma execução pelo event bus (latência, cache, validação, módulos tocados). Sem trace_id lista os traces recentes.",
     "inputSchema": {"type": "object", "properties": {"trace_id": {"type": "string"}},
                     "required": []}},
    {"name": "apex_record_outcome",
     "description": "Registra o resultado VALIDADO de uma skill em um problema (alimenta o cache de resolução e o aprendizado). MUTAÇÃO: exige approved=true.",
     "inputSchema": {"type": "object", "properties": {"problem": {"type": "string"},
                                                      "skill": {"type": "string"},
                                                      "solved": {"type": "boolean"},
                                                      "approved": {"type": "boolean", "default": False}},
                     "required": ["problem", "skill", "solved"]}},
]


def _blocked(what):
    return {"status": "BLOCKED", "why": f"{what} é mutação de estado — exige approved=true "
                                        "(gate H5: aprovação humana explícita)"}


def call_tool(name, args):
    if name == "apex_classify":
        import taxonomy
        return taxonomy.classify(args["task"])
    if name == "apex_triage":
        import execution_policy
        return execution_policy.triage(args["task"])
    if name == "apex_resolution_check":
        import orchestrator
        rc = orchestrator.resolution_check(args["task"])
        return rc or {"path": "FULL_PIPELINE", "reason": "sem solução validada lembrada — rodar o pipeline"}
    if name == "apex_recall":
        import memory
        return {"hits": memory.MemoryStore().recall(args["query"], k=int(args.get("k", 5)))}
    if name == "apex_worked_for":
        import skill_ledger
        return {"skills": skill_ledger.worked_for(args["task"], k=int(args.get("k", 5)))}
    if name == "apex_route":
        import agent_registry
        return agent_registry.match_task_to_ext_agents(args["task"])
    if name == "apex_equip":
        if not args.get("approved"):
            return _blocked("equip")
        import agent_spawn
        return {"granted": [agent_spawn.equip(a, args["skill"], approved=True)
                            for a in args["agents"]]}
    if name == "apex_unequip":
        if not args.get("approved"):
            return _blocked("unequip")
        import agent_spawn
        return agent_spawn.unequip(args["agent"], args["skill"])
    if name == "apex_learning_best":
        import learning
        ls = learning.LearningStore()
        return {"best": ls.best(args.get("kind", "skill"), args.get("domain", "general"),
                                k=int(args.get("k", 5)))}
    if name == "apex_trace_evaluate":
        import event_bus
        tid = args.get("trace_id")
        return event_bus.evaluate(tid) if tid else {"recent": event_bus.recent_traces()}
    if name == "apex_record_outcome":
        if not args.get("approved"):
            return _blocked("record_outcome")
        import skill_ledger
        return {"recorded": skill_ledger.record(args["problem"], args["skill"],
                                                solved=bool(args["solved"]))}
    raise ValueError(f"unknown tool: {name}")


def handle(msg):
    mid, method = msg.get("id"), msg.get("method")
    params = msg.get("params") or {}
    if method == "initialize":
        return {"jsonrpc": "2.0", "id": mid,
                "result": {"protocolVersion": PROTOCOL, "serverInfo": SERVER_INFO,
                           "capabilities": {"tools": {}}}}
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": mid, "result": {"tools": TOOLS}}
    if method == "tools/call":
        try:
            out = call_tool(params.get("name"), params.get("arguments") or {})
            return {"jsonrpc": "2.0", "id": mid,
                    "result": {"content": [{"type": "text",
                                            "text": json.dumps(out, ensure_ascii=False, default=str)}]}}
        except Exception as e:
            return {"jsonrpc": "2.0", "id": mid,
                    "result": {"content": [{"type": "text",
                                            "text": json.dumps({"error": f"{type(e).__name__}: {e}"})}],
                               "isError": True}}
    if method == "ping":
        return {"jsonrpc": "2.0", "id": mid, "result": {}}
    if mid is None:          # notification (initialized etc.) — no response
        return None
    return {"jsonrpc": "2.0", "id": mid,
            "error": {"code": -32601, "message": f"method not found: {method}"}}


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        resp = handle(msg)
        if resp is not None:
            sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
