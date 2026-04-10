---
skill_id: engineering_agentops.using-git-worktrees
name: using-git-worktrees
description: >
  Cria workspaces git isolados para desenvolvimento paralelo sem troca de branches.
  Processo sistemático: verificar diretório existente → checar CLAUDE.md → perguntar ao usuário.
  Verifica .gitignore antes de criar, roda setup do projeto, valida baseline de testes.
version: v00.36.0
status: ADAPTED
domain_path: engineering_agentops/using-git-worktrees
source_repo: obra/superpowers
risk: safe
tier: ADAPTED
anchors:
  - git_worktrees
  - isolation
  - parallel_development
  - workspace
  - branch_isolation
  - git
cross_domain_bridges:
  - to: engineering_agentops.subagent-driven-development
    strength: 0.90
    reason: "SDD requer worktree isolado como pré-requisito obrigatório"
  - to: engineering_agentops.executing-plans
    strength: 0.88
    reason: "executing-plans requer worktree isolado como pré-requisito obrigatório"
  - to: engineering_agentops.finishing-a-development-branch
    strength: 0.95
    reason: "finishing limpa o worktree criado por este skill — par obrigatório"
  - to: engineering_git.worktree_management
    strength: 0.90
    reason: "extensão do workflow padrão de engineering_git com padrões de segurança adicionais"
input_schema:
  - name: branch_name
    type: string
    description: "Nome da branch/feature para o worktree"
    required: true
  - name: base_branch
    type: string
    description: "Branch base para criar o worktree"
    required: false
    default: "main"
  - name: worktree_location_preference
    type: string
    description: ".worktrees/ | worktrees/ | ~/.config/superpowers/worktrees/"
    required: false
output_schema:
  - name: worktree_path
    type: string
    description: "Path completo do worktree criado"
  - name: baseline_tests_pass
    type: boolean
    description: "Se os testes passaram no baseline antes de qualquer implementação"
  - name: setup_ran
    type: boolean
    description: "Se npm install / pip install / etc. foi executado"
what_if_fails: >
  Se diretório não está no .gitignore: adicionar imediatamente antes de criar o worktree.
  Se testes do baseline falharem: reportar e perguntar se prossegue ou investiga.
  Se setup falhar (npm install, etc.): reportar erro específico — não prosseguir silenciosamente.
synergy_map:
  - type: skill
    ref: engineering_agentops.finishing-a-development-branch
    benefit: "par obrigatório: este cria, finishing limpa"
  - type: skill
    ref: engineering_agentops.subagent-driven-development
    benefit: "pré-requisito para SDD"
  - type: skill
    ref: engineering_agentops.executing-plans
    benefit: "pré-requisito para executing-plans"
security:
  - risk: "Worktree não ignorado pelo git causa commit acidental de conteúdo de worktree"
    mitigation: "SEMPRE verificar git check-ignore antes de criar worktree project-local; adicionar ao .gitignore se necessário"
  - risk: "Baseline de testes falhando mascara regressões introduzidas durante desenvolvimento"
    mitigation: "Verificar baseline ANTES de qualquer implementação; recusar prosseguir com baseline quebrado"
---

# Using Git Worktrees

## Overview

Git worktrees create isolated workspaces sharing the same repository, allowing work on multiple branches simultaneously without switching.

**Core principle:** Systematic directory selection + safety verification = reliable isolation.

**Announce at start:** "I'm using the using-git-worktrees skill to set up an isolated workspace."

## Directory Selection Process

Follow this priority order:

### 1. Check Existing Directories

```bash
# Check in priority order
ls -d .worktrees 2>/dev/null     # Preferred (hidden)
ls -d worktrees 2>/dev/null      # Alternative
```

**If found:** Use that directory. If both exist, `.worktrees` wins.

### 2. Check CLAUDE.md

```bash
grep -i "worktree.*director" CLAUDE.md 2>/dev/null
```

**If preference specified:** Use it without asking.

### 3. Ask User

If no directory exists and no CLAUDE.md preference:

```
No worktree directory found. Where should I create worktrees?

1. .worktrees/ (project-local, hidden)
2. ~/.config/superpowers/worktrees/<project-name>/ (global location)

Which would you prefer?
```

## Safety Verification

### For Project-Local Directories (.worktrees or worktrees)

**MUST verify directory is ignored before creating worktree:**

```bash
# Check if directory is ignored (respects local, global, and system gitignore)
git check-ignore -q .worktrees 2>/dev/null || git check-ignore -q worktrees 2>/dev/null
```

**If NOT ignored:**

Per Jesse's rule "Fix broken things immediately":
1. Add appropriate line to .gitignore
2. Commit the change
3. Proceed with worktree creation

**Why critical:** Prevents accidentally committing worktree contents to repository.

### For Global Directory (~/.config/superpowers/worktrees)

No .gitignore verification needed - outside project entirely.

## Creation Steps

### 1. Detect Project Name

```bash
project=$(basename "$(git rev-parse --show-toplevel)")
```

### 2. Create Worktree

```bash
# Determine full path
case $LOCATION in
  .worktrees|worktrees)
    path="$LOCATION/$BRANCH_NAME"
    ;;
  ~/.config/superpowers/worktrees/*)
    path="~/.config/superpowers/worktrees/$project/$BRANCH_NAME"
    ;;
esac

# Create worktree with new branch
git worktree add "$path" -b "$BRANCH_NAME"
cd "$path"
```

### 3. Run Project Setup

Auto-detect and run appropriate setup:

```bash
# Node.js
if [ -f package.json ]; then npm install; fi

# Rust
if [ -f Cargo.toml ]; then cargo build; fi

# Python
if [ -f requirements.txt ]; then pip install -r requirements.txt; fi
if [ -f pyproject.toml ]; then poetry install; fi

# Go
if [ -f go.mod ]; then go mod download; fi
```

### 4. Verify Clean Baseline

Run tests to ensure worktree starts clean:

```bash
# Examples - use project-appropriate command
npm test
cargo test
pytest
go test ./...
```

**If tests fail:** Report failures, ask whether to proceed or investigate.

**If tests pass:** Report ready.

### 5. Report Location

```
Worktree ready at <full-path>
Tests passing (<N> tests, 0 failures)
Ready to implement <feature-name>
```

## Quick Reference

| Situation | Action |
|-----------|--------|
| `.worktrees/` exists | Use it (verify ignored) |
| `worktrees/` exists | Use it (verify ignored) |
| Both exist | Use `.worktrees/` |
| Neither exists | Check CLAUDE.md → Ask user |
| Directory not ignored | Add to .gitignore + commit |
| Tests fail during baseline | Report failures + ask |
| No package.json/Cargo.toml | Skip dependency install |

## Common Mistakes

### Skipping ignore verification

- **Problem:** Worktree contents get tracked, pollute git status
- **Fix:** Always use `git check-ignore` before creating project-local worktree

### Assuming directory location

- **Problem:** Creates inconsistency, violates project conventions
- **Fix:** Follow priority: existing > CLAUDE.md > ask

### Proceeding with failing tests

- **Problem:** Can't distinguish new bugs from pre-existing issues
- **Fix:** Report failures, get explicit permission to proceed

### Hardcoding setup commands

- **Problem:** Breaks on projects using different tools
- **Fix:** Auto-detect from project files (package.json, etc.)

## Example Workflow

```
You: I'm using the using-git-worktrees skill to set up an isolated workspace.

[Check .worktrees/ - exists]
[Verify ignored - git check-ignore confirms .worktrees/ is ignored]
[Create worktree: git worktree add .worktrees/auth -b feature/auth]
[Run npm install]
[Run npm test - 47 passing]

Worktree ready at /Users/jesse/myproject/.worktrees/auth
Tests passing (47 tests, 0 failures)
Ready to implement auth feature
```

## Red Flags

**Never:**
- Create worktree without verifying it's ignored (project-local)
- Skip baseline test verification
- Proceed with failing tests without asking
- Assume directory location when ambiguous
- Skip CLAUDE.md check

**Always:**
- Follow directory priority: existing > CLAUDE.md > ask
- Verify directory is ignored for project-local
- Auto-detect and run project setup
- Verify clean test baseline

## Integration

**Called by:**
- **brainstorming** (Phase 4) - REQUIRED when design is approved and implementation follows
- **subagent-driven-development** - REQUIRED before executing any tasks
- **executing-plans** - REQUIRED before executing any tasks
- Any skill needing isolated workspace

**Pairs with:**
- **finishing-a-development-branch** - REQUIRED for cleanup after work complete
