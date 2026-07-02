# UCO Sensor — Missão, Revalidação e Metas

> Documento de alinhamento estratégico (Sprint BP). Congela **o que a
> ferramenta É**, **o que ela já faz de verdade (revalidado com dado
> real)**, e **as metas** que orientam tudo daqui em diante. Toda criação
> futura deve mirar este horizonte.

## 1. Missão (3 camadas)

1. **UCO Sensor — rastreia** bugs, loops, dead-code, vulnerabilidades e
   **degradação de código**: qual módulo está degradando, qual linha tem
   erro, quando deve falhar. Emite **sinais mapeáveis** e identifica onde
   alguém pode quebrar/invadir.
2. **UCO Core (UCO V4)** — **identifica o que falhou e o que corrigir**, do
   vibe-coding ao repositório completo. Determina o patch/reparo.
3. **APEX** — integra depois: monitora, **aprende**, cria correções, sugere
   aperfeiçoamentos (módulos de hamiltoniano alto, quais dividir),
   auto-desenvolvimento via MCP; monitoramento em tempo real.

O motor probabilístico (**propagação de sinal + SA + HMC**) pontua falhas de
segurança e pontos fracos.

## 2. Revalidação — estado atual (dado real, 2026-07-02)

| Dimensão da missão | Motor | Evidência real (revalidada) | Status |
|---|---|---|---|
| Degradação / módulo / linha | MetricVector (UCO) | roots.py: hamiltonian=5.03, cyclomatic=76, dup=41, dsm=0.15 | ✅ funciona |
| Dead-code / loop-infinito | `cfg_signals` (CFG do V4, M15) | reachable_ratio/infinite_loop_risk computados p/ Python+genérico | ✅ funciona (subusado) |
| Bug sem-âncora (memory-safety) | GuardAwareScanner M11 | php-src: dispara L1212 GA01 sem conhecer o fix | ⚠️ funciona, ruidoso (C só) |
| Localizar fix / classe / versão | FixDiffLocalizer M10 | php-src: L1212, CWE-190/476 | ✅ funciona (âncora no diff) |
| Injeção / deserialização | TaintAnalyzer (M16/M16.1) | request.args.get→os.system + pickle.loads: 4 caminhos | ✅ funciona (Python, intra-proc) |
| Parou de disparar? (before/after) | CorpusValidator M12 | 6 C validados; php-src detect→resolve; artefato JSON | ⚠️ parcial (Python bloqueado por dado) |
| O que corrigir (Core) | UCO V4 `analyze`/`quick_optimize`/HMC | AnalysisResult com métricas; otimizadores presentes | ⚠️ presente, não ligado a "sugerir patch por finding" |
| Segurança probabilística (SA/HMC/sinal) | spectral_aps + HMC repair | fingerprint espectral + reparo HMC existem | ⚠️ não ligado a "score de ponto fraco" |
| APEX auto-correção via IA/MCP | — | — | ❌ futuro |

**Leitura honesta:** o Sensor já tem sinais reais em TODAS as dimensões de
rastreio; os gaps são de **precisão** (M11 ruidoso), **cobertura de
linguagem** (detecção sem-âncora só C+Python), **ligação Core→patch** (V4
não emite sugestão de correção por finding) e **camada APEX** (não iniciada).

## 3. Metas (roadmap orientado à missão)

### META A — Precisão de rastreio (Sensor confiável)
- A1. M11 site-aware + gated por dataflow (cortar FP tipo ffmpeg/postgres).
- A2. Cobrir classes faltantes: type-widening (redis), early-return (ffmpeg),
  clamp (sqlite), use-after-free, signed/unsigned.
- **Sucesso:** ≥90% precisão nos 100 repos; FP barrado e reportado.

### META B — Cobertura de linguagem da detecção sem-âncora
- B1. Taint + guard-aware para JS/TS/Java/Go/PHP/Rust via tree-sitter + CFG
  genérico do V4 (hoje: C no M11, Python no taint).
- **Sucesso:** detecção sem-âncora rodando nas 8 categorias do corpus.

### META C — UCO Core determina o que corrigir (o elo Sensor→fix)
- C1. Dado um finding do Sensor, o UCO Core (V4 `quick_optimize`/HMC/greedy)
  emite o **patch mínimo sugerido** + prova de não-regressão do APS.
- C2. Validar que o patch sugerido faz o Sensor **parar de disparar**.
- **Sucesso:** loop Sensor→Core→re-scan fechado num finding real.

### META D — Motor probabilístico de ponto fraco
- D1. `weak_point_score(módulo)` combinando propagação de sinal + SA + HMC +
  superfície de taint → mapa de "onde quebra/invade".
- **Sucesso:** ranking de módulos por risco, validado contra CVEs reais.

### META E — Validação em escala + dataset de regressão
- E1. Rodar M12 nos ~40 pares Python/JS/Rust via **tags de release**
  (contorno da API 403) → dataset "parou de disparar".
- **Sucesso:** artefato de degradação para os 100 repos.

### META F — Camada APEX (auto-correção)
- F1. API que expõe os sinais do Sensor para uma IA consumir.
- F2. Loop: IA lê sinais → propõe fix → Sensor revalida → aprende.
- F3. Integração MCP para auto-desenvolvimento.
- **Sucesso:** APEX corrige um bug real end-to-end usando só sinais do Sensor.

## 4. Prioridade proposta

**Agora:** META C (Core→patch — é o que fecha o valor "identifica o que
corrigir" e conecta as duas camadas já prontas) e META A (precisão, sem a
qual sugestões de fix não são confiáveis). **Depois:** E (escala) → B
(linguagens) → D (probabilístico) → F (APEX).

Racional: o Sensor já **rastreia**; o próximo salto de valor é **fechar o elo
com o UCO Core para dizer o que corrigir** (META C), porque é o que
transforma sinais em ação e prepara a camada APEX. Sem precisão (META A) as
sugestões perdem confiança — por isso as duas andam juntas.
