---
skill_id: engineering_agentops.finishing-a-development-branch
name: finishing-a-development-branch
description: >
  Guia o encerramento de uma branch de desenvolvimento com 4 opções estruturadas:
  merge local, push+PR, manter como-está, ou descartar com confirmação.
  Verifica testes antes de qualquer opção. Limpa worktree para opções 1 e 4.
version: v00.36.0
status: ADOPTED
domain_path: engineering_agentops/finishing-a-development-branch
source_repo: obra/superpowers
risk: safe
tier: ADAPTED
anchors:
  - branch_finishing
  - merge
  - pull_request
  - worktree_cleanup
  - git_workflow
  - branch_management
  - pr_creation
cross_domain_bridges:
  - to: engineering_agentops.using-git-worktrees
    strength: 0.95
    reason: "limpa o worktree criado por using-git-worktrees — par obrigatório"
  - to: engineering_agentops.subagent-driven-development
    strength: 0.90
    reason: "chamado ao final de toda sessão subagent-driven-development"
  - to: engineering_agentops.executing-plans
    strength: 0.90
    reason: "chamado ao final de toda sessão executing-plans"
  - to: engineering_git.pull_request_workflow
    strength: 0.85
    reason: "opção 2 (Push+PR) usa o workflow padrão de PR do engineering_git"
  - to: engineering_agentops.verification-before-completion
    strength: 0.92
    reason: "verifica testes ANTES de apresentar opções — aplicação direta do princípio"
input_schema:
  - name: feature_branch
    type: string
    description: "Nome da branch de feature a finalizar"
    required: true
  - name: base_branch
    type: string
    description: "Branch base (main/master/develop)"
    required: false
    default: "main"
  - name: worktree_path
    type: string
    description: "Path do worktree a limpar (se aplicável)"
    required: false
output_schema:
  - name: chosen_option
    type: string
    description: "MERGED | PR_CREATED | KEPT | DISCARDED"
  - name: pr_url
    type: string
    description: "URL do PR criado (se opção 2)"
  - name: cleanup_done
    type: boolean
    description: "Se worktree foi removido"
what_if_fails: >
  Se testes falharem: não apresentar opções — reportar falhas e aguardar correção.
  Se merge conflitar: reportar conflitos especificamente, não tentar resolver automaticamente.
  Se discard sem confirmação: NUNCA executar — sempre exigir 'discard' digitado.
synergy_map:
  - type: skill
    ref: engineering_agentops.using-git-worktrees
    benefit: "limpa o worktree criado por este skill"
  - type: skill
    ref: engineering_agentops.verification-before-completion
    benefit: "aplica verificação obrigatória antes de apresentar opções"
  - type: skill
    ref: engineering_agentops.requesting-code-review
    benefit: "review final antes do merge é boa prática complementar"
security:
  - risk: "Discard acidental destroi trabalho irreversivelmente"
    mitigation: "Exigir confirmação digitada 'discard' — nunca aceitar implícito"
  - risk: "Merge com testes falhando"
    mitigation: "Verificar testes ANTES de apresentar qualquer opção — nunca pular"
  - risk: "Force-push sem consentimento"
    mitigation: "NUNCA force-push sem pedido explícito do usuário"
executor: LLM_BEHAVIOR
---

# Finishing a Development Branch

## Overview

Guide completion of development work by presenting clear options and handling chosen workflow.

**Core principle:** Verify tests → Present options → Execute choice → Clean up.

**Announce at start:** "I'm using the finishing-a-development-branch skill to complete this work."

## The Process

### Step 1: Verify Tests

**Before presenting options, verify tests pass:**

```bash
# Run project's test suite
npm test / cargo test / pytest / go test ./...
```

**If tests fail:**
```
Tests failing (<N> failures). Must fix before completing:

[Show failures]

Cannot proceed with merge/PR until tests pass.
```

Stop. Don't proceed to Step 2.

**If tests pass:** Continue to Step 2.

### Step 2: Determine Base Branch

```bash
# Try common base branches
git merge-base HEAD main 2>/dev/null || git merge-base HEAD master 2>/dev/null
```

Or ask: "This branch split from main - is that correct?"

### Step 3: Present Options

Present exactly these 4 options:

```
Implementation complete. What would you like to do?

1. Merge back to <base-branch> locally
2. Push and create a Pull Request
3. Keep the branch as-is (I'll handle it later)
4. Discard this work

Which option?
```

**Don't add explanation** - keep options concise.

### Step 4: Execute Choice

#### Option 1: Merge Locally

```bash
# Switch to base branch
git checkout <base-branch>

# Pull latest
git pull

# Merge feature branch
git merge <feature-branch>

# Verify tests on merged result
<test command>

# If tests pass
git branch -d <feature-branch>
```

Then: Cleanup worktree (Step 5)

#### Option 2: Push and Create PR

```bash
# Push branch
git push -u origin <feature-branch>

# Create PR
gh pr create --title "<title>" --body "$(cat <<'EOF'
## Summary
<2-3 bullets of what changed>

## Test Plan
- [ ] <verification steps>
EOF
)"
```

Then: Cleanup worktree (Step 5)

#### Option 3: Keep As-Is

Report: "Keeping branch <name>. Worktree preserved at <path>."

**Don't cleanup worktree.**

#### Option 4: Discard

**Confirm first:**
```
This will permanently delete:
- Branch <name>
- All commits: <commit-list>
- Worktree at <path>

Type 'discard' to confirm.
```

Wait for exact confirmation.

If confirmed:
```bash
git checkout <base-branch>
git branch -D <feature-branch>
```

Then: Cleanup worktree (Step 5)

### Step 5: Cleanup Worktree

**For Options 1, 2, 4:**

Check if in worktree:
```bash
git worktree list | grep $(git branch --show-current)
```

If yes:
```bash
git worktree remove <worktree-path>
```

**For Option 3:** Keep worktree.

## Quick Reference

| Option | Merge | Push | Keep Worktree | Cleanup Branch |
|--------|-------|------|---------------|----------------|
| 1. Merge locally | ✓ | - | - | ✓ |
| 2. Create PR | - | ✓ | ✓ | - |
| 3. Keep as-is | - | - | ✓ | - |
| 4. Discard | - | - | - | ✓ (force) |

## Common Mistakes

**Skipping test verification**
- **Problem:** Merge broken code, create failing PR
- **Fix:** Always verify tests before offering options

**Open-ended questions**
- **Problem:** "What should I do next?" → ambiguous
- **Fix:** Present exactly 4 structured options

**Automatic worktree cleanup**
- **Problem:** Remove worktree when might need it (Option 2, 3)
- **Fix:** Only cleanup for Options 1 and 4

**No confirmation for discard**
- **Problem:** Accidentally delete work
- **Fix:** Require typed "discard" confirmation

## Red Flags

**Never:**
- Proceed with failing tests
- Merge without verifying tests on result
- Delete work without confirmation
- Force-push without explicit request

**Always:**
- Verify tests before offering options
- Present exactly 4 options
- Get typed confirmation for Option 4
- Clean up worktree for Options 1 & 4 only

## Integration

**Called by:**
- **subagent-driven-development** (Step 7) - After all tasks complete
- **executing-plans** (Step 5) - After all batches complete

**Pairs with:**
- **using-git-worktrees** - Cleans up worktree created by that skill
