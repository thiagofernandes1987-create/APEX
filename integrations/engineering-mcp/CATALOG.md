---
skill_id: integrations.engineering.mcp_catalog
name: "Engineering MCP Catalog -- NASA, OpenFOAM, OpenSCAD, GitHub, PagerDuty, Datadog"
description: "Engineering workflow MCP servers: NASA APIs (20+), NASA Earthdata, OpenFOAM CFD, OpenSCAD CAD, plus DevOps: GitHub, PagerDuty, Datadog, Atlassian."
version: v00.33.0
status: ADOPTED
domain_path: integrations/engineering-mcp
anchors:
  - engineering
  - nasa
  - cfd
  - cad
  - simulation
  - devops
  - github
  - pagerduty
  - datadog
  - space
source_repo: community-research
risk: safe
languages: [python, go, cpp]
llm_compat: {claude: full, gpt4o: full, gemini: full, llama: partial}
apex_version: v00.33.0
---

# Engineering MCP Catalog

## Scientific & Space Engineering

| Server | Repo | Coverage |
|--------|------|---------|
| NASA (20+ APIs) | github.com/ProgramComputer/NASA-MCP-server | APOD, Mars Rovers, Near Earth Objects, DONKI space weather, FIRMS fires, Exoplanets, JPL Solar System |
| NASA Earthdata (official) | github.com/nasa/earthdata-mcp | Earth science data semantic search and retrieval |

## Simulation & CAD

| Server | Repo | Coverage |
|--------|------|---------|
| OpenFOAM CFD | github.com/webworn/openfoam-mcp-server | Computational fluid dynamics, AI-guided error resolution, Socratic debugging |
| OpenFOAM (config) | github.com/ymg2007/openfoam-mcp | Boundary conditions, parameter management |
| OpenSCAD (3D CAD) | github.com/fboldo/openscad-mcp-server | Parametric 3D modeling, STL + PNG rendering, agentic CAD |

## DevOps & Monitoring (from knowledge-work ZIPs)

| Server | URL | Coverage |
|--------|-----|---------|
| GitHub | https://api.github.com/mcp | Repos, PRs, issues, actions, code search |
| PagerDuty | https://mcp.pagerduty.com/mcp | Incident management, on-call schedules, alerts |
| Datadog | https://mcp.datadoghq.com/mcp | Metrics, logs, traces, APM, dashboards |
| Linear | https://mcp.linear.app/mcp | Issue tracking, project management |
| Atlassian | https://mcp.atlassian.com/v1/mcp | Jira, Confluence, project tracking |
| ServiceNow | https://mcp.servicenow.com/mcp | ITSM, change management, CMDB |

## Diff History
- **v00.33.0**: Cataloged from knowledge-work ZIPs + community research — 2026-04