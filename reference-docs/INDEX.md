# Reference Documentation

Infrastructure and tooling repos from v00.33.0 ingestion batch.
These are documented as REFERENCE status — not extracted as APEX skills
because they are pure DevOps/infrastructure with no direct skill relevance.

| Repo | Domain | Files | Status |
|------|--------|-------|--------|
| [argo-cd](argo-cd/REFERENCE.md) | GitOps/Kubernetes CD | 6,758 | REFERENCE |
| [terragrunt](terragrunt/REFERENCE.md) | Terraform/IaC | 6,262 | REFERENCE |

## Total Coverage

With these entries, **all 39 repositories** from the v00.33.0 ZIP ingestion are
documented in the APEX repo:

- **37 repos**: Fully extracted (skills, agents, source code, examples)
- **2 repos**: Documented as REFERENCE (DevOps infrastructure)

## When to Activate

These references activate when user tasks involve:
- Kubernetes deployment pipelines (`gitops`, `kubernetes`)
- Terraform/OpenTofu infrastructure (`terraform`, `iac`)
- CI/CD and GitOps patterns