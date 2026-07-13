#!/usr/bin/env python3
"""
apex_st_metric.py — APEX apex_st_metric (v00.32.1, OPP-MAS-06), nativized.

WHY: without this, APEX can't tell whether it's progressing or running in circles. It measures
the distance between consecutive session snapshots in information space and flags stagnation.

WHEN: STEP_13.

WHAT IF IT FAILS: first session (no history) -> dS2=0, curvature=FIRST_SESSION, don't trigger
meta_learning; missing data -> defaults (H=0.5, conf=50), less precise but doesn't fail.

NOTE (bug fixed in APEX PATCH_C6): the correct formula is ALL POSITIVE — dS2 is a distance, not
a displacement. The old dS2 = ... - gamma*dCoh2 was wrong (higher coherence reduced progress).
"""
A, B, G = 1.0, 0.5, 0.8


def compute_apex_st(prev_snap, curr_snap, alpha=A, beta=B, gamma=G):
    if not prev_snap:
        return {"dS2": 0.0, "curvature": "FIRST_SESSION", "trigger_meta_learning": False}
    def g(snap, k, default):
        return snap.get(k, default)
    dMCFE = g(curr_snap, "mcfe", 0.5) - g(prev_snap, "mcfe", 0.5)
    dInfo = g(curr_snap, "info", 0.5) - g(prev_snap, "info", 0.5)
    dCoh = g(curr_snap, "coh", 0.5) - g(prev_snap, "coh", 0.5)
    dS2 = alpha * dMCFE ** 2 + beta * dInfo ** 2 + gamma * dCoh ** 2   # ALL positive
    if dS2 < 0.02:
        curv = "FLAT"
    elif dS2 < 0.10:
        curv = "LOW"
    elif dS2 < 0.30:
        curv = "MEDIUM"
    else:
        curv = "HIGH"
    # stagnation trigger requires 2+ consecutive FLAT (caller tracks history)
    trigger = curv == "FLAT" and prev_snap.get("prev_curvature") == "FLAT"
    return {"dS2": round(dS2, 4), "curvature": curv, "trigger_meta_learning": trigger}


if __name__ == "__main__":
    print("first:", compute_apex_st(None, {"mcfe": 0.5}))
    print("progress:", compute_apex_st({"mcfe": 0.4, "info": 0.3, "coh": 0.5}, {"mcfe": 0.7, "info": 0.6, "coh": 0.55}))
    print("stagnation:", compute_apex_st({"mcfe": 0.5, "info": 0.5, "coh": 0.5, "prev_curvature": "FLAT"},
                                          {"mcfe": 0.51, "info": 0.5, "coh": 0.5}))
