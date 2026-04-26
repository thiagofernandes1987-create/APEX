# UCO-Sensor — CHANGELOG

Todas as mudanças notáveis são documentadas aqui.  
Formato: [Semantic Versioning](https://semver.org/) | Convenção: [Keep a Changelog](https://keepachangelog.com/)

---

## [2.0.0] — 2026-04-26 — M6.2 MULTI-LANGUAGE SUPPORT (APEX SCIENTIFIC)

### Adicionado — M6.2 40 Language Adapters

**APEX SCIENTIFIC mode** | Diferencial: SonarQube OSS suporta ~30 linguagens; UCO-Sensor v2 entrega **40 adaptadores calibrados** com Hamiltonian, CC, ILR, DSM e dead-code por linguagem — superando a cobertura do SonarQube Community Edition.

#### Arquitetura

- **`lang_adapters/generic.py`** — `GenericRegexAdapter(LanguageAdapter)`: base universal
  - `_strip(source)` → strings → bloco → linha (evita falsos positivos CC/import dentro de literais)
  - `_compute_ilr(clean)` → window-scan de 20 linhas por loop infinito; fração sem escape = ILR
  - `_count_dead_code(clean)` → brace-depth tracking pós-`return/throw/exit`
  - `_classify(h, cc)` → CRITICAL / WARNING / STABLE (limiares H≥20/8, CC>20/10)
  - `_halstead_metrics(tokens, ops)` → (n1, n2, N1, N2) particionamento Halstead 1977
  - `_count_duplicates(source, prefix)` → clone density proxy — linhas repetidas ≥ 2×
  - Calibrado para ±15% de medições AST tree-sitter no corpus UCO-Sensor

#### Grupos de Adaptadores

- **`lang_adapters/c_family.py`** — C, C++, Objective-C
  - `CAdapter` (.c, .h): `#include`, typed functions, `struct/union/enum`
  - `CppAdapter` (.cpp, .cc, .cxx, .hpp, .hxx, .h++, .c++, .cp, .inl): `catch`, `co_await/co_yield`, namespace/template
  - `ObjectiveCAdapter` (.m, .mm): `@interface/@implementation`, `[-+] (type) method:` selectors

- **`lang_adapters/csharp.py`** — C# (.cs)
  - `foreach/when/??`, `global using`, `record`, access-modifier function patterns

- **`lang_adapters/rust.py`** — Rust (.rs)
  - `match =>` arms, `loop {}` ILR, `?` propagation, `pub/async/const/unsafe fn`

- **`lang_adapters/ruby.py`** — Ruby (.rb, .rake, .gemspec, .ru, .rbw)
  - `=begin/=end` block comments, `unless/until/rescue/ensure/when`, `.each/.map` iterators

- **`lang_adapters/swift.py`** — Swift (.swift)
  - `guard/where/if let`, `??` null-coalescing, `fatalError/preconditionFailure`, `actor`

- **`lang_adapters/kotlin.py`** — Kotlin (.kt, .kts)
  - `when` expressions, `?.` safe-call, `?:` Elvis, `data/sealed class`, `companion object`

- **`lang_adapters/php.py`** — PHP (.php, .php3–7, .phps, .phtml)
  - PHP-8 `match`, `??` null-coalescing, heredoc strings, `require_once/use`, `die`

- **`lang_adapters/scala.py`** — Scala + Groovy
  - `ScalaAdapter` (.scala, .sc, .sbt): triple-quoted, `s"..."` interpolation, `match/case`, `sealed/case class`
  - `GroovyAdapter` (.groovy, .gradle, .gvy, .gy): GString `"...$var"`, Elvis `?:`, safe navigation `?.`

- **`lang_adapters/scripting_langs.py`** — R, Shell, PowerShell, Lua, Perl, MATLAB (6 adapters)
  - `RAdapter` (.r/.R/.rmd/.Rmd/.rscript): `library()`/`require()`, `name <- function(`, R6Class, `repeat{}` ILR
  - `ShellAdapter` (.sh/.bash/.zsh/.ksh/.fish/.command): `[[`/`[` conditions, `source`/`.` imports, sem classes
  - `PowerShellAdapter` (.ps1/.psm1/.psd1/.pssc): `<# #>` block, `-and/-or`, `Import-Module`, case-insensitive
  - `LuaAdapter` (.lua): `--[[ ]]` block, `and/or`, `require()`, `while true do` ILR
  - `PerlAdapter` (.pl/.pm/.t/.cgi/.plx): POD `=begin/=cut`, `elsif/unless/until`, `sub name {`
  - `MatlabAdapter` (.matlab/.octave): `%{ %}` blocks, `function [out]=name(`, `parfor`, `while 1`

- **`lang_adapters/functional_langs.py`** — Haskell, Erlang, Elixir, F#, OCaml, Clojure (6 adapters)
  - `HaskellAdapter` (.hs/.lhs): `|` guards como CC, `--`/`{- -}`, `forever`/`fix` = ILR
  - `ErlangAdapter` (.erl/.hrl): `->` clause arrows, `andalso/orelse`, `receive` = ILR
  - `ElixirAdapter` (.ex/.exs): sigils `~r/.../`, `cond/with/receive`, `defmodule/defprotocol`
  - `FSharpAdapter` (.fs/.fsx/.fsi): `(* *)`, `|` arms (não `||` ou `|>`), `let rec/member/override`
  - `OCamlAdapter` (.ml/.mli): sem line comments, `(* *)`, `|` arms, `while true do` ILR
  - `ClojureAdapter` (.clj/.cljs/.cljc/.edn): `;`/`#_`, `(if/when/cond/loop...)`, `(defn...)`

- **`lang_adapters/modern_systems.py`** — Dart, Julia, Zig, Nim, Crystal, D (6 adapters)
  - `DartAdapter` (.dart): `??/?.`, `on/rethrow`, `import/export/part`, `mixin/extension/typedef`
  - `JuliaAdapter` (.jl): `#= =#` block, `elseif`, `using/import/include`, `mutable struct/abstract type`
  - `ZigAdapter` (.zig): sem block comments, `\\` multiline, `comptime/orelse/catch/try`, `@import()`
  - `NimAdapter` (.nim/.nims): `#[...]#`, `proc/func/method/iterator/macro/template`, `of` case arms
  - `CrystalAdapter` (.cr): Ruby-like, `select` channels, `loop do/loop {`, `lib/annotation`
  - `DAdapter` (.d/.di): `/+ +/` nestable, `foreach_reverse`, `scope(exit/failure/success)`, backtick strings

- **`lang_adapters/domain_langs.py`** — VB.NET, Assembly, COBOL, Fortran, Tcl, Solidity, HCL (7 adapters)
  - `VBNetAdapter` (.vb): `'` comments, `For Each/AndAlso/OrElse/Select Case`, `Sub/Function/Property`
  - `AssemblyAdapter` (.asm/.s/.S/.nasm/.nas): `jXX` branches, `cbz/cbnz` ARM, labels = funções, `section` = struct
  - `CobolAdapter` (.cob/.cbl/.cpy/.cobol): `*>` e col-7 `*`, `EVALUATE/WHEN/PERFORM/UNTIL`, `PERFORM FOREVER`
  - `FortranAdapter` (.f/.for/.f77-.f08): `.AND./.OR./.NOT./.EQV./.NEQV.`, `USE`, `SUBROUTINE/FUNCTION/PROGRAM`
  - `TclAdapter` (.tcl/.tk/.tclsh): `package require`, `proc`, `namespace eval`, `while {1}` ILR
  - `SolidityAdapter` (.sol): `///` NatSpec, `require/revert` como CC, `contract/interface/library`
  - `HCLAdapter` (.hcl/.tf/.tfvars): `count/for_each/for/dynamic`, `module/data` = imports, `resource/provider`

#### Registry

- **`lang_adapters/registry.py`** — REESCRITO para M6.2
  - `_EXT_MAP`: 140+ extensões → 40 classes de adaptadores
  - `_load_adapter_by_name(class_name)`: factory com lazy imports para todos os 40 adaptadores
  - `UCOBridgeRegistry.supported_languages()` → 41 linguagens (TypeScript listado separado de JavaScript)
  - `UCOBridgeRegistry.supported_extensions()` → 140+ extensões mapeadas
  - `reset_registry()`: helper para isolamento de testes

#### IncrementalScanner — extensões M6.2

- **`scan/incremental_scanner.py`** — `_SUPPORTED_EXT` expandido
  - Adicionadas 100+ extensões cobrindo todos os 40 adaptadores M6.2
  - Grupos: C/C++/ObjC, C#, Rust, Ruby, Swift, Kotlin, PHP, Scala/Groovy, R, Shell, PowerShell, Lua, Perl, MATLAB, Haskell, Erlang, Elixir, F#, OCaml, Clojure, Dart, Julia, Zig, Nim, Crystal, D, VB.NET, Assembly, COBOL, Fortran, Tcl, Solidity, HCL

#### Testes

- **`tests/test_marco_m10.py`** — 30 testes TL01–TL30 (210/210 acumulado M4–M10)
  - Group 1 — `GenericRegexAdapter` (TL01–TL05): empty, LOC, CC, strip, classify
  - Group 2 — C-family (TL06–TL10): C, C++, ObjC extensões; C# foreach/??
  - Group 3 — Rust/Swift/Kotlin/Scala/PHP (TL11–TL15): match arms, guard, when, extensões
  - Group 4 — Scripting (TL16–TL20): R library(), Shell [[, PS case-insensitive, Lua and/or, Perl sub
  - Group 5 — Functional (TL21–TL24): Haskell guards, Elixir defmodule, F# arms, Clojure defn
  - Group 6 — Modern systems (TL25–TL27): Dart ??, Zig comptime, Nim proc/elif
  - Group 7 — Registry (TL28–TL30): ≥36 linguagens, ≥100 extensões, dispatch por extensão

### Alterado

- **`lang_adapters/registry.py`**: completamente reescrito (substituiu stub de 6 linguagens)
- **`scan/incremental_scanner.py`**: `_SUPPORTED_EXT` expandido de 10 para 110+ extensões
- Versão bumped: 1.5.0 → **2.0.0** (major — cobertura de linguagens 6× maior)

---

## [1.5.0] — 2026-04-26 — M6.1 INCREMENTAL ANALYSIS ENGINE

### Adicionado — M6.1 IncrementalScanner

**APEX DEEP mode** | Diferencial: SonarQube incremental = enterprise-only; UCO-Sensor entrega grátis com Hamiltonian delta e detecção de regressão persistida.

- **`scan/incremental_scanner.py`** — motor de análise incremental
  - `ChangedFile(path, change_type, old_path, content)` — ADDED / MODIFIED / DELETED / RENAMED
  - `FileDelta` — comparação before/after de métricas por arquivo:
    - `old_hamiltonian`, `new_hamiltonian`, `delta_h`
    - `old_cc`, `new_cc`, `delta_cc`
    - `status_before`, `status_after`, `regression`, `scan_error`
    - `to_dict()` com rounding correto
  - `IncrementalScanResult` — resultado agregado da passagem incremental:
    - Contadores: `total_changed`, `added_count`, `modified_count`, `deleted_count`, `renamed_count`
    - `scanned_count`, `error_count`, `regressions`, `new_criticals`
    - `regressions_list()` — lista de `FileDelta` com `regression=True`
    - `new_criticals_list()` — arquivos que passaram para CRITICAL nesta passagem
    - `summary()` — string legível para CI logs
    - `to_dict()` — serialização completa (incluindo `file_deltas`)
  - `IncrementalScanner(root, store, commit_hash)`:
    - `scan_files(paths, commit_hash, base_commit)` — lê do disco, detecta ADDED vs MODIFIED via store
    - `scan_changed_files(changed_files, …)` — lista pré-construída de `ChangedFile`
    - `scan_git_diff(repo_path, base_commit, head_commit)` — `git diff --name-status`
    - `_baseline(path)` → `(h, cc, status)` da última snapshot no `SnapshotStore`
    - `_git_changed_files(repo, base, head)` — parser de saída git: A/M/D/R
  - **Detecção de regressão**: `delta_h > max(0.5, old_h * 0.05)` OR piora de status rank
  - Fallback seguro: git ausente → lista vazia; extensão não suportada → `scan_error`

- **`api/server.py`** — novo endpoint `POST /scan-incremental`
  - Modo `files`: aceita lista de `{"path", "content", "change_type"}` + `persist`, `root`
  - Modo `git_diff`: delega a `scan_git_diff()` com `repo_path`, `base_commit`, `head_commit`
  - `persist=False` → scanner usa `store=None` (sem escrita no DB)
  - Retorna `IncrementalScanResult.to_dict()` com regressions e new_criticals
  - Versão bumped: 1.4.0 → **1.5.0**

- **`tests/test_marco_m9.py`** — 30 testes TI01–TI30 (210/210 passing acumulado)
  - Group 1 — `ChangedFile` (TI01–TI03): construção, rename, conteúdo
  - Group 2 — `FileDelta` (TI04–TI07): defaults, to_dict, regression, DELETED
  - Group 3 — `IncrementalScanResult` (TI08–TI12): summary, regressions_list, new_criticals_list, to_dict, rounding
  - Group 4 — `scan_files()` (TI13–TI17): empty, ADDED, MODIFIED, DELETED, contadores múltiplos
  - Group 5 — `scan_changed_files()` (TI18–TI21): empty content, extensão insuportada, DELETED, Python válido
  - Group 6 — `_baseline()` (TI22–TI23): sem store, com history
  - Group 7 — `_git_changed_files()` (TI24–TI26): não-git, parse A/M/D/R, timeout
  - Group 8 — `handle_scan_incremental()` REST (TI27–TI30): 400 sem files, 200 files mode, git_diff mode mock, persist=False

---

## [1.4.0] — 2026-04-26 — M5.3 AI EXPLANATIONS VIA APEX ENGINEER

### Adicionado — M5.3 FixExplainer

- **`sensor_core/explainer.py`** — `FixExplainer` + `ExplanationReport`
  - `explain(autofix_result, module_id, forecast?, anomaly_type?, …)` → `ExplanationReport`
  - Auto-detecção de `anomaly_type` via `_infer_anomaly_type()`:
    1. Dominant transform aplicado pelo AutofixEngine (`DeadCodeRemover` → `DEAD_CODE_DRIFT`, etc.)
    2. Fallback para `DegradationForecast.risk_level` → tipo APEX correspondente
    3. Fallback final: `TECH_DEBT_ACCUMULATION`
  - `ExplanationReport` (13 campos + `to_dict()`):
    - `apex_prompt` — pronto para o agente APEX engineer (renderizado via `render_prompt()`)
    - `mode` — FAST | DEEP | RESEARCH determinado pelo template do anomaly_type
    - `agents` — lista de agentes APEX recomendados
    - `transforms_summary` — sumário do que o AutofixEngine já corrigiu
    - `transforms_auto_applied` — nomes únicos (dedup, order-preserving)
    - `remaining_transforms` — o que ainda precisa de intervenção manual/agente
    - `success_criteria` — critério de sucesso APEX para o tipo de anomalia
    - `risk_narrative` — narrativa derivada do `DegradationForecast` (slope, Hurst, advice)
    - `intervention_now` — True quando template exige ação imediata
    - `uco_channels` — canais UCO afetados
  - Enriquecimento automático de `delta_h` e `hurst` a partir do forecast quando não fornecidos
- **Integração completa M5.1 + M5.2 + M5.3**: Forecast → Autofix → Explain → APEX prompt

### Modo APEX utilizado: `DEEP`
  - Agentes: `["engineer", "architect", "critic"]`
  - Justificativa: síntese multi-camada (predictor + AST transforms + templates)

### Testes

- `tests/test_marco_m8.py` — 30 testes TE01-TE30, **30/30 PASS**
- Regressão: M1…M8 = **240/240 PASS**

---

## [1.3.0] — 2026-04-26 — M5.2 AUTOFIX ENGINE (AST TRANSFORMS)

### Adicionado — M5.2 AutofixEngine

- **`sensor_core/autofix/engine.py`** — `AutofixEngine` + `AutofixResult`
  - Pipeline configurável de 4 transforms aplicados em sequência
  - `apply(source)` → `AutofixResult` com `fixed_source`, `transforms_applied`, `is_valid_python`, `parse_error`, `changed`
  - `apply_named(source, names)` — aplica apenas transforms selecionados
  - Guarda-costas completo: parse error → original retornado; transform exception nunca quebra o pipeline
- **`sensor_core/autofix/transforms/dead_code.py`** — `DeadCodeRemover`
  - Remove statements após `return`/`raise`/`continue`/`break` em function bodies
  - Aplica recursivamente em branches `if`/`for`/`while`/`try`
- **`sensor_core/autofix/transforms/redundant_else.py`** — `RedundantElseRemover`
  - Guard clause pattern: `if x: return … else: …` → `if x: return …\n…`
  - Multi-pass até estabilidade; trata `raise` como terminador
- **`sensor_core/autofix/transforms/boolean_simplify.py`** — `BooleanSimplifier`
  - `x == True` → `x`, `x is True` → `x`
  - `x == False` → `not x`, `x is False` → `not x`
  - `x != True` → `not x`, `x is not False` → `x`
- **`sensor_core/autofix/transforms/unused_imports.py`** — `UnusedImportRemover`
  - Remove `import` e `from … import` cujos nomes não aparecem no AST
  - Preserva `from __future__ import`, star imports, `__all__`-exported names
  - Bail-out automático quando `getattr`/`eval`/`exec` presentes (dynamic access)
- **Pipeline order**: `UnusedImports → BooleanSimplify → RedundantElse → DeadCode`
  - Ordem garante que `RedundantElse` cria novos terminators antes de `DeadCode` varrer

### Testes

- `tests/test_marco_m7.py` — 30 testes TF01-TF30, **30/30 PASS**
- Regressão: M1…M7 = **210/210 PASS**

---

## [1.2.0] — 2026-04-26 — M6 PREDICTOR API + FLEET HEALTH ENGINE

### Adicionado — M6 Predictor API + AutoAnalyzer

- **`sensor_core/auto_analyzer.py`** — `AutoAnalyzer` + `FleetReport`
  - `analyze_module(module_id, window, horizon)` → `DegradationForecast` direto do store
  - `analyze_fleet(window, top_n, horizon)` → `FleetReport` com todos os módulos ordenados por risco
  - `FleetReport`: `total_modules`, `analysed_modules`, `risk_counts`, `critical_count`, `high_count`, `avg_confidence`, `most_at_risk`, `all_forecasts`, `summary()`
  - Ordenação: `_RISK_ORDER` (CRITICAL < HIGH < MEDIUM < LOW < STABLE), desempate por `slope_pct` decrescente
- **`api/server.py`** — 2 novos endpoints REST
  - `GET /predict?module=<id>&window=<n>&horizon=<h>` — forecast por módulo
  - `GET /predict/all?window=<n>&horizon=<h>&top_n=<k>` — fleet forecast completo
  - Versão bumped para `1.1.0`

### Testes

- `tests/test_marco_m6.py` — 30 testes TA01-TA30, **30/30 PASS**
- Regressão: M1 (30) + M2 (30) + M3 (30) + M4 (30) + M5 (30) + M6 (30) = **180/180 PASS**

---

## [1.1.0] — 2026-04-26 — M5 DEGRADATION PREDICTOR

### Adicionado — M5.1 DegradationPredictor

- **`sensor_core/predictor.py`** — `DegradationPredictor` com previsão combinada de dois sinais
- **Hurst Exponent** via Rescaled Range (R/S): H > 0.55 → persistente, H < 0.45 → auto-corretivo
- **OLS Slope** (% change per snapshot): slope positivo → Hamiltonian crescendo → degradação
- `DegradationForecast` dataclass com 13 campos + `to_dict()`
- Risk classification: `CRITICAL | HIGH | MEDIUM | LOW | STABLE` com amplificação por persistência
- `hurst_rs(series)` — estimador Hurst por análise R/S com OLS sobre log(R/S) ~ H·log(L)
- `_ols() / _r2()` — regressão linear + R² para projeção de tendência
- `confidence` — escala com `n_samples / 20 × R²`; `predicted_h` clampado em ≥ 0
- Fast-path para dados insuficientes (< 4 snapshots) → retorna `insufficient_data=True`

### Testes

- `tests/test_marco_m5.py` — 30 testes TP01-TP30, **30/30 PASS** (0 falhas na primeira execução)
- Regressão: M1 (30) + M2 (30) + M3 (30) + M4 (30) + M5 (30) = **150/150 PASS**

---

## [1.0.0] — 2026-04-26 — M4 WEB UI + SARIF + GITHUB ACTIONS + VS CODE

### Adicionado — M4.3 SARIF 2.1.0 Melhorado

- **`report/sarif.py`** — `SARIFBuilder` incremental: 22 regras (9 UCO + 13 SAST)
- Line/column reais em `physicalLocation.region`: `startLine` e `startColumn` (1-based)
- `add_sast_findings(uri, sast_result)` — mapeia `SASTFinding.line/col` para região SARIF
- `add_uco_findings_from_profiles(uri, fps)` — emite UCO001/UCO002 por função com CC/CogCC alto
- `add_uco_finding(...)` — finding UCO com `logicalLocations` (nome da função)
- CWE/OWASP tags em `rule.properties`; `fullDescription` e `help.markdown` por regra
- `/analyze-pr` refatorado para usar `SARIFBuilder` (elimina `startLine: 1` hardcoded)

### Adicionado — M4.4 GitHub Actions Native Action

- **`algorithms/uco-sensor/action.yml`** — composite action com 8 inputs + 7 outputs
- Inputs: `path`, `fail_on_critical`, `fail_on_gate_fail`, `gate_threshold`, `sarif_output`,
  `policy_file`, `max_files`, `include_tests`, `python_version`, `upload_sarif`
- Outputs: `uco_score`, `status`, `critical_count`, `warning_count`, `files_scanned`,
  `sarif_file`, `debt_minutes`
- **`ci/action_entrypoint.py`** — script standalone: RepoScanner + SARIFBuilder + SAST scan
- SARIF auto-upload via `github/codeql-action/upload-sarif@v3`
- GitHub Step Summary com tabela de métricas + emoji de status

### Adicionado — M4.1 Web Dashboard Temporal

- **`report/webui.py`** — `generate_dashboard_html()`: HTML standalone com Chart.js 4.x (CDN)
- 4 canvas: Hamiltonian temporal, CC temporal, Cognitive CC por módulo, SQALE debt por módulo
- Module health cards com status/trend icons, SQALE rating badges
- Top-issues table + SQALE debt budget progress bar
- Auto-refresh configável via `setInterval + fetch('/dashboard')`
- `GET /dashboard/ui` — endpoint no servidor stdlib servindo o dashboard completo
- Dados pré-embutidos como JSON (`INITIAL_DATA`) para renderização imediata

### Adicionado — M4.2 VS Code Extension

- **`vscode-extension/package.json`** — manifesto completo v1.0.0
  - Activation: Python, JS, TS, Java, Go
  - 4 commands: `analyze`, `showDashboard`, `analyzeWorkspace`, `configureServer`
  - 6 configurações: serverUrl, apiKey, analyzeOnSave, decorations, statusBarFormat, refresh
- **`vscode-extension/src/api.ts`** — `UCOClient` typed (fetch-based): 10 métodos API
- **`vscode-extension/src/extension.ts`** — extensão completa:
  - Status bar com H/status/SQALE rating
  - 3 decoration types: CRITICAL, HIGH, MEDIUM (coloured highlights + hover)
  - VS Code Diagnostics (Problems panel) com SAST + função profiles
  - WebView dashboard panel (HTML inline, sem servidor Node)
  - Auto-analyse on save; configureServer com ping test

### Modificado

- `api/server.py` — versão `1.0.0`; `/analyze-pr` usa `SARIFBuilder`; `GET /dashboard/ui`
- `pyproject.toml` — versão `1.0.0`; `webui = [fastapi, uvicorn]` optional dep; `ci*` package

### Testes

- `tests/test_marco_m4.py` — 30 testes TW01-TW30, **30/30 PASS** (0 falhas na primeira execução)
- Regressão: M1 (30) + M2 (30) + M3 (30) + M4 (30) = **120/120 PASS**

---

## [0.9.0] — 2026-04-25 — M3 SAST SECURITY RULES

### Adicionado — M3 SAST Security Rules

- **`sast/` package** — Static Application Security Testing engine com 13 regras de segurança
- **SAST001** (CWE-89, CRITICAL) — SQL Injection via `execute()` com string formatada ou concatenada
- **SAST002** (CWE-78, HIGH) — OS Command Injection via `os.system()` / `os.popen()` com argumento variável
- **SAST003** (CWE-95, HIGH) — Unsafe `eval()` / `exec()` com argumento não-literal
- **SAST004** (CWE-502, HIGH) — Pickle deserialization via `pickle.load()` / `pickle.loads()`
- **SAST005** (CWE-502, MEDIUM) — YAML unsafe load sem `Loader` contendo "safe"
- **SAST006** (CWE-327, MEDIUM) — Algoritmo de hash fraco: MD5, SHA1
- **SAST007** (CWE-338, MEDIUM) — Randomness insegura via módulo `random`
- **SAST008** (CWE-798, HIGH) — Segredo hardcoded: `password`, `api_key`, `token`, etc.; exclui placeholders (`CHANGEME`, `YOUR_`, etc.)
- **SAST009** (CWE-321, CRITICAL) — Chave privada PEM no código-fonte
- **SAST010** (CWE-489, MEDIUM) — Flask/app `debug=True` em produção
- **SAST011** (CWE-22, HIGH) — Path Traversal via `open()` com caminho variável
- **SAST012** (CWE-617, LOW) — `assert` usado para verificação de segurança
- **SAST013** (CWE-78, HIGH) — `subprocess` com `shell=True` + argumento não-literal
- **`SASTFinding` / `SASTResult`** — dataclasses com `to_dict()`, debt_minutes, security_rating A-E
- **Security rating** — CRITICAL→E, ≥2 HIGH→D, 1 HIGH→C, ≥2 MEDIUM→C, 1 MEDIUM→B, clean→A
- **SAST debt** — CRITICAL=240 min, HIGH=120 min, MEDIUM=60 min, LOW=30 min, INFO=5 min

### API — Novos endpoints (v0.9.0)

- `POST /sast` — scan de código-fonte; retorna findings + rating + debt
- `GET /sast/rules` — catálogo das 13 regras SAST
- `POST /analyze` — enriquecido com campo `"sast"` no payload de resposta

### Testes

- `tests/test_marco_m3.py` — 30 testes TS01-TS30, **30/30 PASS**
- Regressão: M1 (30/30) + M2 (30/30) mantidos intactos

---

## [0.8.0] — 2026-04-25 — M2 GOVERNANCE ENGINE

### Adicionado — M2 Governance Engine

**M2.1 — Policy Engine (`governance/policy_engine.py`)**
- `PolicyRule`: id, field, operator, threshold, severity (ERROR/WARNING/INFO)
- Operadores: `lte`, `gte`, `lt`, `gt`, `eq`, `neq`, `in`, `not_in`, `rating_lte`, `rating_gte`
- `evaluate_policy(metrics_dict, policy)` → `PolicyResult(passed, gate_score, grade, violations)`
- `load_default_policy()` — 11 regras default cobrindo CC, Cognitive CC, ILR, SQALE, DI, clones

**M2.2 — Quality Gate**
- `POST /gate` — analisa código e avalia política em uma chamada
- `gate_score` = 100 − Σ penalidades (ERROR −20, WARNING −10, INFO −2)
- `grade` A–F; `passed` = gate_score ≥ pass_threshold (default 70)
- Em caso de falha publica evento `UCO_GATE_FAILURE` ao APEX (quando apex_enabled=1)
- `gate_score_to_grade()`, `mv_to_metrics_dict()`

**M2.3 — Trend Engine (`governance/trend_engine.py`)**
- `analyze_trend(history, metric, window)` → `TrendAnalysis`
- Classificação: IMPROVING | STABLE | DEGRADING | VOLATILE | INSUFFICIENT_DATA
- Linear regression slope + R² — VOLATILE só quando R² < 0.6 AND CV > 30%
- `forecast_next` via extrapolação da regressão linear
- `analyze_module_trends()` — multi-metric para um módulo
- `overall_trend()` — direção agregada em múltiplas métricas

**M2.4 — Debt Budget**
- `track_debt_budget(module_debts, budget_minutes)` → `DebtBudget`
- Campos: `total_debt_minutes`, `remaining_minutes`, `over_budget`, `velocity_min_per_day`
- `days_until_exhausted` — previsão baseada na velocidade de acúmulo de dívida

**M2.5 + M2.6 — Dashboard + Trend API**
- `GET /trend?module=<id>&metric=<field>&window=<n>` — trend per-módulo
- `GET /dashboard` — snapshot de todos os módulos + debt budget + contagens por status/trend

### Testes
- `tests/test_marco_m2.py` — TG01–TG30 (30 testes)

### Resultados de Validação

| Conjunto | Resultado |
|----------|-----------|
| M2 Governance (30) | ✅ 30/30 |
| M1 Advanced (30)   | ✅ 30/30 |
| Calibration (25)   | ✅ 24/25 (1 skip) |
| Marco 6 (14)       | ✅ 14/14 |
| Marco 7 (16)       | ✅ 16/16 |
| Marco 8 (10)       | ✅ 10/10 |
| **Total acumulado** | **124/125** |

---

## [0.7.0] — 2026-04-25 — M1 ADVANCED METRICS

### Adicionado — M1 Advanced Quality Metrics

**M1.1 — Cognitive Complexity (Campbell 2018) (`advanced_metrics.py`)**
- `cognitive_complexity(source)` → `(total, per_function_dict)`
- Regras: +1 + depth para estruturas (if/for/while/except/with/lambda/fn aninhada)
- elif/else: +1 flat; BoolOp: +1 flat por sequência; ternary: +1 flat; recursão: +1 flat
- Nesting depth incrementa dentro de cada estrutura de controle

**M1.2 — SQALE Technical Debt (`advanced_metrics.py`)**
- `sqale_debt(metrics_dict, loc)` → `SQALEResult(debt_minutes, sqale_ratio, rating, breakdown)`
- Tabela de remediation costs: CC alto (30-60min), dead code (5min/linha), ILR (30min/loop), clones (30min/grupo), DI > 0.8 (480min)
- `sqale_ratio = debt / (loc × 30) × 100%`; Ratings A (≤5%) → E (>50%)

**M1.3 — Function-level Breakdown (`advanced_metrics.py`)**
- `build_function_profiles(source, fn_cc, fn_cog)` → `List[FunctionProfile]`
- `FunctionProfile`: name, loc, cc, cognitive_cc, halstead_volume, is_complex, debt_minutes, risk_level (LOW/MEDIUM/HIGH)

**M1.4 — Real Dependency Instability (`advanced_metrics.py`)**
- `ImportGraphAnalyzer` — compute real Martin DI via project-level import graph
- `DI(m) = Ce(m) / (Ca(m) + Ce(m))` contando apenas imports internos ao projeto

**M1.5 — Clone Detection Type-2 (`advanced_metrics.py`)**
- `detect_clones(source)` → número de grupos de clone
- Skeleton hash: normaliza `id`, `arg`, `attr`, `name`, `value` em AST dump
- Funções estruturalmente idênticas (renomeadas) são detectadas como Type-2 clones

**M1.6 — Ratings A–E (`advanced_metrics.py`)**
- `compute_ratings(uco_score, sqale_ratio_pct, ...)` → `Ratings(uco, sqale, reliability, security)`
- UCO: ≥80→A, ≥60→B, ≥40→C, ≥20→D, <20→E
- Reliability: penaliza ILR > 0.5 (−40pts) e CC > 20 (−20pts)
- Security: penaliza dead code ratio > 0.1 (−30pts) e Halstead bugs > 3 (−30pts)

**`AdvancedAnalyzer` — Orquestrador M1**
- `UCOBridge(mode="full")` injeta automaticamente todos os atributos M1 no MetricVector
- Dynamic attribute pattern: `mv.cognitive_complexity`, `mv.sqale_rating`, `mv.ratings`, `mv.function_profiles`, `mv.clone_count`, etc.
- `mode="fast"` não executa M1 (preserva performance de análises em lote)

**`/analyze` endpoint ampliado**
- Response inclui: `cognitive_complexity`, `cognitive_fn_max`, `sqale_debt_minutes`, `sqale_ratio`, `sqale_rating`, `clone_count`, `ratings`, `function_profiles`

### Testes
- `tests/test_marco_m1.py` — TM01–TM30 (30 testes)

### Resultados de Validação

| Conjunto | Resultado |
|----------|-----------|
| M1 Advanced (30) | ✅ 30/30 |
| Calibration (25) | ✅ 24/25 (1 skip) |
| Marco 6 (14) | ✅ 14/14 |
| Marco 7 (16) | ✅ 16/16 |
| Marco 8 (10) | ✅ 10/10 |
| **Total novo** | **94/95** |

---

## [0.6.0] — 2026-04-25 — M0 FOUNDATION (Bug Fix Sprint)

### Corrigido — M0.1 Métricas (9 bugs de medição)

**BUG-06 — Halstead overcounting ~10× (uco_bridge.py)**
- `visit_Attribute`: removido `self._operand(node.attr)` — `.attr` é operador, não operando. Reduz n2/N2 em ~50%.

**BUG-07 — CC undercount ~33% — padrões Python ausentes (uco_bridge.py)**
- Adicionados visitors: `visit_AsyncFor`, `visit_AsyncWith`, `visit_Lambda`, `visit_match_case`

**BUG-15 — CC comprehension inflation (uco_bridge.py)**
- `visit_comprehension`: `+= 1` → `+= len(node.ifs)`. `[x for x in lst]` → +0 CC.

**BUG-08 — ILR: recursão sem base case não detectada (uco_bridge.py)**
- `_check_recursion_risk()`: detecta `def f(n): return f(n-1)` sem `if` guard → ILR+1.

**BUG-13 — Dead code: constant-False branches ignoradas (uco_bridge.py)**
- `_scan_dead_code()`: detecta `if False:`, `while False:`, `if True: ... else: ...`

**BUG-01 — Java CC logical expressions (java.py)**
- `child_by_field_name("operator")` substitui text-scan para `&&`/`||`.

**BUG-17 — Java while(true) case-sensitive (java.py)**
- Normaliza whitespace+lowercase: `while ( true )` e `while(TRUE)` detectados.

**BUG-02 — JS ILR sempre zero (javascript.py)**
- `child_by_field_name("condition")` substitui `_get_child(node, "condition")` (type ≠ field).

**BUG-16 — Go ILR false negative: time.After/ctx.Done (golang.py)**
- `_has_channel_escape()`: detecta `<-` operator, `time.After`, `time.NewTimer`, `ctx.Done`.

### Corrigido — M0.2 Estabilidade e Segurança

**BUG-03 — Registry race condition (registry.py)**
- Double-checked locking em `get_registry()`.

**BUG-04 — SQLite thread-unsafe (snapshot_store.py)**
- Per-thread connections via `threading.local()` + `_get_conn()` helper.

**BUG-05 — Auth desabilitada por padrão (server.py)**
- `auth_enabled` lê `UCO_AUTH_ENABLED` env var. Produção requer `UCO_AUTH_ENABLED=1`.

**SEC-04 — APEX webhook recursão ilimitada (server.py)**
- Depth guard via `threading.local()`, limite de 3 níveis.

**T77 — Body size sem limite (server.py)**
- Rejeita `Content-Length > 10MB` com HTTP 413.

### Adicionado

- `tests/test_calibration.py` — 25 testes: CC, ILR, DeadCode, Halstead, radon comparison, performance
- `pyproject.toml`: versão 0.3.0 → 0.6.0; `python_files` inclui `test_calibration.py`

### Resultados de Validação

| Conjunto | Resultado |
|----------|-----------|
| M1 Core (27) | ✅ 27/27 |
| M2 Lang+Auth (48) | ✅ 48/48 |
| M3 APEX (16) | ✅ 16/16 |
| M4 Reports (35) | ✅ 35/35 |
| M5 Diff+Bench (15) | ✅ 15/15 |
| M6 Docker (14) | ✅ 14/14 |
| M7 Templates (16) | ✅ 16/16 |
| M8 Demo (10) | ✅ 10/10 |
| **Calibration (25)** | **✅ 24/25 (1 skip)** |
| **Total** | **205/206** |

---

## [0.5.0] — 2026-04-19 — ENTREGAR

### Adicionado — Marco 8 (M8 — ENTREGAR)
- `README.md` — documentação completa com badges, instalação, endpoints, APEX integration, tabela de marcos
- `demo/demo_full.py` — demo ponta a ponta em 8 steps: analyze → history → classify → diff → report → apex_event → apex_fix → status
- `tests/test_marco8.py` — T80–T89 (10 testes de integração E2E)
- `/docs` atualizado — 19 endpoints documentados
- Demo executa em < 2s; CHANGELOG cobre v0.1.0 → v0.5.0

---

## [0.4.0] — 2026-04-19 — AGIR

### Adicionado — Marco 7 (M7 — AGIR)
- `apex_integration/templates.py` — 8 templates de ação corretiva por tipo de erro UCO
  - TECH_DEBT_ACCUMULATION, AI_CODE_BOMB, GOD_CLASS_FORMATION
  - DEPENDENCY_CYCLE_INTRODUCTION, LOOP_RISK_INTRODUCTION
  - COGNITIVE_COMPLEXITY_EXPLOSION, DEAD_CODE_DRIFT, HALSTEAD_BUG_DENSITY
- `POST /apex/fix` — endpoint bidirecional: APEX envia `APEX_FIX_REQUEST`, sensor aplica transforms
  - Retorna: `fixed_code`, `h_before/after`, `delta_h`, `apex_prompt` contextualizado
  - `transforms_applied` detectados por comparação de métricas antes/depois
- `POST /apex/webhook` ampliado: `APEX_FIX_REQUEST` + `APEX_TEMPLATE_REQUEST`
- `render_prompt()` — preenchimento contextual do template com métricas reais
- `fix_action_for()` — retorna mode, agents, transforms por tipo
- Suite de testes T70–T7D (16 testes)

---

## [0.3.0] — 2026-04-19 — DISTRIBUIR

### Adicionado
- `pyproject.toml` — packaging PEP 517/518 com entry point `uco-sensor`
- `docker-compose.yml` — stack completa dev/prod com volume persistente e profile cron
- `CHANGELOG.md` — histórico de versões
- `ROADMAP.md` — plano de marcos PMI M4→M8

### Marco 6 (M6 — DISTRIBUIR)
- `pyproject.toml` com `[project.scripts] uco-sensor = "cli:main"`
- `docker-compose.yml` com service `uco-sensor` e `uco-cron` (profile)
- Dockerfile multi-stage existente validado (T65, T66)
- Suite de testes T60–T69: empacotamento, container, release artifacts

---

## [0.2.0] — 2026-04-19 — CALIBRAR

### Adicionado — Marco 5 (M5 — CALIBRAR)
- `POST /diff` — endpoint de comparação entre 2 commits
  - Retorna delta dos 9 canais UCO (Hamiltoniano, CC, ILR, DSM, ...)
  - Campo `regression` (bool) com threshold baseado em ΔH e ΔCC
  - `suggested_transforms`: lista de ações corretivas automáticas
  - `uco_score_before/after` e `score_delta`
  - `summary` legível: `"REGRESSÃO: ΔH=+3.2  ΔCC=+5  Score 72→45"`
- Benchmark confirmado: 20 arquivos < 5s
- Calibração: código saudável real → UCO Score ≥ 40
- Suite de testes T50–T5D (15 testes)

---

## [0.1.3] — 2026-04-19 — VISUALIZAR

### Adicionado — Marco 4 (M4 — VISUALIZAR)
- `GET /report?module=<id>` — HTML report standalone com:
  - Gauge SVG do UCO Score
  - Tabela de arquivos por status (CRITICAL/WARNING/STABLE)
  - Breakdown por linguagem
  - Sparklines de tendência
- `GET /badge?score=87&status=STABLE` — badge SVG estilo shields.io (público)
- `GET /badge?module=<id>` — badge gerado do histórico do módulo
- `report/html_report.py` — gerador HTML self-contained (zero deps externas)
- `report/badge.py` — badges SVG com paleta de cores por faixa de score
- `_send_html()` e `_send_svg()` no handler HTTP
- Suite de testes T40–T49 (35 testes)

---

## [0.1.2] — 2026-04-18 — CONECTAR

### Adicionado — Marco 3 (M3 — CONECTAR)
- `apex_integration/event_bus.py` — ApexEventBus com transportes: null, callback, file, webhook
- `apex_integration/connector.py` — ApexConnector com severity gate e SnapshotStore
- `GET /apex/status` — status da integração APEX
- `GET /apex/ping` — teste de conectividade bidirecional
- `POST /apex/webhook` — handshake bidirecional (ACK APEX_PING, APEX_RESCAN_REQUEST)
- `GET /anomalies` — lista anomalias persistidas
- Evento `UCO_ANOMALY_DETECTED` — publicado automaticamente em análise CRITICAL
- Suite de testes T30–T34 (16 testes)

---

## [0.1.1] — 2026-04-18 — EXPANDIR

### Adicionado — Marco 2 (M2 — EXPANDIR)
- `lang_adapters/` — registry multi-linguagem (Python, JS/TS, Java, Go)
- Auth/Billing: `POST /auth/keys`, `GET /auth/keys`, `DELETE /auth/keys`
- `POST /analyze-pr` — análise de PR com saída SARIF 2.1.0
- `ci/uco-pr-check.yml` — GitHub Actions Quality Gate
- `Dockerfile` multi-stage (Python 3.11-slim, usuário não-root)
- `requirements.txt` com numpy, scipy, PyWavelets, tree-sitter
- Suite de testes T10–T29 (20 testes)

---

## [0.1.0] — 2026-04-17 — ANALISAR

### Adicionado — Marco 1 (M1 — ANALISAR)
- `sensor_core/uco_bridge.py` — UCOBridge: extrai 9 canais do UCO v4
- `sensor_storage/snapshot_store.py` — SnapshotStore SQLite com baseline e z-score
- `api/server.py` — HTTP server stdlib-only (BaseHTTPRequestHandler)
  - `GET /health`, `GET /docs`, `GET /modules`, `GET /history`, `GET /baseline`
  - `POST /analyze`, `POST /repair`
- `POST /scan-repo` — RepoScanner batch
- FrequencyEngine integrado via `pipeline/` (frequency-engine)
- Gaps CSL: weighted_mean_freq (fw_shift), dual-confirmation, POST /repair
- Suite de testes T01–T08 (30 testes)

---

[Unreleased]: https://github.com/thiagofernandes1987-create/APEX/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/thiagofernandes1987-create/APEX/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/thiagofernandes1987-create/APEX/compare/v0.1.3...v0.2.0
[0.1.3]: https://github.com/thiagofernandes1987-create/APEX/compare/v0.1.2...v0.1.3
[0.1.2]: https://github.com/thiagofernandes1987-create/APEX/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/thiagofernandes1987-create/APEX/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/thiagofernandes1987-create/APEX/releases/tag/v0.1.0
