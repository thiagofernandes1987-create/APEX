---
skill_id: integrations.legal.mcp_catalog
name: "Legal MCP Server Catalog -- CourtListener, USPTO, SEC, GovInfo, Congress"
description: "Comprehensive legal research MCP servers: GovInfo (official GPO), CourtListener case law, USPTO patents (52 tools), SEC EDGAR filings, Congress.gov, Federal Register, US Law mega-server (40+ gov APIs)."
version: v00.33.0
status: ADOPTED
domain_path: integrations/legal-mcp
anchors:
  - legal
  - case_law
  - patents
  - sec_edgar
  - federal_register
  - congress
  - govinfo
  - courtlistener
  - uspto
  - compliance
  - regulation
source_repo: community-research
risk: safe
languages: [python, typescript]
llm_compat: {claude: full, gpt4o: full, gemini: full, llama: partial}
apex_version: v00.33.0
---

# Legal MCP Server Catalog

## Official / Institutional Servers

| Server | Endpoint/Repo | Coverage | Auth |
|--------|--------------|----------|------|
| GovInfo (GPO — official) | https://api.govinfo.gov/mcp | Federal Register, CFR, Congressional Records, Court Opinions, entire GPO corpus | Free API key |
| CourtListener (DefendTheDisabled) | github.com/DefendTheDisabled/courtlistener-mcp | Case law, opinions, dockets, semantic search (12 tools) | CourtListener API key |
| CourtListener + eCFR | github.com/Travis-Prall/court-listener-mcp | CourtListener + Electronic Code of Federal Regulations | API key |
| USPTO Patents (52 tools) | github.com/riemannzeta/patent_mcp_server | Patent Public Search, PTAB, Litigation, File Wrapper, Final Petition Decisions | Free |
| SEC EDGAR | github.com/stefanoamorelli/sec-edgar-mcp | Company filings, financials, insider trading, 8-K/10-K/10-Q | Free |
| Congress.gov | github.com/bsmi021/mcp-congress_gov_server | Bills, votes, members, legislative history | Congress.gov API key |
| Federal Register | github.com/aml25/federal-register-mcp | Executive orders, rules, federal documents | Free, no auth |
| US Legal (unified) | github.com/JamesANZ/us-legal-mcp | Congress + Federal Register + CourtListener | Multiple |
| US Law (130 statutes) | github.com/Ansvar-Systems/US-law-mcp | eCFR + USC validated statutes | Free |
| US Gov Mega (250+ tools) | github.com/lzinga/us-gov-open-data-mcp | Treasury, FRED, FDA, CDC, FEC, lobbying, 40+ APIs | Free |

## Activation Anchors

`legal`, `case_law`, `patents`, `contract_review`, `compliance`, `regulation`,
`sec_edgar`, `federal_register`, `congress`, `govinfo`, `courtlistener`, `uspto`

## APEX Use Cases

- Contract review → `legal` anchor → knowledge-work/legal plugin + CourtListener
- Patent research → `patents` anchor → USPTO Patents MCP (52 tools)
- Regulatory compliance → `regulation` anchor → GovInfo + Federal Register
- Financial filings → `sec_edgar` anchor → SEC EDGAR MCP
- Legislative tracking → `congress` anchor → Congress.gov MCP

## Diff History
- **v00.33.0**: Cataloged from community research — all verified functional as of 2026-04