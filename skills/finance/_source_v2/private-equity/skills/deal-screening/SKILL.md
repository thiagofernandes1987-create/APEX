---
executor: LLM_BEHAVIOR
skill_id: finance.private_equity.deal_screening_2
status: ADOPTED
security: {level: high, pii: true, approval_required: true}
anchors:
  - finance
  - design
tier: 2
input_schema:
  - name: code_or_task
    type: string
    description: "Code snippet, script, or task description to process"
    required: true
output_schema:
  - name: plan
    type: string
    description: "Strategic plan or design document"
  - name: next_steps
    type: array
    description: "List of recommended next steps"
---
# Deal Screening

description: "Analyze — Quickly screen inbound deal flow — CIMs, teasers, and broker materials — against the fund's investment criteria. Extracts key deal metrics, runs a pass/fail framework, and outputs "
## Workflow

### Step 1: Extract Deal Facts

From the provided CIM, teaser, or description, extract:

- **Company**: Name, location, sector/subsector
- **Description**: What they do (1-2 sentences)
- **Financials**: Revenue, EBITDA, margins, growth rate
- **Deal type**: Platform, add-on, recap, minority, carve-out
- **Asking price / valuation**: Multiple, enterprise value if stated
- **Seller motivation**: Why selling now
- **Management**: Rolling or exiting
- **Key customers**: Concentration risk
- **Key risks**: Obvious red flags

### Step 2: Screen Against Criteria

Apply the fund's investment criteria (ask user if not known):

| Criterion | Target | Actual | Pass/Fail |
|-----------|--------|--------|-----------|
| Revenue range | | | |
| EBITDA range | | | |
| EBITDA margin | | | |
| Growth profile | | | |
| Sector fit | | | |
| Geography | | | |
| Deal size / EV | | | |
| Valuation (x EBITDA) | | | |
| Customer concentration | | | |
| Management continuity | | | |

### Step 3: Quick Assessment

Provide a 3-part assessment:

1. **Verdict**: Pass / Further Diligence / Hard Pass
2. **Bull case** (2-3 bullets): Why this could be a good deal
3. **Bear case** (2-3 bullets): Key risks and concerns
4. **Key questions**: What you'd need to answer on a first call

### Step 4: Output

One-page screening memo suitable for sharing with partners or an IC quick screen.

## Important Notes

- Speed matters — screening should take minutes, not hours
- Be direct about red flags. Don't bury concerns
- If financials seem inconsistent or incomplete, flag it explicitly
- Ask for the fund's criteria upfront if this is the first screening
- Save screening criteria in memory for future deals once confirmed

---

## Why This Skill Exists

Analyze — Quickly screen inbound deal flow — CIMs, teasers, and broker materials — against the fund

<!-- SR_40: auto-generated from frontmatter `purpose`/`description` (OPP-Phase3). Expand with domain-specific rationale. -->

## When to Use

Use this skill when the task requires deal screening capabilities.

<!-- SR_40: auto-generated from frontmatter `when`/`description` (OPP-Phase3). -->

## What If Fails

If this skill fails to produce the expected output: (1) verify input completeness, (2) retry with more specific context, (3) fall back to the parent workflow without this skill.

<!-- SR_40: auto-generated from frontmatter `what_if_fails` (OPP-Phase3). -->
