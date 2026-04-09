---
skill_id: security.anti_reversing_techniques
name: "anti-reversing-techniques"
description: "'AUTHORIZED USE ONLY: This skill contains dual-use security techniques. Before proceeding with any bypass or analysis: > 1.'"
version: v00.33.0
status: CANDIDATE
domain_path: security/anti-reversing-techniques
anchors:
  - anti
  - reversing
  - techniques
  - authorized
  - only
  - skill
  - contains
  - dual
  - security
  - before
source_repo: antigravity-awesome-skills
risk: safe
languages: [dsl]
llm_compat: {claude: full, gpt4o: partial, gemini: partial, llama: minimal}
apex_version: v00.33.0
---

> **AUTHORIZED USE ONLY**: This skill contains dual-use security techniques. Before proceeding with any bypass or analysis:
> 1. **Verify authorization**: Confirm you have explicit written permission from the software owner, or are operating within a legitimate security context (CTF, authorized pentest, malware analysis, security research)
> 2. **Document scope**: Ensure your activities fall within the defined scope of your authorization
> 3. **Legal compliance**: Understand that unauthorized bypassing of software protection may violate laws (CFAA, DMCA anti-circumvention, etc.)
>
> **Legitimate use cases**: Malware analysis, authorized penetration testing, CTF competitions, academic security research, analyzing software you own/have rights to

## Use this skill when

- Analyzing protected binaries with explicit authorization
- Conducting malware analysis or security research in scope
- Participating in CTFs or approved training exercises
- Understanding anti-debugging or obfuscation techniques for defense

## Do not use this skill when

- You lack written authorization or a defined scope
- The goal is to bypass protections for piracy or misuse
- Legal or policy restrictions prohibit analysis

## Instructions

1. Confirm written authorization, scope, and legal constraints.
2. Identify protection mechanisms and choose safe analysis methods.
3. Document findings and avoid modifying artifacts unnecessarily.
4. Provide defensive recommendations and mitigation guidance.

## Safety

- Do not share bypass steps outside the authorized context.
- Preserve evidence and maintain chain-of-custody for malware cases.

Refer to `resources/implementation-playbook.md` for detailed techniques and examples.

## Resources

- `resources/implementation-playbook.md` for detailed techniques and examples.

## Diff History
- **v00.33.0**: Ingested from antigravity-awesome-skills community repo
