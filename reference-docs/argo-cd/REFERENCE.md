---
skill_id: reference_docs.argo_cd
name: "Argo CD -- GitOps Continuous Delivery for Kubernetes"
description: "Argo CD is a declarative GitOps CD tool for Kubernetes. Automates deployment of apps to Kubernetes clusters from Git repos. NOT directly used by APEX skills — included as DevOps infrastructure reference."
version: v00.33.0
status: REFERENCE
domain_path: reference-docs/argo-cd
anchors:
  - gitops
  - kubernetes
  - continuous_delivery
  - deployment
  - argocd
  - devops
source_repo: argo-cd-master
risk: safe
languages: [go, typescript]
llm_compat: {claude: partial, gpt4o: partial, gemini: partial, llama: minimal}
apex_version: v00.33.0
---

# Argo CD

## Status: REFERENCE (DevOps Infrastructure)

Argo CD is a **Kubernetes-native GitOps tool** for continuous delivery. It is included
in the APEX repo as a reference document because it was part of the v00.33.0 ingestion
batch, but its source code is NOT extracted — it contains 6,758 files of pure Kubernetes
operator/controller code with no APEX-skill or agent relevance.

## Why Not Fully Extracted

- **Domain**: Kubernetes cluster management, Helm chart deployment, GitOps reconciliation
- **Language**: Go (Kubernetes controller runtime), TypeScript (UI)
- **APEX relevance**: None direct — APEX does not deploy to Kubernetes
- **File count**: 6,758 files (would add noise without value)

## Potential APEX Use Cases

If APEX were to manage its own deployment pipeline or assist users with Kubernetes:
- `gitops` anchor would activate this reference
- GitOps principles align with APEX's diff-governance model (OPP-94)
- Declarative config management patterns useful for APEX's config system

## README

**Releases:**
[![Release Version](https://img.shields.io/github/v/release/argoproj/argo-cd?label=argo-cd)](https://github.com/argoproj/argo-cd/releases/latest)
[![Artifact HUB](https://img.shields.io/endpoint?url=https://artifacthub.io/badge/repository/argo-cd)](https://artifacthub.io/packages/helm/argo/argo-cd)
[![SLSA 3](https://slsa.dev/images/gh-badge-level3.svg)](https://slsa.dev)

**Code:** 
[![Integration tests](https://github.com/argoproj/argo-cd/workflows/Integration%20tests/badge.svg?branch=master)](https://github.com/argoproj/argo-cd/actions?query=workflow%3A%22Integration+tests%22)
[![codecov](https://codecov.io/gh/argoproj/argo-cd/branch/master/graph/badge.svg)](https://codecov.io/gh/argoproj/argo-cd)
[![CII Best Practices](https://bestpractices.coreinfrastructure.org/projects/4486/badge)](https://bestpractices.coreinfrastructure.org/projects/4486)
[![OpenSSF Scorecard](https://api.securityscorecards.dev/projects/github.com/argoproj/argo-cd/badge)](https://scorecard.dev/viewer/?uri=github.com/argoproj/argo-cd)

**Social:**
[![Twitter Follow](https://img.shields.io/twitter/follow/argoproj?style=social)](https://twitter.com/argoproj)
[![Slack](https://img.shields.io/badge/slack-argoproj-brightgreen.svg?logo=slack)](https://argoproj.github.io/community/join-slack)
[![LinkedIn](https://img.shields.io/badge/LinkedIn-argoproj-blue.svg?logo=linkedin)](https://www.linkedin.com/company/argoproj/)
[![Bluesky](https://img.shields.io/badge/Bluesky-argoproj-blue.svg?style=social&logo=bluesky)](https://bsky.app/profile/argoproj.bsky.social)

# Argo CD - Declarative Continuous Delivery for Kubernetes

## What is Argo CD?

Argo CD is a declarative, GitOps continuous delivery tool for Kubernetes.

![Argo CD UI](docs/assets/argocd-ui.gif)

[![Argo CD Demo](https://img.youtube.com/vi/0WAm0y2vLIo/0.jpg)](https://youtu.be/0WAm0y2vLIo)

## Why Argo CD?

1. Application definitions, configurations, and environments should be declarative and version controlled.
1. Application d

## Diff History
- **v00.33.0**: Ingested as REFERENCE from argo-cd-master (6758 source files, not extracted)