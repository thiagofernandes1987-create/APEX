---
skill_id: engineering.programming.rust.akf_trust_metadata
name: "akf-trust-metadata"
description: "'The AI native file format. EXIF for AI — stamps every file with trust scores, source provenance, and compliance metadata. Embeds into 20+ formats (DOCX, PDF, images, code). EU AI Act, SOX, HIPAA audi"
version: v00.33.0
status: CANDIDATE
domain_path: engineering/programming/rust/akf-trust-metadata
anchors:
  - trust
  - metadata
  - native
  - file
  - format
  - exif
  - stamps
  - every
  - scores
  - source
source_repo: antigravity-awesome-skills
risk: safe
languages: [dsl]
llm_compat: {claude: full, gpt4o: partial, gemini: partial, llama: minimal}
apex_version: v00.33.0
---

# AKF — The AI Native File Format

Every photo has EXIF. Every song has ID3. AKF is the native metadata format for AI-generated content.

## When to Use

Use this skill when you need to stamp, inspect, or audit provenance and trust metadata on AI-generated or AI-modified files for compliance, review, or handoff workflows.

## After creating or modifying files

```bash
akf stamp <file> --agent <agent-name> --evidence "<what you did>"
```

Evidence examples:
- "generated from user prompt"
- "refactored existing code"
- "tests pass"
- "docs reviewed"

## Before modifying existing files

```bash
akf read <file>          # Check existing trust metadata
akf inspect <file>       # See detailed trust scores
```

## Compliance auditing

```bash
akf audit <file> --regulation eu_ai_act    # EU AI Act Article 50
akf audit <file> --regulation hipaa         # HIPAA
akf audit <file> --regulation sox           # SOX
akf audit <file> --regulation nist_ai       # NIST AI RMF
```

## Classification

- `--label confidential` for finance/secret/internal paths
- `--label public` for README, docs, examples
- Default: `internal`

## Install

```bash
pip install akf
```

## Links

- https://akf.dev
- https://github.com/HMAKT99/AKF
- npm: `npm install akf-format`

## Diff History
- **v00.33.0**: Ingested from antigravity-awesome-skills community repo
