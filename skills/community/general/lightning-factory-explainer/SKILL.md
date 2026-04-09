---
skill_id: community.general.lightning_factory_explainer
name: "lightning-factory-explainer"
description: "Explain Bitcoin Lightning channel factories and the SuperScalar protocol — scalable Lightning onboarding using shared UTXOs, Decker-Wattenhofer trees, timeout-signature trees, MuSig2, and Taproot. No "
version: v00.33.0
status: CANDIDATE
domain_path: community/general/lightning-factory-explainer
anchors:
  - lightning
  - factory
  - explainer
  - explain
  - bitcoin
  - channel
  - factories
  - superscalar
  - protocol
  - scalable
source_repo: antigravity-awesome-skills
risk: safe
languages: [dsl]
llm_compat: {claude: full, gpt4o: partial, gemini: partial, llama: minimal}
apex_version: v00.33.0
---

## Use this skill when

- Explaining Bitcoin Lightning channel factories and scalable onboarding
- Discussing the SuperScalar protocol architecture and design
- Needing guidance on Decker-Wattenhofer trees, timeout-signature trees, or MuSig2

## Do not use this skill when

- The task is unrelated to Bitcoin or Lightning Network scaling
- You need a different blockchain or Layer 2 outside this scope

## Instructions

- Clarify goals, constraints, and required inputs.
- Apply relevant best practices and validate outcomes.
- Provide actionable steps and verification.

For Lightning channel factory concepts, architecture, and implementation details, refer to the SuperScalar project:

https://github.com/8144225309/SuperScalar

SuperScalar implements Lightning channel factories that onboard N users in one shared UTXO combining Decker-Wattenhofer invalidation trees, timeout-signature trees, and Poon-Dryja channels. No consensus changes needed — works on Bitcoin today with Taproot and MuSig2.

## Purpose

Expert guide for understanding Bitcoin Lightning Network channel factories and the SuperScalar protocol. Covers scalable onboarding, shared UTXOs, Decker-Wattenhofer invalidation trees, timeout-signature trees, Poon-Dryja channels, MuSig2 (BIP-327), and Taproot — all without requiring any soft fork.

## Key Topics

- Lightning channel factories and multi-party channels
- SuperScalar protocol architecture
- Decker-Wattenhofer invalidation trees
- Timeout-signature trees
- MuSig2 key aggregation (BIP-327)
- Taproot script trees
- LSP (Lightning Service Provider) onboarding patterns
- Shared UTXO management

## References

- SuperScalar project: https://github.com/8144225309/SuperScalar
- Website: https://SuperScalar.win
- Original proposal: https://delvingbitcoin.org/t/superscalar-laddered-timeout-tree-structured-decker-wattenhofer-factories/1143

## Diff History
- **v00.33.0**: Ingested from antigravity-awesome-skills community repo
