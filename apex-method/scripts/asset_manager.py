#!/usr/bin/env python3
"""
asset_manager.py — APEX manages & routes all mined assets.

WHY: the full APEX repo yields (a) APEX-native assets (UCO, UCO-Sensor) that are
nativized, and (b) 39 third-party assets + 18 MCP servers that are INDEXED (not copied).
This lets APEX list, filter, and route to any of them by need — with third-party items
always going through scout + approval before install/run.

WHAT IT IS NOT: it does not copy or execute third-party code. It manages references.

WHEN: Call at skill-resolution time to route a need across managed assets + MCPs.
WHAT IF IT FAILS: A missing catalog is skipped; route() returns [] and the caller falls back to the router/scout.
"""
import json, os, sys
HERE = os.path.dirname(__file__)
CAT = os.path.join(HERE, "..", "catalog")


def _load(name):
    try:
        return json.load(open(os.path.join(CAT, name), encoding="utf-8"))
    except Exception:
        return []


def managed(kind=None, type=None):
    items = _load("managed_assets.json")
    if kind:
        items = [i for i in items if i.get("asset_kind") == kind]
    if type:
        items = [i for i in items if i.get("type") == type]
    return items


def mcps(domain=None):
    items = _load("mcp_registry.json")
    if domain:
        items = [i for i in items if domain.lower() in i.get("domain", "").lower()]
    return items


def route(need, k=5):
    """Keyword-route a need across managed assets + MCPs (no sklearn dependency)."""
    need_l = need.lower()
    hits = []
    for i in managed():
        text = f"{i['id']} {i.get('asset_kind','')} {i.get('type','')}".lower()
        score = sum(w in text for w in need_l.split())
        if score:
            hits.append((score, "asset", i["id"], i["treatment"]))
    for m in mcps():
        text = f"{m['id']} {m.get('domain','')} {m.get('type','')}".lower()
        score = sum(w in text for w in need_l.split())
        if score:
            hits.append((score, "mcp", m["id"], m.get("domain", "")))
    hits.sort(reverse=True)
    return hits[:k]


def summary():
    m = managed()
    native = [x for x in m if x["type"] == "apex-native"]
    third = [x for x in m if x["type"] == "third-party"]
    return {"total_assets": len(m), "native": len(native), "third_party": len(third),
            "skill_collections": len([x for x in third if x["asset_kind"] == "skill-collection"]),
            "libraries": len([x for x in third if x["asset_kind"] == "library"]),
            "mcp_servers": len(mcps())}


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "route":
        for s, t, i, extra in route(" ".join(sys.argv[2:])):
            print(f"  [{t}] {i}  ({extra})")
    else:
        print(json.dumps(summary(), indent=2))
        print("\nAPEX-native:")
        for a in managed(type="apex-native"):
            print(f"  {a['id']}  ({a['skills']} skills, {a['py_files']} py) — {a['treatment']}")
