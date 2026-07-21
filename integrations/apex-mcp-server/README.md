# APEX MCP Server

Expõe o kernel APEX (`apex-method/`) como ferramentas MCP via stdio — **stdlib-only,
zero dependências**. Qualquer cliente MCP (Claude Code, IDEs, outros agentes) passa a
consultar a memória, a taxonomia e o cache do APEX, e a **equipar/desequipar skills**
nos agentes com a mesma governança do kernel.

## Instalação (Claude Code)

```bash
claude mcp add apex -- python3 /caminho/para/APEX/integrations/apex-mcp-server/server.py
```

## Ferramentas

| Tool | Tipo | O que faz |
|---|---|---|
| `apex_classify` | leitura | Facets canônicos (domain/subdomain/intent/platform, PT+EN) |
| `apex_triage` | leitura | Modo de operação recomendado + razões (token economy) |
| `apex_resolution_check` | leitura | Cache de resolução híbrido (tier `prior`/`facet`) |
| `apex_recall` | leitura | Busca semântica na memória persistente |
| `apex_worked_for` | leitura | Skills que já resolveram problema similar (prior validado) |
| `apex_route` | leitura | Melhor agente do roster (213 personas) para a tarefa |
| `apex_learning_best` | leitura | Melhores skills/personas por domínio (aprendizado durável) |
| `apex_trace_evaluate` | leitura | Avaliação de execução via event bus (latência, cache, validação) |
| `apex_equip` | **mutação** | Equipa skill em agente — **exige `approved: true` (H5)** |
| `apex_unequip` | **mutação** | Desequipa skill — **exige `approved: true` (H5)** |
| `apex_record_outcome` | **mutação** | Registra resultado validado — **exige `approved: true`** |

## Governança

O gate H5 do APEX é preservado na borda: toda ferramenta de **mutação** retorna
`BLOCKED` sem `approved: true` explícito. A aprovação humana continua sendo a
fronteira real — o MCP não cria nenhum caminho novo de escrita que o kernel já
não governasse.

## Smoke test

```bash
python3 integrations/apex-mcp-server/test_server.py
```
