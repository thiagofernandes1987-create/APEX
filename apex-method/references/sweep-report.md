# skills.sh sweep — reusable scripts, algorithms & agents

Swept the top skills.sh repos by install count, cloned each, and inventoried what ships
**real executable value**. Machine-readable in `catalog/algorithms_map.json`. Safety uses
APEX's two-tier scanner: **reject** = RCE vector (block); **review** = often benign
(list.remove, dataclass vars, third-party imports) — inspect before adopting.

## Inventory (cloned & counted)

| Repo | SKILL.md | scripts | script LOC | verdict |
|------|---------:|--------:|-----------:|---------|
| agiprolabs/claude-trading-skills | 67 | 119 py | 58,738 | algorithm trove (crypto/quant) |
| vercel-labs/agent-skills | 9 | 163 ts | 28,809 | frontend best-practices + helpers |
| gauss314/skills | 32 | 74 py | 24,566 | **finance algorithms (highest signal)** |
| firecrawl/cli | 10 | 79 ts | 22,333 | web-data extraction tools |
| vercel-labs/skills | 1 | 78 js | 20,930 | the `npx skills` CLI itself |
| anthropics/skills | 18 | 75 | 14,950 | **official doc + skill tooling** |
| wshobson/agents | 162 | 62 | 14,111 | **domain agents + patterns** |
| obra/superpowers | 14 | 52 | 10,180 | **agent workflows** |
| mattpocock/skills | 39 | 5 | 340 | mostly text workflows |
| supabase/agent-skills | 2 | 3 | 262 | mostly text |

## Significant-gain findings, mapped to APEX agents

### Algorithms → Finance Analyst / Scientist
- **gauss314/skills** — the strongest algorithmic haul. `option_pricing.py` implements
  Black-Scholes, Binomial (CRR), Trinomial, Monte Carlo (antithetic), Longstaff-Schwartz,
  Bjerksund-Stensland/BAW, Heston, Bates, full greeks and implied vol — all confirmed present,
  flat numpy+scipy (zero finance libs), so directly portable. Plus portfolio optimization
  (Markowitz/HRP/HERC/NCO/Black-Litterman), risk measures (VaR/CVaR/CDaR/MAD/max-drawdown),
  covariance estimators (Ledoit-Wolf/OAS/EWMA), 30+ backtest ratios, 10 indicator classes.
  Scanner: **safe=True, review-only.**
- **agiprolabs/claude-trading-skills** — 58.7K LOC: crypto indicators, MEV sandwich detection
  & risk estimation, DEX pool analysis, trade ledger/journal analytics, tax export. Network
  scripts need key/rate review.

### Scripts & tooling → Software Engineer
- **anthropics/skills** — official, highest-trust: docx/pptx/xlsx/pdf generation + validators;
  `skill-creator` ships `package_skill.py`, `generate_review.py`, `run_loop.py` (a real skill
  optimization loop); `mcp-builder`; `webapp-testing`. These are the gold-standard reusable tools.
- **firecrawl/cli** — scrape/crawl/map/search/parse/extract/monitor (structured web extraction).
  Network tools; not for the sandbox allowlist.
- **vercel-labs/agent-skills** — React/Next best-practices, composition patterns, deploy-to-vercel.

### Agents & orchestration → Controller / Mediator / Chaos
- **obra/superpowers** — the closest thing to reusable "agents": `dispatching-parallel-agents`
  and `subagent-driven-development` (orchestration), `brainstorming` (→ chaos stance),
  `writing-plans`/`executing-plans` (→ pmi_pm), `systematic-debugging`, `verification-before-
  completion`, `using-git-worktrees`. Text workflows + 37 shell helpers (review shell first).
- **wshobson/agents** — 162 skills as plugins: security-scanning (STRIDE, attack-tree, SAST),
  ML-ops (recsys/ml-pipeline → data_ml), data-engineering (dbt/spark/airflow), python patterns,
  database-design, startup-business-analyst (market-sizing, financial-modeling → enterprise_strategist).

### Ecosystem tooling → Controller
- **vercel-labs/skills** — the `npx skills` find/install CLI (1.4M installs). Used to install
  skills, not embedded.

## Honest caveats
- The APEX scanner **over-flagged** every finance script on the first pass (vars(), list.remove,
  __future__, argparse). That was a false-positive problem, now fixed with the reject/review split
  — real attacks (os.system/eval/pickle.loads/__import__) still hard-block.
- "Significant gains" concentrate in a **minority** of repos that ship real code (gauss314,
  agiprolabs, anthropics, firecrawl, wshobson). Many top skills.sh repos are text/persona only.
- Adopt any external script only after review + user approval (APEX H5). Nothing is auto-run.
