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
    # environment-gated acceleration: solve_ode uses scipy when importable, else stdlib RK4 —
    # same signature, and must conserve energy either way
    caps = numeric.capabilities()
    sol = numeric.solve_ode(d, [1.0, 0.0], 0.01, 628, method="auto")
    assert sol["backend"] in ("scipy", "rk4") and abs(sol["final"][0]**2 + sol["final"][1]**2 - 1.0) < 1e-3, sol
    forced = numeric.solve_ode(d, [1.0, 0.0], 0.01, 628, method="rk4")
    assert forced["backend"] == "rk4", forced
    return f"RK4 err {err:.2e}; solve_ode backend={sol['backend']} (numpy={caps['numpy']},scipy={caps['scipy']})"

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


def t_chaos_operators():
    import chaos_operators as ch, config
    assert ch.p_chaos(0.5) == 0.30 and ch.p_chaos(0.05) == 0.05, "P_chaos = min(0.30, T)"
    m = ch.structural_mutation({"stance": "optimistic"})
    assert m["stance"] == "pessimistic" and m["mutated"], m       # structure flip
    g = ch.genius_stance("x", [{"stance": "optimistic", "confidence": 0.8}])
    assert g["stance"] == "genius" and g["confidence"] <= 0.30, g  # low conf (SR_11)
    # exploration policy: chaos starts at FOGGY, parallelism switches to B, RESEARCH forces genius
    assert config.exploration_policy("STANDARD")["parallelism"] == "A"
    assert config.exploration_policy("FOGGY")["chaos"] and config.exploration_policy("FOGGY")["parallelism"] == "B"
    assert config.exploration_policy("RESEARCH")["genius"] is True
    return "levy/mutation/genius + chaos from FOGGY, A->B, RESEARCH genius"


def t_competence_matrix():
    import competence_matrix as cm, os
    # isolate: a fresh session + durable ledger so reward-history doesn't flip PERSONA_SWAP
    for db in ("competence.db", "learning.db"):
        try:
            os.remove(os.path.expanduser(f"~/.apex-method/{db}"))
        except OSError:
            pass
    assert cm.estimate_difficulty("navier stokes turbulência fluido pde")["bde_score"] >= 0.85
    assert cm.is_stuck(25, [0.5])[0] and cm.is_stuck(3, [0.50, 0.505, 0.50])[0]
    hard = cm.diagnose("architect", "science", "navier stokes turbulência fluido reynolds pde")
    assert hard["diagnosis"] == "HARD_PROBLEM", hard
    swap = cm.diagnose("critic", "engineering", "refatorar backend", rejections_streak=25)
    assert swap["diagnosis"] == "PERSONA_SWAP" and "new_phase_offset" in swap, swap
    return f"difficulty+stuck+diagnosis (HARD/{swap['diagnosis']})"


def t_evaluate_hypotheses():
    import concurrent_executor as ce, os
    for db in ("competence.db", "learning.db"):     # fresh session + durable ledgers
        try:
            os.remove(os.path.expanduser(f"~/.apex-method/{db}"))
        except OSError:
            pass
    hyps = [{"stance": "optimistic", "answer": "A", "confidence": 0.78},
            {"stance": "neutral", "answer": "A", "confidence": 0.70},
            {"stance": "pessimistic", "answer": "B", "confidence": 0.55}]
    out = ce.evaluate_hypotheses("optimize the backend memory architecture", hyps, mode="DEEP")
    assert out["n_directors"] >= 3, out["n_directors"]
    assert all(len(l["sha256"]) == 64 and "best" in l for l in out["laudos"]), "hashed laudos"
    assert out["decision"] in ("ADOPT", "REVIEW", "REJECT")
    # FOGGY+ : chaos operators expand the set with divergent candidates before scoring
    assert any(s and s.startswith("chaos_") for s in out["hypotheses_scored"]), out["hypotheses_scored"]
    # Level-B: a spawn_subagents manifest tells Claude which real Agent subagents to fan out
    man = out.get("spawn_subagents")
    assert man and man["level"] == "B" and man["spawn"], "level-B manifest"
    assert {"optimistic", "pessimistic", "neutral"} <= {s["stance"] for s in man["spawn"]}, man["spawn"]
    # RESEARCH injects the mandatory genius (non-obvious) hypothesis before directors score
    res = ce.evaluate_hypotheses("optimize the backend memory architecture", hyps, mode="RESEARCH")
    assert any(x["stance"] == "genius" for x in res["laudos"][0]["ranking"]), "genius injected"
    assert any(s["stance"] == "genius" for s in res["spawn_subagents"]["spawn"]), "genius framing in manifest"
    # 2nd call: real subagent hypotheses merge in as first-class candidates, no further manifest
    sub = [{"stance": "contrarian", "answer": "C", "confidence": 0.62, "rationale": "z"}]
    res2 = ce.evaluate_hypotheses("optimize the backend memory architecture", hyps,
                                  mode="RESEARCH", subagent_hypotheses=sub)
    assert "contrarian" in res2["hypotheses_scored"], res2["hypotheses_scored"]
    assert "spawn_subagents" not in res2, "no re-spawn once subagents supplied"
    # STANDARD is Level-A: no chaos, no subagent manifest
    stt = ce.evaluate_hypotheses("optimize", hyps, mode="STANDARD")
    assert not any(s and s.startswith("chaos_") for s in stt["hypotheses_scored"]), stt["hypotheses_scored"]
    assert "spawn_subagents" not in stt, "Level-A has no subagent manifest"
    # re-anchored abort: a stuck persona (rejections_streak>20) is swapped, not kept
    st = {"critic": {"rejections_streak": 25, "confidence_history": [0.75]}}
    r = ce.run_stances("refactor", [{"name": "s", "persona": "critic",
                                     "program": ce.qualitative_stance_program("X", 0.75)}],
                       mode="DEEP", agent_states=st)
    assert r["aborted"] and r["aborted"][0]["diagnosis"] == "PERSONA_SWAP", r["aborted"]
    return f"{out['n_directors']} directors, hashed laudos, {out['decision']}; abort->PERSONA_SWAP"


def t_project_ledger():
    import project_ledger as pl_mod, tempfile, os
    pl = pl_mod.ProjectLedger("build memory", mode="DEEP", backend="git")
    pl.add_micro("m1", "design", "architect", "critic", "doc")
    pl.add_micro("m2", "implement", "engineer", "critic", "code", depends_on=["m1"])
    pl.add_micro("m3", "test", "qa", "pmi_pm", "code", depends_on=["m2"])
    pl.add_micro("m4", "docs", "writer", "pmi_pm", "doc", depends_on=["m2"])
    d = pl.dsm()
    assert d["critical_path"] == ["m1", "m2", "m3"] or d["critical_path"] == ["m1", "m2", "m4"], d["critical_path"]
    assert ["m3", "m4"] in d["parallel_batches"] or ["m4", "m3"] in d["parallel_batches"], d["parallel_batches"]
    assert d["cycle"] is False
    # completion gate blocks advancing while micros are open
    assert pl.guard_completion()["blocked_advance"] is True
    # abandon needs a justified reason
    assert pl.authorize_abandon("m4", "")["status"] == "REFUSED"
    assert pl.authorize_abandon("m4", "descoped: out of scope this cycle")["status"] == "AUTHORIZED"
    # cycle is detected, not hung
    c = pl_mod.ProjectLedger("c", mode="DEEP")
    c.add_micro("x", "X", "a", "b", "doc", depends_on=["y"])
    c.add_micro("y", "Y", "a", "b", "doc", depends_on=["x"])
    assert c.dsm()["cycle"] is True
    # DEEP+ only; STANDARD stays bureaucracy-free; zip roundtrip
    assert pl_mod.ProjectLedger("t", mode="STANDARD").is_active() is False
    assert len(pl_mod.ProjectLedger.from_json(pl.to_json()).micros) == 4
    z = pl.export_zip(directory=tempfile.mkdtemp())
    assert os.path.isfile(z["zip"]) and "PROJECT_LEDGER.md" in z["contents"]
    return "MACRO+micros, DSM critical-path+parallel, gate, justified-abandon, cycle, zip"


def t_memory():
    import memory as mem_mod, tempfile, os
    m = mem_mod.MemoryStore(os.path.join(tempfile.mkdtemp(), "memory.db"))
    m.remember("APEX uses beta-binomial for the Bayesian layer", "semantic")
    m.remember("the char-n-gram backend fixes cross-language routing", "semantic")
    # semantic dedup: same fact stored once
    a = m.remember("dedup me exactly", "semantic")
    b = m.remember("dedup me exactly", "semantic")
    assert a == b, "semantic content-address dedup"
    # episodic is NOT deduped (distinct events)
    e1 = m.remember("same event text", "episodic")
    e2 = m.remember("same event text", "episodic")
    assert e1 != e2, "episodic keeps distinct events"
    # recall ranks the relevant memory first (char-n-gram, language-robust)
    top = m.recall("bayesian statistics")
    assert top and "bayes" in top[0]["text"].lower() and len(top[0]["sha"]) == 64, top
    # curated write from a snapshot
    m.remember_from_snapshot({"objective": "build memory",
                              "findings": [{"what": "SQLite default", "where": "memory.py",
                                            "how": "stdlib", "confidence": "high"}]})
    # governance ledger: SHA-256 chained + tamper-evident
    m.record_event("vaccine_promoted", "err->fix", "promote", {"uses": 3})
    m.record_event("skill_granted", "vt->react", "grant")
    assert m.verify_ledger()["ok"] and m.verify_ledger()["events"] == 2
    # ── B1 Knowledge Graph: typed edges + graph-walk recall + acyclic guard ──
    r = m.relate_text("the default persistence store should be SQLite for offline portability",
                      "MongoDB is the better persistence store for multi-server deployments",
                      "contradiz")
    assert r["status"] == "OK" and len(r["sha"]) == 64, r
    g = m.recall_graph("persistence store", k=1, depth=1, rel="contradiz")
    assert any("mongodb" in e["text"].lower() for e in g["expanded"]), g["expanded"]
    # directional causa chain x->y->z; a cycle z->x MUST be rejected by the hypothesis_dag engine
    x = m.remember("premise: the container is ephemeral", "semantic")
    y = m.remember("therefore local db is not durable", "semantic")
    z = m.remember("therefore durability needs git or zip export", "semantic")
    m.relate(x, y, "causa"); m.relate(y, z, "causa")
    assert m.relate(z, x, "causa")["status"] == "REFUSED", "acyclic guard must reject the cycle"
    assert m.relate("nope", z, "causa")["status"] == "REFUSED", "edge needs existing nodes"
    assert m.relate(x, y, "bogus_rel")["status"] == "REFUSED", "unknown rel refused"
    assert m.stats()["relations"] == 3, m.stats()
    return (f"episodic/semantic + dedup + recall + snapshot + chained ledger; "
            f"KG {m.stats()['relations']} edges + graph-walk + acyclic guard ({m.stats()['memories']} mem)")


def t_execution_policy():
    import execution_policy as ep
    # routing contract: compute -> sealed subprocess; discovery -> internet-enabled agent
    assert ep.route("integrate the ODE with rk4")["surface"] == "subprocess"
    disc = ep.route("search skills.sh and github for a legal MCP")
    assert disc["surface"] == "agent+internet" and disc["needs_internet"] is True, disc
    assert ep.route("decide the best architecture")["surface"] == "agent", ep.route("decide")
    assert ep.route("x")["provider_of_tools"] == "llm-orchestrator"
    # HARD RULE: no classification ever routes an internet task into the sandbox
    for probe in ("baixar paper do arxiv", "buscar skill no marketplace", "compute hash",
                  "download latest repo", "reason about tradeoffs", "optimize the matrix"):
        r = ep.route(probe)
        assert not (r["surface"] == "subprocess" and r["needs_internet"]), r
    # 3-persona dissect entry
    plan = ep.dissect_entry("build a compliant medical billing pipeline", mode="DEEP")
    assert [p["persona"] for p in plan["personas"]] == ["architect", "analyst", "critic"], plan["personas"]
    assert plan["micros"] and all("swot" in m and "routing" in m and m["template"] for m in plan["micros"])
    assert plan["provisioning"]["provider_of_tools"] == "llm-orchestrator"
    assert "needs_internet=True is NEVER routed to the subprocess" in plan["hard_rule"]
    # a regulated discipline carries region-specific governance
    reg = ep.dissect_entry("draft a HIPAA healthcare data policy")
    assert any("regulatory" in m["needed"]["governance"] for m in reg["micros"]), reg["micros"]
    return f"route compute/discover/reason + HARD-RULE; dissect_entry 3 personas, {len(plan['micros'])} micros"


def t_learning():
    import learning as lrn, tempfile, os
    s = lrn.LearningStore(os.path.join(tempfile.mkdtemp(), "learning.db"))
    # KEEP until MIN_OBS observations, then PROMOTE once the posterior clears Ω 0.72
    r1 = s.record_outcome("persona", "architect", "engineering", True)
    assert r1["decision"] == "KEEP" and r1["n"] == 1, r1
    s.record_outcome("persona", "architect", "engineering", True)
    r3 = s.record_outcome("persona", "architect", "engineering", True)
    assert r3["status"] == "PROMOTED" and r3["changed"] is True, r3
    # sustained failure DEMOTES (crosses the Ω review floor) with a durable status change
    for _ in range(3):
        d = s.record_outcome("persona", "poet", "engineering", False)
    assert d["status"] == "DEMOTED", d
    # best() ranks by validated posterior and excludes DEMOTED picks
    best = s.best("persona", "engineering")
    assert best and best[0]["subject"] == "architect" and all(b["status"] != "DEMOTED" for b in best), best
    # unknown kind refused; neutral score with no history
    assert s.record_outcome("bogus", "x", "d", True)["status"] == "REFUSED"
    assert s.score("persona", "never-seen", "engineering")["n"] == 0
    # the durable reward is what competence_matrix consults across sessions (Op-P3 closes the loop)
    mean, n = s.reward("architect", "engineering")
    assert mean >= lrn.PROMOTE_AT and n >= lrn.MIN_OBS, (mean, n)
    return f"promote@{r3['n']} obs, demote sustained-fail, best-excludes-demoted; stats={s.stats()}"


def t_swap_store():
    import swap_store as ss, memory as mem_mod, tempfile, os, json
    root = os.path.join(tempfile.mkdtemp(), "APEX")
    # materialize the canonical tree in a local folder (the PC-folder option)
    res = ss.materialize(root)
    for rel in ("apex.manifest.json", "README.md", "user/versions", "memory/versions",
                "swap", "staging", "archive"):
        assert os.path.exists(os.path.join(root, rel)), f"missing {rel}"
    # seed data files carry the canonical versioned name; find them via latest()
    up = ss.latest(os.listdir(os.path.join(root, "user")), "persona")
    assert up and ss.parse_filename(up)["ts"] == ss.SEED_TS, up
    man = json.load(open(os.path.join(root, "apex.manifest.json")))
    assert man["schema_version"] == ss.SCHEMA_VERSION and "promotion_gate" in man, man
    assert man["rotation"]["keep_backups"] == ss.KEEP_BACKUPS, man["rotation"]
    # idempotent: a second call creates nothing new and never overwrites
    res2 = ss.materialize(root)
    assert res2["created"] == [], res2["created"]
    # ── naming standard: <name>-<function>-<YYYYMMDDHHMMSS>-R<NN>.<ext> ──
    fn = ss.make_filename("memory")
    p = ss.parse_filename(fn)
    assert p and p["name"] == "memory" and p["function"] == "User" and p["ext"] == "ndjson"
    assert len(p["ts"]) == 14 and p["rev"] == ss.FILE_REVISIONS["memory"], p
    assert ss.parse_filename("not a valid name.json") is None
    # latest picks highest (revision, ts); a higher revision beats a newer timestamp
    cand = ["persona-User-20260101000000-R00.json", "persona-User-20260716000000-R00.json",
            "persona-User-20260101000000-R01.json"]
    assert ss.latest(cand, "persona") == "persona-User-20260101000000-R01.json", ss.latest(cand)
    # ── rotation: keep the newest N, older are obsolete; MAIN holds the latest ──
    folder = os.path.join(root, "user")
    for i in range(5):
        ss.write_versioned(folder, "persona", json.dumps({"v": i}), keep=3,
                           ts=time.strftime(ss.NAME_TS_FMT, time.gmtime(1000000000 + i)))
    main = [x for x in os.listdir(folder) if (ss.parse_filename(x) or {}).get("name") == "persona"]
    assert len(main) == 1, f"main holds exactly the latest, got {main}"
    vers = [x for x in os.listdir(os.path.join(folder, "versions"))
            if (ss.parse_filename(x) or {}).get("name") == "persona"]
    assert len(vers) == 3, f"rotation keeps 3 backups, got {len(vers)}"
    assert json.load(open(os.path.join(folder, main[0])))["v"] == 4, "latest content is the newest write"
    # the standard is shipped as a repo model file (built from the same spec)
    mpath = ss.write_model(os.path.join(root, "models"))
    spec = json.load(open(mpath))
    assert spec["naming"]["pattern"].startswith("<name>-<function>") and spec["folders"] == ss.FOLDERS
    # portable memory export/import round-trips durable memory (the swap page for memory)
    db = os.path.join(tempfile.mkdtemp(), "m.db")
    m = mem_mod.MemoryStore(db)
    m.remember("APEX swap survives the ephemeral container", "semantic")
    a = m.remember("premise ephemeral", "semantic"); b = m.remember("durability needs git", "semantic")
    m.relate(a, b, "causa")
    dump = m.export()
    assert dump["memory"] and dump["relations"], dump
    db2 = os.path.join(tempfile.mkdtemp(), "m2.db")
    stats = mem_mod.MemoryStore(db2).load_rows(dump)
    assert stats["memories"] == m.stats()["memories"] and stats["relations"] == 1, stats
    # page-out / page-in bundle with integrity hash
    bundle = ss.export_bundle("sess1", memory_db=db, snapshot={"objective": "x"},
                              working=[{"finding": "unvalidated"}], session_meta={"mode": "DEEP"})
    assert len(bundle["sha256"]) == 64
    back = ss.import_bundle(bundle, memory_db=db2)
    assert back["integrity_ok"] and back["snapshot"]["objective"] == "x", back
    # promotion gate: validated -> promote; not validated -> stays in swap
    good = ss.promotion_manifest("sess1", [{"name": "d1", "kind": "diff", "target": "commit"}],
                                 {"pmi_adopt": True, "ledger_ok": True, "tests_ok": True})
    bad = ss.promotion_manifest("sess1", [{"name": "h1", "kind": "hypothesis", "target": "commit"}],
                                {"pmi_adopt": False})
    assert good["validated"] and good["promote"] and not good["keep_in_swap"], good
    assert (not bad["validated"]) and bad["keep_in_swap"] and not bad["promote"], bad
    # the Drive layout is the SAME standard (folders + static + seed files), single source of truth
    dt = ss.drive_tree()
    assert {e["path"] for e in dt if e["kind"] == "folder"} == set(ss.FOLDERS), "drive tree = folders"
    assert any(e["path"].startswith("memory/memory-User-") for e in dt), "drive seeds are versioned"
    return (f"materialize idempotent; memory export/import round-trip; bundle integrity; "
            f"gate promote={len(good['promote'])} keep={len(bad['keep_in_swap'])}")


def t_llm_adapter():
    import llm_adapter as la
    # claude (reference): meets all required, RESEARCH fits, Level-B parallelism, no adjustments
    r = la.report("claude", "RESEARCH")
    assert r["check"]["ok"] and r["fits"]["fits"], r
    assert r["plan"]["parallelism"] == "B" and r["plan"]["effective_mode"] == "RESEARCH", r["plan"]
    # gpt: meets required but no subagents -> degrade to Level A, mode still fits
    g = la.degrade("gpt", "RESEARCH")
    assert g["parallelism"] == "A" and g["effective_mode"] == "RESEARCH", g
    assert any("Level A" in a for a in g["adjustments"]), g["adjustments"]
    # local: missing required caps + tiny window -> RESEARCH capped, manual tool loop + JSON parse
    loc = la.check("local")
    assert not loc["ok"] and set(loc["missing_required"]) >= {"tool_calling", "structured_json_output"}, loc
    ld = la.degrade("local", "RESEARCH")
    assert ld["effective_mode"] != "RESEARCH" and len(ld["adjustments"]) >= 3, ld
    # unknown provider -> conservative baseline (optional caps off, smallest window)
    caps = la.capabilities("mystery-xyz")
    assert caps["subagents"] is False and caps["tool_calling"] is True, caps
    assert la.degrade("mystery-xyz", "DEEP")["effective_mode"] == "EXPRESS", "tiny window caps hard"
    return (f"claude=B/full; gpt->A; local caps->{ld['effective_mode']} +{len(ld['adjustments'])} adj; "
            f"unknown->baseline")


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
    ("chaos_operators", t_chaos_operators), ("competence_matrix", t_competence_matrix),
    ("evaluate_hypotheses", t_evaluate_hypotheses), ("project_ledger", t_project_ledger),
    ("memory", t_memory), ("llm_adapter", t_llm_adapter), ("swap_store", t_swap_store),
    ("learning", t_learning), ("execution_policy", t_execution_policy),
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
