---
skill_id: security.attack_tree_construction
name: "attack-tree-construction"
description: "'Build comprehensive attack trees to visualize threat paths. Use when mapping attack scenarios, identifying defense gaps, or communicating security risks to stakeholders.'"
version: v00.33.0
status: CANDIDATE
domain_path: security/attack-tree-construction
anchors:
  - attack
  - tree
  - construction
  - build
  - comprehensive
  - trees
  - visualize
  - threat
  - paths
  - mapping
source_repo: antigravity-awesome-skills
risk: unknown
languages: [dsl]
llm_compat: {claude: full, gpt4o: partial, gemini: partial, llama: minimal}
apex_version: v00.33.0
---

> AUTHORIZED USE ONLY: Use this skill only for authorized security assessments, defensive validation, or controlled educational environments.

# Attack Tree Construction

Systematic attack path visualization and analysis.

## Use this skill when

- Visualizing complex attack scenarios
- Identifying defense gaps and priorities
- Communicating risks to stakeholders
- Planning defensive investments or test scopes

## Do not use this skill when

- You lack authorization or a defined scope to model the system
- The task is a general risk review without attack-path modeling
- The request is unrelated to security assessment or design

## Instructions

- Confirm scope, assets, and the attacker goal for the root node.
- Decompose into sub-goals with AND/OR structure.
- Annotate leaves with cost, skill, time, and detectability.
- Map mitigations per branch and prioritize high-impact paths.
- If detailed templates are required, open `resources/implementation-playbook.md`.

## Safety

- Share attack trees only with authorized stakeholders.
- Avoid including sensitive exploit details unless required.

## Resources

- `resources/implementation-playbook.md` for detailed patterns, templates, and examples.

## Diff History
- **v00.33.0**: Ingested from antigravity-awesome-skills community repo
