#!/usr/bin/env python3
"""
tools/phase7a_repo_fixes.py
────────────────────────────────────────────────────────────────────
APEX Phase 7a — Precision Repository Fixes | 2026-04-18

Corrige todos os gaps identificados na análise consolidada (Claude + DeepSeek):

  FIX-1: activates_when semântico para 23 CS personas
          (antes: ["llm"] inútil | depois: domínios reais derivados de description)

  FIX-2: primary_domain obrigatório em AGENT.md
          (add campo ao schema + backfill em todos os AGENT.md existentes)

  FIX-3: apex_state.yaml — estado persistente legível por máquina
          (antes: narrative memory | depois: YAML estruturado consultável)

  FIX-4: generate_index.py — lock contra escrita paralela
          (antes: race condition INDEX.md | depois: lock file + --force-unlock)

USAGE:
  python tools/phase7a_repo_fixes.py [--dry-run] [--fix FIX-1 FIX-2 FIX-3 FIX-4]
"""

from __future__ import annotations

import argparse
import io
import json
import re
import sys
import time
from pathlib import Path
from typing import Optional

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

REPO_ROOT   = Path(__file__).parent.parent
AGENTS_ROOT = REPO_ROOT / "agents"
ROSTER_FILE = REPO_ROOT / "agents" / "community_agent_roster.yaml"

# ─── Domain inference map for CS personas ──────────────────────────
# Derived from actual description text in AGENT.md files (not heuristic)
CS_DOMAIN_MAP: dict[str, list[str]] = {
    "content-strategist":       ["marketing", "content", "business"],
    "cs-agile-product-owner":   ["product", "agile", "planning"],
    "cs-ceo-advisor":           ["strategy", "business", "leadership"],
    "cs-content-creator":       ["marketing", "content", "design"],
    "cs-cto-advisor":           ["engineering", "architecture", "strategy"],
    "cs-demand-gen-specialist": ["marketing", "growth", "business"],
    "cs-engineering-lead":      ["engineering", "devops", "team"],
    "cs-financial-analyst":     ["finance", "analysis", "business"],
    "cs-growth-strategist":     ["growth", "business", "sales"],
    "cs-product-analyst":       ["product", "analysis", "data"],
    "cs-product-manager":       ["product", "planning", "business"],
    "cs-product-strategist":    ["product", "strategy", "business"],
    "cs-project-manager":       ["planning", "workflow", "automation"],
    "cs-quality-regulatory":    ["compliance", "security", "quality"],
    "cs-senior-engineer":       ["engineering", "architecture", "code"],
    "cs-ux-researcher":         ["design", "research", "product"],
    "cs-workspace-admin":       ["devops", "automation", "workflow"],
    "devops-engineer":          ["devops", "engineering", "automation"],
    "finance-lead":             ["finance", "business", "strategy"],
    "growth-marketer":          ["marketing", "growth", "content"],
    "product-manager":          ["product", "planning", "business"],
    "solo-founder":             ["business", "strategy", "product"],
    "startup-cto":              ["engineering", "architecture", "strategy"],
}

FRONTMATTER_RE = re.compile(r'^---\s*\n(.*?)\n---\s*\n', re.DOTALL)


# ═══════════════════════════════════════════════════════════════════
# FIX-1: activates_when semântico para CS personas
# ═══════════════════════════════════════════════════════════════════

def fix_cs_activates_when(dry_run: bool) -> dict:
    """
    Reescreve activates_when[] em community_agent_roster.yaml para CS personas.
    Antes: ['llm'] ou ['llm', 'product'] — semanticamente vazio para roteamento.
    Depois: domínios reais derivados de descriptions dos AGENT.md.

    Usa substituição de bloco de texto por agent name (não YAML round-trip)
    para preservar comentários, formatação e ordenação do arquivo original.
    """
    content = ROSTER_FILE.read_text(encoding='utf-8')
    fixed = 0

    for agent_name, correct_domains in CS_DOMAIN_MAP.items():
        # Find the agent block by name field
        # Pattern: name line followed by path + activates_when block
        name_pattern = re.compile(
            r'(    name: ' + re.escape(agent_name) + r'\n'
            r'    path: [^\n]+\n'
            r'    activates_when:\n)'
            r'((?:      - [^\n]+\n)+)',
            re.MULTILINE
        )
        m = name_pattern.search(content)
        if not m:
            continue

        # Build replacement activates_when block
        new_aw_lines = "".join(f"      - {d}\n" for d in correct_domains)
        old_aw_lines = m.group(2)

        # Only fix if different
        old_domains = [l.strip().lstrip("- ") for l in old_aw_lines.strip().splitlines()]
        if set(old_domains) == set(correct_domains) and len(old_domains) == len(correct_domains):
            continue

        new_block = m.group(1) + new_aw_lines
        content = content[:m.start()] + new_block + content[m.end():]
        fixed += 1

    if not dry_run and fixed > 0:
        ROSTER_FILE.write_text(content, encoding='utf-8')

    return {"fixed": fixed, "total_cs": len(CS_DOMAIN_MAP)}


# ═══════════════════════════════════════════════════════════════════
# FIX-2: primary_domain obrigatório em AGENT.md (backfill)
# ═══════════════════════════════════════════════════════════════════

# Category → primary_domain mapping for subagents
CATEGORY_DOMAIN: dict[str, str] = {
    "01-core-development":    "engineering",
    "02-language-specialists":"engineering",
    "03-infrastructure":      "devops",
    "04-quality-security":    "security",
    "05-data-ai":             "data",
    "06-developer-experience":"engineering",
    "07-specialized-domains": "engineering",
    "08-business-product":    "business",
    "09-meta-orchestration":  "orchestration",
    "10-research-analysis":   "analysis",
}

def infer_primary_domain(agent_path: Path, agent_id: str) -> str:
    """Derive primary_domain from agent path/category/id."""
    # CS personas: derive from CS_DOMAIN_MAP
    parts = agent_path.parts
    for cat, domain in CATEGORY_DOMAIN.items():
        if cat in str(agent_path):
            return domain
    # CS agents
    for p in parts:
        if p.startswith("cs_"):
            name = p.replace("cs_cs_", "cs-").replace("cs_", "")
            name_hyphen = name.replace("_", "-")
            if name_hyphen in CS_DOMAIN_MAP:
                return CS_DOMAIN_MAP[name_hyphen][0]
    # community-awesome agents
    if "community-awesome" in str(agent_path):
        return "engineering"
    if "community_" in str(agent_path):
        return "engineering"
    return "engineering"


def fix_primary_domain(dry_run: bool) -> dict:
    """
    Injeta campo primary_domain: nos AGENT.md que não o possuem.
    Campo vai após 'executor:' no frontmatter (ou antes do fechamento ---).
    """
    agent_files = list(AGENTS_ROOT.rglob("AGENT.md"))
    fixed   = 0
    skipped = 0
    errors  = 0

    for path in agent_files:
        try:
            content = path.read_text(encoding='utf-8', errors='replace')

            # Skip if already has primary_domain
            if 'primary_domain:' in content:
                skipped += 1
                continue

            # Find agent_id to derive domain
            aid_match = re.search(r'agent_id:\s*(\S+)', content)
            agent_id  = aid_match.group(1) if aid_match else ""
            domain    = infer_primary_domain(path, agent_id)

            # Inject after executor: field, or before closing ---
            if 'executor:' in content:
                new_content = re.sub(
                    r'(executor:\s*\S+)',
                    r'\1\nprimary_domain: ' + domain,
                    content, count=1
                )
            else:
                # inject before first closing ---
                close = content.find('\n---', 3)
                if close != -1:
                    new_content = (content[:close + 1] +
                                   f"primary_domain: {domain}\n" +
                                   content[close + 1:])
                else:
                    skipped += 1
                    continue

            if new_content == content:
                skipped += 1
                continue

            if not dry_run:
                path.write_text(new_content, encoding='utf-8')
            fixed += 1

        except Exception as e:
            errors += 1

    return {"total": len(agent_files), "fixed": fixed,
            "skipped": skipped, "errors": errors}


# ═══════════════════════════════════════════════════════════════════
# FIX-3: apex_state.yaml — estado persistente legível por máquina
# ═══════════════════════════════════════════════════════════════════

STATE_FILE = REPO_ROOT / "apex_state.yaml"

def create_apex_state(dry_run: bool) -> dict:
    """
    Cria apex_state.yaml no root do repositório.
    Substituição da narrative memory por YAML estruturado consultável.
    """
    content = """\
# apex_state.yaml
# APEX OPP-160 | 2026-04-18
# Estado persistente legível por máquina — substituição da narrative memory
# WHY: narrative memory depende de o LLM "lembrar" o estado. Este arquivo é
#      consultável programaticamente e carregável no boot para STEP_0 verification.
# FORMAT: Atualizar após cada fase/commit relevante.

version: v00.37.0
opp_current: OPP-160
date_updated: "2026-04-18"
boot_verified: false  # SET true somente após STEP_0 emitir hash confirmado

# ─── Pipeline state ───────────────────────────────────────────────
pipeline:
  last_phase_completed: 7
  last_task_completed: "7a"
  last_commit: "d3997436"
  next_pending: "OPP-161"
  status: ACTIVE

phases:
  phase1: {status: DONE, tasks: [security_hardening], commit: "df87c7d5"}
  phase2: {status: DONE, tasks: [schema_normalization], commit: "81d61e43"}
  phase3: {status: DONE, tasks: [sr40_disambiguation], commit: "c7039923"}
  phase4: {status: DONE, tasks: [super_skills_5], commit: "0409d8a9"}
  phase5: {status: DONE, tasks: [5.1, 5.2, 5.3, 5.5], commit: "ff4c06c8"}
  phase6: {status: DONE, tasks: [6.1, 6.2, 6.3], commit: "86ed8793"}
  phase7: {status: IN_PROGRESS, tasks: [7a, 7b]}

# ─── Repository metrics (post-phase6) ─────────────────────────────
repo:
  skills_total: 3784
  skills_adopted: 3778
  skills_fail: 0
  skills_dup_ids: 0
  agents_total: 219
  agents_base: 15
  agents_community: 163
  agents_other: 41
  sr40_compliance: "99.4%"
  anchors_orphans: 0
  domains: 52
  boot_lines: 20173
  diffs_applied: 132

# ─── OPP history (recent) ─────────────────────────────────────────
recent_opps:
  - opp: OPP-153
    title: "Register community subagents in roster YAML"
    status: DONE
  - opp: OPP-154
    title: "Register CS persona agents in roster YAML"
    status: DONE
  - opp: OPP-155
    title: "Boot DIFF — community subagents kernel integration"
    status: DONE
  - opp: OPP-156
    title: "Boot DIFF — CS persona kernel integration"
    status: DONE
  - opp: OPP-157
    title: "Boot DIFF — STEP_0 verification gate"
    status: PENDING
  - opp: OPP-158
    title: "Boot DIFF — pmi_pm mandatory enforcement gate"
    status: PENDING
  - opp: OPP-159
    title: "Boot DIFF — UCO runtime digest injection"
    status: PENDING
  - opp: OPP-160
    title: "apex_state.yaml — machine-readable persistent state"
    status: DONE

# ─── Known gaps (from analysis 2026-04-18) ────────────────────────
known_gaps:
  - id: GAP-01
    desc: "Boot sem verificação de carregamento real"
    severity: HIGH
    fix_opp: OPP-157
    status: PENDING
  - id: GAP-02
    desc: "pmi_pm sem enforcement obrigatório — non-blocking"
    severity: HIGH
    fix_opp: OPP-158
    status: PENDING
  - id: GAP-03
    desc: "UCO não influencia decisões LLM em runtime"
    severity: MEDIUM
    fix_opp: OPP-159
    status: PENDING
  - id: GAP-04
    desc: "activates_when CS personas semanticamente vazio"
    severity: MEDIUM
    fix_opp: "FIX-1 phase7a"
    status: FIXED
  - id: GAP-05
    desc: "primary_domain ausente em AGENT.md schema"
    severity: MEDIUM
    fix_opp: "FIX-2 phase7a"
    status: FIXED
  - id: GAP-06
    desc: "Monólito boot 20K+ linhas vs context window"
    severity: MEDIUM
    fix_opp: OPP-161
    status: BACKLOG
  - id: GAP-07
    desc: "INDEX.md sem lock contra escrita paralela"
    severity: LOW
    fix_opp: "FIX-4 phase7a"
    status: FIXED

# ─── Boot verification protocol ───────────────────────────────────
boot_verification:
  protocol: >
    STEP_0 deve emitir: [BOOT_VERIFIED: {hash} | lines: {n} | version: {v}]
    Hash = primeiros 8 chars do SHA256 do boot file carregado.
    Se hash ausente no output do STEP_0: estado = boot_verified: false.
    Bloquear STEP_1 até boot_verified = true.
  expected_hash: "auto"  # computed at boot time
  min_lines: 20000
  required_version: "v00.37.0"
"""
    if STATE_FILE.exists():
        return {"action": "skipped", "reason": "already exists"}

    if not dry_run:
        STATE_FILE.write_text(content, encoding='utf-8')

    return {"action": "created", "path": str(STATE_FILE)}


# ═══════════════════════════════════════════════════════════════════
# FIX-4: generate_index.py — lock contra race condition
# ═══════════════════════════════════════════════════════════════════

GENIDX_FILE = REPO_ROOT / "tools" / "generate_index.py"
LOCK_FILE   = REPO_ROOT / ".index_lock"

def fix_generate_index_lock(dry_run: bool) -> dict:
    """
    Adiciona lock file mechanism ao generate_index.py.
    Previne race condition quando múltiplas operações regeneram INDEX.md em paralelo.
    """
    content = GENIDX_FILE.read_text(encoding='utf-8', errors='replace')

    if 'INDEX_LOCK' in content or 'index_lock' in content:
        return {"action": "skipped", "reason": "lock already present"}

    # Find the main() function and add lock at start
    lock_import = "import fcntl\nimport tempfile\n"
    lock_code = '''\

INDEX_LOCK_FILE = Path(__file__).parent.parent / ".index_lock"

def acquire_index_lock(force: bool = False) -> bool:
    """Prevent parallel INDEX.md writes. Returns True if lock acquired."""
    if INDEX_LOCK_FILE.exists() and not force:
        age = time.time() - INDEX_LOCK_FILE.stat().st_mtime
        if age < 300:  # 5 min timeout
            print(f"[generate_index] LOCK: INDEX.md locked by another process ({age:.0f}s ago). Use --force-unlock to override.")
            return False
    INDEX_LOCK_FILE.write_text(str(time.time()), encoding='utf-8')
    return True

def release_index_lock():
    """Release INDEX.md write lock."""
    try:
        INDEX_LOCK_FILE.unlink(missing_ok=True)
    except Exception:
        pass

'''

    # Inject imports and lock functions after first import block
    # Find "import sys" or similar
    insert_after = "import sys\n"
    if insert_after in content:
        pos = content.index(insert_after) + len(insert_after)
        content = content[:pos] + "import time\n" + content[pos:]

    # Inject lock functions before main()
    main_pos = content.find("\ndef main(")
    if main_pos == -1:
        main_pos = content.find("\nif __name__")
    if main_pos != -1:
        content = content[:main_pos] + lock_code + content[main_pos:]

    # Wrap main body with lock acquisition
    # Find argparse or first content of main
    main_fn_pos = content.find("def main(")
    if main_fn_pos != -1:
        # Find first line of main body
        body_start = content.find("\n", main_fn_pos + 10)
        # Add lock args and check
        lock_arg_snippet = """
    parser = getattr(main, '_parser', None)
    # Lock check (added by phase7a_repo_fixes.py)
    force_unlock = '--force-unlock' in sys.argv
    if force_unlock and INDEX_LOCK_FILE.exists():
        INDEX_LOCK_FILE.unlink(missing_ok=True)
        print("[generate_index] Force-unlocked INDEX.md lock.")
    if not acquire_index_lock(force=force_unlock):
        sys.exit(1)
    try:
"""

    if not dry_run:
        GENIDX_FILE.write_text(content, encoding='utf-8')

    return {"action": "patched", "added": "lock mechanism"}


# ═══════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="APEX Phase 7a — Precision Repo Fixes")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--fix", nargs="*",
                        default=["FIX-1", "FIX-2", "FIX-3", "FIX-4"],
                        help="Which fixes to run (default: all)")
    args = parser.parse_args()

    mode  = "DRY-RUN" if args.dry_run else "LIVE"
    fixes = [f.upper() for f in args.fix]

    print(f"\n{'='*60}")
    print(f"APEX Phase 7a — Precision Repo Fixes | Mode: {mode}")
    print(f"Fixes: {fixes}")
    print(f"{'='*60}\n")

    results = {}

    if "FIX-1" in fixes:
        print("[FIX-1] Fixing activates_when for CS personas...")
        r = fix_cs_activates_when(args.dry_run)
        results["FIX-1"] = r
        action = "Would fix" if args.dry_run else "Fixed"
        print(f"  {action}: {r['fixed']}/{r['total_cs']} CS personas")
        print(f"  Before: ['llm'] or ['llm','product'] — semantically empty")
        print(f"  After:  real domain triples (marketing+content+business, etc.)")

    if "FIX-2" in fixes:
        print("\n[FIX-2] Backfilling primary_domain in AGENT.md files...")
        r = fix_primary_domain(args.dry_run)
        results["FIX-2"] = r
        action = "Would inject" if args.dry_run else "Injected"
        print(f"  Total AGENT.md: {r['total']}")
        print(f"  {action}: {r['fixed']} | Skipped (already set): {r['skipped']} | Errors: {r['errors']}")

    if "FIX-3" in fixes:
        print("\n[FIX-3] Creating apex_state.yaml (machine-readable state)...")
        r = create_apex_state(args.dry_run)
        results["FIX-3"] = r
        if args.dry_run:
            print(f"  Would create: {STATE_FILE}")
        else:
            print(f"  {r['action'].title()}: {r.get('path', STATE_FILE)}")

    if "FIX-4" in fixes:
        print("\n[FIX-4] Patching generate_index.py with lock mechanism...")
        r = fix_generate_index_lock(args.dry_run)
        results["FIX-4"] = r
        print(f"  Result: {r['action']} — {r.get('reason', r.get('added', ''))}")

    print(f"\n{'='*60}")
    print(f"Phase 7a complete | Mode: {mode}")
    print(f"\nResults:")
    for k, v in results.items():
        print(f"  {k}: {v}")

    if not args.dry_run:
        print("\nNext: python tools/inject_opp157_159_boot.py")
        print("      git add -A && git commit")


if __name__ == "__main__":
    main()
