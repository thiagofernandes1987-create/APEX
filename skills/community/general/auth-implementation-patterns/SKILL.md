---
skill_id: community.general.auth_implementation_patterns
name: "auth-implementation-patterns"
description: "'Build secure, scalable authentication and authorization systems using industry-standard patterns and modern best practices.'"
version: v00.33.0
status: CANDIDATE
domain_path: community/general/auth-implementation-patterns
anchors:
  - auth
  - implementation
  - patterns
  - build
  - secure
  - scalable
  - authentication
  - authorization
  - systems
  - industry
source_repo: antigravity-awesome-skills
risk: safe
languages: [dsl]
llm_compat: {claude: full, gpt4o: partial, gemini: partial, llama: minimal}
apex_version: v00.33.0
---

# Authentication & Authorization Implementation Patterns

Build secure, scalable authentication and authorization systems using industry-standard patterns and modern best practices.

## Use this skill when

- Implementing user authentication systems
- Securing REST or GraphQL APIs
- Adding OAuth2/social login or SSO
- Designing session management or RBAC
- Debugging authentication or authorization issues

## Do not use this skill when

- You only need UI copy or login page styling
- The task is infrastructure-only without identity concerns
- You cannot change auth policies or credential storage

## Instructions

- Define users, tenants, flows, and threat model constraints.
- Choose auth strategy (session, JWT, OIDC) and token lifecycle.
- Design authorization model and policy enforcement points.
- Plan secrets storage, rotation, logging, and audit requirements.
- If detailed examples are required, open `resources/implementation-playbook.md`.

## Safety

- Never log secrets, tokens, or credentials.
- Enforce least privilege and secure storage for keys.

## Resources

- `resources/implementation-playbook.md` for detailed patterns and examples.

## Diff History
- **v00.33.0**: Ingested from antigravity-awesome-skills community repo
