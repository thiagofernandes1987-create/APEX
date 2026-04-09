---
skill_id: operations.process_optimization
name: "process-optimization"
description: "Analyze and improve business processes. Trigger with 'this process is slow', 'how can we improve', 'streamline this workflow', 'too many steps', 'bottleneck', or when the user describes an inefficient"
version: v00.33.0
status: ADOPTED
domain_path: operations/process-optimization
anchors:
  - process
  - optimization
  - analyze
  - improve
  - business
  - processes
  - trigger
  - slow
  - streamline
  - workflow
  - many
  - steps
source_repo: knowledge-work-plugins-main
risk: safe
languages: [dsl]
llm_compat: {claude: full, gpt4o: partial, gemini: partial, llama: minimal}
apex_version: v00.33.0
---

# Process Optimization

Analyze existing processes and recommend improvements.

## Analysis Framework

### 1. Map Current State
- Document every step, decision point, and handoff
- Identify who does what and how long each step takes
- Note manual steps, approvals, and waiting times

### 2. Identify Waste
- **Waiting**: Time spent in queues or waiting for approvals
- **Rework**: Steps that fail and need to be redone
- **Handoffs**: Each handoff is a potential point of failure or delay
- **Over-processing**: Steps that add no value
- **Manual work**: Tasks that could be automated

### 3. Design Future State
- Eliminate unnecessary steps
- Automate where possible
- Reduce handoffs
- Parallelize independent steps
- Add checkpoints (not gates)

### 4. Measure Impact
- Time saved per cycle
- Error rate reduction
- Cost savings
- Employee satisfaction improvement

## Output

Produce a before/after process comparison with specific improvement recommendations, estimated impact, and an implementation plan.

## Diff History
- **v00.33.0**: Ingested from knowledge-work-plugins-main — auto-converted to APEX format
