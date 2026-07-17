# APEX-R Scientific Core

Primeiro incremento executável do APEX-R: contratos auditáveis, catálogo M0–M11,
perfil pré-clínico PCL, macros de trabalho, banco SQLite e núcleos matemáticos iniciais.

As fórmulas e suas hipóteses são governadas pelo [registro normativo](FORMULAS.md). O
CausalDSM possui scaffold tipado para nós, hiperarestas, intervenções, regimes DAG/D-SCM
e papéis de otimização; propagação numérica continua bloqueada até validação das equações.

Este software ainda é de pesquisa. Um gate `PASSED` confirma somente a propriedade
matemática ou computacional declarada pelo próprio gate; não comprova eficácia, segurança,
causalidade biológica, validade clínica nem adequação regulatória.

## Estado dos módulos

- Ativos: M0 (identificabilidade linear local), M1 (proveniência), M2 (afinidade/termodinâmica/calibração), M3
  (Windkessel 2 elementos) e M4 (balanço de massa PBPK).
- Com contrato inicial: M10, M11 e PCL.
- Planejados: M2.5, M5A, M5B, M6, M7, M8 e M9.

O catálogo não mascara lacunas: macros que dependem de módulos ainda não ativos retornam
`BLOCKED`, com os módulos faltantes listados.

## Execução local

O núcleo não exige dependências externas. A partir deste diretório:

```powershell
$env:PYTHONPATH = "src"
python -m apex_r modules list
python -m apex_r formulas list
python -m apex_r validate dsm --input .\examples\causal_dsm.json
python -m apex_r macros list
python -m apex_r macros check full_pipeline
python -m apex_r macros run molecular_to_pbpk --input .\examples\molecular_to_pbpk.json --db .\data\apex-r.sqlite3
python -m apex_r validate affinity --kd 1e-9 --temperature 298.15
python -m apex_r validate design --matrix "[[1,0],[1,1],[1,2]]"
python -m apex_r validate hemodynamics --flow 5 --resistance 2 --compliance 1
python -m apex_r validate pbpk --amounts "[100,20]" --transfers "[[0,0.2],[0.1,0]]"
python -m apex_r db init .\data\apex-r.sqlite3
python -m unittest discover -s tests -v
```

Para instalar o comando `apex-r` em um ambiente virtual:

```powershell
python -m pip install -e .
apex-r modules list
```

## Macros iniciais

| Macro | Finalidade |
|---|---|
| `molecular_to_pbpk` | Proveniência → afinidade → identificabilidade → PBPK → validação |
| `coefficient_validation` | Estimar e validar coeficientes com versão e evidência |
| `preclinical_translation` | Mecanismo → exposição → efeito/risco → PCL → validação |
| `full_pipeline` | Mapa completo M0–M11, incluindo o perfil PCL |

As definições ficam em `macros/*.json`; JSON foi escolhido para manter a primeira versão
sem dependência obrigatória de parser YAML.

Na execução, cada seção do payload usa o ID do módulo. Todos os gates recebem o mesmo
`run_id`; se `--db` for informado, são gravados no histórico append-only. A macro para no
primeiro resultado diferente de `PASSED`.

## Governança de coeficientes

Cada coeficiente possui definição separada de suas estimativas. Uma estimativa registra
o `run_id`, método, hash do conjunto de dados, incerteza e metadados. Estimativas, gates e
eventos de auditoria são append-only no SQLite: correções geram um novo registro, nunca a
reescrita silenciosa do histórico.

Os documentos [INVENTARIO.md](INVENTARIO.md) e [SPEC.md](SPEC.md) são as fontes normativas
locais deste incremento.
