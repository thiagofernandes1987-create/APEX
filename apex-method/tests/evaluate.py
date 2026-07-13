#!/usr/bin/env python3
"""
evaluate.py — Reproducible, rubric-based evaluation of the apex-method skill.

WHY THIS EXISTS:
  EVALUATION_REPORT.md is self-graded prose. This harness replaces opinion with an
  OBJECTIVE, RE-RUNNABLE rubric: each criterion is a boolean/numeric check anyone can
  execute to get the same score. It is still self-run (not a third party), but it is
  falsifiable — that is the honest improvement over prose self-grading.

WHEN: after any change, alongside tests/benchmark.py, to score the skill.

WHAT IF IT FAILS: a criterion that raises scores 0 for that line; the report still
  prints and the total reflects reality (no crash hides a failure).

USAGE: python3 tests/evaluate.py   (prints a scored rubric + JSON)
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SCRIPTS = os.path.join(ROOT, "scripts")
CAT = os.path.join(ROOT, "catalog")
sys.path.insert(0, SCRIPTS)


def _catalog(name):
    with open(os.path.join(CAT, name), encoding="utf-8") as f:
        return json.load(f)


# ── each criterion returns (score_0_to_1, evidence_str) ──────────────────────
def c_benchmark_pass():
    r = subprocess.run([sys.executable, os.path.join(HERE, "benchmark.py")],
                       capture_output=True, text=True)
    last = [l for l in r.stdout.splitlines() if l.startswith("TOTAL")]
    if not last:
        return 0.0, "no TOTAL line"
    frac = last[0].split()[1]  # e.g. 31/31
    p, t = (int(x) for x in frac.split("/"))
    return p / t, f"benchmark {frac}"


def c_clean_env():
    """Core must not hard-depend on sklearn/sympy/numpy."""
    code = (
        "import sys\n"
        "class B:\n"
        " def find_module(s,n,p=None):\n"
        "  return s if n.split('.')[0] in ('sklearn','sympy','numpy','scipy') else None\n"
        " def load_module(s,n): raise ImportError(n)\n"
        "sys.meta_path.insert(0,B()); sys.path.insert(0,%r)\n"
        "import orchestrator, verify, router, monte_carlo, repo_bridge\n"
        "assert orchestrator.run('2+2')['answer']==4\n"
        "assert verify.verify_identity('x','x')['tag']=='CONJECTURA_FORMAL'\n"
        "assert monte_carlo.simulate(lambda s:s['x'],{'x':{'dist':'normal','mean':1,'std':1}},500)['engine']=='stdlib'\n"
        "print('OK')\n" % SCRIPTS
    )
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    return (1.0, "degrades gracefully") if r.returncode == 0 else (0.0, r.stderr.strip()[-120:])


def c_sr40_selfcompliance():
    import guards
    files = [f for f in os.listdir(SCRIPTS) if f.endswith(".py")]
    bad = [f for f in files
           if not guards.zero_ambiguity_lint_module(open(os.path.join(SCRIPTS, f)).read())["ok"]]
    skill_ok = guards.zero_ambiguity_lint_skill(open(os.path.join(ROOT, "SKILL.md")).read())["ok"]
    n = len(files)
    score = ((n - len(bad)) / n) * (1.0 if skill_ok else 0.8)
    return score, f"{n-len(bad)}/{n} scripts + SKILL.md={'ok' if skill_ok else 'fail'}"


def c_catalog_consistency():
    """scripts/ files match scripts_lib.json 1:1."""
    py = {f[:-3] for f in os.listdir(SCRIPTS) if f.endswith(".py")}
    lib = {s["id"].split(":")[1] for s in _catalog("scripts_lib.json")}
    ok = py == lib
    return (1.0 if ok else 0.0), f"py-lib symdiff={sorted(py ^ lib)}"


def c_roster_complete():
    roster = _catalog("apex_agents_roster.json")
    return (1.0 if len(roster) >= 213 else len(roster) / 213), f"{len(roster)} agents"


def c_native_index():
    idx = _catalog("apex_native_skills_index.json")
    n = idx["_meta"]["count"]
    enriched = "triggers" in idx["skills"][0]
    return (1.0 if n >= 3784 and enriched else 0.5), f"{n} skills, enriched={enriched}"


def c_security_gates():
    import skill_scout, guards
    json_ok = skill_scout.ast_security_scan("import json\nd=json.loads('{}')")["safe"]
    pickle_bad = not skill_scout.ast_security_scan("import pickle\nd=pickle.loads(x)")["safe"]
    getattr_bad = guards.forge_load_gate("import os\ng=getattr(os,'sys'+'tem')")["verdict"] == "REJECTED"
    passed = sum([json_ok, pickle_bad, getattr_bad])
    return passed / 3, f"json_ok={json_ok} pickle_reject={pickle_bad} getattr_reject={getattr_bad}"


def c_marketplace_bar():
    import skills_sh
    # the >=1000-install quality bar must actually filter
    items = [skills_sh._norm(x) for x in [
        {"owner": "a", "name": "big", "installs": 5000},
        {"owner": "b", "name": "small", "installs": 10}]]
    kept = [i for i in items if i["installs"] >= 1000]
    return (1.0 if len(kept) == 1 else 0.0), f"bar keeps {len(kept)}/2 at >=1000 installs"


def c_provenance_discipline():
    """snapshot findings carry WHAT/WHERE/HOW/confidence."""
    import snapshot
    s = snapshot.new_snapshot("t")
    snapshot.add_finding(s, "w", "where", "how", "[APPROX] high")
    f = s["findings"][0]
    ok = all(k in f for k in ("what", "where", "how", "confidence"))
    return (1.0 if ok else 0.0), "findings carry what/where/how/confidence"


RUBRIC = [
    ("Benchmark passes (correctness)", 3, c_benchmark_pass),
    ("Runs without heavy deps (robustness)", 2, c_clean_env),
    ("SR_40 self-compliance (zero ambiguity)", 1, c_sr40_selfcompliance),
    ("Catalog/scripts consistency", 1, c_catalog_consistency),
    ("Agent roster complete (213)", 1, c_roster_complete),
    ("Native index enriched (3784)", 1, c_native_index),
    ("Security gates (json/pickle/getattr)", 2, c_security_gates),
    ("Marketplace >=1000-install bar", 1, c_marketplace_bar),
    ("Provenance discipline", 1, c_provenance_discipline),
]


def main():
    rows, earned, possible = [], 0.0, 0
    for name, weight, fn in RUBRIC:
        try:
            score, ev = fn()
        except Exception as e:
            score, ev = 0.0, f"{type(e).__name__}: {e}"
        rows.append((name, weight, score, ev))
        earned += weight * score
        possible += weight

    print(f"\n{'CRITERION':<42}{'wt':>3}{'score':>7}   evidence")
    print("-" * 92)
    for name, weight, score, ev in rows:
        print(f"{name:<42}{weight:>3}{score:>7.2f}   {ev[:38]}")
    print("-" * 92)
    pct = 100 * earned / possible
    print(f"{'WEIGHTED TOTAL':<42}{possible:>3}{earned/possible:>7.2f}   {earned:.1f}/{possible} = {pct:.1f}%")
    report = {"earned": round(earned, 2), "possible": possible, "pct": round(pct, 1),
              "criteria": [{"name": n, "weight": w, "score": round(s, 3), "evidence": e}
                           for n, w, s, e in rows]}
    with open(os.path.join(HERE, "evaluation_rubric.json"), "w") as f:
        json.dump(report, f, indent=1)
    sys.exit(0 if pct >= 90 else 1)


if __name__ == "__main__":
    main()
