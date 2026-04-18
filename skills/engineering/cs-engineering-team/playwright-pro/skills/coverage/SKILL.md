---
name: "coverage"
description: >-
  Analyze test coverage gaps. Use when user says "test coverage",
  "what's not tested", "coverage gaps", "missing tests", "coverage report",
  or "what needs testing".
executor: LLM_BEHAVIOR
skill_id: engineering.cs_engineering_team.playwright_pro.coverage
status: ADOPTED
security: {level: standard, pii: false, approval_required: false}
anchors:
  - engineering
  - testing
tier: 2
input_schema:
  - name: code_or_task
    type: string
    description: "Code snippet, script, or task description to process"
    required: true
output_schema:
  - name: report
    type: string
    description: "Analysis report or summary from coverage"
---

# Analyze Test Coverage Gaps

Map all testable surfaces in the application and identify what's tested vs. what's missing.

## Steps

### 1. Map Application Surface

Use the `Explore` subagent to catalog:

**Routes/Pages:**
- Scan route definitions (Next.js `app/`, React Router config, Vue Router, etc.)
- List all user-facing pages with their paths

**Components:**
- Identify interactive components (forms, modals, dropdowns, tables)
- Note components with complex state logic

**API Endpoints:**
- Scan API route files or backend controllers
- List all endpoints with their methods

**User Flows:**
- Identify critical paths: auth, checkout, onboarding, core features
- Map multi-step workflows

### 2. Map Existing Tests

Scan all `*.spec.ts` / `*.spec.js` files:

- Extract which pages/routes are covered (by `page.goto()` calls)
- Extract which components are tested (by locator usage)
- Extract which API endpoints are mocked or hit
- Count tests per area

### 3. Generate Coverage Matrix

```
## Coverage Matrix

| Area | Route | Tests | Status |
|---|---|---|---|
| Auth | /login | 5 | ✅ Covered |
| Auth | /register | 0 | ❌ Missing |
| Auth | /forgot-password | 0 | ❌ Missing |
| Dashboard | /dashboard | 3 | ⚠️ Partial (no error states) |
| Settings | /settings | 0 | ❌ Missing |
| Checkout | /checkout | 8 | ✅ Covered |
```

### 4. Prioritize Gaps

Rank uncovered areas by business impact:

1. **Critical** — auth, payment, core features → test first
2. **High** — user-facing CRUD, search, navigation
3. **Medium** — settings, preferences, edge cases
4. **Low** — static pages, about, terms

### 5. Suggest Test Plan

For each gap, recommend:
- Number of tests needed
- Which template from `templates/` to use
- Estimated effort (quick/medium/complex)

```
## Recommended Test Plan

### Priority 1: Critical
1. /register (4 tests) — use auth/registration template — quick
2. /forgot-password (3 tests) — use auth/password-reset template — quick

### Priority 2: High
3. /settings (4 tests) — use settings/ templates — medium
4. Dashboard error states (2 tests) — use dashboard/data-loading template — quick
```

### 6. Auto-Generate (Optional)

Ask user: "Generate tests for the top N gaps? [Yes/No/Pick specific]"

If yes, invoke `/pw:generate` for each gap with the recommended template.

## Output

- Coverage matrix (table format)
- Coverage percentage estimate
- Prioritized gap list with effort estimates
- Option to auto-generate missing tests

---

## Why This Skill Exists

Analyze test coverage gaps.

<!-- SR_40: auto-generated from frontmatter `purpose`/`description` (OPP-Phase3). Expand with domain-specific rationale. -->

## When to Use

Use this skill when user says "test coverage",

<!-- SR_40: auto-generated from frontmatter `when`/`description` (OPP-Phase3). -->

## What If Fails

If this skill fails to produce the expected output: (1) verify input completeness, (2) retry with more specific context, (3) fall back to the parent workflow without this skill.

<!-- SR_40: auto-generated from frontmatter `what_if_fails` (OPP-Phase3). -->
