# Sprint AE — Lista Master de Repositórios (curadoria original do usuário)

> Salvo verbatim (recuperado do transcript da sessão) para servir de
> fonte única de verdade do loop de análise contínua AE. Esta é a lista
> completa de ~100 repositórios enviada pelo usuário em
> 2026-06-26T22:32:36Z, organizada em 8 categorias de ecossistema, mais
> as 3 dicas de estratégia de teste que orientam a metodologia.

## Status de cobertura — atualizado Sprint AO (honesto, não amostra)

> Correção: a tabela anterior (Sprint AD) ficou obsoleta desde Sprint AG
> (laravel/rails/dotnet/netty/lodash) e Sprint AJ (capstone re-scan).
> Sprint AM (`AM_sca_repo_sweep.md`) introduziu um **segundo eixo de
> evidência**, complementar ao CVE-diff (SAST): varredura de
> manifesto-de-dependências real via `OSVScannerBridge` (M9.1/SCA).
> Sprint AN (`AN_sca_repo_sweep_round2.md`) automatizou a descoberta de
> manifesto (tenta candidatos por ecossistema) e escaneou 45
> repositórios numerados de uma vez, com 28 sucessos. Sprint AO
> (`AO_sca_repo_sweep_round3.md`) resolveu o bloqueio histórico de
> `trino`/`netty` (POM agregador → POM de submódulo-folha) e descobriu
> 16 manifestos novos via inspeção direta de root-listing, incluindo
> correção de truncamento da GitHub Contents API (>1MB) via
> `raw.githubusercontent.com`/`curl`. Os dois eixos são contados
> separadamente por repo — um repo pode ter 0, 1 ou 2 eixos cobertos.
> `golang/go` e `rust-lang/regex` continuam fora da numeração original
> (extras de AD) e não contam para os denominadores abaixo.

| Categoria | Cobertura real (≥1 eixo) | Repo/CVE/SCA numerados já testados |
|---|---|---|
| JS/TS (1-20) | **18/20** | #1 vscode SCA (D, 11), #2 react SCA (E, 239), #3 electron SCA (D, 48), #5 next.js SCA (D, 58, via Cargo.lock), #6 vue-core SCA (E, 39), #7 angular SCA (E, 59), #8 remix SCA (D, 21), #9 tailwindcss SCA (C, 5), #10 strapi SCA (E, 119), #11 axios CVE-2023-45857 (SAST) + ws CVE-2026-48779 (SCA), #13 three.js SCA (A, limpo), #15 vite SCA (E, 22), #16 metabase SCA (E, 151, via bun.lock), #17 kibana SCA (E, 45); deno (extra, mesmo bloco #5/#17) SCA (D, 12), #18 grafana SCA (D, 32 yarn.lock + B, 8 go.mod), #19 lodash CVE-2021-23337 (SAST), #20 berry SCA (E, 181) |
| Python (21-40) | **19/20** | #21 cpython CVE-2024-6232 (SAST AST-anchored em tarfile.py, churn=196 — Sprint AV, via GHSA), #22 pandas (sem CVE), #23 scikit-learn CVE-2024-5206 (SAST AST-anchored, churn=28 — Sprint AU), #24 tensorflow SCA (B, 6), #25 pytorch SCA (A, limpo), #26 fastapi, #27 django, #28 flask, #29 transformers CVE-2023-6730 (SAST AST-anchored, churn=117 — AU), #30 ansible SCA (E, 8), #31 celery (SAST) + SCA limpo, #32 home-assistant SCA (A, limpo), #33 scipy CVE-2023-25399 (SAST AST-anchored em nd_image.c via grammar C, churn=7 — AU), #35 airflow SCA (B, 8, via uv.lock), #36 salt CVE-2024-22232 (SAST AST-anchored, churn=213 — AU), #37 scrapy, #38 requests (×3 CVEs SAST) + SCA limpo, #39 sqlalchemy CVE-2019-7164 (SAST AST-anchored, churn=188 — AU), #40 localstack SCA (B, 8); #34 boto3 **confirmado não aplicável** (requirements.txt só com `-e git+...`, sem lockfile real). Todos os 5 da Sprint AU via fix-commit resolvido pelo GHSA M9.3 + diff AST M9.2 |
| Go (41-55) | **15/15 — categoria fechada** | #41 kubernetes SCA (A, limpo), #42 moby SCA (A, limpo), #43 terraform SCA (A, limpo), #44 vault SCA (D, 9), #45 prometheus SCA (B, 2), #46 etcd CVE-2021-28235 (SAST) + SCA limpo, #47 istio SCA (B, 14), #48 cockroach SCA (E, 66), #49 caddy SCA (A, limpo), #50 gin SCA (A, limpo), #51 syncthing SCA (B, 3), #52 rancher SCA (B, 5), #53 influxdb SCA (E, 27, via Cargo.lock), #54 argo-cd SCA (B, 2), #55 hugo SCA (B, 17); `golang/go` (extra) CVE-2023-29404 |
| Rust (56-65) | **9/10** | #56 rust-lang/rust SCA (B, 8) + CVE-2024-24576 BatBadBut (SAST AST-anchored M9.2, validação cruzada: churn=640), #57 tokio CVE-2023-22466 (SAST), #58 alacritty SCA (B, 2), #60 nushell SCA (B, 9), #61 tikv SCA (D, 33), **#62 diesel soundness fix (SAST AST-anchored M9.2: `unsafe` 2→3, churn=20 — fechado em Sprint AS)**, #63 swc SCA (E, 39), #64 actix-web SCA (D, 10), #65 tauri SCA (D, 36); `rust-lang/regex` (extra) CVE-2022-24713. Resta #59 serde sem CVE/fix localizável (lib de serialização, sem memory-safety CVE indexada) |
| Java/Kotlin (66-75) | **7/10** | **#66 spring-boot CVE-2023-20883 (SAST AST-anchored M9.2 via fix-commit resolvido pelo GHSA M9.3: churn=180 — fechado em Sprint AT)**, #67 spring-framework CVE-2022-22965 (SAST), #68 commons-lang SCA (A, limpo), #69 flink SCA (A, limpo), **#70 kafka CVE-2022-34917 (SAST AST-anchored Java em DataInputStreamReadable.java, churn=71 — Sprint AV via GHSA)**, #72 netty CVE-2019-20444 (SAST) + SCA (A, limpo, via pom.xml de submódulo: common/buffer/transport/handler/codec), #74 guava SCA (A, limpo, via guava/pom.xml de submódulo — não o pom-pai). Gaps: #71 elasticsearch, #73 redisson, #75 kotlin (sem fix-commit resolvível via GHSA/commit-search; kotlin precisaria de grammar tree-sitter própria) |
| C/C++ (76-85) | **7/10** | #76 linux CVE-2016-5195 (SAST), #77 postgres CVE-2021-32027 (SAST), #78 redis CVE-2022-24834 (SAST), #79 curl CVE-2023-38545 (SAST), #80 ffmpeg CVE-2020-22015 (SAST), #81 git CVE-2021-21300 (SAST), #82 opencv CVE-2019-7317 (SAST) — eixo SCA estruturalmente não aplicável a esta categoria (sem package manager de terceiros resolvível em C puro, ver AN); #83 sqlite reservado para teste de FP, #84 httpd e #85 wireshark sem commit de fix localizável via busca automatizada (ver AP) |
| PHP/Ruby/C#/Mobile (86-95) | **6/10** | #86 laravel GHSA-crmm-hgp2-wgrp (SAST), #87 rails CVE-2024-26143 (SAST) + SCA (E, 61), #88 dotnet/runtime CVE-2026-45491 (SAST), #90 flutter SCA (A, limpo), **#91 wordpress SCA vendorizado (A, limpo — Sprint AW, motor M9.4: libs embutidas `rmccue/requests`@2.0.17 e `phpmailer/phpmailer`@7.0.2 checadas por range contra 1+14 advisories GHSA, ambas patched)**, #92 php-src CVE-2019-11043 (SAST AST-anchored M9.2: regex dava delta=0, AST churn=12 com bounds-check `>`+1). Gaps: #89 roslyn, #93 jekyll, #94 signal-android, #95 shadowsocks-windows (sem lockfile, sem fix-commit GHSA, sem lib vendorizada versionada detectada ainda) |
| Infra dados/cloud (96-100) | **4/5** | #96 spark SCA (A, limpo), #97 nomad SCA (B, 2), **#98 ceph CVE-2021-3979 (SAST AST-anchored Python em encryption.py, churn=105 — Sprint AV via GHSA; o eixo SCA continua N/A, mas o SAST fecha o repo)**, #99 trino SCA (A, limpo, via pom.xml de submódulo: core/trino-main, client/trino-jdbc, lib/trino-filesystem); #100 clickhouse **confirmado não aplicável** ao SCA (só pyproject.toml sem lock) e sem fix-commit SAST resolvível |

**Total real: 86/100 repositórios numerados com pelo menos um eixo de
evidência validado** (SAST CVE-diff e/ou SCA dependência-exposição) —
salto de 50/100 (Sprint AN) para 69/100 (Sprint AO), **74/100 (Sprint
AP)**, **75/100 (Sprint AR)**, **76/100 (Sprint AS)**, **77/100
(Sprint AT)**, **82/100 (Sprint AU)**, **85/100 (Sprint AV)**, e
**86/100 (Sprint AW)**. AU fechou 5 repos Python e AV mais 3 (cpython
#21, kafka #70, ceph #98) via o pipeline resolve-commit(GHSA M9.3)→
diff-AST (M9.2); AW introduziu o **terceiro motor — SCA de dependência
vendorizada (M9.4)** — e fechou `#91 wordpress` (veredito limpo sobre
libs embutidas sem lockfile). Sprint AP estendeu o eixo SAST
CVE-anchored before/after a 5 repositórios C/C++ (`linux`, `postgres`,
`redis`, `ffmpeg`, `opencv`). Sprint AR introduziu um **motor novo**
(M9.2 — diff estrutural AST via tree-sitter, ver
`AR_deep_research_synthesis.md`) que resolve a limitação onde o eixo
regex dava delta=0 em fixes de uma linha, fechando `php-src`
(CVE-2019-11043: AST churn=12 com o bounds-check `>`+1 visível, contra
delta=0 do adapter regex). Sprint AS estendeu o motor M9.2 à gramática
Rust e fechou `#62 diesel` (fix de soundness `unsafe` 2→3), validando
de passagem `rust-lang/rust` CVE-2024-24576 (já coberto por SCA).
Sprint AT adicionou o **resolver GHSA de fix-commit (M9.3)** — localiza
o commit de correção direto das `references` do GitHub Advisory quando o
projeto não cita o CVE na mensagem — e fechou `#66 spring-boot`
(CVE-2023-20883: fix resolvido via GHSA-xf96-w227-r7c4, churn AST=180).
Restam 14/100 sem eixo: Python (1: `#34 boto3` N/A), Rust (1: `#59
serde`, sem CVE/fix localizável), Java/Kotlin (3: elasticsearch/redisson
sem fix-commit resolvível + kotlin sem grammar), PHP/Ruby/C#/Mobile (4:
roslyn/jekyll/signal/shadowsocks — sem lockfile, sem fix-commit GHSA e
sem lib vendorizada versionada detectada), Infra (1:
clickhouse), e C/C++ (3:
`sqlite` reservado para teste de FP, `httpd`/`wireshark` sem commit de
fix localizável via busca automatizada do GitHub). Eixos de
falso-positivo (dica 3: sqlite/guava)
e throughput (dica 1: kubernetes/tensorflow/linux/vscode) foram
amostrados **uma única vez cada**, em Sprint AE, nunca estendidos a
outros repositórios da lista (exceto vscode e kubernetes, que agora
também têm cobertura SCA). Reconhecido explicitamente pelo usuário
como requisito obrigatório, não amostra opcional — tratado como
trabalho em andamento, task #68. Plano para fechar 100/100 detalhado
na seção final de `AN_sca_repo_sweep_round2.md`.

---

### 🌐 1. Ecossistema JavaScript / TypeScript (Alto volume de dependências e concorrência)
*Ideal para testar análise de vulnerabilidades em cadeias de dependências (Supply Chain), gargalos de concorrência e degradação de performance na Web.*

 1. **microsoft/vscode**: Gigantesco, milhões de linhas de código em TS. Excelente para testar velocidade de escaneamento de monorepos.
 2. **facebook/react**: Histórico massivo de refatorações, perfeito para rastrear quebras de compatibilidade (breaking changes).
 3. **vercel/next.js**: Evolução rápida, alta densidade de features e atualizações constantes de segurança.
 4. **nodejs/node**: Código híbrido (C++ e JS). Ótimo para testar escaneadores híbridos e vazamentos de memória históricos.
 5. **denoland/deno**: Rust e TS. Excelente para verificar arquiteturas modernas e segurança de sandbox.
 6. **vuejs/core**: TypeScript estrito, arquitetura modular e documentação cirúrgica de bugs.
 7. **angular/angular**: Monorepo corporativo massivo. Um teste rigoroso para a velocidade de árvores de dependência complexas.
 8. **remix-run/remix**: Atualizações frequentes de arquitetura e padrões web.
 9. **tailwindlabs/tailwindcss**: Excelente para testar o parseamento de folhas de estilo e otimização de build em lote.
 10. **strapi/strapi**: Node.js massivo voltado para CMS, contendo muitas regras de permissão e endpoints vulneráveis no histórico.
 11. **axios/axios**: Código mais enxuto, porém com um histórico gigante de patches de segurança e concorrência HTTP. *(testado em AD: CVE-2023-45857)*
 12. **expressjs/express**: Base histórica do Node.js. Excelente para testar detecção de padrões de código legados (legacy patterns).
 13. **mrdoob/three.js**: Processamento gráfico em JS. Enorme volume de vetores e matemática propensa a bugs de performance.
 14. **electron/electron**: Integração pesada com Chromium. Um dos maiores repositórios em uso na indústria web/desktop.
 15. **vitejs/vite**: Ferramenta de build moderna. Ótimo para testar análise de ferramentas que manipulam AST (Abstract Syntax Tree).
 16. **metabase/metabase**: Clojure e TypeScript. Excelente para testar o comportamento de ferramentas em bases de código poliglotas.
 17. **elastic/kibana**: Um monorepo TypeScript absurdamente gigante e complexo. Vai estressar o motor do seu SaaS ao limite.
 18. **grafana/grafana**: Mistura Go e TypeScript em larga escala. Perfeito para testes de análise estática e concorrência.
 19. **lodash/lodash**: Histórico riquíssimo em otimizações extremas de algoritmos básicos e correção de bugs de mutabilidade.
 20. **yarnpkg/berry**: Arquitetura de gerenciamento de pacotes complexa, ideal para testar lógica de grafos de arquivos.

### 🐍 2. Ecossistema Python (Análise Estática, IA e Ciência de Dados)
*Ótimos para testar a detecção de bugs de tipagem dinâmica, complexidade ciclomática elevada e algoritmos pesados de processamento de dados.*

 21. **python/cpython**: O interpretador oficial do Python (C e Python). Histórico de décadas, massivo, excelente para testar regressões complexas.
 22. **pandas-dev/pandas**: Volume gigantesco de manipulação de matrizes. Ideal para capturar degradação de performance de memória. *(testado em AC-2; sem CVE indexado)*
 23. **scikit-learn/scikit-learn**: Padrão ouro em machine learning tradicional. Código limpo, mas matematicamente denso.
 24. **tensorflow/tensorflow**: C++ e Python. Um dos maiores repositórios do mundo. Se o seu SaaS escanear isso rápido, ele escaneia qualquer coisa.
 25. **pytorch/pytorch**: Semelhante ao TensorFlow, excelente para testar análise de bindings C++/Python e alocação de GPU.
 26. **fastapi/fastapi**: Uso intensivo de Pydantic e tipagem moderna. Perfeito para validar se o seu SaaS entende Type Hints. *(testado em AC-3: CVE-2021-32677)*
 27. **django/django**: O framework web clássico do Python. Histórico impecável de releases, Pull Requests detalhados e correções de segurança (CVEs). *(testado em AC-3: CVE-2024-53908)*
 28. **pallets/flask**: Microframework com decisões arquiteturais maduras e histórico de refatoração transparente. *(testado em AC-3: CVE-2023-30861)*
 29. **huggingface/transformers**: Mudanças de código em ritmo frenético. Excelente para testar como seu SaaS lida com obsolescência rápida de código.
 30. **ansible/ansible**: Automação de TI em larga escala. Excelente para testar análise sintática de módulos Python dinâmicos.
 31. **celery/celery**: Sistemas de filas assíncronas. Perfeito para caçar bugs de concorrência, deadlocks e race conditions. *(testado em AC-3: CVE-2021-23727)*
 32. **home-assistant/core**: Um dos maiores projetos de IoT em Python. Altamente modular, integra centenas de bibliotecas terceiras.
 33. **scipy/scipy**: Computação científica avançada. Teste severo para algoritmos numéricos de baixa performance.
 34. **boto3/boto3**: SDK da AWS para Python. Código gerado e atualizado constantemente, ideal para testar varredura de interfaces gigantescas.
 35. **apache/airflow**: Orquestrador de workflows massivo. Ótimo para analisar degradação em DAGs e agendamentos.
 36. **saltstack/salt**: Gerenciamento de infraestrutura. Histórico complexo com vulnerabilidades críticas de bypass já corrigidas no passado.
 37. **scrapy/scrapy**: Framework de web scraping. Ótimo para testar análise de vazamento de memória em loops assíncronos. *(testado em AC-3: CVE-2022-0577)*
 38. **psf/requests**: O padrão de requisições HTTP. Histórico focado em estabilidade de API e tratamento de exceções edge-case. *(testado em AC-3: CVE-2024-47081, CVE-2023-32681, CVE-2024-35195)*
 39. **SQLAlchemy/sqlalchemy**: ORM massivo e complexo. Excelente para testar geradores de queries e degradação em conexões de banco de dados.
 40. **localstack/localstack**: Emulação de nuvem AWS em Python. Código denso com simulação de múltiplos serviços.

### 🐹 3. Ecossistema Go (Sistemas Distribuídos e Concorrência Nativa)
*Essenciais para testar a capacidade do seu SaaS de rastrear vazamento de Goroutines, problemas de concorrência e gerenciamento de memória em microsserviços.*

 41. **kubernetes/kubernetes**: O colosso do ecossistema cloud-native. Indispensável para testes de estresse de velocidade de escaneamento em Go.
 42. **moby/moby**: O motor por trás do Docker. Histórico riquíssimo sobre isolamento de container e chamadas de sistema (syscalls).
 43. **hashicorp/terraform**: Infraestrutura como Código. Excelente para testar o parseamento de grafos de recursos e estados.
 44. **hashicorp/vault**: Focado em segurança extrema. Ideal para validar se o seu SaaS detecta vulnerabilidades de criptografia e vazamento de segredos.
 45. **prometheus/prometheus**: Banco de dados de séries temporais. Perfeito para caçar bugs de performance de escrita/leitura.
 46. **etcd-io/etcd**: Armazenamento distribuído de chave-valor. Excelente para testar consistência lógica e concorrência estrita (Raft).
 47. **istio/istio**: Service mesh massivo. Desafio gigante de arquitetura distribuída e configuração para qualquer analisador de código.
 48. **cockroachdb/cockroach**: Banco de dados SQL distribuído escrito em Go. Código gigantesco, altamente técnico e focado em resiliência.
 49. **caddyserver/caddy**: Servidor web moderno. Ótimo para testar concorrência HTTP/3 e recarga dinâmica de configurações.
 50. **gin-gonic/gin**: Framework web focado em performance. Histórico limpo, excelente para validar falsos positivos em APIs Go.
 51. **syncthing/syncthing**: Sincronização de arquivos P2P. Ótimo para testar lógica de IO de disco e rede.
 52. **rancher/rancher**: Gerenciador de clusters Kubernetes. Grande volume de regras de negócio e integrações de API.
 53. **influxdata/influxdb**: Banco de dados de alta volumetria. Excelente para avaliar como seu SaaS lida com refatorações estruturais massivas (Go para Rust no histórico).
 54. **argoproj/argo-cd**: Ferramenta GitOps de alta adoção corporativa. Ótimo para validar segurança em pipelines de entrega contínua.
 55. **gohugoio/hugo**: Gerador de sites estáticos ultraveloz. Excelente para testar o parseamento de arquivos template e strings em lote.

*(`golang/go` em si — testado em AD: CVE-2023-29404 — não estava na lista numerada original, mas foi o caso usado na AD por já ter um CVE bem documentado e fácil de resolver via API.)*

### 🦀 4. Ecossistema Rust (Segurança de Memória e Baixo Nível)
*Para testar se o seu analisador consegue processar macros complexas, tipagem estrita e inferir gargalos lógicos onde o compilador do Rust não alcança (lógica de negócios).*

 56. **rust-lang/rust**: O próprio compilador e biblioteca padrão. Um dos repositórios mais complexos e densos da atualidade.
 57. **tokio-rs/tokio**: A espinha dorsal do ecossistema assíncrono em Rust. Perfeito para testar análise de concorrência avançada.
 58. **alacritty/alacritty**: Emulador de terminal acelerado por GPU. Ótimo para testar código Rust focado em performance gráfica direta.
 59. **serde-rs/serde**: Framework de serialização/deserialização baseado em macros fortes. Desafio clássico para engines de AST.
 60. **nushell (configuration-as-code / nushell)**: Um shell moderno escrito em Rust com código em rápida expansão e refatoração ativa.
 61. **tikv/tikv**: Banco de dados KV distribuído transacional. Engenharia de baixíssimo nível e alta performance.
 62. **diesel-rs/diesel**: ORM estrito e seguro para Rust. Excelente para testar inferência de tipos complexos em tempo de compilação.
 63. **swc-project/swc**: Plataforma de compilação JS/TS escrita em Rust. Extremamente veloz, ótimo teste de concorrência.
 64. **actix/actix-web**: Um dos frameworks web mais rápidos do planeta. Histórico famoso de discussões técnicas sobre o uso de blocos unsafe.
 65. **tauri-apps/tauri**: Alternativa ao Electron (Rust + Webview). Ótimo para testar segurança na ponte de comunicação IPC entre front e back.

*(`rust-lang/regex` — testado em AD: CVE-2022-24713 — não estava na lista numerada original, mas foi escolhido por ter o CVE de ReDoS mais documentado e ter revelado o bug do `RustAdapter`.)*

### ☕ 5. Ecossistema Java / Kotlin (Arquiteturas Corporativas Clássicas)
*Ideais para testar escaneamento de padrões corporativos, injeção de dependências pesada, acoplamento estrutural e o clássico "Spaghetti Enterprise Code".*

 66. **spring-projects/spring-boot**: O framework Java mais utilizado no mundo. Indispensável para validar se o seu SaaS entende injeção de dependências e anotações complexas.
 67. **spring-projects/spring-framework**: A base do ecossistema Spring. Décadas de histórico de commits e evoluções arquiteturais. *(testado em AD: CVE-2022-22965/Spring4Shell)*
 68. **apache/commons-lang**: Biblioteca utilitária clássica. Excelente para testar a detecção de bugs lógicos de baixo nível em manipulação de objetos e strings.
 69. **apache/flink**: Processamento de stream de dados em larga escala. Código massivo focado em computação distribuída na JVM.
 70. **apache/kafka**: Inicialmente Scala/Java, hoje majoritariamente Java. Um dos sistemas de mensageria mais críticos do mundo. Ótimo teste para degradação de IO.
 71. **elastic/elasticsearch**: Mecanismo de busca massivo em Java. Altíssima complexidade de threads, alocação de memória e heap da JVM.
 72. **netty/netty**: Framework de rede assíncrono conduzido por eventos. Engenharia de alto nível para IO de rede.
 73. **redisson/redisson**: Cliente Redis para Java. Excelente para validar o tratamento de concorrência e travas distribuídas (locks).
 74. **google/guava**: Bibliotecas principais do Google para Java. Referência absoluta em design de código e otimização. **(reservado para teste de falsos positivos — ver dicas abaixo)**
 75. **JetBrains/kotlin**: O próprio compilador e ecossistema da linguagem Kotlin. Massivo e extremamente bem documentado.

### 🛠️ 6. Ecossistema C / C++ (Sistemas Operacionais, Infraestrutura Básica e Bancos de Dados)
*Indispensáveis para avaliar se o seu SaaS consegue capturar bugs críticos de gerenciamento manual de memória (Buffer Overflow, Use-After-Free, Race Conditions tradicionais).*

 76. **torvalds/linux**: O Kernel do Linux. O teste definitivo de escala e velocidade mundial. Se o seu SaaS indexar o Kernel do Linux sem travar, sua arquitetura de filas é sólida.
 77. **postgres/postgres**: O banco de dados relacional mais robusto do mundo. Histórico cirúrgico de correção de bugs de concorrência e escrita em disco.
 78. **antirez/redis**: Escrito em C limpo e minimalista. Excelente para testar detecção de vazamentos em estruturas de dados single-thread.
 79. **curl/curl**: Código C hiper-otimizado que roda em bilhões de dispositivos. Histórico público transparente de todas as falhas de segurança já encontradas (ótimo para testes de regressão de vulnerabilidades). *(testado em AD: CVE-2023-38545)*
 80. **ffmpeg/ffmpeg**: Processamento multimídia em C. Extremamente complexo, cheio de otimizações assembly. Desafio brutal para análise de fluxo de dados.
 81. **git/git**: O próprio motor do Git. Código focado em performance de sistema de arquivos e manipulação de hashes.
 82. **opencv/opencv**: Visão computacional massiva em C++. Excelente para testar alocação de matrizes gráficas e vazamento de ponteiros.
 83. **sqlite/sqlite**: (Espelho no GitHub). O banco de dados mais replicado do mundo. Famoso por sua cobertura de testes de 100%. Excelente para testar se seu SaaS gera falsos positivos em códigos ultra-estáveis. **(reservado para teste de falsos positivos)**
 84. **apache/httpd**: O servidor web Apache. Código legado misturado com atualizações modernas, ótimo para avaliar análise de código antigo.
 85. **wireshark/wireshark**: Analisador de pacotes de rede em C. Histórico vasto de correções de parsing de protocolos (vulneráveis a estouros de pilha).

### 🐘 7. Ecossistema PHP / Ruby / C# / Mobile
*Para garantir a cobertura poliglota do seu SaaS, avaliando desde ORMs clássicos até o gerenciamento de estados em plataformas móveis.*

 86. **laravel/laravel** (e laravel/framework): O padrão ouro em documentação PHP. Excelente para testar rotas e detecção de SQL Injection.
 87. **rails/rails**: O gigante do Ruby. Histórico de quase duas décadas de convenções de código sobre configuração.
 88. **dotnet/runtime**: O core do ecossistema .NET (C#). Repositório gigantesco, corporativo e com gerência estrita de bugs.
 89. **dotnet/roslyn**: O compilador do C# escrito em C#. Excelente para testar analisadores estáticos que mimetizam compiladores.
 90. **flutter/flutter**: Dart/C++. O maior repositório de ecossistema mobile. Excelente para testar análise de árvores de renderização (UI).
 91. **wordpress/wordpress**: (Espelho). A base de código PHP mais difundida do planeta. Excelente para testar detecção de código legado perigoso e padrões antiquados de segurança.
 92. **php/php-src**: O core do próprio interpretador PHP em C. Histórico denso focado em gerenciamento de memória interna da linguagem.
 93. **jekyll/jekyll**: Ruby. Gerador estático estável com histórico muito claro de transição de dependências.
 94. **Signal/Signal-Android**: Repositório focado em segurança de ponta a ponta. Excelente para caçar bugs em implementações criptográficas móveis.
 95. **shadowsocks/shadowsocks-windows**: C#. Excelente para verificar segurança de rede e tratamento de tunelamento criptografado.

### 🏗️ 8. Repositórios de Grande Escala Focados em Infraestrutura de Dados e Cloud
*Sistemas que misturam orquestração complexa com pipelines críticos de dados, ideais para testar "Architectural Decay" (degradação arquitetural).*

 96. **apache/spark**: Scala e Java. Sistema massivo de processamento de dados distribuídos. Perfeito para capturar bugs em lógica de lazy evaluation.
 97. **hashicorp/nomad**: Alternativa ao Kubernetes escrita em Go. Focado em agendamento de micro-tarefas e clusters em escala.
 98. **ceph/ceph**: Sistema de armazenamento distribuído massivo escrito em C++ e Python. Código de altíssima complexidade de rede e hardware.
 99. **trinodb/trino** (antigo PrestoSQL): Motor de query SQL distribuído massivo em Java, focado em Big Data e execução concorrente em memória.
 100. **clickhouse/clickhouse**: Banco de dados analítico (OLAP) em C++. Um monstro em termos de performance de leitura e paralelismo estrutural.

---

### 💡 Dica de Estratégia de Teste do usuário (orienta a metodologia do loop AE)

 1. **Teste de Velocidade Pura (Throughput)**: Monitorar uso de CPU/Memória do UCO Sensor enquanto monta a árvore sintática (AST) dos repositórios gigantes (linux, kubernetes, tensorflow, vscode, elasticsearch).
 2. **Teste de Precisão de Bugs Lógicos**: Usar `curl/curl` ou `django/django` (e por extensão qualquer repo da lista) voltando o histórico do Git para tags antigas com CVEs conhecidos, e ver se o UCO Sensor consegue apontá-los de forma preditiva. **Esta é exatamente a metodologia `cve_diff_check.py` já em uso desde AC-3/AD.**
 3. **Teste de Falsos Positivos**: Executar o escaneador em `sqlite/sqlite` ou `google/guava` — código de cobertura de teste cirúrgica e padrões de qualidade altíssimos. Qualquer achado CRITICAL/HIGH ali tem alta probabilidade de ser falso positivo do motor. **Ainda não executado em nenhum sprint até agora — abre o Eixo 3 do loop AE (ver `inventario.md` §Sprint AE).**
