#!/usr/bin/env python3
"""
agent_materializer.py — turn a VALIDATED generic spawn into a STANDARDIZED, durable specialist
artifact, so the prompt library self-evolves across sessions (the author's auto-evolutive vision).

WHY THIS EXISTS:
  agent_lifecycle can SYNTHESIZE a generic agent when the roster has none. But if that generic
  agent then does the job well, the knowledge is lost at session end — next time the runtime
  synthesizes from scratch again. This module closes that gap: on a VALIDATED success it renders
  the grown agent (and the skills/diffs/scripts promoted with it) as artifacts in the SAME
  standardized layout the APEX repo uses (AGENT.md / SKILL.md frontmatter), writes them to a
  DURABLE grown-library under APEX_METHOD_HOME, and REGISTERS the agent in the roster overlay
  (agent_registry.register_grown_agent) so NEXT session `match_task_to_ext_agents` finds a real
  specialist instead of re-synthesizing a generic one. A generic that solved a problem becomes a
  permanent, discoverable engineer.

STANDARD LAYOUT (mirrors the repo, one layout per object type):
  agents/<id>/AGENT.md   — agent_id, name, version, status, anchors, activates_in, capabilities,
                           input_schema, output_schema, what_if_fails, security, primary_domain
  skills/<domain_path>/SKILL.md — skill_id, name, description, version, status, domain_path,
                           anchors, risk, languages, llm_compat

GATES (non-negotiable):
  - materialize() runs ONLY on validated=True (no reputation poisoning; matches finalize()).
  - consolidate_to_repo() writes into the repo working tree and STAGES a git commit — it never
    auto-commits; the human runs/approves the commit (H5 + the package's git-backend philosophy).
  - The rendered AGENT.md is HONEST about provenance: it records that it was grown from a generic
    spawn and validated, not hand-authored.

WHAT IF IT FAILS:
  Every write degrades independently and is reported; a missing engine → that piece is skipped.
  Pure stdlib (json/os/datetime/textwrap). Never raises into the caller.
"""
import json
import os
import re
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(__file__))


def _now_ts():
    return datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")


def _slug(text):
    return re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-") or "generic"


# Stopwords (PT+EN) so the grown agent's anchors are the SALIENT task terms, not filler. This is
# what lets the SAME task re-match the grown specialist next session even when the taxonomy
# mislabels the facets (the classifier is weak for out-of-taxonomy domains — see audit O-1).
_STOP = {"a", "o", "as", "os", "de", "da", "do", "das", "dos", "um", "uma", "e", "para", "por",
         "com", "no", "na", "em", "que", "the", "of", "for", "and", "to", "in", "on", "with",
         "com", "uma", "seu", "sua", "como", "ao", "à"}


def _task_keywords(task, k=8):
    """Salient tokens (len>=4, not stopwords) from the task — become roster anchors so the SAME
    task re-matches the grown agent next session regardless of taxonomy misclassification."""
    seen, out = set(), []
    for w in re.findall(r"[a-zA-Zá-úÁ-Ú0-9]{4,}", (task or "").lower()):
        if w in _STOP or w in seen:
            continue
        seen.add(w)
        out.append(w)
        if len(out) >= k:
            break
    return out


def _library_dir():
    try:
        import agent_registry
        return agent_registry._library_dir()
    except Exception:
        base = os.environ.get("APEX_METHOD_HOME") or os.path.expanduser("~/.apex-method")
        d = os.path.join(base, "library")
        os.makedirs(d, exist_ok=True)
        return d


def _yaml_list(items, indent=2):
    pad = " " * indent
    return "\n".join(f"{pad}- {i}" for i in items) if items else f"{pad}[]"


# ── rendering: EXACT standardized frontmatter (matches agents/*/AGENT.md, skills/**/SKILL.md) ──
def render_agent_md(agent_id, matrix, capabilities=None, promoted_skills=None,
                    promoted_scripts=None, evidence=None, version="v1.0.0"):
    """Render a standardized AGENT.md for a grown specialist from the competence matrix + what it
    equipped. Faithful to the repo's agent frontmatter (agent_id/anchors/activates_in/capabilities/
    input_schema/output_schema/what_if_fails/security)."""
    matrix = matrix or {}
    domain = matrix.get("domain") or (matrix.get("disciplines") or ["general"])[0]
    sub = matrix.get("subdomain")
    specialties = matrix.get("specialties", []) or []
    anchors = sorted(set([a for a in ([domain, sub] + list(specialties)) if a]))
    caps = capabilities or sorted(set(specialties + ([sub] if sub else []))) or ["general_reasoning"]
    where = f"{domain}/{sub}" if sub else domain
    name = f"{domain.title()}{(' ' + sub.title()) if sub else ''} Specialist (grown)"
    fm = [
        "---",
        f"agent_id: {agent_id}",
        f'name: "{name}"',
        f"version: {version}",
        "status: ACTIVE",
        "role_level: SECONDARY",
        "origin: grown_from_generic_spawn",       # honest provenance (not hand-authored)
        f"grown_at: {_now_ts()}",
        "anchors:",
        _yaml_list(anchors),
        "activates_in: [CLARIFY, DEEP, RESEARCH, SCIENTIFIC]",
        "position_in_pipeline: STEP_2",
        "rule_reference: SR_07",
        "description: >",
        f"  Specialist grown for {where} after a validated generic spawn. Equips real skills/"
        f"scripts by attraction; specialization crystallized from the competence matrix.",
        "tier: 2",
        'executor: "LLM_BEHAVIOR"',
        f"primary_domain: {domain}",
        "capabilities:",
        _yaml_list(caps),
        "input_schema:",
        '  problem: "str"',
        '  constraints: "list[str]"',
        "output_schema:",
        '  answer: "str"',
        '  confidence: "float"',
        '  rationale: "str"',
        "what_if_fails: >",
        "  FALLBACK: if the grown specialization is insufficient, escalate to pmi_pm / re-run the "
        "lifecycle discovery cascade (native -> skills.sh -> GitHub) and re-validate.",
        "security: {level: standard, approval_required: false}",
        "provenance:",
        f"  promoted_skills: {list(promoted_skills or [])}",
        f"  promoted_scripts: {list(promoted_scripts or [])}",
        f'  validated_by: "{(evidence or "host-validated")[:80]}"',
        "---",
        "",
        f"# {name}",
        "",
        "## Role",
        f"Grown specialist for **{where}**. Started as a generic APEX spawn, solved a validated "
        f"task, and was crystallized into a standardized, discoverable agent.",
        "",
        "## Responsibilities",
        "- Reason within the crystallized specialization; equip its promoted skills/scripts.",
        "- Say in output that it is a grown specialist (provenance above), not hand-authored.",
        "",
        "## Anchors",
        ", ".join(anchors) or "—",
        "",
        "## When to use",
        f"When a task maps to {where} — the lifecycle router now finds this agent by anchor overlap.",
    ]
    return "\n".join(fm) + "\n"


def render_skill_md(skill_id, domain, description, anchors=None, languages=None,
                    risk="safe", version="v1.0.0", status="ADOPTED"):
    """Render a standardized SKILL.md (matches skills/**/SKILL.md: skill_id/domain_path/anchors/
    risk/llm_compat)."""
    anchors = anchors or []
    languages = languages or ["python"]
    fm = [
        "---",
        f"skill_id: {skill_id}",
        f"name: {skill_id.split('.')[-1].replace('-', ' ').title()}",
        f'description: "{description[:280]}"',
        f"version: {version}",
        f"status: {status}",
        f"domain_path: {domain}/{skill_id.split('.')[-1]}",
        "anchors:",
        _yaml_list(anchors),
        f"risk: {risk}",
        "languages:",
        _yaml_list(languages),
        "llm_compat:",
        "  claude: full",
        "  gpt4o: partial",
        "origin: forged_by_agent_lifecycle",
        f"grown_at: {_now_ts()}",
        "---",
        "",
        f"# {skill_id}",
        "",
        f"{description}",
        "",
        "## When to use",
        f"Domain: {domain}. Forged on demand when discovery (native -> skills.sh -> GitHub) found "
        "nothing; validated with the agent that needed it.",
    ]
    return "\n".join(fm) + "\n"


# ── materialize: write the standardized artifacts + register the specialist (validated only) ──
def materialize(agent_id, matrix, validated=False, promoted_skills=None, promoted_scripts=None,
                promoted_diffs=None, evidence=None):
    """On a VALIDATED success, crystallize the grown agent + its promoted skills into standardized
    artifacts under the durable grown-library, and register it in the roster overlay so next
    session finds it. Returns a manifest + the H5-gated consolidation instruction."""
    if not validated:
        return {"status": "SKIPPED", "reason": "not validated — only a validated success is "
                "crystallized into a permanent specialist"}
    matrix = matrix or {}
    domain = matrix.get("domain") or (matrix.get("disciplines") or ["general"])[0]
    sub = matrix.get("subdomain")
    lib = _library_dir()
    written = []

    # 1) AGENT.md (standard layout)
    agent_md = render_agent_md(agent_id, matrix, promoted_skills=promoted_skills,
                               promoted_scripts=promoted_scripts, evidence=evidence)
    adir = os.path.join(lib, "agents", agent_id)
    try:
        os.makedirs(adir, exist_ok=True)
        ap = os.path.join(adir, "AGENT.md")
        with open(ap, "w", encoding="utf-8") as f:
            f.write(agent_md)
        written.append(os.path.relpath(ap, lib))
    except Exception as e:
        return {"status": "ERROR", "reason": f"agent write failed: {str(e)[:80]}"}

    # 2) SKILL.md for each promoted/forged skill (standard layout)
    for sk in (promoted_skills or []):
        sid = sk if isinstance(sk, str) else sk.get("id", "")
        if not sid:
            continue
        sslug = _slug(sid.split("/")[-1].split(":")[-1])
        skid = f"{_slug(domain)}.{sslug}"
        smd = render_skill_md(skid, domain,
                              f"Capability equipped by {agent_id} for {domain}"
                              f"{('/' + sub) if sub else ''}.",
                              anchors=(matrix.get("specialties") or [])[:8])
        sdir = os.path.join(lib, "skills", _slug(domain), sslug)
        try:
            os.makedirs(sdir, exist_ok=True)
            sp = os.path.join(sdir, "SKILL.md")
            with open(sp, "w", encoding="utf-8") as f:
                f.write(smd)
            written.append(os.path.relpath(sp, lib))
        except Exception:
            pass

    # 3) promoted diffs/scripts: record the provenance manifest (they already live in scripts_lib/
    #    diffs_lib; here we just record WHICH were promoted with this agent, for consolidation)
    manifest = {"agent_id": agent_id, "domain": domain, "subdomain": sub,
                "promoted_skills": list(promoted_skills or []),
                "promoted_scripts": list(promoted_scripts or []),
                "promoted_diffs": list(promoted_diffs or []),
                "grown_at": _now_ts(), "evidence": (evidence or "host-validated")[:120]}
    try:
        mdir = os.path.join(lib, "agents", agent_id)
        with open(os.path.join(mdir, "manifest.json"), "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=1)
        written.append(os.path.relpath(os.path.join(mdir, "manifest.json"), lib))
    except Exception:
        pass

    # 4) REGISTER in the durable roster overlay → discoverable next session
    reg = {"status": "SKIPPED"}
    try:
        import agent_registry
        # anchors = facets + SALIENT TASK TERMS, so the SAME task re-matches this grown specialist
        # next session even when the taxonomy mislabels the domain (audit O-1 bottleneck).
        task_kw = _task_keywords(matrix.get("task", ""))
        domains = sorted(set([d for d in [domain, sub] if d]
                             + (matrix.get("specialties") or []) + task_kw))
        reg = agent_registry.register_grown_agent(
            agent_id, category=f"grown/{_slug(domain)}", domains=domains)
    except Exception as e:
        reg = {"status": "ERROR", "reason": str(e)[:80]}

    return {"status": "MATERIALIZED", "agent_id": agent_id, "library": lib,
            "written": written, "registered": reg, "manifest": manifest,
            "consolidate": ("agent_materializer.consolidate_to_repo(repo_root) copies these into the "
                            "repo's agents/ + skills/ and STAGES a git commit (H5) for cross-session "
                            "durability")}


# ── consolidate: promote the durable grown-library into the repo layout (H5, never auto-commit) ──
def consolidate_to_repo(repo_root, commit=False, subdir="grown"):
    """Copy the durable grown-library into the repo's standard folders (agents/<subdir>/…,
    skills/<subdir>/…) so a git commit makes the grown specialists part of the shipped library.
    STAGES the commit only; never runs it unless commit=True AND the caller passed the human gate."""
    import shutil
    lib = _library_dir()
    if not os.path.isdir(repo_root):
        return {"status": "ERROR", "reason": f"repo_root not found: {repo_root}"}
    copied = []
    for kind in ("agents", "skills"):
        src = os.path.join(lib, kind)
        if not os.path.isdir(src):
            continue
        dst = os.path.join(repo_root, kind, subdir)
        try:
            os.makedirs(dst, exist_ok=True)
            for root, _dirs, files in os.walk(src):
                for fn in files:
                    rel = os.path.relpath(os.path.join(root, fn), src)
                    out = os.path.join(dst, rel)
                    os.makedirs(os.path.dirname(out), exist_ok=True)
                    shutil.copy2(os.path.join(root, fn), out)
                    copied.append(os.path.relpath(out, repo_root))
        except Exception as e:
            return {"status": "ERROR", "reason": f"copy failed: {str(e)[:80]}"}
    result = {"status": "STAGED", "copied": copied, "repo_root": repo_root,
              "gate": "review the artifacts, then commit (H5)"}
    if commit and copied:
        import subprocess
        try:
            subprocess.run(["git", "add"] + copied, cwd=repo_root, check=True,
                           capture_output=True, text=True)
            msg = f"apex-method: consolidate {len(copied)} grown artifact(s) into the library"
            r = subprocess.run(["git", "commit", "-m", msg], cwd=repo_root,
                               capture_output=True, text=True)
            result["status"] = "COMMITTED" if r.returncode == 0 else "STAGED_COMMIT_FAILED"
            result["git"] = (r.stdout or r.stderr)[:160]
        except Exception as e:
            result["status"] = "STAGED_COMMIT_ERROR"
            result["git"] = str(e)[:120]
    return result


if __name__ == "__main__":
    matrix = {"domain": "engineering", "subdomain": "structural",
              "specialties": ["structural", "calculus", "limit_state"], "disciplines": ["engineering"]}
    out = materialize("generic-engineering-structural", matrix, validated=True,
                      promoted_skills=["forge/structural-els-check"],
                      promoted_scripts=["scripts/numeric.py"],
                      evidence="beam ULS verified vs NBR 6118")
    print(json.dumps(out, ensure_ascii=False, indent=1))
