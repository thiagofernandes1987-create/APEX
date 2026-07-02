# Sprint BN — Expansão da detecção de fonte do motor de taint (M16)

> Objetivo do usuário: "ampliar o motor fluxo de dados/taint-tracking".
> Diagnóstico com dado real → correção real e testada, mantendo precisão.

## Diagnóstico (dado real, sem inventar)

Rodei o `TaintAnalyzer` existente num fluxo Flask canônico
(`request.args.get("cmd")` → `os.system("ls "+cmd)`):

| padrão de fonte | detectava antes? |
|---|---|
| `request.args["x"]` (subscript) | **sim** (sources=1, 2 caminhos) |
| `request.args.get("x")` (acessor) | **NÃO** (sources=0) ← padrão Flask/Django MAIS comum |
| `flask.request.args.get(...)` (cadeia c/ prefixo) | **NÃO** (sources=0) |
| `request.form.getlist(...)` / `request.get_json()` | **NÃO** |
| `input()`, `sys.argv[n]` | sim |

Ou seja: o motor tinha a máquina de propagação (TaintSet/paths) e o sink
(`os.system`), mas **perdia a maioria dos fluxos web reais** por não
reconhecer o método acessor `.get()` sobre um atributo-fonte, nem a cadeia
`flask.request.args`. Um avaliador de "vibe-coding" que não vê
`request.args.get()` é cego para o padrão de injeção web nº 1.

## Correção — M16 (`sast/taint_engine.py`)

1. **Método acessor sobre fonte:** `_SOURCE_ACCESSOR_METHODS` =
   `{get, getlist, getall, getvalue, getone, get_json, first, dict,
   to_dict, read}`. Quando chamados sobre um atributo-fonte
   (`request.args.get(...)`), o retorno é marcado tainted.
2. **Acessor direto no request:** `request.get_json()`/`get_data()` etc.
3. **Cadeia com prefixo:** `_attr_source_label` casa pelo **último segmento**
   do objeto (`flask.request` → `request`), tolerando o prefixo de módulo.
4. **Subscript de atributo-fonte:** `request.args["x"]` também via o mesmo
   helper (unifica o caminho).

### Resultado (revalidação, dado real)

| padrão | depois do M16 |
|---|---|
| `request.args.get("x")` | **sources=1, 2 caminhos** ✓ |
| `flask.request.args.get(...)` | detectado ✓ |
| `request.form.getlist(...)` / `request.get_json()` | detectado ✓ |
| `request.args["x"]` (regressão) | continua detectado ✓ |
| **`d.get("x")` num dict comum** | **NÃO é fonte** ✓ (sem FP) |

5 testes TX84 pinam o comportamento (incluindo o não-FP do `dict.get`).
Regressão **2410 verdes** (304 testes de taint verdes, nenhum quebrado).

## Impacto

O motor de taint agora enxerga o padrão de entrada web mais comum
(Flask/Werkzeug/Django/aiohttp: `.args.get`/`.form.getlist`/`.get_json`),
mantendo precisão. Isso amplia diretamente a capacidade de detecção
fonte→sink sem âncora de fix — o requisito central do avaliador de código
gerado por IA.

## Contorno de dados descoberto (desbloqueia o próximo passo)

O bloqueio da API de commits (403 → sem parent SHA) para rodar M12/taint nos
pares Python é **contornável por tags de release**: `raw.githubusercontent`
aceita tag, e confirmei que arquivos de versões antigas (`salt v3006.0`,
`django 4.2/5.0`, etc.) são acessíveis. A versão "vulnerável" passa a ser uma
tag anterior ao fix, e a "corrigida" o commit-fix.

## Checklist — evolução

- [x] **M16 — expansão de fonte do taint (acessores + cadeia)**, testado,
      sem FP *(esta sprint)*
- [x] Contorno de dados via tags de release confirmado
- [ ] Rodar taint before/after num par Python real (path-traversal/injection)
      via tags — validar "parou de disparar" no fluxo fonte→sink
- [ ] Ampliar sinks (subprocess.*, eval/exec, jinja render, cursor.execute
      já cobertos?) e sanitizers (shlex.quote, escape) — auditar cobertura
- [ ] Cobrir classes redis/ffmpeg/sqlite no M11 (widening/early-return/clamp)
- [ ] Taint inter-procedural via CFG do V4 (uses/defs) para fluxo entre funções
