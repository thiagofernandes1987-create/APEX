---
skill_id: algorithms.nix_eval_jobs
name: "Nix Eval Jobs -- Evaluation Infrastructure"
description: "Reference documentation for Nix Eval Jobs -- Evaluation Infrastructure. Source: nix-eval-jobs-main"
version: v00.33.0
status: CANDIDATE
domain_path: algorithms/nix-eval-jobs
anchors:
  - nix
  - nix_eval_jobs
source_repo: nix-eval-jobs-main
risk: safe
languages: [dsl]
llm_compat: {claude: full, gpt4o: partial, gemini: partial, llama: minimal}
apex_version: v00.33.0
---

# Nix Eval Jobs -- Evaluation Infrastructure

Source: `nix-eval-jobs-main` (46 files)

## README

# nix-eval-jobs

This project evaluates nix attribute sets in parallel with streamable json
output. This is useful for time and memory intensive evaluations such as NixOS
machines, i.e. in a CI context. The evaluation is done with a controllable
number of threads that are restarted when their memory consumption exceeds a
certain threshold.

To facilitate integration, nix-eval-jobs creates garbage collection roots for
each evaluated derivation (drv file, not the build) within the provided
attribute. This prevents race conditions between the nix garbage collection
service and user-started nix builds processes.

## Why using nix-eval-jobs?

- Faster evaluation by using threads
- Memory used for evaluation is reclaimed after nix-eval-jobs finish, so that
  the build can use it.
- Evaluation of jobs can fail individually

## Example

In the following example we evaluate the hydraJobs attribute of the
[patchelf](https://github.com/NixOS/patchelf) flake:

```console
$ nix-eval-jobs --gc-roots-dir gcroot --flake 'github:NixOS/patchelf#hydraJobs'
{"attr":"coverage","attrPath":["coverage"],"drvPath":"/nix/store/fmbqzaq8mim1423879lhn9whs6imx5w4-patchelf-coverage-0.18.0.drv","inputDrvs":{"/nix/store/23632hx2c98lbbjld279dx0w08lxn6kp-hook.drv":["out"],"/nix/store/6z1jfnqqgyqr221zgbpm30v91yfj3r45-bash-5.1-p16.drv":["out"],"/nix/store/ap9g09fxbicj836zm88d56dn3ff4clxl-stdenv-linux.drv":["out"],"/nix/store/c0gg7lj101xhd8v2b3cjl5dwwkpxfc0q-patchelf-tarball-0.18.0.drv":["out"],"/nix/store/vslywm

## Diff History
- **v00.33.0**: Ingested from nix-eval-jobs-main