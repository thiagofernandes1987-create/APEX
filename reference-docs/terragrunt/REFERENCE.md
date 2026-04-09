---
skill_id: reference_docs.terragrunt
name: "Terragrunt -- Terraform Wrapper and IaC Orchestrator"
description: "Terragrunt is a thin wrapper around Terraform/OpenTofu that provides extra tools for working with multiple Terraform modules. Infrastructure-as-Code orchestration. NOT directly used by APEX — included as DevOps infrastructure reference."
version: v00.33.0
status: REFERENCE
domain_path: reference-docs/terragrunt
anchors:
  - terraform
  - infrastructure_as_code
  - iac
  - devops
  - opentofu
  - cloud_infrastructure
source_repo: terragrunt-main
risk: safe
languages: [go, hcl]
llm_compat: {claude: partial, gpt4o: partial, gemini: partial, llama: minimal}
apex_version: v00.33.0
---

# Terragrunt

## Status: REFERENCE (DevOps Infrastructure)

Terragrunt is a **Terraform/OpenTofu wrapper** for IaC orchestration. Included as a
reference document from the v00.33.0 ingestion batch. Source code NOT extracted
— 6,262 files of Go CLI + HCL config tooling with no direct APEX-skill relevance.

## Why Not Fully Extracted

- **Domain**: Infrastructure provisioning (AWS/GCP/Azure resource management)
- **Language**: Go (CLI), HCL (config language)
- **APEX relevance**: None direct — APEX does not provision cloud infrastructure
- **File count**: 6,262 files (would add noise without value)

## Potential APEX Use Cases

If APEX were to assist users with IaC tasks:
- `terraform` and `iac` anchors activate this reference
- Module composition patterns transferable to APEX skill composition
- DRY principles in Terragrunt mirror APEX's deduplication strategy

## README

# Terragrunt

[![Maintained by Gruntwork.io](https://img.shields.io/badge/maintained%20by-gruntwork.io-%235849a6.svg)](https://gruntwork.io/?ref=repo_terragrunt)
[![Go Report Card](https://goreportcard.com/badge/github.com/gruntwork-io/terragrunt)](https://goreportcard.com/report/github.com/gruntwork-io/terragrunt)
[![GoDoc](https://godoc.org/github.com/gruntwork-io/terragrunt?status.svg)](https://godoc.org/github.com/gruntwork-io/terragrunt)
![OpenTofu Version](https://img.shields.io/badge/tofu-%3E%3D1.6.0-blue.svg)
![Terraform Version](https://img.shields.io/badge/tf-%3E%3D0.12.0-blue.svg)

Terragrunt is a flexible orchestration tool that allows Infrastructure as Code written in [OpenTofu](https://opentofu.org)/[Terraform](https://www.terraform.io) to scale.

Please see the following for more info, including install instructions and complete documentation:

* [Terragrunt Website](https://terragrunt.com)
* [Getting started with Terragrunt](https://docs.terragrunt.com/getting-started/quick-start/)
* [Terragrunt Documentation](https://docs.terragrunt.com/)
* [Contributing to Terragrunt](https://docs.terragrunt.com/community/contributing)
* [Commercial Support](https://gruntwork.io/support/)

## Join the Discord!

Join [our community](https://discord.com/invite/YENaT9h8jh) for discussions, support, and contributions:

[![](https://dcbadge.limes.pink/api/server/https://discord.com/invite/YENaT9h8jh)](https://discord.com/invite/YENaT9h8jh)

## License

This code is released under the MIT License. See [LICENSE.txt](LICENSE.txt).


## Diff History
- **v00.33.0**: Ingested as REFERENCE from terragrunt-main (6262 source files, not extracted)