# APEX Repository Intake Workflow

**WHY**: Define o processo padronizado para integrar novos repositórios ao APEX.
**WHEN**: Sempre que o usuário enviar um novo repositório (ZIP, URL, ou pasta).
**HOW**: Pipeline de 5 estágios: Receber → Extrair → Catalogar → Converter → Indexar.

---

## Quando Ativar

Ativado quando o usuário:
- Envia arquivos ZIP (incluindo multi-part: `.001`, `.002`, ...)
- Menciona "repositório", "repo", "plugins", "skills" + pedir integração
- Diz "adicione isso ao APEX" ou "organize isso"

---

## Pipeline de Integração (5 Estágios)

### STAGE_1: RECEIVE — Receber e Montar

```
INPUT: arquivo(s) enviados pelo usuário

1a. SE multi-part ZIP (.001, .002, ...):
    - Montar com: python3 -c "
      parts = sorted(glob('Repo.zip.*'))
      with open('assembled.zip', 'wb') as out:
          for p in parts: out.write(open(p, 'rb').read())
      "
    - Verificar header: bytes[0:4] == b'PK\x03\x04' (magic ZIP)

1b. SE URL GitHub:
    - Usar trusted_domains para download via urllib.request
    - Verificar que URL está em apex_superrepo.trusted_domains

1c. SE pasta local:
    - Listar estrutura com os.walk()
    - Identificar repos por presença de README.md ou package.json ou *.md
```

### STAGE_2: EXTRACT — Extrair e Catalogar

```
2a. Listar conteúdo do ZIP:
    - zf.namelist() → identificar top-level directories (= repos)
    - Contar arquivos por repo para priorização

2b. Extrair SKILL.md files (seletivo, não extrair binários):
    - Padrões: SKILL.md, AGENT.md, ALGORITHM.md, plugin.json, README.md
    - Destino: /tmp/extracted_{timestamp}/

2c. Catalogar estrutura:
    - Para cada SKILL.md: ler frontmatter (name, description)
    - Para cada plugin.json: ler connectors, MCP tools
    - Produzir: catalog.json com todos os artefatos encontrados
```

### STAGE_3: ANALYZE — Análise e Classificação

```
3a. Classificar cada artefato:
    - Tipo: skill | agent | algorithm | plugin | mcp_server | documentation
    - Domínio: finance | engineering | legal | science | data | healthcare | ...
    - Qualidade: ADOPTED (oficial Anthropic) | CANDIDATE (partner/community)

3b. Detectar duplicatas:
    - Comparar skill_id com registry existente
    - SE duplicata: verificar se nova versão é superior (mais âncoras, melhor FMEA)

3c. Identificar cross-domain bridges:
    - Analisar descrições para referências a outros domínios
    - Exemplo: "DCF + WACC" → bridge para mathematics.financial_math
```

### STAGE_4: CONVERT — Converter para Formato APEX

```
Para cada SKILL.md original, gerar APEX-format com:
  
  FRONTMATTER obrigatório:
    skill_id: {domain.subdomain.skill_name}  # notação dot
    name: "{nome humano}"
    description: "{descrição original}"
    version: v00.33.0
    status: ADOPTED | CANDIDATE
    domain_path: {domain/subdomain/skill_name}
    anchors:  # extraídos de keywords da descrição
      - {keyword1}
      - {keyword2}
    source_repo: {nome do repo de origem}
    risk: safe | unknown | critical
    languages: [dsl]
    llm_compat: {claude: full, gpt4o: partial, ...}
    apex_version: v00.33.0

  BODY:
    - Preservar conteúdo original completo
    - Adicionar seção "## Diff History" no final

OUTPUT: skills/{domain}/{skill_name}/SKILL.md no APEX GitHub repo
```

### STAGE_5: INDEX — Atualizar INDEX.md e Anchors

```
5a. Atualizar INDEX.md:
    - Adicionar novo domínio em domain_map (se não existir)
    - Listar todos os skills do novo domínio com:
        skill_id, path, anchors[:4], status
    - Atualizar counter: "Skills registradas: N"

5b. Atualizar meta/anchors.yaml:
    - Adicionar todos os novos anchors à seção relevante
    - Criar grupo novo se domínio não existe
    - Atualizar anchor_lookup flat dict

5c. Push ao GitHub:
    - git add skills/ agents/ INDEX.md meta/anchors.yaml
    - git commit -m "feat: ingest {repo_name} — {N} skills, {M} anchors"
    - git push origin main
```

---

## Tabela de Priorização de Repos

| Tipo de Repo | Prioridade | Ação |
|---|---|---|
| Oficial Anthropic (anthropic/*) | ALTA | ADOPTED imediato |
| Plugin/Skill com SKILL.md | ALTA | Converter e indexar |
| MCP Server | MEDIA | Documentar em `integrations/mcp-servers/` |
| SDK / biblioteca | MEDIA | Documentar em `algorithms/` se algoritmos úteis |
| DevOps (k8s, terraform, argo-cd) | BAIXA | Documentar apenas se relacionado ao APEX infra |
| Apps de terceiros | BAIXA | Plugin doc apenas |

---

## Estrutura de Diretórios APEX (referência)

```
APEX/
├── INDEX.md                    ← ENTRY POINT para LLMs
├── README.md                   ← Documentação humana
├── INTAKE_WORKFLOW.md          ← Este documento
├── agents/
│   ├── pmi_pm/AGENT.md
│   ├── architect/AGENT.md
│   ├── engineer/AGENT.md
│   ├── critic/AGENT.md
│   ├── researcher/AGENT.md
│   ├── meta_reasoning/AGENT.md
│   ├── bayesian_curator/AGENT.md
│   ├── diff_governance/AGENT.md
│   ├── scientist_agent/AGENT.md
│   └── anchor_destroyer/AGENT.md
├── skills/
│   ├── mathematics/            ← APEX core math skills
│   ├── legal/                  ← APEX core legal skills
│   ├── finance/                ← Financial services (56+ skills)
│   ├── engineering/            ← Software engineering skills
│   ├── data-science/           ← Data analysis skills
│   ├── healthcare/             ← Healthcare skills
│   ├── science/                ← Life sciences, bio-research
│   ├── marketing/              ← Marketing skills
│   ├── sales/                  ← Sales skills
│   ├── human-resources/        ← HR skills
│   ├── operations/             ← Operations skills
│   ├── product-management/     ← PM skills
│   ├── customer-support/       ← Support skills
│   ├── knowledge-management/   ← Enterprise search
│   ├── productivity/           ← Personal productivity
│   ├── design/                 ← UX/Design skills
│   ├── integrations/           ← Slack, Apollo, etc.
│   └── anthropic-official/     ← Official Anthropic skills
├── algorithms/
├── meta/
│   ├── anchors.yaml
│   └── llm_compat.yaml
└── diffs/
    └── v00_33_0/
```

---

## Exemplo de Execução

Quando o usuário disser "adicione este repo ao APEX":

```
[INTAKE_WORKFLOW: ATIVADO]

STAGE_1: Montando ZIP...
  → Partes encontradas: 16 × 25MB = 390MB total
  → Header verificado: PK magic OK

STAGE_2: Extraindo...
  → 207 SKILL.md encontrados em 5 repos prioritários

STAGE_3: Analisando...
  → 206 skills classificados (1 template ignorado)
  → Domínios: finance(64), knowledge-work(124), healthcare(3), life-sciences(6), official(18)

STAGE_4: Convertendo para APEX format...
  → 206 SKILL.md gerados com frontmatter APEX completo

STAGE_5: Indexando...
  → INDEX.md: 18 novos domínios adicionados
  → anchors.yaml: ~400 novos anchors
  → Git push: OK

[INTAKE_WORKFLOW: COMPLETO — 206 skills disponíveis]
```

---

## Diff History
- **v00.33.0**: Criado para documentar processo de intake de repositórios externos
