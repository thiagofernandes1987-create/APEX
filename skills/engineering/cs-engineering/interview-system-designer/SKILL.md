---
name: "interview-system-designer"
description: "Implement — This skill should be used when the user asks to 'design interview processes', 'create hiring pipelines', 'calibrate interview loops', 'generate interview questions', 'design compet"
executor: HYBRID
skill_id: engineering.cs-engineering.interview-system-designer
status: CANDIDATE
security: {level: standard, pii: false, approval_required: false}
anchors:
  - engineering
  - design
---

# Interview System Designer

Comprehensive interview loop planning and calibration support for role-based hiring systems.

## Overview

Use this skill to create structured interview loops, standardize question quality, and keep hiring signal consistent across interviewers.

## Core Capabilities

- Interview loop planning by role and level
- Round-by-round focus and timing recommendations
- Suggested question sets by round type
- Framework support for scoring and calibration
- Bias-reduction and process consistency guidance

## Quick Start

```bash
# Generate a loop plan for a role and level
python3 scripts/interview_planner.py --role "Senior Software Engineer" --level senior

# JSON output for integration with internal tooling
python3 scripts/interview_planner.py --role "Product Manager" --level mid --json
```

## Recommended Workflow

1. Run `scripts/interview_planner.py` to generate a baseline loop.
2. Align rounds to role-specific competencies.
3. Validate scoring rubric consistency with interview panel leads.
4. Review for bias controls before rollout.
5. Recalibrate quarterly using hiring outcome data.

## References

- `references/interview-frameworks.md`
- `references/bias_mitigation_checklist.md`
- `references/competency_matrix_templates.md`
- `references/debrief_facilitation_guide.md`

## Common Pitfalls

- Overweighting one round while ignoring other competency signals
- Using unstructured interviews without standardized scoring
- Skipping calibration sessions for interviewers
- Changing hiring bar without documenting rationale

## Best Practices

1. Keep round objectives explicit and non-overlapping.
2. Require evidence for each score recommendation.
3. Use the same baseline rubric across comparable roles.
4. Revisit loop design based on quality-of-hire outcomes.

---

## Why This Skill Exists

Implement — This skill should be used when the user asks to

<!-- SR_40: auto-generated from frontmatter `purpose`/`description` (OPP-Phase3). Expand with domain-specific rationale. -->

## When to Use

Use this skill when the task requires interview system designer capabilities.

<!-- SR_40: auto-generated from frontmatter `when`/`description` (OPP-Phase3). -->

## What If Fails

If this skill fails to produce the expected output: (1) verify input completeness, (2) retry with more specific context, (3) fall back to the parent workflow without this skill.

<!-- SR_40: auto-generated from frontmatter `what_if_fails` (OPP-Phase3). -->
