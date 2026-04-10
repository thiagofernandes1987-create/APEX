---
skill_id: engineering_agentops.writing-plans
name: writing-plans
description: >
  Cria planos de implementação exaustivos assumindo que o executor tem zero contexto
  do projeto. Cada tarefa tem: arquivo exato a modificar, código completo, steps de
  verificação. DRY, YAGNI, TDD, commits frequentes. Mapeia estrutura de arquivos
  antes de definir tarefas. Tasks de 2-5 minutos cada.
version: v00.36.0
status: ADAPTED
domain_path: engineering_agentops/writing-plans
source_repo: obra/superpowers
risk: safe
tier: ADAPTED
anchors:
  - writing_plans
  - implementation_plan
  - task_breakdown
  - yagni
  - dry
  - tdd
  - planning
  - specification
cross_domain_bridges:
  - to: engineering_agentops.brainstorming
    strength: 0.98
    reason: "brainstorming é o pré-requisito direto — sempre chamado antes de writing-plans"
  - to: engineering_agentops.subagent-driven-development
    strength: 0.95
    reason: "SDD executa o plano criado por este skill — dependência direta"
  - to: engineering_agentops.executing-plans
    strength: 0.92
    reason: "executing-plans também executa o plano criado por este skill"
  - to: engineering_agentops.test-driven-development
    strength: 0.85
    reason: "plano deve incluir steps de TDD explícitos em cada tarefa de implementação"
  - to: engineering_agentops.using-git-worktrees
    strength: 0.80
    reason: "plano deve incluir task de setup de worktree como primeira tarefa"
input_schema:
  - name: design_doc_path
    type: string
    description: "Path do spec/design aprovado (output do brainstorming)"
    required: true
  - name: worktree_path
    type: string
    description: "Path do worktree onde a implementação ocorrerá"
    required: false
  - name: task_duration_target
    type: string
    description: "Duração alvo por tarefa (default: 2-5 minutos)"
    required: false
    default: "2-5 minutos"
output_schema:
  - name: plan_file_path
    type: string
    description: "Path do plano salvo: docs/superpowers/plans/YYYY-MM-DD-<feature>.md"
  - name: task_count
    type: integer
    description: "Número total de tarefas no plano"
  - name: file_structure_map
    type: object
    description: "Mapa de arquivos a criar/modificar com responsabilidade de cada um"
what_if_fails: >
  Se spec cobre múltiplos subsistemas independentes: decompor em planos separados.
  Se tarefa > 5 minutos: decompor em sub-tarefas menores.
  Se qualquer tarefa tem dependência circular: reordenar ou separar em fases.
synergy_map:
  - type: skill
    ref: engineering_agentops.brainstorming
    benefit: "fornece o design aprovado que este skill transforma em plano"
  - type: skill
    ref: engineering_agentops.subagent-driven-development
    benefit: "executa o plano criado por este skill"
  - type: skill
    ref: engineering_agentops.test-driven-development
    benefit: "cada tarefa de implementação no plano inclui steps TDD"
security:
  - risk: "Plano com tasks que requerem acesso privilegiado não documentado"
    mitigation: "Documentar explicitamente qualquer requisito de permissão em cada task"
  - risk: "Plano assume dependências externas não verificadas"
    mitigation: "Incluir task de verificação de dependências como primeira tarefa do plano"
---

# Writing Plans

## Overview

Write comprehensive implementation plans assuming the engineer has zero context for our codebase and questionable taste. Document everything they need to know: which files to touch for each task, code, testing, docs they might need to check, how to test it. Give them the whole plan as bite-sized tasks. DRY. YAGNI. TDD. Frequent commits.

Assume they are a skilled developer, but know almost nothing about our toolset or problem domain. Assume they don't know good test design very well.

**Announce at start:** "I'm using the writing-plans skill to create the implementation plan."

**Context:** This should be run in a dedicated worktree (created by brainstorming skill).

**Save plans to:** `docs/superpowers/plans/YYYY-MM-DD-<feature-name>.md`
- (User preferences for plan location override this default)

## Scope Check

If the spec covers multiple independent subsystems, it should have been broken into sub-project specs during brainstorming. If it wasn't, suggest breaking this into separate plans — one per subsystem. Each plan should produce working, testable software on its own.

## File Structure

Before defining tasks, map out which files will be created or modified and what each one is responsible for. This is where decomposition decisions get locked in.

- Design units with clear boundaries and well-defined interfaces. Each file should have one clear responsibility.
- You reason best about code you can hold in context at once, and your edits are more reliable when files are focused. Prefer smaller, focused files over large ones that do too much.
- Files that change together should live together. Split by responsibility, not by technical layer.
- In existing codebases, follow established patterns. If the codebase uses large files, don't unilaterally restructure - but if a file you're modifying has grown unwieldy, including a split in the plan is reasonable.

This structure informs the task decomposition. Each task should produce self-contained changes that make sense independently.

## Bite-Sized Task Granularity

**Each step is one action (2-5 minutes):**
- "Write the failing test" - step
- "Run it to make sure it fails" - step
- "Implement the minimal code to make the test pass" - step
- "Run the tests and make sure they pass" - step
- "Commit" - step

## Plan Document Header

**Every plan MUST start with this header:**

```markdown
# [Feature Name] Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** [One sentence describing what this builds]

**Architecture:** [2-3 sentences about approach]

**Tech Stack:** [Key technologies/libraries]

---
```

## Task Structure

````markdown
### Task N: [Component Name]

**Files:**
- Create: `exact/path/to/file.py`
- Modify: `exact/path/to/existing.py:123-145`
- Test: `tests/exact/path/to/test.py`

- [ ] **Step 1: Write the failing test**

```python
def test_specific_behavior():
    result = function(input)
    assert result == expected
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/path/test.py::test_name -v`
Expected: FAIL with "function not defined"

- [ ] **Step 3: Write minimal implementation**

```python
def function(input):
    return expected
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/path/test.py::test_name -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/path/test.py src/path/file.py
git commit -m "feat: add specific feature"
```
````

## No Placeholders

Every step must contain the actual content an engineer needs. These are **plan failures** — never write them:
- "TBD", "TODO", "implement later", "fill in details"
- "Add appropriate error handling" / "add validation" / "handle edge cases"
- "Write tests for the above" (without actual test code)
- "Similar to Task N" (repeat the code — the engineer may be reading tasks out of order)
- Steps that describe what to do without showing how (code blocks required for code steps)
- References to types, functions, or methods not defined in any task

## Remember
- Exact file paths always
- Complete code in every step — if a step changes code, show the code
- Exact commands with expected output
- DRY, YAGNI, TDD, frequent commits

## Self-Review

After writing the complete plan, look at the spec with fresh eyes and check the plan against it. This is a checklist you run yourself — not a subagent dispatch.

**1. Spec coverage:** Skim each section/requirement in the spec. Can you point to a task that implements it? List any gaps.

**2. Placeholder scan:** Search your plan for red flags — any of the patterns from the "No Placeholders" section above. Fix them.

**3. Type consistency:** Do the types, method signatures, and property names you used in later tasks match what you defined in earlier tasks? A function called `clearLayers()` in Task 3 but `clearFullLayers()` in Task 7 is a bug.

If you find issues, fix them inline. No need to re-review — just fix and move on. If you find a spec requirement with no task, add the task.

## Execution Handoff

After saving the plan, offer execution choice:

**"Plan complete and saved to `docs/superpowers/plans/<filename>.md`. Two execution options:**

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?"**

**If Subagent-Driven chosen:**
- **REQUIRED SUB-SKILL:** Use superpowers:subagent-driven-development
- Fresh subagent per task + two-stage review

**If Inline Execution chosen:**
- **REQUIRED SUB-SKILL:** Use superpowers:executing-plans
- Batch execution with checkpoints for review
