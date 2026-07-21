# APEX — Autonomous Polymorphic Engineering eXpert

**Skill canônica**: [`apex-method/`](apex-method/) v1.63.0 | **Skills nativas**: 3.784 (52 domínios) | **Agentes**: 219 | **Licença**: MIT (skill) / CC BY-NC 4.0 (biblioteca)

> Workflow de raciocínio token-aware com ferramentas reais: escolhe um modo de operação para
> controlar custo, roda um pipeline estruturado (decompose → validate → verify → snapshot) e dá
> ao LLM Program-of-Thought, RK4/Euler, code gate, roteador de skills seguro, memória persistente
> e um ciclo de aprendizado com governança (ledger SHA-256).

---

## Comece aqui

**A fonte canônica do APEX é a skill [`apex-method/`](apex-method/)** — 55 scripts Python
(stdlib-only, aceleradores opcionais), catálogos, testes e referências. Tudo o mais no
repositório é biblioteca (skills/agentes minerados), material de referência ou histórico.

### Para humanos

```bash
git clone https://github.com/thiagofernandes1987-create/APEX.git
cd APEX/apex-method
python3 tests/benchmark.py        # valida a instalação (72 testes por módulo)
python3 scripts/menu.py --help    # menu: update, modos preferidos, deep research
```

Instalação como skill do Claude Code: copie `apex-method/` para `~/.claude/skills/apex-method/`
(ou `npx skills add` quando publicado no marketplace).

### Para LLMs (ordem de leitura)

1. `apex-method/SKILL.md` — o método + as ferramentas (entry point: `scripts/orchestrator.py` → `run(task)`).
2. `apex-method/references/` — detalhe por subsistema (pipeline, validação, agentes, Bayes…).
3. `INDEX.md` — índice **gerado** dos 3.784 skills da biblioteca (`python3 tools/generate_index.py`).
4. `apex-method/catalog/` — catálogos JSON (roster de agentes, attraction graph, RAG index, registro de módulos).

### Fluxo mínimo (o contrato do kernel)

```python
# de dentro de apex-method/scripts/
import orchestrator
r = orchestrator.run("sua tarefa")           # triage → dissect → specialists → modo → checklist
# r["kernel_checklist"]: passos DONE (código) + llm_actions (o que VOCÊ executa)
# execute os passos, marque com complete_step(...), e feche com orchestrator.gate(checklist)
# a run só está completa quando o gate diz COMPLETE.
```

---

## Estrutura do repositório

| Caminho | O que é | Status |
|---|---|---|
| `apex-method/` | **A skill canônica** — scripts, catálogos, testes, referências | ativo |
| `skills/` | Biblioteca com 3.784 skills em 52 domínios (ver `INDEX.md`) | biblioteca |
| `agents/` | 219 agentes/personas especializados | biblioteca |
| `integrations/` | Integrações (MCP servers, pontes) — inclui `apex-mcp-server/` | ativo |
| `tools/` | Utilitários do repo (`generate_index.py`, validadores, standardizer) | ativo |
| `algorithms/` | Repositórios de terceiros vendorizados — ver [`algorithms/THIRD_PARTY.md`](algorithms/THIRD_PARTY.md) | referência |
| `apex_boot/` | Sistema legado de boot por prompt (111 páginas, pré-skill) | legado |
| `diffs/`, `meta/`, `references/`, `reference-docs/` | Histórico de evolução + material de referência | histórico |
| `docs/reports/` | Relatórios de auditoria/avaliação por versão | histórico |
| `Full Bundle/` | Bundle binário fatiado (legado; candidato a remoção) | legado |

## Documentos-chave

- [`apex-method/SKILL.md`](apex-method/SKILL.md) — o método completo.
- [`spec_atualizacoes.md`](spec_atualizacoes.md) — **estado atual: o que foi implementado, o que falta, decisões pendentes.**
- [`APEX_CREATION_GUIDE.md`](APEX_CREATION_GUIDE.md) — schemas e templates para criar artefatos APEX.
- [`INTAKE_WORKFLOW.md`](INTAKE_WORKFLOW.md) — pipeline de ingestão de repositórios externos.
- [`docs/reports/`](docs/reports/) — auditorias e avaliações históricas.
- [`docs/README_legacy_v00.39.md`](docs/README_legacy_v00.39.md) — README anterior (sistema de boot por prompt).

## Qualidade

- `apex-method/tests/benchmark.py` — 1 teste real por módulo + regressões de auditoria.
- `apex-method/tests/test_regressions_v162.py` — regressões empíricas v1.62 (cache híbrido, triage, taxonomy).
- `tools/validate_skills.py` / `tools/skill_standardizer.py` — conformidade da biblioteca de skills.
- Ledger de governança SHA-256 (`memory.record_event` / `verify_ledger`) — trilha auditável de
  toda promoção/rebaixamento.

## Princípios (invariantes)

1. **Nada roda sem gate** — código passa por `uco_gate`; instalação de skill externa exige aprovação humana (H5).
2. **Verificar, não afirmar** — matemática via `verify.py` (sympy) ou marcada `CONJECTURE`; execução simulada é sempre rotulada.
3. **Aprender só com validação** — promoção/rebaixamento (beta-binomial) apenas após resultado validado; tudo espelhado no ledger.
4. **Token economy primeiro** — triage decide o modo mais leve que serve; cache de resolução pula o pipeline quando um problema já foi resolvido e validado.
