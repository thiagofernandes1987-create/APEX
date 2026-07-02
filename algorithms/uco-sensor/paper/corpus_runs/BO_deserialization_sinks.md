# Sprint BO — Sinks de deserialização insegura no motor de taint (M16.1)

Classe CWE-502 (deserialização insegura) presente no corpus (transformers-
style / pickle) que o motor de taint não modelava. Adicionados a
`_SINK_METHODS`: `pickle`/`cPickle`/`marshal`/`dill`.`load`/`loads`,
`yaml.load`, `torch.load`, `joblib.load` (SAST046).

## Validação before/after (dado real de padrão, sem inventar)

| fluxo | sink | taint_paths |
|---|---|---|
| `pickle.loads(request.data)` (VULN) | 1 | 2 (dispara) |
| `yaml.load(request.data)` (VULN) | 1 | 2 (dispara) |
| `json.loads(request.data)` (FIX típico) | 0 | 0 (**parou de disparar**) |

O par pickle→json é o "parou de disparar" fiel da classe: o fix comum
(trocar `pickle`/`yaml.load` por `json.loads`/`yaml.safe_load`) elimina o
caminho fonte→sink. 4 testes TX85. Combinado com o M16 (Sprint BN, fontes
`request.args.get`), o motor agora cobre injeção web + deserialização.

## Checklist — evolução
- [x] M16 fontes acessoras (request.args.get / cadeia) — BN
- [x] **M16.1 sinks de deserialização (pickle/yaml/torch/marshal/dill/joblib)**
- [x] Auditoria de sinks (SQL/cmd/SSTI/eval/open/deserialização) e sanitizers
- [ ] Modelar fonte "arquivo baixado/remoto" p/ casar a CVE exata do transformers
- [ ] Cobrir classes redis/ffmpeg/sqlite no M11 (widening/early-return/clamp)
- [ ] Taint inter-procedural via CFG do V4 (uses/defs)
