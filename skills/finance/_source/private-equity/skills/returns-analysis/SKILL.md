---
executor: LLM_BEHAVIOR
skill_id: finance.private_equity.returns_analysis_3
status: ADOPTED
security: {level: high, pii: true, approval_required: true}
anchors:
  - finance
  - testing
  - ai_ml
  - design
tier: 2
input_schema:
  - name: code_or_task
    type: string
    description: "Code snippet, script, or task description to process"
    required: true
output_schema:
  - name: report
    type: string
    description: "Analysis report or summary from returns analysis"
---
# Returns Analysis

description: Build quick IRR/MOIC sensitivity tables for PE deal evaluation. Models returns across entry multiple, leverage, exit multiple, growth, and hold period scenarios. Use when sizing up a deal, stress-testing assumptions, or preparing IC returns exhibits. Triggers on "returns analysis", "IRR sensitivity", "MOIC table", "what's the return at", "model the returns", or "back of the envelope".

## Workflow

### Step 1: Gather Deal Inputs

Ask for (or extract from prior analysis):

**Entry:**
- Entry EBITDA (LTM or NTM)
- Entry multiple (EV / EBITDA)
- Enterprise value
- Net debt at close
- Equity check size
- Transaction fees & expenses

**Financing:**
- Senior debt (x EBITDA, rate, amortization)
- Subordinated debt / mezzanine (if any)
- Total leverage at entry (x EBITDA)
- Equity contribution

**Operating Assumptions:**
- Revenue growth rate (annual)
- EBITDA margin trajectory
- Capex as % of revenue
- Working capital changes
- Debt paydown schedule

**Exit:**
- Hold period (years)
- Exit multiple (EV / EBITDA)
- Exit EBITDA (calculated from growth assumptions)

### Step 2: Base Case Returns

Calculate:

| Metric | Value |
|--------|-------|
| Entry EV | |
| Equity invested | |
| Exit EBITDA | |
| Exit EV | |
| Net debt at exit | |
| Exit equity value | |
| **MOIC** | |
| **IRR** | |
| Cash-on-cash | |

Show the returns waterfall:
- EBITDA growth contribution
- Multiple expansion/contraction contribution
- Debt paydown contribution
- Fee/expense drag

### Step 3: Sensitivity Tables

Build 2-way sensitivity matrices:

**Entry Multiple vs. Exit Multiple**
| | Exit 6x | Exit 7x | Exit 8x | Exit 9x | Exit 10x |
|---|---------|---------|---------|---------|----------|
| Entry 7x | | | | | |
| Entry 8x | | | | | |
| Entry 9x | | | | | |
| Entry 10x | | | | | |

**EBITDA Growth vs. Exit Multiple** (at fixed entry)

**Leverage vs. Exit Multiple** (at fixed entry and growth)

**Hold Period vs. Exit Multiple**

Show both IRR and MOIC in each cell (IRR / MOIC format).

### Step 4: Scenario Analysis

Build 3 scenarios:

| | Bull | Base | Bear |
|---|------|------|------|
| Revenue CAGR | | | |
| Exit EBITDA margin | | | |
| Exit multiple | | | |
| Exit EBITDA | | | |
| MOIC | | | |
| IRR | | | |

### Step 5: Output

- Excel workbook with:
  - Assumptions tab
  - Returns calculation
  - Sensitivity tables (formatted with conditional coloring)
  - Scenario summary
- One-page returns summary suitable for IC deck

## Key Formulas

- **MOIC** = Exit Equity Value / Equity Invested
- **IRR** = solve for r: Equity Invested × (1 + r)^n = Exit Equity Value (adjust for interim cash flows)
- **Returns attribution**:
  - Growth: (Exit EBITDA - Entry EBITDA) × Exit Multiple / Equity
  - Multiple: (Exit Multiple - Entry Multiple) × Entry EBITDA / Equity
  - Leverage: Debt paydown over hold period / Equity

## Important Notes

- Always show returns both gross and net of fees/carry where applicable
- Management rollover and co-invest change the equity check — ask if relevant
- Dividend recaps or interim distributions affect IRR significantly — include if planned
- Don't forget transaction costs (typically 2-4% of EV) — they reduce Day 1 equity value
- Tax considerations (asset vs. stock deal, 338(h)(10) election) can materially affect after-tax returns

---

## Why This Skill Exists

Build quick IRR/MOIC sensitivity tables for PE deal evaluation. Models returns across entry multiple, leverage, exit multiple, growth, and hold period scenarios.

<!-- SR_40: auto-generated from frontmatter `purpose`/`description` (OPP-Phase3). Expand with domain-specific rationale. -->

## When to Use

Use this skill when sizing up a deal, stress-testing assumptions, or preparing IC returns exhibits

<!-- SR_40: auto-generated from frontmatter `when`/`description` (OPP-Phase3). -->

## What If Fails

If this skill fails to produce the expected output: (1) verify input completeness, (2) retry with more specific context, (3) fall back to the parent workflow without this skill.

<!-- SR_40: auto-generated from frontmatter `what_if_fails` (OPP-Phase3). -->
