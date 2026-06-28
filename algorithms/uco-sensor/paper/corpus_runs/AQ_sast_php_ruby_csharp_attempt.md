# Sprint AQ — Tentativa de eixo SAST CVE-anchored para PHP/Ruby/C#/Mobile restantes

> Continuação direta de AO/AP. Objetivo: tentar fechar parte dos 6
> repositórios da categoria PHP/Ruby/C#/Mobile (86-95) ainda sem
> nenhum eixo de evidência (`dotnet/roslyn`, `WordPress/WordPress`,
> `php/php-src`, `jekyll/jekyll`, `signalapp/Signal-Android`,
> `shadowsocks/shadowsocks-windows`), usando a técnica de busca de
> commits via GitHub Search Commits API ancorada em CVE-ID, que teve
> sucesso em AP para 5 repositórios C/C++.

## Resultado: nenhum novo eixo confirmado

A busca por commits de fix referenciando CVE-ID retornou resultados
para apenas 2 dos 6 repositórios — e em ambos os casos a análise
mais rigorosa invalidou o resultado como "sucesso":

### `php/php-src` — CVE-2019-11043 (RCE via env_path_info underflow)

Commit de fix real localizado: `ab061f95ca966731b1c84cf5b7b20155c0a1c06a`
("Fix bug #78599 ... (CVE-2019-11043)"), pai
`fadd7f0f1e7a44d6209b5c5cf30870e4b73efa7d`. Arquivo modificado:
`sapi/fpm/fpm/fpm_main.c` (C puro, não PHP — `php-src` é majoritariamente
C). Patch real:

```c
-  path_info = env_path_info ? env_path_info + pilen - slen : NULL;
-  tflag = (orig_path_info != path_info);
+  path_info = (env_path_info && pilen > slen) ? env_path_info + pilen - slen : NULL;
+  tflag = path_info && (orig_path_info != path_info);
```

Rodando `lang_adapters.registry.get_registry().analyze()` (adapter C)
antes/depois: **delta = 0 em todos os 9 canais** (hamiltonian,
cyclomatic_complexity, lines_of_code, halstead_bugs,
syntactic_dead_code, duplicate_block_count, dsm_density,
dependency_instability, n_classes). O fix é uma correção de bounds-check
de uma linha (adiciona `pilen > slen` a uma condição existente) — não
altera a estrutura sintática do arquivo o suficiente para mover o
fingerprint espectral via adapter regex-based. Isto é consistente com a
limitação já documentada em `AK_fingerprint_corpus_validation.md`
(fingerprint puro captura estilo/estrutura, não semântica fina). **Não
conta como sucesso** — é um resultado nulo honesto, não um bug da ponte.

### `jekyll/jekyll` — candidato a CVE-2014-9490 (path traversal)

Único commit retornado pela busca por "path traversal":
`8ecd2d9218c4ea7e9e92b29e1169e989b9461a5f` ("Don't allow path traversal
or syntax overrides."), datado de 2014-01-12. Arquivo modificado:
`test/test_sass.rb` — **arquivo de teste apenas**, sem alteração de
código de produção. Mesmo padrão de falso-candidato já visto em AP com
`apache/httpd` (commit de teste, não o fix real). **Rejeitado** — não é
o fix de produção da CVE.

### Demais 4 repositórios — zero resultados

`dotnet/roslyn`, `WordPress/WordPress`, `signalapp/Signal-Android`,
`shadowsocks/shadowsocks-windows`: nenhum commit retornado para
CVE-IDs conhecidos associados a esses projetos (ou, no caso do
WordPress, porque os fixes reais acontecem via SVN — o mirror GitHub
não preserva referências de CVE em mensagens de commit). `Signal-Android`
e `shadowsocks-windows` retornaram apenas commits genéricos de
"security"/dependency-bump, sem relação com uma CVE específica
identificável.

## Conclusão

Esta avenida foi tentada de boa fé com a mesma metodologia que funcionou
em AP, mas **não produziu nenhum novo sucesso legítimo**. A cobertura
real permanece em **74/100** — sem alteração. Os 26/100 restantes
continuam genuinamente sem eixo de evidência, com as barreiras
estruturais já documentadas em AO/AP/AE permanecendo válidas. Não foi
feita nenhuma tentativa de inflar o número com resultados de delta=0
ou commits de teste — ambos os candidatos encontrados foram
explicitamente descartados após verificação.
