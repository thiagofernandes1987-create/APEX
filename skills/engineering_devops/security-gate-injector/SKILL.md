---
skill_id: engineering_devops.security_gate_injector
name: security-gate-injector
description: >
  Injeta gates de segurança verificáveis em pipelines CI/CD existentes. Conecta
  security.codebase-audit-pre-push ao pipeline de CD de forma declarativa, garantindo
  que cada deploy passe por security scan antes de chegar ao ambiente alvo. Resolve
  o gap Gap-2: security skills existem isoladas, sem integração formal com DevOps.
version: v00.36.0
status: ADOPTED
tier: 2
executor: HYBRID
domain_path: engineering_devops/security_gate_injector
risk: medium
opp: OPP-Phase4-super-skills
anchors:
  - security
  - ci_cd
  - gate
  - devops
  - pipeline
  - devsecops
  - injection
  - pre_deploy
  - audit
input_schema:
  - name: pipeline_config_path
    type: string
    description: "Path do arquivo de configuração do pipeline (GitHub Actions, GitLab CI, Jenkinsfile, etc.)"
    required: true
  - name: pipeline_type
    type: string
    enum: [github_actions, gitlab_ci, jenkins, azure_devops, circleci]
    description: "Tipo de pipeline CI/CD"
    required: true
  - name: security_level
    type: string
    enum: [minimal, standard, strict]
    description: "minimal=só dependency scan; standard=+code review; strict=+pen testing"
    required: false
    default: "standard"
  - name: block_on_critical
    type: boolean
    description: "Se true, bloqueia deploy ao encontrar vulnerabilidade CRITICAL"
    required: false
    default: true
output_schema:
  - name: patched_pipeline_path
    type: string
    description: "Path do pipeline modificado com security gates injetados"
  - name: gates_added
    type: array
    description: "Lista de gates adicionados com posição no pipeline"
  - name: estimated_overhead_minutes
    type: number
    description: "Overhead estimado em minutos por execução do pipeline"
synergy_map:
  complements:
    - security.codebase-audit-pre-push
    - security.dependency-auditor
    - security_engineering.secure_delivery_pipeline
    - engineering_devops.ci-cd-pipeline-builder
    - engineering_devops.release-manager
  activates_with:
    - engineering_agentops.full_dev_cycle
  cross_domain_bridges:
    - domain: security
      strength: 0.95
      note: "Primary bridge — injects security skills into DevOps pipeline"
    - domain: engineering_agentops
      strength: 0.80
      note: "full_dev_cycle can invoke this as optional security phase"
security:
  level: standard
  pii: false
  approval_required: false
  note: "Modifies CI/CD config files — review patched_pipeline_path before merging"
what_if_fails: >
  Se pipeline_type não reconhecido: gerar template genérico com instruções de adaptação manual.
  Se block_on_critical == false e CRITICAL encontrado: log warning obrigatório no pipeline output.
  Se overhead > 15 min: sugerir caching de dependências e scans paralelos para otimização.
  Se pipeline quebra após injeção: rollback para original e reportar conflito.
---

# Security Gate Injector — Gap-Filling Skill

Pontes o gap Gap-2: `security` tem `codebase-audit-pre-push` mas `engineering_devops` não
tem gate de segurança no pipeline. Esta skill injeta a conexão declarativa.

## Why This Skill Exists

O domínio `security` tem `codebase-audit-pre-push` — uma skill excelente para auditoria
de código antes do push. O domínio `engineering_devops` tem `ci-cd-pipeline-builder` e
`release-manager`. **Porém, nenhuma skill conecta os dois**: security scans não são
invocados automaticamente no pipeline CI/CD, dependendo de disciplina manual do desenvolvedor.
Esta skill resolve o Gap-2 identificado na análise de sinergia do APEX: injeta security
gates verificáveis nos pipelines de forma declarativa e auditável.

## When to Use

Use esta skill quando:
- Configurando um novo pipeline CI/CD e quer security gates desde o início
- Um pipeline existente não tem security scan automatizado
- Quer elevar o `security_level` de um pipeline (minimal → standard → strict)
- Preparando compliance para ISO27001/SOC2 (security gates são evidência de controle)

## What If Fails

| Situação | Ação |
|----------|------|
| Pipeline type não reconhecido | Gerar template genérico + instruções de adaptação manual |
| Overhead > 15 min | Sugerir: cache de dependências, scans em paralelo, scan incremental |
| Pipeline quebra após injeção | Rollback automático para original; reportar conflito específico |
| `block_on_critical=false` + CRITICAL | Warning obrigatório no log; nunca silenciar |

## Security Level Matrix

| Level | Gates Injetados | Overhead Est. |
|-------|----------------|--------------|
| minimal | dependency scan (npm audit / pip-audit) | ~2 min |
| standard | dependency scan + LLM code review (OWASP Top 10) | ~5 min |
| strict | dependency + code review + secrets scan + SAST | ~10 min |

## Pipeline Injection Points

```yaml
# Ponto de injeção recomendado no pipeline:
# ANTES do job de deploy (não antes de build — evita falso positivo por código não compilado)

# GitHub Actions example (gerado automaticamente):
jobs:
  security-gate:
    runs-on: ubuntu-latest
    needs: [build]          # após build
    steps:
      - uses: actions/checkout@v4
      - name: Dependency Audit
        run: |
          # injetado por security-gate-injector
          npm audit --audit-level=critical  # ou pip-audit, gradle audit, etc.
      - name: APEX Security Review
        run: |
          # invoca security.codebase-audit-pre-push via APEX
          echo "::set-output name=gate::passed"
  deploy:
    needs: [security-gate]  # deploy bloqueado até gate passar
```

## Diff History
- **v00.36.0**: Criado via OPP-Phase4-super-skills — Gap-2 bridge: security ↔ engineering_devops
