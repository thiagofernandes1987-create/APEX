---
skill_id: integrations.tavily.tavily_web
name: "tavily-web"
description: "'Web search, content extraction, crawling, and research capabilities using Tavily API. Use when you need to search the web for current information, extracting content from URLs, or crawling websites.'"
version: v00.33.0
status: CANDIDATE
domain_path: integrations/tavily/tavily-web
anchors:
  - tavily
  - search
  - content
  - extraction
  - crawling
  - research
  - capabilities
  - need
  - current
  - information
source_repo: antigravity-awesome-skills
risk: safe
languages: [dsl]
llm_compat: {claude: full, gpt4o: partial, gemini: partial, llama: minimal}
apex_version: v00.33.0
---

# tavily-web

## Overview
Web search, content extraction, crawling, and research capabilities using Tavily API

## When to Use
- When you need to search the web for current information
- When extracting content from URLs
- When crawling websites

## Installation
```bash
npx skills add -g BenedictKing/tavily-web
```

## Step-by-Step Guide
1. Install the skill using the command above
2. Configure Tavily API key
3. Use naturally in Claude Code conversations

## Examples
See [GitHub Repository](https://github.com/BenedictKing/tavily-web) for examples.

## Best Practices
- Configure API keys via environment variables

## Troubleshooting
See the GitHub repository for troubleshooting guides.

## Related Skills
- context7-auto-research, exa-search, firecrawl-scraper, codex-review

## Diff History
- **v00.33.0**: Ingested from antigravity-awesome-skills community repo
