---
skill_id: human_resources.org_planning
name: "org-planning"
description: "Headcount planning, org design, and team structure optimization. Trigger with 'org planning', 'headcount plan', 'team structure', 'reorg', 'who should we hire next', or when the user is thinking about"
version: v00.33.0
status: ADOPTED
domain_path: human-resources/org-planning
anchors:
  - planning
  - headcount
  - design
  - team
  - structure
  - optimization
  - trigger
  - plan
  - reorg
  - hire
  - next
  - user
source_repo: knowledge-work-plugins-main
risk: safe
languages: [dsl]
llm_compat: {claude: full, gpt4o: partial, gemini: partial, llama: minimal}
apex_version: v00.33.0
---

# Org Planning

Help plan organizational structure, headcount, and team design.

## Planning Dimensions

- **Headcount**: How many people do we need, in what roles, by when?
- **Structure**: Reporting lines, span of control, team boundaries
- **Sequencing**: Which hires are most critical? What's the right order?
- **Budget**: Headcount cost modeling and trade-offs

## Healthy Org Benchmarks

| Metric | Healthy Range | Warning Sign |
|--------|---------------|--------------|
| Span of control | 5-8 direct reports | < 3 or > 12 |
| Management layers | 4-6 for 500 people | Too many = slow decisions |
| IC-to-manager ratio | 6:1 to 10:1 | < 4:1 = top-heavy |
| Team size | 5-9 people | < 4 = lonely, > 12 = hard to manage |

## Output

Produce org charts (text-based), headcount plans with cost modeling, and sequenced hiring roadmaps. Flag structural issues like single points of failure or excessive management overhead.

## Diff History
- **v00.33.0**: Ingested from knowledge-work-plugins-main — auto-converted to APEX format
