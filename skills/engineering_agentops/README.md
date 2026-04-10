# Engineering AgentOps — Domínio APEX

**Origem**: [obra/superpowers](https://github.com/obra/superpowers) — adaptado para APEX v00.36.0
**Skills**: 14 | **Tier**: ADAPTED

> Metodologia completa de engenharia com agentes: brainstorming socrático, planos de implementação,
> subagent-driven development com revisão em duas etapas, TDD, debugging sistemático e code review.

## Workflow Principal

```
brainstorming → using-git-worktrees → writing-plans → subagent-driven-development
      ↓                                                         ↓
 [design doc]                                    [per task: TDD + 2-stage review]
                                                              ↓
                                              finishing-a-development-branch
```

## Skills Disponíveis

| Skill | Propósito | Quando Usar |
|-------|-----------|-------------|
| [brainstorming](brainstorming/SKILL.md) | Design antes de código | Antes de qualquer implementação |
| [writing-plans](writing-plans/SKILL.md) | Planos de implementação detalhados | Após design aprovado |
| [subagent-driven-development](subagent-driven-development/SKILL.md) | Execução com subagentes + 2-stage review | Com plano + subagente disponível |
| [executing-plans](executing-plans/SKILL.md) | Execução sequencial com checkpoints | Sem suporte a subagentes |
| [test-driven-development](test-driven-development/SKILL.md) | RED-GREEN-REFACTOR | Em toda implementação |
| [systematic-debugging](systematic-debugging/SKILL.md) | Root cause analysis 4 fases | Ao encontrar qualquer bug |
| [verification-before-completion](verification-before-completion/SKILL.md) | Gate de evidência antes de claims | Antes de declarar qualquer sucesso |
| [requesting-code-review](requesting-code-review/SKILL.md) | Despachar subagente reviewer | Entre tarefas e antes de merge |
| [receiving-code-review](receiving-code-review/SKILL.md) | Processar feedback com rigor técnico | Ao receber qualquer review |
| [dispatching-parallel-agents](dispatching-parallel-agents/SKILL.md) | Agentes paralelos por domínio | 3+ problemas independentes |
| [using-git-worktrees](using-git-worktrees/SKILL.md) | Workspace isolado por feature | Antes de SDD ou executing-plans |
| [finishing-a-development-branch](finishing-a-development-branch/SKILL.md) | Merge/PR/Discard estruturado | Ao completar implementação |
| [using-superpowers](using-superpowers/SKILL.md) | Introdução ao sistema | Onboarding ou dúvida sobre qual skill |
| [writing-skills](writing-skills/SKILL.md) | Criar novas skills | Ao precisar de nova skill |

## Integração com APEX

- **Tier**: ADAPTED — skills importadas e normalizadas com schema APEX completo
- **Source**: `obra/superpowers` (MIT License)
- **OPP**: OPP-136
- **Normalizado por**: `import_superpowers.py` — frontmatter gerado cirurgicamente
- **Cross-bridges**: Todas as skills têm bridges para `engineering_testing`, `engineering_git`, `apex_internals`
