# APEX Index — Hub de Navegação

**Gerado automaticamente** por `tools/generate_index.py` — 2026-04-17 21:25 UTC
**Versão APEX**: v00.36.0 | **Skills**: 3761 | **Domínios**: 52 | **Erros de parse**: 0

> Este arquivo é gerado automaticamente. Não editar manualmente.
> Para atualizar: `python tools/generate_index.py` ou aguardar o GitHub Action.

---

## Como Encontrar Qualquer Skill em 3 Passos

```
PASSO 1: Identifique o domínio na tabela abaixo ou no domain_map YAML
PASSO 2: Acesse skills/{domínio}/  (use o path exato da tabela)
PASSO 3: Leia o SKILL.md do skill específico
```

> ATENÇÃO: Use nomes canônicos de domínio (ex: `engineering_frontend`,
> não `frontend`). Ver coluna 'Path' na tabela abaixo.

---

## Domínios Disponíveis

| Domínio | Skills | Path | Status |
|---------|--------|------|--------|
| AI & Machine Learning | 286 | `skills/ai-ml/` | OK |
| AI/ML — Agents | 25 | `skills/ai_ml_agents/` | OK |
| AI/ML — LLMs | 14 | `skills/ai_ml_llm/` | OK |
| AI/ML — Machine Learning | 14 | `skills/ai_ml_ml/` | OK |
| Anthropic Official | 35 | `skills/anthropic-official/` | OK |
| Anthropic-Skills | 32 | `skills/anthropic-skills/` | OK |
| APEX Internals | 8 | `skills/apex_internals/` | OK |
| Awesome Claude | 14 | `skills/awesome_claude/` | OK |
| Business | 159 | `skills/business/` | OK |
| Business — Content | 6 | `skills/business_content/` | OK |
| Business — Human Resources | 6 | `skills/business_human_resources/` | OK |
| Business — Productivity | 9 | `skills/business_productivity/` | OK |
| Business — Sales | 4 | `skills/business_sales/` | OK |
| Claude Skills (M) | 9 | `skills/claude_skills_m/` | OK |
| Community | 414 | `skills/community/` | OK |
| Community — General | 27 | `skills/community_general/` | OK |
| Customer Support | 6 | `skills/customer-support/` | OK |
| Data | 34 | `skills/data/` | OK |
| Data Science | 11 | `skills/data-science/` | OK |
| Design | 73 | `skills/design/` | OK |
| Engineering (Core) | 596 | `skills/engineering/` | OK |
| Engineering Agentops | 14 | `skills/engineering_agentops/` | OK |
| Engineering — API | 14 | `skills/engineering_api/` | OK |
| Engineering — Backend | 9 | `skills/engineering_backend/` | OK |
| Engineering — CLI | 3 | `skills/engineering_cli/` | OK |
| Engineering — Cloud AWS | 4 | `skills/engineering_cloud_aws/` | OK |
| Engineering — Cloud Azure | 161 | `skills/engineering_cloud_azure/` | OK |
| Engineering — Cloud GCP | 2 | `skills/engineering_cloud_gcp/` | OK |
| Engineering — Database | 13 | `skills/engineering_database/` | OK |
| Engineering — DevOps | 29 | `skills/engineering_devops/` | OK |
| Engineering — Frontend | 15 | `skills/engineering_frontend/` | OK |
| Engineering — Git | 6 | `skills/engineering_git/` | OK |
| Engineering — Mobile | 3 | `skills/engineering_mobile/` | OK |
| Engineering — Security | 29 | `skills/engineering_security/` | OK |
| Engineering — Testing | 19 | `skills/engineering_testing/` | OK |
| Finance | 191 | `skills/finance/` | OK |
| Healthcare | 23 | `skills/healthcare/` | OK |
| Human Resources | 10 | `skills/human-resources/` | OK |
| Integrations | 841 | `skills/integrations/` | OK |
| Knowledge Management | 10 | `skills/knowledge-management/` | OK |
| Knowledge Work | 248 | `skills/knowledge-work/` | OK |
| Legal | 27 | `skills/legal/` | OK |
| Marketing | 137 | `skills/marketing/` | OK |
| Mathematics | 2 | `skills/mathematics/` | OK |
| Operations | 10 | `skills/operations/` | OK |
| Product Management | 11 | `skills/product-management/` | OK |
| Productivity | 22 | `skills/productivity/` | OK |
| Sales | 26 | `skills/sales/` | OK |
| Science | 25 | `skills/science/` | OK |
| Science — Research | 1 | `skills/science_research/` | OK |
| Security | 60 | `skills/security/` | OK |
| Web3 | 14 | `skills/web3/` | OK |

---

## Domain Map (machine-parseable YAML)

```yaml
domain_map:
  AI_ML:
    path: skills/ai-ml/
    display_name: "AI & Machine Learning"
    skill_count: 286
    anchors: [automation, automate, tasks, rube, composio, agent, claude, agents, skill, expert, azure, search, build, management, code]
    sub_domains:
      agents:
        path: skills/ai-ml/agents/
        skill_count: 47
        skills:
          - skill: ai_ml.agents.agent_evaluation
            path: skills/ai-ml/agents/agent-evaluation/SKILL.md
            status: CANDIDATE
            anchors: [agent, evaluation, testing, benchmarking, agents]
          - skill: ai_ml.agents.agent_framework_azure_ai_py
            path: skills/ai-ml/agents/agent-framework-azure-ai-py/SKILL.md
            status: CANDIDATE
            anchors: [agent, framework, azure, build, persistent]
          - skill: ai_ml.agents.agent_manager_skill
            path: skills/ai-ml/agents/agent-manager-skill/SKILL.md
            status: CANDIDATE
            anchors: [agent, manager, skill, manage, multiple]
          - skill: ai_ml.agents.agent_memory_mcp
            path: skills/ai-ml/agents/agent-memory-mcp/SKILL.md
            status: CANDIDATE
            anchors: [agent, memory, hybrid, system, provides]
          - skill: ai_ml.agents.agent_memory_systems
            path: skills/ai-ml/agents/agent-memory-systems/SKILL.md
            status: CANDIDATE
            anchors: [agent, memory, systems, cornerstone, intelligent]
          # ... +42 skills adicionais
      computer-vision:
        path: skills/ai-ml/computer-vision/
        skill_count: 3
        skills:
          - skill: ai_ml.computer_vision.computer_vision_expert
            path: skills/ai-ml/computer-vision/computer-vision-expert/SKILL.md
            status: CANDIDATE
            anchors: [computer, vision, expert, sota, specialized]
          - skill: ai_ml.computer_vision.fal_image_edit
            path: skills/ai-ml/computer-vision/fal-image-edit/SKILL.md
            status: CANDIDATE
            anchors: [image, edit, powered, editing, style]
          - skill: ai_ml.computer_vision.seo_image_gen
            path: skills/ai-ml/computer-vision/seo-image-gen/SKILL.md
            status: CANDIDATE
            anchors: [image, generate, focused, images, cards]
      embeddings:
        path: skills/ai-ml/embeddings/
        skill_count: 10
        skills:
          - skill: ai_ml.embeddings.api_fuzzing_bug_bounty
            path: skills/ai-ml/embeddings/api-fuzzing-bug-bounty/SKILL.md
            status: CANDIDATE
            anchors: [fuzzing, bounty, provide, comprehensive, techniques]
          - skill: ai_ml.embeddings.azure_search_documents_dotnet
            path: skills/ai-ml/embeddings/azure-search-documents-dotnet/SKILL.md
            status: CANDIDATE
            anchors: [azure, search, documents, dotnet, building]
          - skill: ai_ml.embeddings.azure_search_documents_py
            path: skills/ai-ml/embeddings/azure-search-documents-py/SKILL.md
            status: CANDIDATE
            anchors: [azure, search, documents, python, vector]
          - skill: ai_ml.embeddings.azure_search_documents_ts
            path: skills/ai-ml/embeddings/azure-search-documents-ts/SKILL.md
            status: CANDIDATE
            anchors: [azure, search, documents, build, applications]
          - skill: ai_ml.embeddings.context_manager
            path: skills/ai-ml/embeddings/context-manager/SKILL.md
            status: CANDIDATE
            anchors: [context, manager, elite, engineering, specialist]
          # ... +5 skills adicionais
      frameworks:
        path: skills/ai-ml/frameworks/
        skill_count: 1
        skills:
          - skill: ai_ml.frameworks.langgraph
            path: skills/ai-ml/frameworks/langgraph/SKILL.md
            status: CANDIDATE
            anchors: [langgraph, expert, production, grade, framework]
      llm:
        path: skills/ai-ml/llm/
        skill_count: 82
        skills:
          - skill: ai_ml.llm.activecampaign_automation
            path: skills/ai-ml/llm/activecampaign-automation/SKILL.md
            status: CANDIDATE
            anchors: [activecampaign, automation, automate, tasks, rube]
          - skill: ai_ml.llm.adhx
            path: skills/ai-ml/llm/adhx/SKILL.md
            status: CANDIDATE
            anchors: [adhx, fetch, twitter, post, clean]
          - skill: ai_ml.llm.advanced_evaluation
            path: skills/ai-ml/llm/advanced-evaluation/SKILL.md
            status: CANDIDATE
            anchors: [advanced, evaluation, skill, user, asks]
          - skill: ai_ml.llm.aegisops_ai
            path: skills/ai-ml/llm/aegisops-ai/SKILL.md
            status: CANDIDATE
            anchors: [aegisops, autonomous, devsecops, finops, guardrails]
          - skill: ai_ml.llm.agents_md
            path: skills/ai-ml/llm/agents-md/SKILL.md
            status: CANDIDATE
            anchors: [agents, skill, user, asks, create]
          # ... +77 skills adicionais
      mcp:
        path: skills/ai-ml/mcp/
        skill_count: 87
        skills:
          - skill: ai_ml.mcp.airtable_automation
            path: skills/ai-ml/mcp/airtable-automation/SKILL.md
            status: CANDIDATE
            anchors: [airtable, automation, automate, tasks, rube]
          - skill: ai_ml.mcp.amplitude_automation
            path: skills/ai-ml/mcp/amplitude-automation/SKILL.md
            status: CANDIDATE
            anchors: [amplitude, automation, automate, tasks, rube]
          - skill: ai_ml.mcp.asana_automation
            path: skills/ai-ml/mcp/asana-automation/SKILL.md
            status: CANDIDATE
            anchors: [asana, automation, automate, tasks, rube]
          - skill: ai_ml.mcp.bamboohr_automation
            path: skills/ai-ml/mcp/bamboohr-automation/SKILL.md
            status: CANDIDATE
            anchors: [bamboohr, automation, automate, tasks, rube]
          - skill: ai_ml.mcp.basecamp_automation
            path: skills/ai-ml/mcp/basecamp-automation/SKILL.md
            status: CANDIDATE
            anchors: [basecamp, automation, automate, project, management]
          # ... +82 skills adicionais
      ml:
        path: skills/ai-ml/ml/
        skill_count: 15
        skills:
          - skill: ai_ml.ml.hugging_face_cli
            path: skills/ai-ml/ml/hugging-face-cli/SKILL.md
            status: CANDIDATE
            anchors: [hugging, face, download, upload, manage]
          - skill: ai_ml.ml.hugging_face_community_evals
            path: skills/ai-ml/ml/hugging-face-community-evals/SKILL.md
            status: CANDIDATE
            anchors: [hugging, face, community, evals, local]
          - skill: ai_ml.ml.hugging_face_dataset_viewer
            path: skills/ai-ml/ml/hugging-face-dataset-viewer/SKILL.md
            status: CANDIDATE
            anchors: [hugging, face, dataset, viewer, query]
          - skill: ai_ml.ml.hugging_face_gradio
            path: skills/ai-ml/ml/hugging-face-gradio/SKILL.md
            status: CANDIDATE
            anchors: [hugging, face, gradio, build, edit]
          - skill: ai_ml.ml.hugging_face_jobs
            path: skills/ai-ml/ml/hugging-face-jobs/SKILL.md
            status: CANDIDATE
            anchors: [hugging, face, jobs, workloads, managed]
          # ... +10 skills adicionais
      rag:
        path: skills/ai-ml/rag/
        skill_count: 41
        skills:
          - skill: ai_ml.rag.ai_engineering_toolkit
            path: skills/ai-ml/rag/ai-engineering-toolkit/SKILL.md
            status: CANDIDATE
            anchors: [engineering, toolkit, production, ready, workflows]
          - skill: ai_ml.rag.appdeploy
            path: skills/ai-ml/rag/appdeploy/SKILL.md
            status: CANDIDATE
            anchors: [appdeploy, deploy, apps, backend, apis]
          - skill: ai_ml.rag.azure_data_tables_java
            path: skills/ai-ml/rag/azure-data-tables-java/SKILL.md
            status: CANDIDATE
            anchors: [azure, data, tables, java, build]
          - skill: ai_ml.rag.azure_data_tables_py
            path: skills/ai-ml/rag/azure-data-tables-py/SKILL.md
            status: CANDIDATE
            anchors: [azure, data, tables, python, storage]
          - skill: ai_ml.rag.azure_keyvault_py
            path: skills/ai-ml/rag/azure-keyvault-py/SKILL.md
            status: CANDIDATE
            anchors: [azure, keyvault, vault, python, secrets]
          # ... +36 skills adicionais

  AI_ML_AGENTS:
    path: skills/ai_ml_agents/
    display_name: "AI/ML — Agents"
    skill_count: 25
    anchors: [agent, and, skills, plugins, claude, the, skill, agents, for, designer, when, multi-agent, protocol, board, agenthub]
    sub_domains:
      agent-designer:
        path: skills/ai_ml_agents/agent-designer/
        skill_count: 1
        skills:
          - skill: ai_ml_agents.agent_designer
            path: skills/ai_ml_agents/agent-designer/SKILL.md
            status: CANDIDATE
            anchors: [agent, designer, when, design, agent-designer]
      agent-protocol:
        path: skills/ai_ml_agents/agent-protocol/
        skill_count: 1
        skills:
          - skill: ai_ml_agents.agent_protocol
            path: skills/ai_ml_agents/agent-protocol/SKILL.md
            status: CANDIDATE
            anchors: [agent, protocol, inter, communication, suite]
      agent-workflow-designer:
        path: skills/ai_ml_agents/agent-workflow-designer/
        skill_count: 1
        skills:
          - skill: ai_ml_agents.agent_workflow_designer
            path: skills/ai_ml_agents/agent-workflow-designer/SKILL.md
            status: CANDIDATE
            anchors: [agent, workflow, designer, agent-workflow-designer, generate]
      board:
        path: skills/ai_ml_agents/board/
        skill_count: 1
        skills:
          - skill: ai_ml_agents.board
            path: skills/ai_ml_agents/board/SKILL.md
            status: CANDIDATE
            anchors: [board, read, write, browse, agenthub]
      board-meeting:
        path: skills/ai_ml_agents/board-meeting/
        skill_count: 1
        skills:
          - skill: ai_ml_agents.board_meeting
            path: skills/ai_ml_agents/board-meeting/SKILL.md
            status: CANDIDATE
            anchors: [board, meeting, multi, agent, protocol]
      c-level-advisor:
        path: skills/ai_ml_agents/c-level-advisor/
        skill_count: 1
        skills:
          - skill: ai_ml_agents.c_level_advisor
            path: skills/ai_ml_agents/c-level-advisor/SKILL.md
            status: CANDIDATE
            anchors: [level, advisor, advisory, agent, skills]
      cherry-assistant-guide:
        path: skills/ai_ml_agents/cherry-assistant-guide/
        skill_count: 1
        skills:
          - skill: ai_ml_agents.cherry_assistant_guide
            path: skills/ai_ml_agents/cherry-assistant-guide/SKILL.md
            status: CANDIDATE
            anchors: [cherry, assistant, guide, studio, provider]
      composio-skills:
        path: skills/ai_ml_agents/composio-skills/
        skill_count: 1
        skills:
          - skill: ai_ml_agents.composio_skills
            path: skills/ai_ml_agents/composio-skills/SKILL.md
            status: CANDIDATE
            anchors: [composio, skills, automate, agent, mail]
      continual-learning:
        path: skills/ai_ml_agents/continual-learning/
        skill_count: 1
        skills:
          - skill: ai_ml_agents.continual_learning
            path: skills/ai_ml_agents/continual-learning/SKILL.md
            status: CANDIDATE
            anchors: [continual, learning, guide, implementing, coding]
      create-skill:
        path: skills/ai_ml_agents/create-skill/
        skill_count: 1
        skills:
          - skill: ai_ml_agents.create_skill
            path: skills/ai_ml_agents/create-skill/SKILL.md
            status: CANDIDATE
            anchors: [create, skill, current, repository, when]
      finance:
        path: skills/ai_ml_agents/finance/
        skill_count: 1
        skills:
          - skill: ai_ml_agents.finance
            path: skills/ai_ml_agents/finance/SKILL.md
            status: CANDIDATE
            anchors: [finance, financial, analyst, agent, skill]
      gh-pr-review:
        path: skills/ai_ml_agents/gh-pr-review/
        skill_count: 1
        skills:
          - skill: ai_ml_agents.gh_pr_review
            path: skills/ai_ml_agents/gh-pr-review/SKILL.md
            status: CANDIDATE
            anchors: [review, automated, code, local, branches]
      init:
        path: skills/ai_ml_agents/init/
        skill_count: 1
        skills:
          - skill: ai_ml_agents.init
            path: skills/ai_ml_agents/init/SKILL.md
            status: CANDIDATE
            anchors: [init, create, agenthub, collaboration, session]
      langsmith-fetch:
        path: skills/ai_ml_agents/langsmith-fetch/
        skill_count: 1
        skills:
          - skill: ai_ml_agents.langsmith_fetch
            path: skills/ai_ml_agents/langsmith-fetch/SKILL.md
            status: CANDIDATE
            anchors: [langsmith, fetch, debug, langchain, langgraph]
      m365-agents-py:
        path: skills/ai_ml_agents/m365-agents-py/
        skill_count: 1
        skills:
          - skill: ai_ml_agents.m365_agents_py
            path: skills/ai_ml_agents/m365-agents-py/SKILL.md
            status: CANDIDATE
            anchors: [m365, agents, agents-py, adapter, agent_app]
      marketing-skill:
        path: skills/ai_ml_agents/marketing-skill/
        skill_count: 1
        skills:
          - skill: ai_ml_agents.marketing_skill
            path: skills/ai_ml_agents/marketing-skill/SKILL.md
            status: CANDIDATE
            anchors: [marketing, skill, agent, skills, plugins]
      merge:
        path: skills/ai_ml_agents/merge/
        skill_count: 1
        skills:
          - skill: ai_ml_agents.merge
            path: skills/ai_ml_agents/merge/SKILL.md
            status: CANDIDATE
            anchors: [merge, winning, agent, branch, into]
      product-team:
        path: skills/ai_ml_agents/product-team/
        skill_count: 1
        skills:
          - skill: ai_ml_agents.product_team
            path: skills/ai_ml_agents/product-team/SKILL.md
            status: CANDIDATE
            anchors: [product, team, agent, skills, plugins]
      project-management:
        path: skills/ai_ml_agents/project-management/
        skill_count: 1
        skills:
          - skill: ai_ml_agents.project_management
            path: skills/ai_ml_agents/project-management/SKILL.md
            status: CANDIDATE
            anchors: [project, management, agent, skills, plugins]
      ra-qm-team:
        path: skills/ai_ml_agents/ra-qm-team/
        skill_count: 1
        skills:
          - skill: ai_ml_agents.ra_qm_team
            path: skills/ai_ml_agents/ra-qm-team/SKILL.md
            status: CANDIDATE
            anchors: [team, regulatory, agent, skills, plugins]
      research-summarizer:
        path: skills/ai_ml_agents/research-summarizer/
        skill_count: 1
        skills:
          - skill: ai_ml_agents.research_summarizer
            path: skills/ai_ml_agents/research-summarizer/SKILL.md
            status: CANDIDATE
            anchors: [research, summarizer, structured, summarization, agent]
      run:
        path: skills/ai_ml_agents/run/
        skill_count: 1
        skills:
          - skill: ai_ml_agents.run
            path: skills/ai_ml_agents/run/SKILL.md
            status: CANDIDATE
            anchors: [shot, lifecycle, command, that, chains]
      self-improving-agent:
        path: skills/ai_ml_agents/self-improving-agent/
        skill_count: 1
        skills:
          - skill: ai_ml_agents.self_improving_agent
            path: skills/ai_ml_agents/self-improving-agent/SKILL.md
            status: CANDIDATE
            anchors: [self, improving, agent, curate, claude]
      spawn:
        path: skills/ai_ml_agents/spawn/
        skill_count: 1
        skills:
          - skill: ai_ml_agents.spawn
            path: skills/ai_ml_agents/spawn/SKILL.md
            status: CANDIDATE
            anchors: [spawn, launch, parallel, subagents, isolated]
      status:
        path: skills/ai_ml_agents/status/
        skill_count: 1
        skills:
          - skill: ai_ml_agents.status
            path: skills/ai_ml_agents/status/SKILL.md
            status: CANDIDATE
            anchors: [status, show, state, agent, progress]

  AI_ML_LLM:
    path: skills/ai_ml_llm/
    display_name: "AI/ML — LLMs"
    skill_count: 14
    anchors: [agent, that, optimize, autonomous, experiment, loop, coverage, gaps, critical, eval, evaluate, when, prompt, engineer, agenthub]
    sub_domains:
      agenthub:
        path: skills/ai_ml_llm/agenthub/
        skill_count: 1
        skills:
          - skill: ai_ml_llm.agenthub
            path: skills/ai_ml_llm/agenthub/SKILL.md
            status: CANDIDATE
            anchors: [agenthub, multi, agent, collaboration, plugin]
      ai-seo:
        path: skills/ai_ml_llm/ai-seo/
        skill_count: 1
        skills:
          - skill: ai_ml_llm.ai_seo
            path: skills/ai_ml_llm/ai-seo/SKILL.md
            status: CANDIDATE
            anchors: [optimize, content, cited, search, engines]
      autoresearch-agent:
        path: skills/ai_ml_llm/autoresearch-agent/
        skill_count: 1
        skills:
          - skill: ai_ml_llm.autoresearch_agent
            path: skills/ai_ml_llm/autoresearch-agent/SKILL.md
            status: CANDIDATE
            anchors: [autoresearch, agent, autonomous, experiment, loop]
      composio-skills:
        path: skills/ai_ml_llm/composio-skills/
        skill_count: 1
        skills:
          - skill: ai_ml_llm.composio_skills
            path: skills/ai_ml_llm/composio-skills/SKILL.md
            status: CANDIDATE
            anchors: [composio, skills, automate, appdrag, tasks]
      coverage:
        path: skills/ai_ml_llm/coverage/
        skill_count: 1
        skills:
          - skill: ai_ml_llm.coverage
            path: skills/ai_ml_llm/coverage/SKILL.md
            status: CANDIDATE
            anchors: [coverage, test, gaps, map, matrix]
      eval:
        path: skills/ai_ml_llm/eval/
        skill_count: 1
        skills:
          - skill: ai_ml_llm.eval
            path: skills/ai_ml_llm/eval/SKILL.md
            status: CANDIDATE
            anchors: [eval, evaluate, rank, agent, results]
      loop:
        path: skills/ai_ml_llm/loop/
        skill_count: 1
        skills:
          - skill: ai_ml_llm.loop
            path: skills/ai_ml_llm/loop/SKILL.md
            status: CANDIDATE
            anchors: [loop, start, autonomous, experiment, user-selected]
      paywall-upgrade-cro:
        path: skills/ai_ml_llm/paywall-upgrade-cro/
        skill_count: 1
        skills:
          - skill: ai_ml_llm.paywall_upgrade_cro
            path: skills/ai_ml_llm/paywall-upgrade-cro/SKILL.md
            status: CANDIDATE
            anchors: [paywall, upgrade, when, create, paywall-upgrade-cro]
      prompt-engineering:
        path: skills/ai_ml_llm/prompt-engineering/
        skill_count: 1
        skills:
          - skill: ai_ml_llm.prompt_engineering
            path: skills/ai_ml_llm/prompt-engineering/SKILL.md
            status: CANDIDATE
            anchors: [prompt, engineering, patterns, including, structured]
      review:
        path: skills/ai_ml_llm/review/
        skill_count: 1
        skills:
          - skill: ai_ml_llm.review
            path: skills/ai_ml_llm/review/SKILL.md
            status: CANDIDATE
            anchors: [review, file, score, critical, warning]
      sales-engineer:
        path: skills/ai_ml_llm/sales-engineer/
        skill_count: 1
        skills:
          - skill: ai_ml_llm.sales_engineer
            path: skills/ai_ml_llm/sales-engineer/SKILL.md
            status: CANDIDATE
            anchors: [sales, engineer, analyzes, responses, coverage]
      self-eval:
        path: skills/ai_ml_llm/self-eval/
        skill_count: 1
        skills:
          - skill: ai_ml_llm.self_eval
            path: skills/ai_ml_llm/self-eval/SKILL.md
            status: CANDIDATE
            anchors: [self, eval, honestly, evaluate, work]
      senior-prompt-engineer:
        path: skills/ai_ml_llm/senior-prompt-engineer/
        skill_count: 1
        skills:
          - skill: ai_ml_llm.senior_prompt_engineer
            path: skills/ai_ml_llm/senior-prompt-engineer/SKILL.md
            status: CANDIDATE
            anchors: [senior, prompt, engineer, this, skill]
      wiki-llms-txt:
        path: skills/ai_ml_llm/wiki-llms-txt/
        skill_count: 1
        skills:
          - skill: ai_ml_llm.wiki_llms_txt
            path: skills/ai_ml_llm/wiki-llms-txt/SKILL.md
            status: CANDIDATE
            anchors: [wiki, llms, generates, full, files]

  AI_ML_ML:
    path: skills/ai_ml_ml/
    display_name: "AI/ML — Machine Learning"
    skill_count: 14
    anchors: [companies, for, advisor, leadership, and, skills, analyzes, financial, scaling, marketing, saas, analysis, campaign, analytics, performance]
    sub_domains:
      campaign-analytics:
        path: skills/ai_ml_ml/campaign-analytics/
        skill_count: 1
        skills:
          - skill: ai_ml_ml.campaign_analytics
            path: skills/ai_ml_ml/campaign-analytics/SKILL.md
            status: CANDIDATE
            anchors: [campaign, analytics, analyzes, performance, multi]
      cfo-advisor:
        path: skills/ai_ml_ml/cfo-advisor/
        skill_count: 1
        skills:
          - skill: ai_ml_ml.cfo_advisor
            path: skills/ai_ml_ml/cfo-advisor/SKILL.md
            status: CANDIDATE
            anchors: [advisor, financial, leadership, startups, scaling]
      cmo-advisor:
        path: skills/ai_ml_ml/cmo-advisor/
        skill_count: 1
        skills:
          - skill: ai_ml_ml.cmo_advisor
            path: skills/ai_ml_ml/cmo-advisor/SKILL.md
            status: CANDIDATE
            anchors: [advisor, marketing, leadership, scaling, companies]
      competitive-teardown:
        path: skills/ai_ml_ml/competitive-teardown/
        skill_count: 1
        skills:
          - skill: ai_ml_ml.competitive_teardown
            path: skills/ai_ml_ml/competitive-teardown/SKILL.md
            status: CANDIDATE
            anchors: [competitive, teardown, analyzes, competitor, products]
      composio-skills:
        path: skills/ai_ml_ml/composio-skills/
        skill_count: 1
        skills:
          - skill: ai_ml_ml.composio_skills
            path: skills/ai_ml_ml/composio-skills/SKILL.md
            status: CANDIDATE
            anchors: [composio, skills, automate, tasks, rube]
      cro-advisor:
        path: skills/ai_ml_ml/cro-advisor/
        skill_count: 1
        skills:
          - skill: ai_ml_ml.cro_advisor
            path: skills/ai_ml_ml/cro-advisor/SKILL.md
            status: CANDIDATE
            anchors: [advisor, revenue, leadership, saas, companies]
      customer-success-manager:
        path: skills/ai_ml_ml/customer-success-manager/
        skill_count: 1
        skills:
          - skill: ai_ml_ml.customer_success_manager
            path: skills/ai_ml_ml/customer-success-manager/SKILL.md
            status: CANDIDATE
            anchors: [customer, success, manager, monitors, health]
      document-skills:
        path: skills/ai_ml_ml/document-skills/
        skill_count: 1
        skills:
          - skill: ai_ml_ml.document_skills
            path: skills/ai_ml_ml/document-skills/SKILL.md
            status: CANDIDATE
            anchors: [document, skills, comprehensive, creation, editing]
      financial-analyst:
        path: skills/ai_ml_ml/financial-analyst/
        skill_count: 1
        skills:
          - skill: ai_ml_ml.financial_analyst
            path: skills/ai_ml_ml/financial-analyst/SKILL.md
            status: CANDIDATE
            anchors: [financial, analyst, performs, ratio, analysis]
      marketing-psychology:
        path: skills/ai_ml_ml/marketing-psychology/
        skill_count: 1
        skills:
          - skill: ai_ml_ml.marketing_psychology
            path: skills/ai_ml_ml/marketing-psychology/SKILL.md
            status: CANDIDATE
            anchors: [marketing, psychology, when, apply, marketing-psychology]
      pricing-strategy:
        path: skills/ai_ml_ml/pricing-strategy/
        skill_count: 1
        skills:
          - skill: ai_ml_ml.pricing_strategy
            path: skills/ai_ml_ml/pricing-strategy/SKILL.md
            status: CANDIDATE
            anchors: [pricing, strategy, design, optimize, communicate]
      raffle-winner-picker:
        path: skills/ai_ml_ml/raffle-winner-picker/
        skill_count: 1
        skills:
          - skill: ai_ml_ml.raffle_winner_picker
            path: skills/ai_ml_ml/raffle-winner-picker/SKILL.md
            status: CANDIDATE
            anchors: [raffle, winner, picker, picks, random]
      skill-share:
        path: skills/ai_ml_ml/skill-share/
        skill_count: 1
        skills:
          - skill: ai_ml_ml.skill_share
            path: skills/ai_ml_ml/skill-share/SKILL.md
            status: CANDIDATE
            anchors: [skill, share, that, creates, claude]
      theme-factory:
        path: skills/ai_ml_ml/theme-factory/
        skill_count: 1
        skills:
          - skill: ai_ml_ml.theme_factory
            path: skills/ai_ml_ml/theme-factory/SKILL.md
            status: CANDIDATE
            anchors: [theme, factory, toolkit, styling, artifacts]

  ANTHROPIC_OFFICIAL:
    path: skills/anthropic-official/
    display_name: "Anthropic Official"
    skill_count: 35
    anchors: [skill, creating, create, and, for, guide, this, whenever, the, time, file, toolkit, visual, high, design]
    sub_domains:
      _source:
        path: skills/anthropic-official/_source/
        skill_count: 18
        skills:
          - skill: algorithmic-art
            path: skills/anthropic-official/_source/skills/algorithmic-art/SKILL.md
            status: UNKNOWN
            anchors: [algorithmic-art, creating, algorithmic, art, seeded]
          - skill: brand-guidelines
            path: skills/anthropic-official/_source/skills/brand-guidelines/SKILL.md
            status: UNKNOWN
            anchors: [brand-guidelines, applies, anthropic, official, brand]
          - skill: canvas-design
            path: skills/anthropic-official/_source/skills/canvas-design/SKILL.md
            status: UNKNOWN
            anchors: [canvas-design, create, beautiful, visual, art]
          - skill: claude-api
            path: skills/anthropic-official/_source/skills/claude-api/SKILL.md
            status: UNKNOWN
          - skill: doc-coauthoring
            path: skills/anthropic-official/_source/skills/doc-coauthoring/SKILL.md
            status: UNKNOWN
            anchors: [doc-coauthoring, guide, through, structured, workflow]
          # ... +13 skills adicionais
      algorithmic-art:
        path: skills/anthropic-official/algorithmic-art/
        skill_count: 1
        skills:
          - skill: anthropic_official.algorithmic_art
            path: skills/anthropic-official/algorithmic-art/SKILL.md
            status: ADOPTED
            anchors: [algorithmic, creating, seeded, randomness, interactive]
      brand-guidelines:
        path: skills/anthropic-official/brand-guidelines/
        skill_count: 1
        skills:
          - skill: anthropic_official.brand_guidelines
            path: skills/anthropic-official/brand-guidelines/SKILL.md
            status: ADOPTED
            anchors: [brand, guidelines, applies, anthropic, official]
      canvas-design:
        path: skills/anthropic-official/canvas-design/
        skill_count: 1
        skills:
          - skill: anthropic_official.canvas_design
            path: skills/anthropic-official/canvas-design/SKILL.md
            status: ADOPTED
            anchors: [canvas, design, create, beautiful, visual]
      claude-api:
        path: skills/anthropic-official/claude-api/
        skill_count: 1
        skills:
          - skill: anthropic_official.claude_api
            path: skills/anthropic-official/claude-api/SKILL.md
            status: ADOPTED
            anchors: [claude, building, powered, applications, skill]
      doc-coauthoring:
        path: skills/anthropic-official/doc-coauthoring/
        skill_count: 1
        skills:
          - skill: anthropic_official.doc_coauthoring
            path: skills/anthropic-official/doc-coauthoring/SKILL.md
            status: ADOPTED
            anchors: [coauthoring, guide, users, through, structured]
      docx:
        path: skills/anthropic-official/docx/
        skill_count: 1
        skills:
          - skill: anthropic_official.docx
            path: skills/anthropic-official/docx/SKILL.md
            status: ADOPTED
            anchors: [docx, skill, whenever, user, wants]
      frontend-design:
        path: skills/anthropic-official/frontend-design/
        skill_count: 1
        skills:
          - skill: anthropic_official.frontend_design
            path: skills/anthropic-official/frontend-design/SKILL.md
            status: ADOPTED
            anchors: [frontend, design, create, distinctive, production]
      internal-comms:
        path: skills/anthropic-official/internal-comms/
        skill_count: 1
        skills:
          - skill: anthropic_official.internal_comms
            path: skills/anthropic-official/internal-comms/SKILL.md
            status: ADOPTED
            anchors: [internal, comms, resources, help, write]
      mcp-builder:
        path: skills/anthropic-official/mcp-builder/
        skill_count: 1
        skills:
          - skill: anthropic_official.mcp_builder
            path: skills/anthropic-official/mcp-builder/SKILL.md
            status: ADOPTED
            anchors: [builder, guide, creating, high, quality]
      pdf:
        path: skills/anthropic-official/pdf/
        skill_count: 1
        skills:
          - skill: anthropic_official.pdf
            path: skills/anthropic-official/pdf/SKILL.md
            status: ADOPTED
            anchors: [skill, whenever, user, wants, anything]
      pptx:
        path: skills/anthropic-official/pptx/
        skill_count: 1
        skills:
          - skill: anthropic_official.pptx
            path: skills/anthropic-official/pptx/SKILL.md
            status: ADOPTED
            anchors: [pptx, skill, time, file, involved]
      skill-creator:
        path: skills/anthropic-official/skill-creator/
        skill_count: 1
        skills:
          - skill: anthropic_official.skill_creator
            path: skills/anthropic-official/skill-creator/SKILL.md
            status: ADOPTED
            anchors: [skill, creator, create, skills, modify]
      slack-gif-creator:
        path: skills/anthropic-official/slack-gif-creator/
        skill_count: 1
        skills:
          - skill: anthropic_official.slack_gif_creator
            path: skills/anthropic-official/slack-gif-creator/SKILL.md
            status: ADOPTED
            anchors: [slack, creator, knowledge, utilities, creating]
      theme-factory:
        path: skills/anthropic-official/theme-factory/
        skill_count: 1
        skills:
          - skill: anthropic_official.theme_factory
            path: skills/anthropic-official/theme-factory/SKILL.md
            status: ADOPTED
            anchors: [theme, factory, toolkit, styling, artifacts]
      web-artifacts-builder:
        path: skills/anthropic-official/web-artifacts-builder/
        skill_count: 1
        skills:
          - skill: anthropic_official.web_artifacts_builder
            path: skills/anthropic-official/web-artifacts-builder/SKILL.md
            status: ADOPTED
            anchors: [artifacts, builder, suite, tools, creating]
      webapp-testing:
        path: skills/anthropic-official/webapp-testing/
        skill_count: 1
        skills:
          - skill: anthropic_official.webapp_testing
            path: skills/anthropic-official/webapp-testing/SKILL.md
            status: ADOPTED
            anchors: [webapp, testing, toolkit, interacting, local]
      xlsx:
        path: skills/anthropic-official/xlsx/
        skill_count: 1
        skills:
          - skill: anthropic_official.xlsx
            path: skills/anthropic-official/xlsx/SKILL.md
            status: ADOPTED
            anchors: [xlsx, skill, time, spreadsheet, file]

  ANTHROPIC_SKILLS:
    path: skills/anthropic-skills/
    display_name: "Anthropic-Skills"
    skill_count: 32
    sub_domains:
      artifacts-builder:
        path: skills/anthropic-skills/artifacts-builder/
        skill_count: 1
        skills:
          - skill: artifacts-builder
            path: skills/anthropic-skills/artifacts-builder/SKILL.md
            status: UNKNOWN
      brand-guidelines:
        path: skills/anthropic-skills/brand-guidelines/
        skill_count: 1
        skills:
          - skill: brand-guidelines
            path: skills/anthropic-skills/brand-guidelines/SKILL.md
            status: UNKNOWN
      canvas-design:
        path: skills/anthropic-skills/canvas-design/
        skill_count: 1
        skills:
          - skill: canvas-design
            path: skills/anthropic-skills/canvas-design/SKILL.md
            status: UNKNOWN
      changelog-generator:
        path: skills/anthropic-skills/changelog-generator/
        skill_count: 1
        skills:
          - skill: changelog-generator
            path: skills/anthropic-skills/changelog-generator/SKILL.md
            status: UNKNOWN
      competitive-ads-extractor:
        path: skills/anthropic-skills/competitive-ads-extractor/
        skill_count: 1
        skills:
          - skill: competitive-ads-extractor
            path: skills/anthropic-skills/competitive-ads-extractor/SKILL.md
            status: UNKNOWN
      connect:
        path: skills/anthropic-skills/connect/
        skill_count: 1
        skills:
          - skill: connect
            path: skills/anthropic-skills/connect/SKILL.md
            status: UNKNOWN
      connect-apps:
        path: skills/anthropic-skills/connect-apps/
        skill_count: 1
        skills:
          - skill: connect-apps
            path: skills/anthropic-skills/connect-apps/SKILL.md
            status: UNKNOWN
      content-research-writer:
        path: skills/anthropic-skills/content-research-writer/
        skill_count: 1
        skills:
          - skill: content-research-writer
            path: skills/anthropic-skills/content-research-writer/SKILL.md
            status: UNKNOWN
      developer-growth-analysis:
        path: skills/anthropic-skills/developer-growth-analysis/
        skill_count: 1
        skills:
          - skill: developer-growth-analysis
            path: skills/anthropic-skills/developer-growth-analysis/SKILL.md
            status: UNKNOWN
      document-skills:
        path: skills/anthropic-skills/document-skills/
        skill_count: 4
        skills:
          - skill: docx
            path: skills/anthropic-skills/document-skills/docx/SKILL.md
            status: UNKNOWN
          - skill: pdf
            path: skills/anthropic-skills/document-skills/pdf/SKILL.md
            status: UNKNOWN
          - skill: pptx
            path: skills/anthropic-skills/document-skills/pptx/SKILL.md
            status: UNKNOWN
          - skill: xlsx
            path: skills/anthropic-skills/document-skills/xlsx/SKILL.md
            status: UNKNOWN
      domain-name-brainstormer:
        path: skills/anthropic-skills/domain-name-brainstormer/
        skill_count: 1
        skills:
          - skill: domain-name-brainstormer
            path: skills/anthropic-skills/domain-name-brainstormer/SKILL.md
            status: UNKNOWN
      file-organizer:
        path: skills/anthropic-skills/file-organizer/
        skill_count: 1
        skills:
          - skill: file-organizer
            path: skills/anthropic-skills/file-organizer/SKILL.md
            status: UNKNOWN
      image-enhancer:
        path: skills/anthropic-skills/image-enhancer/
        skill_count: 1
        skills:
          - skill: image-enhancer
            path: skills/anthropic-skills/image-enhancer/SKILL.md
            status: UNKNOWN
      internal-comms:
        path: skills/anthropic-skills/internal-comms/
        skill_count: 1
        skills:
          - skill: internal-comms
            path: skills/anthropic-skills/internal-comms/SKILL.md
            status: UNKNOWN
      invoice-organizer:
        path: skills/anthropic-skills/invoice-organizer/
        skill_count: 1
        skills:
          - skill: invoice-organizer
            path: skills/anthropic-skills/invoice-organizer/SKILL.md
            status: UNKNOWN
      langsmith-fetch:
        path: skills/anthropic-skills/langsmith-fetch/
        skill_count: 1
        skills:
          - skill: langsmith-fetch
            path: skills/anthropic-skills/langsmith-fetch/SKILL.md
            status: UNKNOWN
      lead-research-assistant:
        path: skills/anthropic-skills/lead-research-assistant/
        skill_count: 1
        skills:
          - skill: lead-research-assistant
            path: skills/anthropic-skills/lead-research-assistant/SKILL.md
            status: UNKNOWN
      mcp-builder:
        path: skills/anthropic-skills/mcp-builder/
        skill_count: 1
        skills:
          - skill: mcp-builder
            path: skills/anthropic-skills/mcp-builder/SKILL.md
            status: UNKNOWN
      meeting-insights-analyzer:
        path: skills/anthropic-skills/meeting-insights-analyzer/
        skill_count: 1
        skills:
          - skill: meeting-insights-analyzer
            path: skills/anthropic-skills/meeting-insights-analyzer/SKILL.md
            status: UNKNOWN
      raffle-winner-picker:
        path: skills/anthropic-skills/raffle-winner-picker/
        skill_count: 1
        skills:
          - skill: raffle-winner-picker
            path: skills/anthropic-skills/raffle-winner-picker/SKILL.md
            status: UNKNOWN
      skill-creator:
        path: skills/anthropic-skills/skill-creator/
        skill_count: 1
        skills:
          - skill: skill-creator
            path: skills/anthropic-skills/skill-creator/SKILL.md
            status: UNKNOWN
      skill-share:
        path: skills/anthropic-skills/skill-share/
        skill_count: 1
        skills:
          - skill: skill-share
            path: skills/anthropic-skills/skill-share/SKILL.md
            status: UNKNOWN
      slack-gif-creator:
        path: skills/anthropic-skills/slack-gif-creator/
        skill_count: 1
        skills:
          - skill: slack-gif-creator
            path: skills/anthropic-skills/slack-gif-creator/SKILL.md
            status: UNKNOWN
      tailored-resume-generator:
        path: skills/anthropic-skills/tailored-resume-generator/
        skill_count: 1
        skills:
          - skill: tailored-resume-generator
            path: skills/anthropic-skills/tailored-resume-generator/SKILL.md
            status: UNKNOWN
      template-skill:
        path: skills/anthropic-skills/template-skill/
        skill_count: 1
        skills:
          - skill: template-skill
            path: skills/anthropic-skills/template-skill/SKILL.md
            status: UNKNOWN
      theme-factory:
        path: skills/anthropic-skills/theme-factory/
        skill_count: 1
        skills:
          - skill: theme-factory
            path: skills/anthropic-skills/theme-factory/SKILL.md
            status: UNKNOWN
      twitter-algorithm-optimizer:
        path: skills/anthropic-skills/twitter-algorithm-optimizer/
        skill_count: 1
        skills:
          - skill: twitter-algorithm-optimizer
            path: skills/anthropic-skills/twitter-algorithm-optimizer/SKILL.md
            status: UNKNOWN
      video-downloader:
        path: skills/anthropic-skills/video-downloader/
        skill_count: 1
        skills:
          - skill: video-downloader
            path: skills/anthropic-skills/video-downloader/SKILL.md
            status: UNKNOWN
      webapp-testing:
        path: skills/anthropic-skills/webapp-testing/
        skill_count: 1
        skills:
          - skill: webapp-testing
            path: skills/anthropic-skills/webapp-testing/SKILL.md
            status: UNKNOWN

  APEX_INTERNALS:
    path: skills/apex_internals/
    display_name: "APEX Internals"
    skill_count: 8
    anchors: [cowork, plugin, bdistill, create, build, scratch, through, guided, conversation, context, guardian, guardiao, contexto, preserva, dados]
    sub_domains:
      cognitive:
        path: skills/apex_internals/cognitive/
        skill_count: 1
        skills:
          - skill: apex_internals.cognitive.context_guardian
            path: skills/apex_internals/cognitive/context-guardian/SKILL.md
            status: CANDIDATE
            anchors: [context, guardian, guardiao, contexto, preserva]
      cognitive-modes:
        path: skills/apex_internals/cognitive-modes/
        skill_count: 1
        skills:
          - skill: apex_internals.cognitive_modes
            path: skills/apex_internals/cognitive-modes/SKILL.md
            status: ADOPTED
            anchors: [cognitive_mode, BDS_simplex, wE, wD, wK]
      forgeskills:
        path: skills/apex_internals/forgeskills/
        skill_count: 1
        skills:
          - skill: apex_internals.forgeskills
            path: skills/apex_internals/forgeskills/SKILL.md
            status: ADOPTED
            anchors: [ForgeSkills, dynamic_skill_forge, git_clone, AST_scan, trusted_domains]
      knowledge:
        path: skills/apex_internals/knowledge/
        skill_count: 2
        skills:
          - skill: apex_internals.knowledge.bdistill_behavioral_xray
            path: skills/apex_internals/knowledge/bdistill-behavioral-xray/SKILL.md
            status: CANDIDATE
            anchors: [bdistill, behavioral, xray, model, patterns]
          - skill: apex_internals.knowledge.bdistill_knowledge_extraction
            path: skills/apex_internals/knowledge/bdistill-knowledge-extraction/SKILL.md
            status: CANDIDATE
            anchors: [bdistill, knowledge, extraction, extract, structured]
      plugins:
        path: skills/apex_internals/plugins/
        skill_count: 3
        skills:
          - skill: apex_internals.plugins.cowork_plugin_customizer
            path: skills/apex_internals/plugins/cowork-plugin-customizer/SKILL.md
            status: ADOPTED
            anchors: [cowork, plugin, customizer, customization, customize]
          - skill: apex_internals.plugins.create_cowork_plugin
            path: skills/apex_internals/plugins/create-cowork-plugin/SKILL.md
            status: ADOPTED
            anchors: [create, cowork, plugin, build, scratch]
          - skill: apex_internals.plugins.skills
            path: skills/apex_internals/plugins/skills/SKILL.md
            status: ADOPTED
            anchors: [create, cowork, plugin, build, scratch]

  AWESOME_CLAUDE:
    path: skills/awesome_claude/
    display_name: "Awesome Claude"
    skill_count: 14
    anchors: [skills, composio, automate, tasks, rube, via, automation, capsule, operations, manage, crm, agentql, agentql-automation, customgpt, customgpt-automation]
    sub_domains:
      ai_ml_agents:
        path: skills/awesome_claude/ai_ml_agents/
        skill_count: 1
        skills:
          - skill: awesome_claude.ai_ml_agents.composio_skills
            path: skills/awesome_claude/ai_ml_agents/composio-skills/SKILL.md
            status: CANDIDATE
            anchors: [composio, skills, automate, agentql, tasks]
      ai_ml_llm:
        path: skills/awesome_claude/ai_ml_llm/
        skill_count: 1
        skills:
          - skill: awesome_claude.ai_ml_llm.composio_skills
            path: skills/awesome_claude/ai_ml_llm/composio-skills/SKILL.md
            status: CANDIDATE
            anchors: [composio, skills, automate, customgpt, tasks]
      ai_ml_ml:
        path: skills/awesome_claude/ai_ml_ml/
        skill_count: 2
        skills:
          - skill: awesome_claude.ai_ml_ml.composio_skills
            path: skills/awesome_claude/ai_ml_ml/composio-skills/SKILL.md
            status: CANDIDATE
            anchors: [composio, skills, automate, bigml, tasks]
          - skill: awesome_claude.ai_ml_ml.document_skills
            path: skills/awesome_claude/ai_ml_ml/document-skills/SKILL.md
            status: CANDIDATE
            anchors: [document, skills, presentation, creation, editing]
      business_human_resources:
        path: skills/awesome_claude/business_human_resources/
        skill_count: 1
        skills:
          - skill: awesome_claude.business_human_resources.composio_skills
            path: skills/awesome_claude/business_human_resources/composio-skills/SKILL.md
            status: CANDIDATE
            anchors: [composio, skills, automate, chat, tasks]
      business_productivity:
        path: skills/awesome_claude/business_productivity/
        skill_count: 1
        skills:
          - skill: awesome_claude.business_productivity.composio_skills
            path: skills/awesome_claude/business_productivity/composio-skills/SKILL.md
            status: CANDIDATE
            anchors: [composio, skills, automate, google, workspace]
      business_sales:
        path: skills/awesome_claude/business_sales/
        skill_count: 1
        skills:
          - skill: awesome_claude.business_sales.composio_skills
            path: skills/awesome_claude/business_sales/composio-skills/SKILL.md
            status: CANDIDATE
            anchors: [composio, skills, automate, capsule, operations]
      design:
        path: skills/awesome_claude/design/
        skill_count: 1
        skills:
          - skill: awesome_claude.design.composio_skills
            path: skills/awesome_claude/design/composio-skills/SKILL.md
            status: CANDIDATE
            anchors: [composio, skills, automate, aryn, tasks]
      engineering_api:
        path: skills/awesome_claude/engineering_api/
        skill_count: 1
        skills:
          - skill: awesome_claude.engineering_api.composio_skills
            path: skills/awesome_claude/engineering_api/composio-skills/SKILL.md
            status: CANDIDATE
            anchors: [composio, skills, automate, onesignal, tasks]
      engineering_database:
        path: skills/awesome_claude/engineering_database/
        skill_count: 1
        skills:
          - skill: awesome_claude.engineering_database.composio_skills
            path: skills/awesome_claude/engineering_database/composio-skills/SKILL.md
            status: CANDIDATE
            anchors: [composio, skills, automate, snowflake, data]
      engineering_devops:
        path: skills/awesome_claude/engineering_devops/
        skill_count: 1
        skills:
          - skill: awesome_claude.engineering_devops.composio_skills
            path: skills/awesome_claude/engineering_devops/composio-skills/SKILL.md
            status: CANDIDATE
            anchors: [composio, skills, automate, capsule, tasks]
      engineering_security:
        path: skills/awesome_claude/engineering_security/
        skill_count: 1
        skills:
          - skill: awesome_claude.engineering_security.composio_skills
            path: skills/awesome_claude/engineering_security/composio-skills/SKILL.md
            status: CANDIDATE
            anchors: [composio, skills, automate, auth0, tasks]
      finance:
        path: skills/awesome_claude/finance/
        skill_count: 1
        skills:
          - skill: awesome_claude.finance.composio_skills
            path: skills/awesome_claude/finance/composio-skills/SKILL.md
            status: CANDIDATE
            anchors: [composio, skills, ramp, automation, manage]
      marketing:
        path: skills/awesome_claude/marketing/
        skill_count: 1
        skills:
          - skill: awesome_claude.marketing.composio_skills
            path: skills/awesome_claude/marketing/composio-skills/SKILL.md
            status: CANDIDATE
            anchors: [composio, skills, automate, aeroleads, tasks]

  BUSINESS:
    path: skills/business/
    display_name: "Business"
    skill_count: 159
    anchors: [startup, business, analyst, comprehensive, analysis, financial, market, generate, year, sizing, calculating, master, modern, powered, analytics]
    sub_domains:
      analysis:
        path: skills/business/analysis/
        skill_count: 4
        skills:
          - skill: business.analysis.business_analyst
            path: skills/business/analysis/business-analyst/SKILL.md
            status: CANDIDATE
            anchors: [business, analyst, master, modern, analysis]
          - skill: business.analysis.startup_business_analyst_business_case
            path: skills/business/analysis/startup-business-analyst-business-case/SKILL.md
            status: CANDIDATE
            anchors: [startup, business, analyst, case, generate]
          - skill: business.analysis.startup_business_analyst_financial_projections
            path: skills/business/analysis/startup-business-analyst-financial-projections/SKILL.md
            status: CANDIDATE
            anchors: [startup, business, analyst, financial, projections]
          - skill: business.analysis.startup_business_analyst_market_opportunity
            path: skills/business/analysis/startup-business-analyst-market-opportunity/SKILL.md
            status: CANDIDATE
            anchors: [startup, business, analyst, market, opportunity]
      business-growth:
        path: skills/business/business-growth/
        skill_count: 5
        skills:
          - skill: business-growth
            path: skills/business/business-growth/SKILL.md
            status: UNKNOWN
          - skill: contract-and-proposal-writer
            path: skills/business/business-growth/contract-and-proposal-writer/SKILL.md
            status: UNKNOWN
          - skill: customer-success-manager
            path: skills/business/business-growth/customer-success-manager/SKILL.md
            status: UNKNOWN
          - skill: revenue-operations
            path: skills/business/business-growth/revenue-operations/SKILL.md
            status: UNKNOWN
          - skill: sales-engineer
            path: skills/business/business-growth/sales-engineer/SKILL.md
            status: UNKNOWN
      c-level-advisor:
        path: skills/business/c-level-advisor/
        skill_count: 34
        skills:
          - skill: c-level-advisor
            path: skills/business/c-level-advisor/SKILL.md
            status: UNKNOWN
          - skill: agent-protocol
            path: skills/business/c-level-advisor/agent-protocol/SKILL.md
            status: UNKNOWN
          - skill: board-deck-builder
            path: skills/business/c-level-advisor/board-deck-builder/SKILL.md
            status: UNKNOWN
          - skill: board-meeting
            path: skills/business/c-level-advisor/board-meeting/SKILL.md
            status: UNKNOWN
          - skill: ceo-advisor
            path: skills/business/c-level-advisor/ceo-advisor/SKILL.md
            status: UNKNOWN
          # ... +29 skills adicionais
      finance:
        path: skills/business/finance/
        skill_count: 4
        skills:
          - skill: finance
            path: skills/business/finance/SKILL.md
            status: UNKNOWN
          - skill: business-investment-advisor
            path: skills/business/finance/business-investment-advisor/SKILL.md
            status: UNKNOWN
          - skill: financial-analyst
            path: skills/business/finance/financial-analyst/SKILL.md
            status: UNKNOWN
          - skill: saas-metrics-coach
            path: skills/business/finance/saas-metrics-coach/SKILL.md
            status: UNKNOWN
      marketing-skill:
        path: skills/business/marketing-skill/
        skill_count: 45
        skills:
          - skill: marketing-skill
            path: skills/business/marketing-skill/SKILL.md
            status: UNKNOWN
          - skill: ab-test-setup
            path: skills/business/marketing-skill/ab-test-setup/SKILL.md
            status: UNKNOWN
          - skill: ad-creative
            path: skills/business/marketing-skill/ad-creative/SKILL.md
            status: UNKNOWN
          - skill: ai-seo
            path: skills/business/marketing-skill/ai-seo/SKILL.md
            status: UNKNOWN
          - skill: analytics-tracking
            path: skills/business/marketing-skill/analytics-tracking/SKILL.md
            status: UNKNOWN
          # ... +40 skills adicionais
      personas:
        path: skills/business/personas/
        skill_count: 23
        skills:
          - skill: business.personas.personas.content_strategist
            path: skills/business/personas/content-strategist/SKILL.md
            status: CANDIDATE
          - skill: business.personas.product.cs_agile_product_owner
            path: skills/business/personas/cs-agile-product-owner/SKILL.md
            status: CANDIDATE
          - skill: business.personas.c-level.cs_ceo_advisor
            path: skills/business/personas/cs-ceo-advisor/SKILL.md
            status: CANDIDATE
          - skill: business.personas.marketing.cs_content_creator
            path: skills/business/personas/cs-content-creator/SKILL.md
            status: CANDIDATE
          - skill: business.personas.c-level.cs_cto_advisor
            path: skills/business/personas/cs-cto-advisor/SKILL.md
            status: CANDIDATE
          # ... +18 skills adicionais
      product-team:
        path: skills/business/product-team/
        skill_count: 16
        skills:
          - skill: product-team
            path: skills/business/product-team/SKILL.md
            status: UNKNOWN
          - skill: agile-product-owner
            path: skills/business/product-team/agile-product-owner/SKILL.md
            status: UNKNOWN
          - skill: code-to-prd
            path: skills/business/product-team/code-to-prd/SKILL.md
            status: UNKNOWN
          - skill: competitive-teardown
            path: skills/business/product-team/competitive-teardown/SKILL.md
            status: UNKNOWN
          - skill: experiment-designer
            path: skills/business/product-team/experiment-designer/SKILL.md
            status: UNKNOWN
          # ... +11 skills adicionais
      project-management:
        path: skills/business/project-management/
        skill_count: 9
        skills:
          - skill: project-management
            path: skills/business/project-management/SKILL.md
            status: UNKNOWN
          - skill: atlassian-admin
            path: skills/business/project-management/atlassian-admin/SKILL.md
            status: UNKNOWN
          - skill: atlassian-templates
            path: skills/business/project-management/atlassian-templates/SKILL.md
            status: UNKNOWN
          - skill: confluence-expert
            path: skills/business/project-management/confluence-expert/SKILL.md
            status: UNKNOWN
          - skill: jira-expert
            path: skills/business/project-management/jira-expert/SKILL.md
            status: UNKNOWN
          # ... +4 skills adicionais
      ra-qm-team:
        path: skills/business/ra-qm-team/
        skill_count: 14
        skills:
          - skill: ra-qm-team
            path: skills/business/ra-qm-team/SKILL.md
            status: UNKNOWN
          - skill: capa-officer
            path: skills/business/ra-qm-team/capa-officer/SKILL.md
            status: UNKNOWN
          - skill: fda-consultant-specialist
            path: skills/business/ra-qm-team/fda-consultant-specialist/SKILL.md
            status: UNKNOWN
          - skill: gdpr-dsgvo-expert
            path: skills/business/ra-qm-team/gdpr-dsgvo-expert/SKILL.md
            status: UNKNOWN
          - skill: information-security-manager-iso27001
            path: skills/business/ra-qm-team/information-security-manager-iso27001/SKILL.md
            status: UNKNOWN
          # ... +9 skills adicionais
      startup:
        path: skills/business/startup/
        skill_count: 5
        skills:
          - skill: business.startup.market_sizing_analysis
            path: skills/business/startup/market-sizing-analysis/SKILL.md
            status: CANDIDATE
            anchors: [market, sizing, analysis, comprehensive, methodologies]
          - skill: business.startup.startup_analyst
            path: skills/business/startup/startup-analyst/SKILL.md
            status: CANDIDATE
            anchors: [startup, analyst, expert, business, specializing]
          - skill: business.startup.startup_financial_modeling
            path: skills/business/startup/startup-financial-modeling/SKILL.md
            status: CANDIDATE
            anchors: [startup, financial, modeling, build, comprehensive]
          - skill: business.startup.startup_metrics_framework
            path: skills/business/startup/startup-metrics-framework/SKILL.md
            status: CANDIDATE
            anchors: [startup, metrics, framework, comprehensive, guide]
          - skill: business.startup.team_composition_analysis
            path: skills/business/startup/team-composition-analysis/SKILL.md
            status: CANDIDATE
            anchors: [team, composition, analysis, design, optimal]

  BUSINESS_CONTENT:
    path: skills/business_content/
    display_name: "Business — Content"
    skill_count: 6
    anchors: [writer, agile, product, owner, ownership, backlog, management, agile-product-owner, for, changelog, generator, automatically, creates, facing, changelog-generator]
    sub_domains:
      agile-product-owner:
        path: skills/business_content/agile-product-owner/
        skill_count: 1
        skills:
          - skill: business_content.agile_product_owner
            path: skills/business_content/agile-product-owner/SKILL.md
            status: CANDIDATE
            anchors: [agile, product, owner, ownership, backlog]
      changelog-generator:
        path: skills/business_content/changelog-generator/
        skill_count: 1
        skills:
          - skill: business_content.changelog_generator
            path: skills/business_content/changelog-generator/SKILL.md
            status: CANDIDATE
            anchors: [changelog, generator, automatically, creates, facing]
      content-research-writer:
        path: skills/business_content/content-research-writer/
        skill_count: 1
        skills:
          - skill: business_content.content_research_writer
            path: skills/business_content/content-research-writer/SKILL.md
            status: CANDIDATE
            anchors: [content, research, writer, assists, writing]
      image-enhancer:
        path: skills/business_content/image-enhancer/
        skill_count: 1
        skills:
          - skill: business_content.image_enhancer
            path: skills/business_content/image-enhancer/SKILL.md
            status: CANDIDATE
            anchors: [image, enhancer, improves, quality, images]
      twitter-algorithm-optimizer:
        path: skills/business_content/twitter-algorithm-optimizer/
        skill_count: 1
        skills:
          - skill: business_content.twitter_algorithm_optimizer
            path: skills/business_content/twitter-algorithm-optimizer/SKILL.md
            status: CANDIDATE
            anchors: [twitter, algorithm, optimizer, analyze, optimize]
      wiki-page-writer:
        path: skills/business_content/wiki-page-writer/
        skill_count: 1
        skills:
          - skill: business_content.wiki_page_writer
            path: skills/business_content/wiki-page-writer/SKILL.md
            status: CANDIDATE
            anchors: [wiki, page, writer, generates, rich]

  BUSINESS_HUMAN_RESOURCES:
    path: skills/business_human_resources/
    display_name: "Business — Human Resources"
    skill_count: 6
    anchors: [risk, for, when, codebase, onboarding, codebase-onboarding, template, overview, core, capabilities, quick, composio, skills, automate, tasks]
    sub_domains:
      codebase-onboarding:
        path: skills/business_human_resources/codebase-onboarding/
        skill_count: 1
        skills:
          - skill: business_human_resources.codebase_onboarding
            path: skills/business_human_resources/codebase-onboarding/SKILL.md
            status: CANDIDATE
            anchors: [codebase, onboarding, codebase-onboarding, template, overview]
      composio-skills:
        path: skills/business_human_resources/composio-skills/
        skill_count: 1
        skills:
          - skill: business_human_resources.composio_skills
            path: skills/business_human_resources/composio-skills/SKILL.md
            status: CANDIDATE
            anchors: [composio, skills, automate, risk, tasks]
      risk-management-specialist:
        path: skills/business_human_resources/risk-management-specialist/
        skill_count: 1
        skills:
          - skill: business_human_resources.risk_management_specialist
            path: skills/business_human_resources/risk-management-specialist/SKILL.md
            status: CANDIDATE
            anchors: [risk, management, specialist, medical, device]
      scrum-master:
        path: skills/business_human_resources/scrum-master/
        skill_count: 1
        skills:
          - skill: business_human_resources.scrum_master
            path: skills/business_human_resources/scrum-master/SKILL.md
            status: CANDIDATE
            anchors: [scrum, master, advanced, skill, data]
      signup-flow-cro:
        path: skills/business_human_resources/signup-flow-cro/
        skill_count: 1
        skills:
          - skill: business_human_resources.signup_flow_cro
            path: skills/business_human_resources/signup-flow-cro/SKILL.md
            status: CANDIDATE
            anchors: [signup, flow, when, optimize, signup-flow-cro]
      threat-detection:
        path: skills/business_human_resources/threat-detection/
        skill_count: 1
        skills:
          - skill: business_human_resources.threat_detection
            path: skills/business_human_resources/threat-detection/SKILL.md
            status: CANDIDATE
            anchors: [threat, detection, when, hunting, threats]

  BUSINESS_PRODUCTIVITY:
    path: skills/business_productivity/
    display_name: "Business — Productivity"
    skill_count: 9
    anchors: [when, the, create, for, tracker, technical, composio, skills, braintree, automation, manage, payment, processing, via, file]
    sub_domains:
      composio-skills:
        path: skills/business_productivity/composio-skills/
        skill_count: 1
        skills:
          - skill: business_productivity.composio_skills
            path: skills/business_productivity/composio-skills/SKILL.md
            status: CANDIDATE
            anchors: [composio, skills, braintree, automation, manage]
      file-organizer:
        path: skills/business_productivity/file-organizer/
        skill_count: 1
        skills:
          - skill: business_productivity.file_organizer
            path: skills/business_productivity/file-organizer/SKILL.md
            status: CANDIDATE
            anchors: [file, organizer, intelligently, organizes, your]
      gh-create-issue:
        path: skills/business_productivity/gh-create-issue/
        skill_count: 1
        skills:
          - skill: business_productivity.gh_create_issue
            path: skills/business_productivity/gh-create-issue/SKILL.md
            status: CANDIDATE
            anchors: [create, issue, when, github, gh-create-issue]
      prepare-release:
        path: skills/business_productivity/prepare-release/
        skill_count: 1
        skills:
          - skill: business_productivity.prepare_release
            path: skills/business_productivity/prepare-release/SKILL.md
            status: CANDIDATE
            anchors: [prepare, release, collecting, commits, generating]
      qms-audit-expert:
        path: skills/business_productivity/qms-audit-expert/
        skill_count: 1
        skills:
          - skill: business_productivity.qms_audit_expert
            path: skills/business_productivity/qms-audit-expert/SKILL.md
            status: CANDIDATE
            anchors: [audit, expert, internal, expertise, medical]
      report:
        path: skills/business_productivity/report/
        skill_count: 1
        skills:
          - skill: business_productivity.report
            path: skills/business_productivity/report/SKILL.md
            status: CANDIDATE
            anchors: [report, tests, test, run, results]
      spec-driven-workflow:
        path: skills/business_productivity/spec-driven-workflow/
        skill_count: 1
        skills:
          - skill: business_productivity.spec_driven_workflow
            path: skills/business_productivity/spec-driven-workflow/SKILL.md
            status: CANDIDATE
            anchors: [spec, driven, workflow, when, spec-driven-workflow]
      tc-tracker:
        path: skills/business_productivity/tc-tracker/
        skill_count: 1
        skills:
          - skill: business_productivity.tc_tracker
            path: skills/business_productivity/tc-tracker/SKILL.md
            status: CANDIDATE
            anchors: [tracker, when, track, technical, tc-tracker]
      tech-debt-tracker:
        path: skills/business_productivity/tech-debt-tracker/
        skill_count: 1
        skills:
          - skill: business_productivity.tech_debt_tracker
            path: skills/business_productivity/tech-debt-tracker/SKILL.md
            status: CANDIDATE
            anchors: [tech, debt, tracker, scan, codebases]

  BUSINESS_SALES:
    path: skills/business_sales/
    display_name: "Business — Sales"
    skill_count: 4
    anchors: [competitive, intel, systematic, competitor, tracking, that, competitive-intel, feeds, composio, skills, automate, attio, operations, search, automation]
    sub_domains:
      competitive-intel:
        path: skills/business_sales/competitive-intel/
        skill_count: 1
        skills:
          - skill: business_sales.competitive_intel
            path: skills/business_sales/competitive-intel/SKILL.md
            status: CANDIDATE
            anchors: [competitive, intel, systematic, competitor, tracking]
      composio-skills:
        path: skills/business_sales/composio-skills/
        skill_count: 1
        skills:
          - skill: business_sales.composio_skills
            path: skills/business_sales/composio-skills/SKILL.md
            status: CANDIDATE
            anchors: [composio, skills, automate, attio, operations]
      ma-playbook:
        path: skills/business_sales/ma-playbook/
        skill_count: 1
        skills:
          - skill: business_sales.ma_playbook
            path: skills/business_sales/ma-playbook/SKILL.md
            status: CANDIDATE
            anchors: [playbook, strategy, acquiring, companies, being]
      postmortem:
        path: skills/business_sales/postmortem/
        skill_count: 1
        skills:
          - skill: business_sales.postmortem
            path: skills/business_sales/postmortem/SKILL.md
            status: CANDIDATE
            anchors: [postmortem, honest, analysis, what, went]

  CLAUDE_SKILLS_M:
    path: skills/claude_skills_m/
    display_name: "Claude Skills (M)"
    skill_count: 9
    anchors: [when, the, copy, review, improve, marketing, optimize, for, changelog, generator, changelog-generator, generate, entry, overview, core]
    sub_domains:
      business_content:
        path: skills/claude_skills_m/business_content/
        skill_count: 1
        skills:
          - skill: claude_skills_m.business_content.changelog_generator
            path: skills/claude_skills_m/business_content/changelog-generator/SKILL.md
            status: CANDIDATE
            anchors: [changelog, generator, changelog-generator, generate, entry]
      marketing:
        path: skills/claude_skills_m/marketing/
        skill_count: 8
        skills:
          - skill: claude_skills_m.marketing.brand_guidelines
            path: skills/claude_skills_m/marketing/brand-guidelines/SKILL.md
            status: CANDIDATE
            anchors: [brand, guidelines, when, apply, brand-guidelines]
          - skill: claude_skills_m.marketing.copy_editing
            path: skills/claude_skills_m/marketing/copy-editing/SKILL.md
            status: CANDIDATE
            anchors: [copy, editing, when, edit, copy-editing]
          - skill: claude_skills_m.marketing.copywriting
            path: skills/claude_skills_m/marketing/copywriting/SKILL.md
            status: CANDIDATE
            anchors: [copywriting, when, write, rewrite, the]
          - skill: claude_skills_m.marketing.email_sequence
            path: skills/claude_skills_m/marketing/email-sequence/SKILL.md
            status: CANDIDATE
            anchors: [email, sequence, when, create, email-sequence]
          - skill: claude_skills_m.marketing.free_tool_strategy
            path: skills/claude_skills_m/marketing/free-tool-strategy/SKILL.md
            status: CANDIDATE
            anchors: [free, tool, strategy, when, free-tool-strategy]
          # ... +3 skills adicionais

  COMMUNITY:
    path: skills/community/
    display_name: "Community"
    skill_count: 414
    anchors: [expert, skill, patterns, code, design, building, specializing, build, context, sentence, does, invoke, development, create, principles]
    sub_domains:
      general:
        path: skills/community/general/
        skill_count: 414
        skills:
          - skill: community.general.00_andruia_consultant
            path: skills/community/general/00-andruia-consultant/SKILL.md
            status: CANDIDATE
            anchors: [andruia, consultant, arquitecto, soluciones, principal]
          - skill: community.general.10_andruia_skill_smith
            path: skills/community/general/10-andruia-skill-smith/SKILL.md
            status: CANDIDATE
            anchors: [andruia, skill, smith, ingeniero, sistemas]
          - skill: community.general.2d_games
            path: skills/community/general/2d-games/SKILL.md
            status: CANDIDATE
            anchors: [games, game, development, principles, sprites]
          - skill: community.general.3d_games
            path: skills/community/general/3d-games/SKILL.md
            status: CANDIDATE
            anchors: [games, game, development, principles, rendering]
          - skill: community.general.ab_test_setup
            path: skills/community/general/ab-test-setup/SKILL.md
            status: CANDIDATE
            anchors: [test, setup, structured, guide, setting]
          # ... +409 skills adicionais

  COMMUNITY_GENERAL:
    path: skills/community_general/
    display_name: "Community — General"
    skill_count: 27
    anchors: [for, memory, analyzes, and, patterns, including, auto, auto-memory, analysis, claude, generates, proven, pattern, test, infrastructure]
    sub_domains:
      capa-officer:
        path: skills/community_general/capa-officer/
        skill_count: 1
        skills:
          - skill: community_general.capa_officer
            path: skills/community_general/capa-officer/SKILL.md
            status: CANDIDATE
            anchors: [capa, officer, system, management, medical]
      data-quality-auditor:
        path: skills/community_general/data-quality-auditor/
        skill_count: 1
        skills:
          - skill: community_general.data_quality_auditor
            path: skills/community_general/data-quality-auditor/SKILL.md
            status: CANDIDATE
            anchors: [data, quality, auditor, audit, datasets]
      decision-logger:
        path: skills/community_general/decision-logger/
        skill_count: 1
        skills:
          - skill: community_general.decision_logger
            path: skills/community_general/decision-logger/SKILL.md
            status: CANDIDATE
            anchors: [decision, logger, layer, memory, architecture]
      developer-growth-analysis:
        path: skills/community_general/developer-growth-analysis/
        skill_count: 1
        skills:
          - skill: community_general.developer_growth_analysis
            path: skills/community_general/developer-growth-analysis/SKILL.md
            status: CANDIDATE
            anchors: [developer, growth, analysis, analyzes, your]
      domain-name-brainstormer:
        path: skills/community_general/domain-name-brainstormer/
        skill_count: 1
        skills:
          - skill: community_general.domain_name_brainstormer
            path: skills/community_general/domain-name-brainstormer/SKILL.md
            status: CANDIDATE
            anchors: [domain, name, brainstormer, generates, creative]
      extract:
        path: skills/community_general/extract/
        skill_count: 1
        skills:
          - skill: community_general.extract
            path: skills/community_general/extract/SKILL.md
            status: CANDIDATE
            anchors: [extract, turn, proven, pattern, debugging]
      faq-collector:
        path: skills/community_general/faq-collector/
        skill_count: 1
        skills:
          - skill: community_general.faq_collector
            path: skills/community_general/faq-collector/SKILL.md
            status: CANDIDATE
            anchors: [collector, faq-collector, faq, add, issue]
      fix:
        path: skills/community_general/fix/
        skill_count: 1
        skills:
          - skill: community_general.fix
            path: skills/community_general/fix/SKILL.md
            status: CANDIDATE
            anchors: [fix, failure, timing, async, test]
      founder-coach:
        path: skills/community_general/founder-coach/
        skill_count: 1
        skills:
          - skill: community_general.founder_coach
            path: skills/community_general/founder-coach/SKILL.md
            status: CANDIDATE
            anchors: [founder, coach, personal, leadership, development]
      generate:
        path: skills/community_general/generate/
        skill_count: 1
        skills:
          - skill: community_general.generate
            path: skills/community_general/generate/SKILL.md
            status: CANDIDATE
            anchors: [generate, explore, test, page, $arguments]
      internal-comms:
        path: skills/community_general/internal-comms/
        skill_count: 1
        skills:
          - skill: community_general.internal_comms
            path: skills/community_general/internal-comms/SKILL.md
            status: CANDIDATE
            anchors: [internal, comms, resources, write, kinds]
      meeting-insights-analyzer:
        path: skills/community_general/meeting-insights-analyzer/
        skill_count: 1
        skills:
          - skill: community_general.meeting_insights_analyzer
            path: skills/community_general/meeting-insights-analyzer/SKILL.md
            status: CANDIDATE
            anchors: [meeting, insights, analyzer, analyzes, transcripts]
      migration-architect:
        path: skills/community_general/migration-architect/
        skill_count: 1
        skills:
          - skill: community_general.migration_architect
            path: skills/community_general/migration-architect/SKILL.md
            status: CANDIDATE
            anchors: [migration, architect, migration-architect, rollback, validation]
      nextjs-mastery:
        path: skills/community_general/nextjs-mastery/
        skill_count: 1
        skills:
          - skill: community_general.nextjs_mastery
            path: skills/community_general/nextjs-mastery/SKILL.md
            status: CANDIDATE
            anchors: [nextjs, mastery, next, router, patterns]
      performance-optimization:
        path: skills/community_general/performance-optimization/
        skill_count: 1
        skills:
          - skill: community_general.performance_optimization
            path: skills/community_general/performance-optimization/SKILL.md
            status: CANDIDATE
            anchors: [performance, optimization, including, bundle, analysis]
      promote:
        path: skills/community_general/promote/
        skill_count: 1
        skills:
          - skill: community_general.promote
            path: skills/community_general/promote/SKILL.md
            status: CANDIDATE
            anchors: [promote, graduate, proven, pattern, auto]
      remember:
        path: skills/community_general/remember/
        skill_count: 1
        skills:
          - skill: community_general.remember
            path: skills/community_general/remember/SKILL.md
            status: CANDIDATE
            anchors: [remember, explicitly, save, important, knowledge]
      review:
        path: skills/community_general/review/
        skill_count: 1
        skills:
          - skill: community_general.review
            path: skills/community_general/review/SKILL.md
            status: CANDIDATE
            anchors: [review, analyze, auto, memory, promotion]
      skill-creator:
        path: skills/community_general/skill-creator/
        skill_count: 1
        skills:
          - skill: community_general.skill_creator
            path: skills/community_general/skill-creator/SKILL.md
            status: CANDIDATE
            anchors: [skill, creator, create, skills, modify]
      slack-gif-creator:
        path: skills/community_general/slack-gif-creator/
        skill_count: 1
        skills:
          - skill: community_general.slack_gif_creator
            path: skills/community_general/slack-gif-creator/SKILL.md
            status: CANDIDATE
            anchors: [slack, creator, toolkit, creating, animated]
      status:
        path: skills/community_general/status/
        skill_count: 1
        skills:
          - skill: community_general.status
            path: skills/community_general/status/SKILL.md
            status: CANDIDATE
            anchors: [status, show, experiment, dashboard, results]
      stripe-integration-expert:
        path: skills/community_general/stripe-integration-expert/
        skill_count: 1
        skills:
          - skill: community_general.stripe_integration_expert
            path: skills/community_general/stripe-integration-expert/SKILL.md
            status: CANDIDATE
            anchors: [stripe, integration, expert, stripe-integration-expert, subscription]
      tailored-resume-generator:
        path: skills/community_general/tailored-resume-generator/
        skill_count: 1
        skills:
          - skill: community_general.tailored_resume_generator
            path: skills/community_general/tailored-resume-generator/SKILL.md
            status: CANDIDATE
            anchors: [tailored, resume, generator, analyzes, descriptions]
      template-skill:
        path: skills/community_general/template-skill/
        skill_count: 1
        skills:
          - skill: community_general.template_skill
            path: skills/community_general/template-skill/SKILL.md
            status: CANDIDATE
            anchors: [template, skill, replace, description, when]
      typescript-advanced:
        path: skills/community_general/typescript-advanced/
        skill_count: 1
        skills:
          - skill: community_general.typescript_advanced
            path: skills/community_general/typescript-advanced/SKILL.md
            status: CANDIDATE
            anchors: [typescript, advanced, patterns, including, generics]
      websocket-realtime:
        path: skills/community_general/websocket-realtime/
        skill_count: 1
        skills:
          - skill: community_general.websocket_realtime
            path: skills/community_general/websocket-realtime/SKILL.md
            status: CANDIDATE
            anchors: [websocket, realtime, real, time, communication]
      wiki-qa:
        path: skills/community_general/wiki-qa/
        skill_count: 1
        skills:
          - skill: community_general.wiki_qa
            path: skills/community_general/wiki-qa/SKILL.md
            status: CANDIDATE
            anchors: [wiki, answers, questions, about, code]

  CUSTOMER_SUPPORT:
    path: skills/customer-support/
    display_name: "Customer Support"
    skill_count: 6
    anchors: [customer, issue, question, draft, ticket, triage, prioritize, support, comes, needs, escalation, package, engineering, product, leadership]
    sub_domains:
      customer-escalation:
        path: skills/customer-support/customer-escalation/
        skill_count: 1
        skills:
          - skill: customer_support.customer_escalation
            path: skills/customer-support/customer-escalation/SKILL.md
            status: ADOPTED
            anchors: [customer, escalation, package, engineering, product]
      customer-research:
        path: skills/customer-support/customer-research/
        skill_count: 1
        skills:
          - skill: customer_support.customer_research
            path: skills/customer-support/customer-research/SKILL.md
            status: ADOPTED
            anchors: [customer, research, multi, source, question]
      draft-response:
        path: skills/customer-support/draft-response/
        skill_count: 1
        skills:
          - skill: customer_support.draft_response
            path: skills/customer-support/draft-response/SKILL.md
            status: ADOPTED
            anchors: [draft, response, professional, customer, facing]
      kb-article:
        path: skills/customer-support/kb-article/
        skill_count: 1
        skills:
          - skill: customer_support.kb_article
            path: skills/customer-support/kb-article/SKILL.md
            status: ADOPTED
            anchors: [article, draft, knowledge, base, resolved]
      skills:
        path: skills/customer-support/skills/
        skill_count: 1
        skills:
          - skill: customer_support.skills
            path: skills/customer-support/skills/SKILL.md
            status: ADOPTED
            anchors: [ticket, triage, prioritize, support, customer]
      ticket-triage:
        path: skills/customer-support/ticket-triage/
        skill_count: 1
        skills:
          - skill: customer_support.ticket_triage
            path: skills/customer-support/ticket-triage/SKILL.md
            status: ADOPTED
            anchors: [ticket, triage, prioritize, support, customer]

  DATA:
    path: skills/data/
    display_name: "Data"
    skill_count: 34
    anchors: [odoo, expert, guide, database, optimization, postgres, databases, workflow, design, migrations, postgresql, patterns, best, custom, inventory]
    sub_domains:
      databases:
        path: skills/data/databases/
        skill_count: 15
        skills:
          - skill: data.databases.cache.debug_buttercup
            path: skills/data/databases/cache/debug-buttercup/SKILL.md
            status: CANDIDATE
            anchors: [debug, buttercup, pods, namespace, crashloopbackoff]
          - skill: data.databases.sql.claimable_postgres
            path: skills/data/databases/sql/claimable-postgres/SKILL.md
            status: CANDIDATE
            anchors: [claimable, postgres, provision, instant, temporary]
          - skill: data.databases.sql.database
            path: skills/data/databases/sql/database/SKILL.md
            status: CANDIDATE
            anchors: [database, development, operations, workflow, covering]
          - skill: data.databases.sql.database_migrations_sql_migrations
            path: skills/data/databases/sql/database-migrations-sql-migrations/SKILL.md
            status: CANDIDATE
            anchors: [database, migrations, zero, downtime, strategies]
          - skill: data.databases.sql.neon_postgres
            path: skills/data/databases/sql/neon-postgres/SKILL.md
            status: CANDIDATE
            anchors: [neon, postgres, expert, patterns, serverless]
          # ... +10 skills adicionais
      erp:
        path: skills/data/erp/
        skill_count: 19
        skills:
          - skill: data.erp.odoo_accounting_setup
            path: skills/data/erp/odoo-accounting-setup/SKILL.md
            status: CANDIDATE
            anchors: [odoo, accounting, setup, expert, guide]
          - skill: data.erp.odoo_automated_tests
            path: skills/data/erp/odoo-automated-tests/SKILL.md
            status: CANDIDATE
            anchors: [odoo, automated, tests, write, transactioncase]
          - skill: data.erp.odoo_edi_connector
            path: skills/data/erp/odoo-edi-connector/SKILL.md
            status: CANDIDATE
            anchors: [odoo, connector, guide, implementing, electronic]
          - skill: data.erp.odoo_hr_payroll_setup
            path: skills/data/erp/odoo-hr-payroll-setup/SKILL.md
            status: CANDIDATE
            anchors: [odoo, payroll, setup, expert, guide]
          - skill: data.erp.odoo_inventory_optimizer
            path: skills/data/erp/odoo-inventory-optimizer/SKILL.md
            status: CANDIDATE
            anchors: [odoo, inventory, optimizer, expert, guide]
          # ... +14 skills adicionais

  DATA_SCIENCE:
    path: skills/data-science/
    display_name: "Data Science"
    skill_count: 11
    anchors: [data, query, write, create, quality, visualizations, python, optimized, dialect, best, practices, translating, natural, analysis, analyze]
    sub_domains:
      analytics:
        path: skills/data-science/analytics/
        skill_count: 11
        skills:
          - skill: data_science.analytics.analyze
            path: skills/data-science/analytics/analyze/SKILL.md
            status: ADOPTED
            anchors: [analyze, answer, data, questions, quick]
          - skill: data_science.analytics.build_dashboard
            path: skills/data-science/analytics/build-dashboard/SKILL.md
            status: ADOPTED
            anchors: [build, dashboard, interactive, html, charts]
          - skill: data_science.analytics.create_viz
            path: skills/data-science/analytics/create-viz/SKILL.md
            status: ADOPTED
            anchors: [create, publication, quality, visualizations, python]
          - skill: data_science.analytics.data_context_extractor
            path: skills/data-science/analytics/data-context-extractor/SKILL.md
            status: ADOPTED
            anchors: [data, context, extractor, meta, skill]
          - skill: data_science.analytics.data_visualization
            path: skills/data-science/analytics/data-visualization/SKILL.md
            status: ADOPTED
            anchors: [data, visualization, create, effective, visualizations]
          # ... +6 skills adicionais

  DESIGN:
    path: skills/design/
    display_name: "Design"
    skill_count: 73
    anchors: [design, for, apple, and, when, the, components, guidance, interface, advisor, leadership, patterns, product, human, guidelines]
    sub_domains:
      atlassian-templates:
        path: skills/design/atlassian-templates/
        skill_count: 1
        skills:
          - skill: design.atlassian_templates
            path: skills/design/atlassian-templates/SKILL.md
            status: CANDIDATE
            anchors: [atlassian, templates, template, files, creator]
      board-deck-builder:
        path: skills/design/board-deck-builder/
        skill_count: 1
        skills:
          - skill: design.board_deck_builder
            path: skills/design/board-deck-builder/SKILL.md
            status: CANDIDATE
            anchors: [board, deck, builder, assembles, comprehensive]
      business-investment-advisor:
        path: skills/design/business-investment-advisor/
        skill_count: 1
        skills:
          - skill: design.business_investment_advisor
            path: skills/design/business-investment-advisor/SKILL.md
            status: CANDIDATE
            anchors: [business, investment, advisor, analysis, capital]
      ceo-advisor:
        path: skills/design/ceo-advisor/
        skill_count: 1
        skills:
          - skill: design.ceo_advisor
            path: skills/design/ceo-advisor/SKILL.md
            status: CANDIDATE
            anchors: [advisor, executive, leadership, guidance, strategic]
      churn-prevention:
        path: skills/design/churn-prevention/
        skill_count: 1
        skills:
          - skill: design.churn_prevention
            path: skills/design/churn-prevention/SKILL.md
            status: CANDIDATE
            anchors: [churn, prevention, reduce, voluntary, involuntary]
      code-tour:
        path: skills/design/code-tour/
        skill_count: 1
        skills:
          - skill: design.code_tour
            path: skills/design/code-tour/SKILL.md
            status: CANDIDATE
            anchors: [code, tour, when, create, code-tour]
      company-os:
        path: skills/design/company-os/
        skill_count: 1
        skills:
          - skill: design.company_os
            path: skills/design/company-os/SKILL.md
            status: CANDIDATE
            anchors: [company, meta, framework, runs, connective]
      composio-skills:
        path: skills/design/composio-skills/
        skill_count: 1
        skills:
          - skill: design.composio_skills
            path: skills/design/composio-skills/SKILL.md
            status: CANDIDATE
            anchors: [composio, skills, automate, ably, tasks]
      connect-apps:
        path: skills/design/connect-apps/
        skill_count: 1
        skills:
          - skill: design.connect_apps
            path: skills/design/connect-apps/SKILL.md
            status: CANDIDATE
            anchors: [apps, claude, external, like, gmail]
      continuous-learning:
        path: skills/design/continuous-learning/
        skill_count: 1
        skills:
          - skill: design.continuous_learning
            path: skills/design/continuous-learning/SKILL.md
            status: CANDIDATE
            anchors: [continuous, learning, auto, extract, patterns]
      coo-advisor:
        path: skills/design/coo-advisor/
        skill_count: 1
        skills:
          - skill: design.coo_advisor
            path: skills/design/coo-advisor/SKILL.md
            status: CANDIDATE
            anchors: [advisor, operations, leadership, scaling, companies]
      cpo-advisor:
        path: skills/design/cpo-advisor/
        skill_count: 1
        skills:
          - skill: design.cpo_advisor
            path: skills/design/cpo-advisor/SKILL.md
            status: CANDIDATE
            anchors: [advisor, product, leadership, scaling, companies]
      cs-onboard:
        path: skills/design/cs-onboard/
        skill_count: 1
        skills:
          - skill: design.cs_onboard
            path: skills/design/cs-onboard/SKILL.md
            status: CANDIDATE
            anchors: [onboard, founder, onboarding, interview, that]
      cto-advisor:
        path: skills/design/cto-advisor/
        skill_count: 1
        skills:
          - skill: design.cto_advisor
            path: skills/design/cto-advisor/SKILL.md
            status: CANDIDATE
            anchors: [advisor, technical, leadership, guidance, engineering]
      culture-architect:
        path: skills/design/culture-architect/
        skill_count: 1
        skills:
          - skill: design.culture_architect
            path: skills/design/culture-architect/SKILL.md
            status: CANDIDATE
            anchors: [culture, architect, build, measure, evolve]
      document-skills:
        path: skills/design/document-skills/
        skill_count: 1
        skills:
          - skill: design.document_skills
            path: skills/design/document-skills/SKILL.md
            status: CANDIDATE
            anchors: [document, skills, comprehensive, manipulation, toolkit]
      email-template-builder:
        path: skills/design/email-template-builder/
        skill_count: 1
        skills:
          - skill: design.email_template_builder
            path: skills/design/email-template-builder/SKILL.md
            status: CANDIDATE
            anchors: [email, template, builder, email-template-builder, overview]
      executive-mentor:
        path: skills/design/executive-mentor/
        skill_count: 1
        skills:
          - skill: design.executive_mentor
            path: skills/design/executive-mentor/SKILL.md
            status: CANDIDATE
            anchors: [executive, mentor, adversarial, thinking, partner]
      experiment-designer:
        path: skills/design/experiment-designer/
        skill_count: 1
        skills:
          - skill: design.experiment_designer
            path: skills/design/experiment-designer/SKILL.md
            status: CANDIDATE
            anchors: [experiment, designer, when, planning, product]
      focused-fix:
        path: skills/design/focused-fix/
        skill_count: 1
        skills:
          - skill: design.focused_fix
            path: skills/design/focused-fix/SKILL.md
            status: CANDIDATE
            anchors: [focused, when, debug, make, focused-fix]
      gdpr-dsgvo-expert:
        path: skills/design/gdpr-dsgvo-expert/
        skill_count: 1
        skills:
          - skill: design.gdpr_dsgvo_expert
            path: skills/design/gdpr-dsgvo-expert/SKILL.md
            status: CANDIDATE
            anchors: [gdpr, dsgvo, expert, german, compliance]
      internal-narrative:
        path: skills/design/internal-narrative/
        skill_count: 1
        skills:
          - skill: design.internal_narrative
            path: skills/design/internal-narrative/SKILL.md
            status: CANDIDATE
            anchors: [internal, narrative, build, maintain, coherent]
      intl-expansion:
        path: skills/design/intl-expansion/
        skill_count: 1
        skills:
          - skill: design.intl_expansion
            path: skills/design/intl-expansion/SKILL.md
            status: CANDIDATE
            anchors: [intl, expansion, international, market, strategy]
      ios-hig:
        path: skills/design/ios-hig/
        skill_count: 10
        skills:
          - skill: design.ios_hig.hig_components_content
            path: skills/design/ios-hig/hig-components-content/SKILL.md
            status: CANDIDATE
            anchors: [components, content, apple, human, interface]
          - skill: design.ios_hig.hig_components_dialogs
            path: skills/design/ios-hig/hig-components-dialogs/SKILL.md
            status: CANDIDATE
            anchors: [components, dialogs, apple, guidance, presentation]
          - skill: design.ios_hig.hig_components_layout
            path: skills/design/ios-hig/hig-components-layout/SKILL.md
            status: CANDIDATE
            anchors: [components, layout, apple, human, interface]
          - skill: design.ios_hig.hig_components_search
            path: skills/design/ios-hig/hig-components-search/SKILL.md
            status: CANDIDATE
            anchors: [components, search, apple, guidance, navigation]
          - skill: design.ios_hig.hig_components_status
            path: skills/design/ios-hig/hig-components-status/SKILL.md
            status: CANDIDATE
            anchors: [components, status, apple, guidance, progress]
          # ... +5 skills adicionais
      jira-expert:
        path: skills/design/jira-expert/
        skill_count: 1
        skills:
          - skill: design.jira_expert
            path: skills/design/jira-expert/SKILL.md
            status: CANDIDATE
            anchors: [jira, expert, atlassian, creating, managing]
      mcp-server-builder:
        path: skills/design/mcp-server-builder/
        skill_count: 1
        skills:
          - skill: design.mcp_server_builder
            path: skills/design/mcp-server-builder/SKILL.md
            status: CANDIDATE
            anchors: [server, builder, mcp-server-builder, mcp, strategy]
      microservices-design:
        path: skills/design/microservices-design/
        skill_count: 1
        skills:
          - skill: design.microservices_design
            path: skills/design/microservices-design/SKILL.md
            status: CANDIDATE
            anchors: [microservices, design, patterns, including, service]
      migrate:
        path: skills/design/migrate/
        skill_count: 1
        skills:
          - skill: design.migrate
            path: skills/design/migrate/SKILL.md
            status: CANDIDATE
            anchors: [migrate, playwright, convert, custom, commands]
      monorepo-navigator:
        path: skills/design/monorepo-navigator/
        skill_count: 1
        skills:
          - skill: design.monorepo_navigator
            path: skills/design/monorepo-navigator/SKILL.md
            status: CANDIDATE
            anchors: [monorepo, navigator, monorepo-navigator, turborepo, claude]
      observability-designer:
        path: skills/design/observability-designer/
        skill_count: 1
        skills:
          - skill: design.observability_designer
            path: skills/design/observability-designer/SKILL.md
            status: CANDIDATE
            anchors: [observability, designer, powerful, observability-designer, metrics]
      onboarding-cro:
        path: skills/design/onboarding-cro/
        skill_count: 1
        skills:
          - skill: design.onboarding_cro
            path: skills/design/onboarding-cro/SKILL.md
            status: CANDIDATE
            anchors: [onboarding, when, optimize, post, onboarding-cro]
      org-health-diagnostic:
        path: skills/design/org-health-diagnostic/
        skill_count: 1
        skills:
          - skill: design.org_health_diagnostic
            path: skills/design/org-health-diagnostic/SKILL.md
            status: CANDIDATE
            anchors: [health, diagnostic, cross, functional, organizational]
      product-analytics:
        path: skills/design/product-analytics/
        skill_count: 1
        skills:
          - skill: design.product_analytics
            path: skills/design/product-analytics/SKILL.md
            status: CANDIDATE
            anchors: [product, analytics, when, defining, kpis]
      product-manager-toolkit:
        path: skills/design/product-manager-toolkit/
        skill_count: 1
        skills:
          - skill: design.product_manager_toolkit
            path: skills/design/product-manager-toolkit/SKILL.md
            status: CANDIDATE
            anchors: [product, manager, toolkit, comprehensive, managers]
      product-strategist:
        path: skills/design/product-strategist/
        skill_count: 1
        skills:
          - skill: design.product_strategist
            path: skills/design/product-strategist/SKILL.md
            status: CANDIDATE
            anchors: [product, strategist, strategic, leadership, toolkit]
      quality-documentation-manager:
        path: skills/design/quality-documentation-manager/
        skill_count: 1
        skills:
          - skill: design.quality_documentation_manager
            path: skills/design/quality-documentation-manager/SKILL.md
            status: CANDIDATE
            anchors: [quality, documentation, manager, document, control]
      quality-manager-qmr:
        path: skills/design/quality-manager-qmr/
        skill_count: 1
        skills:
          - skill: design.quality_manager_qmr
            path: skills/design/quality-manager-qmr/SKILL.md
            status: CANDIDATE
            anchors: [quality, manager, senior, responsible, person]
      quality-manager-qms-iso13485:
        path: skills/design/quality-manager-qms-iso13485/
        skill_count: 1
        skills:
          - skill: design.quality_manager_qms_iso13485
            path: skills/design/quality-manager-qms-iso13485/SKILL.md
            status: CANDIDATE
            anchors: [quality, manager, iso13485, management, system]
      roadmap-communicator:
        path: skills/design/roadmap-communicator/
        skill_count: 1
        skills:
          - skill: design.roadmap_communicator
            path: skills/design/roadmap-communicator/SKILL.md
            status: CANDIDATE
            anchors: [roadmap, communicator, when, preparing, narratives]
      rust-systems:
        path: skills/design/rust-systems/
        skill_count: 1
        skills:
          - skill: design.rust_systems
            path: skills/design/rust-systems/SKILL.md
            status: CANDIDATE
            anchors: [rust, systems, programming, patterns, including]
      setup:
        path: skills/design/setup/
        skill_count: 1
        skills:
          - skill: design.setup
            path: skills/design/setup/SKILL.md
            status: CANDIDATE
            anchors: [setup, autoresearch, experiment, interactively, collects]
      skill-creator:
        path: skills/design/skill-creator/
        skill_count: 1
        skills:
          - skill: design.skill_creator
            path: skills/design/skill-creator/SKILL.md
            status: CANDIDATE
            anchors: [skill, creator, guide, creating, effective]
      soc2-compliance:
        path: skills/design/soc2-compliance/
        skill_count: 1
        skills:
          - skill: design.soc2_compliance
            path: skills/design/soc2-compliance/SKILL.md
            status: CANDIDATE
            anchors: [soc2, compliance, when, prepare, the]
      social-content:
        path: skills/design/social-content/
        skill_count: 1
        skills:
          - skill: design.social_content
            path: skills/design/social-content/SKILL.md
            status: CANDIDATE
            anchors: [social, content, when, social-content, the]
      social-media-manager:
        path: skills/design/social-media-manager/
        skill_count: 1
        skills:
          - skill: design.social_media_manager
            path: skills/design/social-media-manager/SKILL.md
            status: CANDIDATE
            anchors: [social, media, manager, when, social-media-manager]
      statistical-analyst:
        path: skills/design/statistical-analyst/
        skill_count: 1
        skills:
          - skill: design.statistical_analyst
            path: skills/design/statistical-analyst/SKILL.md
            status: CANDIDATE
            anchors: [statistical, analyst, hypothesis, tests, analyze]
      status:
        path: skills/design/status/
        skill_count: 1
        skills:
          - skill: design.status
            path: skills/design/status/SKILL.md
            status: CANDIDATE
            anchors: [status, memory, health, dashboard, showing]
      strategic-alignment:
        path: skills/design/strategic-alignment/
        skill_count: 1
        skills:
          - skill: design.strategic_alignment
            path: skills/design/strategic-alignment/SKILL.md
            status: CANDIDATE
            anchors: [strategic, alignment, cascades, strategy, boardroom]
      testrail:
        path: skills/design/testrail/
        skill_count: 1
        skills:
          - skill: design.testrail
            path: skills/design/testrail/SKILL.md
            status: CANDIDATE
            anchors: [testrail, test, cases, integration, prerequisites]
      ui-design-system:
        path: skills/design/ui-design-system/
        skill_count: 1
        skills:
          - skill: design.ui_design_system
            path: skills/design/ui-design-system/SKILL.md
            status: CANDIDATE
            anchors: [design, system, toolkit, senior, designer]
      ux:
        path: skills/design/ux/
        skill_count: 11
        skills:
          - skill: design.ux.accessibility_review
            path: skills/design/ux/accessibility-review/SKILL.md
            status: ADOPTED
            anchors: [accessibility, review, wcag, audit, design]
          - skill: design.ux.design_critique
            path: skills/design/ux/design-critique/SKILL.md
            status: ADOPTED
            anchors: [design, critique, structured, feedback, usability]
          - skill: design.ux.design_handoff
            path: skills/design/ux/design-handoff/SKILL.md
            status: ADOPTED
            anchors: [design, handoff, generate, developer, specs]
          - skill: design.ux.design_system
            path: skills/design/ux/design-system/SKILL.md
            status: ADOPTED
            anchors: [design, system, audit, document, extend]
          - skill: design.ux.research_synthesis
            path: skills/design/ux/research-synthesis/SKILL.md
            status: ADOPTED
            anchors: [research, synthesis, synthesize, user, themes]
          # ... +6 skills adicionais
      wiki-architect:
        path: skills/design/wiki-architect/
        skill_count: 1
        skills:
          - skill: design.wiki_architect
            path: skills/design/wiki-architect/SKILL.md
            status: CANDIDATE
            anchors: [wiki, architect, analyzes, code, repositories]
      wiki-onboarding:
        path: skills/design/wiki-onboarding/
        skill_count: 1
        skills:
          - skill: design.wiki_onboarding
            path: skills/design/wiki-onboarding/SKILL.md
            status: CANDIDATE
            anchors: [wiki, onboarding, generates, four, audience]
      wiki-vitepress:
        path: skills/design/wiki-vitepress/
        skill_count: 1
        skills:
          - skill: design.wiki_vitepress
            path: skills/design/wiki-vitepress/SKILL.md
            status: CANDIDATE
            anchors: [wiki, vitepress, packages, generated, markdown]

  ENGINEERING:
    path: skills/engineering/
    display_name: "Engineering (Core)"
    skill_count: 596
    anchors: [azure, patterns, expert, python, build, comprehensive, master, architecture, development, testing, workflow, modern, dotnet, code, production]
    sub_domains:
      architecture:
        path: skills/engineering/architecture/
        skill_count: 37
        skills:
          - skill: engineering.architecture.architect_review
            path: skills/engineering/architecture/architect-review/SKILL.md
            status: CANDIDATE
            anchors: [architect, review, master, software, specializing]
          - skill: engineering.architecture.architecture
            path: skills/engineering/architecture/architecture/SKILL.md
            status: CANDIDATE
            anchors: [architecture, architectural, decision, making, framework]
          - skill: engineering.architecture.architecture_decision_records
            path: skills/engineering/architecture/architecture-decision-records/SKILL.md
            status: CANDIDATE
            anchors: [architecture, decision, records, comprehensive, patterns]
          - skill: engineering.architecture.architecture_patterns
            path: skills/engineering/architecture/architecture-patterns/SKILL.md
            status: CANDIDATE
            anchors: [architecture, patterns, master, proven, backend]
          - skill: engineering.architecture.astro
            path: skills/engineering/architecture/astro/SKILL.md
            status: CANDIDATE
            anchors: [astro, build, content, focused, websites]
          # ... +32 skills adicionais
      backend:
        path: skills/engineering/backend/
        skill_count: 20
        skills:
          - skill: engineering.backend.fastapi.fastapi_router_py
            path: skills/engineering/backend/fastapi/fastapi-router-py/SKILL.md
            status: CANDIDATE
            anchors: [fastapi, router, create, routers, following]
          - skill: engineering.backend.fastapi.fastapi_templates
            path: skills/engineering/backend/fastapi/fastapi-templates/SKILL.md
            status: CANDIDATE
            anchors: [fastapi, templates, create, production, ready]
          - skill: engineering.backend.fastapi.junta_leiloeiros
            path: skills/engineering/backend/fastapi/junta-leiloeiros/SKILL.md
            status: CANDIDATE
            anchors: [junta, leiloeiros, coleta, consulta, dados]
          - skill: engineering.backend.graphql.api_design_principles
            path: skills/engineering/backend/graphql/api-design-principles/SKILL.md
            status: CANDIDATE
            anchors: [design, principles, master, rest, graphql]
          - skill: engineering.backend.graphql.api_patterns
            path: skills/engineering/backend/graphql/api-patterns/SKILL.md
            status: CANDIDATE
            anchors: [patterns, design, principles, decision, making]
          # ... +15 skills adicionais
      cli:
        path: skills/engineering/cli/
        skill_count: 25
        skills:
          - skill: engineering_cli.arp
            path: skills/engineering/cli/arp/SKILL.md
            status: CANDIDATE
            anchors: [x-arp, arp, output, entries, format]
          - skill: engineering_cli.ccal
            path: skills/engineering/cli/ccal/SKILL.md
            status: CANDIDATE
            anchors: [ccal, chinese, calendar, lunar, solar]
          - skill: engineering_cli.cpu
            path: skills/engineering/cli/cpu/SKILL.md
            status: CANDIDATE
            anchors: [x-cpu, cpu, endianness, information, output]
          - skill: engineering_cli.df
            path: skills/engineering/cli/df/SKILL.md
            status: CANDIDATE
            anchors: [x-df, usage, disk, format, output]
          - skill: engineering_cli.dns
            path: skills/engineering/cli/dns/SKILL.md
            status: CANDIDATE
            anchors: [x-dns, dns, list, refresh, configuration]
          # ... +20 skills adicionais
      cloud:
        path: skills/engineering/cloud/
        skill_count: 67
        skills:
          - skill: engineering.cloud.aws.aws_compliance_checker
            path: skills/engineering/cloud/aws/aws-compliance-checker/SKILL.md
            status: CANDIDATE
            anchors: [compliance, checker, automated, checking, against]
          - skill: engineering.cloud.aws.aws_cost_cleanup
            path: skills/engineering/cloud/aws/aws-cost-cleanup/SKILL.md
            status: CANDIDATE
            anchors: [cost, cleanup, automated, unused, resources]
          - skill: engineering.cloud.aws.aws_cost_optimizer
            path: skills/engineering/cloud/aws/aws-cost-optimizer/SKILL.md
            status: CANDIDATE
            anchors: [cost, optimizer, comprehensive, analysis, optimization]
          - skill: engineering.cloud.aws.aws_iam_best_practices
            path: skills/engineering/cloud/aws/aws-iam-best-practices/SKILL.md
            status: CANDIDATE
            anchors: [best, practices, policy, review, hardening]
          - skill: engineering.cloud.aws.aws_penetration_testing
            path: skills/engineering/cloud/aws/aws-penetration-testing/SKILL.md
            status: CANDIDATE
            anchors: [penetration, testing, provide, comprehensive, techniques]
          # ... +62 skills adicionais
      cms:
        path: skills/engineering/cms/
        skill_count: 3
        skills:
          - skill: engineering.cms.wordpress.wordpress_penetration_testing
            path: skills/engineering/cms/wordpress/wordpress-penetration-testing/SKILL.md
            status: CANDIDATE
            anchors: [wordpress, penetration, testing, assess, installations]
          - skill: engineering.cms.wordpress.wordpress_theme_development
            path: skills/engineering/cms/wordpress/wordpress-theme-development/SKILL.md
            status: CANDIDATE
            anchors: [wordpress, theme, development, workflow, covering]
          - skill: engineering.cms.wordpress.wordpress_woocommerce_development
            path: skills/engineering/cms/wordpress/wordpress-woocommerce-development/SKILL.md
            status: CANDIDATE
            anchors: [wordpress, woocommerce, development, store, workflow]
      cs-engineering:
        path: skills/engineering/cs-engineering/
        skill_count: 58
        skills:
          - skill: cs-engineering
            path: skills/engineering/cs-engineering/SKILL.md
            status: UNKNOWN
          - skill: agent-designer
            path: skills/engineering/cs-engineering/agent-designer/SKILL.md
            status: UNKNOWN
          - skill: agent-workflow-designer
            path: skills/engineering/cs-engineering/agent-workflow-designer/SKILL.md
            status: UNKNOWN
          - skill: agenthub
            path: skills/engineering/cs-engineering/agenthub/SKILL.md
            status: UNKNOWN
          - skill: board
            path: skills/engineering/cs-engineering/agenthub/skills/board/SKILL.md
            status: UNKNOWN
          # ... +53 skills adicionais
      cs-engineering-team:
        path: skills/engineering/cs-engineering-team/
        skill_count: 51
        skills:
          - skill: cs-engineering-team
            path: skills/engineering/cs-engineering-team/SKILL.md
            status: UNKNOWN
          - skill: a11y-audit
            path: skills/engineering/cs-engineering-team/a11y-audit/SKILL.md
            status: UNKNOWN
          - skill: adversarial-reviewer
            path: skills/engineering/cs-engineering-team/adversarial-reviewer/SKILL.md
            status: UNKNOWN
          - skill: ai-security
            path: skills/engineering/cs-engineering-team/ai-security/SKILL.md
            status: UNKNOWN
          - skill: aws-solution-architect
            path: skills/engineering/cs-engineering-team/aws-solution-architect/SKILL.md
            status: UNKNOWN
          # ... +46 skills adicionais
      devops:
        path: skills/engineering/devops/
        skill_count: 53
        skills:
          - skill: engineering.devops.bash.bash_defensive_patterns
            path: skills/engineering/devops/bash/bash-defensive-patterns/SKILL.md
            status: CANDIDATE
            anchors: [bash, defensive, patterns, master, programming]
          - skill: engineering.devops.bash.bash_linux
            path: skills/engineering/devops/bash/bash-linux/SKILL.md
            status: CANDIDATE
            anchors: [bash, linux, terminal, patterns, critical]
          - skill: engineering.devops.bash.bash_pro
            path: skills/engineering/devops/bash/bash-pro/SKILL.md
            status: CANDIDATE
            anchors: [bash, master, defensive, scripting, production]
          - skill: engineering.devops.bash.bash_scripting
            path: skills/engineering/devops/bash/bash-scripting/SKILL.md
            status: CANDIDATE
            anchors: [bash, scripting, workflow, creating, production]
          - skill: engineering.devops.bash.bats_testing_patterns
            path: skills/engineering/devops/bash/bats-testing-patterns/SKILL.md
            status: CANDIDATE
            anchors: [bats, testing, patterns, master, bash]
          # ... +48 skills adicionais
      documentation:
        path: skills/engineering/documentation/
        skill_count: 22
        skills:
          - skill: engineering.documentation.api_documentation
            path: skills/engineering/documentation/api-documentation/SKILL.md
            status: CANDIDATE
            anchors: [documentation, workflow, generating, openapi, specs]
          - skill: engineering.documentation.api_documentation_generator
            path: skills/engineering/documentation/api-documentation-generator/SKILL.md
            status: CANDIDATE
            anchors: [documentation, generator, generate, comprehensive, developer]
          - skill: engineering.documentation.api_documenter
            path: skills/engineering/documentation/api-documenter/SKILL.md
            status: CANDIDATE
            anchors: [documenter, master, documentation, openapi, powered]
          - skill: engineering.documentation.brand_guidelines
            path: skills/engineering/documentation/brand-guidelines/SKILL.md
            status: CANDIDATE
            anchors: [brand, guidelines, write, copy, following]
          - skill: engineering.documentation.c4_code
            path: skills/engineering/documentation/c4-code/SKILL.md
            status: CANDIDATE
            anchors: [code, expert, level, documentation, specialist]
          # ... +17 skills adicionais
      frontend:
        path: skills/engineering/frontend/
        skill_count: 52
        skills:
          - skill: engineering.frontend.angular.angular_best_practices
            path: skills/engineering/frontend/angular/angular-best-practices/SKILL.md
            status: CANDIDATE
            anchors: [angular, best, practices, performance, optimization]
          - skill: engineering.frontend.angular.angular_migration
            path: skills/engineering/frontend/angular/angular-migration/SKILL.md
            status: CANDIDATE
            anchors: [angular, migration, master, angularjs, hybrid]
          - skill: engineering.frontend.angular.angular_state_management
            path: skills/engineering/frontend/angular/angular-state-management/SKILL.md
            status: CANDIDATE
            anchors: [angular, state, management, master, modern]
          - skill: engineering.frontend.angular.angular_ui_patterns
            path: skills/engineering/frontend/angular/angular-ui-patterns/SKILL.md
            status: CANDIDATE
            anchors: [angular, patterns, modern, loading, states]
          - skill: engineering.frontend.application_performance_performance_optimization
            path: skills/engineering/frontend/application-performance-performance-optimization/SKILL.md
            status: CANDIDATE
            anchors: [application, performance, optimization, optimize, profiling]
          # ... +47 skills adicionais
      programming:
        path: skills/engineering/programming/
        skill_count: 168
        skills:
          - skill: engineering.programming.c.c_pro
            path: skills/engineering/programming/c/c-pro/SKILL.md
            status: CANDIDATE
            anchors: [write, efficient, code, proper, memory]
          - skill: engineering.programming.c.customer_psychographic_profiler
            path: skills/engineering/programming/c/customer-psychographic-profiler/SKILL.md
            status: CANDIDATE
            anchors: [customer, psychographic, profiler, sentence, skill]
          - skill: engineering.programming.cpp.cpp_pro
            path: skills/engineering/programming/cpp/cpp-pro/SKILL.md
            status: CANDIDATE
            anchors: [write, idiomatic, code, modern, features]
          - skill: engineering.programming.cpp.unreal_engine_cpp_pro
            path: skills/engineering/programming/cpp/unreal-engine-cpp-pro/SKILL.md
            status: CANDIDATE
            anchors: [unreal, engine, expert, guide, development]
          - skill: engineering.programming.csharp.avalonia_layout_zafiro
            path: skills/engineering/programming/csharp/avalonia-layout-zafiro/SKILL.md
            status: CANDIDATE
            anchors: [avalonia, layout, zafiro, guidelines, modern]
          # ... +163 skills adicionais
      software:
        path: skills/engineering/software/
        skill_count: 11
        skills:
          - skill: engineering.software.architecture
            path: skills/engineering/software/architecture/SKILL.md
            status: ADOPTED
            anchors: [architecture, create, evaluate, decision, record]
          - skill: engineering.software.code_review
            path: skills/engineering/software/code-review/SKILL.md
            status: ADOPTED
            anchors: [code, review, changes, security, performance]
          - skill: engineering.software.debug
            path: skills/engineering/software/debug/SKILL.md
            status: ADOPTED
            anchors: [debug, structured, debugging, session, reproduce]
          - skill: engineering.software.deploy_checklist
            path: skills/engineering/software/deploy-checklist/SKILL.md
            status: ADOPTED
            anchors: [deploy, checklist, deployment, verification, ship]
          - skill: engineering.software.documentation
            path: skills/engineering/software/documentation/SKILL.md
            status: ADOPTED
            anchors: [documentation, write, maintain, technical, trigger]
          # ... +6 skills adicionais
      testing:
        path: skills/engineering/testing/
        skill_count: 29
        skills:
          - skill: engineering.testing.ad_creative
            path: skills/engineering/testing/ad-creative/SKILL.md
            status: CANDIDATE
            anchors: [creative, create, iterate, scale, paid]
          - skill: engineering.testing.android_ui_verification
            path: skills/engineering/testing/android_ui_verification/SKILL.md
            status: CANDIDATE
            anchors: [android, verification, automated, testing, emulator]
          - skill: engineering.testing.api_testing_observability_api_mock
            path: skills/engineering/testing/api-testing-observability-api-mock/SKILL.md
            status: CANDIDATE
            anchors: [testing, observability, mock, mocking, expert]
          - skill: engineering.testing.backtesting_frameworks
            path: skills/engineering/testing/backtesting-frameworks/SKILL.md
            status: CANDIDATE
            anchors: [backtesting, frameworks, build, robust, production]
          - skill: engineering.testing.browser_automation
            path: skills/engineering/testing/browser-automation/SKILL.md
            status: CANDIDATE
            anchors: [browser, automation, powers, testing, scraping]
          # ... +24 skills adicionais

  ENGINEERING_AGENTOPS:
    path: skills/engineering_agentops/
    display_name: "Engineering Agentops"
    skill_count: 14
    sub_domains:
      brainstorming:
        path: skills/engineering_agentops/brainstorming/
        skill_count: 1
        skills:
          - skill: engineering_agentops.brainstorming
            path: skills/engineering_agentops/brainstorming/SKILL.md
            status: ADOPTED
      dispatching-parallel-agents:
        path: skills/engineering_agentops/dispatching-parallel-agents/
        skill_count: 1
        skills:
          - skill: engineering_agentops.dispatching-parallel-agents
            path: skills/engineering_agentops/dispatching-parallel-agents/SKILL.md
            status: ADOPTED
      executing-plans:
        path: skills/engineering_agentops/executing-plans/
        skill_count: 1
        skills:
          - skill: engineering_agentops.executing-plans
            path: skills/engineering_agentops/executing-plans/SKILL.md
            status: ADOPTED
      finishing-a-development-branch:
        path: skills/engineering_agentops/finishing-a-development-branch/
        skill_count: 1
        skills:
          - skill: engineering_agentops.finishing-a-development-branch
            path: skills/engineering_agentops/finishing-a-development-branch/SKILL.md
            status: ADOPTED
      receiving-code-review:
        path: skills/engineering_agentops/receiving-code-review/
        skill_count: 1
        skills:
          - skill: engineering_agentops.receiving-code-review
            path: skills/engineering_agentops/receiving-code-review/SKILL.md
            status: ADOPTED
      requesting-code-review:
        path: skills/engineering_agentops/requesting-code-review/
        skill_count: 1
        skills:
          - skill: engineering_agentops.requesting-code-review
            path: skills/engineering_agentops/requesting-code-review/SKILL.md
            status: ADOPTED
      subagent-driven-development:
        path: skills/engineering_agentops/subagent-driven-development/
        skill_count: 1
        skills:
          - skill: engineering_agentops.subagent-driven-development
            path: skills/engineering_agentops/subagent-driven-development/SKILL.md
            status: ADOPTED
      systematic-debugging:
        path: skills/engineering_agentops/systematic-debugging/
        skill_count: 1
        skills:
          - skill: engineering_agentops.systematic-debugging
            path: skills/engineering_agentops/systematic-debugging/SKILL.md
            status: ADOPTED
      test-driven-development:
        path: skills/engineering_agentops/test-driven-development/
        skill_count: 1
        skills:
          - skill: engineering_agentops.test-driven-development
            path: skills/engineering_agentops/test-driven-development/SKILL.md
            status: ADOPTED
      using-git-worktrees:
        path: skills/engineering_agentops/using-git-worktrees/
        skill_count: 1
        skills:
          - skill: engineering_agentops.using-git-worktrees
            path: skills/engineering_agentops/using-git-worktrees/SKILL.md
            status: ADOPTED
      using-superpowers:
        path: skills/engineering_agentops/using-superpowers/
        skill_count: 1
        skills:
          - skill: engineering_agentops.using-superpowers
            path: skills/engineering_agentops/using-superpowers/SKILL.md
            status: ADOPTED
      verification-before-completion:
        path: skills/engineering_agentops/verification-before-completion/
        skill_count: 1
        skills:
          - skill: engineering_agentops.verification-before-completion
            path: skills/engineering_agentops/verification-before-completion/SKILL.md
            status: ADOPTED
      writing-plans:
        path: skills/engineering_agentops/writing-plans/
        skill_count: 1
        skills:
          - skill: engineering_agentops.writing-plans
            path: skills/engineering_agentops/writing-plans/SKILL.md
            status: ADOPTED
      writing-skills:
        path: skills/engineering_agentops/writing-skills/
        skill_count: 1
        skills:
          - skill: engineering_agentops.writing-skills
            path: skills/engineering_agentops/writing-skills/SKILL.md
            status: ADOPTED

  ENGINEERING_API:
    path: skills/engineering_api/
    display_name: "Engineering — API"
    skill_count: 14
    anchors: [for, design, patterns, api, changes, when, the, atlassian, managing, skills, graphql, and, including, rest, resource]
    sub_domains:
      api-design-patterns:
        path: skills/engineering_api/api-design-patterns/
        skill_count: 1
        skills:
          - skill: engineering_api.api_design_patterns
            path: skills/engineering_api/api-design-patterns/SKILL.md
            status: CANDIDATE
            anchors: [design, patterns, rest, resource, naming]
      api-design-reviewer:
        path: skills/engineering_api/api-design-reviewer/
        skill_count: 1
        skills:
          - skill: engineering_api.api_design_reviewer
            path: skills/engineering_api/api-design-reviewer/SKILL.md
            status: CANDIDATE
            anchors: [design, reviewer, api-design-reviewer, api, versioning]
      api-test-suite-builder:
        path: skills/engineering_api/api-test-suite-builder/
        skill_count: 1
        skills:
          - skill: engineering_api.api_test_suite_builder
            path: skills/engineering_api/api-test-suite-builder/SKILL.md
            status: CANDIDATE
            anchors: [test, suite, builder, when, api-test-suite-builder]
      atlassian-admin:
        path: skills/engineering_api/atlassian-admin/
        skill_count: 1
        skills:
          - skill: engineering_api.atlassian_admin
            path: skills/engineering_api/atlassian-admin/SKILL.md
            status: CANDIDATE
            anchors: [atlassian, admin, administrator, managing, organizing]
      change-management:
        path: skills/engineering_api/change-management/
        skill_count: 1
        skills:
          - skill: engineering_api.change_management
            path: skills/engineering_api/change-management/SKILL.md
            status: CANDIDATE
            anchors: [change, management, framework, rolling, organizational]
      chro-advisor:
        path: skills/engineering_api/chro-advisor/
        skill_count: 1
        skills:
          - skill: engineering_api.chro_advisor
            path: skills/engineering_api/chro-advisor/SKILL.md
            status: CANDIDATE
            anchors: [chro, advisor, people, leadership, scaling]
      composio-skills:
        path: skills/engineering_api/composio-skills/
        skill_count: 1
        skills:
          - skill: engineering_api.composio_skills
            path: skills/engineering_api/composio-skills/SKILL.md
            status: CANDIDATE
            anchors: [composio, skills, automate, contentful, graphql]
      confluence-expert:
        path: skills/engineering_api/confluence-expert/
        skill_count: 1
        skills:
          - skill: engineering_api.confluence_expert
            path: skills/engineering_api/confluence-expert/SKILL.md
            status: CANDIDATE
            anchors: [confluence, expert, atlassian, creating, managing]
      fastapi-router-py:
        path: skills/engineering_api/fastapi-router-py/
        skill_count: 1
        skills:
          - skill: engineering_api.fastapi_router_py
            path: skills/engineering_api/fastapi-router-py/SKILL.md
            status: CANDIDATE
            anchors: [fastapi, router, create, routers, crud]
      find-skills:
        path: skills/engineering_api/find-skills/
        skill_count: 1
        skills:
          - skill: engineering_api.find_skills
            path: skills/engineering_api/find-skills/SKILL.md
            status: CANDIDATE
            anchors: [find, skills, helps, discover, install]
      graphql-design:
        path: skills/engineering_api/graphql-design/
        skill_count: 1
        skills:
          - skill: engineering_api.graphql_design
            path: skills/engineering_api/graphql-design/SKILL.md
            status: CANDIDATE
            anchors: [graphql, design, schema, resolver, patterns]
      launch-strategy:
        path: skills/engineering_api/launch-strategy/
        skill_count: 1
        skills:
          - skill: engineering_api.launch_strategy
            path: skills/engineering_api/launch-strategy/SKILL.md
            status: CANDIDATE
            anchors: [launch, strategy, when, plan, launch-strategy]
      senior-backend:
        path: skills/engineering_api/senior-backend/
        skill_count: 1
        skills:
          - skill: engineering_api.senior_backend
            path: skills/engineering_api/senior-backend/SKILL.md
            status: CANDIDATE
            anchors: [senior, backend, designs, implements, systems]
      springboot-patterns:
        path: skills/engineering_api/springboot-patterns/
        skill_count: 1
        skills:
          - skill: engineering_api.springboot_patterns
            path: skills/engineering_api/springboot-patterns/SKILL.md
            status: CANDIDATE
            anchors: [springboot, patterns, spring, boot, including]

  ENGINEERING_BACKEND:
    path: skills/engineering_backend/
    display_name: "Engineering — Backend"
    skill_count: 9
    anchors: [skills, optimization, canvas, design, create, beautiful, visual, documents, canvas-design, art, composio, automate, hashnode, tasks, rube]
    sub_domains:
      canvas-design:
        path: skills/engineering_backend/canvas-design/
        skill_count: 1
        skills:
          - skill: engineering_backend.canvas_design
            path: skills/engineering_backend/canvas-design/SKILL.md
            status: CANDIDATE
            anchors: [canvas, design, create, beautiful, visual]
      composio-skills:
        path: skills/engineering_backend/composio-skills/
        skill_count: 1
        skills:
          - skill: engineering_backend.composio_skills
            path: skills/engineering_backend/composio-skills/SKILL.md
            status: CANDIDATE
            anchors: [composio, skills, automate, hashnode, tasks]
      django-patterns:
        path: skills/engineering_backend/django-patterns/
        skill_count: 1
        skills:
          - skill: engineering_backend.django_patterns
            path: skills/engineering_backend/django-patterns/SKILL.md
            status: CANDIDATE
            anchors: [django, patterns, architecture, including, optimization]
      m365-agents-ts:
        path: skills/engineering_backend/m365-agents-ts/
        skill_count: 1
        skills:
          - skill: engineering_backend.m365_agents_ts
            path: skills/engineering_backend/m365-agents-ts/SKILL.md
            status: CANDIDATE
            anchors: [m365, agents, agents-ts, copilot, studio]
      mcp-builder:
        path: skills/engineering_backend/mcp-builder/
        skill_count: 1
        skills:
          - skill: engineering_backend.mcp_builder
            path: skills/engineering_backend/mcp-builder/SKILL.md
            status: CANDIDATE
            anchors: [builder, guide, creating, high, quality]
      monitoring-observability:
        path: skills/engineering_backend/monitoring-observability/
        skill_count: 1
        skills:
          - skill: engineering_backend.monitoring_observability
            path: skills/engineering_backend/monitoring-observability/SKILL.md
            status: CANDIDATE
            anchors: [monitoring, observability, opentelemetry, prometheus, grafana]
      performance-profiler:
        path: skills/engineering_backend/performance-profiler/
        skill_count: 1
        skills:
          - skill: engineering_backend.performance_profiler
            path: skills/engineering_backend/performance-profiler/SKILL.md
            status: CANDIDATE
            anchors: [performance, profiler, performance-profiler, optimization, first]
      skills-manager:
        path: skills/engineering_backend/skills-manager/
        skill_count: 1
        skills:
          - skill: engineering_backend.skills_manager
            path: skills/engineering_backend/skills-manager/SKILL.md
            status: CANDIDATE
            anchors: [skills, manager, claude, code, agent]
      spec-to-repo:
        path: skills/engineering_backend/spec-to-repo/
        skill_count: 1
        skills:
          - skill: engineering_backend.spec_to_repo
            path: skills/engineering_backend/spec-to-repo/SKILL.md
            status: CANDIDATE
            anchors: [spec, repo, when, says, build]

  ENGINEERING_CLI:
    path: skills/engineering_cli/
    display_name: "Engineering — CLI"
    skill_count: 3
    anchors: [board, prep, meeting, preparation, board-prep, phase, questions, numbers, challenge, mortem, plan, analysis, pre-mortem, assumptions, step]
    sub_domains:
      board-prep:
        path: skills/engineering_cli/board-prep/
        skill_count: 1
        skills:
          - skill: engineering_cli.board_prep
            path: skills/engineering_cli/board-prep/SKILL.md
            status: CANDIDATE
            anchors: [board, prep, meeting, preparation, board-prep]
      challenge:
        path: skills/engineering_cli/challenge/
        skill_count: 1
        skills:
          - skill: engineering_cli.challenge
            path: skills/engineering_cli/challenge/SKILL.md
            status: CANDIDATE
            anchors: [challenge, mortem, plan, analysis, pre-mortem]
      hard-call:
        path: skills/engineering_cli/hard-call/
        skill_count: 1
        skills:
          - skill: engineering_cli.hard_call
            path: skills/engineering_cli/hard-call/SKILL.md
            status: CANDIDATE
            anchors: [hard, call, framework, decisions, good]

  ENGINEERING_CLOUD_AWS:
    path: skills/engineering_cloud_aws/
    display_name: "Engineering — Cloud AWS"
    skill_count: 4
    anchors: [aws, skills, cloud, patterns, lambda, dynamodb, infrastructure, code, aws-cloud-patterns, solution, architect, design, architectures, startups, aws-solution-architect]
    sub_domains:
      aws-cloud-patterns:
        path: skills/engineering_cloud_aws/aws-cloud-patterns/
        skill_count: 1
        skills:
          - skill: engineering_cloud_aws.aws_cloud_patterns
            path: skills/engineering_cloud_aws/aws-cloud-patterns/SKILL.md
            status: CANDIDATE
            anchors: [cloud, patterns, lambda, dynamodb, infrastructure]
      aws-solution-architect:
        path: skills/engineering_cloud_aws/aws-solution-architect/
        skill_count: 1
        skills:
          - skill: engineering_cloud_aws.aws_solution_architect
            path: skills/engineering_cloud_aws/aws-solution-architect/SKILL.md
            status: CANDIDATE
            anchors: [solution, architect, design, architectures, startups]
      composio-skills:
        path: skills/engineering_cloud_aws/composio-skills/
        skill_count: 1
        skills:
          - skill: engineering_cloud_aws.composio_skills
            path: skills/engineering_cloud_aws/composio-skills/SKILL.md
            status: CANDIDATE
            anchors: [composio, skills, automate, jigsawstack, tasks]
      engineering-team:
        path: skills/engineering_cloud_aws/engineering-team/
        skill_count: 1
        skills:
          - skill: engineering_cloud_aws.engineering_team
            path: skills/engineering_cloud_aws/engineering-team/SKILL.md
            status: CANDIDATE
            anchors: [engineering, team, agent, skills, plugins]

  ENGINEERING_CLOUD_AZURE:
    path: skills/engineering_cloud_azure/
    display_name: "Engineering — Cloud Azure"
    skill_count: 161
    anchors: [azure, dotnet, java, build, create, client, for, key, applications, and, mgmt, storage, resource, manager, api]
    sub_domains:
      agent-framework-azure-ai-py:
        path: skills/engineering_cloud_azure/agent-framework-azure-ai-py/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.agent_framework_azure_ai_py
            path: skills/engineering_cloud_azure/agent-framework-azure-ai-py/SKILL.md
            status: CANDIDATE
            anchors: [agent, framework, azure, build, foundry]
      agents-v2-py:
        path: skills/engineering_cloud_azure/agents-v2-py/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.agents_v2_py
            path: skills/engineering_cloud_azure/agents-v2-py/SKILL.md
            status: CANDIDATE
            anchors: [agents, agents-, agent, version, environment]
      appinsights-instrumentation:
        path: skills/engineering_cloud_azure/appinsights-instrumentation/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.appinsights_instrumentation
            path: skills/engineering_cloud_azure/appinsights-instrumentation/SKILL.md
            status: CANDIDATE
            anchors: [appinsights, instrumentation, guidance, instrumenting, webapps]
      azure-ai:
        path: skills/engineering_cloud_azure/azure-ai/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.azure_ai
            path: skills/engineering_cloud_azure/azure-ai/SKILL.md
            status: CANDIDATE
            anchors: [azure, search, speech, openai, document]
      azure-ai-agents-persistent-dotnet:
        path: skills/engineering_cloud_azure/azure-ai-agents-persistent-dotnet/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.azure_ai_agents_persistent_dotnet
            path: skills/engineering_cloud_azure/azure-ai-agents-persistent-dotnet/SKILL.md
            status: CANDIDATE
            anchors: [azure, agents, persistent, dotnet, azure-ai-agents-persistent-dotnet]
      azure-ai-agents-persistent-java:
        path: skills/engineering_cloud_azure/azure-ai-agents-persistent-java/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.azure_ai_agents_persistent_java
            path: skills/engineering_cloud_azure/azure-ai-agents-persistent-java/SKILL.md
            status: CANDIDATE
            anchors: [azure, agents, persistent, java, azure-ai-agents-persistent-java]
      azure-ai-anomalydetector-java:
        path: skills/engineering_cloud_azure/azure-ai-anomalydetector-java/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.azure_ai_anomalydetector_java
            path: skills/engineering_cloud_azure/azure-ai-anomalydetector-java/SKILL.md
            status: CANDIDATE
            anchors: [azure, anomalydetector, java, build, anomaly]
      azure-ai-contentsafety-java:
        path: skills/engineering_cloud_azure/azure-ai-contentsafety-java/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.azure_ai_contentsafety_java
            path: skills/engineering_cloud_azure/azure-ai-contentsafety-java/SKILL.md
            status: CANDIDATE
            anchors: [azure, contentsafety, java, build, content]
      azure-ai-contentsafety-py:
        path: skills/engineering_cloud_azure/azure-ai-contentsafety-py/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.azure_ai_contentsafety_py
            path: skills/engineering_cloud_azure/azure-ai-contentsafety-py/SKILL.md
            status: CANDIDATE
            anchors: [azure, contentsafety, azure-ai-contentsafety-py, severity, analyze]
      azure-ai-contentsafety-ts:
        path: skills/engineering_cloud_azure/azure-ai-contentsafety-ts/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.azure_ai_contentsafety_ts
            path: skills/engineering_cloud_azure/azure-ai-contentsafety-ts/SKILL.md
            status: CANDIDATE
            anchors: [azure, contentsafety, analyze, text, images]
      azure-ai-contentunderstanding-py:
        path: skills/engineering_cloud_azure/azure-ai-contentunderstanding-py/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.azure_ai_contentunderstanding_py
            path: skills/engineering_cloud_azure/azure-ai-contentunderstanding-py/SKILL.md
            status: CANDIDATE
            anchors: [azure, contentunderstanding, azure-ai-contentunderstanding-py, access, content]
      azure-ai-document-intelligence-dotnet:
        path: skills/engineering_cloud_azure/azure-ai-document-intelligence-dotnet/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.azure_ai_document_intelligence_dotnet
            path: skills/engineering_cloud_azure/azure-ai-document-intelligence-dotnet/SKILL.md
            status: CANDIDATE
            anchors: [azure, document, intelligence, dotnet, azure-ai-document-intelligence-dotnet]
      azure-ai-document-intelligence-ts:
        path: skills/engineering_cloud_azure/azure-ai-document-intelligence-ts/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.azure_ai_document_intelligence_ts
            path: skills/engineering_cloud_azure/azure-ai-document-intelligence-ts/SKILL.md
            status: CANDIDATE
            anchors: [azure, document, intelligence, extract, text]
      azure-ai-formrecognizer-java:
        path: skills/engineering_cloud_azure/azure-ai-formrecognizer-java/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.azure_ai_formrecognizer_java
            path: skills/engineering_cloud_azure/azure-ai-formrecognizer-java/SKILL.md
            status: CANDIDATE
            anchors: [azure, formrecognizer, java, build, document]
      azure-ai-language-conversations-py:
        path: skills/engineering_cloud_azure/azure-ai-language-conversations-py/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.azure_ai_language_conversations_py
            path: skills/engineering_cloud_azure/azure-ai-language-conversations-py/SKILL.md
            status: CANDIDATE
            anchors: [azure, language, conversations, implement, conversational]
      azure-ai-ml-py:
        path: skills/engineering_cloud_azure/azure-ai-ml-py/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.azure_ai_ml_py
            path: skills/engineering_cloud_azure/azure-ai-ml-py/SKILL.md
            status: CANDIDATE
            anchors: [azure, azure-ai-ml-py, register, list, create]
      azure-ai-openai-dotnet:
        path: skills/engineering_cloud_azure/azure-ai-openai-dotnet/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.azure_ai_openai_dotnet
            path: skills/engineering_cloud_azure/azure-ai-openai-dotnet/SKILL.md
            status: CANDIDATE
            anchors: [azure, openai, dotnet, azure-ai-openai-dotnet, chat]
      azure-ai-projects-dotnet:
        path: skills/engineering_cloud_azure/azure-ai-projects-dotnet/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.azure_ai_projects_dotnet
            path: skills/engineering_cloud_azure/azure-ai-projects-dotnet/SKILL.md
            status: CANDIDATE
            anchors: [azure, projects, dotnet, azure-ai-projects-dotnet, agents]
      azure-ai-projects-java:
        path: skills/engineering_cloud_azure/azure-ai-projects-java/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.azure_ai_projects_java
            path: skills/engineering_cloud_azure/azure-ai-projects-java/SKILL.md
            status: CANDIDATE
            anchors: [azure, projects, java, azure-ai-projects-java, environment]
      azure-ai-projects-py:
        path: skills/engineering_cloud_azure/azure-ai-projects-py/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.azure_ai_projects_py
            path: skills/engineering_cloud_azure/azure-ai-projects-py/SKILL.md
            status: CANDIDATE
            anchors: [azure, projects, build, applications, python]
      azure-ai-projects-ts:
        path: skills/engineering_cloud_azure/azure-ai-projects-ts/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.azure_ai_projects_ts
            path: skills/engineering_cloud_azure/azure-ai-projects-ts/SKILL.md
            status: CANDIDATE
            anchors: [azure, projects, build, applications, javascript]
      azure-ai-textanalytics-py:
        path: skills/engineering_cloud_azure/azure-ai-textanalytics-py/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.azure_ai_textanalytics_py
            path: skills/engineering_cloud_azure/azure-ai-textanalytics-py/SKILL.md
            status: CANDIDATE
            anchors: [azure, textanalytics, azure-ai-textanalytics-py, client, text]
      azure-ai-transcription-py:
        path: skills/engineering_cloud_azure/azure-ai-transcription-py/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.azure_ai_transcription_py
            path: skills/engineering_cloud_azure/azure-ai-transcription-py/SKILL.md
            status: CANDIDATE
            anchors: [azure, transcription, azure-ai-transcription-py, batch, sdk]
      azure-ai-translation-document-py:
        path: skills/engineering_cloud_azure/azure-ai-translation-document-py/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.azure_ai_translation_document_py
            path: skills/engineering_cloud_azure/azure-ai-translation-document-py/SKILL.md
            status: CANDIDATE
            anchors: [azure, translation, document, azure-ai-translation-document-py, supported]
      azure-ai-translation-text-py:
        path: skills/engineering_cloud_azure/azure-ai-translation-text-py/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.azure_ai_translation_text_py
            path: skills/engineering_cloud_azure/azure-ai-translation-text-py/SKILL.md
            status: CANDIDATE
            anchors: [azure, translation, text, azure-ai-translation-text-py, languages]
      azure-ai-translation-ts:
        path: skills/engineering_cloud_azure/azure-ai-translation-ts/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.azure_ai_translation_ts
            path: skills/engineering_cloud_azure/azure-ai-translation-ts/SKILL.md
            status: CANDIDATE
            anchors: [azure, translation, build, applications, sdks]
      azure-ai-vision-imageanalysis-java:
        path: skills/engineering_cloud_azure/azure-ai-vision-imageanalysis-java/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.azure_ai_vision_imageanalysis_java
            path: skills/engineering_cloud_azure/azure-ai-vision-imageanalysis-java/SKILL.md
            status: CANDIDATE
            anchors: [azure, vision, imageanalysis, java, build]
      azure-ai-vision-imageanalysis-py:
        path: skills/engineering_cloud_azure/azure-ai-vision-imageanalysis-py/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.azure_ai_vision_imageanalysis_py
            path: skills/engineering_cloud_azure/azure-ai-vision-imageanalysis-py/SKILL.md
            status: CANDIDATE
            anchors: [azure, vision, imageanalysis, azure-ai-vision-imageanalysis-py, image]
      azure-ai-voicelive-dotnet:
        path: skills/engineering_cloud_azure/azure-ai-voicelive-dotnet/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.azure_ai_voicelive_dotnet
            path: skills/engineering_cloud_azure/azure-ai-voicelive-dotnet/SKILL.md
            status: CANDIDATE
            anchors: [azure, voicelive, dotnet, azure-ai-voicelive-dotnet, key]
      azure-ai-voicelive-java:
        path: skills/engineering_cloud_azure/azure-ai-voicelive-java/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.azure_ai_voicelive_java
            path: skills/engineering_cloud_azure/azure-ai-voicelive-java/SKILL.md
            status: CANDIDATE
            anchors: [azure, voicelive, java, azure-ai-voicelive-java, key]
      azure-ai-voicelive-py:
        path: skills/engineering_cloud_azure/azure-ai-voicelive-py/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.azure_ai_voicelive_py
            path: skills/engineering_cloud_azure/azure-ai-voicelive-py/SKILL.md
            status: CANDIDATE
            anchors: [azure, voicelive, build, real, time]
      azure-ai-voicelive-ts:
        path: skills/engineering_cloud_azure/azure-ai-voicelive-ts/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.azure_ai_voicelive_ts
            path: skills/engineering_cloud_azure/azure-ai-voicelive-ts/SKILL.md
            status: CANDIDATE
            anchors: [azure, voicelive, azure-ai-voicelive-ts, key, typescript]
      azure-aigateway:
        path: skills/engineering_cloud_azure/azure-aigateway/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.azure_aigateway
            path: skills/engineering_cloud_azure/azure-aigateway/SKILL.md
            status: CANDIDATE
            anchors: [azure, aigateway, configure, management, gateway]
      azure-appconfiguration-java:
        path: skills/engineering_cloud_azure/azure-appconfiguration-java/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.azure_appconfiguration_java
            path: skills/engineering_cloud_azure/azure-appconfiguration-java/SKILL.md
            status: CANDIDATE
            anchors: [azure, appconfiguration, java, azure-appconfiguration-java, list]
      azure-appconfiguration-py:
        path: skills/engineering_cloud_azure/azure-appconfiguration-py/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.azure_appconfiguration_py
            path: skills/engineering_cloud_azure/azure-appconfiguration-py/SKILL.md
            status: CANDIDATE
            anchors: [azure, appconfiguration, azure-appconfiguration-py, settings, feature]
      azure-appconfiguration-ts:
        path: skills/engineering_cloud_azure/azure-appconfiguration-ts/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.azure_appconfiguration_ts
            path: skills/engineering_cloud_azure/azure-appconfiguration-ts/SKILL.md
            status: CANDIDATE
            anchors: [azure, appconfiguration, build, applications, configuration]
      azure-cloud-architect:
        path: skills/engineering_cloud_azure/azure-cloud-architect/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.azure_cloud_architect
            path: skills/engineering_cloud_azure/azure-cloud-architect/SKILL.md
            status: CANDIDATE
            anchors: [azure, cloud, architect, design, architectures]
      azure-cloud-migrate:
        path: skills/engineering_cloud_azure/azure-cloud-migrate/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.azure_cloud_migrate
            path: skills/engineering_cloud_azure/azure-cloud-migrate/SKILL.md
            status: CANDIDATE
            anchors: [azure, cloud, migrate, assess, cross]
      azure-communication-callautomation-java:
        path: skills/engineering_cloud_azure/azure-communication-callautomation-java/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.azure_communication_callautomation_java
            path: skills/engineering_cloud_azure/azure-communication-callautomation-java/SKILL.md
            status: CANDIDATE
            anchors: [azure, communication, callautomation, java, build]
      azure-communication-callingserver-java:
        path: skills/engineering_cloud_azure/azure-communication-callingserver-java/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.azure_communication_callingserver_java
            path: skills/engineering_cloud_azure/azure-communication-callingserver-java/SKILL.md
            status: CANDIDATE
            anchors: [azure, communication, callingserver, java, services]
      azure-communication-chat-java:
        path: skills/engineering_cloud_azure/azure-communication-chat-java/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.azure_communication_chat_java
            path: skills/engineering_cloud_azure/azure-communication-chat-java/SKILL.md
            status: CANDIDATE
            anchors: [azure, communication, chat, java, build]
      azure-communication-common-java:
        path: skills/engineering_cloud_azure/azure-communication-common-java/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.azure_communication_common_java
            path: skills/engineering_cloud_azure/azure-communication-common-java/SKILL.md
            status: CANDIDATE
            anchors: [azure, communication, common, java, services]
      azure-communication-sms-java:
        path: skills/engineering_cloud_azure/azure-communication-sms-java/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.azure_communication_sms_java
            path: skills/engineering_cloud_azure/azure-communication-sms-java/SKILL.md
            status: CANDIDATE
            anchors: [azure, communication, java, send, messages]
      azure-compliance:
        path: skills/engineering_cloud_azure/azure-compliance/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.azure_compliance
            path: skills/engineering_cloud_azure/azure-compliance/SKILL.md
            status: CANDIDATE
            anchors: [azure, compliance, security, audits, azqr]
      azure-compute:
        path: skills/engineering_cloud_azure/azure-compute/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.azure_compute
            path: skills/engineering_cloud_azure/azure-compute/SKILL.md
            status: CANDIDATE
            anchors: [azure, compute, vmss, router, recommendations]
      azure-compute-batch-java:
        path: skills/engineering_cloud_azure/azure-compute-batch-java/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.azure_compute_batch_java
            path: skills/engineering_cloud_azure/azure-compute-batch-java/SKILL.md
            status: CANDIDATE
            anchors: [azure, compute, batch, java, azure-compute-batch-java]
      azure-containerregistry-py:
        path: skills/engineering_cloud_azure/azure-containerregistry-py/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.azure_containerregistry_py
            path: skills/engineering_cloud_azure/azure-containerregistry-py/SKILL.md
            status: CANDIDATE
            anchors: [azure, containerregistry, azure-containerregistry-py, delete, manifest]
      azure-cosmos-db-py:
        path: skills/engineering_cloud_azure/azure-cosmos-db-py/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.azure_cosmos_db_py
            path: skills/engineering_cloud_azure/azure-cosmos-db-py/SKILL.md
            status: CANDIDATE
            anchors: [azure, cosmos, build, nosql, services]
      azure-cosmos-java:
        path: skills/engineering_cloud_azure/azure-cosmos-java/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.azure_cosmos_java
            path: skills/engineering_cloud_azure/azure-cosmos-java/SKILL.md
            status: CANDIDATE
            anchors: [azure, cosmos, java, azure-cosmos-java, client]
      azure-cosmos-py:
        path: skills/engineering_cloud_azure/azure-cosmos-py/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.azure_cosmos_py
            path: skills/engineering_cloud_azure/azure-cosmos-py/SKILL.md
            status: CANDIDATE
            anchors: [azure, cosmos, azure-cosmos-py, partition, key]
      azure-cosmos-rust:
        path: skills/engineering_cloud_azure/azure-cosmos-rust/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.azure_cosmos_rust
            path: skills/engineering_cloud_azure/azure-cosmos-rust/SKILL.md
            status: CANDIDATE
            anchors: [azure, cosmos, rust, azure-cosmos-rust, item]
      azure-cosmos-ts:
        path: skills/engineering_cloud_azure/azure-cosmos-ts/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.azure_cosmos_ts
            path: skills/engineering_cloud_azure/azure-cosmos-ts/SKILL.md
            status: CANDIDATE
            anchors: [azure, cosmos, azure-cosmos-ts, document, operations]
      azure-cost:
        path: skills/engineering_cloud_azure/azure-cost/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.azure_cost
            path: skills/engineering_cloud_azure/azure-cost/SKILL.md
            status: CANDIDATE
      azure-data-tables-java:
        path: skills/engineering_cloud_azure/azure-data-tables-java/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.azure_data_tables_java
            path: skills/engineering_cloud_azure/azure-data-tables-java/SKILL.md
            status: CANDIDATE
            anchors: [azure, data, tables, java, build]
      azure-data-tables-py:
        path: skills/engineering_cloud_azure/azure-data-tables-py/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.azure_data_tables_py
            path: skills/engineering_cloud_azure/azure-data-tables-py/SKILL.md
            status: CANDIDATE
            anchors: [azure, data, tables, azure-data-tables-py, table]
      azure-deploy:
        path: skills/engineering_cloud_azure/azure-deploy/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.azure_deploy
            path: skills/engineering_cloud_azure/azure-deploy/SKILL.md
            status: CANDIDATE
            anchors: [azure, deploy, execute, deployments, already]
      azure-diagnostics:
        path: skills/engineering_cloud_azure/azure-diagnostics/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.azure_diagnostics
            path: skills/engineering_cloud_azure/azure-diagnostics/SKILL.md
            status: CANDIDATE
            anchors: [azure, diagnostics, debug, production, issues]
      azure-enterprise-infra-planner:
        path: skills/engineering_cloud_azure/azure-enterprise-infra-planner/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.azure_enterprise_infra_planner
            path: skills/engineering_cloud_azure/azure-enterprise-infra-planner/SKILL.md
            status: CANDIDATE
            anchors: [azure, enterprise, infra, planner, architect]
      azure-eventgrid-dotnet:
        path: skills/engineering_cloud_azure/azure-eventgrid-dotnet/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.azure_eventgrid_dotnet
            path: skills/engineering_cloud_azure/azure-eventgrid-dotnet/SKILL.md
            status: CANDIDATE
            anchors: [azure, eventgrid, dotnet, azure-eventgrid-dotnet, events]
      azure-eventgrid-java:
        path: skills/engineering_cloud_azure/azure-eventgrid-java/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.azure_eventgrid_java
            path: skills/engineering_cloud_azure/azure-eventgrid-java/SKILL.md
            status: CANDIDATE
            anchors: [azure, eventgrid, java, build, event]
      azure-eventgrid-py:
        path: skills/engineering_cloud_azure/azure-eventgrid-py/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.azure_eventgrid_py
            path: skills/engineering_cloud_azure/azure-eventgrid-py/SKILL.md
            status: CANDIDATE
            anchors: [azure, eventgrid, azure-eventgrid-py, event, properties]
      azure-eventhub-dotnet:
        path: skills/engineering_cloud_azure/azure-eventhub-dotnet/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.azure_eventhub_dotnet
            path: skills/engineering_cloud_azure/azure-eventhub-dotnet/SKILL.md
            status: CANDIDATE
            anchors: [azure, eventhub, dotnet, azure-eventhub-dotnet, receiving]
      azure-eventhub-java:
        path: skills/engineering_cloud_azure/azure-eventhub-java/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.azure_eventhub_java
            path: skills/engineering_cloud_azure/azure-eventhub-java/SKILL.md
            status: CANDIDATE
            anchors: [azure, eventhub, java, build, real]
      azure-eventhub-py:
        path: skills/engineering_cloud_azure/azure-eventhub-py/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.azure_eventhub_py
            path: skills/engineering_cloud_azure/azure-eventhub-py/SKILL.md
            status: CANDIDATE
            anchors: [azure, eventhub, azure-eventhub-py, partition, event]
      azure-eventhub-rust:
        path: skills/engineering_cloud_azure/azure-eventhub-rust/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.azure_eventhub_rust
            path: skills/engineering_cloud_azure/azure-eventhub-rust/SKILL.md
            status: CANDIDATE
            anchors: [azure, eventhub, rust, azure-eventhub-rust, event]
      azure-eventhub-ts:
        path: skills/engineering_cloud_azure/azure-eventhub-ts/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.azure_eventhub_ts
            path: skills/engineering_cloud_azure/azure-eventhub-ts/SKILL.md
            status: CANDIDATE
            anchors: [azure, eventhub, build, event, streaming]
      azure-hosted-copilot-sdk:
        path: skills/engineering_cloud_azure/azure-hosted-copilot-sdk/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.azure_hosted_copilot_sdk
            path: skills/engineering_cloud_azure/azure-hosted-copilot-sdk/SKILL.md
            status: CANDIDATE
            anchors: [azure, hosted, copilot, build, deploy]
      azure-identity-dotnet:
        path: skills/engineering_cloud_azure/azure-identity-dotnet/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.azure_identity_dotnet
            path: skills/engineering_cloud_azure/azure-identity-dotnet/SKILL.md
            status: CANDIDATE
            anchors: [azure, identity, dotnet, azure-identity-dotnet, credential]
      azure-identity-java:
        path: skills/engineering_cloud_azure/azure-identity-java/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.azure_identity_java
            path: skills/engineering_cloud_azure/azure-identity-java/SKILL.md
            status: CANDIDATE
            anchors: [azure, identity, java, library, authentication]
      azure-identity-py:
        path: skills/engineering_cloud_azure/azure-identity-py/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.azure_identity_py
            path: skills/engineering_cloud_azure/azure-identity-py/SKILL.md
            status: CANDIDATE
            anchors: [azure, identity, azure-identity-py, credential, credentials]
      azure-identity-rust:
        path: skills/engineering_cloud_azure/azure-identity-rust/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.azure_identity_rust
            path: skills/engineering_cloud_azure/azure-identity-rust/SKILL.md
            status: CANDIDATE
            anchors: [azure, identity, rust, azure-identity-rust, credential]
      azure-identity-ts:
        path: skills/engineering_cloud_azure/azure-identity-ts/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.azure_identity_ts
            path: skills/engineering_cloud_azure/azure-identity-ts/SKILL.md
            status: CANDIDATE
            anchors: [azure, identity, authenticate, services, library]
      azure-keyvault-certificates-rust:
        path: skills/engineering_cloud_azure/azure-keyvault-certificates-rust/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.azure_keyvault_certificates_rust
            path: skills/engineering_cloud_azure/azure-keyvault-certificates-rust/SKILL.md
            status: CANDIDATE
            anchors: [azure, keyvault, certificates, rust, azure-keyvault-certificates-rust]
      azure-keyvault-keys-rust:
        path: skills/engineering_cloud_azure/azure-keyvault-keys-rust/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.azure_keyvault_keys_rust
            path: skills/engineering_cloud_azure/azure-keyvault-keys-rust/SKILL.md
            status: CANDIDATE
            anchors: [azure, keyvault, keys, rust, azure-keyvault-keys-rust]
      azure-keyvault-keys-ts:
        path: skills/engineering_cloud_azure/azure-keyvault-keys-ts/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.azure_keyvault_keys_ts
            path: skills/engineering_cloud_azure/azure-keyvault-keys-ts/SKILL.md
            status: CANDIDATE
            anchors: [azure, keyvault, keys, manage, cryptographic]
      azure-keyvault-py:
        path: skills/engineering_cloud_azure/azure-keyvault-py/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.azure_keyvault_py
            path: skills/engineering_cloud_azure/azure-keyvault-py/SKILL.md
            status: CANDIDATE
            anchors: [azure, keyvault, azure-keyvault-py, key, secret]
      azure-keyvault-secrets-rust:
        path: skills/engineering_cloud_azure/azure-keyvault-secrets-rust/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.azure_keyvault_secrets_rust
            path: skills/engineering_cloud_azure/azure-keyvault-secrets-rust/SKILL.md
            status: CANDIDATE
            anchors: [azure, keyvault, secrets, rust, azure-keyvault-secrets-rust]
      azure-keyvault-secrets-ts:
        path: skills/engineering_cloud_azure/azure-keyvault-secrets-ts/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.azure_keyvault_secrets_ts
            path: skills/engineering_cloud_azure/azure-keyvault-secrets-ts/SKILL.md
            status: CANDIDATE
            anchors: [azure, keyvault, secrets, manage, vault]
      azure-kubernetes:
        path: skills/engineering_cloud_azure/azure-kubernetes/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.azure_kubernetes
            path: skills/engineering_cloud_azure/azure-kubernetes/SKILL.md
            status: CANDIDATE
            anchors: [azure, kubernetes, plan, create, configure]
      azure-kusto:
        path: skills/engineering_cloud_azure/azure-kusto/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.azure_kusto
            path: skills/engineering_cloud_azure/azure-kusto/SKILL.md
            status: CANDIDATE
            anchors: [azure, kusto, query, analyze, data]
      azure-maps-search-dotnet:
        path: skills/engineering_cloud_azure/azure-maps-search-dotnet/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.azure_maps_search_dotnet
            path: skills/engineering_cloud_azure/azure-maps-search-dotnet/SKILL.md
            status: CANDIDATE
            anchors: [azure, maps, search, dotnet, azure-maps-search-dotnet]
      azure-messaging:
        path: skills/engineering_cloud_azure/azure-messaging/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.azure_messaging
            path: skills/engineering_cloud_azure/azure-messaging/SKILL.md
            status: CANDIDATE
            anchors: [azure, messaging, troubleshoot, resolve, issues]
      azure-messaging-webpubsub-java:
        path: skills/engineering_cloud_azure/azure-messaging-webpubsub-java/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.azure_messaging_webpubsub_java
            path: skills/engineering_cloud_azure/azure-messaging-webpubsub-java/SKILL.md
            status: CANDIDATE
            anchors: [azure, messaging, webpubsub, java, build]
      azure-messaging-webpubsubservice-py:
        path: skills/engineering_cloud_azure/azure-messaging-webpubsubservice-py/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.azure_messaging_webpubsubservice_py
            path: skills/engineering_cloud_azure/azure-messaging-webpubsubservice-py/SKILL.md
            status: CANDIDATE
            anchors: [azure, messaging, webpubsubservice, azure-messaging-webpubsubservice-py, client]
      azure-mgmt-apicenter-dotnet:
        path: skills/engineering_cloud_azure/azure-mgmt-apicenter-dotnet/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.azure_mgmt_apicenter_dotnet
            path: skills/engineering_cloud_azure/azure-mgmt-apicenter-dotnet/SKILL.md
            status: CANDIDATE
            anchors: [azure, mgmt, apicenter, dotnet, azure-mgmt-apicenter-dotnet]
      azure-mgmt-apicenter-py:
        path: skills/engineering_cloud_azure/azure-mgmt-apicenter-py/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.azure_mgmt_apicenter_py
            path: skills/engineering_cloud_azure/azure-mgmt-apicenter-py/SKILL.md
            status: CANDIDATE
            anchors: [azure, mgmt, apicenter, azure-mgmt-apicenter-py, api]
      azure-mgmt-apimanagement-dotnet:
        path: skills/engineering_cloud_azure/azure-mgmt-apimanagement-dotnet/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.azure_mgmt_apimanagement_dotnet
            path: skills/engineering_cloud_azure/azure-mgmt-apimanagement-dotnet/SKILL.md
            status: CANDIDATE
            anchors: [azure, mgmt, apimanagement, dotnet, azure-mgmt-apimanagement-dotnet]
      azure-mgmt-apimanagement-py:
        path: skills/engineering_cloud_azure/azure-mgmt-apimanagement-py/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.azure_mgmt_apimanagement_py
            path: skills/engineering_cloud_azure/azure-mgmt-apimanagement-py/SKILL.md
            status: CANDIDATE
            anchors: [azure, mgmt, apimanagement, azure-mgmt-apimanagement-py, create]
      azure-mgmt-applicationinsights-dotnet:
        path: skills/engineering_cloud_azure/azure-mgmt-applicationinsights-dotnet/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.azure_mgmt_applicationinsights_dotnet
            path: skills/engineering_cloud_azure/azure-mgmt-applicationinsights-dotnet/SKILL.md
            status: CANDIDATE
            anchors: [azure, mgmt, applicationinsights, dotnet, azure-mgmt-applicationinsights-dotnet]
      azure-mgmt-arizeaiobservabilityeval-dotnet:
        path: skills/engineering_cloud_azure/azure-mgmt-arizeaiobservabilityeval-dotnet/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.azure_mgmt_arizeaiobservabilityeval_dotnet
            path: skills/engineering_cloud_azure/azure-mgmt-arizeaiobservabilityeval-dotnet/SKILL.md
            status: CANDIDATE
            anchors: [azure, mgmt, arizeaiobservabilityeval, dotnet, resource]
      azure-mgmt-botservice-dotnet:
        path: skills/engineering_cloud_azure/azure-mgmt-botservice-dotnet/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.azure_mgmt_botservice_dotnet
            path: skills/engineering_cloud_azure/azure-mgmt-botservice-dotnet/SKILL.md
            status: CANDIDATE
            anchors: [azure, mgmt, botservice, dotnet, azure-mgmt-botservice-dotnet]
      azure-mgmt-botservice-py:
        path: skills/engineering_cloud_azure/azure-mgmt-botservice-py/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.azure_mgmt_botservice_py
            path: skills/engineering_cloud_azure/azure-mgmt-botservice-py/SKILL.md
            status: CANDIDATE
            anchors: [azure, mgmt, botservice, azure-mgmt-botservice-py, bot]
      azure-mgmt-fabric-dotnet:
        path: skills/engineering_cloud_azure/azure-mgmt-fabric-dotnet/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.azure_mgmt_fabric_dotnet
            path: skills/engineering_cloud_azure/azure-mgmt-fabric-dotnet/SKILL.md
            status: CANDIDATE
            anchors: [azure, mgmt, fabric, dotnet, azure-mgmt-fabric-dotnet]
      azure-mgmt-fabric-py:
        path: skills/engineering_cloud_azure/azure-mgmt-fabric-py/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.azure_mgmt_fabric_py
            path: skills/engineering_cloud_azure/azure-mgmt-fabric-py/SKILL.md
            status: CANDIDATE
            anchors: [azure, mgmt, fabric, azure-mgmt-fabric-py, capacity]
      azure-mgmt-mongodbatlas-dotnet:
        path: skills/engineering_cloud_azure/azure-mgmt-mongodbatlas-dotnet/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.azure_mgmt_mongodbatlas_dotnet
            path: skills/engineering_cloud_azure/azure-mgmt-mongodbatlas-dotnet/SKILL.md
            status: CANDIDATE
            anchors: [azure, mgmt, mongodbatlas, dotnet, manage]
      azure-mgmt-weightsandbiases-dotnet:
        path: skills/engineering_cloud_azure/azure-mgmt-weightsandbiases-dotnet/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.azure_mgmt_weightsandbiases_dotnet
            path: skills/engineering_cloud_azure/azure-mgmt-weightsandbiases-dotnet/SKILL.md
            status: CANDIDATE
            anchors: [azure, mgmt, weightsandbiases, dotnet, azure-mgmt-weightsandbiases-dotnet]
      azure-microsoft-playwright-testing-ts:
        path: skills/engineering_cloud_azure/azure-microsoft-playwright-testing-ts/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.azure_microsoft_playwright_testing_ts
            path: skills/engineering_cloud_azure/azure-microsoft-playwright-testing-ts/SKILL.md
            status: CANDIDATE
            anchors: [azure, microsoft, playwright, testing, tests]
      azure-monitor-ingestion-java:
        path: skills/engineering_cloud_azure/azure-monitor-ingestion-java/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.azure_monitor_ingestion_java
            path: skills/engineering_cloud_azure/azure-monitor-ingestion-java/SKILL.md
            status: CANDIDATE
            anchors: [azure, monitor, ingestion, java, azure-monitor-ingestion-java]
      azure-monitor-ingestion-py:
        path: skills/engineering_cloud_azure/azure-monitor-ingestion-py/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.azure_monitor_ingestion_py
            path: skills/engineering_cloud_azure/azure-monitor-ingestion-py/SKILL.md
            status: CANDIDATE
            anchors: [azure, monitor, ingestion, azure-monitor-ingestion-py, dcr]
      azure-monitor-opentelemetry-exporter-java:
        path: skills/engineering_cloud_azure/azure-monitor-opentelemetry-exporter-java/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.azure_monitor_opentelemetry_exporter_java
            path: skills/engineering_cloud_azure/azure-monitor-opentelemetry-exporter-java/SKILL.md
            status: CANDIDATE
            anchors: [azure, monitor, opentelemetry, exporter, java]
      azure-monitor-opentelemetry-exporter-py:
        path: skills/engineering_cloud_azure/azure-monitor-opentelemetry-exporter-py/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.azure_monitor_opentelemetry_exporter_py
            path: skills/engineering_cloud_azure/azure-monitor-opentelemetry-exporter-py/SKILL.md
            status: CANDIDATE
            anchors: [azure, monitor, opentelemetry, exporter, azure-monitor-opentelemetry-exporter-py]
      azure-monitor-opentelemetry-py:
        path: skills/engineering_cloud_azure/azure-monitor-opentelemetry-py/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.azure_monitor_opentelemetry_py
            path: skills/engineering_cloud_azure/azure-monitor-opentelemetry-py/SKILL.md
            status: CANDIDATE
            anchors: [azure, monitor, opentelemetry, azure-monitor-opentelemetry-py, custom]
      azure-monitor-opentelemetry-ts:
        path: skills/engineering_cloud_azure/azure-monitor-opentelemetry-ts/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.azure_monitor_opentelemetry_ts
            path: skills/engineering_cloud_azure/azure-monitor-opentelemetry-ts/SKILL.md
            status: CANDIDATE
            anchors: [azure, monitor, opentelemetry, instrument, applications]
      azure-monitor-query-java:
        path: skills/engineering_cloud_azure/azure-monitor-query-java/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.azure_monitor_query_java
            path: skills/engineering_cloud_azure/azure-monitor-query-java/SKILL.md
            status: CANDIDATE
            anchors: [azure, monitor, query, java, azure-monitor-query-java]
      azure-monitor-query-py:
        path: skills/engineering_cloud_azure/azure-monitor-query-py/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.azure_monitor_query_py
            path: skills/engineering_cloud_azure/azure-monitor-query-py/SKILL.md
            status: CANDIDATE
            anchors: [azure, monitor, query, azure-monitor-query-py, metrics]
      azure-postgres-ts:
        path: skills/engineering_cloud_azure/azure-postgres-ts/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.azure_postgres_ts
            path: skills/engineering_cloud_azure/azure-postgres-ts/SKILL.md
            status: CANDIDATE
            anchors: [azure, postgres, azure-postgres-ts, connection, pool]
      azure-prepare:
        path: skills/engineering_cloud_azure/azure-prepare/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.azure_prepare
            path: skills/engineering_cloud_azure/azure-prepare/SKILL.md
            status: CANDIDATE
      azure-quotas:
        path: skills/engineering_cloud_azure/azure-quotas/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.azure_quotas
            path: skills/engineering_cloud_azure/azure-quotas/SKILL.md
            status: CANDIDATE
      azure-rbac:
        path: skills/engineering_cloud_azure/azure-rbac/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.azure_rbac
            path: skills/engineering_cloud_azure/azure-rbac/SKILL.md
            status: CANDIDATE
            anchors: [azure, rbac, helps, find, right]
      azure-resource-lookup:
        path: skills/engineering_cloud_azure/azure-resource-lookup/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.azure_resource_lookup
            path: skills/engineering_cloud_azure/azure-resource-lookup/SKILL.md
            status: CANDIDATE
            anchors: [azure, resource, lookup, azure-resource-lookup, resources]
      azure-resource-manager-cosmosdb-dotnet:
        path: skills/engineering_cloud_azure/azure-resource-manager-cosmosdb-dotnet/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.azure_resource_manager_cosmosdb_dotnet
            path: skills/engineering_cloud_azure/azure-resource-manager-cosmosdb-dotnet/SKILL.md
            status: CANDIDATE
            anchors: [azure, resource, manager, cosmosdb, dotnet]
      azure-resource-manager-durabletask-dotnet:
        path: skills/engineering_cloud_azure/azure-resource-manager-durabletask-dotnet/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.azure_resource_manager_durabletask_dotnet
            path: skills/engineering_cloud_azure/azure-resource-manager-durabletask-dotnet/SKILL.md
            status: CANDIDATE
            anchors: [azure, resource, manager, durabletask, dotnet]
      azure-resource-manager-mysql-dotnet:
        path: skills/engineering_cloud_azure/azure-resource-manager-mysql-dotnet/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.azure_resource_manager_mysql_dotnet
            path: skills/engineering_cloud_azure/azure-resource-manager-mysql-dotnet/SKILL.md
            status: CANDIDATE
            anchors: [azure, resource, manager, mysql, dotnet]
      azure-resource-manager-playwright-dotnet:
        path: skills/engineering_cloud_azure/azure-resource-manager-playwright-dotnet/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.azure_resource_manager_playwright_dotnet
            path: skills/engineering_cloud_azure/azure-resource-manager-playwright-dotnet/SKILL.md
            status: CANDIDATE
            anchors: [azure, resource, manager, playwright, dotnet]
      azure-resource-manager-postgresql-dotnet:
        path: skills/engineering_cloud_azure/azure-resource-manager-postgresql-dotnet/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.azure_resource_manager_postgresql_dotnet
            path: skills/engineering_cloud_azure/azure-resource-manager-postgresql-dotnet/SKILL.md
            status: CANDIDATE
            anchors: [azure, resource, manager, postgresql, dotnet]
      azure-resource-manager-redis-dotnet:
        path: skills/engineering_cloud_azure/azure-resource-manager-redis-dotnet/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.azure_resource_manager_redis_dotnet
            path: skills/engineering_cloud_azure/azure-resource-manager-redis-dotnet/SKILL.md
            status: CANDIDATE
            anchors: [azure, resource, manager, redis, dotnet]
      azure-resource-manager-sql-dotnet:
        path: skills/engineering_cloud_azure/azure-resource-manager-sql-dotnet/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.azure_resource_manager_sql_dotnet
            path: skills/engineering_cloud_azure/azure-resource-manager-sql-dotnet/SKILL.md
            status: CANDIDATE
            anchors: [azure, resource, manager, dotnet, azure-resource-manager-sql-dotnet]
      azure-resource-visualizer:
        path: skills/engineering_cloud_azure/azure-resource-visualizer/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.azure_resource_visualizer
            path: skills/engineering_cloud_azure/azure-resource-visualizer/SKILL.md
            status: CANDIDATE
            anchors: [azure, resource, visualizer, analyze, groups]
      azure-search-documents-dotnet:
        path: skills/engineering_cloud_azure/azure-search-documents-dotnet/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.azure_search_documents_dotnet
            path: skills/engineering_cloud_azure/azure-search-documents-dotnet/SKILL.md
            status: CANDIDATE
            anchors: [azure, search, documents, dotnet, azure-search-documents-dotnet]
      azure-search-documents-py:
        path: skills/engineering_cloud_azure/azure-search-documents-py/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.azure_search_documents_py
            path: skills/engineering_cloud_azure/azure-search-documents-py/SKILL.md
            status: CANDIDATE
            anchors: [azure, search, documents, azure-search-documents-py, vector]
      azure-search-documents-ts:
        path: skills/engineering_cloud_azure/azure-search-documents-ts/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.azure_search_documents_ts
            path: skills/engineering_cloud_azure/azure-search-documents-ts/SKILL.md
            status: CANDIDATE
            anchors: [azure, search, documents, build, applications]
      azure-security-keyvault-keys-dotnet:
        path: skills/engineering_cloud_azure/azure-security-keyvault-keys-dotnet/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.azure_security_keyvault_keys_dotnet
            path: skills/engineering_cloud_azure/azure-security-keyvault-keys-dotnet/SKILL.md
            status: CANDIDATE
            anchors: [azure, security, keyvault, keys, dotnet]
      azure-security-keyvault-keys-java:
        path: skills/engineering_cloud_azure/azure-security-keyvault-keys-java/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.azure_security_keyvault_keys_java
            path: skills/engineering_cloud_azure/azure-security-keyvault-keys-java/SKILL.md
            status: CANDIDATE
            anchors: [azure, security, keyvault, keys, java]
      azure-security-keyvault-secrets-java:
        path: skills/engineering_cloud_azure/azure-security-keyvault-secrets-java/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.azure_security_keyvault_secrets_java
            path: skills/engineering_cloud_azure/azure-security-keyvault-secrets-java/SKILL.md
            status: CANDIDATE
            anchors: [azure, security, keyvault, secrets, java]
      azure-servicebus-dotnet:
        path: skills/engineering_cloud_azure/azure-servicebus-dotnet/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.azure_servicebus_dotnet
            path: skills/engineering_cloud_azure/azure-servicebus-dotnet/SKILL.md
            status: CANDIDATE
            anchors: [azure, servicebus, dotnet, azure-servicebus-dotnet, net]
      azure-servicebus-py:
        path: skills/engineering_cloud_azure/azure-servicebus-py/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.azure_servicebus_py
            path: skills/engineering_cloud_azure/azure-servicebus-py/SKILL.md
            status: CANDIDATE
            anchors: [azure, servicebus, azure-servicebus-py, receive, messages]
      azure-servicebus-ts:
        path: skills/engineering_cloud_azure/azure-servicebus-ts/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.azure_servicebus_ts
            path: skills/engineering_cloud_azure/azure-servicebus-ts/SKILL.md
            status: CANDIDATE
            anchors: [azure, servicebus, build, messaging, applications]
      azure-speech-to-text-rest-py:
        path: skills/engineering_cloud_azure/azure-speech-to-text-rest-py/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.azure_speech_to_text_rest_py
            path: skills/engineering_cloud_azure/azure-speech-to-text-rest-py/SKILL.md
            status: CANDIDATE
            anchors: [azure, speech, text, rest, azure-speech-to-text-rest-py]
      azure-storage:
        path: skills/engineering_cloud_azure/azure-storage/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.azure_storage
            path: skills/engineering_cloud_azure/azure-storage/SKILL.md
            status: CANDIDATE
            anchors: [azure, storage, services, including, blob]
      azure-storage-blob-java:
        path: skills/engineering_cloud_azure/azure-storage-blob-java/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.azure_storage_blob_java
            path: skills/engineering_cloud_azure/azure-storage-blob-java/SKILL.md
            status: CANDIDATE
            anchors: [azure, storage, blob, java, build]
      azure-storage-blob-py:
        path: skills/engineering_cloud_azure/azure-storage-blob-py/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.azure_storage_blob_py
            path: skills/engineering_cloud_azure/azure-storage-blob-py/SKILL.md
            status: CANDIDATE
            anchors: [azure, storage, blob, azure-storage-blob-py, download]
      azure-storage-blob-rust:
        path: skills/engineering_cloud_azure/azure-storage-blob-rust/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.azure_storage_blob_rust
            path: skills/engineering_cloud_azure/azure-storage-blob-rust/SKILL.md
            status: CANDIDATE
            anchors: [azure, storage, blob, rust, azure-storage-blob-rust]
      azure-storage-blob-ts:
        path: skills/engineering_cloud_azure/azure-storage-blob-ts/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.azure_storage_blob_ts
            path: skills/engineering_cloud_azure/azure-storage-blob-ts/SKILL.md
            status: CANDIDATE
            anchors: [azure, storage, blob, azure-storage-blob-ts, node]
      azure-storage-file-datalake-py:
        path: skills/engineering_cloud_azure/azure-storage-file-datalake-py/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.azure_storage_file_datalake_py
            path: skills/engineering_cloud_azure/azure-storage-file-datalake-py/SKILL.md
            status: CANDIDATE
            anchors: [azure, storage, file, datalake, azure-storage-file-datalake-py]
      azure-storage-file-share-py:
        path: skills/engineering_cloud_azure/azure-storage-file-share-py/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.azure_storage_file_share_py
            path: skills/engineering_cloud_azure/azure-storage-file-share-py/SKILL.md
            status: CANDIDATE
            anchors: [azure, storage, file, share, azure-storage-file-share-py]
      azure-storage-file-share-ts:
        path: skills/engineering_cloud_azure/azure-storage-file-share-ts/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.azure_storage_file_share_ts
            path: skills/engineering_cloud_azure/azure-storage-file-share-ts/SKILL.md
            status: CANDIDATE
            anchors: [azure, storage, file, share, azure-storage-file-share-ts]
      azure-storage-queue-py:
        path: skills/engineering_cloud_azure/azure-storage-queue-py/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.azure_storage_queue_py
            path: skills/engineering_cloud_azure/azure-storage-queue-py/SKILL.md
            status: CANDIDATE
            anchors: [azure, storage, queue, azure-storage-queue-py, messages]
      azure-storage-queue-ts:
        path: skills/engineering_cloud_azure/azure-storage-queue-ts/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.azure_storage_queue_ts
            path: skills/engineering_cloud_azure/azure-storage-queue-ts/SKILL.md
            status: CANDIDATE
            anchors: [azure, storage, queue, azure-storage-queue-ts, message]
      azure-upgrade:
        path: skills/engineering_cloud_azure/azure-upgrade/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.azure_upgrade
            path: skills/engineering_cloud_azure/azure-upgrade/SKILL.md
            status: CANDIDATE
            anchors: [azure, upgrade, assess, workloads, between]
      azure-validate:
        path: skills/engineering_cloud_azure/azure-validate/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.azure_validate
            path: skills/engineering_cloud_azure/azure-validate/SKILL.md
            status: CANDIDATE
            anchors: [azure, validate, azure-validate, .azure/deployment-plan.md, validation]
      azure-web-pubsub-ts:
        path: skills/engineering_cloud_azure/azure-web-pubsub-ts/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.azure_web_pubsub_ts
            path: skills/engineering_cloud_azure/azure-web-pubsub-ts/SKILL.md
            status: CANDIDATE
            anchors: [azure, pubsub, build, real, time]
      capacity:
        path: skills/engineering_cloud_azure/capacity/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.capacity
            path: skills/engineering_cloud_azure/capacity/SKILL.md
            status: CANDIDATE
            anchors: [capacity, discovers, available, azure, openai]
      cloud-security:
        path: skills/engineering_cloud_azure/cloud-security/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.cloud_security
            path: skills/engineering_cloud_azure/cloud-security/SKILL.md
            status: CANDIDATE
            anchors: [cloud, security, when, assessing, infrastructure]
      cloud-solution-architect:
        path: skills/engineering_cloud_azure/cloud-solution-architect/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.cloud_solution_architect
            path: skills/engineering_cloud_azure/cloud-solution-architect/SKILL.md
            status: CANDIDATE
            anchors: [cloud, solution, architect, cloud-solution-architect, design]
      copilot-sdk:
        path: skills/engineering_cloud_azure/copilot-sdk/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.copilot_sdk
            path: skills/engineering_cloud_azure/copilot-sdk/SKILL.md
            status: CANDIDATE
            anchors: [copilot, build, applications, powered, github]
      customize:
        path: skills/engineering_cloud_azure/customize/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.customize
            path: skills/engineering_cloud_azure/customize/SKILL.md
            status: CANDIDATE
            anchors: [customize, interactive, guided, deployment, flow]
      deploy-model:
        path: skills/engineering_cloud_azure/deploy-model/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.deploy_model
            path: skills/engineering_cloud_azure/deploy-model/SKILL.md
            status: CANDIDATE
            anchors: [deploy, model, unified, azure, openai]
      entra-app-registration:
        path: skills/engineering_cloud_azure/entra-app-registration/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.entra_app_registration
            path: skills/engineering_cloud_azure/entra-app-registration/SKILL.md
            status: CANDIDATE
            anchors: [entra, registration, guides, microsoft, oauth]
      hosted-agents-v2-py:
        path: skills/engineering_cloud_azure/hosted-agents-v2-py/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.hosted_agents_v2_py
            path: skills/engineering_cloud_azure/hosted-agents-v2-py/SKILL.md
            status: CANDIDATE
      m365-agents-dotnet:
        path: skills/engineering_cloud_azure/m365-agents-dotnet/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.m365_agents_dotnet
            path: skills/engineering_cloud_azure/m365-agents-dotnet/SKILL.md
            status: CANDIDATE
            anchors: [m365, agents, dotnet, agents-dotnet, net]
      mcp-builder:
        path: skills/engineering_cloud_azure/mcp-builder/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.mcp_builder
            path: skills/engineering_cloud_azure/mcp-builder/SKILL.md
            status: CANDIDATE
            anchors: [builder, guide, creating, high, quality]
      microsoft-azure-webjobs-extensions-authentication-events-dotnet:
        path: skills/engineering_cloud_azure/microsoft-azure-webjobs-extensions-authentication-events-dotnet/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.microsoft_azure_webjobs_extensions_authentication_events_dotnet
            path: skills/engineering_cloud_azure/microsoft-azure-webjobs-extensions-authentication-events-dotnet/SKILL.md
            status: CANDIDATE
            anchors: [microsoft, azure, webjobs, extensions, authentication]
      microsoft-docs:
        path: skills/engineering_cloud_azure/microsoft-docs/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.microsoft_docs
            path: skills/engineering_cloud_azure/microsoft-docs/SKILL.md
            status: CANDIDATE
            anchors: [microsoft, docs, understand, technologies, querying]
      microsoft-foundry:
        path: skills/engineering_cloud_azure/microsoft-foundry/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.microsoft_foundry
            path: skills/engineering_cloud_azure/microsoft-foundry/SKILL.md
            status: CANDIDATE
            anchors: [microsoft, foundry, deploy, evaluate, manage]
      ms365-tenant-manager:
        path: skills/engineering_cloud_azure/ms365-tenant-manager/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.ms365_tenant_manager
            path: skills/engineering_cloud_azure/ms365-tenant-manager/SKILL.md
            status: CANDIDATE
            anchors: [ms365, tenant, manager, microsoft, administration]
      podcast-generation:
        path: skills/engineering_cloud_azure/podcast-generation/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.podcast_generation
            path: skills/engineering_cloud_azure/podcast-generation/SKILL.md
            status: CANDIDATE
            anchors: [podcast, generation, generate, powered, style]
      preset:
        path: skills/engineering_cloud_azure/preset/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.preset
            path: skills/engineering_cloud_azure/preset/SKILL.md
            status: CANDIDATE
            anchors: [preset, intelligently, deploys, azure, openai]
      secrets-vault-manager:
        path: skills/engineering_cloud_azure/secrets-vault-manager/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.secrets_vault_manager
            path: skills/engineering_cloud_azure/secrets-vault-manager/SKILL.md
            status: CANDIDATE
            anchors: [secrets, vault, manager, when, secrets-vault-manager]
      senior-devops:
        path: skills/engineering_cloud_azure/senior-devops/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.senior_devops
            path: skills/engineering_cloud_azure/senior-devops/SKILL.md
            status: CANDIDATE
            anchors: [senior, devops, comprehensive, skill, infrastructure]
      skill-creator:
        path: skills/engineering_cloud_azure/skill-creator/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.skill_creator
            path: skills/engineering_cloud_azure/skill-creator/SKILL.md
            status: CANDIDATE
            anchors: [skill, creator, guide, creating, effective]
      wiki-ado-convert:
        path: skills/engineering_cloud_azure/wiki-ado-convert/
        skill_count: 1
        skills:
          - skill: engineering_cloud_azure.wiki_ado_convert
            path: skills/engineering_cloud_azure/wiki-ado-convert/SKILL.md
            status: CANDIDATE
            anchors: [wiki, convert, converts, vitepress, markdown]

  ENGINEERING_CLOUD_GCP:
    path: skills/engineering_cloud_gcp/
    display_name: "Engineering — Cloud GCP"
    skill_count: 2
    anchors: [composio, skills, automate, google, bigquery, tasks, googlebigquery-automation, via, cloud, architect, design, architectures, startups, enterprises, gcp-cloud-architect]
    sub_domains:
      composio-skills:
        path: skills/engineering_cloud_gcp/composio-skills/
        skill_count: 1
        skills:
          - skill: engineering_cloud_gcp.composio_skills
            path: skills/engineering_cloud_gcp/composio-skills/SKILL.md
            status: CANDIDATE
            anchors: [composio, skills, automate, google, bigquery]
      gcp-cloud-architect:
        path: skills/engineering_cloud_gcp/gcp-cloud-architect/
        skill_count: 1
        skills:
          - skill: engineering_cloud_gcp.gcp_cloud_architect
            path: skills/engineering_cloud_gcp/gcp-cloud-architect/SKILL.md
            status: CANDIDATE
            anchors: [cloud, architect, design, architectures, startups]

  ENGINEERING_DATABASE:
    path: skills/engineering_database/
    display_name: "Engineering — Database"
    skill_count: 13
    anchors: [the, database, when, create, skills, postgres, claude, designer, optimization, query, strategies, and, patterns, including, composio]
    sub_domains:
      composio-skills:
        path: skills/engineering_database/composio-skills/
        skill_count: 1
        skills:
          - skill: engineering_database.composio_skills
            path: skills/engineering_database/composio-skills/SKILL.md
            status: CANDIDATE
            anchors: [composio, skills, automate, neon, serverless]
      connect:
        path: skills/engineering_database/connect/
        skill_count: 1
        skills:
          - skill: engineering_database.connect
            path: skills/engineering_database/connect/SKILL.md
            status: CANDIDATE
            anchors: [claude, send, emails, create, issues]
      database-designer:
        path: skills/engineering_database/database-designer/
        skill_count: 1
        skills:
          - skill: engineering_database.database_designer
            path: skills/engineering_database/database-designer/SKILL.md
            status: CANDIDATE
            anchors: [database, designer, when, design, database-designer]
      database-optimization:
        path: skills/engineering_database/database-optimization/
        skill_count: 1
        skills:
          - skill: engineering_database.database_optimization
            path: skills/engineering_database/database-optimization/SKILL.md
            status: CANDIDATE
            anchors: [database, optimization, query, indexing, strategies]
      database-schema-designer:
        path: skills/engineering_database/database-schema-designer/
        skill_count: 1
        skills:
          - skill: engineering_database.database_schema_designer
            path: skills/engineering_database/database-schema-designer/SKILL.md
            status: CANDIDATE
            anchors: [database, schema, designer, when, database-schema-designer]
      engineering:
        path: skills/engineering_database/engineering/
        skill_count: 1
        skills:
          - skill: engineering_database.engineering
            path: skills/engineering_database/engineering/SKILL.md
            status: CANDIDATE
            anchors: [engineering, advanced, agent, skills, plugins]
      frontend-excellence:
        path: skills/engineering_database/frontend-excellence/
        skill_count: 1
        skills:
          - skill: engineering_database.frontend_excellence
            path: skills/engineering_database/frontend-excellence/SKILL.md
            status: CANDIDATE
            anchors: [frontend, excellence, modern, patterns, react]
      postgres-optimization:
        path: skills/engineering_database/postgres-optimization/
        skill_count: 1
        skills:
          - skill: engineering_database.postgres_optimization
            path: skills/engineering_database/postgres-optimization/SKILL.md
            status: CANDIDATE
            anchors: [postgres, optimization, postgresql, including, indexes]
      pydantic-models-py:
        path: skills/engineering_database/pydantic-models-py/
        skill_count: 1
        skills:
          - skill: engineering_database.pydantic_models_py
            path: skills/engineering_database/pydantic-models-py/SKILL.md
            status: CANDIDATE
            anchors: [pydantic, models, create, following, multi]
      redis-patterns:
        path: skills/engineering_database/redis-patterns/
        skill_count: 1
        skills:
          - skill: engineering_database.redis_patterns
            path: skills/engineering_database/redis-patterns/SKILL.md
            status: CANDIDATE
            anchors: [redis, patterns, including, caching, strategies]
      saas-scaffolder:
        path: skills/engineering_database/saas-scaffolder/
        skill_count: 1
        skills:
          - skill: engineering_database.saas_scaffolder
            path: skills/engineering_database/saas-scaffolder/SKILL.md
            status: CANDIDATE
            anchors: [saas, scaffolder, generates, complete, production]
      senior-architect:
        path: skills/engineering_database/senior-architect/
        skill_count: 1
        skills:
          - skill: engineering_database.senior_architect
            path: skills/engineering_database/senior-architect/SKILL.md
            status: CANDIDATE
            anchors: [senior, architect, this, skill, should]
      sql-database-assistant:
        path: skills/engineering_database/sql-database-assistant/
        skill_count: 1
        skills:
          - skill: engineering_database.sql_database_assistant
            path: skills/engineering_database/sql-database-assistant/SKILL.md
            status: CANDIDATE
            anchors: [database, assistant, when, write, sql-database-assistant]

  ENGINEERING_DEVOPS:
    path: skills/engineering_devops/
    display_name: "Engineering — DevOps"
    skill_count: 29
    anchors: [skill, for, when, pipeline, senior, and, data, engineering, agent, pipelines, patterns, docker, including, development, engineer]
    sub_domains:
      a11y-audit:
        path: skills/engineering_devops/a11y-audit/
        skill_count: 1
        skills:
          - skill: engineering_devops.a11y_audit
            path: skills/engineering_devops/a11y-audit/SKILL.md
            status: CANDIDATE
            anchors: [a11y, audit, accessibility, skill, scanning]
      business-growth:
        path: skills/engineering_devops/business-growth/
        skill_count: 1
        skills:
          - skill: engineering_devops.business_growth
            path: skills/engineering_devops/business-growth/SKILL.md
            status: CANDIDATE
            anchors: [business, growth, agent, skills, plugins]
      ci-cd-pipeline-builder:
        path: skills/engineering_devops/ci-cd-pipeline-builder/
        skill_count: 1
        skills:
          - skill: engineering_devops.ci_cd_pipeline_builder
            path: skills/engineering_devops/ci-cd-pipeline-builder/SKILL.md
            status: CANDIDATE
            anchors: [pipeline, builder, ci-cd-pipeline-builder, detection, overview]
      ci-cd-pipelines:
        path: skills/engineering_devops/ci-cd-pipelines/
        skill_count: 1
        skills:
          - skill: engineering_devops.ci_cd_pipelines
            path: skills/engineering_devops/ci-cd-pipelines/SKILL.md
            status: CANDIDATE
            anchors: [pipelines, pipeline, patterns, github, actions]
      composio-skills:
        path: skills/engineering_devops/composio-skills/
        skill_count: 1
        skills:
          - skill: engineering_devops.composio_skills
            path: skills/engineering_devops/composio-skills/SKILL.md
            status: CANDIDATE
            anchors: [composio, skills, automate, apollo, lead]
      content-production:
        path: skills/engineering_devops/content-production/
        skill_count: 1
        skills:
          - skill: engineering_devops.content_production
            path: skills/engineering_devops/content-production/SKILL.md
            status: CANDIDATE
            anchors: [content, production, full, pipeline, takes]
      data-engineering:
        path: skills/engineering_devops/data-engineering/
        skill_count: 1
        skills:
          - skill: engineering_devops.data_engineering
            path: skills/engineering_devops/data-engineering/SKILL.md
            status: CANDIDATE
            anchors: [data, engineering, patterns, pipelines, warehousing]
      devops-automation:
        path: skills/engineering_devops/devops-automation/
        skill_count: 1
        skills:
          - skill: engineering_devops.devops_automation
            path: skills/engineering_devops/devops-automation/SKILL.md
            status: CANDIDATE
            anchors: [devops, automation, pipeline, design, github]
      docker-best-practices:
        path: skills/engineering_devops/docker-best-practices/
        skill_count: 1
        skills:
          - skill: engineering_devops.docker_best_practices
            path: skills/engineering_devops/docker-best-practices/SKILL.md
            status: CANDIDATE
            anchors: [docker, best, practices, including, multi]
      docker-development:
        path: skills/engineering_devops/docker-development/
        skill_count: 1
        skills:
          - skill: engineering_devops.docker_development
            path: skills/engineering_devops/docker-development/SKILL.md
            status: CANDIDATE
            anchors: [docker, development, container, agent, skill]
      env-secrets-manager:
        path: skills/engineering_devops/env-secrets-manager/
        skill_count: 1
        skills:
          - skill: engineering_devops.env_secrets_manager
            path: skills/engineering_devops/env-secrets-manager/SKILL.md
            status: CANDIDATE
            anchors: [secrets, manager, env-secrets-manager, env, secret]
      helm-chart-builder:
        path: skills/engineering_devops/helm-chart-builder/
        skill_count: 1
        skills:
          - skill: engineering_devops.helm_chart_builder
            path: skills/engineering_devops/helm-chart-builder/SKILL.md
            status: CANDIDATE
            anchors: [helm, chart, builder, development, agent]
      interview-system-designer:
        path: skills/engineering_devops/interview-system-designer/
        skill_count: 1
        skills:
          - skill: engineering_devops.interview_system_designer
            path: skills/engineering_devops/interview-system-designer/SKILL.md
            status: CANDIDATE
            anchors: [interview, system, designer, this, skill]
      kubernetes-operations:
        path: skills/engineering_devops/kubernetes-operations/
        skill_count: 1
        skills:
          - skill: engineering_devops.kubernetes_operations
            path: skills/engineering_devops/kubernetes-operations/SKILL.md
            status: CANDIDATE
            anchors: [kubernetes, operations, including, manifests, helm]
      llm-cost-optimizer:
        path: skills/engineering_devops/llm-cost-optimizer/
        skill_count: 1
        skills:
          - skill: engineering_devops.llm_cost_optimizer
            path: skills/engineering_devops/llm-cost-optimizer/SKILL.md
            status: CANDIDATE
            anchors: [cost, optimizer, when, need, reduce]
      llm-integration:
        path: skills/engineering_devops/llm-integration/
        skill_count: 1
        skills:
          - skill: engineering_devops.llm_integration
            path: skills/engineering_devops/llm-integration/SKILL.md
            status: CANDIDATE
            anchors: [integration, patterns, including, usage, streaming]
      marketing-demand-acquisition:
        path: skills/engineering_devops/marketing-demand-acquisition/
        skill_count: 1
        skills:
          - skill: engineering_devops.marketing_demand_acquisition
            path: skills/engineering_devops/marketing-demand-acquisition/SKILL.md
            status: CANDIDATE
            anchors: [marketing, demand, acquisition, creates, generation]
      prompt-governance:
        path: skills/engineering_devops/prompt-governance/
        skill_count: 1
        skills:
          - skill: engineering_devops.prompt_governance
            path: skills/engineering_devops/prompt-governance/SKILL.md
            status: CANDIDATE
            anchors: [prompt, governance, when, managing, prompts]
      rag-architect:
        path: skills/engineering_devops/rag-architect/
        skill_count: 1
        skills:
          - skill: engineering_devops.rag_architect
            path: skills/engineering_devops/rag-architect/SKILL.md
            status: CANDIDATE
            anchors: [architect, when, design, pipelines, rag-architect]
      release-manager:
        path: skills/engineering_devops/release-manager/
        skill_count: 1
        skills:
          - skill: engineering_devops.release_manager
            path: skills/engineering_devops/release-manager/SKILL.md
            status: CANDIDATE
            anchors: [release, manager, when, plan, release-manager]
      revenue-operations:
        path: skills/engineering_devops/revenue-operations/
        skill_count: 1
        skills:
          - skill: engineering_devops.revenue_operations
            path: skills/engineering_devops/revenue-operations/SKILL.md
            status: CANDIDATE
            anchors: [revenue, operations, analyzes, sales, pipeline]
      runbook-generator:
        path: skills/engineering_devops/runbook-generator/
        skill_count: 1
        skills:
          - skill: engineering_devops.runbook_generator
            path: skills/engineering_devops/runbook-generator/SKILL.md
            status: CANDIDATE
            anchors: [runbook, generator, runbook-generator, overview, core]
      senior-computer-vision:
        path: skills/engineering_devops/senior-computer-vision/
        skill_count: 1
        skills:
          - skill: engineering_devops.senior_computer_vision
            path: skills/engineering_devops/senior-computer-vision/SKILL.md
            status: CANDIDATE
            anchors: [senior, computer, vision, engineering, skill]
      senior-data-engineer:
        path: skills/engineering_devops/senior-data-engineer/
        skill_count: 1
        skills:
          - skill: engineering_devops.senior_data_engineer
            path: skills/engineering_devops/senior-data-engineer/SKILL.md
            status: CANDIDATE
            anchors: [senior, data, engineer, engineering, skill]
      senior-data-scientist:
        path: skills/engineering_devops/senior-data-scientist/
        skill_count: 1
        skills:
          - skill: engineering_devops.senior_data_scientist
            path: skills/engineering_devops/senior-data-scientist/SKILL.md
            status: CANDIDATE
            anchors: [senior, data, scientist, world, class]
      senior-ml-engineer:
        path: skills/engineering_devops/senior-ml-engineer/
        skill_count: 1
        skills:
          - skill: engineering_devops.senior_ml_engineer
            path: skills/engineering_devops/senior-ml-engineer/SKILL.md
            status: CANDIDATE
            anchors: [senior, engineer, engineering, skill, productionizing]
      senior-secops:
        path: skills/engineering_devops/senior-secops/
        skill_count: 1
        skills:
          - skill: engineering_devops.senior_secops
            path: skills/engineering_devops/senior-secops/SKILL.md
            status: CANDIDATE
            anchors: [senior, secops, engineer, skill, application]
      snowflake-development:
        path: skills/engineering_devops/snowflake-development/
        skill_count: 1
        skills:
          - skill: engineering_devops.snowflake_development
            path: skills/engineering_devops/snowflake-development/SKILL.md
            status: CANDIDATE
            anchors: [snowflake, development, when, writing, building]
      video-content-strategist:
        path: skills/engineering_devops/video-content-strategist/
        skill_count: 1
        skills:
          - skill: engineering_devops.video_content_strategist
            path: skills/engineering_devops/video-content-strategist/SKILL.md
            status: CANDIDATE
            anchors: [video, content, strategist, when, planning]

  ENGINEERING_FRONTEND:
    path: skills/engineering_frontend/
    display_name: "Engineering — Frontend"
    skill_count: 15
    anchors: [react, for, frontend, patterns, and, including, page, design, skill, mode, generates, development, create, components, typescript]
    sub_domains:
      accessibility-wcag:
        path: skills/engineering_frontend/accessibility-wcag/
        skill_count: 1
        skills:
          - skill: engineering_frontend.accessibility_wcag
            path: skills/engineering_frontend/accessibility-wcag/SKILL.md
            status: CANDIDATE
            anchors: [accessibility, wcag, patterns, compliance, including]
      artifacts-builder:
        path: skills/engineering_frontend/artifacts-builder/
        skill_count: 1
        skills:
          - skill: engineering_frontend.artifacts_builder
            path: skills/engineering_frontend/artifacts-builder/SKILL.md
            status: CANDIDATE
            anchors: [artifacts, builder, suite, tools, creating]
      code-to-prd:
        path: skills/engineering_frontend/code-to-prd/
        skill_count: 1
        skills:
          - skill: engineering_frontend.code_to_prd
            path: skills/engineering_frontend/code-to-prd/SKILL.md
            status: CANDIDATE
            anchors: [code, code-to-prd, api, page, prd]
      epic-design:
        path: skills/engineering_frontend/epic-design/
        skill_count: 1
        skills:
          - skill: engineering_frontend.epic_design
            path: skills/engineering_frontend/epic-design/SKILL.md
            status: CANDIDATE
            anchors: [epic, design, epic-design, step, skill]
      frontend-design-review:
        path: skills/engineering_frontend/frontend-design-review/
        skill_count: 1
        skills:
          - skill: engineering_frontend.frontend_design_review
            path: skills/engineering_frontend/frontend-design-review/SKILL.md
            status: CANDIDATE
            anchors: [frontend, design, review, frontend-design-review, mode]
      frontend-ui-dark-ts:
        path: skills/engineering_frontend/frontend-ui-dark-ts/
        skill_count: 1
        skills:
          - skill: engineering_frontend.frontend_ui_dark_ts
            path: skills/engineering_frontend/frontend-ui-dark-ts/SKILL.md
            status: CANDIDATE
            anchors: [frontend, dark, build, themed, react]
      landing-page-generator:
        path: skills/engineering_frontend/landing-page-generator/
        skill_count: 1
        skills:
          - skill: engineering_frontend.landing_page_generator
            path: skills/engineering_frontend/landing-page-generator/SKILL.md
            status: CANDIDATE
            anchors: [landing, page, generator, generates, high]
      mobile-development:
        path: skills/engineering_frontend/mobile-development/
        skill_count: 1
        skills:
          - skill: engineering_frontend.mobile_development
            path: skills/engineering_frontend/mobile-development/SKILL.md
            status: CANDIDATE
            anchors: [mobile, development, patterns, react, native]
      react-flow-node-ts:
        path: skills/engineering_frontend/react-flow-node-ts/
        skill_count: 1
        skills:
          - skill: engineering_frontend.react_flow_node_ts
            path: skills/engineering_frontend/react-flow-node-ts/SKILL.md
            status: CANDIDATE
            anchors: [react, flow, node, create, components]
      react-patterns:
        path: skills/engineering_frontend/react-patterns/
        skill_count: 1
        skills:
          - skill: engineering_frontend.react_patterns
            path: skills/engineering_frontend/react-patterns/SKILL.md
            status: CANDIDATE
            anchors: [react, patterns, including, server, components]
      senior-frontend:
        path: skills/engineering_frontend/senior-frontend/
        skill_count: 1
        skills:
          - skill: engineering_frontend.senior_frontend
            path: skills/engineering_frontend/senior-frontend/SKILL.md
            status: CANDIDATE
            anchors: [senior, frontend, development, skill, react]
      senior-qa:
        path: skills/engineering_frontend/senior-qa/
        skill_count: 1
        skills:
          - skill: engineering_frontend.senior_qa
            path: skills/engineering_frontend/senior-qa/SKILL.md
            status: CANDIDATE
            anchors: [senior, generates, unit, tests, integration]
      vercel-react-best-practices:
        path: skills/engineering_frontend/vercel-react-best-practices/
        skill_count: 1
        skills:
          - skill: engineering_frontend.vercel_react_best_practices
            path: skills/engineering_frontend/vercel-react-best-practices/SKILL.md
            status: CANDIDATE
            anchors: [vercel, react, best, practices, next]
      webapp-testing:
        path: skills/engineering_frontend/webapp-testing/
        skill_count: 1
        skills:
          - skill: engineering_frontend.webapp_testing
            path: skills/engineering_frontend/webapp-testing/SKILL.md
            status: CANDIDATE
            anchors: [webapp, testing, toolkit, interacting, local]
      zustand-store-ts:
        path: skills/engineering_frontend/zustand-store-ts/
        skill_count: 1
        skills:
          - skill: engineering_frontend.zustand_store_ts
            path: skills/engineering_frontend/zustand-store-ts/SKILL.md
            status: CANDIDATE
            anchors: [zustand, store, create, stores, typescript]

  ENGINEERING_GIT:
    path: skills/engineering_git/
    display_name: "Engineering — Git"
    skill_count: 6
    anchors: [manager, git, worktree, git-worktree-manager, checklist, creation, overview, core, github, issue, creator, convert, notes, error, github-issue-creator]
    sub_domains:
      git-worktree-manager:
        path: skills/engineering_git/git-worktree-manager/
        skill_count: 1
        skills:
          - skill: engineering_git.git_worktree_manager
            path: skills/engineering_git/git-worktree-manager/SKILL.md
            status: CANDIDATE
            anchors: [worktree, manager, git-worktree-manager, git, checklist]
      github-issue-creator:
        path: skills/engineering_git/github-issue-creator/
        skill_count: 1
        skills:
          - skill: engineering_git.github_issue_creator
            path: skills/engineering_git/github-issue-creator/SKILL.md
            status: CANDIDATE
            anchors: [github, issue, creator, convert, notes]
      run:
        path: skills/engineering_git/run/
        skill_count: 1
        skills:
          - skill: engineering_git.run
            path: skills/engineering_git/run/SKILL.md
            status: CANDIDATE
            anchors: [single, experiment, iteration, edit, target]
      senior-pm:
        path: skills/engineering_git/senior-pm/
        skill_count: 1
        skills:
          - skill: engineering_git.senior_pm
            path: skills/engineering_git/senior-pm/SKILL.md
            status: CANDIDATE
            anchors: [senior, project, manager, enterprise, software]
      team-communications:
        path: skills/engineering_git/team-communications/
        skill_count: 1
        skills:
          - skill: engineering_git.team_communications
            path: skills/engineering_git/team-communications/SKILL.md
            status: CANDIDATE
            anchors: [team, communications, write, internal, company]
      wiki-changelog:
        path: skills/engineering_git/wiki-changelog/
        skill_count: 1
        skills:
          - skill: engineering_git.wiki_changelog
            path: skills/engineering_git/wiki-changelog/SKILL.md
            status: CANDIDATE
            anchors: [wiki, changelog, analyzes, commit, history]

  ENGINEERING_MOBILE:
    path: skills/engineering_mobile/
    display_name: "Engineering — Mobile"
    skill_count: 3
    anchors: [store, optimization, toolkit, researching, keywords, analyzing, app-store-optimization, app, code, reviewer, review, automation, typescript, javascript, code-reviewer]
    sub_domains:
      app-store-optimization:
        path: skills/engineering_mobile/app-store-optimization/
        skill_count: 1
        skills:
          - skill: engineering_mobile.app_store_optimization
            path: skills/engineering_mobile/app-store-optimization/SKILL.md
            status: CANDIDATE
            anchors: [store, optimization, toolkit, researching, keywords]
      code-reviewer:
        path: skills/engineering_mobile/code-reviewer/
        skill_count: 1
        skills:
          - skill: engineering_mobile.code_reviewer
            path: skills/engineering_mobile/code-reviewer/SKILL.md
            status: CANDIDATE
            anchors: [code, reviewer, review, automation, typescript]
      mcp-development:
        path: skills/engineering_mobile/mcp-development/
        skill_count: 1
        skills:
          - skill: engineering_mobile.mcp_development
            path: skills/engineering_mobile/mcp-development/SKILL.md
            status: CANDIDATE
            anchors: [development, server, including, tool, design]

  ENGINEERING_SECURITY:
    path: skills/engineering_security/
    display_name: "Engineering — Security"
    skill_count: 29
    anchors: [security, when, skill, the, for, code, review, patterns, including, and, automate, analyze, auditor, agent, incident]
    sub_domains:
      adversarial-reviewer:
        path: skills/engineering_security/adversarial-reviewer/
        skill_count: 1
        skills:
          - skill: engineering_security.adversarial_reviewer
            path: skills/engineering_security/adversarial-reviewer/SKILL.md
            status: CANDIDATE
            anchors: [adversarial, reviewer, code, review, that]
      ai-security:
        path: skills/engineering_security/ai-security/
        skill_count: 1
        skills:
          - skill: engineering_security.ai_security
            path: skills/engineering_security/ai-security/SKILL.md
            status: CANDIDATE
            anchors: [security, when, assessing, systems, prompt]
      authentication-patterns:
        path: skills/engineering_security/authentication-patterns/
        skill_count: 1
        skills:
          - skill: engineering_security.authentication_patterns
            path: skills/engineering_security/authentication-patterns/SKILL.md
            status: CANDIDATE
            anchors: [authentication, patterns, authorization, including, oauth2]
      behuman:
        path: skills/engineering_security/behuman/
        skill_count: 1
        skills:
          - skill: engineering_security.behuman
            path: skills/engineering_security/behuman/SKILL.md
            status: CANDIDATE
            anchors: [behuman, when, more, human, the]
      ciso-advisor:
        path: skills/engineering_security/ciso-advisor/
        skill_count: 1
        skills:
          - skill: engineering_security.ciso_advisor
            path: skills/engineering_security/ciso-advisor/SKILL.md
            status: CANDIDATE
            anchors: [ciso, advisor, security, leadership, growth]
      composio-skills:
        path: skills/engineering_security/composio-skills/
        skill_count: 1
        skills:
          - skill: engineering_security.composio_skills
            path: skills/engineering_security/composio-skills/SKILL.md
            status: CANDIDATE
            anchors: [composio, skills, automate, research, ahrefs]
      content-humanizer:
        path: skills/engineering_security/content-humanizer/
        skill_count: 1
        skills:
          - skill: engineering_security.content_humanizer
            path: skills/engineering_security/content-humanizer/SKILL.md
            status: CANDIDATE
            anchors: [content, humanizer, makes, generated, sound]
      content-strategy:
        path: skills/engineering_security/content-strategy/
        skill_count: 1
        skills:
          - skill: engineering_security.content_strategy
            path: skills/engineering_security/content-strategy/SKILL.md
            status: CANDIDATE
      dependency-auditor:
        path: skills/engineering_security/dependency-auditor/
        skill_count: 1
        skills:
          - skill: engineering_security.dependency_auditor
            path: skills/engineering_security/dependency-auditor/SKILL.md
            status: CANDIDATE
            anchors: [dependency, auditor, dependency-auditor, security, metrics]
      entra-agent-id:
        path: skills/engineering_security/entra-agent-id/
        skill_count: 1
        skills:
          - skill: engineering_security.entra_agent_id
            path: skills/engineering_security/entra-agent-id/SKILL.md
            status: CANDIDATE
            anchors: [entra, agent, entra-agent-id, identity, step]
      fda-consultant-specialist:
        path: skills/engineering_security/fda-consultant-specialist/
        skill_count: 1
        skills:
          - skill: engineering_security.fda_consultant_specialist
            path: skills/engineering_security/fda-consultant-specialist/SKILL.md
            status: CANDIDATE
            anchors: [consultant, specialist, regulatory, medical, device]
      git-advanced:
        path: skills/engineering_security/git-advanced/
        skill_count: 1
        skills:
          - skill: engineering_security.git_advanced
            path: skills/engineering_security/git-advanced/SKILL.md
            status: CANDIDATE
            anchors: [advanced, workflows, including, worktrees, bisect]
      google-workspace-cli:
        path: skills/engineering_security/google-workspace-cli/
        skill_count: 1
        skills:
          - skill: engineering_security.google_workspace_cli
            path: skills/engineering_security/google-workspace-cli/SKILL.md
            status: CANDIDATE
            anchors: [google, workspace, administration, install, authenticate]
      incident-commander:
        path: skills/engineering_security/incident-commander/
        skill_count: 1
        skills:
          - skill: engineering_security.incident_commander
            path: skills/engineering_security/incident-commander/SKILL.md
            status: CANDIDATE
            anchors: [incident, commander, skill, incident-commander, response]
      incident-response:
        path: skills/engineering_security/incident-response/
        skill_count: 1
        skills:
          - skill: engineering_security.incident_response
            path: skills/engineering_security/incident-response/SKILL.md
            status: CANDIDATE
            anchors: [incident, response, when, security, been]
      information-security-manager-iso27001:
        path: skills/engineering_security/information-security-manager-iso27001/
        skill_count: 1
        skills:
          - skill: engineering_security.information_security_manager_iso27001
            path: skills/engineering_security/information-security-manager-iso27001/SKILL.md
            status: CANDIDATE
            anchors: [information, security, manager, iso27001, isms]
      isms-audit-expert:
        path: skills/engineering_security/isms-audit-expert/
        skill_count: 1
        skills:
          - skill: engineering_security.isms_audit_expert
            path: skills/engineering_security/isms-audit-expert/SKILL.md
            status: CANDIDATE
            anchors: [isms, audit, expert, information, security]
      issue-reporter:
        path: skills/engineering_security/issue-reporter/
        skill_count: 1
        skills:
          - skill: engineering_security.issue_reporter
            path: skills/engineering_security/issue-reporter/SKILL.md
            status: CANDIDATE
            anchors: [issue, reporter, report, feature, request]
      pr-review-expert:
        path: skills/engineering_security/pr-review-expert/
        skill_count: 1
        skills:
          - skill: engineering_security.pr_review_expert
            path: skills/engineering_security/pr-review-expert/SKILL.md
            status: CANDIDATE
            anchors: [review, expert, when, pull, pr-review-expert]
      red-team:
        path: skills/engineering_security/red-team/
        skill_count: 1
        skills:
          - skill: engineering_security.red_team
            path: skills/engineering_security/red-team/SKILL.md
            status: CANDIDATE
            anchors: [team, when, planning, executing, authorized]
      sample-skill:
        path: skills/engineering_security/sample-skill/
        skill_count: 1
        skills:
          - skill: engineering_security.sample_skill
            path: skills/engineering_security/sample-skill/SKILL.md
            status: CANDIDATE
            anchors: [sample, skill, sample-skill, text, example]
      security-hardening:
        path: skills/engineering_security/security-hardening/
        skill_count: 1
        skills:
          - skill: engineering_security.security_hardening
            path: skills/engineering_security/security-hardening/SKILL.md
            status: CANDIDATE
            anchors: [security, hardening, application, covering, input]
      security-pen-testing:
        path: skills/engineering_security/security-pen-testing/
        skill_count: 1
        skills:
          - skill: engineering_security.security_pen_testing
            path: skills/engineering_security/security-pen-testing/SKILL.md
            status: CANDIDATE
            anchors: [security, testing, when, perform, security-pen-testing]
      senior-fullstack:
        path: skills/engineering_security/senior-fullstack/
        skill_count: 1
        skills:
          - skill: engineering_security.senior_fullstack
            path: skills/engineering_security/senior-fullstack/SKILL.md
            status: CANDIDATE
            anchors: [senior, fullstack, development, toolkit, project]
      senior-security:
        path: skills/engineering_security/senior-security/
        skill_count: 1
        skills:
          - skill: engineering_security.senior_security
            path: skills/engineering_security/senior-security/SKILL.md
            status: CANDIDATE
            anchors: [senior, security, engineering, toolkit, threat]
      skill-security-auditor:
        path: skills/engineering_security/skill-security-auditor/
        skill_count: 1
        skills:
          - skill: engineering_security.skill_security_auditor
            path: skills/engineering_security/skill-security-auditor/SKILL.md
            status: CANDIDATE
            anchors: [skill, security, auditor, skill-security-auditor, audit]
      skill-tester:
        path: skills/engineering_security/skill-tester/
        skill_count: 1
        skills:
          - skill: engineering_security.skill_tester
            path: skills/engineering_security/skill-tester/SKILL.md
            status: CANDIDATE
            anchors: [skill, tester, skill-tester, quality, testing]
      tech-stack-evaluator:
        path: skills/engineering_security/tech-stack-evaluator/
        skill_count: 1
        skills:
          - skill: engineering_security.tech_stack_evaluator
            path: skills/engineering_security/tech-stack-evaluator/SKILL.md
            status: CANDIDATE
            anchors: [tech, stack, evaluator, technology, evaluation]
      terraform-patterns:
        path: skills/engineering_security/terraform-patterns/
        skill_count: 1
        skills:
          - skill: engineering_security.terraform_patterns
            path: skills/engineering_security/terraform-patterns/SKILL.md
            status: CANDIDATE
            anchors: [terraform, patterns, infrastructure, code, agent]

  ENGINEERING_TESTING:
    path: skills/engineering_testing/
    display_name: "Engineering — Testing"
    skill_count: 19
    anchors: [test, when, the, for, testing, toolkit, design, generate, playwright, assumptions, and, driven, development, test-driven, setup]
    sub_domains:
      ab-test-setup:
        path: skills/engineering_testing/ab-test-setup/
        skill_count: 1
        skills:
          - skill: engineering_testing.ab_test_setup
            path: skills/engineering_testing/ab-test-setup/SKILL.md
            status: CANDIDATE
            anchors: [test, setup, when, plan, ab-test-setup]
      ad-creative:
        path: skills/engineering_testing/ad-creative/
        skill_count: 1
        skills:
          - skill: engineering_testing.ad_creative
            path: skills/engineering_testing/ad-creative/SKILL.md
            status: CANDIDATE
            anchors: [creative, when, generate, iterate, ad-creative]
      browser-automation:
        path: skills/engineering_testing/browser-automation/
        skill_count: 1
        skills:
          - skill: engineering_testing.browser_automation
            path: skills/engineering_testing/browser-automation/SKILL.md
            status: CANDIDATE
            anchors: [browser, automation, when, automate, browser-automation]
      browserstack:
        path: skills/engineering_testing/browserstack/
        skill_count: 1
        skills:
          - skill: engineering_testing.browserstack
            path: skills/engineering_testing/browserstack/SKILL.md
            status: CANDIDATE
            anchors: [browserstack, integration, prerequisites, capabilities, configure]
      cherry-pr-test:
        path: skills/engineering_testing/cherry-pr-test/
        skill_count: 1
        skills:
          - skill: engineering_testing.cherry_pr_test
            path: skills/engineering_testing/cherry-pr-test/SKILL.md
            status: CANDIDATE
            anchors: [cherry, test, studio, checking, branch]
      gh-create-pr:
        path: skills/engineering_testing/gh-create-pr/
        skill_count: 1
        skills:
          - skill: engineering_testing.gh_create_pr
            path: skills/engineering_testing/gh-create-pr/SKILL.md
            status: CANDIDATE
            anchors: [create, update, github, pull, requests]
      golang-idioms:
        path: skills/engineering_testing/golang-idioms/
        skill_count: 1
        skills:
          - skill: engineering_testing.golang_idioms
            path: skills/engineering_testing/golang-idioms/SKILL.md
            status: CANDIDATE
            anchors: [golang, idioms, idiomatic, patterns, error]
      init:
        path: skills/engineering_testing/init/
        skill_count: 1
        skills:
          - skill: engineering_testing.init
            path: skills/engineering_testing/init/SKILL.md
            status: CANDIDATE
            anchors: [init, playwright, generate, project, initialize]
      playwright-pro:
        path: skills/engineering_testing/playwright-pro/
        skill_count: 1
        skills:
          - skill: engineering_testing.playwright_pro
            path: skills/engineering_testing/playwright-pro/SKILL.md
            status: CANDIDATE
            anchors: [playwright, production, grade, testing, toolkit]
      product-discovery:
        path: skills/engineering_testing/product-discovery/
        skill_count: 1
        skills:
          - skill: engineering_testing.product_discovery
            path: skills/engineering_testing/product-discovery/SKILL.md
            status: CANDIDATE
            anchors: [product, discovery, when, validating, opportunities]
      prompt-engineer-toolkit:
        path: skills/engineering_testing/prompt-engineer-toolkit/
        skill_count: 1
        skills:
          - skill: engineering_testing.prompt_engineer_toolkit
            path: skills/engineering_testing/prompt-engineer-toolkit/SKILL.md
            status: CANDIDATE
            anchors: [prompt, engineer, toolkit, analyzes, rewrites]
      python-best-practices:
        path: skills/engineering_testing/python-best-practices/
        skill_count: 1
        skills:
          - skill: engineering_testing.python_best_practices
            path: skills/engineering_testing/python-best-practices/SKILL.md
            status: CANDIDATE
            anchors: [python, best, practices, pythonic, code]
      scenario-war-room:
        path: skills/engineering_testing/scenario-war-room/
        skill_count: 1
        skills:
          - skill: engineering_testing.scenario_war_room
            path: skills/engineering_testing/scenario-war-room/SKILL.md
            status: CANDIDATE
            anchors: [scenario, room, cross, functional, what]
      stress-test:
        path: skills/engineering_testing/stress-test/
        skill_count: 1
        skills:
          - skill: engineering_testing.stress_test
            path: skills/engineering_testing/stress-test/SKILL.md
            status: CANDIDATE
            anchors: [stress, test, business, assumption, testing]
      tdd-guide:
        path: skills/engineering_testing/tdd-guide/
        skill_count: 1
        skills:
          - skill: engineering_testing.tdd_guide
            path: skills/engineering_testing/tdd-guide/SKILL.md
            status: CANDIDATE
            anchors: [guide, test, driven, development, skill]
      tdd-mastery:
        path: skills/engineering_testing/tdd-mastery/
        skill_count: 1
        skills:
          - skill: engineering_testing.tdd_mastery
            path: skills/engineering_testing/tdd-mastery/SKILL.md
            status: CANDIDATE
            anchors: [mastery, test, driven, development, workflow]
      testing-strategies:
        path: skills/engineering_testing/testing-strategies/
        skill_count: 1
        skills:
          - skill: engineering_testing.testing_strategies
            path: skills/engineering_testing/testing-strategies/SKILL.md
            status: CANDIDATE
            anchors: [testing, strategies, including, contract, snapshot]
      ux-researcher-designer:
        path: skills/engineering_testing/ux-researcher-designer/
        skill_count: 1
        skills:
          - skill: engineering_testing.ux_researcher_designer
            path: skills/engineering_testing/ux-researcher-designer/SKILL.md
            status: CANDIDATE
            anchors: [researcher, designer, research, design, toolkit]
      wiki-agents-md:
        path: skills/engineering_testing/wiki-agents-md/
        skill_count: 1
        skills:
          - skill: engineering_testing.wiki_agents_md
            path: skills/engineering_testing/wiki-agents-md/SKILL.md
            status: CANDIDATE
            anchors: [wiki, agents, generates, files, repository]

  FINANCE:
    path: skills/finance/
    display_name: "Finance"
    skill_count: 191
    anchors: [description, data, generate, combining, professional, build, pricing, equity, investment, analyze, analysis, research, financial, company, skills]
    sub_domains:
      _source:
        path: skills/finance/_source/
        skill_count: 56
        skills:
          - skill: catalyst-calendar
            path: skills/finance/_source/equity-research/skills/catalyst-calendar/SKILL.md
            status: UNKNOWN
          - skill: earnings-analysis
            path: skills/finance/_source/equity-research/skills/earnings-analysis/SKILL.md
            status: UNKNOWN
            anchors: [earnings-analysis, create, professional, equity, research]
          - skill: earnings-preview
            path: skills/finance/_source/equity-research/skills/earnings-preview/SKILL.md
            status: UNKNOWN
          - skill: idea-generation
            path: skills/finance/_source/equity-research/skills/idea-generation/SKILL.md
            status: UNKNOWN
          - skill: initiating-coverage
            path: skills/finance/_source/equity-research/skills/initiating-coverage/SKILL.md
            status: UNKNOWN
            anchors: [initiating-coverage, create, institutional-quality, equity, research]
          # ... +51 skills adicionais
      _source_v2:
        path: skills/finance/_source_v2/
        skill_count: 56
        skills:
          - skill: catalyst-calendar
            path: skills/finance/_source_v2/equity-research/skills/catalyst-calendar/SKILL.md
            status: UNKNOWN
          - skill: earnings-analysis
            path: skills/finance/_source_v2/equity-research/skills/earnings-analysis/SKILL.md
            status: UNKNOWN
            anchors: [earnings-analysis, create, professional, equity, research]
          - skill: earnings-preview
            path: skills/finance/_source_v2/equity-research/skills/earnings-preview/SKILL.md
            status: UNKNOWN
          - skill: idea-generation
            path: skills/finance/_source_v2/equity-research/skills/idea-generation/SKILL.md
            status: UNKNOWN
          - skill: initiating-coverage
            path: skills/finance/_source_v2/equity-research/skills/initiating-coverage/SKILL.md
            status: UNKNOWN
            anchors: [initiating-coverage, create, institutional-quality, equity, research]
          # ... +51 skills adicionais
      accounting:
        path: skills/finance/accounting/
        skill_count: 9
        skills:
          - skill: finance.accounting.audit_support
            path: skills/finance/accounting/audit-support/SKILL.md
            status: ADOPTED
            anchors: [audit, support, compliance, control, testing]
          - skill: finance.accounting.close_management
            path: skills/finance/accounting/close-management/SKILL.md
            status: ADOPTED
            anchors: [close, management, manage, month, process]
          - skill: finance.accounting.financial_statements
            path: skills/finance/accounting/financial-statements/SKILL.md
            status: ADOPTED
            anchors: [financial, statements, generate, income, statement]
          - skill: finance.accounting.journal_entry
            path: skills/finance/accounting/journal-entry/SKILL.md
            status: ADOPTED
            anchors: [journal, entry, prepare, entries, proper]
          - skill: finance.accounting.journal_entry_prep
            path: skills/finance/accounting/journal-entry-prep/SKILL.md
            status: ADOPTED
            anchors: [journal, entry, prep, prepare, entries]
          # ... +4 skills adicionais
      composio-skills:
        path: skills/finance/composio-skills/
        skill_count: 1
        skills:
          - skill: finance.composio_skills
            path: skills/finance/composio-skills/SKILL.md
            status: CANDIDATE
            anchors: [composio, skills, freshbooks, automation, manage]
      equity-research:
        path: skills/finance/equity-research/
        skill_count: 10
        skills:
          - skill: finance.equity_research.catalyst_calendar
            path: skills/finance/equity-research/catalyst-calendar/SKILL.md
            status: ADOPTED
            anchors: [catalyst, calendar, description, build, maintain]
          - skill: finance.equity_research.earnings_analysis
            path: skills/finance/equity-research/earnings-analysis/SKILL.md
            status: ADOPTED
            anchors: [earnings, analysis, create, professional, equity]
          - skill: finance.equity_research.earnings_preview
            path: skills/finance/equity-research/earnings-preview/SKILL.md
            status: ADOPTED
            anchors: [earnings, preview, description, build, analysis]
          - skill: finance.equity_research.idea_generation
            path: skills/finance/equity-research/idea-generation/SKILL.md
            status: ADOPTED
            anchors: [idea, generation, description, systematic, stock]
          - skill: finance.equity_research.initiating_coverage
            path: skills/finance/equity-research/initiating-coverage/SKILL.md
            status: ADOPTED
            anchors: [initiating, coverage, create, institutional, quality]
          # ... +5 skills adicionais
      financial-analysis:
        path: skills/finance/financial-analysis/
        skill_count: 12
        skills:
          - skill: finance.financial_analysis.3_statement_model
            path: skills/finance/financial-analysis/3-statement-model/SKILL.md
            status: ADOPTED
            anchors: [statement, model, complete, populate, fill]
          - skill: finance.financial_analysis.audit_xls
            path: skills/finance/financial-analysis/audit-xls/SKILL.md
            status: ADOPTED
            anchors: [audit, spreadsheet, formula, accuracy, errors]
          - skill: finance.financial_analysis.clean_data_xls
            path: skills/finance/financial-analysis/clean-data-xls/SKILL.md
            status: ADOPTED
            anchors: [clean, data, messy, spreadsheet, trim]
          - skill: finance.financial_analysis.competitive_analysis
            path: skills/finance/financial-analysis/competitive-analysis/SKILL.md
            status: ADOPTED
            anchors: [competitive, analysis, framework, building, landscape]
          - skill: finance.financial_analysis.comps_analysis
            path: skills/finance/financial-analysis/comps-analysis/SKILL.md
            status: ADOPTED
            anchors: [comps, analysis, comparable, company, critical]
          # ... +7 skills adicionais
      fixed-income:
        path: skills/finance/fixed-income/
        skill_count: 9
        skills:
          - skill: finance.fixed_income.bond_futures_basis
            path: skills/finance/fixed-income/bond-futures-basis/SKILL.md
            status: ADOPTED
            anchors: [bond, futures, basis, analyze, pricing]
          - skill: finance.fixed_income.bond_relative_value
            path: skills/finance/fixed-income/bond-relative-value/SKILL.md
            status: ADOPTED
            anchors: [bond, relative, value, perform, analysis]
          - skill: finance.fixed_income.equity_research
            path: skills/finance/fixed-income/equity-research/SKILL.md
            status: ADOPTED
            anchors: [equity, research, generate, comprehensive, snapshots]
          - skill: finance.fixed_income.fixed_income_portfolio
            path: skills/finance/fixed-income/fixed-income-portfolio/SKILL.md
            status: ADOPTED
            anchors: [fixed, income, portfolio, review, portfolios]
          - skill: finance.fixed_income.fx_carry_trade
            path: skills/finance/fixed-income/fx-carry-trade/SKILL.md
            status: ADOPTED
            anchors: [carry, trade, evaluate, opportunities, combining]
          # ... +4 skills adicionais
      investment-banking:
        path: skills/finance/investment-banking/
        skill_count: 10
        skills:
          - skill: finance.investment_banking.buyer_list
            path: skills/finance/investment-banking/buyer-list/SKILL.md
            status: ADOPTED
            anchors: [buyer, list, description, build, organize]
          - skill: finance.investment_banking.cim_builder
            path: skills/finance/investment-banking/cim-builder/SKILL.md
            status: ADOPTED
            anchors: [builder, description, structure, draft, confidential]
          - skill: finance.investment_banking.datapack_builder
            path: skills/finance/investment-banking/datapack-builder/SKILL.md
            status: ADOPTED
            anchors: [datapack, builder, build, professional, financial]
          - skill: finance.investment_banking.deal_tracker
            path: skills/finance/investment-banking/deal-tracker/SKILL.md
            status: ADOPTED
            anchors: [deal, tracker, description, track, multiple]
          - skill: finance.investment_banking.merger_model
            path: skills/finance/investment-banking/merger-model/SKILL.md
            status: ADOPTED
            anchors: [merger, model, description, build, accretion]
          # ... +5 skills adicionais
      invoice-organizer:
        path: skills/finance/invoice-organizer/
        skill_count: 1
        skills:
          - skill: finance.invoice_organizer
            path: skills/finance/invoice-organizer/SKILL.md
            status: CANDIDATE
            anchors: [invoice, organizer, automatically, organizes, invoices]
      leiloeiro-risco:
        path: skills/finance/leiloeiro-risco/
        skill_count: 1
        skills:
          - skill: finance.leiloeiro_risco
            path: skills/finance/leiloeiro-risco/SKILL.md
            status: CANDIDATE
            anchors: [leiloeiro, risco, analise, leiloes, imoveis]
      market-data:
        path: skills/finance/market-data/
        skill_count: 4
        skills:
          - skill: finance.market_data.earnings_preview_beta
            path: skills/finance/market-data/earnings-preview-beta/SKILL.md
            status: ADOPTED
            anchors: [earnings, preview, single, generate, concise]
          - skill: finance.market_data.funding_digest
            path: skills/finance/market-data/funding-digest/SKILL.md
            status: ADOPTED
            anchors: [funding, digest, generate, polished, page]
          - skill: finance.market_data.skills
            path: skills/finance/market-data/skills/SKILL.md
            status: ADOPTED
            anchors: [tear, sheet, generate, professional, company]
          - skill: finance.market_data.tear_sheet
            path: skills/finance/market-data/tear-sheet/SKILL.md
            status: ADOPTED
            anchors: [tear, sheet, generate, professional, company]
      payments:
        path: skills/finance/payments/
        skill_count: 3
        skills:
          - skill: finance.payments.churn_prevention
            path: skills/finance/payments/churn-prevention/SKILL.md
            status: CANDIDATE
            anchors: [churn, prevention, reduce, voluntary, involuntary]
          - skill: finance.payments.pakistan_payments_stack
            path: skills/finance/payments/pakistan-payments-stack/SKILL.md
            status: CANDIDATE
            anchors: [pakistan, payments, stack, design, implement]
          - skill: finance.payments.stripe_integration
            path: skills/finance/payments/stripe-integration/SKILL.md
            status: CANDIDATE
            anchors: [stripe, integration, master, payment, processing]
      private-equity:
        path: skills/finance/private-equity/
        skill_count: 11
        skills:
          - skill: finance.private_equity.ai_readiness
            path: skills/finance/private-equity/ai-readiness/SKILL.md
            status: ADOPTED
            anchors: [readiness, portfolio, description, scan, highest]
          - skill: finance.private_equity.dd_checklist
            path: skills/finance/private-equity/dd-checklist/SKILL.md
            status: ADOPTED
            anchors: [checklist, diligence, description, generate, track]
          - skill: finance.private_equity.dd_meeting_prep
            path: skills/finance/private-equity/dd-meeting-prep/SKILL.md
            status: ADOPTED
            anchors: [meeting, prep, diligence, description, prepare]
          - skill: finance.private_equity.deal_screening
            path: skills/finance/private-equity/deal-screening/SKILL.md
            status: ADOPTED
            anchors: [deal, screening, description, quickly, screen]
          - skill: finance.private_equity.deal_sourcing
            path: skills/finance/private-equity/deal-sourcing/SKILL.md
            status: ADOPTED
            anchors: [deal, sourcing, description, workflow, discover]
          # ... +6 skills adicionais
      saas-metrics-coach:
        path: skills/finance/saas-metrics-coach/
        skill_count: 1
        skills:
          - skill: finance.saas_metrics_coach
            path: skills/finance/saas-metrics-coach/SKILL.md
            status: CANDIDATE
            anchors: [saas, metrics, coach, financial, health]
      wealth-management:
        path: skills/finance/wealth-management/
        skill_count: 7
        skills:
          - skill: finance.wealth_management.client_report
            path: skills/finance/wealth-management/client-report/SKILL.md
            status: ADOPTED
            anchors: [client, report, description, generate, professional]
          - skill: finance.wealth_management.client_review
            path: skills/finance/wealth-management/client-review/SKILL.md
            status: ADOPTED
            anchors: [client, review, prep, description, prepare]
          - skill: finance.wealth_management.financial_plan
            path: skills/finance/wealth-management/financial-plan/SKILL.md
            status: ADOPTED
            anchors: [financial, plan, description, build, update]
          - skill: finance.wealth_management.investment_proposal
            path: skills/finance/wealth-management/investment-proposal/SKILL.md
            status: ADOPTED
            anchors: [investment, proposal, description, create, professional]
          - skill: finance.wealth_management.portfolio_rebalance
            path: skills/finance/wealth-management/portfolio-rebalance/SKILL.md
            status: ADOPTED
            anchors: [portfolio, rebalance, description, analyze, allocation]
          # ... +2 skills adicionais

  HEALTHCARE:
    path: skills/healthcare/
    display_name: "Healthcare"
    skill_count: 23
    anchors: [analyzer, health, diff, history, for, medical, generate, clinical, trial, protocols, devices, fhir, automate, payer, review]
    sub_domains:
      _source:
        path: skills/healthcare/_source/
        skill_count: 3
        skills:
          - skill: clinical-trial-protocol-skill
            path: skills/healthcare/_source/clinical-trial-protocol-skill/SKILL.md
            status: UNKNOWN
            anchors: [clinical-trial-protocol-skill, generate, clinical, trial, protocols]
          - skill: fhir-developer-skill
            path: skills/healthcare/_source/fhir-developer-skill/SKILL.md
            status: UNKNOWN
            anchors: [fhir-developer-skill, fhir, api, development, guide]
          - skill: prior-auth-review-skill
            path: skills/healthcare/_source/prior-auth-review-skill/SKILL.md
            status: UNKNOWN
            anchors: [prior-auth-review-skill, automate, payer, review, prior]
      _source_v2:
        path: skills/healthcare/_source_v2/
        skill_count: 3
        skills:
          - skill: clinical-trial-protocol-skill
            path: skills/healthcare/_source_v2/clinical-trial-protocol-skill/SKILL.md
            status: UNKNOWN
            anchors: [clinical-trial-protocol-skill, generate, clinical, trial, protocols]
          - skill: fhir-developer-skill
            path: skills/healthcare/_source_v2/fhir-developer-skill/SKILL.md
            status: UNKNOWN
            anchors: [fhir-developer-skill, fhir, api, development, guide]
          - skill: prior-auth-review-skill
            path: skills/healthcare/_source_v2/prior-auth-review-skill/SKILL.md
            status: UNKNOWN
            anchors: [prior-auth-review-skill, automate, payer, review, prior]
      analyze-project:
        path: skills/healthcare/analyze-project/
        skill_count: 1
        skills:
          - skill: healthcare.analyze_project
            path: skills/healthcare/analyze-project/SKILL.md
            status: CANDIDATE
            anchors: [analyze, project, forensic, root, cause]
      clinical-trial-protocol-skill:
        path: skills/healthcare/clinical-trial-protocol-skill/
        skill_count: 1
        skills:
          - skill: healthcare.clinical_trial_protocol_skill
            path: skills/healthcare/clinical-trial-protocol-skill/SKILL.md
            status: ADOPTED
            anchors: [clinical, trial, protocol, skill, generate]
      family-health-analyzer:
        path: skills/healthcare/family-health-analyzer/
        skill_count: 1
        skills:
          - skill: healthcare.family_health_analyzer
            path: skills/healthcare/family-health-analyzer/SKILL.md
            status: CANDIDATE
            anchors: [family, health, analyzer, family-health-analyzer, diff]
      fda-medtech-compliance-auditor:
        path: skills/healthcare/fda-medtech-compliance-auditor/
        skill_count: 1
        skills:
          - skill: healthcare.fda_medtech_compliance_auditor
            path: skills/healthcare/fda-medtech-compliance-auditor/SKILL.md
            status: CANDIDATE
            anchors: [medtech, compliance, auditor, expert, medical]
      fhir-developer-skill:
        path: skills/healthcare/fhir-developer-skill/
        skill_count: 1
        skills:
          - skill: healthcare.fhir_developer_skill
            path: skills/healthcare/fhir-developer-skill/SKILL.md
            status: ADOPTED
            anchors: [fhir, developer, skill, quick, reference]
      health-trend-analyzer:
        path: skills/healthcare/health-trend-analyzer/
        skill_count: 1
        skills:
          - skill: healthcare.health_trend_analyzer
            path: skills/healthcare/health-trend-analyzer/SKILL.md
            status: CANDIDATE
            anchors: [health, trend, analyzer, html, echarts]
      mental-health-analyzer:
        path: skills/healthcare/mental-health-analyzer/
        skill_count: 1
        skills:
          - skill: healthcare.mental_health_analyzer
            path: skills/healthcare/mental-health-analyzer/SKILL.md
            status: CANDIDATE
            anchors: [mental, health, analyzer, mental-health-analyzer, top]
      occupational-health-analyzer:
        path: skills/healthcare/occupational-health-analyzer/
        skill_count: 1
        skills:
          - skill: healthcare.occupational_health_analyzer
            path: skills/healthcare/occupational-health-analyzer/SKILL.md
            status: CANDIDATE
            anchors: [occupational, health, analyzer, occupational-health-analyzer, diff]
      oral-health-analyzer:
        path: skills/healthcare/oral-health-analyzer/
        skill_count: 1
        skills:
          - skill: healthcare.oral_health_analyzer
            path: skills/healthcare/oral-health-analyzer/SKILL.md
            status: CANDIDATE
            anchors: [oral, health, analyzer, oral-health-analyzer, diff]
      prior-auth-review-skill:
        path: skills/healthcare/prior-auth-review-skill/
        skill_count: 1
        skills:
          - skill: healthcare.prior_auth_review_skill
            path: skills/healthcare/prior-auth-review-skill/SKILL.md
            status: ADOPTED
            anchors: [prior, auth, review, skill, automate]
      satori:
        path: skills/healthcare/satori/
        skill_count: 1
        skills:
          - skill: healthcare.satori
            path: skills/healthcare/satori/SKILL.md
            status: CANDIDATE
            anchors: [satori, clinically, informed, wisdom, companion]
      sexual-health-analyzer:
        path: skills/healthcare/sexual-health-analyzer/
        skill_count: 1
        skills:
          - skill: healthcare.sexual_health_analyzer
            path: skills/healthcare/sexual-health-analyzer/SKILL.md
            status: CANDIDATE
            anchors: [sexual, health, analyzer, sexual-health-analyzer, iief-]
      skin-health-analyzer:
        path: skills/healthcare/skin-health-analyzer/
        skill_count: 1
        skills:
          - skill: healthcare.skin_health_analyzer
            path: skills/healthcare/skin-health-analyzer/SKILL.md
            status: CANDIDATE
            anchors: [skin, health, analyzer, analyze, data]
      travel-health-analyzer:
        path: skills/healthcare/travel-health-analyzer/
        skill_count: 1
        skills:
          - skill: healthcare.travel_health_analyzer
            path: skills/healthcare/travel-health-analyzer/SKILL.md
            status: CANDIDATE
            anchors: [travel, health, analyzer, travel-health-analyzer, thailand]
      wellally-tech:
        path: skills/healthcare/wellally-tech/
        skill_count: 1
        skills:
          - skill: healthcare.wellally_tech
            path: skills/healthcare/wellally-tech/SKILL.md
            status: CANDIDATE
            anchors: [wellally, tech, integrate, multiple, digital]
      wellness:
        path: skills/healthcare/wellness/
        skill_count: 2
        skills:
          - skill: healthcare.wellness.sleep_analyzer
            path: skills/healthcare/wellness/sleep-analyzer/SKILL.md
            status: CANDIDATE
            anchors: [sleep, analyzer, sleep-analyzer, psqi, stop-bang]
          - skill: healthcare.wellness.weightloss_analyzer
            path: skills/healthcare/wellness/weightloss-analyzer/SKILL.md
            status: CANDIDATE
            anchors: [weightloss, analyzer, weightloss-analyzer, bmi, diff]

  HUMAN_RESOURCES:
    path: skills/human-resources/
    display_name: "Human Resources"
    skill_count: 10
    anchors: [candidate, trigger, comp, generate, plan, headcount, structure, recruiting, pipeline, track, manage, stages, update, analysis, analyze]
    sub_domains:
      comp-analysis:
        path: skills/human-resources/comp-analysis/
        skill_count: 1
        skills:
          - skill: human_resources.comp_analysis
            path: skills/human-resources/comp-analysis/SKILL.md
            status: ADOPTED
            anchors: [comp, analysis, analyze, compensation, benchmarking]
      draft-offer:
        path: skills/human-resources/draft-offer/
        skill_count: 1
        skills:
          - skill: human_resources.draft_offer
            path: skills/human-resources/draft-offer/SKILL.md
            status: ADOPTED
            anchors: [draft, offer, letter, comp, details]
      interview-prep:
        path: skills/human-resources/interview-prep/
        skill_count: 1
        skills:
          - skill: human_resources.interview_prep
            path: skills/human-resources/interview-prep/SKILL.md
            status: ADOPTED
            anchors: [interview, prep, create, structured, plans]
      onboarding:
        path: skills/human-resources/onboarding/
        skill_count: 1
        skills:
          - skill: human_resources.onboarding
            path: skills/human-resources/onboarding/SKILL.md
            status: ADOPTED
            anchors: [onboarding, generate, checklist, first, week]
      org-planning:
        path: skills/human-resources/org-planning/
        skill_count: 1
        skills:
          - skill: human_resources.org_planning
            path: skills/human-resources/org-planning/SKILL.md
            status: ADOPTED
            anchors: [planning, headcount, design, team, structure]
      people-report:
        path: skills/human-resources/people-report/
        skill_count: 1
        skills:
          - skill: human_resources.people_report
            path: skills/human-resources/people-report/SKILL.md
            status: ADOPTED
            anchors: [people, report, generate, headcount, attrition]
      performance-review:
        path: skills/human-resources/performance-review/
        skill_count: 1
        skills:
          - skill: human_resources.performance_review
            path: skills/human-resources/performance-review/SKILL.md
            status: ADOPTED
            anchors: [performance, review, structure, self, assessment]
      policy-lookup:
        path: skills/human-resources/policy-lookup/
        skill_count: 1
        skills:
          - skill: human_resources.policy_lookup
            path: skills/human-resources/policy-lookup/SKILL.md
            status: ADOPTED
            anchors: [policy, lookup, find, explain, company]
      recruiting-pipeline:
        path: skills/human-resources/recruiting-pipeline/
        skill_count: 1
        skills:
          - skill: human_resources.recruiting_pipeline
            path: skills/human-resources/recruiting-pipeline/SKILL.md
            status: ADOPTED
            anchors: [recruiting, pipeline, track, manage, stages]
      skills:
        path: skills/human-resources/skills/
        skill_count: 1
        skills:
          - skill: human_resources.skills
            path: skills/human-resources/skills/SKILL.md
            status: ADOPTED
            anchors: [recruiting, pipeline, track, manage, stages]

  INTEGRATIONS:
    path: skills/integrations/
    display_name: "Integrations"
    skill_count: 841
    anchors: [guidance, slack, search, messages, for, effectively, searching, find, files, node, configuration, operation, aware, configuring, nodes]
    sub_domains:
      composio:
        path: skills/integrations/composio/
        skill_count: 832
        skills:
          - skill: -21risk-automation
            path: skills/integrations/composio/-21risk-automation/SKILL.md
            status: UNKNOWN
          - skill: -2chat-automation
            path: skills/integrations/composio/-2chat-automation/SKILL.md
            status: UNKNOWN
          - skill: ably-automation
            path: skills/integrations/composio/ably-automation/SKILL.md
            status: UNKNOWN
          - skill: abstract-automation
            path: skills/integrations/composio/abstract-automation/SKILL.md
            status: UNKNOWN
          - skill: abuselpdb-automation
            path: skills/integrations/composio/abuselpdb-automation/SKILL.md
            status: UNKNOWN
          # ... +827 skills adicionais
      n8n:
        path: skills/integrations/n8n/
        skill_count: 3
        skills:
          - skill: integrations.n8n.n8n_node_configuration
            path: skills/integrations/n8n/n8n-node-configuration/SKILL.md
            status: CANDIDATE
            anchors: [node, configuration, operation, aware, guidance]
          - skill: integrations.n8n.n8n_validation_expert
            path: skills/integrations/n8n/n8n-validation-expert/SKILL.md
            status: CANDIDATE
            anchors: [validation, expert, guide, interpreting, fixing]
          - skill: integrations.n8n.n8n_workflow_patterns
            path: skills/integrations/n8n/n8n-workflow-patterns/SKILL.md
            status: CANDIDATE
            anchors: [workflow, patterns, proven, architectural, building]
      slack:
        path: skills/integrations/slack/
        skill_count: 5
        skills:
          - skill: integrations.slack.skills
            path: skills/integrations/slack/skills/SKILL.md
            status: ADOPTED
            anchors: [slack, search, guidance, effectively, searching]
          - skill: integrations.slack.slack_gif_creator
            path: skills/integrations/slack/slack-gif-creator/SKILL.md
            status: CANDIDATE
            anchors: [slack, creator, toolkit, providing, utilities]
          - skill: integrations.slack.slack_messaging
            path: skills/integrations/slack/slack-messaging/SKILL.md
            status: ADOPTED
            anchors: [slack, messaging, guidance, composing, well]
          - skill: integrations.slack.slack_search
            path: skills/integrations/slack/slack-search/SKILL.md
            status: ADOPTED
            anchors: [slack, search, guidance, effectively, searching]
          - skill: integrations.slack.yes_md
            path: skills/integrations/slack/yes-md/SKILL.md
            status: CANDIDATE
            anchors: [layer, governance, safety, gates, evidence]
      tavily:
        path: skills/integrations/tavily/
        skill_count: 1
        skills:
          - skill: integrations.tavily.tavily_web
            path: skills/integrations/tavily/tavily-web/SKILL.md
            status: CANDIDATE
            anchors: [tavily, search, content, extraction, crawling]

  KNOWLEDGE_MANAGEMENT:
    path: skills/knowledge-management/
    display_name: "Knowledge Management"
    skill_count: 10
    anchors: [sources, search, connected, source, generate, query, management, manages, enterprise, detects, digest, daily, weekly, activity, catching]
    sub_domains:
      search:
        path: skills/knowledge-management/search/
        skill_count: 6
        skills:
          - skill: knowledge_management.search.digest
            path: skills/knowledge-management/search/digest/SKILL.md
            status: ADOPTED
            anchors: [digest, generate, daily, weekly, activity]
          - skill: knowledge_management.search.knowledge_synthesis
            path: skills/knowledge-management/search/knowledge-synthesis/SKILL.md
            status: ADOPTED
            anchors: [knowledge, synthesis, combines, search, results]
          - skill: knowledge_management.search.search
            path: skills/knowledge-management/search/search/SKILL.md
            status: ADOPTED
            anchors: [search, connected, sources, query, trigger]
          - skill: knowledge_management.search.search_strategy
            path: skills/knowledge-management/search/search-strategy/SKILL.md
            status: ADOPTED
            anchors: [search, strategy, query, decomposition, multi]
          - skill: knowledge_management.search.skills
            path: skills/knowledge-management/search/skills/SKILL.md
            status: ADOPTED
            anchors: [source, management, manages, connected, sources]
          # ... +1 skills adicionais
      wiki:
        path: skills/knowledge-management/wiki/
        skill_count: 4
        skills:
          - skill: knowledge_management.wiki.wiki_changelog
            path: skills/knowledge-management/wiki/wiki-changelog/SKILL.md
            status: CANDIDATE
          - skill: knowledge_management.wiki.wiki_onboarding
            path: skills/knowledge-management/wiki/wiki-onboarding/SKILL.md
            status: CANDIDATE
            anchors: [wiki, onboarding, generate, complementary, documents]
          - skill: knowledge_management.wiki.wiki_researcher
            path: skills/knowledge-management/wiki/wiki-researcher/SKILL.md
            status: CANDIDATE
          - skill: knowledge_management.wiki.wiki_vitepress
            path: skills/knowledge-management/wiki/wiki-vitepress/SKILL.md
            status: CANDIDATE

  KNOWLEDGE_WORK:
    path: skills/knowledge-work/
    display_name: "Knowledge Work"
    skill_count: 248
    anchors: [and, generate, for, research, when, your, analysis, create, design, this, draft, common, run, skill, data]
    sub_domains:
      _source:
        path: skills/knowledge-work/_source/
        skill_count: 124
        skills:
          - skill: instrument-data-to-allotrope
            path: skills/knowledge-work/_source/bio-research/skills/instrument-data-to-allotrope/SKILL.md
            status: UNKNOWN
            anchors: [instrument-data-to-allotrope, convert, laboratory, instrument, output]
          - skill: nextflow-development
            path: skills/knowledge-work/_source/bio-research/skills/nextflow-development/SKILL.md
            status: UNKNOWN
            anchors: [nextflow-development, run, nf-core, bioinformatics, pipelines]
          - skill: scientific-problem-selection
            path: skills/knowledge-work/_source/bio-research/skills/scientific-problem-selection/SKILL.md
            status: UNKNOWN
            anchors: [scientific-problem-selection, this, skill, should, when]
          - skill: scvi-tools
            path: skills/knowledge-work/_source/bio-research/skills/scvi-tools/SKILL.md
            status: UNKNOWN
            anchors: [scvi-tools, deep, learning, for, single-cell]
          - skill: single-cell-rna-qc
            path: skills/knowledge-work/_source/bio-research/skills/single-cell-rna-qc/SKILL.md
            status: UNKNOWN
            anchors: [single-cell-rna-qc, performs, quality, control, single-cell]
          # ... +119 skills adicionais
      _source_v2:
        path: skills/knowledge-work/_source_v2/
        skill_count: 124
        skills:
          - skill: instrument-data-to-allotrope
            path: skills/knowledge-work/_source_v2/bio-research/skills/instrument-data-to-allotrope/SKILL.md
            status: UNKNOWN
            anchors: [instrument-data-to-allotrope, convert, laboratory, instrument, output]
          - skill: nextflow-development
            path: skills/knowledge-work/_source_v2/bio-research/skills/nextflow-development/SKILL.md
            status: UNKNOWN
            anchors: [nextflow-development, run, nf-core, bioinformatics, pipelines]
          - skill: scientific-problem-selection
            path: skills/knowledge-work/_source_v2/bio-research/skills/scientific-problem-selection/SKILL.md
            status: UNKNOWN
            anchors: [scientific-problem-selection, this, skill, should, when]
          - skill: scvi-tools
            path: skills/knowledge-work/_source_v2/bio-research/skills/scvi-tools/SKILL.md
            status: UNKNOWN
            anchors: [scvi-tools, deep, learning, for, single-cell]
          - skill: single-cell-rna-qc
            path: skills/knowledge-work/_source_v2/bio-research/skills/single-cell-rna-qc/SKILL.md
            status: UNKNOWN
            anchors: [single-cell-rna-qc, performs, quality, control, single-cell]
          # ... +119 skills adicionais

  LEGAL:
    path: skills/legal/
    display_name: "Legal"
    skill_count: 27
    anchors: [legal, compliance, design, contract, check, advogado, criminal, art_406_cc, juros_legais, accessibility, audit, expert, review, for, data]
    sub_domains:
      brazil:
        path: skills/legal/brazil/
        skill_count: 2
        skills:
          - skill: legal.brazil.advogado_criminal
            path: skills/legal/brazil/advogado-criminal/SKILL.md
            status: CANDIDATE
            anchors: [advogado, criminal, criminalista, especializado, maria]
          - skill: legal.brazil.advogado_especialista
            path: skills/legal/brazil/advogado-especialista/SKILL.md
            status: CANDIDATE
            anchors: [advogado, especialista, todas, areas, direito]
      civil-law:
        path: skills/legal/civil-law/
        skill_count: 2
        skills:
          - skill: legal.civil_law.contracts.financial_clauses
            path: skills/legal/civil-law/contracts/financial-clauses/SKILL.md
            status: ADOPTED
            anchors: [IGPM, IPCA, INPC, reajuste, correcao_monetaria]
          - skill: legal.civil_law.obligations
            path: skills/legal/civil-law/obligations/SKILL.md
            status: ADOPTED
            anchors: [obrigacao, devedor, credor, mora, art_394_cc]
      compliance:
        path: skills/legal/compliance/
        skill_count: 5
        skills:
          - skill: legal.compliance.accessibility_compliance_accessibility_audit
            path: skills/legal/compliance/accessibility-compliance-accessibility-audit/SKILL.md
            status: CANDIDATE
            anchors: [accessibility, compliance, audit, expert, specializing]
          - skill: legal.compliance.fda_food_safety_auditor
            path: skills/legal/compliance/fda-food-safety-auditor/SKILL.md
            status: CANDIDATE
            anchors: [food, safety, auditor, expert, fsma]
          - skill: legal.compliance.fixing_accessibility
            path: skills/legal/compliance/fixing-accessibility/SKILL.md
            status: CANDIDATE
            anchors: [fixing, accessibility, audit, html, issues]
          - skill: legal.compliance.payment_integration
            path: skills/legal/compliance/payment-integration/SKILL.md
            status: CANDIDATE
            anchors: [payment, integration, integrate, stripe, paypal]
          - skill: legal.compliance.web_design_guidelines
            path: skills/legal/compliance/web-design-guidelines/SKILL.md
            status: CANDIDATE
            anchors: [design, guidelines, review, files, compliance]
      contract-and-proposal-writer:
        path: skills/legal/contract-and-proposal-writer/
        skill_count: 1
        skills:
          - skill: legal.contract_and_proposal_writer
            path: skills/legal/contract-and-proposal-writer/SKILL.md
            status: CANDIDATE
            anchors: [contract, proposal, writer, contract-and-proposal-writer, data]
      contracts:
        path: skills/legal/contracts/
        skill_count: 3
        skills:
          - skill: legal.contracts.ai_native_cli
            path: skills/legal/contracts/ai-native-cli/SKILL.md
            status: CANDIDATE
            anchors: [native, design, spec, rules, building]
          - skill: legal.contracts.data_quality_frameworks
            path: skills/legal/contracts/data-quality-frameworks/SKILL.md
            status: CANDIDATE
            anchors: [data, quality, frameworks, implement, validation]
          - skill: legal.contracts.pydantic_models_py
            path: skills/legal/contracts/pydantic-models-py/SKILL.md
            status: CANDIDATE
            anchors: [pydantic, models, create, following, multi]
      knowledge-work:
        path: skills/legal/knowledge-work/
        skill_count: 10
        skills:
          - skill: legal.knowledge_work.brief
            path: skills/legal/knowledge-work/brief/SKILL.md
            status: ADOPTED
            anchors: [brief, generate, contextual, briefings, legal]
          - skill: legal.knowledge_work.compliance_check
            path: skills/legal/knowledge-work/compliance-check/SKILL.md
            status: ADOPTED
            anchors: [compliance, check, proposed, action, product]
          - skill: legal.knowledge_work.legal_response
            path: skills/legal/knowledge-work/legal-response/SKILL.md
            status: ADOPTED
            anchors: [legal, response, generate, common, inquiry]
          - skill: legal.knowledge_work.legal_risk_assessment
            path: skills/legal/knowledge-work/legal-risk-assessment/SKILL.md
            status: ADOPTED
            anchors: [legal, risk, assessment, assess, classify]
          - skill: legal.knowledge_work.meeting_briefing
            path: skills/legal/knowledge-work/meeting-briefing/SKILL.md
            status: ADOPTED
            anchors: [meeting, briefing, prepare, structured, briefings]
          # ... +5 skills adicionais
      legal-advisor:
        path: skills/legal/legal-advisor/
        skill_count: 1
        skills:
          - skill: legal.legal_advisor
            path: skills/legal/legal-advisor/SKILL.md
            status: CANDIDATE
            anchors: [legal, advisor, draft, privacy, policies]
      lex:
        path: skills/legal/lex/
        skill_count: 1
        skills:
          - skill: legal.lex
            path: skills/legal/lex/SKILL.md
            status: CANDIDATE
            anchors: [centralized, truth, engine, cross, jurisdictional]
      mdr-745-specialist:
        path: skills/legal/mdr-745-specialist/
        skill_count: 1
        skills:
          - skill: legal.mdr_745_specialist
            path: skills/legal/mdr-745-specialist/SKILL.md
            status: CANDIDATE
            anchors: [specialist, compliance, medical, device, classification]
      regulatory-affairs-head:
        path: skills/legal/regulatory-affairs-head/
        skill_count: 1
        skills:
          - skill: legal.regulatory_affairs_head
            path: skills/legal/regulatory-affairs-head/SKILL.md
            status: CANDIDATE
            anchors: [regulatory, affairs, head, senior, manager]

  MARKETING:
    path: skills/marketing/
    display_name: "Marketing"
    skill_count: 137
    anchors: [when, the, content, optimize, create, marketing, plan, audit, analysis, improve, and, pages, page, schema, for]
    sub_domains:
      _source_marketingskills:
        path: skills/marketing/_source_marketingskills/
        skill_count: 35
        skills:
          - skill: ab-test-setup
            path: skills/marketing/_source_marketingskills/skills/ab-test-setup/SKILL.md
            status: UNKNOWN
            anchors: [ab-test-setup, when, the, plan, design]
          - skill: ad-creative
            path: skills/marketing/_source_marketingskills/skills/ad-creative/SKILL.md
            status: UNKNOWN
            anchors: [ad-creative, when, the, generate, iterate]
          - skill: ai-seo
            path: skills/marketing/_source_marketingskills/skills/ai-seo/SKILL.md
            status: UNKNOWN
            anchors: [ai-seo, when, the, optimize, content]
          - skill: analytics-tracking
            path: skills/marketing/_source_marketingskills/skills/analytics-tracking/SKILL.md
            status: UNKNOWN
            anchors: [analytics-tracking, when, the, set, improve]
          - skill: churn-prevention
            path: skills/marketing/_source_marketingskills/skills/churn-prevention/SKILL.md
            status: UNKNOWN
            anchors: [churn-prevention, when, the, reduce, churn]
          # ... +30 skills adicionais
      ab-test-setup:
        path: skills/marketing/ab-test-setup/
        skill_count: 1
        skills:
          - skill: marketing.ab_test_setup
            path: skills/marketing/ab-test-setup/SKILL.md
            status: CANDIDATE
            anchors: [test, setup, when, plan, ab-test-setup]
      ad-creative:
        path: skills/marketing/ad-creative/
        skill_count: 1
        skills:
          - skill: marketing.ad_creative
            path: skills/marketing/ad-creative/SKILL.md
            status: CANDIDATE
            anchors: [creative, when, generate, iterate, ad-creative]
      ai-seo:
        path: skills/marketing/ai-seo/
        skill_count: 1
        skills:
          - skill: marketing.ai_seo
            path: skills/marketing/ai-seo/SKILL.md
            status: CANDIDATE
            anchors: [when, optimize, content, search, ai-seo]
      analytics-tracking:
        path: skills/marketing/analytics-tracking/
        skill_count: 1
        skills:
          - skill: marketingskills.marketing.analytics_tracking
            path: skills/marketing/analytics-tracking/SKILL.md
            status: CANDIDATE
            anchors: [analytics, tracking, when, improve, analytics-tracking]
      brand-guidelines:
        path: skills/marketing/brand-guidelines/
        skill_count: 1
        skills:
          - skill: marketing.brand_guidelines
            path: skills/marketing/brand-guidelines/SKILL.md
            status: CANDIDATE
            anchors: [brand, guidelines, applies, anthropic, official]
      brand-review:
        path: skills/marketing/brand-review/
        skill_count: 1
        skills:
          - skill: marketing.brand_review
            path: skills/marketing/brand-review/SKILL.md
            status: ADOPTED
            anchors: [brand, review, content, against, voice]
      brand-voice:
        path: skills/marketing/brand-voice/
        skill_count: 4
        skills:
          - skill: marketing.brand_voice.brand_voice_enforcement
            path: skills/marketing/brand-voice/brand-voice-enforcement/SKILL.md
            status: ADOPTED
            anchors: [brand, voice, enforcement, apply, existing]
          - skill: marketing.brand_voice.discover_brand
            path: skills/marketing/brand-voice/discover-brand/SKILL.md
            status: ADOPTED
            anchors: [discover, brand, discovery, orchestrate, autonomous]
          - skill: marketing.brand_voice.guideline_generation
            path: skills/marketing/brand-voice/guideline-generation/SKILL.md
            status: ADOPTED
            anchors: [guideline, generation, generate, comprehensive, ready]
          - skill: marketing.brand_voice.skills
            path: skills/marketing/brand-voice/skills/SKILL.md
            status: ADOPTED
            anchors: [guideline, generation, generate, comprehensive, ready]
      campaign-plan:
        path: skills/marketing/campaign-plan/
        skill_count: 1
        skills:
          - skill: marketing.campaign_plan
            path: skills/marketing/campaign-plan/SKILL.md
            status: ADOPTED
            anchors: [campaign, plan, generate, full, brief]
      chief-of-staff:
        path: skills/marketing/chief-of-staff/
        skill_count: 1
        skills:
          - skill: marketing.chief_of_staff
            path: skills/marketing/chief-of-staff/SKILL.md
            status: CANDIDATE
            anchors: [chief, staff, suite, orchestration, layer]
      churn-prevention:
        path: skills/marketing/churn-prevention/
        skill_count: 1
        skills:
          - skill: marketing.churn_prevention
            path: skills/marketing/churn-prevention/SKILL.md
            status: CANDIDATE
            anchors: [churn, prevention, when, reduce, churn-prevention]
      cold-email:
        path: skills/marketing/cold-email/
        skill_count: 1
        skills:
          - skill: marketingskills.marketing.cold_email
            path: skills/marketing/cold-email/SKILL.md
            status: CANDIDATE
            anchors: [cold, email, write, emails, follow]
      community-marketing:
        path: skills/marketing/community-marketing/
        skill_count: 1
        skills:
          - skill: marketing.community_marketing
            path: skills/marketing/community-marketing/SKILL.md
            status: CANDIDATE
            anchors: [community, marketing, build, leverage, online]
      competitive-ads-extractor:
        path: skills/marketing/competitive-ads-extractor/
        skill_count: 1
        skills:
          - skill: marketing.competitive_ads_extractor
            path: skills/marketing/competitive-ads-extractor/SKILL.md
            status: CANDIDATE
            anchors: [competitive, extractor, extracts, analyzes, competitors]
      competitive-brief:
        path: skills/marketing/competitive-brief/
        skill_count: 1
        skills:
          - skill: marketing.competitive_brief
            path: skills/marketing/competitive-brief/SKILL.md
            status: ADOPTED
            anchors: [competitive, brief, research, competitors, generate]
      competitor-alternatives:
        path: skills/marketing/competitor-alternatives/
        skill_count: 1
        skills:
          - skill: marketingskills.marketing.competitor_alternatives
            path: skills/marketing/competitor-alternatives/SKILL.md
            status: CANDIDATE
            anchors: [competitor, alternatives, when, create, competitor-alternatives]
      composio-skills:
        path: skills/marketing/composio-skills/
        skill_count: 1
        skills:
          - skill: marketing.composio_skills
            path: skills/marketing/composio-skills/SKILL.md
            status: CANDIDATE
            anchors: [composio, skills, automate, activecampaign, tasks]
      content-creation:
        path: skills/marketing/content-creation/
        skill_count: 1
        skills:
          - skill: marketing.content_creation
            path: skills/marketing/content-creation/SKILL.md
            status: ADOPTED
            anchors: [content, creation, draft, marketing, channels]
      content-creator:
        path: skills/marketing/content-creator/
        skill_count: 1
        skills:
          - skill: marketing.content_creator
            path: skills/marketing/content-creator/SKILL.md
            status: CANDIDATE
            anchors: [content, creator, deprecated, redirect, skill]
      content-marketer:
        path: skills/marketing/content-marketer/
        skill_count: 1
        skills:
          - skill: marketing.content_marketer
            path: skills/marketing/content-marketer/SKILL.md
            status: CANDIDATE
            anchors: [content, marketer, elite, marketing, strategist]
      content-strategy:
        path: skills/marketing/content-strategy/
        skill_count: 1
        skills:
          - skill: marketing.content_strategy
            path: skills/marketing/content-strategy/SKILL.md
            status: CANDIDATE
            anchors: [content, strategy, when, plan, content-strategy]
      context-engine:
        path: skills/marketing/context-engine/
        skill_count: 1
        skills:
          - skill: marketing.context_engine
            path: skills/marketing/context-engine/SKILL.md
            status: CANDIDATE
            anchors: [context, engine, loads, manages, company]
      copy-editing:
        path: skills/marketing/copy-editing/
        skill_count: 1
        skills:
          - skill: marketingskills.marketing.copy_editing
            path: skills/marketing/copy-editing/SKILL.md
            status: CANDIDATE
            anchors: [copy, editing, when, edit, copy-editing]
      copywriting:
        path: skills/marketing/copywriting/
        skill_count: 1
        skills:
          - skill: marketingskills.marketing.copywriting
            path: skills/marketing/copywriting/SKILL.md
            status: CANDIDATE
            anchors: [copywriting, when, write, rewrite, the]
      customer-research:
        path: skills/marketing/customer-research/
        skill_count: 1
        skills:
          - skill: marketing.customer_research
            path: skills/marketing/customer-research/SKILL.md
            status: CANDIDATE
            anchors: [customer, research, when, conduct, customer-research]
      demo-video:
        path: skills/marketing/demo-video/
        skill_count: 1
        skills:
          - skill: marketing.demo_video
            path: skills/marketing/demo-video/SKILL.md
            status: CANDIDATE
            anchors: [demo, video, when, create, demo-video]
      draft-content:
        path: skills/marketing/draft-content/
        skill_count: 1
        skills:
          - skill: marketing.draft_content
            path: skills/marketing/draft-content/SKILL.md
            status: ADOPTED
            anchors: [draft, content, blog, posts, social]
      email-sequence:
        path: skills/marketing/email-sequence/
        skill_count: 1
        skills:
          - skill: marketingskills.marketing.email_sequence
            path: skills/marketing/email-sequence/SKILL.md
            status: CANDIDATE
            anchors: [email, sequence, when, create, email-sequence]
      email-systems:
        path: skills/marketing/email-systems/
        skill_count: 1
        skills:
          - skill: marketing.email_systems
            path: skills/marketing/email-systems/SKILL.md
            status: CANDIDATE
            anchors: [email, systems, highest, marketing, channel]
      form-cro:
        path: skills/marketing/form-cro/
        skill_count: 1
        skills:
          - skill: marketingskills.marketing.form_cro
            path: skills/marketing/form-cro/SKILL.md
            status: CANDIDATE
            anchors: [form, when, optimize, that, form-cro]
      free-tool-strategy:
        path: skills/marketing/free-tool-strategy/
        skill_count: 1
        skills:
          - skill: marketingskills.marketing.free_tool_strategy
            path: skills/marketing/free-tool-strategy/SKILL.md
            status: CANDIDATE
            anchors: [free, tool, strategy, when, free-tool-strategy]
      growth-engine:
        path: skills/marketing/growth-engine/
        skill_count: 1
        skills:
          - skill: marketing.growth_engine
            path: skills/marketing/growth-engine/SKILL.md
            status: CANDIDATE
            anchors: [growth, engine, motor, crescimento, para]
      launch-strategy:
        path: skills/marketing/launch-strategy/
        skill_count: 1
        skills:
          - skill: marketing.launch_strategy
            path: skills/marketing/launch-strategy/SKILL.md
            status: CANDIDATE
            anchors: [launch, strategy, when, plan, launch-strategy]
      lead-magnets:
        path: skills/marketing/lead-magnets/
        skill_count: 1
        skills:
          - skill: marketing.lead_magnets
            path: skills/marketing/lead-magnets/SKILL.md
            status: CANDIDATE
            anchors: [lead, magnets, when, create, lead-magnets]
      lead-research-assistant:
        path: skills/marketing/lead-research-assistant/
        skill_count: 1
        skills:
          - skill: marketing.lead_research_assistant
            path: skills/marketing/lead-research-assistant/SKILL.md
            status: CANDIDATE
            anchors: [lead, research, assistant, identifies, high]
      marketing-context:
        path: skills/marketing/marketing-context/
        skill_count: 1
        skills:
          - skill: marketing.marketing_context
            path: skills/marketing/marketing-context/SKILL.md
            status: CANDIDATE
            anchors: [marketing, context, create, maintain, document]
      marketing-ideas:
        path: skills/marketing/marketing-ideas/
        skill_count: 1
        skills:
          - skill: marketingskills.marketing.marketing_ideas
            path: skills/marketing/marketing-ideas/SKILL.md
            status: CANDIDATE
            anchors: [marketing, ideas, when, inspiration, marketing-ideas]
      marketing-ops:
        path: skills/marketing/marketing-ops/
        skill_count: 1
        skills:
          - skill: marketing.marketing_ops
            path: skills/marketing/marketing-ops/SKILL.md
            status: CANDIDATE
            anchors: [marketing, central, router, skill, ecosystem]
      marketing-psychology:
        path: skills/marketing/marketing-psychology/
        skill_count: 1
        skills:
          - skill: marketing.marketing_psychology
            path: skills/marketing/marketing-psychology/SKILL.md
            status: CANDIDATE
            anchors: [marketing, psychology, when, apply, marketing-psychology]
      marketing-strategy-pmm:
        path: skills/marketing/marketing-strategy-pmm/
        skill_count: 1
        skills:
          - skill: marketing.marketing_strategy_pmm
            path: skills/marketing/marketing-strategy-pmm/SKILL.md
            status: CANDIDATE
            anchors: [marketing, strategy, product, skill, positioning]
      meeting-analyzer:
        path: skills/marketing/meeting-analyzer/
        skill_count: 1
        skills:
          - skill: marketing.meeting_analyzer
            path: skills/marketing/meeting-analyzer/SKILL.md
            status: CANDIDATE
            anchors: [meeting, analyzer, analyzes, transcripts, recordings]
      onboarding-cro:
        path: skills/marketing/onboarding-cro/
        skill_count: 1
        skills:
          - skill: marketing.onboarding_cro
            path: skills/marketing/onboarding-cro/SKILL.md
            status: CANDIDATE
            anchors: [onboarding, when, optimize, post, onboarding-cro]
      page-cro:
        path: skills/marketing/page-cro/
        skill_count: 1
        skills:
          - skill: marketingskills.marketing.page_cro
            path: skills/marketing/page-cro/SKILL.md
            status: CANDIDATE
            anchors: [page, when, optimize, improve, page-cro]
      paid-ads:
        path: skills/marketing/paid-ads/
        skill_count: 1
        skills:
          - skill: marketingskills.marketing.paid_ads
            path: skills/marketing/paid-ads/SKILL.md
            status: CANDIDATE
            anchors: [paid, when, paid-ads, the, advertising]
      paywall-upgrade-cro:
        path: skills/marketing/paywall-upgrade-cro/
        skill_count: 1
        skills:
          - skill: marketing.paywall_upgrade_cro
            path: skills/marketing/paywall-upgrade-cro/SKILL.md
            status: CANDIDATE
            anchors: [paywall, upgrade, when, create, paywall-upgrade-cro]
      performance-report:
        path: skills/marketing/performance-report/
        skill_count: 1
        skills:
          - skill: marketing.performance_report
            path: skills/marketing/performance-report/SKILL.md
            status: ADOPTED
            anchors: [performance, report, build, marketing, metrics]
      popup-cro:
        path: skills/marketing/popup-cro/
        skill_count: 1
        skills:
          - skill: marketingskills.marketing.popup_cro
            path: skills/marketing/popup-cro/SKILL.md
            status: CANDIDATE
            anchors: [popup, when, create, optimize, popup-cro]
      pricing-strategy:
        path: skills/marketing/pricing-strategy/
        skill_count: 1
        skills:
          - skill: marketing.pricing_strategy
            path: skills/marketing/pricing-strategy/SKILL.md
            status: CANDIDATE
            anchors: [pricing, strategy, when, pricing-strategy, the]
      product-marketing-context:
        path: skills/marketing/product-marketing-context/
        skill_count: 1
        skills:
          - skill: marketingskills.marketing.product_marketing_context
            path: skills/marketing/product-marketing-context/SKILL.md
            status: CANDIDATE
            anchors: [product, marketing, context, when, product-marketing-context]
      programmatic-seo:
        path: skills/marketing/programmatic-seo/
        skill_count: 1
        skills:
          - skill: marketingskills.marketing.programmatic_seo
            path: skills/marketing/programmatic-seo/SKILL.md
            status: CANDIDATE
            anchors: [programmatic, when, create, driven, programmatic-seo]
      referral-program:
        path: skills/marketing/referral-program/
        skill_count: 1
        skills:
          - skill: marketingskills.marketing.referral_program
            path: skills/marketing/referral-program/SKILL.md
            status: CANDIDATE
            anchors: [referral, program, when, create, referral-program]
      resume:
        path: skills/marketing/resume/
        skill_count: 1
        skills:
          - skill: marketing.resume
            path: skills/marketing/resume/SKILL.md
            status: CANDIDATE
            anchors: [resume, paused, experiment, checkout, branch]
      revops:
        path: skills/marketing/revops/
        skill_count: 1
        skills:
          - skill: marketingskills.marketing.revops
            path: skills/marketing/revops/SKILL.md
            status: CANDIDATE
            anchors: [revops, when, the, revenue, operations]
      sales-enablement:
        path: skills/marketing/sales-enablement/
        skill_count: 1
        skills:
          - skill: marketing.sales_enablement
            path: skills/marketing/sales-enablement/SKILL.md
            status: CANDIDATE
            anchors: [sales, enablement, when, create, sales-enablement]
      schema-markup:
        path: skills/marketing/schema-markup/
        skill_count: 1
        skills:
          - skill: marketingskills.marketing.schema_markup
            path: skills/marketing/schema-markup/SKILL.md
            status: CANDIDATE
            anchors: [schema, markup, when, optimize, schema-markup]
      sendgrid-automation:
        path: skills/marketing/sendgrid-automation/
        skill_count: 1
        skills:
          - skill: marketing.sendgrid_automation
            path: skills/marketing/sendgrid-automation/SKILL.md
            status: CANDIDATE
            anchors: [sendgrid, automation, automate, email, delivery]
      seo:
        path: skills/marketing/seo/
        skill_count: 36
        skills:
          - skill: marketing.seo.content_creator
            path: skills/marketing/seo/content-creator/SKILL.md
            status: CANDIDATE
            anchors: [content, creator, professional, grade, brand]
          - skill: marketing.seo.fixing_metadata
            path: skills/marketing/seo/fixing-metadata/SKILL.md
            status: CANDIDATE
            anchors: [fixing, metadata, audit, html, page]
          - skill: marketing.seo.local_legal_seo_audit
            path: skills/marketing/seo/local-legal-seo-audit/SKILL.md
            status: CANDIDATE
            anchors: [local, legal, audit, improve, firms]
          - skill: marketing.seo.programmatic_seo
            path: skills/marketing/seo/programmatic-seo/SKILL.md
            status: CANDIDATE
            anchors: [programmatic, design, evaluate, strategies, creating]
          - skill: marketing.seo.schema_markup
            path: skills/marketing/seo/schema-markup/SKILL.md
            status: CANDIDATE
            anchors: [schema, markup, design, validate, optimize]
          # ... +31 skills adicionais
      seo-audit:
        path: skills/marketing/seo-audit/
        skill_count: 1
        skills:
          - skill: marketingskills.marketing.seo_audit
            path: skills/marketing/seo-audit/SKILL.md
            status: CANDIDATE
            anchors: [audit, when, review, diagnose, seo-audit]
      signup-flow-cro:
        path: skills/marketing/signup-flow-cro/
        skill_count: 1
        skills:
          - skill: marketing.signup_flow_cro
            path: skills/marketing/signup-flow-cro/SKILL.md
            status: CANDIDATE
            anchors: [signup, flow, when, optimize, signup-flow-cro]
      site-architecture:
        path: skills/marketing/site-architecture/
        skill_count: 1
        skills:
          - skill: marketingskills.marketing.site_architecture
            path: skills/marketing/site-architecture/SKILL.md
            status: CANDIDATE
            anchors: [site, architecture, when, plan, site-architecture]
      skills:
        path: skills/marketing/skills/
        skill_count: 1
        skills:
          - skill: marketing.skills
            path: skills/marketing/skills/SKILL.md
            status: ADOPTED
            anchors: [audit, comprehensive, keyword, research, page]
      social-content:
        path: skills/marketing/social-content/
        skill_count: 1
        skills:
          - skill: marketing.social_content
            path: skills/marketing/social-content/SKILL.md
            status: CANDIDATE
            anchors: [social, content, when, social-content, the]
      social-media-analyzer:
        path: skills/marketing/social-media-analyzer/
        skill_count: 1
        skills:
          - skill: marketing.social_media_analyzer
            path: skills/marketing/social-media-analyzer/SKILL.md
            status: CANDIDATE
            anchors: [social, media, analyzer, campaign, analysis]
      video-downloader:
        path: skills/marketing/video-downloader/
        skill_count: 1
        skills:
          - skill: marketing.video_downloader
            path: skills/marketing/video-downloader/SKILL.md
            status: CANDIDATE
            anchors: [video, downloader, download, youtube, videos]
      x-twitter-growth:
        path: skills/marketing/x-twitter-growth/
        skill_count: 1
        skills:
          - skill: marketing.x_twitter_growth
            path: skills/marketing/x-twitter-growth/SKILL.md
            status: CANDIDATE
            anchors: [twitter, growth, engine, building, audience]

  MATHEMATICS:
    path: skills/mathematics/
    display_name: "Mathematics"
    skill_count: 2
    anchors: [compound_interest, juros_compostos, taxa, periodo, montante, capitalizacao, igpm, ipca, inpc, ipca_e, correcao_monetaria, fator_correcao, indice_inflacionario, reajuste_monetario]
    sub_domains:
      financial-math:
        path: skills/mathematics/financial-math/
        skill_count: 2
        skills:
          - skill: mathematics.financial_math.compound_interest
            path: skills/mathematics/financial-math/compound-interest/SKILL.md
            status: ADOPTED
            anchors: [compound_interest, juros_compostos, VP, VF, taxa]
          - skill: mathematics.financial_math.inflation_adjustment
            path: skills/mathematics/financial-math/inflation-adjustment/SKILL.md
            status: ADOPTED
            anchors: [IGPM, IPCA, INPC, IPCA_E, correcao_monetaria]

  OPERATIONS:
    path: skills/operations/
    display_name: "Operations"
    skill_count: 10
    anchors: [analysis, trigger, risk, assessment, plan, create, process, business, operational, risks, vendor, review, evaluate, cost, recommendation]
    sub_domains:
      capacity-plan:
        path: skills/operations/capacity-plan/
        skill_count: 1
        skills:
          - skill: operations.capacity_plan
            path: skills/operations/capacity-plan/SKILL.md
            status: ADOPTED
            anchors: [capacity, plan, resource, workload, analysis]
      change-request:
        path: skills/operations/change-request/
        skill_count: 1
        skills:
          - skill: operations.change_request
            path: skills/operations/change-request/SKILL.md
            status: ADOPTED
            anchors: [change, request, create, management, impact]
      compliance-tracking:
        path: skills/operations/compliance-tracking/
        skill_count: 1
        skills:
          - skill: operations.compliance_tracking
            path: skills/operations/compliance-tracking/SKILL.md
            status: ADOPTED
            anchors: [compliance, tracking, track, requirements, audit]
      process-doc:
        path: skills/operations/process-doc/
        skill_count: 1
        skills:
          - skill: operations.process_doc
            path: skills/operations/process-doc/SKILL.md
            status: ADOPTED
            anchors: [process, document, business, flowcharts, raci]
      process-optimization:
        path: skills/operations/process-optimization/
        skill_count: 1
        skills:
          - skill: operations.process_optimization
            path: skills/operations/process-optimization/SKILL.md
            status: ADOPTED
            anchors: [process, optimization, analyze, improve, business]
      risk-assessment:
        path: skills/operations/risk-assessment/
        skill_count: 1
        skills:
          - skill: operations.risk_assessment
            path: skills/operations/risk-assessment/SKILL.md
            status: ADOPTED
            anchors: [risk, assessment, identify, assess, mitigate]
      runbook:
        path: skills/operations/runbook/
        skill_count: 1
        skills:
          - skill: operations.runbook
            path: skills/operations/runbook/SKILL.md
            status: ADOPTED
            anchors: [runbook, create, update, operational, recurring]
      skills:
        path: skills/operations/skills/
        skill_count: 1
        skills:
          - skill: operations.skills
            path: skills/operations/skills/SKILL.md
            status: ADOPTED
            anchors: [vendor, review, evaluate, cost, analysis]
      status-report:
        path: skills/operations/status-report/
        skill_count: 1
        skills:
          - skill: operations.status_report
            path: skills/operations/status-report/SKILL.md
            status: ADOPTED
            anchors: [status, report, generate, kpis, risks]
      vendor-review:
        path: skills/operations/vendor-review/
        skill_count: 1
        skills:
          - skill: operations.vendor_review
            path: skills/operations/vendor-review/SKILL.md
            status: ADOPTED
            anchors: [vendor, review, evaluate, cost, analysis]

  PRODUCT_MANAGEMENT:
    path: skills/product-management/
    display_name: "Product Management"
    skill_count: 11
    anchors: [product, feature, problem, create, analysis, insights, manager, frameworks, update, write, spec, statement, idea, turning, vague]
    sub_domains:
      competitive-brief:
        path: skills/product-management/competitive-brief/
        skill_count: 1
        skills:
          - skill: product_management.competitive_brief
            path: skills/product-management/competitive-brief/SKILL.md
            status: ADOPTED
            anchors: [competitive, brief, create, analysis, competitors]
      metrics-review:
        path: skills/product-management/metrics-review/
        skill_count: 1
        skills:
          - skill: product_management.metrics_review
            path: skills/product-management/metrics-review/SKILL.md
            status: ADOPTED
            anchors: [metrics, review, analyze, product, trend]
      product-brainstorming:
        path: skills/product-management/product-brainstorming/
        skill_count: 1
        skills:
          - skill: product_management.product_brainstorming
            path: skills/product-management/product-brainstorming/SKILL.md
            status: ADOPTED
            anchors: [product, brainstorming, brainstorm, ideas, explore]
      product-manager:
        path: skills/product-management/product-manager/
        skill_count: 1
        skills:
          - skill: product_management.product_manager
            path: skills/product-management/product-manager/SKILL.md
            status: CANDIDATE
            anchors: [product, manager, senior, agent, knowledge]
      product-manager-toolkit:
        path: skills/product-management/product-manager-toolkit/
        skill_count: 1
        skills:
          - skill: product_management.product_manager_toolkit
            path: skills/product-management/product-manager-toolkit/SKILL.md
            status: CANDIDATE
            anchors: [product, manager, toolkit, essential, tools]
      roadmap-update:
        path: skills/product-management/roadmap-update/
        skill_count: 1
        skills:
          - skill: product_management.roadmap_update
            path: skills/product-management/roadmap-update/SKILL.md
            status: ADOPTED
            anchors: [roadmap, update, create, reprioritize, product]
      skills:
        path: skills/product-management/skills/
        skill_count: 1
        skills:
          - skill: product_management.skills
            path: skills/product-management/skills/SKILL.md
            status: ADOPTED
            anchors: [write, spec, feature, problem, statement]
      sprint-planning:
        path: skills/product-management/sprint-planning/
        skill_count: 1
        skills:
          - skill: product_management.sprint_planning
            path: skills/product-management/sprint-planning/SKILL.md
            status: ADOPTED
            anchors: [sprint, planning, plan, scope, work]
      stakeholder-update:
        path: skills/product-management/stakeholder-update/
        skill_count: 1
        skills:
          - skill: product_management.stakeholder_update
            path: skills/product-management/stakeholder-update/SKILL.md
            status: ADOPTED
            anchors: [stakeholder, update, generate, tailored, audience]
      synthesize-research:
        path: skills/product-management/synthesize-research/
        skill_count: 1
        skills:
          - skill: product_management.synthesize_research
            path: skills/product-management/synthesize-research/SKILL.md
            status: ADOPTED
            anchors: [synthesize, research, user, interviews, surveys]
      write-spec:
        path: skills/product-management/write-spec/
        skill_count: 1
        skills:
          - skill: product_management.write_spec
            path: skills/product-management/write-spec/SKILL.md
            status: ADOPTED
            anchors: [write, spec, feature, problem, statement]

  PRODUCTIVITY:
    path: skills/productivity/
    display_name: "Productivity"
    skill_count: 22
    anchors: [writing, user, task, skill, open, memory, management, tasks, skills, planning, plan, view, interactive, viewer, wants]
    sub_domains:
      concise-planning:
        path: skills/productivity/concise-planning/
        skill_count: 1
        skills:
          - skill: productivity.concise_planning
            path: skills/productivity/concise-planning/SKILL.md
            status: CANDIDATE
            anchors: [concise, planning, user, asks, plan]
      documents:
        path: skills/productivity/documents/
        skill_count: 2
        skills:
          - skill: productivity.documents.skills
            path: skills/productivity/documents/skills/SKILL.md
            status: ADOPTED
            anchors: [view, interactive, viewer, user, wants]
          - skill: productivity.documents.view_pdf
            path: skills/productivity/documents/view-pdf/SKILL.md
            status: ADOPTED
            anchors: [view, interactive, viewer, user, wants]
      memory-management:
        path: skills/productivity/memory-management/
        skill_count: 1
        skills:
          - skill: productivity.memory_management
            path: skills/productivity/memory-management/SKILL.md
            status: ADOPTED
            anchors: [memory, management, tier, system, makes]
      office-productivity:
        path: skills/productivity/office-productivity/
        skill_count: 1
        skills:
          - skill: productivity.office_productivity
            path: skills/productivity/office-productivity/SKILL.md
            status: CANDIDATE
            anchors: [office, productivity, workflow, covering, document]
      skills:
        path: skills/productivity/skills/
        skill_count: 1
        skills:
          - skill: productivity.skills
            path: skills/productivity/skills/SKILL.md
            status: ADOPTED
            anchors: [update, sync, tasks, refresh, memory]
      start:
        path: skills/productivity/start/
        skill_count: 1
        skills:
          - skill: productivity.start
            path: skills/productivity/start/SKILL.md
            status: ADOPTED
            anchors: [start, initialize, productivity, system, open]
      task-management:
        path: skills/productivity/task-management/
        skill_count: 1
        skills:
          - skill: productivity.task_management
            path: skills/productivity/task-management/SKILL.md
            status: ADOPTED
            anchors: [task, management, simple, shared, tasks]
      update:
        path: skills/productivity/update/
        skill_count: 1
        skills:
          - skill: productivity.update
            path: skills/productivity/update/SKILL.md
            status: ADOPTED
            anchors: [update, sync, tasks, refresh, memory]
      writing:
        path: skills/productivity/writing/
        skill_count: 13
        skills:
          - skill: productivity.writing.avoid_ai_writing
            path: skills/productivity/writing/avoid-ai-writing/SKILL.md
            status: CANDIDATE
            anchors: [avoid, writing, audit, rewrite, content]
          - skill: productivity.writing.beautiful_prose
            path: skills/productivity/writing/beautiful-prose/SKILL.md
            status: CANDIDATE
            anchors: [beautiful, prose, hard, edged, writing]
          - skill: productivity.writing.blog_writing_guide
            path: skills/productivity/writing/blog-writing-guide/SKILL.md
            status: CANDIDATE
            anchors: [blog, writing, guide, skill, enforces]
          - skill: productivity.writing.citation_management
            path: skills/productivity/writing/citation-management/SKILL.md
            status: CANDIDATE
            anchors: [citation, management, manage, citations, systematically]
          - skill: productivity.writing.cloudformation_best_practices
            path: skills/productivity/writing/cloudformation-best-practices/SKILL.md
            status: CANDIDATE
            anchors: [cloudformation, best, practices, template, optimization]
          # ... +8 skills adicionais

  SALES:
    path: skills/sales/
    display_name: "Sales"
    skill_count: 26
    anchors: [sales, research, common, room, generate, account, prospect, prep, company, leads, pipeline, call, briefing, person, works]
    sub_domains:
      account-research:
        path: skills/sales/account-research/
        skill_count: 1
        skills:
          - skill: sales.account_research
            path: skills/sales/account-research/SKILL.md
            status: ADOPTED
            anchors: [account, research, company, person, actionable]
      apollo:
        path: skills/sales/apollo/
        skill_count: 4
        skills:
          - skill: sales.apollo.enrich_lead
            path: skills/sales/apollo/enrich-lead/SKILL.md
            status: ADOPTED
            anchors: [enrich, lead, instant, enrichment, drop]
          - skill: sales.apollo.prospect
            path: skills/sales/apollo/prospect/SKILL.md
            status: ADOPTED
            anchors: [prospect, full, leads, pipeline, describe]
          - skill: sales.apollo.sequence_load
            path: skills/sales/apollo/sequence-load/SKILL.md
            status: ADOPTED
            anchors: [sequence, load, find, leads, matching]
          - skill: sales.apollo.skills
            path: skills/sales/apollo/skills/SKILL.md
            status: ADOPTED
            anchors: [sequence, load, find, leads, matching]
      call-prep:
        path: skills/sales/call-prep/
        skill_count: 1
        skills:
          - skill: sales.call_prep
            path: skills/sales/call-prep/SKILL.md
            status: ADOPTED
            anchors: [call, prep, prepare, sales, account]
      call-summary:
        path: skills/sales/call-summary/
        skill_count: 1
        skills:
          - skill: sales.call_summary
            path: skills/sales/call-summary/SKILL.md
            status: ADOPTED
            anchors: [call, summary, process, notes, transcript]
      common-room:
        path: skills/sales/common-room/
        skill_count: 7
        skills:
          - skill: sales.common_room.account_research
            path: skills/sales/common-room/account-research/SKILL.md
            status: ADOPTED
            anchors: [account, research, company, common, room]
          - skill: sales.common_room.call_prep
            path: skills/sales/common-room/call-prep/SKILL.md
            status: ADOPTED
            anchors: [call, prep, prepare, customer, prospect]
          - skill: sales.common_room.compose_outreach
            path: skills/sales/common-room/compose-outreach/SKILL.md
            status: ADOPTED
            anchors: [compose, outreach, generate, personalized, messages]
          - skill: sales.common_room.contact_research
            path: skills/sales/common-room/contact-research/SKILL.md
            status: ADOPTED
            anchors: [contact, research, specific, person, common]
          - skill: sales.common_room.prospect
            path: skills/sales/common-room/prospect/SKILL.md
            status: ADOPTED
            anchors: [prospect, build, targeted, account, contact]
          # ... +2 skills adicionais
      competitive-intelligence:
        path: skills/sales/competitive-intelligence/
        skill_count: 1
        skills:
          - skill: sales.competitive_intelligence
            path: skills/sales/competitive-intelligence/SKILL.md
            status: ADOPTED
            anchors: [competitive, intelligence, research, competitors, build]
      create-an-asset:
        path: skills/sales/create-an-asset/
        skill_count: 1
        skills:
          - skill: sales.create_an_asset
            path: skills/sales/create-an-asset/SKILL.md
            status: ADOPTED
            anchors: [create, asset, generate, tailored, sales]
      crm:
        path: skills/sales/crm/
        skill_count: 1
        skills:
          - skill: sales.crm.hubspot_integration
            path: skills/sales/crm/hubspot-integration/SKILL.md
            status: CANDIDATE
            anchors: [hubspot, integration, expert, patterns, oauth]
      daily-briefing:
        path: skills/sales/daily-briefing/
        skill_count: 1
        skills:
          - skill: sales.daily_briefing
            path: skills/sales/daily-briefing/SKILL.md
            status: ADOPTED
            anchors: [daily, briefing, start, prioritized, sales]
      draft-outreach:
        path: skills/sales/draft-outreach/
        skill_count: 1
        skills:
          - skill: sales.draft_outreach
            path: skills/sales/draft-outreach/SKILL.md
            status: ADOPTED
            anchors: [draft, outreach, research, prospect, then]
      forecast:
        path: skills/sales/forecast/
        skill_count: 1
        skills:
          - skill: sales.forecast
            path: skills/sales/forecast/SKILL.md
            status: ADOPTED
            anchors: [forecast, generate, weighted, sales, best]
      linkedin-cli:
        path: skills/sales/linkedin-cli/
        skill_count: 1
        skills:
          - skill: sales.linkedin_cli
            path: skills/sales/linkedin-cli/SKILL.md
            status: CANDIDATE
            anchors: [linkedin, automating, fetch, profiles, search]
      pipeline-review:
        path: skills/sales/pipeline-review/
        skill_count: 1
        skills:
          - skill: sales.pipeline_review
            path: skills/sales/pipeline-review/SKILL.md
            status: ADOPTED
            anchors: [pipeline, review, analyze, health, prioritize]
      sales-automator:
        path: skills/sales/sales-automator/
        skill_count: 1
        skills:
          - skill: sales.sales_automator
            path: skills/sales/sales-automator/SKILL.md
            status: CANDIDATE
            anchors: [sales, automator, draft, cold, emails]
      sales-enablement:
        path: skills/sales/sales-enablement/
        skill_count: 1
        skills:
          - skill: sales.sales_enablement
            path: skills/sales/sales-enablement/SKILL.md
            status: CANDIDATE
            anchors: [sales, enablement, create, collateral, decks]
      salesforce-development:
        path: skills/sales/salesforce-development/
        skill_count: 1
        skills:
          - skill: sales.salesforce_development
            path: skills/sales/salesforce-development/SKILL.md
            status: CANDIDATE
            anchors: [salesforce, development, expert, patterns, platform]
      skills:
        path: skills/sales/skills/
        skill_count: 1
        skills:
          - skill: sales.skills
            path: skills/sales/skills/SKILL.md
            status: ADOPTED
            anchors: [pipeline, review, analyze, health, prioritize]

  SCIENCE:
    path: skills/science/
    display_name: "Science"
    skill_count: 25
    anchors: [skill, files, data, research, instrument, convert, laboratory, output, bioinformatics, pipelines, rnaseq, sarek, atacseq, scientists, need]
    sub_domains:
      bio-research:
        path: skills/science/bio-research/
        skill_count: 7
        skills:
          - skill: science.bio_research.instrument_data_to_allotrope
            path: skills/science/bio-research/instrument-data-to-allotrope/SKILL.md
            status: ADOPTED
            anchors: [instrument, data, allotrope, convert, laboratory]
          - skill: science.bio_research.nextflow_development
            path: skills/science/bio-research/nextflow-development/SKILL.md
            status: ADOPTED
            anchors: [nextflow, development, core, bioinformatics, pipelines]
          - skill: science.bio_research.scientific_problem_selection
            path: skills/science/bio-research/scientific-problem-selection/SKILL.md
            status: ADOPTED
            anchors: [scientific, problem, selection, skill, scientists]
          - skill: science.bio_research.scvi_tools
            path: skills/science/bio-research/scvi-tools/SKILL.md
            status: ADOPTED
            anchors: [scvi, tools, deep, learning, single]
          - skill: science.bio_research.single_cell_rna_qc
            path: skills/science/bio-research/single-cell-rna-qc/SKILL.md
            status: ADOPTED
            anchors: [single, cell, performs, quality, control]
          # ... +2 skills adicionais
      life-sciences:
        path: skills/science/life-sciences/
        skill_count: 18
        skills:
          - skill: clinical-trial-protocol-skill
            path: skills/science/life-sciences/_source/clinical-trial-protocol-skill/SKILL.md
            status: UNKNOWN
            anchors: [clinical-trial-protocol-skill, generate, clinical, trial, protocols]
          - skill: instrument-data-to-allotrope
            path: skills/science/life-sciences/_source/instrument-data-to-allotrope/SKILL.md
            status: UNKNOWN
            anchors: [instrument-data-to-allotrope, convert, laboratory, instrument, output]
          - skill: nextflow-development
            path: skills/science/life-sciences/_source/nextflow-development/SKILL.md
            status: UNKNOWN
            anchors: [nextflow-development, run, nf-core, bioinformatics, pipelines]
          - skill: scientific-problem-selection
            path: skills/science/life-sciences/_source/scientific-problem-selection/SKILL.md
            status: UNKNOWN
            anchors: [scientific-problem-selection, this, skill, should, when]
          - skill: scvi-tools
            path: skills/science/life-sciences/_source/scvi-tools/SKILL.md
            status: UNKNOWN
            anchors: [scvi-tools, deep, learning, for, single-cell]
          # ... +13 skills adicionais

  SCIENCE_RESEARCH:
    path: skills/science_research/
    display_name: "Science — Research"
    skill_count: 1
    anchors: [wiki, researcher, conducts, multi, turn, iterative, wiki-researcher, multi-turn]
    sub_domains:
      wiki-researcher:
        path: skills/science_research/wiki-researcher/
        skill_count: 1
        skills:
          - skill: science_research.wiki_researcher
            path: skills/science_research/wiki-researcher/SKILL.md
            status: CANDIDATE
            anchors: [wiki, researcher, conducts, multi, turn]

  SECURITY:
    path: skills/security/
    display_name: "Security"
    skill_count: 60
    anchors: [security, expert, comprehensive, specializing, testing, code, analysis, application, review, vulnerability, penetration, audit, threat, practices, provide]
    sub_domains:
      007:
        path: skills/security/007/
        skill_count: 1
        skills:
          - skill: security.007
            path: skills/security/007/SKILL.md
            status: CANDIDATE
            anchors: [security, audit, hardening, threat, modeling]
      anti-reversing-techniques:
        path: skills/security/anti-reversing-techniques/
        skill_count: 1
        skills:
          - skill: security.anti_reversing_techniques
            path: skills/security/anti-reversing-techniques/SKILL.md
            status: CANDIDATE
            anchors: [anti, reversing, techniques, authorized, only]
      antigravity-workflows:
        path: skills/security/antigravity-workflows/
        skill_count: 1
        skills:
          - skill: security.antigravity_workflows
            path: skills/security/antigravity-workflows/SKILL.md
            status: CANDIDATE
            anchors: [antigravity, workflows, orchestrate, multiple, skills]
      api-endpoint-builder:
        path: skills/security/api-endpoint-builder/
        skill_count: 1
        skills:
          - skill: security.api_endpoint_builder
            path: skills/security/api-endpoint-builder/SKILL.md
            status: CANDIDATE
            anchors: [endpoint, builder, builds, production, ready]
      api-security-best-practices:
        path: skills/security/api-security-best-practices/
        skill_count: 1
        skills:
          - skill: security.api_security_best_practices
            path: skills/security/api-security-best-practices/SKILL.md
            status: CANDIDATE
            anchors: [security, best, practices, implement, secure]
      attack-tree-construction:
        path: skills/security/attack-tree-construction/
        skill_count: 1
        skills:
          - skill: security.attack_tree_construction
            path: skills/security/attack-tree-construction/SKILL.md
            status: CANDIDATE
            anchors: [attack, tree, construction, build, comprehensive]
      backend-security-coder:
        path: skills/security/backend-security-coder/
        skill_count: 1
        skills:
          - skill: security.backend_security_coder
            path: skills/security/backend-security-coder/SKILL.md
            status: CANDIDATE
            anchors: [backend, security, coder, expert, secure]
      burp-suite-testing:
        path: skills/security/burp-suite-testing/
        skill_count: 1
        skills:
          - skill: security.burp_suite_testing
            path: skills/security/burp-suite-testing/SKILL.md
            status: CANDIDATE
            anchors: [burp, suite, testing, execute, comprehensive]
      burpsuite-project-parser:
        path: skills/security/burpsuite-project-parser/
        skill_count: 1
        skills:
          - skill: security.burpsuite_project_parser
            path: skills/security/burpsuite-project-parser/SKILL.md
            status: CANDIDATE
            anchors: [burpsuite, project, parser, searches, explores]
      cc-skill-security-review:
        path: skills/security/cc-skill-security-review/
        skill_count: 1
        skills:
          - skill: security.cc_skill_security_review
            path: skills/security/cc-skill-security-review/SKILL.md
            status: CANDIDATE
            anchors: [skill, security, review, ensures, code]
      cicd-automation-workflow-automate:
        path: skills/security/cicd-automation-workflow-automate/
        skill_count: 1
        skills:
          - skill: security.cicd_automation_workflow_automate
            path: skills/security/cicd-automation-workflow-automate/SKILL.md
            status: CANDIDATE
            anchors: [cicd, automation, workflow, automate, expert]
      code-review-checklist:
        path: skills/security/code-review-checklist/
        skill_count: 1
        skills:
          - skill: security.code_review_checklist
            path: skills/security/code-review-checklist/SKILL.md
            status: CANDIDATE
            anchors: [code, review, checklist, comprehensive, conducting]
      codebase-audit-pre-push:
        path: skills/security/codebase-audit-pre-push/
        skill_count: 1
        skills:
          - skill: security.codebase_audit_pre_push
            path: skills/security/codebase-audit-pre-push/SKILL.md
            status: CANDIDATE
            anchors: [codebase, audit, push, deep, before]
      codebase-cleanup-deps-audit:
        path: skills/security/codebase-cleanup-deps-audit/
        skill_count: 1
        skills:
          - skill: security.codebase_cleanup_deps_audit
            path: skills/security/codebase-cleanup-deps-audit/SKILL.md
            status: CANDIDATE
            anchors: [codebase, cleanup, deps, audit, dependency]
      cryptography:
        path: skills/security/cryptography/
        skill_count: 3
        skills:
          - skill: security.cryptography.alpha_vantage
            path: skills/security/cryptography/alpha-vantage/SKILL.md
            status: CANDIDATE
            anchors: [alpha, vantage, access, years, global]
          - skill: security.cryptography.constant_time_analysis
            path: skills/security/cryptography/constant-time-analysis/SKILL.md
            status: CANDIDATE
            anchors: [constant, time, analysis, analyze, cryptographic]
          - skill: security.cryptography.emblemai_crypto_wallet
            path: skills/security/cryptography/emblemai-crypto-wallet/SKILL.md
            status: CANDIDATE
            anchors: [emblemai, crypto, wallet, management, across]
      dependency-management-deps-audit:
        path: skills/security/dependency-management-deps-audit/
        skill_count: 1
        skills:
          - skill: security.dependency_management_deps_audit
            path: skills/security/dependency-management-deps-audit/SKILL.md
            status: CANDIDATE
            anchors: [dependency, management, deps, audit, security]
      differential-review:
        path: skills/security/differential-review/
        skill_count: 1
        skills:
          - skill: security.differential_review
            path: skills/security/differential-review/SKILL.md
            status: CANDIDATE
            anchors: [differential, review, security, focused, code]
      ethical-hacking-methodology:
        path: skills/security/ethical-hacking-methodology/
        skill_count: 1
        skills:
          - skill: security.ethical_hacking_methodology
            path: skills/security/ethical-hacking-methodology/SKILL.md
            status: CANDIDATE
            anchors: [ethical, hacking, methodology, master, complete]
      find-bugs:
        path: skills/security/find-bugs/
        skill_count: 1
        skills:
          - skill: security.find_bugs
            path: skills/security/find-bugs/SKILL.md
            status: CANDIDATE
            anchors: [find, bugs, security, vulnerabilities, code]
      firmware-analyst:
        path: skills/security/firmware-analyst/
        skill_count: 1
        skills:
          - skill: security.firmware_analyst
            path: skills/security/firmware-analyst/SKILL.md
            status: CANDIDATE
            anchors: [firmware, analyst, expert, specializing, embedded]
      gha-security-review:
        path: skills/security/gha-security-review/
        skill_count: 1
        skills:
          - skill: security.gha_security_review
            path: skills/security/gha-security-review/SKILL.md
            status: CANDIDATE
            anchors: [security, review, find, exploitable, vulnerabilities]
      metasploit-framework:
        path: skills/security/metasploit-framework/
        skill_count: 1
        skills:
          - skill: security.metasploit_framework
            path: skills/security/metasploit-framework/SKILL.md
            status: CANDIDATE
            anchors: [metasploit, framework, authorized, only, skill]
      mobile-security-coder:
        path: skills/security/mobile-security-coder/
        skill_count: 1
        skills:
          - skill: security.mobile_security_coder
            path: skills/security/mobile-security-coder/SKILL.md
            status: CANDIDATE
            anchors: [mobile, security, coder, expert, secure]
      network-101:
        path: skills/security/network-101/
        skill_count: 1
        skills:
          - skill: security.network_101
            path: skills/security/network-101/SKILL.md
            status: CANDIDATE
            anchors: [network, configure, test, common, services]
      network-engineer:
        path: skills/security/network-engineer/
        skill_count: 1
        skills:
          - skill: security.network_engineer
            path: skills/security/network-engineer/SKILL.md
            status: CANDIDATE
            anchors: [network, engineer, expert, specializing, modern]
      pci-compliance:
        path: skills/security/pci-compliance/
        skill_count: 1
        skills:
          - skill: security.pci_compliance
            path: skills/security/pci-compliance/SKILL.md
            status: CANDIDATE
            anchors: [compliance, master, payment, card, industry]
      pentest-commands:
        path: skills/security/pentest-commands/
        skill_count: 1
        skills:
          - skill: security.pentest_commands
            path: skills/security/pentest-commands/SKILL.md
            status: CANDIDATE
            anchors: [pentest, commands, provide, comprehensive, command]
      pentesting:
        path: skills/security/pentesting/
        skill_count: 4
        skills:
          - skill: security.pentesting.active_directory_attacks
            path: skills/security/pentesting/active-directory-attacks/SKILL.md
            status: CANDIDATE
            anchors: [active, directory, attacks, provide, comprehensive]
          - skill: security.pentesting.ffuf_web_fuzzing
            path: skills/security/pentesting/ffuf-web-fuzzing/SKILL.md
            status: CANDIDATE
            anchors: [ffuf, fuzzing, expert, guidance, during]
          - skill: security.pentesting.pentest_checklist
            path: skills/security/pentesting/pentest-checklist/SKILL.md
            status: CANDIDATE
            anchors: [pentest, checklist, provide, comprehensive, planning]
          - skill: security.pentesting.windows_privilege_escalation
            path: skills/security/pentesting/windows-privilege-escalation/SKILL.md
            status: CANDIDATE
            anchors: [windows, privilege, escalation, provide, systematic]
      protocol-reverse-engineering:
        path: skills/security/protocol-reverse-engineering/
        skill_count: 1
        skills:
          - skill: security.protocol_reverse_engineering
            path: skills/security/protocol-reverse-engineering/SKILL.md
            status: CANDIDATE
            anchors: [protocol, reverse, engineering, comprehensive, techniques]
      reverse-engineering:
        path: skills/security/reverse-engineering/
        skill_count: 1
        skills:
          - skill: security.reverse_engineering.reverse_engineer
            path: skills/security/reverse-engineering/reverse-engineer/SKILL.md
            status: CANDIDATE
            anchors: [reverse, engineer, expert, specializing, binary]
      sast-configuration:
        path: skills/security/sast-configuration/
        skill_count: 1
        skills:
          - skill: security.sast_configuration
            path: skills/security/sast-configuration/SKILL.md
            status: CANDIDATE
            anchors: [sast, configuration, static, application, security]
      scanning-tools:
        path: skills/security/scanning-tools/
        skill_count: 1
        skills:
          - skill: security.scanning_tools
            path: skills/security/scanning-tools/SKILL.md
            status: CANDIDATE
            anchors: [scanning, tools, master, essential, security]
      security-audit:
        path: skills/security/security-audit/
        skill_count: 1
        skills:
          - skill: security.security_audit
            path: skills/security/security-audit/SKILL.md
            status: CANDIDATE
            anchors: [security, audit, comprehensive, auditing, workflow]
      security-auditor:
        path: skills/security/security-auditor/
        skill_count: 1
        skills:
          - skill: security.security_auditor
            path: skills/security/security-auditor/SKILL.md
            status: CANDIDATE
            anchors: [security, auditor, expert, specializing, devsecops]
      security-bluebook-builder:
        path: skills/security/security-bluebook-builder/
        skill_count: 1
        skills:
          - skill: security.security_bluebook_builder
            path: skills/security/security-bluebook-builder/SKILL.md
            status: CANDIDATE
            anchors: [security, bluebook, builder, build, minimal]
      security-compliance-compliance-check:
        path: skills/security/security-compliance-compliance-check/
        skill_count: 1
        skills:
          - skill: security.security_compliance_compliance_check
            path: skills/security/security-compliance-compliance-check/SKILL.md
            status: CANDIDATE
            anchors: [security, compliance, check, expert, specializing]
      security-requirement-extraction:
        path: skills/security/security-requirement-extraction/
        skill_count: 1
        skills:
          - skill: security.security_requirement_extraction
            path: skills/security/security-requirement-extraction/SKILL.md
            status: CANDIDATE
            anchors: [security, requirement, extraction, derive, requirements]
      security-scanning-security-dependencies:
        path: skills/security/security-scanning-security-dependencies/
        skill_count: 1
        skills:
          - skill: security.security_scanning_security_dependencies
            path: skills/security/security-scanning-security-dependencies/SKILL.md
            status: CANDIDATE
            anchors: [security, scanning, dependencies, expert, specializing]
      security-scanning-security-hardening:
        path: skills/security/security-scanning-security-hardening/
        skill_count: 1
        skills:
          - skill: security.security_scanning_security_hardening
            path: skills/security/security-scanning-security-hardening/SKILL.md
            status: CANDIDATE
            anchors: [security, scanning, hardening, coordinate, multi]
      security-scanning-security-sast:
        path: skills/security/security-scanning-security-sast/
        skill_count: 1
        skills:
          - skill: security.security_scanning_security_sast
            path: skills/security/security-scanning-security-sast/SKILL.md
            status: CANDIDATE
            anchors: [security, scanning, sast, static, application]
      semgrep-rule-creator:
        path: skills/security/semgrep-rule-creator/
        skill_count: 1
        skills:
          - skill: security.semgrep_rule_creator
            path: skills/security/semgrep-rule-creator/SKILL.md
            status: CANDIDATE
            anchors: [semgrep, rule, creator, creates, custom]
      service-mesh-expert:
        path: skills/security/service-mesh-expert/
        skill_count: 1
        skills:
          - skill: security.service_mesh_expert
            path: skills/security/service-mesh-expert/SKILL.md
            status: CANDIDATE
            anchors: [service, mesh, expert, architect, specializing]
      skill-scanner:
        path: skills/security/skill-scanner/
        skill_count: 1
        skills:
          - skill: security.skill_scanner
            path: skills/security/skill-scanner/SKILL.md
            status: CANDIDATE
            anchors: [skill, scanner, scan, agent, skills]
      smtp-penetration-testing:
        path: skills/security/smtp-penetration-testing/
        skill_count: 1
        skills:
          - skill: security.smtp_penetration_testing
            path: skills/security/smtp-penetration-testing/SKILL.md
            status: CANDIDATE
            anchors: [smtp, penetration, testing, conduct, comprehensive]
      solidity-security:
        path: skills/security/solidity-security/
        skill_count: 1
        skills:
          - skill: security.solidity_security
            path: skills/security/solidity-security/SKILL.md
            status: CANDIDATE
            anchors: [solidity, security, master, smart, contract]
      ssh-penetration-testing:
        path: skills/security/ssh-penetration-testing/
        skill_count: 1
        skills:
          - skill: security.ssh_penetration_testing
            path: skills/security/ssh-penetration-testing/SKILL.md
            status: CANDIDATE
            anchors: [penetration, testing, conduct, comprehensive, security]
      stride-analysis-patterns:
        path: skills/security/stride-analysis-patterns/
        skill_count: 1
        skills:
          - skill: security.stride_analysis_patterns
            path: skills/security/stride-analysis-patterns/SKILL.md
            status: CANDIDATE
            anchors: [stride, analysis, patterns, apply, methodology]
      supply-chain-risk-auditor:
        path: skills/security/supply-chain-risk-auditor/
        skill_count: 1
        skills:
          - skill: security.supply_chain_risk_auditor
            path: skills/security/supply-chain-risk-auditor/SKILL.md
            status: CANDIDATE
            anchors: [supply, chain, risk, auditor, identifies]
      threat-mitigation-mapping:
        path: skills/security/threat-mitigation-mapping/
        skill_count: 1
        skills:
          - skill: security.threat_mitigation_mapping
            path: skills/security/threat-mitigation-mapping/SKILL.md
            status: CANDIDATE
            anchors: [threat, mitigation, mapping, identified, threats]
      threat-modeling-expert:
        path: skills/security/threat-modeling-expert/
        skill_count: 1
        skills:
          - skill: security.threat_modeling_expert
            path: skills/security/threat-modeling-expert/SKILL.md
            status: CANDIDATE
            anchors: [threat, modeling, expert, methodologies, security]
      top-web-vulnerabilities:
        path: skills/security/top-web-vulnerabilities/
        skill_count: 1
        skills:
          - skill: security.top_web_vulnerabilities
            path: skills/security/top-web-vulnerabilities/SKILL.md
            status: CANDIDATE
            anchors: [vulnerabilities, provide, comprehensive, structured, reference]
      variant-analysis:
        path: skills/security/variant-analysis/
        skill_count: 1
        skills:
          - skill: security.variant_analysis
            path: skills/security/variant-analysis/SKILL.md
            status: CANDIDATE
            anchors: [variant, analysis, find, similar, vulnerabilities]
      vibers-code-review:
        path: skills/security/vibers-code-review/
        skill_count: 1
        skills:
          - skill: security.vibers_code_review
            path: skills/security/vibers-code-review/SKILL.md
            status: CANDIDATE
            anchors: [vibers, code, review, human, workflow]
      vulnerability-scanner:
        path: skills/security/vulnerability-scanner/
        skill_count: 1
        skills:
          - skill: security.vulnerability_scanner
            path: skills/security/vulnerability-scanner/SKILL.md
            status: CANDIDATE
            anchors: [vulnerability, scanner, advanced, analysis, principles]
      wireshark-analysis:
        path: skills/security/wireshark-analysis/
        skill_count: 1
        skills:
          - skill: security.wireshark_analysis
            path: skills/security/wireshark-analysis/SKILL.md
            status: CANDIDATE
            anchors: [wireshark, analysis, execute, comprehensive, network]

  WEB3:
    path: skills/web3/
    display_name: "Web3"
    skill_count: 14
    anchors: [code, production, ready, web3, smart, documentation, level, context, define, master, blockchain, developer, build, applications, spec]
    sub_domains:
      blockchain:
        path: skills/web3/blockchain/
        skill_count: 2
        skills:
          - skill: web3.blockchain.blockchain_developer
            path: skills/web3/blockchain/blockchain-developer/SKILL.md
            status: CANDIDATE
            anchors: [blockchain, developer, build, production, ready]
          - skill: web3.blockchain.spec_to_code_compliance
            path: skills/web3/blockchain/spec-to-code-compliance/SKILL.md
            status: CANDIDATE
            anchors: [spec, code, compliance, verifies, implements]
      defi:
        path: skills/web3/defi/
        skill_count: 10
        skills:
          - skill: web3.defi.20_andruia_niche_intelligence
            path: skills/web3/defi/20-andruia-niche-intelligence/SKILL.md
            status: CANDIDATE
            anchors: [andruia, niche, intelligence, estratega, inteligencia]
          - skill: web3.defi.c4_component
            path: skills/web3/defi/c4-component/SKILL.md
            status: CANDIDATE
            anchors: [component, expert, level, documentation, specialist]
          - skill: web3.defi.context_fundamentals
            path: skills/web3/defi/context-fundamentals/SKILL.md
            status: CANDIDATE
            anchors: [context, fundamentals, complete, state, available]
          - skill: web3.defi.ddd_context_mapping
            path: skills/web3/defi/ddd-context-mapping/SKILL.md
            status: CANDIDATE
            anchors: [context, mapping, relationships, between, bounded]
          - skill: web3.defi.defi_protocol_templates
            path: skills/web3/defi/defi-protocol-templates/SKILL.md
            status: CANDIDATE
            anchors: [defi, protocol, templates, implement, protocols]
          # ... +5 skills adicionais
      nft:
        path: skills/web3/nft/
        skill_count: 1
        skills:
          - skill: web3.nft.nft_standards
            path: skills/web3/nft/nft-standards/SKILL.md
            status: CANDIDATE
            anchors: [standards, master, metadata, best, practices]
      web3-testing:
        path: skills/web3/web3-testing/
        skill_count: 1
        skills:
          - skill: web3.web3_testing
            path: skills/web3/web3-testing/SKILL.md
            status: CANDIDATE
            anchors: [web3, testing, master, comprehensive, strategies]

```

---

## Estatísticas de Geração

**Por Status:**
- CANDIDATE: 1979 (52.6%)
- UNKNOWN: 1531 (40.7%)
- ADOPTED: 251 (6.7%)

**Por Tier:**
- ADAPTED: 2526 (67.2%)
- IMPORTED: 1174 (31.2%)
- COMMUNITY: 37 (1.0%)
- 2: 23 (0.6%)
- STANDARD: 1 (0.0%)

**Top 10 Domínios por Quantidade de Skills:**
1. Integrations: 841 skills
2. Engineering (Core): 596 skills
3. Community: 414 skills
4. AI & Machine Learning: 286 skills
5. Knowledge Work: 248 skills
6. Finance: 191 skills
7. Engineering — Cloud Azure: 161 skills
8. Business: 159 skills
9. Marketing: 137 skills
10. Design: 73 skills

---

*Gerado por `tools/generate_index.py` — APEX v00.36.0 — 2026-04-17 21:25 UTC*