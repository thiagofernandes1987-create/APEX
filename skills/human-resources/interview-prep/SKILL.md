---
skill_id: human_resources.interview_prep
name: "interview-prep"
description: "Create structured interview plans with competency-based questions and scorecards. Trigger with 'interview plan for', 'interview questions for', 'how should we interview', 'scorecard for', or when the "
version: v00.33.0
status: ADOPTED
domain_path: human-resources/interview-prep
anchors:
  - interview
  - prep
  - create
  - structured
  - plans
  - competency
  - based
  - questions
  - scorecards
  - trigger
  - plan
  - scorecard
source_repo: knowledge-work-plugins-main
risk: safe
languages: [dsl]
llm_compat: {claude: full, gpt4o: partial, gemini: partial, llama: minimal}
apex_version: v00.33.0
---

# Interview Prep

Create structured interview plans to evaluate candidates consistently and fairly.

## Interview Design Principles

1. **Structured**: Same questions for all candidates in the role
2. **Competency-based**: Map questions to specific skills and behaviors
3. **Evidence-based**: Use behavioral and situational questions
4. **Diverse panel**: Multiple perspectives reduce bias
5. **Scored**: Use rubrics, not gut feelings

## Interview Plan Components

### Role Competencies
Define 4-6 key competencies for the role (e.g., technical skills, communication, leadership, problem-solving).

### Question Bank
For each competency, provide:
- 2-3 behavioral questions ("Tell me about a time...")
- 1-2 situational questions ("How would you handle...")
- Follow-up probes

### Scorecard
Rate each competency on a consistent scale (1-4) with clear descriptions of what each level looks like.

### Debrief Template
Structured format for interviewers to share findings and make a decision.

## Output

Produce a complete interview kit: panel assignment (who interviews for what), question bank by competency, scoring rubric, and debrief template.

## Diff History
- **v00.33.0**: Ingested from knowledge-work-plugins-main — auto-converted to APEX format
