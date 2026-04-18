---
skill_id: engineering_mlops.model_deployment_pipeline
name: mlops-deployment-pipeline
description: >
  Bridge MLOps entre ai_ml_ml (treinamento de modelos) e engineering_devops (CI/CD).
  Orquestra: validação de modelo → containerização → deployment → drift monitoring →
  A/B testing de modelos em produção. Resolve o Gap-1: modelos treinados não têm
  pipeline de produção declarado no APEX.
version: v00.36.0
status: ADOPTED
tier: 2
executor: HYBRID
domain_path: engineering_mlops/model_deployment_pipeline
risk: medium
opp: OPP-Phase4-super-skills
anchors:
  - mlops
  - model_deployment
  - drift_monitoring
  - ab_testing
  - ml_pipeline
  - containerization
  - production_ml
  - monitoring
  - ci_cd
  - model_validation
input_schema:
  - name: model_artifact_path
    type: string
    description: "Path do modelo treinado (pickle, ONNX, SavedModel, etc.)"
    required: true
  - name: model_framework
    type: string
    enum: [sklearn, pytorch, tensorflow, huggingface, onnx, custom]
    description: "Framework do modelo"
    required: true
  - name: serving_target
    type: string
    enum: [rest_api, batch, streaming, edge]
    description: "Modalidade de serving do modelo"
    required: false
    default: "rest_api"
  - name: performance_baseline
    type: object
    description: "Métricas de performance mínimas: accuracy, latency_p99, throughput"
    required: false
  - name: drift_threshold
    type: number
    description: "Threshold de PSI/KL-divergence para alertar drift de dados"
    required: false
    default: 0.2
output_schema:
  - name: deployment_manifest
    type: string
    description: "Path do manifest de deployment (Dockerfile, helm chart, etc.)"
  - name: serving_endpoint
    type: string
    description: "URL ou configuração do endpoint de serving"
  - name: monitoring_config
    type: object
    description: "Configuração de drift monitoring + alertas + dashboards"
  - name: ab_test_config
    type: object
    description: "Configuração de A/B testing entre versões de modelo"
synergy_map:
  complements:
    - engineering_devops.ci-cd-pipeline-builder
    - engineering_devops.docker-best-practices
    - engineering_devops.kubernetes-operations
    - engineering_devops.senior-ml-engineer
    - engineering_devops.senior-data-scientist
  cross_domain_bridges:
    - domain: ai_ml_ml
      strength: 0.95
      note: "Consumes trained model artifacts from ml training skills"
    - domain: engineering_devops
      strength: 0.92
      note: "Uses CI/CD infrastructure for model deployment automation"
    - domain: data
      strength: 0.85
      note: "Drift monitoring requires data pipeline integration"
    - domain: engineering_testing
      strength: 0.80
      note: "A/B testing integrates with testing infrastructure"
security:
  level: standard
  pii: false
  approval_required: false
  note: "Models trained on PII data require security.level = high"
what_if_fails: >
  Se model validation falha (performance abaixo do baseline): bloquear deployment e reportar delta.
  Se drift detectado (PSI > drift_threshold): trigger retrain pipeline automaticamente.
  Se serving endpoint unhealthy: rollback para versão anterior imediatamente.
  Se A/B test sem significância estatística: manter modelo atual; não promover challenger.
---

# MLOps Deployment Pipeline — Gap-Filling Skill

Bridge declarativo entre `ai_ml_ml` (onde modelos são treinados) e `engineering_devops`
(onde infraestrutura de deployment existe). Fecha o Gap-1 do APEX: modelos treinados
ficavam sem pipeline de produção.

## Why This Skill Exists

O APEX tem skills ricas em `ai_ml_ml` para treinamento de modelos e skills em
`engineering_devops` para CI/CD e Kubernetes. **O gap**: nenhuma skill faz a ponte
entre `model artifact` e `production serving endpoint`. Modelos treinados ficam como
artefatos locais, sem pipeline de containerização, validação, deployment, drift monitoring
ou A/B testing declarativo. Esta skill fecha o Gap-1 identificado na análise de sinergia:
é o pipeline MLOps completo do modelo ao endpoint monitorado.

## When to Use

Use esta skill quando:
- Um modelo foi treinado (via `ai_ml_ml`) e precisa ser servido em produção
- Quiser adicionar drift monitoring a um modelo já em produção
- Precisar de A/B testing entre duas versões de modelo
- Construindo pipeline CI/CD para re-treinamento automático

## What If Fails

| Fase | Falha | Ação |
|------|-------|------|
| Validação | Performance abaixo do baseline | Bloquear deployment; reportar delta das métricas |
| Containerização | Build falha | Verificar dependências e versões de framework |
| Deployment | Endpoint unhealthy | Rollback automático para versão anterior |
| Drift Monitor | PSI > threshold | Trigger retrain pipeline; alertar equipe |
| A/B Test | Sem significância | Manter modelo atual; aumentar período de teste |

## MLOps Pipeline Stages

```
STAGE 1: Model Validation
  → Carrega model_artifact_path
  → Avalia em hold-out set
  → Compara com performance_baseline
  → GATE: métricas >= baseline (bloqueia se não)

STAGE 2: Containerization
  → Gera Dockerfile otimizado por model_framework
  → Build e push da imagem para registry
  → Escaneia imagem por CVEs (via security-gate-injector)
  → Output: container_image_tag

STAGE 3: Deployment
  → Gera manifest (Kubernetes Deployment + Service, ou serverless config)
  → Deploy com health check e readiness probe
  → Output: serving_endpoint
  → GATE: endpoint healthy após deploy

STAGE 4: Drift Monitoring Setup
  → Configura coleta de distribuição de features em produção
  → Define alertas para PSI/KL-divergence > drift_threshold
  → Output: monitoring_config com dashboards

STAGE 5: A/B Test Configuration [se há versão anterior]
  → Configura traffic split entre champion e challenger
  → Define métricas de comparação e sample size
  → Output: ab_test_config
  → GATE: resultado estatisticamente significativo antes de promover
```

## Framework → Serving Stack Map

| model_framework | Serving Stack | Container Base |
|----------------|--------------|----------------|
| sklearn | FastAPI + joblib | python:3.11-slim |
| pytorch | TorchServe / FastAPI | pytorch/torchserve |
| tensorflow | TF Serving | tensorflow/serving |
| huggingface | HuggingFace Inference | huggingface/transformers-pytorch-gpu |
| onnx | ONNX Runtime Server | mcr.microsoft.com/onnxruntime |

## Diff History
- **v00.36.0**: Criado via OPP-Phase4-super-skills — Gap-1 bridge: ai_ml_ml ↔ engineering_devops (MLOps)
