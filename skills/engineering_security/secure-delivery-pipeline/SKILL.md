---
skill_id: security_engineering.secure_delivery_pipeline
name: secure-delivery-pipeline
description: >
  Injeta camadas de segurança em todo pipeline de entrega de software. Orquestra:
  audit de dependências → análise de código → pen testing → ISMS compliance →
  incident response plan. Garante que nenhum código chegue a produção sem passar
  por gates de segurança verificáveis. Resolve o gap entre engineering_devops e security.
version: v00.36.0
status: ADOPTED
tier: SUPER
executor: LLM_BEHAVIOR
domain_path: security_engineering/secure_delivery_pipeline
risk: medium
opp: OPP-Phase4-super-skills
anchors:
  - security
  - pipeline
  - audit
  - dependency
  - pen_testing
  - isms
  - compliance
  - incident_response
  - secure_delivery
  - devsecops
  - gate
  - verification
input_schema:
  - name: codebase_path
    type: string
    description: "Path do código a auditar"
    required: true
  - name: deployment_target
    type: string
    enum: [production, staging, development]
    description: "Ambiente de destino — define rigor dos gates"
    required: true
  - name: compliance_frameworks
    type: array
    description: "Frameworks de compliance aplicáveis: ISO27001, SOC2, GDPR, HIPAA"
    required: false
    default: []
output_schema:
  - name: security_report
    type: object
    description: "Relatório consolidado: vulnerabilidades, compliance gaps, risk score"
  - name: remediation_plan
    type: array
    description: "Lista priorizada de remediações com severity e prazo"
  - name: gate_passed
    type: boolean
    description: "Se o código passou em todos os gates de segurança para o target"
  - name: incident_response_plan
    type: string
    description: "Path do plano de resposta a incidentes gerado"
synergy_map:
  complements:
    - security.dependency-auditor
    - security.claude-code-security-review
    - security.security-pen-testing
    - engineering_security.isms-audit-expert
    - security.incident-commander
    - engineering_agentops.verification-before-completion
  activates_with:
    - engineering_devops.ci-cd-pipeline
    - engineering_agentops.full_dev_cycle
  cross_domain_bridges:
    - domain: engineering_devops
      strength: 0.92
      note: "Gate integration — security pipeline injected into CI/CD"
    - domain: engineering_agentops
      strength: 0.88
      note: "Composable with full_dev_cycle as security gate phase"
    - domain: legal
      strength: 0.80
      note: "Compliance frameworks (GDPR, HIPAA) bridge to legal domain"
orchestration:
  - phase: 1
    skill: security.dependency-auditor
    gate: "CVE report gerado — bloquear se CRITICAL CVE encontrado"
    strength: 0.92
    call_always: true
  - phase: 2
    skill: security.claude-code-security-review
    gate: "OWASP Top 10 assessment completo"
    strength: 0.90
    call_always: true
  - phase: 3
    skill: security.security-pen-testing
    gate: "Endpoints testados para injection, auth bypass, IDOR"
    condition: "deployment_target == production"
    strength: 0.85
  - phase: 4
    skill: engineering_security.isms-audit-expert
    gate: "Controls verified per framework"
    condition: "ISO27001 in compliance_frameworks"
    strength: 0.88
  - phase: 5
    skill: security.incident-commander
    gate: "Runbook de resposta + escalation matrix gerados"
    strength: 0.80
  - phase: 6
    skill: engineering_agentops.verification-before-completion
    gate: "Re-scan confirma remediations aplicados — emite gate_passed"
    strength: 0.95
security:
  level: high
  pii: false
  approval_required: true
  note: "Pen testing phase requires explicit approval before targeting production"
what_if_fails: >
  Se gate_passed == false: bloquear deploy e retornar remediation_plan.
  Se compliance gap crítico: escalate para CISO antes de prosseguir.
  Se pen testing encontrar vulnerabilidade crítica: immediate remediation obrigatória.
  Se CRITICAL CVE em dependência: bloquear pipeline independente do deployment_target.
---

# Secure Delivery Pipeline — Super-Skill

Pipeline DevSecOps que injeta 6 camadas de verificação de segurança em qualquer pipeline
de entrega, transformando um deploy arriscado em uma entrega auditável e compliance-ready.

## Why This Skill Exists

O domínio `security` tem skills excelentes e especializadas (`dependency-auditor`,
`claude-code-security-review`, `security-pen-testing`, `incident-commander`), mas nenhuma
skill as **orquestra em sequência com gates**. O resultado é que cada skill é invocada ad-hoc,
fora de ordem, ou simplesmente não é invocada — código chega à produção sem passar por todos
os gates. Esta super-skill resolve o gap crítico entre `security` e `engineering_devops`:
é o orquestrador declarativo do pipeline DevSecOps.

## When to Use

Use esta skill quando:
- Preparando um deploy para `production` (obrigatório) ou `staging` (recomendado)
- Iniciando um projeto que precisa de compliance (ISO27001, SOC2, GDPR, HIPAA)
- Respondendo a um incidente de segurança que exige auditoria completa
- Quer integrar security gates no pipeline CI/CD de forma declarativa

**Para `development`**: use `security.claude-code-security-review` diretamente — esta
super-skill tem overhead de pen-testing desnecessário em ambientes de desenvolvimento.

## What If Fails

| Gate | Falha | Ação |
|------|-------|------|
| Dependências | CRITICAL CVE | Bloquear imediatamente — não prosseguir |
| Code Review | OWASP Critical | Immediate remediation obrigatória antes de fase 3 |
| Pen Testing | Vulnerabilidade crítica | Bloquear deploy; escalar para security team |
| ISMS | Gap crítico | Escalar para CISO; não emitir gate_passed |
| Verificação | gate_passed == false | Retornar remediation_plan com prazo e owner |
| Qualquer fase | Timeout/erro | Tratar como gate_failed — nunca assumir segurança |

## Orchestration Protocol

```
PHASE 1: dependency-auditor [SEMPRE]
  → Analisa package.json/requirements.txt/go.mod
  → Lista CVEs por severity
  → GATE: se CRITICAL CVE → STOP (bloquear pipeline)

PHASE 2: claude-code-security-review [SEMPRE]
  → OWASP Top 10 assessment
  → SQL injection, XSS, auth bypass, secret leakage
  → GATE: findings consolidados em security_report parcial

PHASE 3: security-pen-testing [SE production]
  → Mapeia endpoints expostos
  → Testa: injection, broken auth, IDOR, SSRF
  → GATE: todos os endpoints testados

PHASE 4: isms-audit-expert [SE ISO27001/SOC2 em compliance_frameworks]
  → Verifica controles por framework
  → Identifica compliance gaps
  → GATE: audit report com gaps priorizados

PHASE 5: incident-commander [SEMPRE]
  → Recebe risk report das fases anteriores
  → Gera runbook de resposta a incidentes
  → Define escalation matrix

PHASE 6: verification-before-completion [SEMPRE]
  → Re-executa scans seletivos
  → Confirma remediations com evidência
  → Emite: gate_passed = true/false
```

## Compliance Framework Mapping

| Framework | Fases Obrigatórias | Gates Adicionais |
|-----------|-------------------|-----------------|
| ISO27001 | 1,2,3,4,5,6 | Annex A controls check |
| SOC2 | 1,2,4,6 | Trust Service Criteria |
| GDPR | 1,2,6 | PII data flow mapping |
| HIPAA | 1,2,4,6 | PHI access audit |

## Diff History
- **v00.36.0**: Criado via OPP-Phase4-super-skills — DevSecOps pipeline super-skill
