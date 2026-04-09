---
skill_id: engineering_cli.shodan
name: "shodan"
description: ""
version: v00.33.0
status: CANDIDATE
domain_path: engineering/cli
anchors:
  - shodan
source_repo: x-cmd
risk: safe
languages: [dsl]
llm_compat: {claude: full, gpt4o: partial, gemini: partial, llama: minimal}
apex_version: v00.33.0
---

---
name: x-shodan
description: |
  Shodan CLI for searching Internet-connected devices.
  Host intel, DNS tools, network scanning, alerts.
  
  **Dependency**: This is an x-cmd module. Install x-cmd first (see x-cmd skill for installation options).
  see x-cmd skill for installation.

## Prerequisites

| Requirement | Purpose | Notes |
|-------------|---------|-------|
| x-cmd | Required module runtime | `brew install x-cmd` |
| Shodan API key | Access Shodan API | Set via `x shodan init <key>` |


license: Apache-2.0
compatibility: POSIX Shell

metadata:
  author: Li Junhao
  version: "1.0.0"
  category: x-cmd-extension
  tags: [x-cmd, security, shodan, reconnaissance, network]

## Diff History
- **v00.33.0**: Ingested from x-cmd