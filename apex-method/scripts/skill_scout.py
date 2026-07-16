#!/usr/bin/env python3
"""
skill_scout.py — Discover, evaluate, and STAGE an external skill (safe).

WHY THIS EXISTS:
  "Find a skill on a directory -> evaluate -> know when to use it" is useful, but
  silently installing/running internet code is a supply-chain risk. This does the
  safe version: fetch (allowlist only) -> parse -> AST security scan -> STAGE with
  an explicit approval gate. It never installs or executes fetched code.

SECURITY NOTE (autopsy fix v1.1.0):
  The previous scanner only flagged exec()/eval() and non-whitelisted imports, so
  `import os; os.system(...)`, `__import__(...)`, and `getattr(os,'system')(...)`
  slipped through. This version also flags dangerous *attribute* calls and unsafe
  builtins, and no longer whitelists `os`/`subprocess` wholesale. It is a
  best-effort static gate, NOT a sandbox — the human approval gate is the real
  safety boundary.

WHAT IF IT FAILS:
  - host not on allowlist -> {"status":"REFUSED_HOST"}
  - scan finds danger      -> {"status":"REJECTED_UNSAFE", reasons:[...]}
  - network blocked        -> {"status":"OFFLINE"}
"""
import ast, json, sys, re
import urllib.request

ALLOWLIST_HOSTS = ("raw.githubusercontent.com",)  # raw only: github.com/blob returns HTML
IMPORT_WHITELIST = {
    "json", "math", "re", "time", "typing", "dataclasses", "collections",
    "itertools", "functools", "datetime", "random", "statistics", "statsmodels",
    "numpy", "pandas", "sklearn", "scipy", "sympy", "matplotlib",
    "argparse", "__future__", "warnings", "enum", "abc", "decimal", "fractions",
}
# HARD REJECT — unambiguous code-exec / RCE vectors
REJECT_BUILTINS = {"exec", "eval", "compile", "__import__"}
REJECT_ATTRS = {"system", "popen", "spawn", "spawnl", "spawnv", "execl", "execv",
                "execve", "urlopen", "urlretrieve", "connect", "fork", "socket"}
# `.loads()` is only an RCE vector on deserializers — json.loads is ubiquitous and benign.
# Audit fix v1.17.0: loads/load are REJECTED only on these receivers; otherwise reviewed.
DESERIALIZER_RECEIVERS = {"pickle", "marshal", "dill", "shelve", "cPickle", "joblib", "yaml"}
# REVIEW — often benign (list.remove, dataclass vars, subprocess wrappers) but worth a look
REVIEW_BUILTINS = {"getattr", "setattr", "delattr", "globals", "locals", "vars", "input"}
REVIEW_ATTRS = {"remove", "rmdir", "unlink", "rename", "chmod", "kill", "run",
                "call", "check_output", "Popen", "load", "loads"}


def _host_ok(url: str) -> bool:
    return any(url.startswith(f"https://{h}/") for h in ALLOWLIST_HOSTS)


def fetch_text(url: str, timeout: int = 10, max_bytes: int = 2_000_000) -> str:
    if not _host_ok(url):
        raise ValueError(f"host not on allowlist (raw.githubusercontent only): {url}")
    with urllib.request.urlopen(url, timeout=timeout) as r:
        # audit fix v1.17.0: a redirect can leave the allowlist — re-check the FINAL url
        if not _host_ok(r.geturl()):
            raise ValueError(f"redirect left the allowlist: {r.geturl()}")
        return r.read(max_bytes).decode("utf-8", errors="replace")


def ast_security_scan(code: str) -> dict:
    """Two-tier static scan. 'reject' = RCE vectors (block). 'review' = often-benign
    (list.remove, dataclass vars, subprocess wrappers) — inspect with context.
    safe=True only when there are no reject reasons AND no non-whitelisted imports."""
    reject, review = [], []
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return {"safe": False, "reject": [f"syntax error: {e}"], "review": [], "reasons": [f"syntax error: {e}"]}
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id in REJECT_BUILTINS:
                reject.append(f"dangerous builtin {node.func.id}() (line {node.lineno})")
            elif node.func.id in REVIEW_BUILTINS:
                review.append(f"{node.func.id}() (line {node.lineno})")
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            recv = node.func.value.id if isinstance(node.func.value, ast.Name) else None
            if node.func.attr in REJECT_ATTRS:
                reject.append(f"dangerous call .{node.func.attr}() (line {node.lineno})")
            elif node.func.attr in ("load", "loads") and recv in DESERIALIZER_RECEIVERS:
                reject.append(f"deserializer {recv}.{node.func.attr}() (line {node.lineno})")
            elif node.func.attr in REVIEW_ATTRS:
                review.append(f".{node.func.attr}() (line {node.lineno})")
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            mods = ([a.name for a in node.names] if isinstance(node, ast.Import)
                    else [node.module or ""])
            for m in mods:
                top = m.split(".")[0]
                if top and top not in IMPORT_WHITELIST:
                    review.append(f"import outside whitelist: {top} (line {node.lineno})")
    # AUD-004 fix: the docstring promises "safe=True only when there are no reject reasons AND no
    # non-whitelisted imports", but the code was `safe = not reject` — it ignored imports, so code
    # that `import subprocess` or `import os` (getattr-obfuscated os.system) returned safe=True.
    # Honour the documented contract: a non-whitelisted import also makes it NOT auto-safe.
    non_whitelisted_imports = [r for r in review if r.startswith("import outside whitelist")]
    return {"safe": not reject and not non_whitelisted_imports,
            "reject": sorted(set(reject)), "review": sorted(set(review)),
            "reasons": sorted(set(reject))}  # 'reasons' kept for back-compat


def parse_skill_md(md: str) -> dict:
    fm = {}
    m = re.match(r"^---\s*\n(.*?)\n---", md, re.S)
    if m:
        for line in m.group(1).splitlines():
            if ":" in line and not line.startswith((" ", "-")):
                k, v = line.split(":", 1)
                fm[k.strip()] = v.strip().strip('"')
    sections = re.findall(r"^#{1,3}\s+(.+)$", md, re.M)
    return {"name": fm.get("name", "?"), "kind": fm.get("kind", "?"),
            "version": fm.get("version", "?"), "description": fm.get("description", "")[:200],
            "sections": sections[:15],
            "has_when_to_use": any("when" in s.lower() or "trigger" in s.lower() for s in sections)
                               or "use when" in md.lower(),
            "has_scope_limits": any("scope" in s.lower() or "limitation" in s.lower() for s in sections)}


def evaluate(skill_md_url: str, code_urls: list = None) -> dict:
    result = {"source": skill_md_url, "status": "STAGED", "checks": {}}
    try:
        md = fetch_text(skill_md_url)
    except ValueError as e:
        return {"source": skill_md_url, "status": "REFUSED_HOST", "reason": str(e)}
    except Exception as e:
        return {"source": skill_md_url, "status": "OFFLINE", "reason": str(e)[:120]}

    meta = parse_skill_md(md)
    result["meta"] = meta
    result["checks"]["structure_ok"] = meta["name"] != "?" and bool(meta["description"])
    result["checks"]["documents_triggers"] = meta["has_when_to_use"]
    result["checks"]["documents_scope"] = meta["has_scope_limits"]

    scan_reasons = []
    for cu in (code_urls or []):
        try:
            scan = ast_security_scan(fetch_text(cu))
            if not scan["safe"]:
                scan_reasons += [f"{cu}: {r}" for r in scan["reasons"]]
        except Exception as e:
            scan_reasons.append(f"{cu}: could not scan ({str(e)[:60]})")
    result["checks"]["ast_security"] = "PASS" if not scan_reasons else "FAIL"
    if scan_reasons:
        result["status"] = "REJECTED_UNSAFE"
        result["reasons"] = scan_reasons

    # trust tier (idea adopted from vercel-labs find-skills): prefer official owners.
    result["checks"]["trust_tier"] = trust_tier(skill_md_url)

    result["snapshot_entry"] = {
        "id": meta["name"], "source": skill_md_url, "kind": meta["kind"],
        "use_when": meta["description"][:120], "status": result["status"],
        "trust_tier": result["checks"]["trust_tier"],
        "gate": "requires explicit user approval before install/run",
    }
    return result


# owners the find-skills convention treats as first-party / pre-trusted (still AST-scanned).
OFFICIAL_OWNERS = ("anthropics", "anthropic-ai", "vercel-labs", "vercel", "openai",
                   "modelcontextprotocol", "thiagofernandes1987-create")


def trust_tier(url: str) -> str:
    """OFFICIAL if the raw URL's owner is a known first-party org, else COMMUNITY.
    Never a substitute for the AST scan + H5 approval — just a ranking signal."""
    m = re.match(r"https://raw\.githubusercontent\.com/([^/]+)/", url or "")
    owner = m.group(1).lower() if m else ""
    return "OFFICIAL" if owner in OFFICIAL_OWNERS else "COMMUNITY"


if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else \
        "https://raw.githubusercontent.com/anthropics/skills/main/README.md"
    print(json.dumps(evaluate(url), indent=2))
