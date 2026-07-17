# APEX-R Scientific — Inventário técnico e científico

> Estado: documento de fundação para implementação  
> Escopo: pesquisa in silico, pré-clínica e translacional; não é ferramenta de prescrição, diagnóstico ou decisão regulatória automática  
> Nome do produto: **APEX-R Scientific**  
> Namespace proposto: `apex_r`

## 1. Objetivo do projeto

O APEX-R Scientific é uma extensão científica do APEX destinada a compilar, executar, validar e auditar modelos mecanísticos farmacológicos. O sistema deve integrar evidências moleculares, causais, hemodinâmicas, PBPK, farmacodinâmicas, de sinergia, segurança, otimização e validação em um fluxo único, tipado e rastreável.

O LLM atua como orquestrador: interpreta a tarefa, seleciona ferramentas, solicita dados e explica resultados. Cálculos, ajustes, simulações e gates são executados por código determinístico ou probabilístico versionado. Nenhum valor produzido apenas por linguagem natural pode ser promovido a coeficiente científico.

## 2. Registro das fontes recebidas

| Prioridade | Fonte | SHA-256 | Papel no projeto |
|---|---|---|---|
| 1 | `APEX_R_Documento_Tecnico_Consolidado_Corrigido.docx` | `9C248304C595E34288262AF1D3DC98F4450CDD0772A23B4D0238F4453BA9D448` | Fonte normativa principal. Define arquitetura, correções, módulos, matemática e governança. |
| 2 | `deep-research-report (5).md` | `1C5DC30CF08B46ADF520BAB49F037CEFF43B3439403C04251A77F49F2F457310` | Auditoria técnica que justifica as correções centrais. |
| 3 | `Validação Matemática do Framework APEX.pdf` | `B05B15BB6D83158B25769837A2610D300A804D2B38C00563F1A46433A9549E4A` | Relatório anterior; exemplos numéricos são preliminares e não normativos. |
| 4 | `Incluindo o link_260716_035622.docx` | `C037032E1941CF3CCF58BA2916F7243411CD14D3A95FFAFAFF96122EF3CAF5E0` | Histórico de evolução e roadmap APEX-Lang/APEX-Core. Alegações formais sem prova permanecem conjecturas. |
| 5 | Lista “Bancos de Dados por Módulo” | `1488E869D256BDD1A45133260BB9CEE9E600131A316DEAD4D76770C418776255` | Candidatos a fontes, benchmarks e fases de calibração. |
| 6 | “Análise Crítica do Relatório de Auditoria” e scripts sugeridos | `85C42AF81FF7FAD6795AB406F619C05791BDF542236A1A506FC27F9B93C6DACC` | Fonte secundária. Conceitos úteis são incorporados; coeficientes fixos, alegações regulatórias e código defeituoso são rejeitados. |

### 2.1 Regra de precedência

1. O documento técnico corrigido prevalece em conflitos conceituais ou matemáticos.
2. Resultados reproduzidos com dados versionados prevalecem sobre exemplos copiados de relatórios.
3. Dados primários prevalecem sobre agregações; agregações devem manter a referência original.
4. Uma alegação posterior não altera o estado de um coeficiente sem nova calibração e validação externa.
5. Nenhuma fonte secundária pode transformar um exemplo em constante universal.

## 3. Arquitetura funcional M0–M11

| Módulo | Função normativa | Entradas mínimas | Saídas verificáveis | Dados essenciais |
|---|---|---|---|---|
| M0 | Identificabilidade e desenho experimental | modelo, parâmetros, observáveis, protocolo | rank, FIM, SVD, perfil de verossimilhança, recomendação de desenho | séries temporais, variância de medição, limites paramétricos |
| M1 | Configuração e proveniência | configuração, unidades, versões, seeds, licenças | manifesto imutável de execução | catálogo de fontes e ambientes |
| M2 | Camada molecular | estrutura, ensaios, docking/QSAR | afinidade calibrada com incerteza e domínio | ChEMBL, BindingDB, PubChem, PDB/PDBe; PDBbind opcional |
| M2.5 | CausalDSM | grafo/hipergrafo, equações estruturais | SCM/D-SCM tipado, consultas identificáveis | Reactome, Open Targets, literatura; KEGG/STITCH opcionais |
| M3 | Hemodinâmica | fisiologia cardiovascular, exposição e efeito | pressão, fluxo e estados dinâmicos | fisiologia de referência, sinais, PK/PD e dados pré-clínicos |
| M4 | PBPK + Bayes | fisiologia, ADME, dose, protocolo e observações | curvas concentração-tempo, posterior e diagnósticos | PK-DB, estudos PK, parâmetros fisiológicos, ADME in vitro/in vivo |
| M5A/5B | PD estática e dinâmica | exposição livre no sítio, mecanismo e baseline | efeitos, estados regulatórios e incerteza | curvas dose-resposta, biomarcadores, séries temporais |
| M6 | Sinergia de referência | matriz dose-resposta e desenho combinado | Bliss, Loewe, HSA e ZIP com intervalos | DrugComb, LINCS e dados celulares/tecido-específicos |
| M7 | Risco e decisão | eficácia, segurança e incerteza | objetivos normalizados, restrições e margens | ADME/Tox, safety pharmacology, toxicocinética, eventos e limites |
| M8 | Otimização robusta | espaço de decisão, simulador e restrições | fronteira Pareto robusta e reavaliada | outputs M3–M7 e distribuições de incerteza |
| M9 | Incerteza e contrafactuais | posterior, SCM/D-SCM e intervenção | intervalos, Sobol, ACE/CATE e cenários | amostras posteriores e dados causais adequados |
| M10 | Relatório | artefatos de todos os módulos | relatório rastreável e claims governados | manifestos, métricas, logs e decisões humanas |
| M11 | Validação em camadas | datasets e protocolo pré-registrado | evidência de aprovação, reprovação ou bloqueio | splits internos, externos, pré-clínicos e clínicos |

## 4. Inventário matemático mínimo

### 4.1 Afinidade e termodinâmica

- Estado padrão: `C° = 1 mol/L`.
- Relação válida: `ΔG° = RT ln(Kd/C°)`.
- Conversão: `pKd = -log10(Kd/C°)`.
- Calibração mínima: `y = β0 + β1 s_docking + ε`, onde `y` deve ser `pKd` ou `ΔG°` declarado, nunca uma mistura.
- `β0 = 0,45` e `β1 = 1,08` são exemplos históricos **ILUSTRATIVOS**, não defaults executáveis.
- Cada calibração deve declarar motor e versão de docking, preparação, função de score, alvo/família, temperatura, dataset, split, incerteza e domínio de aplicação.
- `Kd`, `Ki` e `IC50` permanecem tipos de medição distintos. Conversões exigem modelo, condições e justificativa.

### 4.2 Identificabilidade

- Sensibilidade: `J_ij = ∂y_i/∂θ_j`.
- FIM local: `F = JᵀΣ⁻¹J`.
- O número de condição só é interpretável após normalização de parâmetros e observações.
- Diagnóstico mínimo: rank/SVD, autovalores, correlações, perfil de verossimilhança e avaliação do desenho.
- `κ(F)<10⁴` pode ser perfil configurável de benchmark, não lei universal.

### 4.3 PBPK

- Estrutura perfusão-limitada típica: `V_i dC_i/dt = Q_i(C_art - C_i/Kp_i) + entradas - eliminações`.
- Termos de eliminação devem usar a concentração livre compatível com a definição do clearance.
- O estado deve rastrear quantidade em cada compartimento, dose não absorvida e quantidade eliminada para verificar balanço de massa.
- `Kp`, `fu`, `B:P`, `CLint`, `GFR`, permeabilidade, volumes e fluxos carregam unidade, espécie, população e método.
- Ajuste Bayesiano exige priors rastreáveis, múltiplas cadeias, `R-hat`, ESS, divergências e posterior predictive checks.

### 4.4 PD e sinergia

- Hill: `E(C)=E0 + Emax·C^h/(EC50^h+C^h)`, com concentração e `EC50` na mesma unidade.
- Bliss: `E_AB = E_A + E_B - E_AE_B` somente para efeitos normalizados e sob hipótese de independência.
- Loewe, HSA e ZIP não são intercambiáveis; cada resultado deve nomear o modelo.
- Em exposição dinâmica deve-se avaliar `E(C(t))` e integrar a trajetória; `E(média(C))` não é substituto geral.

### 4.5 Causalidade

- DAG/do-calculus é permitido somente quando aciclicidade e hipóteses de identificação são declaradas.
- Feedback fisiológico requer D-SCM, EDO causal ou discretização temporal explícita.
- Correlação, feature importance ou perturbação de um modelo preditivo não demonstram causalidade.
- Assinaturas biológicas incluem a cadeia de indução `Composto → Receptor nuclear → Gene → Enzima/Transportador`.

### 4.6 Otimização

- Dominância para minimização: `x ≺ y` se todos os objetivos de `x` forem não piores e pelo menos um for melhor.
- Hipervolume exige orientação e ponto de referência fixo e válido.
- Sob ruído: múltiplas seeds, replicações independentes, chance constraints/CVaR ou critério probabilístico nomeado.
- Métricas mínimas: HV, IGD+, epsilon, factibilidade e custo.

## 5. Camada pré-clínica

A evidência pré-clínica é um perfil transversal de M11. Ela não será confundida com evidência clínica nem acrescentará um novo módulo concorrente.

| Nível | Evidência | Conteúdo mínimo | Gate de saída |
|---|---|---|---|
| PCL-0 | In silico qualificado | estrutura, alvo, ADME/Tox previsto, incerteza e domínio | hipóteses priorizadas; nenhum claim de segurança |
| PCL-1 | In vitro molecular/celular | linhagem/célula, espécie, ensaio, concentração, tempo, controles e replicatas | curva reproduzível, QC e efeito com intervalo |
| PCL-2 | Ex vivo/NAM/ADME-Tox | matriz biológica, organoide/tecido, estabilidade, permeabilidade, metabolismo, citotoxicidade | parâmetros IVIVE e riscos principais qualificados |
| PCL-3 | In vivo PK/PD | espécie/cepa/sexo/idade, dose, via, formulação, amostragem e biomarcadores | exposição e resposta reproduzidas; modelo animal relevante |
| PCL-4 | Toxicologia e safety pharmacology | toxicocinética, órgãos-alvo, dose repetida, endpoints cardiovasculares/respiratórios/SNC, patologia | NOAEL/LOAEL ou limites equivalentes com incerteza e contexto |
| PCL-5 | Translação | escalonamento, PBPK interespecífico, exposição livre, MABEL/HED quando aplicável | pacote de evidência revisado por humano; prontidão translacional, não autorização clínica |

### 5.1 Metadados pré-clínicos obrigatórios

- espécie, cepa, sexo, idade, massa e estado fisiológico;
- modelo de doença e justificativa de relevância humana;
- randomização, cegamento, cálculo amostral, inclusões/exclusões e perdas;
- dose, via, veículo, formulação, frequência, duração e lote;
- matriz, tempos, método analítico, LLOQ/ULOQ, recuperação e estabilidade;
- endpoint primário pré-especificado, controles positivos/negativos e replicatas;
- protocolo, aprovação ética, laboratório, GLP/não-GLP e desvios;
- dados individuais quando permitidos, estatística, efeito, incerteza e eventos adversos;
- aderência declarada a 3Rs, PREPARE e ARRIVE 2.0 para estudos animais.

### 5.2 Regras translacionais

- Comparar exposições livres (`Cmax,u`, `AUC_u`) e não apenas dose nominal.
- Alometria simples só é permitida com expoente, espécies, resíduos e domínio documentados.
- IVIVE deve registrar fatores de escala, abundância enzimática/transportador e incerteza.
- NOAEL não vira automaticamente dose humana; MABEL, HED e margens de segurança são métodos distintos.
- Um resultado animal não será rotulado `VALIDADO CLINICAMENTE`.
- Ausência de toxicidade observada não equivale a segurança demonstrada fora das doses, duração e endpoints testados.

## 6. Fontes de dados por domínio

### 6.1 Núcleo aberto

| Domínio | Fontes | Uso principal |
|---|---|---|
| Estruturas e afinidade | ChEMBL, BindingDB, PubChem, PDB/PDBe | M2, benchmarks e entidades |
| Caminhos e alvos | Reactome, Open Targets | M2.5 e M9 |
| PK/PBPK | PK-DB, literatura primária, FDA/EMA públicos | M4 e translação |
| Sinergia/expressão | DrugComb, LINCS/GEO | M5–M6 |
| Ensaios e resultados | ClinicalTrials.gov | contexto clínico; registros sem resultados não calibram efeito |
| Genética/população | GWAS Catalog, FinnGen público, NHANES | M9–M11 e aplicabilidade populacional |
| Pré-clínico/toxicologia | EPA ToxCast/CompTox, Tox21, PubChem BioAssay | PCL-0 a PCL-2 e M7 |
| Padrões não clínicos | OECD Test Guidelines, SEND, ARRIVE, PREPARE | protocolo, interoperabilidade e relatório |

### 6.2 Fontes condicionadas

- PDBbind atual: assinatura/termos; v2020 possui acesso demo condicionado e não deve ser redistribuído.
- DrugBank: licença obrigatória e restrições de redistribuição.
- KEGG: acesso/licença dependente de finalidade; bulk/serviço não é irrestrito.
- Simcyp: software e bibliotecas licenciados.
- PhysioNet: política por dataset; dados credentialed/restricted exigem autorização individual e DUA.
- SEND regulatório e datasets proprietários de CRO: somente via importação autorizada e armazenamento segregado.

### 6.3 Política de aquisição

- API para consulta pontual; bulk release para treinamento/benchmark sistemático.
- Cada aquisição gera snapshot imutável com versão, consulta, horário, licença e hash.
- Atualização nunca substitui snapshot usado em resultado publicado.
- MCP é plano de controle; respostas externas não são usadas diretamente sem congelamento e validação.

## 7. Inventário de coeficientes

Cada coeficiente deve possuir:

- identificador estável, módulo, símbolo e equação;
- valor pontual ou distribuição, unidade e transformação;
- espécie, tecido, população, protocolo e domínio de aplicação;
- fonte primária, IDs/DOI/PMID, versão e licença;
- dataset, query, filtros, exclusões e split;
- método de ajuste, priors, software, seed e commit;
- métricas de ajuste, calibração e validação externa;
- dependências a montante e artefatos a jusante;
- estado de maturidade e estado de validação;
- autor/revisor, justificativa e histórico de promoção.

### 7.1 Estados

Maturidade: `NORMATIVE`, `LITERATURE_PRIOR`, `ILLUSTRATIVE`, `FIT_REQUIRED`, `REJECTED`, `CONJECTURAL`.

Validação: `UNVALIDATED`, `INTERNAL_VALIDATED`, `PRECLINICAL_VALIDATED`, `EXTERNAL_VALIDATED`, `PROMOTED`, `DEPRECATED`, `INVALIDATED`.

`PRECLINICAL_VALIDATED` exige PCL-1 ou superior, dados pré-clínicos independentes e identificação de espécie/modelo; PCL-0 permanece `PRELIMINARY` ou `INTERNAL_VALIDATED`. O rótulo não implica validade clínica.

## 8. Armazenamento necessário

- SQLite: catálogo, estado, coeficientes, relações, gates e auditoria.
- Parquet/Arrow: medições normalizadas, features, splits e outputs tabulares grandes.
- Artefatos endereçados por conteúdo: arquivos brutos, modelos, cadeias posteriores, figuras e relatórios.
- Segredos: variáveis de ambiente ou secret store; nunca SQLite, logs ou manifestos.
- Dados restritos: namespace e política de acesso próprios; nenhum artefato derivado é publicado sem checagem da licença.

## 9. Ferramentas e superfícies necessárias

- Biblioteca Python para contratos, unidades, dados, modelos e validação.
- CLI para ingestão, ajuste, validação, comparação, promoção e lineage.
- Notebooks apenas como consumidores da biblioteca; lógica científica não fica presa a células.
- MCP local por `stdio` inicialmente, com serviço interno independente do transporte.
- Sandbox científico com NumPy/SciPy/pandas/scikit-learn/SymPy e extras Bayesianas controladas.
- Runner único de benchmarks que produza JSON, Markdown, logs e código de saída.

## 10. Componentes APEX reutilizáveis

| Componente existente | Reuso | Adaptação obrigatória |
|---|---|---|
| Orquestrador SCIENTIFIC | seleção e sequência de módulos | contratos `GateEnvelope` e estados científicos |
| Multi-sandbox profiles | execução isolada de Python | dependências pinadas, limites e captura de artefatos |
| SymPy formal verifier | checagens algébricas | unidades, domínios e hipóteses explícitas |
| Monte Carlo simulator | propagação de incerteza | seeds, convergência e distribuição registrada |
| Hypothesis DAG | hipóteses acíclicas | D-SCM separado para feedback |
| Ethical barrier | políticas gerais | pesquisa apenas, dados sensíveis, 3Rs e revisão pré-clínica |
| Verification gate | estrutura de gate | trocar comportamento cognitivo fail-open por científico fail-closed |
| Event bus | eventos e triggers | snapshots, invalidação e promoção auditável |

## 11. Lacunas atuais

- Não existe implementação APEX-R científica no repositório.
- Não há banco de coeficientes, snapshots ou lineage.
- Benchmarks do documento corrigido ainda não foram executados com outputs APEX.
- Valores experimentais históricos de `Kd` carecem de IDs primários verificáveis.
- A suíte anexada contém erros de sinal, baseline, circularidade e algoritmo; não pode ser adotada.
- Não existem datasets pré-clínicos locais nem perfil SEND implementado.
- Não há conectores/MCP científicos ativos.
- APEX-Lang/APEX-Core permanece roadmap até haver semântica e provas implementadas.

## 12. Critérios de conclusão da ferramenta

1. Toda execução é reproduzível por manifesto, hashes, ambiente e seeds.
2. Todo coeficiente é rastreável até dado e protocolo.
3. Unidades incompatíveis e domínios inválidos falham antes da simulação.
4. Datasets sintéticos nunca recebem status de validação externa ou pré-clínica.
5. Evidência in vitro, animal, pré-clínica, translacional e clínica permanece separada.
6. Atualizações criam candidatos e nunca promovem coeficientes sozinhas.
7. Resultados publicáveis declaram dataset, versão, protocolo, métrica e domínio.
8. Nenhum gate pode ser contornado por texto do LLM.

## 13. Referências operacionais verificadas

- ChEMBL: <https://chembl.gitbook.io/chembl-interface-documentation/downloads>
- BindingDB API: <https://www.bindingdb.org/rwd/bind/BindingDBRESTfulAPI.jsp>
- Reactome downloads: <https://release.reactome.org/download-data>
- Open Targets data: <https://platform-docs.opentargets.org/data-access>
- PK-DB: <https://pk-db.com/data>
- ClinicalTrials.gov API: <https://clinicaltrials.gov/data-api>
- GWAS Catalog API: <https://www.ebi.ac.uk/gwas/docs/programmatic-access>
- NHANES: <https://wwwn.cdc.gov/nchs/nhanes/continuousnhanes/>
- EPA ToxCast: <https://www.epa.gov/comptox-tools/exploring-toxcast-data>
- FDA SEND/study data: <https://www.fda.gov/industry/study-data-standards-resources/study-data-submission-cder-and-cber>
- OECD Test Guidelines: <https://www.oecd.org/en/topics/sub-issues/testing-of-chemicals/test-guidelines.html>
- ARRIVE 2.0: <https://arriveguidelines.org/arrive-guidelines>
- PREPARE: <https://norecopa.no/no/prepare>
- Guias não clínicos da Anvisa: <https://www.gov.br/anvisa/pt-br/assuntos/medicamentos/pesquisaclinica/anuencia-em-pesquisa-clinica/guias-e-manuais>
- CONCEA/MCTI: <https://www.gov.br/mcti/pt-br/composicao/colegiados/concea>
