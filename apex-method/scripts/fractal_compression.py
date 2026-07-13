#!/usr/bin/env python3
"""
fractal_compression.py — APEX fractal_hypothesis_compression (v00.20.0), nativized.

WHY: at each fractal level the hypothesis space grows; without pruning, absurd/dominated
hypotheses survive and waste the next level's budget. This prunes them with four objective
filters BEFORE MCFE recomputes H_cognitive.

WHEN: after STEP_5 (post-interference), when fractal_depth>0 AND hypotheses_active>1.

WHAT IF IT FAILS: never prunes below min_hypotheses_preserved (2); if inputs are missing a
filter is skipped. Pipeline continues with the uncompressed set.
"""
MIN_PRESERVED = 2
FLOOR_CONFIDENCE = 40


def _jaccard(a, b):
    a, b = set(a), set(b)
    return len(a & b) / len(a | b) if (a or b) else 0.0


def compress(hypotheses, pruned_by_skill=None):
    """
    hypotheses: [{id, confidence(0-100), evidence_level(int), anchors:[...], contradicted:bool}]
    pruned_by_skill: {id -> reason} from Specialized Skill outputs.
    Returns {kept, report, events}.
    """
    pruned_by_skill = pruned_by_skill or {}
    H = {h["id"]: dict(h, state="ACTIVE") for h in hypotheses}
    events, d = [], {"dominated": 0, "merged": 0, "skill_refuted": 0, "absurd": 0}
    n_before = len(H)

    # 1) skill refutation + absurdity
    for hid, reason in pruned_by_skill.items():
        if hid not in H:
            continue
        if reason == "invariant_violation":
            H[hid]["state"] = "ABSURD"; d["absurd"] += 1
            events.append(f"[HYPOTHESIS_ABSURD: {hid} | invariant]")
        else:
            H[hid]["confidence"] -= 20
            if H[hid]["confidence"] < FLOOR_CONFIDENCE:
                H[hid]["state"] = "REFUTED_BY_SKILL"; d["skill_refuted"] += 1
                events.append(f"[HYPOTHESIS_REFUTED_BY_SKILL: {hid} | {reason}]")

    active = [h for h in H.values() if h["state"] == "ACTIVE"]

    # 2) dominance filter
    for a in active:
        if a["state"] != "ACTIVE":   # audit fix v1.17.0: a pruned hypothesis cannot dominate
            continue
        for b in active:
            if a["id"] == b["id"] or b["state"] != "ACTIVE":
                continue
            if (a["confidence"] > b["confidence"] + 10 and
                    a.get("evidence_level", 0) >= b.get("evidence_level", 0) and
                    not a.get("contradicted")):
                b["state"] = "DOMINATED"; d["dominated"] += 1
                events.append(f"[HYPOTHESIS_COMPRESSED: {b['id']} | dominated_by={a['id']}]")

    active = [h for h in H.values() if h["state"] == "ACTIVE"]

    # 3) similarity merge (jaccard of anchors > 0.80)
    merged_ids = set()
    for i, a in enumerate(active):
        for b in active[i + 1:]:
            if a["id"] in merged_ids or b["id"] in merged_ids:
                continue
            if (_jaccard(a.get("anchors", []), b.get("anchors", [])) > 0.80 and
                    abs(a["confidence"] - b["confidence"]) < 15):
                mid = f"{a['id']}+{b['id']}"
                H[mid] = {"id": mid, "confidence": min(100, max(a["confidence"], b["confidence"]) + 5),
                          "anchors": sorted(set(a.get("anchors", [])) | set(b.get("anchors", []))),
                          "state": "ACTIVE", "evidence_level": max(a.get("evidence_level", 0), b.get("evidence_level", 0))}
                a["state"] = b["state"] = "MERGED"; merged_ids |= {a["id"], b["id"]}
                d["merged"] += 1
                events.append(f"[HYPOTHESIS_MERGED: {a['id']} + {b['id']} -> {mid}]")

    kept = [h for h in H.values() if h["state"] == "ACTIVE"]
    # never prune below the floor
    if len(kept) < MIN_PRESERVED:
        extra = sorted((h for h in H.values() if h["state"] != "ACTIVE"),
                       key=lambda h: -h["confidence"])[:MIN_PRESERVED - len(kept)]
        kept += extra
    report = f"[FHC: before={n_before} | after={len(kept)} | dominated={d['dominated']} | merged={d['merged']} | skill_refuted={d['skill_refuted']} | absurd={d['absurd']}]"
    return {"kept": [h["id"] for h in kept], "report": report, "events": events}


if __name__ == "__main__":
    hyps = [
        {"id": "H1", "confidence": 80, "evidence_level": 3, "anchors": ["a", "b", "c"]},
        {"id": "H2", "confidence": 60, "evidence_level": 2, "anchors": ["a", "b", "c"]},  # merges w/ H1? jaccard=1 but conf diff 20>=15 -> no; dominated by H1
        {"id": "H3", "confidence": 55, "evidence_level": 1, "anchors": ["x", "y"]},
        {"id": "H4", "confidence": 50, "evidence_level": 1, "anchors": ["x", "y", "z"]},  # sim to H3
    ]
    import json
    print(json.dumps(compress(hyps, pruned_by_skill={"H3": "invariant_violation"}), indent=1))
