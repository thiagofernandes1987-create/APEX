---
skill_id: human_resources.skills
name: "recruiting-pipeline"
description: "Track and manage recruiting pipeline stages. Trigger with 'recruiting update', 'candidate pipeline', 'how many candidates', 'hiring status', or when the user discusses sourcing, screening, interviewin"
version: v00.33.0
status: ADOPTED
domain_path: human-resources/skills
anchors:
  - recruiting
  - pipeline
  - track
  - manage
  - stages
  - trigger
  - update
  - candidate
  - many
  - candidates
  - hiring
  - status
source_repo: knowledge-work-plugins-main
risk: safe
languages: [dsl]
llm_compat: {claude: full, gpt4o: partial, gemini: partial, llama: minimal}
apex_version: v00.33.0
---

# Recruiting Pipeline

Help manage the recruiting pipeline from sourcing through offer acceptance.

## Pipeline Stages

| Stage | Description | Key Actions |
|-------|-------------|-------------|
| Sourced | Identified and reached out | Personalized outreach |
| Screen | Phone/video screen | Evaluate basic fit |
| Interview | On-site or panel interviews | Structured evaluation |
| Debrief | Team decision | Calibrate feedback |
| Offer | Extending offer | Comp package, negotiation |
| Accepted | Offer accepted | Transition to onboarding |

## Metrics to Track

- **Pipeline velocity**: Days per stage
- **Conversion rates**: Stage-to-stage drop-off
- **Source effectiveness**: Which channels produce hires
- **Offer acceptance rate**: Offers extended vs. accepted
- **Time to fill**: Days from req open to offer accepted

## If ATS Connected

Pull candidate data automatically, update statuses, and track pipeline metrics in real time.

## Diff History
- **v00.33.0**: Ingested from knowledge-work-plugins-main — auto-converted to APEX format
