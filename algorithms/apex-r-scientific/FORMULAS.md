# Registro normativo de fórmulas APEX-R

## 1. Autoridade e precedência

Quando documentos divergirem, a implementação DEVE aplicar esta ordem:

1. `APEX_R_Documento_Tecnico_Consolidado_Corrigido.docx`;
2. resultados reproduzidos com código, ambiente, dados, splits, seeds e hashes;
3. `SPEC.md` e este registro, depois de conciliados com a fonte 1;
4. `Validação Matemática do Framework APEX.pdf`, como auditoria histórica;
5. o consolidado anterior e textos auxiliares, como material de contexto.

Consequentemente, não entram como verdades do sistema:

- `beta0=0,45` e `beta1=1,08` como calibração universal de docking;
- score de docking tratado diretamente como energia livre termodinâmica;
- `kappa(FIM)<10^4` como lei universal independente de escala e desenho;
- do-calculus estático aplicado a loops fisiológicos instantâneos;
- o valor Bliss `6,912` anteriormente apresentado;
- ganho de hipervolume sob ruído como prova isolada de robustez.

## 2. Contrato obrigatório de fórmula

Toda fórmula executável deve possuir:

- ID e versão estáveis;
- módulo proprietário;
- expressão canônica;
- definição e unidade de cada variável;
- pré-condições e domínio de aplicabilidade;
- fonte normativa e seção;
- implementação identificável;
- testes de propriedades e casos fechados;
- nível de evidência separado da condição `PASSED` de uma execução;
- artefato de validação externa, quando esse status for alegado.

Uma fórmula pode estar correta internamente e ainda não ter validade preditiva externa.
O sistema não promove `TESTED` para `EXTERNALLY_VALIDATED` automaticamente.

## 3. Estados de evidência

| Estado | Significado permitido |
|---|---|
| `PROVED` | Prova formal completa ou mecanizada revisável. |
| `TESTED` | Propriedades internas cobertas no domínio declarado. |
| `REPRODUCED` | Resultado numérico reproduzido com artefatos versionados. |
| `EXTERNALLY_VALIDATED` | Critério pré-especificado atingido em dados externos bloqueados. |
| `PRELIMINARY` | Implementação ou resultado exploratório. |
| `NOT_DEMONSTRATED` | Fórmula prevista, mas sem evidência suficiente para execução científica. |

O catálogo executável está em `apex_r.formula_registry` e pode ser consultado por:

```powershell
python -m apex_r formulas list
python -m apex_r formulas show M2.DELTA_G_FROM_KD
```

## 4. CausalDSM

O DSM não é somente uma matriz de adjacência. Ele deve representar um hipergrafo causal
multicamadas com nós tipados, hiperarestas, mecanismo, fórmula, parâmetros, evidência,
sinal e atraso.

Camadas normativas:

1. fármaco -> alvo;
2. alvo -> via;
3. via -> desfecho ou risco.

Há dois regimes semanticamente distintos:

- `STATIC_DAG`: acíclico, sem atraso e elegível a identificação por critérios de DAG;
- `DYNAMIC_DSCM`: admite feedback, mas arestas de retorno devem declarar atraso positivo
  e posteriormente possuir equações de estado, condições iniciais e solver validados.

Nós podem ser marcados como variável de decisão, objetivo ou restrição. Essa marcação liga
M2.5 a M7/M8, mas não autoriza a otimização antes que os outputs tenham unidade, orientação,
incerteza e critérios de segurança. Intervenções removem as arestas que entram no nó
intervencionado; uma intervenção estrutural não equivale automaticamente a efeito causal
identificado.

No incremento atual, o M2.5 valida topologia, camadas, ciclos, atrasos, referências de fórmula
e papéis de otimização. A previsão numérica permanece bloqueada até a implementação das
equações estruturais e a aprovação por M11.

