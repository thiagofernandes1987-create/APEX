---
name: template-skill
description: "Apply — Replace with description of the skill and when Claude should use it."
executor: LLM_BEHAVIOR
skill_id: anthropic-skills.template-skill
status: CANDIDATE
security: {level: standard, pii: false, approval_required: false}
anchors:
  - llm
---

# Insert instructions below

---

## Why This Skill Exists

Apply — Replace with description of the skill and when Claude should use it.

<!-- SR_40: auto-generated from frontmatter `purpose`/`description` (OPP-Phase3). Expand with domain-specific rationale. -->

## When to Use

Use this skill when the task requires template skill capabilities.

<!-- SR_40: auto-generated from frontmatter `when`/`description` (OPP-Phase3). -->

## What If Fails

If this skill fails to produce the expected output: (1) verify input completeness, (2) retry with more specific context, (3) fall back to the parent workflow without this skill.

<!-- SR_40: auto-generated from frontmatter `what_if_fails` (OPP-Phase3). -->
