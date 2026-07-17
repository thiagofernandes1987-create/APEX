# AM — Varredura SCA (OSV-Scanner) contra Manifestos Reais da Lista Master de 100

Resposta direta ao pedido: *"continuar com o teste nos 100 repositórios,
agora utilizando a ponte com o SCA"*. Eixo de teste **novo e
complementar** ao CVE-anchored diff (SAST): em vez de buscar um único
CVE documentado e comparar o código antes/depois, esta varredura busca
o **manifesto real de dependências** (lockfile/`go.mod`/`pom.xml`/etc.)
de cada repositório na branch principal atual e roda o `OSVScannerBridge`
(`sast/sca_bridge.py`, M9.1) contra ele — reportando TODAS as
dependências vulneráveis conhecidas hoje, não apenas uma.

## Metodologia

1. Para cada repositório-alvo, verificar via GitHub Contents API qual
   manifesto de dependências existe na raiz/caminho conhecido (`curl`
   HTTP 200 antes de tentar).
2. Buscar o conteúdo real (decodificado de base64) e salvar com o nome
   de arquivo correto (o OSV-Scanner identifica o ecossistema pelo
   nome do arquivo).
3. Rodar `OSVScannerBridge.scan_manifest()` (modo offline, DB do OSV.dev
   via Google Cloud Storage) e registrar contagem de findings por
   severidade.

Script: `/tmp/.../scratchpad/sca_repo_sweep.py` (não versionado —
ferramenta de execução, não produto).

## Resultado (11 repositórios tentados, 9 com scan bem-sucedido)

| # lista master | Repo | Categoria | Manifesto | Findings | Severidade | Rating |
|---|---|---|---|---|---|---|
| #96 | `apache/spark` | Infra dados/cloud | `pom.xml` | 0 | — | A |
| #97 | `hashicorp/nomad` | Infra dados/cloud | `go.mod` | 2 | 2 MEDIUM | B |
| #99 | `trinodb/trino` | Infra dados/cloud | `pom.xml` | — | **scan falhou** | — |
| #43 | `hashicorp/terraform` | Go | `go.mod` | 0 | — | A |
| #44 | `hashicorp/vault` | Go | `go.mod` | 9 | 4 HIGH, 5 MEDIUM | D |
| #45 | `prometheus/prometheus` | Go | `go.mod` | 2 | 2 MEDIUM | B |
| #61 | `tikv/tikv` | Rust | `Cargo.lock` | 33 | 7 HIGH, 25 MEDIUM, 1 LOW | D |
| #87 | `rails/rails` | PHP/Ruby/C#/Mobile | `Gemfile.lock` | 61 | 1 CRITICAL, 19 HIGH, 26 MEDIUM, 15 LOW | E |
| #72 | `netty/netty` | Java/Kotlin | `pom.xml` | — | **scan falhou** | — |
| #31 | `celery/celery` | Python | `requirements/default.txt` | 0 | — | A |
| #11 | `axios/axios` | JS/TS | `package-lock.json` | 1 | 1 HIGH | C |

### Destaques concretos (não inventados — saída real do OSV-Scanner)

- **`hashicorp/vault`** (#44): 4 findings HIGH em dependências
  `docker/cli`/`docker/docker` vendorizadas (CVE-2025-15558,
  CVE-2026-34040/42306/41567) — preocupante por se tratar de um cofre
  de segredos.
- **`tikv/tikv`** (#61): 5 findings HIGH na mesma família CVE
  (`openssl@0.10.73`, vários CVEs de 2026) — uma única dependência
  desatualizada concentrando múltiplas vulnerabilidades.
- **`rails/rails`** (#87): pior resultado do lote — 1 CRITICAL
  (`rack-session` CVE-2026-39324) + 19 HIGH, rating E. Importante: isto
  reflete o `Gemfile.lock` usado para DESENVOLVER o próprio Rails (não
  o que uma aplicação Rails em produção usaria necessariamente), então
  não é um veredito sobre a segurança do framework em si.
- **`apache/spark`**, **`hashicorp/terraform`**, **`celery/celery`**:
  limpos (rating A) — confirma que o motor não está gerando ruído
  indiscriminado; quando o manifesto real não tem dependência vulnerável
  conhecida, o `OSVScannerBridge` reporta 0 findings corretamente.

### Falhas (documentadas, não escondidas)

`trinodb/trino` e `netty/netty`: ambos têm `pom.xml` na raiz, mas são
POMs **agregadores/parent** (listam `<modules>`, não
`<dependencies>` diretas resolvíveis) — o OSV-Scanner extrai 0 pacotes
e sai com status "No package sources found". Não é um bug do
`sca_bridge.py`; é uma limitação real de escanear só o POM raiz de
projetos Maven multi-módulo sem descer aos POMs dos submódulos. Não
contabilizado como cobertura "ok" — registrado como tentativa sem
sucesso.

## Cobertura agregada após esta rodada

Repositórios numerados da lista master **tocados nesta rodada com
sucesso** (independente do eixo SAST anterior): #96, #97, #43, #44,
#45, #61. Destes, **#96, #97, #43, #44, #45, #61 são adições novas**
(nenhum tinha sido tocado em nenhum sprint anterior) — categoria
"Infra de dados/cloud" sai de 0/5 para **2/5** (spark + nomad; trino
tentado sem sucesso), categoria Go sai de 2/15 para **4/15** (+terraform,
+vault, +prometheus), categoria Rust sai de 1/10 para **2/10** (+tikv).

#11 (axios), #31 (celery), #72 (netty), #87 (rails) já tinham caso
SAST CVE-anchorado de sprints anteriores — esta rodada adiciona uma
**segunda dimensão de evidência** (exposição real de dependências) aos
mesmos repositórios, não um repositório novo.
