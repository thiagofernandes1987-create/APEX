---
name: template-skill
description: "Apply — Replace with description of the skill and when Claude should use it."
executor: LLM_BEHAVIOR
skill_id: anthropic-skills.template-skill
status: ADOPTED
security: {level: standard, pii: false, approval_required: false}
anchors:
  - llm
tier: 2
input_schema:
  - name: code_or_task
    type: string
    description: "Code snippet, script, or task description to process"
    required: true
  - name: context
    type: string
    description: "Additional context or background information"
    required: false
output_schema:
  - name: result
    type: string
    description: "Generated or refactored code output"
  - name: explanation
    type: string
    description: "Explanation of changes or implementation decisions"
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
