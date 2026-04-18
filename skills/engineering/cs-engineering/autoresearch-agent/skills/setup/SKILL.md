---
name: "setup"
description: "Set up a new autoresearch experiment interactively. Collects domain, target file, eval command, metric, direction, and evaluator."
command: /ar:setup
executor: LLM_BEHAVIOR
skill_id: engineering.cs_engineering.autoresearch_agent.setup
status: ADOPTED
security: {level: standard, pii: false, approval_required: false}
anchors:
  - engineering
  - research
tier: 2
input_schema:
  - name: code_or_task
    type: string
    description: "Code snippet, script, or task description to process"
    required: true
  - name: context
    type: string
    description: "Additional context or background information"
    required: false
output_schema:
  - name: result
    type: string
    description: "Primary output from setup"
---

# /ar:setup — Create New Experiment

Set up a new autoresearch experiment with all required configuration.

## Usage

```
/ar:setup                                    # Interactive mode
/ar:setup engineering api-speed src/api.py "pytest bench.py" p50_ms lower
/ar:setup --list                             # Show existing experiments
/ar:setup --list-evaluators                  # Show available evaluators
```

## What It Does

### If arguments provided

Pass them directly to the setup script:

```bash
python {skill_path}/scripts/setup_experiment.py \
  --domain {domain} --name {name} \
  --target {target} --eval "{eval_cmd}" \
  --metric {metric} --direction {direction} \
  [--evaluator {evaluator}] [--scope {scope}]
```

### If no arguments (interactive mode)

Collect each parameter one at a time:

1. **Domain** — Ask: "What domain? (engineering, marketing, content, prompts, custom)"
2. **Name** — Ask: "Experiment name? (e.g., api-speed, blog-titles)"
3. **Target file** — Ask: "Which file to optimize?" Verify it exists.
4. **Eval command** — Ask: "How to measure it? (e.g., pytest bench.py, python evaluate.py)"
5. **Metric** — Ask: "What metric does the eval output? (e.g., p50_ms, ctr_score)"
6. **Direction** — Ask: "Is lower or higher better?"
7. **Evaluator** (optional) — Show built-in evaluators. Ask: "Use a built-in evaluator, or your own?"
8. **Scope** — Ask: "Store in project (.autoresearch/) or user (~/.autoresearch/)?"

Then run `setup_experiment.py` with the collected parameters.

### Listing

```bash
# Show existing experiments
python {skill_path}/scripts/setup_experiment.py --list

# Show available evaluators
python {skill_path}/scripts/setup_experiment.py --list-evaluators
```

## Built-in Evaluators

| Name | Metric | Use Case |
|------|--------|----------|
| `benchmark_speed` | `p50_ms` (lower) | Function/API execution time |
| `benchmark_size` | `size_bytes` (lower) | File, bundle, Docker image size |
| `test_pass_rate` | `pass_rate` (higher) | Test suite pass percentage |
| `build_speed` | `build_seconds` (lower) | Build/compile/Docker build time |
| `memory_usage` | `peak_mb` (lower) | Peak memory during execution |
| `llm_judge_content` | `ctr_score` (higher) | Headlines, titles, descriptions |
| `llm_judge_prompt` | `quality_score` (higher) | System prompts, agent instructions |
| `llm_judge_copy` | `engagement_score` (higher) | Social posts, ad copy, emails |

## After Setup

Report to the user:
- Experiment path and branch name
- Whether the eval command worked and the baseline metric
- Suggest: "Run `/ar:run {domain}/{name}` to start iterating, or `/ar:loop {domain}/{name}` for autonomous mode."

---

## Why This Skill Exists

Set up a new autoresearch experiment interactively. Collects domain, target file, eval command, metric, direction, and evaluator.

<!-- SR_40: auto-generated from frontmatter `purpose`/`description` (OPP-Phase3). Expand with domain-specific rationale. -->

## When to Use

Use this skill when the task requires setup capabilities.

<!-- SR_40: auto-generated from frontmatter `when`/`description` (OPP-Phase3). -->

## What If Fails

If this skill fails to produce the expected output: (1) verify input completeness, (2) retry with more specific context, (3) fall back to the parent workflow without this skill.

<!-- SR_40: auto-generated from frontmatter `what_if_fails` (OPP-Phase3). -->
