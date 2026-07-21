#!/usr/bin/env python3
"""Smoke test do APEX MCP Server: handshake + tools/list + chamadas de leitura,
gate H5 em mutação sem aprovação, e equip aprovado. Roda o server como subprocesso
stdio real (o mesmo transporte que um cliente MCP usa)."""
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))


def rpc(proc, msg):
    proc.stdin.write(json.dumps(msg) + "\n")
    proc.stdin.flush()
    line = proc.stdout.readline()
    return json.loads(line)


def tool_result(resp):
    return json.loads(resp["result"]["content"][0]["text"])


def main():
    env = dict(os.environ, APEX_METHOD_HOME=tempfile.mkdtemp(prefix="apexmcp_"))
    proc = subprocess.Popen([sys.executable, os.path.join(HERE, "server.py")],
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            text=True, env=env)
    try:
        r = rpc(proc, {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
        assert r["result"]["serverInfo"]["name"] == "apex-mcp-server", r
        print("initialize        OK", r["result"]["protocolVersion"])

        r = rpc(proc, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        names = [t["name"] for t in r["result"]["tools"]]
        assert "apex_classify" in names and "apex_equip" in names, names
        print(f"tools/list        OK ({len(names)} tools)")

        r = rpc(proc, {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                       "params": {"name": "apex_classify",
                                  "arguments": {"task": "criar landing page com glassmorphism"}}})
        c = tool_result(r)
        assert c["domain"] == "software" and c["subdomain"] == "frontend", c
        print("apex_classify     OK", {k: c[k] for k in ("domain", "subdomain", "intent")})

        r = rpc(proc, {"jsonrpc": "2.0", "id": 4, "method": "tools/call",
                       "params": {"name": "apex_triage",
                                  "arguments": {"task": "corrigir typo no README"}}})
        t = tool_result(r)
        assert t["mode"] in ("EXPRESS", "STANDARD"), t
        print("apex_triage       OK mode =", t["mode"])

        r = rpc(proc, {"jsonrpc": "2.0", "id": 5, "method": "tools/call",
                       "params": {"name": "apex_equip",
                                  "arguments": {"skill": "css3-advanced",
                                                "agents": ["engineer"]}}})
        b = tool_result(r)
        assert b.get("status") == "BLOCKED", b
        print("apex_equip (H5)   OK — BLOCKED sem approved=true")

        r = rpc(proc, {"jsonrpc": "2.0", "id": 6, "method": "tools/call",
                       "params": {"name": "apex_equip",
                                  "arguments": {"skill": "css3-advanced",
                                                "agents": ["engineer"], "approved": True}}})
        g = tool_result(r)
        assert g.get("status") != "BLOCKED", g
        print("apex_equip        OK — grant aprovado:", str(g)[:80])

        r = rpc(proc, {"jsonrpc": "2.0", "id": 7, "method": "tools/call",
                       "params": {"name": "apex_trace_evaluate", "arguments": {}}})
        print("apex_trace_eval   OK", str(tool_result(r))[:60])

        # KB compartilhada (v1.63)
        r = rpc(proc, {"jsonrpc": "2.0", "id": 8, "method": "tools/call",
                       "params": {"name": "apex_kb_popularity", "arguments": {}}})
        pop = tool_result(r)
        assert "skills_per_discipline" in pop and pop["skills_per_discipline"], pop
        print("apex_kb_popularity OK", list(pop["skills_per_discipline"])[:4])

        r = rpc(proc, {"jsonrpc": "2.0", "id": 9, "method": "tools/call",
                       "params": {"name": "apex_kb_ranking", "arguments": {"discipline": "security"}}})
        assert "ranking" in tool_result(r), tool_result(r)
        print("apex_kb_ranking   OK")

        r = rpc(proc, {"jsonrpc": "2.0", "id": 10, "method": "tools/call",
                       "params": {"name": "apex_kb_load_state", "arguments": {}}})
        assert tool_result(r).get("status") == "BLOCKED", tool_result(r)
        print("apex_kb_load_state OK — BLOCKED sem approved=true")

        print("\nSMOKE TEST: 10/10 PASS")
        return 0
    finally:
        proc.terminate()


if __name__ == "__main__":
    sys.exit(main())
