---
skill_id: community.general.ux_copy
name: "ux-copy"
description: "'Generate UX microcopy in StyleSeed's Toss-inspired voice for buttons, empty states, errors, toasts, confirmations, and form guidance.'"
version: v00.33.0
status: CANDIDATE
domain_path: community/general/ux-copy
anchors:
  - copy
  - generate
  - microcopy
  - styleseed
  - toss
  - inspired
  - voice
  - buttons
  - empty
  - states
source_repo: antigravity-awesome-skills
risk: safe
languages: [dsl]
llm_compat: {claude: full, gpt4o: partial, gemini: partial, llama: minimal}
apex_version: v00.33.0
---

# UX Copy

## Overview

Part of [StyleSeed](https://github.com/bitjaru/styleseed), this skill generates concise product copy for common UI states. It follows the Toss-inspired tone: casual but polite, direct, active, and specific enough to help the user recover or proceed.

## When to Use

- Use when you need button labels, helper text, toasts, empty states, or error messages
- Use when a feature has functional UI but weak or robotic wording
- Use when you want consistent product voice across a flow
- Use when confirmation dialogs or state feedback need better phrasing

## Tone Rules

- casual but polite
- active voice over passive voice
- positive framing where it stays honest
- plain language instead of internal jargon
- concise wording where every word earns its place

## Common Patterns

### Buttons

Use a short action verb plus object when needed.

### Empty States

Start with a friendly observation, then suggest the next action.

### Errors

Explain what happened in user-facing language and what to do next. Do not surface raw internal error strings.

### Toasts

Confirm the result quickly. Add an undo action for reversible destructive behavior.

### Forms

Use clear labels, useful placeholders, specific helper text, and corrective error messages.

### Confirmation Dialogs

State the action in plain language and explain the consequence if the decision is risky or irreversible.

## Output

Return:
1. The requested microcopy grouped by UI surface
2. Notes on tone or localization considerations if relevant
3. Any places where the UX likely needs a structural fix in addition to better copy

## Best Practices

- Make the next action obvious
- Avoid generic labels like "Submit" or "OK" when the action can be named precisely
- Blame the system, not the user, when something fails
- Keep error and empty states useful even without visual context

## Additional Resources

- [StyleSeed repository](https://github.com/bitjaru/styleseed)
- [Source skill](https://github.com/bitjaru/styleseed/blob/main/seeds/toss/.claude/skills/ux-copy/SKILL.md)

## Diff History
- **v00.33.0**: Ingested from antigravity-awesome-skills community repo
