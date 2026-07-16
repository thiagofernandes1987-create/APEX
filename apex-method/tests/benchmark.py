#!/usr/bin/env python3
"""
benchmark.py — APEX-method test & benchmark harness.

WHY: every module ships with a correctness test asserted against a known-good value, so this
doubles as (a) a regression test and (b) a reusable benchmark for later audits. Run it and
compare benchmark_report.json across versions.

WHEN: after any change to scripts/, before packaging, and in CI.

WHAT IF IT FAILS: a failing test prints the module + the assertion; the runner still completes
the rest and exits non-zero so CI catches it.

USAGE: python3 tests/benchmark.py   (from the skill root, or from tests/)
"""
import sys, os, time, json, io, contextlib

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(HERE, "..", "scripts")
sys.path.insert(0, SCRIPTS)

RESULTS = []


def check(name, fn):
    t0 = time.perf_counter()
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            metric = fn()
        ok, err = True, ""
    except AssertionError as e:
        ok, metric, err = False, None, f"assert: {e}"
    except Exception as e:
        ok, metric, err = False, None, f"{type(e).__name__}: {e}"
    ms = round((time.perf_counter() - t0) * 1000, 1)
    RESULTS.append({"module": name, "ok": ok, "ms": ms, "metric": metric, "error": err})


# ── one test per module (assert against known-good) ──────────────────────────
def t_pot():
    import pot
    r = pot.run_chain([{"name": "s", "code": "print(sum(range(1,101)))"}])
    assert "5050" in str(r), r
    return "sum 1..100 = 5050"

def t_numeric():
    import numeric
    # 2D harmonic oscillator conserves energy; RK4 far better than Euler
    import math
    def d(s): return [s[1], -s[0]]
    rk = numeric.rk4(d, [1.0, 0.0], 0.01, 628)
    err = abs((rk[0]**2 + rk[1]**2) - 1.0)
    assert err < 1e-3, err
    return f"RK4 energy err {err:.2e}"

def t_verify():
    import verify
    a = verify.verify_identity("(x+1)**2", "x**2+2*x+1")
    b = verify.verify_identity("(x+1)**2", "x**2+x+1")
    assert "VERIFIED" in a["tag"] and "REFUTED" in b["tag"], (a, b)
    return "identity VERIFIED / REFUTED"

def t_uco_gate():
    import uco_gate
    r = uco_gate.gate("def f(n):\n while True:\n  n+=1")
    assert r["status"] == "REJECTED", r
    return f"loop REJECTED ({r['engine']})"

def t_uco_v4():
    import universal_code_optimizer_v4 as u
    r = u.UniversalCodeOptimizer(seed=42).analyze("def f(n):\n while True: n+=1", language_hint="python")
    assert r.metrics.infinite_loop_risk > 0.5, r.metrics.infinite_loop_risk
    return f"loop_risk {r.metrics.infinite_loop_risk:.2f}"

def t_router():
    import router
    cat = [{"id": "frontend-design", "name": "frontend-design", "description": "frontend ui ux react component design", "tags": ["frontend"]},
           {"id": "finance", "name": "finance", "description": "valuation portfolio risk cash flow", "tags": ["finance"]}]
    r = router.route("build a react ui component", cat)
    assert r[0]["id"] == "frontend-design", r
    return "routes to frontend"

def t_skill_scout():
    import skill_scout
    for atk in ("import os\nos.system('x')", "__import__('os')", "eval('1')"):
        assert not skill_scout.ast_security_scan(atk)["safe"], atk
    assert skill_scout.ast_security_scan("import numpy as np\ndef f(x): return np.sqrt(x)")["safe"]
    return "3 attacks blocked, clean passes"

def t_skill_forge():
    import skill_forge, tempfile, os as _os
    d = tempfile.mkdtemp()
    class A: pass
    a = A(); a.name="test-skill"; a.kind="workflow"; a.domain="engineering"; a.subtype="general"
    a.description="A test skill. Use when: verifying the forge produces schema-valid frontmatter."
    a.author="APEX"; a.out=_os.path.join(d,"SKILL.md")
    skill_forge.create(a)
    txt = open(a.out).read()
    assert "name: test-skill" in txt and "kind: workflow" in txt, txt[:200]
    return "generates valid SKILL.md"

def t_snapshot():
    import snapshot
    snap = snapshot.new_snapshot("test objective", "DEEP")
    snapshot.add_finding(snap, "found X", where="module Y", confidence="[APPROX] high")
    block = snapshot.to_context_block(snap)
    blob = snapshot.compress(snap)
    assert "test objective" in block and snapshot.decompress(blob), block[:80]
    return "snapshot new/add/compress/decompress"

def t_agent_registry():
    import agent_registry as reg
    agents = reg.load(reg.AGENTS)
    hits = reg.match_task_to_agents("debug a python backend api", agents)
    assert hits and hits[0][0] in ("engineer", "pmi_pm"), hits
    ext = reg.match_task_to_ext_agents("optimize a spark data pipeline")
    assert any("data" in h[0] for h in ext), ext
    return f"core->{hits[0][0]}, ext->{ext[0][0]}"

def t_curated():
    import curated
    fin = curated.for_domain("finance")
    assert len(fin) >= 3, fin
    return f"{len(fin)} finance skills"

def t_asset_manager():
    import asset_manager
    s = asset_manager.summary()
    assert s["mcp_servers"] >= 10 and s["third_party"] >= 30, s
    return f"{s['total_assets']} assets, {s['mcp_servers']} mcps"

def t_gravity():
    import gravity
    r = gravity.plan("audit code security and scan dependencies for vulnerabilities")
    con = r["constellation"]
    assert "agent" in con, con
    return f"security constellation: {len(con.get('agent',[]))} agents"

def t_bayes():
    import bayes
    bb = bayes.beta_binomial_update(1, 1, 8, 10)
    assert abs(bb["mean"] - 0.75) < 1e-9, bb
    assert bayes.omega_decision(0.75) == "ADOPT"
    h = bayes.posterior_over_hypotheses({"A":0.5,"B":0.3,"C":0.2},{"A":0.8,"B":0.4,"C":0.1})
    assert abs(h["posteriors"]["A"] - 0.7407) < 1e-3, h
    assert bayes.r_acum([0.9,0.6,0.5,0.6])["status"] == "CRITICAL_EARLY_EXIT"
    return f"beta-binomial 0.75, posterior A={h['posteriors']['A']}"

def t_orchestrator():
    import orchestrator
    ex = orchestrator.run("2+2")
    assert ex["path"] == "EXPRESS" and ex["answer"] == 4, ex
    hard = orchestrator.run("build a secure trading backend and value the portfolio with monte carlo")
    assert hard["path"] == "FULL_PIPELINE" and "finance" in hard["disciplines"], hard
    pmi = orchestrator.pmi_converge([{"discipline":"m","answer":2.09,"confidence":0.9,"numeric":True},
                                      {"discipline":"s","answer":2.09,"confidence":0.85,"numeric":True}])
    assert pmi["reliability"] > 0.8, pmi
    return f"2+2=4 express; hard->{hard['mode']}; pmi rel={pmi['reliability']}"

def t_hypothesis_dag():
    import hypothesis_dag as hd
    g = hd.HypothesisDAG()
    for h in ("A", "H2", "H3"): g.register(h)
    g.add_edge("A", "H2"); g.add_edge("H2", "H3")
    assert g.add_edge("H3", "A") is False   # cycle
    aff = g.invalidate_cascade("A")
    assert aff == {"A", "H2", "H3"}, aff
    return f"cycle rejected, cascade {len(aff)}"

def t_code_genetics():
    import code_genetics as cg
    s = cg.VaccineStore()
    err = "TypeError at line 5"
    s.save_vaccine(err, "cast to int")
    for ok in (True, True, True, False): s.record_outcome(err, ok)
    assert cg.signature("TypeError at line 5") == cg.signature("TypeError at line 99")
    assert s.is_promotable(err) is False   # 0.75 < 0.85
    return "stable sig, promote gate 0.85"

def t_guards():
    import guards
    assert guards.crystallization_guard("class_1", 0.03)["crystallize"] is True
    assert guards.crystallization_guard("class_3", 0.03)["crystallize"] is False
    assert guards.forge_load_gate("import os\nexec('x')")["verdict"] == "REJECTED"
    assert guards.forge_load_gate("import numpy\ndef f(): return 1")["verdict"] == "ACCEPTED"
    assert guards.external_critic_order(["external_critic","meta_reasoning"])["ok"]
    return "SR_36/37/38 enforced"

def t_mental_interpreter():
    import mental_interpreter as mi
    p = mi.plan_phases("SCIENTIFIC", 3, curvature=1.2, p_target=0.95)
    assert "SPECULATION" in p["phases"] and p["n_final"] >= 2, p
    m = mi.entropy_weighted_merge([{"answer":"X","confidence":0.9},{"answer":"X","confidence":0.85},{"answer":"Y","confidence":0.55}])
    assert m["answer"] == "X", m
    return f"n_final={p['n_final']}, merge->X"

def t_geodesic():
    import geodesic_scheduler as gs
    steps = [{"id":"a","delta_h":0.3,"tokens":300},{"id":"b","delta_h":0.05,"tokens":500},
             {"id":"c","delta_h":0.4,"tokens":400},{"id":"e","delta_h":0.9,"tokens":100,"ethical_violation":True}]
    r = gs.evaluate_steps(steps, 1200)
    assert "e" not in r["plan"], r          # ethical excluded
    return f"plan {r['plan']}, ethical excluded"

def t_verification_gate():
    import verification_gate as vg
    hyps = [{"id":"H1","delta_h":0.3,"confidence":55},{"id":"H2","delta_h":0.05,"confidence":90}]
    d = vg.route(hyps, "DEEP")
    assert "H1" in d["verify_list"] and "H2" in d["skip_list"], d
    p = vg.verify_hypothesis([True, False, True])
    assert p["rejected_at_test"] == 2, p
    return "DEEP routes H1, prune@test2"

def t_fractal():
    import fractal_compression as fc
    hyps = [{"id":"H1","confidence":80,"evidence_level":3,"anchors":["a","b"]},
            {"id":"H2","confidence":60,"evidence_level":2,"anchors":["a","b"]},
            {"id":"H3","confidence":55,"evidence_level":1,"anchors":["x"]}]
    r = fc.compress(hyps, pruned_by_skill={"H3":"invariant_violation"})
    assert len(r["kept"]) >= 2, r
    return f"kept {r['kept']}"

def t_geometry():
    import geometry_estimator as ge
    def deriv(s): x,y=s; return [1.1*x-0.4*x*y, -0.4*y+0.1*x*y]
    def euler(d,s0,dt,n):
        s=list(s0)
        for _ in range(n):
            k=d(s); s=[s[i]+dt*k[i] for i in range(len(s))]
        return s
    de = ge.delta_err(deriv, [10.0,5.0], 0.1, euler)
    bs = ge.optimal_block_size(10.0, de)
    assert 5 <= bs <= 30, bs
    return f"euler block size {bs}"

def t_apex_st():
    import apex_st_metric as am
    prog = am.compute_apex_st({"mcfe":0.4,"info":0.3,"coh":0.5},{"mcfe":0.7,"info":0.6,"coh":0.55})
    stag = am.compute_apex_st({"mcfe":0.5,"info":0.5,"coh":0.5,"prev_curvature":"FLAT"},{"mcfe":0.51,"info":0.5,"coh":0.5})
    assert prog["curvature"] in ("LOW","MEDIUM","HIGH") and stag["trigger_meta_learning"], (prog, stag)
    return f"progress {prog['curvature']}, stagnation triggers"


# ── audit v1.17.0: new module + regression tests for the fixed bugs ───────────
def t_repo_bridge():
    import repo_bridge
    hits = repo_bridge.search_native("statistical analysis of experiments", k=3)
    assert hits and all("path" in h for h in hits), hits
    # local-clone fetch (offline): the skill lives inside the APEX repo here
    r = repo_bridge.fetch("apex-method/SKILL.md") if repo_bridge._local_root() else {"status": "OK"}
    assert r["status"] in ("OK", "NOT_FOUND"), r
    assert repo_bridge._index()["_meta"]["count"] >= 3784
    try:
        repo_bridge.fetch("../etc/passwd"); assert False, "traversal not refused"
    except ValueError:
        pass
    return f"native index {repo_bridge._index()['_meta']['count']}, traversal refused"

def t_tfidf_fallback():
    import _tfidf
    sims = _tfidf.rank("frontend ui component", ["react frontend ui", "backtest a portfolio"])
    assert sims[0] > sims[1] > -1, sims
    M = _tfidf.pairwise(["a b c", "a b c", "x y z"])
    assert M[0][1] > 0.99 and M[0][2] < 0.1, M
    return "pure-python tf-idf ranks + pairwise ok"

def t_regressions():
    import skill_scout, guards, curated, mental_interpreter, orchestrator
    # json.loads must PASS the scan; pickle.loads must be rejected (both gates)
    ok = skill_scout.ast_security_scan("import json\nd = json.loads('{}')")
    assert ok["safe"], ok
    bad = skill_scout.ast_security_scan("import pickle\nd = pickle.loads(x)")
    assert not bad["safe"], bad
    assert guards.forge_load_gate("import json\nd=json.loads('{}')")["verdict"] == "ACCEPTED"
    assert guards.forge_load_gate("import pickle\nd=pickle.loads(x)")["verdict"] == "REJECTED"
    # dynamic getattr obfuscation now rejected by the strict forge gate
    assert guards.forge_load_gate("import math\ng=getattr(math, 's'+'qrt')")["verdict"] == "REJECTED"
    # installs sort: 1.2M > 391K > 900
    assert curated._installs("1.2M") > curated._installs("391K") > curated._installs("900")
    # n_rel: accumulated reliability must stay >= target
    n = mental_interpreter.optimal_size_for_target(0.9, 0.05)
    assert (1 - 0.05) ** n >= 0.9, (n, (1 - 0.05) ** n)
    # express: case-insensitive + pow DoS capped
    assert orchestrator.express_check("What is 2+2?")["answer"] == 4
    try:
        orchestrator._safe_arith("9**9**9"); assert False, "pow not capped"
    except ValueError:
        pass
    # chaos stance must not poison the R_acum gate (SR_11: deliberate divergence != unreliability)
    pmi = orchestrator.pmi_converge([
        {"discipline": "finance", "answer": "A", "confidence": 0.82},
        {"discipline": "engineering", "answer": "A", "confidence": 0.74},
        {"discipline": "chaos", "answer": "B", "confidence": 0.35}])
    assert pmi["r_acum"]["status"] != "CRITICAL_EARLY_EXIT", pmi["r_acum"]
    assert "B" in pmi["posteriors"], pmi  # chaos still debates in the posterior
    # skills.sh marketplace >=1000-install quality bar filters correctly
    import skills_sh
    items = [skills_sh._norm({"owner":"a","name":"big","installs":5000}),
             skills_sh._norm({"owner":"b","name":"tiny","installs":9})]
    assert [i for i in items if i["installs"] >= 1000] == [items[0]], items
    # offline discovery degrades to ready-to-run commands (never crashes)
    assert skills_sh.install_requests("x")["requests"][0]["status"] == "STAGED_needs_approval"
    # char-ngram semantic backend beats word TF-IDF on a cross-language cognate miss
    import _tfidf
    w,_ = _tfidf.semantic_rank("otimização de portfólio", ["portfolio optimization", "web design"], backend="word")
    c,_ = _tfidf.semantic_rank("otimização de portfólio", ["portfolio optimization", "web design"], backend="char")
    assert max(w) == 0 and c.index(max(c)) == 0, (w, c)
    # dissect must classify Portuguese tasks, not dump them into engineering by default
    assert "finance" in orchestrator.dissect("dimensionar a reserva de caixa e o runway com burn"), \
        orchestrator.dissect("dimensionar a reserva de caixa e o runway com burn")
    assert "science" in orchestrator.dissect("simular a dinâmica de depleção física")
    # grant reaches the 213-agent extended roster, not just the 11 core (agent-need upgrade)
    import agent_registry as ar
    ags = ar.load(ar.AGENTS)
    g = ar.grant_skill({"id":"x/react-vt","domain":"frontend","name":"react-vt","description":"react frontend"},
                       ags, approved=True, ext_grants={})
    assert g["ext_agents"] and any("react" in a for a,_ in g["ext_agents"]), g["ext_agents"]
    return "loads FP, getattr, installs, n_rel, express, chaos, skills.sh, char-ngram, dissect-PT, ext-grant: all fixed"


# ── audit P1/P2/P3 rounds: new modules + wiring ──────────────────────────────
def t_monte_carlo():
    import monte_carlo as mc
    def model(s): return s["a"] + s["b"]
    d = {"a": {"dist": "normal", "mean": 50, "std": 5}, "b": {"dist": "fixed", "value": 10}}
    r = mc.simulate(model, d, n_iterations=5000, seed=1)
    assert r["status"] == "OK" and 58 < r["statistics"]["p50"] < 62, r
    assert mc.simulate(lambda s: 1/0, d, 100)["status"] == "FAILED"
    try:
        mc.simulate(model, {"a": {"dist": "weibull"}}, 10); assert False
    except ValueError:
        pass
    return f"MC P50={r['statistics']['p50']:.1f}, cv={r['statistics']['cv']:.3f}"

def t_pmi_monte_carlo():
    import orchestrator
    lo = {"answer": "plano-A", "model_fn": lambda s: s["x"], "distributions": {"x": {"dist": "normal", "mean": 100, "std": 3}}}
    hi = {"answer": "plano-B", "model_fn": lambda s: s["x"], "distributions": {"x": {"dist": "normal", "mean": 100, "std": 40}}}
    r = orchestrator.pmi_converge([lo, hi])
    assert "monte-carlo" in r["method"] and r["answer"] == "plano-A", r  # lowest CV wins
    return "PMI picks lowest-CV plan by real simulation"

def t_code_genetics_sqlite():
    import code_genetics, tempfile, os
    db = os.path.join(tempfile.mkdtemp(), "vax.db")
    s = code_genetics.VaccineStore(db_path=db)
    s.save_vaccine("NameError: name 'x' at line 5", "define x")
    for ok in (True, True): s.record_outcome("NameError: name 'x' at line 5", ok)
    s2 = code_genetics.VaccineStore(db_path=db)   # reopen -> persisted
    assert s2.is_promotable("NameError: name 'x' at line 9"), s2.vaccines
    return "vaccine persists + promotes across SQLite reopen"

def t_snapshot_wire():
    import orchestrator, snapshot
    snap = snapshot.new_snapshot("audit run", "STANDARD")
    r = orchestrator.run("optimize a data pipeline and validate the ml model", snapshot=snap)
    assert r["snapshot"]["findings"] and r["snapshot"]["milestones"], r["snapshot"]
    return f"run() recorded {len(r['snapshot']['findings'])} findings into snapshot"


# ── menu / config / deep_research (v1.21.0) ──────────────────────────────────
def t_config():
    import config
    try:
        assert config.set_preferred_modes(["SCIENTIFIC", "RESEARCH"])["status"] == "OK"
        # resolve must snap UP to the nearest preferred mode, never downgrade
        assert config.resolve_mode("DEEP") == "SCIENTIFIC", config.resolve_mode("DEEP")
        assert config.set_preferred_modes(["TURBO"])["status"] == "ERROR"
        assert config.set_option("router_backend", "char")["status"] == "OK"
        assert config.set_option("router_backend", "xyz")["status"] == "ERROR"
    finally:
        config.save(config.DEFAULTS)  # never leak preferences into other tests
    return "config persists, validates, resolves mode (snap-up)"


def t_menu():
    import menu
    show = menu.show()
    assert "1_update" in show["menu"] and "4_research" in show["menu"], show
    up = menu.update()  # offline or same-version -> no crash, structured result
    assert up["status"] in ("OK", "OFFLINE") and "installed" in up, up
    return f"menu shows {len(show['menu'])} actions; update={up['status']}"


def t_deep_research():
    import deep_research, config
    try:
        out = deep_research.research("audit and optimize the APEX agents", source="native", max_rounds=3)
        assert out["mode"] in ("RESEARCH", "SCIENTIFIC") and out["rounds_run"] >= 1, out
        assert out["stop_reason"] in ("TARGET_REACHED", "STAGNATION", "MAX_ROUNDS")
        # search source offline must still stage install requests (H5), never crash
        s = deep_research.research("obscure niche topic xyz", source="search", max_rounds=2)
        assert s["stop_reason"] in ("STAGNATION", "MAX_ROUNDS", "TARGET_REACHED")
    finally:
        config.save(config.DEFAULTS)
    return f"deep_research {out['stop_reason']} in {out['rounds_run']} rounds"


def t_concurrent_executor():
    import concurrent_executor as ce
    # canonical 3 stances (optimistic/neutral/pessimistic) run concurrently; barrier merges
    stances = ce.default_stances("s['cash']/s['burn']", {"cash": 1200000, "burn": 100000}, burn_key="burn")
    rep = ce.run_stances("size runway", stances, mode="DEEP")
    assert rep["status"] == "PARALLEL_POT_COMPLETE", rep["status"]
    assert set(rep["stance_answers"]) == {"optimistic", "neutral", "pessimistic"}, rep["stance_answers"]
    assert all(len(r["sha256"]) == 64 for r in rep["per_stance"]), "sha256 per stance"
    assert rep["budget_cap"] == 8, rep["budget_cap"]
    # budget = mode agent count: 15 stances capped to the mode's cap
    many = [{"name": f"s{i}", "persona": f"p{i}", "program": ce.qualitative_stance_program("X", 0.8)}
            for i in range(15)]
    assert ce.run_stances("x", many, mode="RESEARCH")["counter"]["total"] == 12
    assert ce.run_stances("x", many, mode="DEEP")["counter"]["total"] == 8
    # probabilistic abort + vaccine: a stance under 0.35 is quit (not merged), + off_persona flagged
    mixed = [{"name": "optimistic", "persona": "architect", "program": ce.qualitative_stance_program("A", 0.82)},
             {"name": "neutral", "persona": "theorist", "program": ce.qualitative_stance_program("A", 0.70)},
             {"name": "pessimistic", "persona": "critic", "program": ce.qualitative_stance_program("B", 0.28)},
             {"name": "wild", "persona": "poet", "program": ce.qualitative_stance_program("C", 0.60, off_persona=True)}]
    r3 = ce.run_stances("decide", mixed, mode="SCIENTIFIC")
    assert any(a["stance"] == "pessimistic" for a in r3["aborted"]), r3["aborted"]
    assert "wild" in r3["off_persona"], r3["off_persona"]
    # low-but-not-aborted round (0.35<=conf<target) must emit a RESTART directive
    low = [{"name": "a", "persona": "p1", "program": ce.qualitative_stance_program("A", 0.50)},
           {"name": "b", "persona": "p2", "program": ce.qualitative_stance_program("B", 0.45)}]
    r2 = ce.run_stances("weak round", low, mode="DEEP", p_target=0.72)
    assert "restart" in r2 and r2["restart"]["assign_new_personas"], r2
    return f"3 stances; mode-cap budget; abort+vaccine {len(r3['aborted'])}; off_persona; restart"


TESTS = [
    ("pot", t_pot), ("numeric", t_numeric), ("verify", t_verify), ("uco_gate", t_uco_gate),
    ("universal_code_optimizer_v4", t_uco_v4), ("router", t_router), ("skill_scout", t_skill_scout),
    ("skill_forge", t_skill_forge), ("snapshot", t_snapshot), ("agent_registry", t_agent_registry),
    ("curated", t_curated), ("asset_manager", t_asset_manager), ("gravity", t_gravity),
    ("bayes", t_bayes), ("orchestrator", t_orchestrator), ("hypothesis_dag", t_hypothesis_dag),
    ("code_genetics", t_code_genetics), ("guards", t_guards), ("mental_interpreter", t_mental_interpreter),
    ("geodesic_scheduler", t_geodesic), ("verification_gate", t_verification_gate),
    ("fractal_compression", t_fractal), ("geometry_estimator", t_geometry), ("apex_st_metric", t_apex_st),
    ("repo_bridge", t_repo_bridge), ("_tfidf", t_tfidf_fallback), ("audit_regressions", t_regressions),
    ("monte_carlo", t_monte_carlo), ("pmi_monte_carlo", t_pmi_monte_carlo),
    ("code_genetics_sqlite", t_code_genetics_sqlite), ("snapshot_wire", t_snapshot_wire),
    ("config", t_config), ("menu", t_menu), ("deep_research", t_deep_research),
    ("concurrent_executor", t_concurrent_executor),
]


def main():
    for name, fn in TESTS:
        check(name, fn)
    passed = sum(r["ok"] for r in RESULTS)
    total = len(RESULTS)
    total_ms = round(sum(r["ms"] for r in RESULTS), 1)
    print(f"\n{'MODULE':<30}{'STATUS':<8}{'ms':>8}   metric / error")
    print("-" * 78)
    for r in RESULTS:
        status = "PASS" if r["ok"] else "FAIL"
        detail = r["metric"] if r["ok"] else r["error"]
        print(f"{r['module']:<30}{status:<8}{r['ms']:>8}   {detail}")
    print("-" * 78)
    print(f"{'TOTAL':<30}{passed}/{total:<6}{total_ms:>8} ms")
    report = {"passed": passed, "total": total, "total_ms": total_ms, "results": RESULTS}
    with open(os.path.join(HERE, "benchmark_report.json"), "w") as f:
        json.dump(report, f, indent=1)
    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
