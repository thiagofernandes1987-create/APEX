# Sprint BQ — FixSuggester (M18): o elo Sensor → UCO Core → patch (META C)

> META C da missão: *"UCO Core identifica o que falhou e o que corrigir"*.
> Dado um finding do Sensor, o Core emite o patch mínimo — e, para CVE
> conhecida, a sugestão **coincide com o fix real dos mantenedores**.

## O que faz (`sast/fix_suggester.py`)

- `suggest_for_guard(GuardFinding)` — usa a classe (GA01/GA02) e as variáveis
  que o M11 já extraiu (`needs_guard_on`) para propor o guard mínimo.
- `suggest_for_taint(flow)` — mapeia o `vuln_type` para a mitigação canônica
  (deser→json/safe_load, cmd→shlex/list-form, SQL→parametrizado, path→realpath…).
- `explains_real_fix(sug, fixed_source)` — valida a sugestão contra a versão
  corrigida real.

## Validação com dado real (php-src CVE-2019-11043)

| Passo | Resultado |
|---|---|
| SENSOR (M11) detecta | GA01 em **L1212** sobre `(pilen, slen)` |
| CORE sugere | guard **`pilen > slen`** |
| COINCIDE com o fix REAL? | **SIM** — os mantenedores adicionaram exatamente `pilen > slen` |

E na deserialização: o Core sugere `json.loads`/`safe_load`; o fix real
(json.loads) satisfaz. O loop **Sensor→Core→(confere com o mundo real)**
está fechado com dado verificável, sem fabricar.

5 testes TX86. Regressão 2419 verdes.

## Evolução das METAS
- [x] **META C (parcial): Core sugere patch por finding + coincide com fix real**
- [ ] META C (restante): aplicar o patch sugerido e re-scan → Sensor silencia
      (auto-fix + prova de não-regressão do APS via UCO V4)
- [ ] META A: precisão do M11 (site-aware/dataflow) — próximo
- [ ] META B: detecção sem-âncora multi-linguagem
- [ ] META D: weak_point_score (SA/HMC)
- [ ] META E: M12 nos ~40 pares via tags
- [ ] META F: camada APEX (IA/MCP)
