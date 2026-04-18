---
skill_id: community.general.git_pushing
name: "git-pushing"
description: "Use — Stage all changes, create a conventional commit, and push to the remote branch. Use when explicitly asks to push changes (\"
version: v00.33.0
status: ADOPTED
domain_path: community/general/git-pushing
anchors:
  - pushing
  - stage
  - changes
  - create
  - conventional
  - commit
  - push
  - remote
  - branch
  - explicitly
source_repo: antigravity-awesome-skills
risk: safe
languages: [dsl]
llm_compat: {claude: full, gpt4o: partial, gemini: partial, llama: minimal}
apex_version: v00.33.0
executor: LLM_BEHAVIOR
security: {level: standard, pii: false, approval_required: false}
tier: 3
input_schema:
  - name: code_or_task
    type: string
    description: "Code snippet, script, or task description to process"
    required: true
output_schema:
  - name: result
    type: string
    description: "Primary output from git pushing"
---

# Git Push Workflow

Stage all changes, create a conventional commit, and push to the remote branch.

## When to Use
Automatically activate when the user:

- Explicitly asks to push changes ("push this", "commit and push")
- Mentions saving work to remote ("save to github", "push to remote")
- Completes a feature and wants to share it
- Says phrases like "let's push this up" or "commit these changes"

## Workflow

**ALWAYS use the script** - do NOT use manual git commands:

```bash
bash skills/git-pushing/scripts/smart_commit.sh
```

With custom message:

```bash
bash skills/git-pushing/scripts/smart_commit.sh "feat: add feature"
```

Script handles: staging, conventional commit message, Claude footer, push with -u flag.

## Diff History
- **v00.33.0**: Ingested from antigravity-awesome-skills community repo

---

## Why This Skill Exists

Use — Stage all changes, create a conventional commit, and push to the remote branch.

<!-- SR_40: auto-generated from frontmatter `purpose`/`description` (OPP-Phase3). Expand with domain-specific rationale. -->

## What If Fails

If this skill fails to produce the expected output: (1) verify input completeness, (2) retry with more specific context, (3) fall back to the parent workflow without this skill.

<!-- SR_40: auto-generated from frontmatter `what_if_fails` (OPP-Phase3). -->
