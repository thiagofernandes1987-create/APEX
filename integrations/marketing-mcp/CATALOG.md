---
skill_id: integrations.marketing.mcp_catalog
name: "Marketing MCP Catalog -- Semrush, Google Ads, Meta, TikTok, LinkedIn, HubSpot"
description: "Full marketing stack MCP servers: Semrush (official), Google Ads (official), Meta Ads, TikTok Ads, LinkedIn Ads, HubSpot, Amplitude analytics, Ahrefs SEO, Klaviyo email, Canva design, all-in-one ads manager (100+ tools)."
version: v00.33.0
status: ADOPTED
domain_path: integrations/marketing-mcp
anchors:
  - marketing
  - seo
  - paid_ads
  - google_ads
  - meta_ads
  - tiktok_ads
  - linkedin_ads
  - semrush
  - hubspot
  - email_marketing
  - analytics
  - content_marketing
source_repo: community-research
risk: safe
languages: [dsl, python, typescript]
llm_compat: {claude: full, gpt4o: full, gemini: full, llama: partial}
apex_version: v00.33.0
---

# Marketing MCP Catalog

## SEO & Web Analytics

| Server | URL/Repo | Tools | Auth |
|--------|---------|-------|------|
| Semrush (official) | https://mcp.semrush.com/v1/mcp | Keyword rankings, traffic analysis, backlinks, domain analytics, competitive intel | API key |
| Ahrefs | https://api.ahrefs.com/mcp/mcp | SEO data, backlink analysis, keyword research | API key |
| SimilarWeb | https://mcp.similarweb.com | Web traffic intelligence, audience insights | API key |
| Supermetrics | https://mcp.supermetrics.com/mcp | Cross-channel marketing data aggregation | Auth |

## Paid Advertising

| Server | Repo | Coverage | Auth |
|--------|------|---------|------|
| Google Ads (official) | github.com/googleads/google-ads-mcp | Search, Display, Shopping campaigns, performance, bidding | Google OAuth |
| Meta Ads (pipeboard) | github.com/pipeboard-co/meta-ads-mcp | Facebook + Instagram campaigns, creatives, performance | pipeboard.co OAuth |
| Meta Ads (24 tools) | github.com/hashcott/meta-ads-mcp-server | Graph API v22.0, full campaign lifecycle | Meta API token |
| TikTok Ads | github.com/AdsMCP/tiktok-ads-mcp-server | TikTok Business API, campaigns, ad groups, performance | TikTok API |
| LinkedIn Ads | github.com/radiateb2b/mcp-linkedin-ads | Campaign performance, benchmarks, optimization | LinkedIn OAuth |
| All-in-One Ads (100+ tools) | github.com/amekala/ads-mcp | Google + Meta + LinkedIn + TikTok simultaneously | Multiple |

## CRM & Marketing Automation

| Server | URL | Coverage |
|--------|-----|---------|
| HubSpot | https://mcp.hubspot.com/anthropic | CRM, contacts, deals, campaigns, email | HubSpot API |
| Klaviyo | https://mcp.klaviyo.com/mcp | Email + SMS marketing, flows, segmentation | Klaviyo API |
| Apollo | https://mcp.apollo.io/mcp | Sales intelligence + outreach | Apollo API |
| Common Room | https://mcp.commonroom.io/mcp | GTM intelligence, account research | Common Room |

## Analytics & Product

| Server | URL | Coverage |
|--------|-----|---------|
| Amplitude | https://mcp.amplitude.com/mcp | Product analytics, user behavior, funnels | Amplitude API |
| Pendo | https://app.pendo.io/mcp/v0/shttp | Product usage, NPS, feature adoption | Pendo API |

## Design & Content

| Server | URL | Coverage |
|--------|-----|---------|
| Canva | https://mcp.canva.com/mcp | Design creation, brand templates | Canva API |
| Figma | https://mcp.figma.com/mcp | Design files, components, prototypes | Figma API |

## Diff History
- **v00.33.0**: Cataloged from knowledge-work ZIPs + community research — 2026-04