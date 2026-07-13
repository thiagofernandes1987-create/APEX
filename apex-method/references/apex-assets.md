# Full APEX repo — everything mined, nativized or managed

Cloned the complete `thiagofernandes1987-create/APEX` repo (16,508 files) and processed
ALL of it. Honest split: **NATIVIZED** = APEX-authored, adapted into this skill;
**INDEXED** = third-party, referenced with provenance so APEX manages/uses it WITHOUT
copying or relabeling authorship.

## A) NATIVIZED (APEX-authored → now part of this skill)

- **Agent roster (183 agents)** → `catalog/apex_agents_roster.json`, routable via
  `agent_registry.match_task_to_ext_agents()`. 140 community subagents (10 categories) +
  native (architect, critic, theorist, bayesian_curator, meta_reasoning) + cs_* roster.
- **Skill-creation method** → `scripts/skill_forge.py`, ported from APEX `tools/skill_forge.py`
  to the neoformat schema, standalone (stdlib only). `create` + `promote` (CANDIDATE→ADOPTED).
  Verified: generated SKILL.md passes the awesome-skills schema.
- **UCO** (Universal Code Optimizer) → already `scripts/uco_gate.py` (Hamiltonian, loop risk,
  dead code; deterministic, LLM-independent).
- **UCO-Sensor** (303 py, APEX-authored) → indexed as APEX-native in `catalog/managed_assets.json`.
  It is a **spectral code-quality analyzer** (FFT/Wavelet/PELT over 9 UCO channels: H, CC, ILR,
  DSM_d, DSM_c, DI, dead, dups, bugs), multi-language (Py/JS/TS/Java/Go), with SAST/SCA/IaC and
  SARIF output — an open-source SonarQube alternative, no LLM. It's a full service (Docker/ASGI),
  so it runs SEPARATELY and APEX calls its CLI/API; the skill records its interface, not 303 files.

## B) INDEXED third-party (managed references, not copied) → `catalog/managed_assets.json`

**41 assets total (2 native, 39 third-party).** Each entry has: source (raw APEX path),
type, asset_kind, py/skill counts, license (verify-at-source), and treatment. Breakdown:
- **4 skill-collections** (claude-code-toolkit 35, x-cmd 24, claude-code-cli 11, claude-cookbooks 4)
  → installable via scout+approve.
- **14 libraries** (orjson, django-admin-interface, blobfile, torchtyping, claude-agent-sdk,
  anthropic-tools, etc.) → dependencies/tools, referenced upstream.
- catalogs/examples (awesome-claude-code, awesome-claude-skills, community-skill-examples,
  claude-skills) → discovery sources.

Why indexed, not copied: these are third-party works with their own authorship and licenses.
Copying them in and calling them "APEX's own" would misrepresent authorship. Indexing lets
APEX route to, scout, and (on approval) install them — the manage-and-use path you asked for.

## C) MCP servers → `catalog/mcp_registry.json`

**18 MCP servers/plugins** indexed by domain from `integrations/`: engineering, financial-services,
healthcare, legal, life-sciences, marketing, science-physics, plus github-mcp-server,
playwright-mcp, mcp-servers, mcp-reference-servers, connectors, and the official-plugins (28)
and knowledge-work (18) trees.

## D) The manager → `scripts/asset_manager.py`

Lets APEX operate over everything: `summary()`, `managed(kind, type)`, `mcps(domain)`,
`route(need)`. Tested: "mcp server legal" → legal-mcp; "code security review" →
claude-code-security-review. Third-party items always route through scout + approval (H5).

## Honest verdict

Everything in the repo is now either **nativized** (agents, skill_forge, UCO, UCO-Sensor
interface) or **managed** (39 third-party assets + 18 MCPs, indexed with provenance). Nothing
third-party was copied-and-relabeled; nothing is auto-run. That keeps authorship, licensing,
and safety intact while giving APEX full reach over the repo's capabilities.

## UCO-Sensor engines (author's own) → `catalog/uco_sensor_engines.json`

The UCO-Sensor is a full security+quality platform (76+ REST endpoints). 9 engines mapped:
uco_core spectral (NATIVIZED), **SCA/OSV-CVE** (dependency vuln + reachability), **SAST**
(multilang + GHSA fix), **taint/FlowVector**, **IaC scan**, **lang_adapters** (tree-sitter,
multi-language), **governance** (Granger causality, PELT change-points), **HMC autofix repair**,
and predictor/explainer. Only `uco_core` runs standalone (embedded); the rest run via the
UCO-Sensor service CLI/API (`python cli.py scan ./proj`, `/sast`, `/scan-sca`, `/scan-iac`,
`/scan-flow`, `/repair/hmc`), which APEX invokes as a managed service.
