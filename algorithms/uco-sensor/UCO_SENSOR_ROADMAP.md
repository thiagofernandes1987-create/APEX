# UCO-Sensor — Inventário Técnico Completo & WBS v3.x
> **APEX SCIENTIFIC MODE** · Gerado em 2026-04-26 · Baseline: v2.2.0 (M6.4)  
> Documento vivo — atualizar após cada marco concluído

---

## ÍNDICE

1. [Estado Atual — Radiografia Completa](#1-estado-atual)
2. [O Que Falta — Gaps Críticos](#2-gaps-críticos)
3. [O Que Melhorar — Melhorias em Módulos Existentes](#3-melhorias)
4. [O Que Criar — Novos Módulos e Vetores](#4-criar)
5. [Grafo de Dependências — Predecessores e Sucessores](#5-dependências)
6. [WBS — Work Breakdown Structure com Datas](#6-wbs)
7. [Especificação Técnica por Entregável](#7-especificação-técnica)
8. [Métricas de Sucesso por Marco](#8-métricas-de-sucesso)
9. [Comparativo Competitivo vs SonarQube](#9-competitivo)
10. [Sumário Executivo](#10-sumário)

---

## 1. ESTADO ATUAL

### 1.1 Mapa de Módulos — Versão Baseline v2.2.0

| Módulo | Arquivo(s) | Status | Canais/Regras | Lacunas Identificadas |
|--------|-----------|--------|--------------|----------------------|
| **AST Core** | `sensor_core/uco_bridge.py` | ✅ Maduro | 9 canais MetricVector | 10 padrões não detectados no `_UCOVisitor` |
| **Advanced Metrics M1** | `sensor_core/advanced_metrics.py` | ✅ Funcional | Cognitive CC, SQALE, clones, fn_profiles | 14 sinais computados mas não persistidos |
| **Predictor M5** | `sensor_core/predictor.py` | ✅ Funcional | Hurst R/S, OLS slope, 5 risk levels | `confidence`, `hurst_exponent`, `velocity` não persistem |
| **AutoFix** | `sensor_core/autofix/` | ⚠️ Raso | 4 transforms | Faltam 12+ transforms; sem suggested_fix no SAST |
| **Lang Adapters** | `lang_adapters/` (40 lang) | ✅ Funcional | CC, ILR, H, DI, DSM | Precisão ±15%; sem AST real para JS/Java/Go |
| **SAST** | `sast/scanner.py` | ⚠️ Raso | 13 regras (Python only) | Faltam 37 regras; sem taint analysis; sem FlowVector |
| **SCA** | `sca/` | ✅ Funcional | 65+ CVEs, 9 ecossistemas | Faltam 135+ CVEs; ecossistemas pip-audit, Gradle nativo |
| **IaC** | `iac/iac_scanner.py` | ✅ Novo | 44 regras, 5 formatos | Faltam 56+ regras; sem Ansible/Pulumi/CDK |
| **FrequencyEngine** | `frequency-engine/` | ✅ Único | Espectral, Hurst, DBSCAN, change-point | `ClassificationResult` descartado após análise; não persiste |
| **Governance** | `governance/` | ✅ Funcional | Policy engine, trend, debt budget | `forecast_next`, `slope_pct` não persistem |
| **SARIF** | `report/sarif.py` | ✅ Presente | SARIF 2.1 export | Sem LSP diagnostics; sem `suggested_fix` integrado |
| **Scan** | `scan/` | ✅ Funcional | Incremental, repo, git history | `uco_score`, `critical_ratio`, `by_language` não persistem |
| **Extended Vectors M6.4** | `metrics/extended_vectors.py` | ✅ Novo | 27 canais (4 vetores) | VelocityVector não persiste no SnapshotStore |
| **SnapshotStore** | `sensor_storage/snapshot_store.py` | ✅ Funcional | SQLite, histórico de MVs | Não armazena vetores estendidos nem ClassificationResult |
| **API Server** | `api/server.py` | ✅ Funcional | 20+ endpoints REST | Sem SSE/streaming; sem `/lsp/diagnostics`; sem `/monitor/*` |

### 1.2 Inventário de Sinais — Estado de Persistência

| Sinal | Computado em | Persistido? | Alimenta FreqEngine? | Prioridade de Correção |
|-------|-------------|------------|---------------------|----------------------|
| `H, CC, ILR, DSM_d, DSM_c, DI, dead, dups, bugs` | `uco_bridge.py` | ✅ Sim | ✅ Sim | — |
| `HalsteadVector (6)` | `uco_bridge.py` + `generic.py` | ✅ Sim (attr) | ❌ Não | ALTA |
| `StructuralVector (7)` | `uco_bridge.py` + `generic.py` | ✅ Sim (attr) | ❌ Não | ALTA |
| `SecurityVector (11)` | `metrics/extended_vectors.py` | ✅ Sim (attr) | ❌ Não | ALTA |
| `VelocityVector (4)` | `metrics/extended_vectors.py` | ❌ Calculado on-the-fly | ❌ Não | **CRÍTICA** |
| `cognitive_cc_total/max` | `advanced_metrics.py` | ❌ Attr informal | ❌ Não | **CRÍTICA** |
| `sqale_debt_minutes` | `advanced_metrics.py` | ❌ Attr informal | ❌ Não | **CRÍTICA** |
| `sqale_rating` | `advanced_metrics.py` | ❌ Attr informal | ❌ Não | ALTA |
| `clone_count` | `advanced_metrics.py` | ❌ Attr informal | ❌ Não | ALTA |
| `fn_profiles[]` | `advanced_metrics.py` | ❌ Attr informal | ❌ Não | MÉDIA |
| `uco_rating, reliability_rating` | `advanced_metrics.py` | ❌ Attr informal | ❌ Não | MÉDIA |
| `change_point` | `frequency_engine.py` | ❌ Em ClassificationResult | ❌ — | ALTA |
| `hflf_ratio_H` | `ClassificationResult` | ❌ Descartado | ❌ — | ALTA |
| `self_cure_probability` | `ClassificationResult` | ❌ Descartado | ❌ — | ALTA |
| `onset_reversibility` | `ClassificationResult` | ❌ Descartado | ❌ — | ALTA |
| `burst_index_H` | `ClassificationResult` | ❌ Descartado | ❌ — | ALTA |
| `phase_coupling_CC_H` | `ClassificationResult` | ❌ Descartado | ❌ — | MÉDIA |
| `slope_pct, forecast_next` | `trend_engine.py` | ❌ Apenas REST response | ❌ — | MÉDIA |
| `hurst_exponent, confidence` | `predictor.py` | ❌ Apenas REST response | ❌ — | MÉDIA |
| `uco_score [0-100]` | `repo_scanner.py` | ❌ Apenas REST response | ❌ — | MÉDIA |
| `critical_ratio` | `repo_scanner.py` | ❌ Apenas REST response | ❌ — | BAIXA |
| `by_language{}` | `repo_scanner.py` | ❌ Apenas REST response | ❌ — | BAIXA |

**Total de sinais computados:** ~54  
**Total persistidos corretamente:** 9 (MetricVector core)  
**Perda de informação:** ~83%

---

## 2. GAPS CRÍTICOS

### 2.1 Gaps de Detecção SAST

| Gap | SonarQube Community | Impacto | Complexidade de Implementação |
|-----|--------------------|---------|-----------------------------|
| Taint analysis cross-function | ❌ (pago) | 🔴 CRÍTICO | Alta — 7 dias |
| Data Flow Analysis (DFA) intra-função | ❌ (pago) | 🔴 CRÍTICO | Alta — parte do M7.2 |
| ReDoS — Regex Denial of Service | ✅ Sim | 🟠 ALTO | Média — 1 dia |
| SSRF — Server-Side Request Forgery | ✅ Sim | 🔴 CRÍTICO | Média — 1 dia |
| XXE — XML External Entity | ✅ Sim | 🔴 CRÍTICO | Baixa — 0.5 dia |
| CSRF detection | ✅ Sim | 🟠 ALTO | Baixa — 0.5 dia |
| JWT misconfiguration | ✅ Sim | 🟠 ALTO | Baixa — 0.5 dia |
| SSL/TLS verify=False | ✅ Sim | 🟠 ALTO | Baixa — 0.5 dia |
| Weak key length (RSA<2048) | ✅ Sim | 🟠 ALTO | Baixa — 0.5 dia |
| ECB mode usage | ✅ Sim | 🟠 ALTO | Baixa — 0.5 dia |
| Hardcoded IV/Nonce | ✅ Sim | 🟠 ALTO | Baixa — 0.5 dia |
| Timing attack (non-constant compare) | ✅ Parcial | 🟠 ALTO | Baixa — 0.5 dia |
| Template injection (Jinja2/Mako) | ✅ Sim | 🔴 CRÍTICO | Baixa — 1 dia |
| LDAP injection | ✅ Sim | 🟠 ALTO | Baixa — 0.5 dia |
| XPath injection | ✅ Sim | 🟡 MÉDIO | Baixa — 0.5 dia |
| NoSQL injection (MongoDB) | ✅ Parcial | 🟠 ALTO | Baixa — 1 dia |
| PII em logs | ✅ Sim | 🟡 MÉDIO | Baixa — 0.5 dia |
| Stack trace exposto | ✅ Sim | 🟡 MÉDIO | Baixa — 0.5 dia |
| CORS wildcard | ✅ Sim | 🟡 MÉDIO | Baixa — 0.5 dia |
| Weak password hashing | ✅ Sim | 🟠 ALTO | Baixa — 0.5 dia |
| Thread safety / race conditions | ✅ (pago) | 🔴 CRÍTICO | Alta — M7.7 (5 dias) |
| Null dereference tracking | ✅ Sim | 🟠 ALTO | Média — M9.0 |
| Memory leak patterns | ✅ Sim | 🟠 ALTO | Média — M9.0 |

### 2.2 Gaps de Qualidade no `_UCOVisitor` (AST Python)

Padrões **não detectados** atualmente em `sensor_core/uco_bridge.py`:

| Padrão | CWE | AST Node | Destino |
|--------|-----|----------|---------|
| `raise` sem argumento fora de `except` | CWE-390 | `ast.Raise(exc=None)` fora de ExceptHandler | SAST038 / ReliabilityVector |
| Bare `except:` sem tipo | CWE-390 | `ExceptHandler(type=None)` | SAST038 / `bare_except_count` |
| Shadow de builtin | — | `Name.id ∈ builtins.__dict__` em ctx Store | `shadow_builtin_count` |
| Retorno inconsistente | CWE-394 | FunctionDef com `Return(value)` em alguns branches e `Return(None)`/ausente em outros | `inconsistent_return_count` |
| Parâmetro mutável default | CWE-1220 | `FunctionDef.defaults` contém `List/Dict/Set` node | SAST039 / `mutable_default_arg_count` |
| Docstring ausente em função pública | — | FunctionDef sem `body[0] = Expr(Constant)`, nome não inicia com `_` | `missing_docstring_ratio` |
| Função com >5 parâmetros | — | `len(args.args) + len(args.posonlyargs) > 5` | `long_parameter_list` |
| `global x` modificado em função | — | `ast.Global` dentro de FunctionDef + assignment posterior | `global_mutation_count` |
| Comprehension aninhada >2 níveis | — | `ListComp/SetComp` dentro de `ListComp/SetComp` | `deeply_nested_ratio` |
| `__all__` ausente em módulo com exports | — | Módulo sem `ast.Assign` com target `__all__` mas com funções públicas | `missing_all_flag` |

### 2.3 Gaps de Persistência no `SnapshotStore`

O `sensor_storage/snapshot_store.py` **não armazena**:
- `HalsteadVector`, `StructuralVector`, `SecurityVector`, `VelocityVector`
- `AdvancedVector` (cognitive_cc, sqale_debt)
- `DiagnosticVector` (hflf_ratio_H, self_cure_probability, onset_reversibility)
- `ClassificationResult` completo (error_type, confidence, change_point)
- `DegradationForecast` (hurst_exponent, r_squared, confidence)

**Impacto direto:** FrequencyEngine não consegue analisar tendências espectral de segurança, performance ou confiabilidade — apenas os 9 canais originais.

### 2.4 Gaps de AutoFix

Transforms implementados (4/16+):
- `boolean_simplify.py` ✅
- `dead_code.py` ✅  
- `redundant_else.py` ✅
- `unused_imports.py` ✅

Transforms **faltando** (prioridade por frequência de ocorrência):
1. `extract_method.py` — função com CC>10 → sugere extração
2. `remove_mutable_default.py` — `def f(x=[])` → `def f(x=None)`
3. `add_docstring.py` — inserção de docstring template
4. `replace_bare_except.py` — `except:` → `except Exception as e:`
5. `add_context_manager.py` — `open()` → `with open()`
6. `replace_weak_hash.py` — `md5()` → `sha256()`
7. `replace_insecure_random.py` — `random.choice()` → `secrets.choice()`
8. `add_type_hints.py` — inferência e inserção de type hints básicos
9. `simplify_comparison.py` — `x == None` → `x is None`; `len(x) == 0` → `not x`
10. `replace_string_concat_loop.py` — `s += x` em loop → `"".join([...])`
11. `add_loop_guard.py` — `while True:` sem break → adiciona guard
12. `replace_format_string.py` — `"..." % var` → `f"..."` ou `.format()`

---

## 3. MELHORIAS

### 3.1 `sast/scanner.py` — Melhorias nas 13 Regras Existentes

| Regra | Problema Atual | Melhoria Necessária |
|-------|---------------|---------------------|
| SAST001 SQL Injection | Detecta apenas `execute()` direto | Adicionar `executemany`, `raw()` Django, `text()` SQLAlchemy |
| SAST002 OS Command | Detecta `os.system/popen` apenas | Adicionar `os.execv`, `os.execl`, `os.spawnl` |
| SAST003 eval/exec | Sem rastreio de variável contaminada | FlowVector M7.2 deve alimentar este |
| SAST007 Insecure Random | Muitos falsos positivos (simulations, games) | Restringir ao contexto: token/password/session em vizinhança |
| SAST008 Hardcoded Secret | Regex muito amplo | Adicionar entropy check: len>16 AND Shannon entropy>3.5 |
| SAST011 Path Traversal | Detecta todo `open(var)` — muitos FP | Rastrear se var vem de input/request via FlowVector |
| TODOS | Sem `suggested_fix` no finding | Adicionar campo `suggested_fix: str` (M8.1) |
| TODOS | Sem `confidence: float` | Adicionar score de confiança 0.0–1.0 |
| TODOS | Sem `false_positive_risk: str` | Adicionar LOW/MEDIUM/HIGH |
| TODOS | Sem `explanation: str` em linguagem natural | Adicionar explicação contextual |

### 3.2 `sca/cve_database.py` — Expansão de CVEs

**Estado atual:** 65+ CVEs, 9 ecossistemas  
**Target:** 200+ CVEs, 12 ecossistemas

| Ecossistema | CVEs Atuais | CVEs Target | Adições Prioritárias |
|------------|------------|------------|---------------------|
| pip | ~18 | 40 | Werkzeug, Celery, Ansible, Fabric, SQLAlchemy, FastAPI, Pydantic |
| npm | ~20 | 50 | express, jsonwebtoken, validator, multer, passport, socket.io, marked |
| maven | ~15 | 40 | Apache Tomcat, Spring Boot, Hibernate, Bouncy Castle, Apache Commons IO |
| cargo | 4 | 15 | tokio, hyper, actix-web, serde, nom, ring |
| go | 4 | 20 | gorilla/mux, gin, echo, gorm, jwt-go, crypto/tls |
| composer | 5 | 20 | Doctrine, Twig, Slim, Yii, Magento |
| gem | 6 | 20 | Devise, Carrierwave, Puma, Rack, ActiveRecord |
| nuget | 6 | 20 | Newtonsoft.Json, log4net, NHibernate, RestSharp |
| gradle | aliases | aliases | manter sincronizado com maven |
| **swift (NEW)** | 0 | 10 | Alamofire, Vapor, Perfect, Kitura |
| **pub/dart (NEW)** | 0 | 8 | http, dio, crypto, shelf |
| **hex/elixir (NEW)** | 0 | 7 | Phoenix, Ecto, Plug, Poison |

### 3.3 `iac/iac_scanner.py` — Expansão de Regras

**Estado atual:** 44 regras, 5 formatos  
**Target:** 100+ regras, 8 formatos

**Novas regras por scanner existente:**

*Dockerfile (10→20):*
- IAC-D011: `RUN apt-get install -y` sem `--no-install-recommends` (imagem inchada)
- IAC-D012: Múltiplos `RUN` consecutivos (deveria ser chain com `&&`)
- IAC-D013: `curl | bash` pipeline (supply chain attack)
- IAC-D014: `wget` sem verificação de checksum
- IAC-D015: WORKDIR com caminho relativo
- IAC-D016: `COPY . .` copiando tudo sem `.dockerignore`
- IAC-D017: Versão base usando digest em vez de tag (recomendação)
- IAC-D018: `sudo` usado dentro de Dockerfile
- IAC-D019: `chmod 777` dentro do Dockerfile
- IAC-D020: Imagem base não oficial (não usa registry oficial)

*Kubernetes (12→25):*
- IAC-K013: Sem `livenessProbe` configurado
- IAC-K014: Sem `readinessProbe` configurado
- IAC-K015: `automountServiceAccountToken: true` (default perigoso)
- IAC-K016: ServiceAccount com bindings admin/cluster-admin
- IAC-K017: Sem PodDisruptionBudget (HA risk)
- IAC-K018: `imagePullPolicy: Never` em produção
- IAC-K019: NetworkPolicy ausente para o namespace
- IAC-K020: Sem Ingress TLS configurado
- IAC-K021: Resource `requests` ausentes (scheduler sem hint)
- IAC-K022: `seccompProfile` ausente
- IAC-K023: `appArmorProfile` ausente
- IAC-K024: Uso de `emptyDir` para dados persistentes
- IAC-K025: Replica count ímpar (split-brain risk para stateful apps)

*Terraform (12→25):*
- IAC-T013: CloudFront sem HTTPS enforcing
- IAC-T014: Lambda sem VPC configurado
- IAC-T015: RDS sem backup retention configurado
- IAC-T016: S3 bucket sem server-side encryption
- IAC-T017: EC2 sem IMDSv2 (metadata service v1 vulnerável)
- IAC-T018: KMS key rotation desabilitada
- IAC-T019: CloudTrail não habilitado
- IAC-T020: GuardDuty não habilitado
- IAC-T021: Security Group egress aberto para 0.0.0.0/0
- IAC-T022: Load Balancer sem access logs
- IAC-T023: SNS topic sem encryption
- IAC-T024: DynamoDB sem encryption at rest
- IAC-T025: WAF ausente em ALB/CloudFront público

**Novos formatos:**
- **Ansible playbooks** (`.yml` com `hosts:` + `tasks:`) — 8 regras
- **Pulumi** (`Pulumi.yaml` + `index.ts`) — 5 regras  
- **AWS CDK** (`cdk.json` + `*.ts`/`*.py` com `aws_cdk` imports) — 5 regras

### 3.4 `sensor_core/advanced_metrics.py` — Cognitive CC Multi-Language

**Problema atual:** `cognitive_complexity()` funciona apenas para Python (AST).  
**Melhoria:** Adaptar para receber resultado do GenericRegexAdapter e calcular Cognitive CC aproximado para as 40 linguagens via profundidade de aninhamento regex.

### 3.5 `governance/policy_engine.py` — Novos Campos de Política

Adicionar campos dos novos vetores ao `mv_to_metrics_dict()`:
- `taint_path_count`, `injection_surface` (FlowVector)
- `bare_except_count`, `resource_leak_risk` (ReliabilityVector)
- `n_plus_one_risk`, `string_concat_in_loop` (PerformanceVector)
- `anti_pattern_score` (APS global)

### 3.6 `sensor_storage/snapshot_store.py` — Persistência de Vetores Estendidos

Adicionar coluna `extended_vectors_json TEXT` na tabela `snapshots`.  
Serializar/deserializar: `HalsteadVector`, `StructuralVector`, `SecurityVector`, `VelocityVector`, `AdvancedVector`, `DiagnosticVector`.

### 3.7 `api/server.py` — Novos Endpoints

| Endpoint | Método | Descrição | Predecessor |
|----------|--------|-----------|-------------|
| `/lsp/diagnostics` | GET | Diagnósticos formato LSP para IDE | M8.1 |
| `/monitor/start` | POST | Inicia FileSystemWatcher | M8.0 |
| `/monitor/stop` | POST | Para watcher | M8.0 |
| `/monitor/stream` | GET | SSE stream de alertas em tempo real | M8.0 |
| `/scan-flow` | POST | Taint analysis (FlowVector) | M7.2 |
| `/metrics/advanced` | GET | AdvancedVector + DiagnosticVector por módulo | M7.0 |
| `/metrics/reliability` | GET | ReliabilityVector por módulo | M7.3 |
| `/metrics/performance` | GET | PerformanceVector por módulo | M7.4 |
| `/metrics/architecture` | GET | ArchitectureVector por módulo/projeto | M7.5 |
| `/metrics/test-quality` | GET | TestQualityVector por módulo | M7.6 |
| `/anti-pattern-score` | GET | APS global do projeto | M7.7 |

---

## 4. CRIAR

### 4.1 Novos Vetores de Métricas — Especificação Completa

#### 4.1.1 `AdvancedVector` (6 canais) — M7.0.1
**Arquivo:** `metrics/extended_vectors.py` (adicionar à classe existente)  
**Formaliza:** Sinais já computados em `advanced_metrics.py` como attrs informais

| Canal | Tipo | Fórmula/Fonte | Thresholds |
|-------|------|--------------|-----------|
| `cognitive_cc_total` | `int` | `cognitive_complexity(source)[0]` | WARN>15, CRIT>30 |
| `cognitive_cc_max` | `int` | `max(per_fn.values())` | WARN>10, CRIT>20 |
| `sqale_debt_minutes` | `int` | `sqale_debt(metrics, loc).total_minutes` | WARN>120, CRIT>480 |
| `sqale_rating` | `str` | `'A'` a `'E'` | WARN=C, CRIT=D/E |
| `clone_count` | `int` | `detect_clones(source)` | WARN>3, CRIT>10 |
| `fn_profile_count` | `int` | `len(build_function_profiles(source))` | info only |

#### 4.1.2 `DiagnosticVector` (8 canais) — M7.0.2
**Arquivo:** `metrics/extended_vectors.py` (nova classe)  
**Formaliza:** Sinais descartados do `ClassificationResult` do FrequencyEngine

| Canal | Tipo | Fonte | Significado |
|-------|------|-------|-------------|
| `dominant_frequency_H` | `float` | PSD peak do histórico H[] | Frequência de degradação mais comum |
| `spectral_entropy_H` | `float` | `-Σ p·log(p)` do PSD normalizado | 0=previsível, 1=caótico |
| `phase_coupling_CC_H` | `float` | Cross-correlation peak CC×H | Quanto CC e H movem juntos |
| `burst_index` | `float` | Kurtosis do sinal H | >3 = bursts súbitos de degradação |
| `self_cure_probability` | `float` | `ClassificationResult.self_cure_probability` | P(auto-correção sem intervenção) |
| `onset_reversibility` | `float` | `ClassificationResult.onset_reversibility` | Quão reversível é a degradação |
| `degradation_signature` | `str` | `ClassificationResult.error_type` | Tipo de padrão de erro |
| `frequency_anomaly_score` | `float` | DBSCAN distance score | Desvio do baseline espectral |

#### 4.1.3 `FlowVector` (6 canais) — M7.2
**Arquivo:** `metrics/extended_vectors.py` (nova classe)  
**Cria:** Análise de fluxo de dados / taint analysis

| Canal | Tipo | Detecção | CWE Coberto |
|-------|------|----------|-------------|
| `taint_source_count` | `int` | `request.*`, `sys.argv`, `os.environ`, `input()` | CWE-20 |
| `taint_sink_count` | `int` | `execute()`, `os.system()`, `open()`, `subprocess` | CWE-78/89 |
| `taint_path_count` | `int` | Fluxos fonte→sink rastreados por DFA | CWE-918 |
| `taint_sanitized_ratio` | `float` | `.escape()`, `re.sub()`, `bleach.clean()` no caminho | — |
| `cross_fn_taint_risk` | `float` | Parâmetros contaminados passados entre funções | CWE-501 |
| `injection_surface` | `float` | `taint_path_count × (1 - taint_sanitized_ratio)` | Composite |

#### 4.1.4 `ReliabilityVector` (10 canais) — M7.3a
**Arquivo:** `metrics/extended_vectors.py` (nova classe)

| Canal | Tipo | AST Detection | CWE |
|-------|------|--------------|-----|
| `bare_except_count` | `int` | `ExceptHandler(type=None)` | CWE-390 |
| `swallowed_exception_count` | `int` | `ExceptHandler` com `body=[Pass]` | CWE-390 |
| `mutable_default_arg_count` | `int` | `FunctionDef.defaults` contém List/Dict/Set | CWE-1220 |
| `inconsistent_return_count` | `int` | Funções com `Return(value)` e `Return(None)` coexistindo | CWE-394 |
| `shadow_builtin_count` | `int` | `Name.id ∈ builtins` em contexto `Store` | — |
| `global_mutation_count` | `int` | `ast.Global` + assignment subsequente | CWE-362 |
| `empty_except_block_count` | `int` | `ExceptHandler.body == [Pass]` sem logging | CWE-390 |
| `resource_leak_risk` | `int` | `open()` não dentro de `ast.With` | CWE-772 |
| `regex_redos_risk` | `int` | Pattern com `(a+)+`, `([a-z]+)*`, nested quantifiers | CWE-1333 |
| `infinite_recursion_risk` | `float` | Elevação do ILR existente: recursão sem base case | CWE-674 |

#### 4.1.5 `MaintainabilityVector` (9 canais) — M7.3b
**Arquivo:** `metrics/extended_vectors.py` (nova classe)

| Canal | Tipo | Cálculo | Threshold Ação |
|-------|------|---------|---------------|
| `missing_docstring_ratio` | `float` | Fns públicas sem docstring / total fns públicas | >0.5 = WARNING |
| `avg_function_args` | `float` | Σ(args por fn) / n_fns | >4.0 = WARNING |
| `long_function_ratio` | `float` | Fns com LOC>50 / total fns | >0.2 = WARNING |
| `deeply_nested_ratio` | `float` | Fns com max_depth>4 / total fns | >0.1 = WARNING |
| `cognitive_cc_hotspot` | `int` | `max(cognitive_cc_per_fn.values())` | >20 = CRITICAL |
| `boolean_param_count` | `int` | Params com default `True/False` | >3 = WARNING |
| `magic_number_count` | `int` | Literais numéricos ∉ {-1,0,1,2} fora de UPPER_CASE | >10 = WARNING |
| `long_parameter_list` | `int` | Fns com >5 params | >2 = WARNING |
| `invariant_density` | `float` | `(assert_count/loc + type_hint_ratio + docstring_ratio) / 3` | <0.3 = WARNING |

#### 4.1.6 `PerformanceVector` (8 canais) — M7.4
**Arquivo:** `metrics/extended_vectors.py` (nova classe)

| Canal | Tipo | AST Detection | Complexidade Algorítmica |
|-------|------|--------------|------------------------|
| `n_plus_one_risk` | `int` | `db.execute/query/filter` dentro de `For/While` | O(n) queries vs O(1) |
| `list_in_loop_append_count` | `int` | `list.append()` em `For` onde list declarada fora | Prefer list comprehension |
| `string_concat_in_loop` | `int` | `AugAssign(Add)` com str target dentro de `For/While` | O(n²) em CPython |
| `quadratic_nested_loop_count` | `int` | `For/While` aninhado sem `break` early | O(n²) mínimo |
| `repeated_computation_count` | `int` | Mesma AST subtree ≥2× no corpo do loop | cache opportunity |
| `regex_compile_in_loop` | `int` | `re.compile/search/match` dentro de `For/While` | compilar 1× fora |
| `io_in_tight_loop` | `int` | `open/requests/socket` dentro de `For/While` | I/O batching |
| `inefficient_dict_lookup` | `int` | `.keys()` dentro de `Compare` com `In` op | `key in dict` é O(1) |

#### 4.1.7 `ArchitectureVector` (8 canais) — M7.5
**Arquivo:** `metrics/extended_vectors.py` (nova classe)

| Canal | Tipo | Cálculo | Baseline Martin |
|-------|------|---------|----------------|
| `fan_in` | `int` | Módulos que importam este módulo (grafo invertido) | info only |
| `fan_out` | `int` | Módulos que este módulo importa | info only |
| `coupling_between_objects` | `int` | Tipos externos referenciados nos métodos da classe | CBO<5 ideal |
| `response_for_class` | `int` | Métodos próprios + externos chamados pela classe | RFC<20 ideal |
| `lack_of_cohesion` | `float` | `(P-Q)/max(P+Q,1)` — pares de métodos sem atributos em comum | LCOM<0.5 ideal |
| `abstraction_level` | `float` | Classes abstratas / total classes no módulo | 0.0–1.0 |
| `circular_import_count` | `int` | Importações circulares via DFS | 0 = ideal |
| `layer_violation_count` | `int` | Imports que violam hierarquia infra→domain→app→api | 0 = ideal |

#### 4.1.8 `TestQualityVector` (8 canais) — M7.6
**Arquivo:** `metrics/extended_vectors.py` (nova classe)

| Canal | Tipo | Cálculo | Target Ideal |
|-------|------|---------|-------------|
| `assertion_density` | `float` | assert_count / n_test_fns | >2.0 assertions/teste |
| `test_complexity` | `float` | CC médio das funções test_* | <3.0 |
| `mock_overuse_ratio` | `float` | Mock/patch count / total Call count | <0.3 |
| `test_isolation_score` | `float` | 1 - (global_access + self_mutation) / n_test_fns | >0.8 |
| `flaky_test_risk` | `int` | test_* com `sleep/time.time/datetime.now` | 0 ideal |
| `parameterized_ratio` | `float` | Testes parametrizados / total testes | >0.3 |
| `test_naming_quality` | `float` | Testes com ≥3 words no nome / total | >0.7 |
| `dead_test_count` | `int` | Funções `test_*` sem nenhum `assert` statement | 0 ideal |

#### 4.1.9 `ThreadSafetyVector` (6 canais) — M7.7
**Arquivo:** `metrics/extended_vectors.py` (nova classe)

| Canal | Tipo | AST Detection | CWE |
|-------|------|--------------|-----|
| `global_shared_state_count` | `int` | `global x` modificado em funções chamadas via `Thread(target=fn)` | CWE-362 |
| `lock_missing_count` | `int` | `global x` modificado sem Lock.acquire/release em context | CWE-362 |
| `daemon_thread_risk` | `int` | `Thread(daemon=True)` sem `.join()` visível no scope | CWE-366 |
| `queue_unbounded_risk` | `int` | `Queue()` sem argumento `maxsize` | CWE-400 |
| `asyncio_blocking_call` | `int` | `time.sleep/requests.get/socket` dentro de `AsyncFunctionDef` | CWE-557 |
| `shared_mutable_default` | `int` | Lista/dict em escopo externo modificado em target de Thread | CWE-362 |

### 4.2 Novos Módulos de Análise

#### 4.2.1 `sast/taint_engine.py` — M7.2
Motor de análise de fluxo de dados (DFA) intra-função para Python.

```
Algoritmo TaintSet propagation:
  1. SOURCES: request.args/form/json, sys.argv, os.environ, input(),
              flask.request.*, django.request.GET/POST, FastAPI Query()
  2. PROPAGAÇÃO: y = tainted_x → y ∈ TaintSet (assignment tracking)
              y = func(tainted_x) → y ∈ TaintSet (call propagation heuristic)
              y, z = tainted → ambos ∈ TaintSet (tuple unpack)
  3. SINKS: cursor.execute, os.system, os.popen, open, subprocess.*,
            Template().render, eval, exec, ldap.search, xpath
  4. SANITIZERS: bleach.clean, markupsafe.escape, re.sub, .strip,
                 html.escape, urllib.parse.quote, hashlib.*, hmac.*
  5. REPORTE: SASTFinding com flow_path: List[str] evidenciando o caminho
```

#### 4.2.2 `sast/regex_analyzer.py` — M7.1 (ReDoS)
Analisador estático de padrões regex para detectar backtracking exponencial.

```
Padrões perigosos detectados:
  (a+)+         → nested quantifier — exponencial
  (a|a)+        → alternação redundante — exponencial  
  ([a-z]+)*$    → possessive sem atomic — exponencial
  (.+)*         → wildcard nested — exponencial
  (a{2,})+      → repetição aninhada
Algoritmo: parse regex → walk alternation tree → detectar nesting de quantifiers
```

#### 4.2.3 `monitor/file_watcher.py` — M8.0
FileSystem watcher usando `os.scandir` + polling (sem dependências externas).

```
Interface:
  FileWatcher(root, callback, interval_ms=500)
  .start() → thread daemon
  .stop()  → sinaliza parada
  callback(changed_file: ChangedFile) → dispara análise incremental
  
SSE endpoint GET /monitor/stream:
  data: {"event": "alert", "module": "...", "delta_h": 0.25, "severity": "WARNING"}
```

#### 4.2.4 `lang_adapters/tree_sitter_bridge.py` — M9.0
Bridge genérico para tree-sitter com fallback automático.

```python
class TreeSitterAdapter(LanguageAdapter):
    """
    Usa tree-sitter para análise AST real.
    Fallback: GenericRegexAdapter se tree-sitter não disponível.
    """
    LANGUAGE = "javascript"  # sobrescrito nas subclasses
    TS_LANGUAGE = None       # tree_sitter.Language object
    
    # Queries tree-sitter (S-expression syntax)
    CC_QUERY = """
      (if_statement) @cc
      (for_statement) @cc
      (while_statement) @cc
    """
```

#### 4.2.5 `metrics/anti_pattern_score.py` — M7.7 (fim)
Anti-Pattern Score (APS) — score normalizado [0-100] agregando todos os vetores.

```python
APS_WEIGHTS = {
    "taint_path_count":      30,   # security critical
    "global_mutation_count": 20,   # reliability
    "n_plus_one_risk":       15,   # performance
    "missing_docstring_ratio": 15, # maintainability
    "lock_missing_count":    20,   # thread safety
}
APS = Σ(weight_i × normalized_i) / Σ(weight_i)
# normalized_i = min(1.0, raw_value / threshold_critical_i)
```

### 4.3 Novos Sinais de Pesquisa (Research Track)

| Sinal | Arquivo Proposto | Fórmula | Marco |
|-------|-----------------|---------|-------|
| **Shannon Entropy** do código-fonte | `metrics/entropy.py` | `H = -Σ p·log₂(p)` sobre token histogram | M9.1 |
| **Temporal Coupling Index** | `scan/git_history_scanner.py` (expandir) | `TCI(A,B) = commits(A∩B)/commits(A∪B)` | M9.1 |
| **CC Churn Index** | `metrics/extended_vectors.py` (VelocityVector) | `std(CC_series)/mean(CC_series)` | M7.0.3 |
| **Invariant Density** | `metrics/extended_vectors.py` (MaintainabilityVector) | `(assert_count + type_ratio + doc_ratio)/3` | M7.3b |
| **Anti-Pattern Score (APS)** | `metrics/anti_pattern_score.py` | Weighted sum normalizado | M7.7 |

---

## 5. DEPENDÊNCIAS

### 5.1 Grafo de Dependências — DAG Completo

```
M7.0.1 (AdvancedVector)
  └─ M7.0.2 (DiagnosticVector)
       └─ M7.0.3 (Persist VelocityVector + SnapshotStore ext.)
            ├─ M7.1 (SAST Round 1 — 9 novas regras)
            │    └─ M7.2 (Taint Analysis + FlowVector)
            │         ├─ M8.1 (IDE/LSP Integration)
            │         └─ M9.0 (Tree-Sitter SAST multi-lang)
            ├─ M7.3a (ReliabilityVector)
            │    └─ M7.3b (MaintainabilityVector)
            │         ├─ M7.4 (PerformanceVector)
            │         │    └─ M7.5 (ArchitectureVector)
            │         ├─ M7.6 (TestQualityVector)
            │         └─ M7.7 (ThreadSafetyVector)
            │              └─ APS (Anti-Pattern Score)
            └─ M8.0 (Real-Time Monitoring)  ← requer M7.2 e M7.3
```

### 5.2 Matriz de Predecessores e Sucessores

| Marco | ID | Predecessores Obrigatórios | Predecessores Recomendados | Sucessores Diretos |
|-------|-----|--------------------------|--------------------------|-------------------|
| AdvancedVector | M7.0.1 | — | — | M7.0.2, M7.1, M7.3a |
| DiagnosticVector | M7.0.2 | M7.0.1 | — | M7.0.3 |
| Persist VelocityVector | M7.0.3 | M7.0.2 | — | M7.1, M7.3a, M8.0 |
| SAST Round 1 | M7.1 | M7.0.3 | — | M7.2, SCA+, M9.0 |
| Taint Analysis | M7.2 | M7.1 | M7.3a | M8.1, M9.0 |
| ReliabilityVector | M7.3a | M7.0.3 | — | M7.3b, M7.4, M7.6, M7.7 |
| MaintainabilityVector | M7.3b | M7.3a | — | M7.4, M7.5, M7.6 |
| PerformanceVector | M7.4 | M7.3b | — | M7.5, APS |
| ArchitectureVector | M7.5 | M7.3b | M7.4 | APS |
| TestQualityVector | M7.6 | M7.3b | — | APS |
| ThreadSafetyVector | M7.7 | M7.3b | M7.2 | APS, M8.0 |
| Real-Time Monitoring | M8.0 | M7.0.3, M7.2 | M7.7 | M8.1 |
| IDE/LSP Integration | M8.1 | M7.2 | M8.0 | M9.0 |
| Tree-Sitter SAST | M9.0 | M7.1, M7.2 | M8.1 | M9.1 |
| SCA Expansion | SCA+ | M7.1 | — | — |
| IaC Expansion | IaC+ | — | M7.1 | — |
| AutoFix Expansion | AFix+ | M7.1, M7.3b | — | M8.1 |
| Research Signals | M9.1 | M9.0 | M7.7 | — |

### 5.3 Grupos de Paralelismo

```
SPRINT 1 (Apr 27 – Apr 30):
  [SEQUENCIAL] M7.0.1 → M7.0.2 → M7.0.3

SPRINT 2 (May 4 – May 8):
  [SEQUENCIAL] M7.1 (bloco SAST)
  [PARALELO]   Preparação docs SCA+ (não bloqueia código)

SPRINT 3 (May 11 – May 14):
  [SEQUENCIAL] M7.3a → M7.3b (ReliabilityVector + MaintainabilityVector)
  [PARALELO]   _UCOVisitor improvements (AST-IMP, 2 dias — pode ser início do sprint)

SPRINT 4 (May 18 – May 28):
  [SEQUENCIAL] M7.2 Taint Analysis (7 dias)

SPRINT 5 (Jun 1 – Jun 5):
  [SEQUENCIAL] M8.1 IDE/LSP Integration
  
SPRINT 6 (Jun 8 – Jun 19):
  [SEQUENCIAL] M7.4 → M7.5 (PerformanceVector → ArchitectureVector)
  
SPRINT 7 (Jun 22 – Jul 1):
  [SEQUENCIAL] M7.6 → M7.7 → APS (TestQuality → ThreadSafety → AntiPatternScore)

SPRINT 8 (Jul 6 – Jul 17):
  [SEQUENCIAL] M8.0 Real-Time Monitoring

SPRINT 9 (Jul 20 – Aug 7):
  [PARALELO começo] SCA+ (3 dias) + IaC+ (3 dias) — podem sobrepor
  [SEQUENCIAL] M9.0 Tree-Sitter (10 dias completos)

SPRINT 10 (Aug 10 – Aug 21):
  [SEQUENCIAL] AFix+ (AutoFix expansion) + M9.1 (Research)
```

---

## 6. WBS — Work Breakdown Structure

### 6.1 Tabela WBS Completa

> **Referência de datas:** Início 2026-04-27 (segunda-feira) · Dias úteis only  
> **Convenção de duração:** 1 dia = 1 dia útil de trabalho focado

| WBS ID | Entregável | Tipo | Duração | Início | Fim | Predecessores | Arquivos Criados/Modificados | Testes |
|--------|-----------|------|---------|--------|-----|--------------|------------------------------|--------|
| **FASE 0 — FUNDAÇÃO (PERSISTÊNCIA E FORMALIZAÇÃO)** | | | | | | | | |
| 1.0 | **M7.0 — Formalizar Sinais Informais** | Refactor | 4d | 27/04 | 30/04 | — | | |
| 1.1 | M7.0.1 — AdvancedVector (6 canais) | Criar | 2d | 27/04 | 28/04 | — | `metrics/extended_vectors.py` (edit) | 6 testes TA01-TA06 |
| 1.2 | M7.0.2 — DiagnosticVector (8 canais) | Criar | 1d | 29/04 | 29/04 | 1.1 | `metrics/extended_vectors.py` (edit) | 5 testes TD01-TD05 |
| 1.3 | M7.0.3 — Persistir vetores no SnapshotStore | Modificar | 1d | 30/04 | 30/04 | 1.2 | `sensor_storage/snapshot_store.py` | 4 testes TS01-TS04 |
| 1.4 | M7.0.4 — Integrar AdvancedVector ao uco_bridge.py | Modificar | 0.5d | 30/04 | 30/04 | 1.3 | `sensor_core/uco_bridge.py` | inline |
| 1.5 | M7.0.5 — Endpoint `/metrics/advanced` | Modificar | 0.5d | 30/04 | 30/04 | 1.4 | `api/server.py` | inline |
| 1.6 | M7.0.6 — CHANGELOG [2.3.0] + pyproject bump | Docs | 0.25d | 30/04 | 30/04 | 1.5 | `CHANGELOG.md`, `pyproject.toml` | — |
| **FASE 1 — SEGURANÇA: SAST ROUND 1** | | | | | | | | |
| 2.0 | **M7.1 — SAST Expansion Round 1** | Criar | 5d | 04/05 | 08/05 | 1.x | | |
| 2.1 | M7.1.1 — SAST014 SSRF | Criar | 0.5d | 04/05 | 04/05 | 1.1 | `sast/scanner.py` | 2 testes |
| 2.2 | M7.1.2 — SAST015 XXE | Criar | 0.5d | 04/05 | 04/05 | 1.1 | `sast/scanner.py` | 2 testes |
| 2.3 | M7.1.3 — SAST018 Template Injection | Criar | 1d | 05/05 | 05/05 | 2.1 | `sast/scanner.py` | 3 testes |
| 2.4 | M7.1.4 — `sast/regex_analyzer.py` + SAST019 ReDoS | Criar | 1d | 06/05 | 06/05 | 2.2 | `sast/regex_analyzer.py` (novo) | 5 testes |
| 2.5 | M7.1.5 — SAST021/022/023/024 Crypto | Criar | 1d | 07/05 | 07/05 | 2.3 | `sast/scanner.py` | 4 testes |
| 2.6 | M7.1.6 — SAST025/026/027/028 Auth/TLS | Criar | 0.5d | 08/05 | 08/05 | 2.5 | `sast/scanner.py` | 4 testes |
| 2.7 | M7.1.7 — SAST037/038/039 Reliability | Criar | 0.5d | 08/05 | 08/05 | 2.6 | `sast/scanner.py` | 3 testes |
| 2.8 | M7.1.8 — Melhorar SAST001-013 existentes | Modificar | 0.5d | 08/05 | 08/05 | 2.7 | `sast/scanner.py` | inline |
| 2.9 | M7.1.9 — CHANGELOG [2.4.0] + testes consolidados (30 total M7.1) | Docs+Test | 0.5d | 08/05 | 08/05 | 2.8 | `tests/test_marco_m13.py`, `CHANGELOG.md` | 30 testes TS01-TS30 |
| **FASE 1.B — MELHORIAS DO _UCOVisitor** | | | | | | | | |
| 3.0 | **AST-IMP — 10 novos padrões no _UCOVisitor** | Modificar | 2d | 11/05 | 12/05 | 2.x | | |
| 3.1 | AST-IMP.1 — bare except, swallowed exception | Modificar | 0.5d | 11/05 | 11/05 | 2.x | `sensor_core/uco_bridge.py` | 2 testes |
| 3.2 | AST-IMP.2 — shadow builtin, mutable default | Modificar | 0.5d | 11/05 | 11/05 | 3.1 | `sensor_core/uco_bridge.py` | 2 testes |
| 3.3 | AST-IMP.3 — inconsistent return, global mutation | Modificar | 0.5d | 12/05 | 12/05 | 3.2 | `sensor_core/uco_bridge.py` | 2 testes |
| 3.4 | AST-IMP.4 — deeply nested comprehension, __all__ | Modificar | 0.5d | 12/05 | 12/05 | 3.3 | `sensor_core/uco_bridge.py` | 2 testes |
| **FASE 2 — QUALIDADE: RELIABILITY + MAINTAINABILITY** | | | | | | | | |
| 4.0 | **M7.3 — ReliabilityVector + MaintainabilityVector** | Criar | 4d | 13/05 | 19/05 | 3.x | | |
| 4.1 | M7.3a.1 — ReliabilityVector dataclass (10 canais) | Criar | 1d | 13/05 | 13/05 | 3.4 | `metrics/extended_vectors.py` | 5 testes TR01-TR05 |
| 4.2 | M7.3a.2 — ReliabilityVector AST visitor | Criar | 1d | 14/05 | 14/05 | 4.1 | `sensor_core/uco_bridge.py`, `lang_adapters/generic.py` | 5 testes TR06-TR10 |
| 4.3 | M7.3b.1 — MaintainabilityVector dataclass (9 canais) | Criar | 1d | 15/05 | 15/05 | 4.2 | `metrics/extended_vectors.py` | 5 testes TM01-TM05 |
| 4.4 | M7.3b.2 — MaintainabilityVector AST visitor | Criar | 1d | 19/05 | 19/05 | 4.3 | `sensor_core/uco_bridge.py` | 5 testes TM06-TM10 |
| 4.5 | M7.3.3 — Endpoints `/metrics/reliability`, `/metrics/maintainability` | Modificar | 0.5d | 19/05 | 19/05 | 4.4 | `api/server.py` | inline |
| 4.6 | M7.3.4 — CHANGELOG [2.5.0] + testes consolidados (30 total M7.3) | Docs+Test | 0.5d | 19/05 | 19/05 | 4.5 | `tests/test_marco_m14.py`, `CHANGELOG.md` | 30 testes |
| **FASE 3 — SEGURANÇA: TAINT ANALYSIS** | | | | | | | | |
| 5.0 | **M7.2 — Taint Analysis + FlowVector** | Criar | 7d | 20/05 | 28/05 | 2.x, 4.x | | |
| 5.1 | M7.2.1 — `sast/taint_engine.py` — TaintSet data structure | Criar | 1d | 20/05 | 20/05 | 4.x | `sast/taint_engine.py` (novo) | 4 testes TF01-TF04 |
| 5.2 | M7.2.2 — Source identification (request.*, sys.argv, os.environ, input) | Criar | 1d | 21/05 | 21/05 | 5.1 | `sast/taint_engine.py` | 5 testes TF05-TF09 |
| 5.3 | M7.2.3 — Propagation rules (assignment, tuple unpack, function call) | Criar | 1d | 22/05 | 22/05 | 5.2 | `sast/taint_engine.py` | 5 testes TF10-TF14 |
| 5.4 | M7.2.4 — Sink detection (execute, os.system, open, subprocess, Template) | Criar | 1d | 26/05 | 26/05 | 5.3 | `sast/taint_engine.py` | 5 testes TF15-TF19 |
| 5.5 | M7.2.5 — Sanitizer detection + taint_sanitized_ratio | Criar | 1d | 27/05 | 27/05 | 5.4 | `sast/taint_engine.py` | 5 testes TF20-TF24 |
| 5.6 | M7.2.6 — FlowVector dataclass (6 canais) + integração ao uco_bridge | Criar | 1d | 28/05 | 28/05 | 5.5 | `metrics/extended_vectors.py`, `sensor_core/uco_bridge.py` | 5 testes TF25-TF29 |
| 5.7 | M7.2.7 — Endpoint `/scan-flow` + CHANGELOG [2.6.0] + 30 testes consolidados | Criar | 1d | 28/05 | 28/05 | 5.6 | `api/server.py`, `tests/test_marco_m15.py`, `CHANGELOG.md` | 30 testes total |
| **FASE 4 — IDE/LSP INTEGRATION** | | | | | | | | |
| 6.0 | **M8.1 — IDE/LSP Integration** | Criar | 5d | 01/06 | 05/06 | 5.x | | |
| 6.1 | M8.1.1 — Expandir SASTFinding: suggested_fix, confidence, explanation | Modificar | 1d | 01/06 | 01/06 | 5.x | `sast/scanner.py`, `sast/taint_engine.py` | 3 testes |
| 6.2 | M8.1.2 — AutoFix transforms 5-12 (extract_method, context_manager, etc.) | Criar | 2d | 02/06 | 03/06 | 6.1 | `sensor_core/autofix/transforms/*.py` | 8 testes |
| 6.3 | M8.1.3 — Endpoint `GET /lsp/diagnostics` — formato LSP completo | Criar | 1d | 04/06 | 04/06 | 6.2 | `api/server.py` | 5 testes TL01-TL05 |
| 6.4 | M8.1.4 — CHANGELOG [2.7.0] + 30 testes consolidados | Docs+Test | 1d | 05/06 | 05/06 | 6.3 | `tests/test_marco_m16.py`, `CHANGELOG.md` | 30 testes |
| **FASE 5 — PERFORMANCE E ARQUITETURA** | | | | | | | | |
| 7.0 | **M7.4 — PerformanceVector** | Criar | 4d | 08/06 | 11/06 | 4.x | | |
| 7.1 | M7.4.1 — PerformanceVector dataclass (8 canais) | Criar | 1d | 08/06 | 08/06 | 4.4 | `metrics/extended_vectors.py` | 4 testes TP01-TP04 |
| 7.2 | M7.4.2 — AST visitor: n_plus_one, list_in_loop, string_concat_in_loop | Criar | 1d | 09/06 | 09/06 | 7.1 | `sensor_core/uco_bridge.py` | 4 testes TP05-TP08 |
| 7.3 | M7.4.3 — AST visitor: nested loops, repeated computation, regex/io in loop | Criar | 1d | 10/06 | 10/06 | 7.2 | `sensor_core/uco_bridge.py` | 4 testes TP09-TP12 |
| 7.4 | M7.4.4 — Endpoint `/metrics/performance` + CHANGELOG [2.8.0] | Modificar | 1d | 11/06 | 11/06 | 7.3 | `api/server.py`, `CHANGELOG.md` | inline |
| 8.0 | **M7.5 — ArchitectureVector** | Criar | 5d | 15/06 | 19/06 | 4.x, 7.x | | |
| 8.1 | M7.5.1 — ImportGraphAnalyzer expansion: fan_in, fan_out (projeto-level) | Modificar | 1d | 15/06 | 15/06 | 7.x | `sensor_core/advanced_metrics.py` | 3 testes |
| 8.2 | M7.5.2 — CBO (Coupling Between Objects) via AST | Criar | 1d | 16/06 | 16/06 | 8.1 | `metrics/extended_vectors.py` | 3 testes |
| 8.3 | M7.5.3 — LCOM (Lack of Cohesion in Methods) via método×atributo matrix | Criar | 1d | 17/06 | 17/06 | 8.2 | `metrics/extended_vectors.py` | 3 testes |
| 8.4 | M7.5.4 — RFC, abstraction_level, circular_import DFS | Criar | 1d | 18/06 | 18/06 | 8.3 | `metrics/extended_vectors.py` | 3 testes |
| 8.5 | M7.5.5 — Endpoint `/metrics/architecture` + CHANGELOG [2.9.0] + 30 testes | Modificar | 1d | 19/06 | 19/06 | 8.4 | `api/server.py`, `tests/test_marco_m17.py`, `CHANGELOG.md` | 30 testes total |
| **FASE 6 — TEST QUALITY + THREAD SAFETY + APS** | | | | | | | | |
| 9.0 | **M7.6 — TestQualityVector** | Criar | 3d | 22/06 | 24/06 | 4.x | | |
| 9.1 | M7.6.1 — TestQualityVector dataclass (8 canais) + AST visitor | Criar | 2d | 22/06 | 23/06 | 4.4 | `metrics/extended_vectors.py`, `sensor_core/uco_bridge.py` | 8 testes TQ01-TQ08 |
| 9.2 | M7.6.2 — Endpoint `/metrics/test-quality` + CHANGELOG | Criar | 1d | 24/06 | 24/06 | 9.1 | `api/server.py`, `CHANGELOG.md` | inline |
| 10.0 | **M7.7 — ThreadSafetyVector + APS** | Criar | 5d | 25/06 | 01/07 | 4.x, 5.x | | |
| 10.1 | M7.7.1 — ThreadSafetyVector dataclass (6 canais) | Criar | 1d | 25/06 | 25/06 | 5.7 | `metrics/extended_vectors.py` | 3 testes |
| 10.2 | M7.7.2 — AST visitor thread safety patterns | Criar | 2d | 26/06 | 29/06 | 10.1 | `sensor_core/uco_bridge.py` | 5 testes |
| 10.3 | M7.7.3 — `metrics/anti_pattern_score.py` (APS) | Criar | 1d | 30/06 | 30/06 | 10.2 | `metrics/anti_pattern_score.py` (novo) | 4 testes |
| 10.4 | M7.7.4 — Endpoint `/anti-pattern-score` + CHANGELOG [3.0.0] + 30 testes | Criar | 1d | 01/07 | 01/07 | 10.3 | `api/server.py`, `tests/test_marco_m18.py`, `CHANGELOG.md` | 30 testes total |
| **FASE 7 — REAL-TIME MONITORING** | | | | | | | | |
| 11.0 | **M8.0 — Real-Time Monitoring Mode** | Criar | 8d | 06/07 | 15/07 | 1.x, 5.x | | |
| 11.1 | M8.0.1 — `monitor/file_watcher.py` — FileSystem polling watcher | Criar | 2d | 06/07 | 07/07 | 1.3 | `monitor/__init__.py`, `monitor/file_watcher.py` (novos) | 4 testes |
| 11.2 | M8.0.2 — Delta engine: ΔH, ΔCC, Δsecurity, Δreliability | Criar | 2d | 08/07 | 09/07 | 11.1 | `monitor/delta_engine.py` (novo) | 4 testes |
| 11.3 | M8.0.3 — Alert thresholds + rule engine (ΔH>20%, nova SAST, ILR>0.7) | Criar | 1d | 10/07 | 10/07 | 11.2 | `monitor/alert_rules.py` (novo) | 3 testes |
| 11.4 | M8.0.4 — SSE stream: `GET /monitor/stream` (Server-Sent Events) | Criar | 1d | 13/07 | 13/07 | 11.3 | `api/server.py` | 3 testes |
| 11.5 | M8.0.5 — Endpoints `POST /monitor/start`, `POST /monitor/stop` | Criar | 1d | 14/07 | 14/07 | 11.4 | `api/server.py` | 3 testes |
| 11.6 | M8.0.6 — CHANGELOG [3.1.0] + 30 testes consolidados | Docs+Test | 1d | 15/07 | 15/07 | 11.5 | `tests/test_marco_m19.py`, `CHANGELOG.md` | 30 testes total |
| **FASE 8 — EXPANSÕES (SCA, IaC, AutoFix)** | | | | | | | | |
| 12.0 | **SCA+ — Expansão CVE Database para 200+** | Melhorar | 3d | 16/07 | 20/07 | 2.x | | |
| 12.1 | SCA+.1 — pip expansion (+22 CVEs: Werkzeug, Celery, SQLAlchemy, FastAPI) | Melhorar | 1d | 16/07 | 16/07 | 2.9 | `sca/cve_database.py` | 4 testes |
| 12.2 | SCA+.2 — npm expansion (+30 CVEs: express, jsonwebtoken, socket.io) | Melhorar | 1d | 17/07 | 17/07 | 12.1 | `sca/cve_database.py` | 4 testes |
| 12.3 | SCA+.3 — maven/cargo/go/gem/nuget expansion + 3 novos ecossistemas | Melhorar | 1d | 20/07 | 20/07 | 12.2 | `sca/cve_database.py`, `sca/vulnerability_scanner.py` | 8 testes |
| 13.0 | **IaC+ — Expansão para 100+ regras + 3 novos formatos** | Melhorar | 4d | 21/07 | 24/07 | — | | |
| 13.1 | IaC+.1 — Dockerfile rules D011-D020 | Melhorar | 1d | 21/07 | 21/07 | — | `iac/iac_scanner.py` | 5 testes |
| 13.2 | IaC+.2 — Kubernetes rules K013-K025 | Melhorar | 1d | 22/07 | 22/07 | 13.1 | `iac/iac_scanner.py` | 6 testes |
| 13.3 | IaC+.3 — Terraform rules T013-T025 | Melhorar | 1d | 23/07 | 23/07 | 13.2 | `iac/iac_scanner.py` | 6 testes |
| 13.4 | IaC+.4 — Ansible + Pulumi + CDK scanners | Criar | 1d | 24/07 | 24/07 | 13.3 | `iac/iac_scanner.py` | 6 testes |
| 14.0 | **AFix+ — AutoFix Engine Expansion** | Melhorar | 4d | 27/07 | 30/07 | 6.x, 4.x | | |
| 14.1 | AFix+.1 — Transforms 5-8: extract_method, remove_mutable_default, add_context_manager, replace_bare_except | Criar | 2d | 27/07 | 28/07 | 6.2 | `sensor_core/autofix/transforms/*.py` | 8 testes |
| 14.2 | AFix+.2 — Transforms 9-12: add_docstring, simplify_comparison, replace_string_concat_loop, add_type_hints | Criar | 2d | 29/07 | 30/07 | 14.1 | `sensor_core/autofix/transforms/*.py` | 8 testes |
| **FASE 9 — TREE-SITTER MULTI-LANGUAGE SAST** | | | | | | | | |
| 15.0 | **M9.0 — Tree-Sitter Multi-Language SAST** | Criar | 10d | 03/08 | 14/08 | 2.x, 5.x | | |
| 15.1 | M9.0.1 — `lang_adapters/tree_sitter_bridge.py` — base adapter | Criar | 2d | 03/08 | 04/08 | 5.7 | `lang_adapters/tree_sitter_bridge.py` (novo) | 4 testes |
| 15.2 | M9.0.2 — JavaScript/TypeScript adapter (XSS, prototype pollution, eval) | Criar | 2d | 05/08 | 06/08 | 15.1 | `lang_adapters/javascript_ts_sast.py` (novo) | 6 testes |
| 15.3 | M9.0.3 — Java adapter (null deref, Spring Security misconfig, thread safety) | Criar | 2d | 07/08 | 10/08 | 15.1 | `lang_adapters/java_sast.py` (novo) | 6 testes |
| 15.4 | M9.0.4 — Go adapter (goroutine leaks, channel deadlocks, defer in loop) | Criar | 2d | 11/08 | 12/08 | 15.1 | `lang_adapters/go_sast.py` (novo) | 6 testes |
| 15.5 | M9.0.5 — CHANGELOG [3.2.0] + 30 testes consolidados M9.0 | Docs+Test | 2d | 13/08 | 14/08 | 15.4 | `tests/test_marco_m20.py`, `CHANGELOG.md` | 30 testes total |
| **FASE 10 — RESEARCH & ADVANCED SIGNALS** | | | | | | | | |
| 16.0 | **M9.1 — Research Signals** | Criar | 5d | 17/08 | 21/08 | 15.x | | |
| 16.1 | M9.1.1 — Shannon entropy module (`metrics/entropy.py`) | Criar | 1d | 17/08 | 17/08 | 15.5 | `metrics/entropy.py` (novo) | 3 testes |
| 16.2 | M9.1.2 — Temporal Coupling Index (`scan/git_history_scanner.py` expand) | Melhorar | 1d | 18/08 | 18/08 | 16.1 | `scan/git_history_scanner.py` | 3 testes |
| 16.3 | M9.1.3 — CC Churn Index (adicionar ao VelocityVector) | Melhorar | 1d | 19/08 | 19/08 | 16.2 | `metrics/extended_vectors.py` | 3 testes |
| 16.4 | M9.1.4 — Invariant Density (adicionar ao MaintainabilityVector) | Melhorar | 1d | 20/08 | 20/08 | 16.3 | `metrics/extended_vectors.py` | 3 testes |
| 16.5 | M9.1.5 — Consolidação final + CHANGELOG [3.3.0] + pyproject 3.3.0 | Docs | 1d | 21/08 | 21/08 | 16.4 | `CHANGELOG.md`, `pyproject.toml` | — |

### 6.2 Cronograma Visual (Gantt Simplificado)

```
                        ABR         MAI                 JUN                 JUL                 AGO
WBS ID / Semana →  W17  W18  W19  W20  W21  W22  W23  W24  W25  W26  W27  W28  W29  W30  W31  W32  W33  W34
                   4/27 5/4  5/11 5/18 5/25 6/1  6/8  6/15 6/22 6/29 7/6  7/13 7/20 7/27 8/3  8/10 8/17
M7.0 Foundation    ████
M7.1 SAST Round1        ████
AST-IMP                       ██
M7.3 Rel+Maint               ██████
M7.2 Taint                         ██████████
M8.1 LSP/IDE                                    █████
M7.4 Performance                                      ████
M7.5 Architecture                                          █████
M7.6 TestQuality                                                 ███
M7.7 Thread+APS                                                      █████
M8.0 Real-Time                                                              ████████
SCA+ Expansion                                                                    ███
IaC+ Expansion                                                                       ████
AFix+ Transforms                                                                         ████
M9.0 Tree-Sitter                                                                               ██████████
M9.1 Research                                                                                           █████

VERSÕES:  v2.3.0      v2.4.0   v2.5.0 v2.6.0  v2.7.0  v2.8.0 v2.9.0  v3.0.0       v3.1.0 v3.2.0  v3.3.0
```

### 6.3 Resumo de Esforço por Fase

| Fase | Descrição | Duração | Início | Fim | Versão |
|------|-----------|---------|--------|-----|--------|
| 0 | M7.0 — Fundação / Persistência | 4 dias | 27/04 | 30/04 | **v2.3.0** |
| 1 | M7.1 — SAST Round 1 | 5 dias | 04/05 | 08/05 | **v2.4.0** |
| 1B | AST-IMP — _UCOVisitor | 2 dias | 11/05 | 12/05 | v2.4.1 |
| 2 | M7.3 — ReliabilityVector + MaintainabilityVector | 4 dias | 13/05 | 19/05 | **v2.5.0** |
| 3 | M7.2 — Taint Analysis + FlowVector | 7 dias | 20/05 | 28/05 | **v2.6.0** |
| 4 | M8.1 — IDE/LSP Integration + AutoFix Round 2 | 5 dias | 01/06 | 05/06 | **v2.7.0** |
| 5a | M7.4 — PerformanceVector | 4 dias | 08/06 | 11/06 | **v2.8.0** |
| 5b | M7.5 — ArchitectureVector | 5 dias | 15/06 | 19/06 | **v2.9.0** |
| 6a | M7.6 — TestQualityVector | 3 dias | 22/06 | 24/06 | v2.9.1 |
| 6b | M7.7 — ThreadSafetyVector + APS | 5 dias | 25/06 | 01/07 | **v3.0.0** |
| 7 | M8.0 — Real-Time Monitoring | 8 dias | 06/07 | 15/07 | **v3.1.0** |
| 8 | SCA+ + IaC+ + AFix+ expansions | 11 dias | 16/07 | 30/07 | v3.1.x |
| 9 | M9.0 — Tree-Sitter Multi-Lang SAST | 10 dias | 03/08 | 14/08 | **v3.2.0** |
| 10 | M9.1 — Research Signals | 5 dias | 17/08 | 21/08 | **v3.3.0** |
| **TOTAL** | | **~78 dias úteis** | **27/04** | **21/08** | |

---

## 7. ESPECIFICAÇÃO TÉCNICA POR ENTREGÁVEL

### 7.1 M7.0.3 — Persistência no SnapshotStore

**Arquivo:** `sensor_storage/snapshot_store.py`  
**Migração SQL:**
```sql
ALTER TABLE snapshots ADD COLUMN extended_vectors_json TEXT DEFAULT NULL;
ALTER TABLE snapshots ADD COLUMN advanced_vector_json TEXT DEFAULT NULL;
ALTER TABLE snapshots ADD COLUMN diagnostic_vector_json TEXT DEFAULT NULL;
```
**Serialização:** `json.dumps(dataclasses.asdict(vector))`  
**Deserialização:** `HalsteadVector(**json.loads(row['extended_vectors_json'])['halstead'])`  
**Backward compatibility:** `DEFAULT NULL` — registros antigos retornam `None` para vetores estendidos.

### 7.2 M7.2 — Algoritmo TaintSet

```python
class TaintSet:
    """Rastreio de dados contaminados dentro de uma função."""
    def __init__(self):
        self.tainted: Set[str] = set()  # nomes de variáveis contaminadas
    
    def mark(self, name: str) -> None:
        self.tainted.add(name)
    
    def is_tainted(self, node: ast.expr) -> bool:
        if isinstance(node, ast.Name):
            return node.id in self.tainted
        if isinstance(node, ast.JoinedStr):  # f-string
            return any(self.is_tainted(v) for v in ast.walk(node))
        if isinstance(node, ast.BinOp):
            return self.is_tainted(node.left) or self.is_tainted(node.right)
        if isinstance(node, ast.Call):
            return any(self.is_tainted(a) for a in node.args)
        return False
    
    def propagate(self, target: ast.expr, value: ast.expr) -> None:
        if self.is_tainted(value):
            if isinstance(target, ast.Name):
                self.mark(target.id)
```

### 7.3 M8.0 — SSE Stream Protocol

```
GET /monitor/stream
Content-Type: text/event-stream
Cache-Control: no-cache

event: connected
data: {"session_id": "uuid", "root": "/repo", "timestamp": 1234567890}

event: alert
data: {"module": "auth.login", "severity": "CRITICAL", "rule": "taint_path_count",
       "value": 2, "delta": null, "message": "2 taint flows detected in auth/login.py"}

event: metric_change
data: {"module": "core.processor", "metric": "hamiltonian", "before": 4.2, 
       "after": 8.7, "delta_pct": 107.1, "severity": "WARNING"}

event: heartbeat
data: {"timestamp": 1234567890, "files_watched": 42, "alerts_total": 3}
```

### 7.4 M9.0 — Tree-Sitter Query Language

```python
# Exemplo: JavaScript SAST — XSS via innerHTML
JS_XSS_QUERY = """
(assignment_expression
  left: (member_expression
    property: (property_identifier) @prop
    (#match? @prop "innerHTML|outerHTML|insertAdjacentHTML"))
  right: (_) @value
  (#not-type? @value string))
"""

# Java SAST — null dereference
JAVA_NULL_QUERY = """
(method_invocation
  object: (identifier) @obj
  (#not-null-safe? @obj))
"""
```

### 7.5 Anti-Pattern Score (APS) — Fórmula Completa

```python
APS_COMPONENTS = {
    # Security (peso 30)
    "taint_path_count":         (30, 1),     # >1 já é crítico
    "injection_surface":        (15, 0.5),   # 0.5 = threshold
    "sca_vulnerable_deps":      (10, 3),     # >3 deps vulneráveis
    "iac_misconfig_count":      (5,  5),     # >5 misconfigs
    # Reliability (peso 20)
    "bare_except_count":        (5,  3),
    "resource_leak_risk":       (5,  2),
    "mutable_default_arg_count":(5,  2),
    "inconsistent_return_count":(5,  3),
    # Performance (peso 15)
    "n_plus_one_risk":          (5,  1),
    "quadratic_nested_loop_count":(5, 2),
    "string_concat_in_loop":    (5,  3),
    # Maintainability (peso 15)
    "missing_docstring_ratio":  (5,  0.5),
    "long_function_ratio":      (5,  0.3),
    "cognitive_cc_hotspot":     (5,  20),
    # Thread Safety (peso 20)
    "lock_missing_count":       (10, 1),
    "asyncio_blocking_call":    (5,  1),
    "global_shared_state_count":(5,  2),
}

def compute_aps(vectors: dict) -> float:
    total_weight = sum(w for w, _ in APS_COMPONENTS.values())
    score = 0.0
    for field, (weight, threshold) in APS_COMPONENTS.items():
        raw = vectors.get(field, 0)
        normalized = min(1.0, raw / max(threshold, 1e-9))
        score += weight * normalized
    return round(100.0 * score / total_weight, 2)
```

---

## 8. MÉTRICAS DE SUCESSO POR MARCO

| Marco | KPI Principal | Target | Medição |
|-------|--------------|--------|---------|
| M7.0 | Sinais persistidos / sinais computados | ≥70% (era 17%) | `SELECT COUNT(*) FROM snapshots WHERE extended_vectors_json IS NOT NULL` |
| M7.1 | Regras SAST total | ≥22 regras | `len(RULES)` em sast/scanner.py |
| AST-IMP | Novos padrões detectados no benchmark | 10/10 padrões | testes TR01-TR10 passando |
| M7.3 | Canais formais totais | ≥55 (era 36) | `len(ReliabilityVector.__dataclass_fields__) + ...` |
| M7.2 | Taxa detecção taint em benchmark | >80% dos casos teste | precision em test_taint_benchmark.py |
| M8.1 | SASTFindings com suggested_fix | 100% das regras | `all(f.suggested_fix for f in findings)` |
| M7.4 | Detecção N+1 no benchmark Django | >90% | 9/10 casos no benchmark |
| M7.5 | CBO/LCOM within 10% de baseline Checkstyle/Radon | ±10% | validation/validate_real_repos.py |
| M7.6 | Dead tests detectados em test suite sintética | 100% | testes TQ07-TQ08 |
| M7.7 | Race condition detectada em exemplo canônico | 100% | teste de benchmark threading |
| M8.0 | Latência de alerta após mudança de arquivo | <2 segundos | benchmark end-to-end watcher |
| SCA+ | CVEs totais no banco | ≥200 | `len(_CVE_DB)` |
| IaC+ | Regras IaC totais | ≥100 | `len(_DOCKERFILE_RULES) + ...` |
| M9.0 | Linguagens com AST real | 5 (Python+JS+TS+Java+Go) | `len(tree_sitter_adapters)` |
| **GLOBAL** | Score vs SonarQube Community | **>90/100** | Checklist competitivo §9 |

---

## 9. COMPARATIVO COMPETITIVO vs SONARQUBE

### 9.1 Matriz de Capacidades — Estado Alvo v3.3.0

| Capacidade | SQ Community | SQ Enterprise | UCO v2.2.0 | UCO v3.3.0 Target |
|-----------|:------------:|:-------------:|:----------:|:-----------------:|
| Linguagens suportadas | 17 | 30+ | **40** ✅ | **50+** ✅ |
| Regras SAST Python | ~120 | ~400 | 13 ❌ | **50+** ✅ |
| Taint Analysis | ❌ | ✅ | ❌ | ✅ (M7.2) |
| SCA nativo | ❌ | ✅ | ✅ 65 CVEs | ✅ **200+ CVEs** |
| IaC Scanner nativo | ❌ | ❌ | ✅ 44 regras | ✅ **100+ regras** |
| Análise Espectral | ❌ | ❌ | ✅ **ÚNICO** | ✅ **ÚNICO** |
| Hurst Exponent | ❌ | ❌ | ✅ **ÚNICO** | ✅ **ÚNICO** + formalizado |
| DBSCAN Error Discovery | ❌ | ❌ | ✅ **ÚNICO** | ✅ **ÚNICO** |
| Degradation Forecast | ❌ | ❌ | ✅ **ÚNICO** | ✅ **ÚNICO** + multi-horizon |
| Self-Cure Probability | ❌ | ❌ | ✅ **ÚNICO** | ✅ **ÚNICO** + persistido |
| Cognitive Complexity | ✅ | ✅ | ✅ Python | ✅ Python + 4 langs |
| SQALE Debt | ✅ | ✅ | ✅ | ✅ expandido |
| Quality Gates CI/CD | ✅ | ✅ | ✅ | ✅ + APS gate |
| ReDoS Detection | ✅ | ✅ | ❌ | ✅ (M7.1) |
| Thread Safety | ❌ | ✅ | ❌ | ✅ (M7.7) |
| Performance Anti-Patterns | ❌ | ❌ | ❌ | ✅ **ÚNICO** (M7.4) |
| Architecture Metrics (CBO/LCOM/RFC) | ❌ | ❌ | ❌ | ✅ **ÚNICO** (M7.5) |
| Test Quality Analysis | ❌ | ❌ | ❌ | ✅ **ÚNICO** (M7.6) |
| Real-Time Monitoring | ❌ | ❌ | ❌ | ✅ SSE (M8.0) |
| IDE/LSP Integration | ✅ (plugin) | ✅ (plugin) | ❌ | ✅ nativo (M8.1) |
| suggested_fix automático | ✅ parcial | ✅ | ❌ | ✅ (M8.1) |
| Anti-Pattern Score (APS) | ❌ | ❌ | ❌ | ✅ **ÚNICO** (M7.7) |
| Shannon Code Entropy | ❌ | ❌ | ❌ | ✅ **ÚNICO** (M9.1) |
| Temporal Coupling Index | ❌ | ❌ | ❌ | ✅ **ÚNICO** (M9.1) |
| Offline-first (zero rede) | ❌ | ❌ | ✅ | ✅ |
| Preço | Free/€15k+/yr | €25k+/yr | **Free** ✅ | **Free** ✅ |

### 9.2 Score de Superioridade (estimado)

| Dimensão | Peso | UCO v2.2.0 | UCO v3.3.0 |
|----------|------|-----------|-----------|
| Security (SAST+SCA+IaC) | 30% | 35/100 | 85/100 |
| Unicidade científica | 20% | 90/100 | 95/100 |
| Cobertura de linguagens | 15% | 80/100 | 90/100 |
| Qualidade de código (vectors) | 15% | 50/100 | 95/100 |
| Developer Experience (DX) | 10% | 40/100 | 80/100 |
| Performance & Monitoring | 10% | 20/100 | 85/100 |
| **Score Ponderado** | | **56/100** | **89/100** |

---

## 10. SUMÁRIO EXECUTIVO

### 10.1 Os 3 Entregáveis Mais Críticos (Quick Wins)

| Rank | Marco | Por quê é crítico | Dias | ROI |
|------|-------|------------------|------|-----|
| 1 | **M7.0** — Formalizar sinais | 83% dos sinais computados são descartados. Corrigir isto de imediato multiplica o valor de todo o pipeline existente sem custo de processamento adicional. | 4 | Altíssimo |
| 2 | **M7.1** — SAST Round 1 (9 regras) | SSRF + XXE + ReDoS + SSL no-verify cobrem as top CWEs de 2024 ainda não detectadas. São as mais rápidas de implementar e mais impactantes para segurança. | 5 | Alto |
| 3 | **M7.2** — Taint Analysis | Único diferencial que coloca UCO-Sensor **acima** do SonarQube Enterprise para Python. Nenhuma outra ferramenta gratuita faz DFA intra-função com FlowVector. | 7 | Máximo |

### 10.2 Marcos que Criam Vantagem Competitiva Irrecuperável

| Marco | Vantagem | Quem tem igual |
|-------|----------|----------------|
| M7.4 PerformanceVector | N+1, O(n²), regex em loop — nenhum analisador estático gratuito cobre | Ninguém |
| M7.5 ArchitectureVector | CBO/LCOM/RFC sem servidor, por PR/commit | Ninguém |
| M7.6 TestQualityVector | Análise qualitativa de testes (não apenas coverage %) | Ninguém |
| M8.0 Real-Time Monitoring | SSE streaming de alertas + IncrementalScanner integrado | Ninguém |
| M9.1 Shannon Entropy + TCI | Sinais de pesquisa originais como canal de metrica | Ninguém |

### 10.3 Evolução de Capacidade por Versão

| Versão | Data | Canais Formais | Regras SAST | Destaques |
|--------|------|---------------|-------------|-----------|
| **v2.2.0** | Atual | 36 | 13 | IaC scanner, 4 vetores estendidos |
| **v2.3.0** | 30/04 | 50 | 13 | AdvancedVector, DiagnosticVector, sinais persistidos |
| **v2.4.0** | 08/05 | 50 | 22 | SAST Round 1: SSRF, XXE, ReDoS, Crypto |
| **v2.5.0** | 19/05 | 70 | 22 | ReliabilityVector (10) + MaintainabilityVector (9) |
| **v2.6.0** | 28/05 | 76 | 22 | FlowVector (6) + Taint Analysis completo |
| **v2.7.0** | 05/06 | 76 | 22 | suggested_fix, LSP diagnostics, AutoFix Round 2 |
| **v2.8.0** | 11/06 | 84 | 22 | PerformanceVector (8) |
| **v2.9.0** | 19/06 | 92 | 22 | ArchitectureVector (8) — CBO, LCOM, RFC |
| **v3.0.0** | 01/07 | **100+** | 22 | TestQualityVector, ThreadSafetyVector, APS |
| **v3.1.0** | 15/07 | 100+ | 22 | Real-Time Monitoring SSE |
| **v3.2.0** | 14/08 | 100+ | **50+** | Tree-Sitter JS/TS/Java/Go SAST |
| **v3.3.0** | 21/08 | **110+** | 50+ | Shannon Entropy, TCI, CC Churn — Release Final |

### 10.4 Regra de Ouro para Implementação

> **Nunca implementar um vetor sem:**  
> (1) Dataclass formal com `to_dict()` e `from_*()` constructor  
> (2) Integração ao `uco_bridge.py` via `mv.{vector_name} = Vector.from_...()`  
> (3) Persistência no `SnapshotStore` como coluna JSON  
> (4) Endpoint REST dedicado ou integração ao endpoint existente  
> (5) 30 testes cobrindo: construção, fórmulas, edge cases, REST endpoint  
> (6) CHANGELOG entry + pyproject.toml version bump  
> (7) Push ao GitHub

---

*Documento gerado em: 2026-04-26 | Baseline: UCO-Sensor v2.2.0 (M6.4)*  
*Próxima revisão: após conclusão de M7.0 (2026-04-30)*  
*Versão do documento: 1.0.0*
