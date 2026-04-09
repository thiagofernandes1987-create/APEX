---
skill_id: engineering_cli.scorecard
name: "scorecard"
description: ""
version: v00.33.0
status: CANDIDATE
domain_path: engineering/cli
anchors:
  - scorecard
source_repo: x-cmd
risk: safe
languages: [dsl]
llm_compat: {claude: full, gpt4o: partial, gemini: partial, llama: minimal}
apex_version: v00.33.0
---

---
name: x-scorecard
description: |
  OpenSSF Scorecard for assessing open source project security.
  Check security best practices and compliance.
  
  **Dependency**: This is an x-cmd module. Install x-cmd first (see x-cmd skill for installation options).
  see x-cmd skill for installation.

## Prerequisites

| Tool | Purpose | Install |
|------|---------|---------|
| x-cmd | Required module runtime | `brew install x-cmd` |


license: Apache-2.0
compatibility: POSIX Shell

metadata:
  author: Li Junhao
  version: "1.0.0"
  category: x-cmd-extension
  tags: [x-cmd, security, scorecard, openssf, audit]

## Diff History
- **v00.33.0**: Ingested from x-cmd