---
skill_id: algorithms.claudes_c_compiler
name: "Claudes C Compiler -- AI-Built C Compiler in Rust"
description: "A C compiler built by Claude, written in Rust. Demonstrates long-horizon coding agent capabilities. Compiles C to x86-64 and ARM64 assembly."
version: v00.33.0
status: CANDIDATE
domain_path: algorithms/claudes-c-compiler
anchors:
  - c_compiler
  - rust
  - codegen
  - assembly
  - x86_64
  - arm64
  - long_horizon_agent
  - compiler
source_repo: claudes-c-compiler
risk: safe
languages: [rust]
llm_compat: {claude: full, gpt4o: partial, gemini: partial, llama: minimal}
apex_version: v00.33.0
---

# Claude C Compiler

## Why This Matters for APEX

This is a real C compiler built by Claude autonomously — a demonstration of
long-horizon coding capability. Useful as a reference for SCIENTIFIC mode tasks.

## README

# CCC — Claude's C Compiler

A C compiler written entirely from scratch in Rust, targeting x86-64, i686,
AArch64, and RISC-V 64. Zero compiler-specific dependencies — the frontend,
SSA-based IR, optimizer, code generator, peephole optimizers, assembler,
linker, and DWARF debug info generation are all implemented from scratch.
Claude's C Compiler produces ELF executables without any external toolchain.

> Note: With the exception of this one paragraph that was written by a human, 100% of the code and documentation in this repository was written by Claude Opus 4.6. A human guided some of this process by writing test cases that Claude was told to pass, but never interactively pair-programmed with Claude to debug or to provide feedback on code quality. As a result, I do not recommend you use this code! None of it has been validated for correctness. Claude wrote this exclusively on a Linux host; it probably will not work on MacOS/Windows — neither I nor Claude have tried. The docs may be wrong and make claims that are false. See [our blog post](https://anthropic.com/engineering/building-c-compiler) for more detail.

## Prerequisites

- **Rust** (stable, 2021 edition) — install via [rustup](https://rustup.rs/)
- **Linux host** — the compiler targets Linux ELF executables and relies on
  Linux system headers / C runtime libraries (glibc or musl) being installed
  on the host
- For cross-compilation targets (ARM, RISC-V, i686), the corresponding
  cross-compilation sysroots should be installed (e.g.,
  `aarch64-linux-gnu-gcc`, `riscv64-linux-gnu-gcc`)

## Building

```bash
cargo build --release
```

This produces five binaries in `target/release/`, all compiled from the same
source. The target architecture is selected by the binary name at runtime:

| Binary | Target |
|--------|--------|
| `ccc` | x86-64 (default) |
| `ccc-x86` | x86-64 |
| `ccc-arm` | AArch64 |
| `ccc-riscv` | RISC-V 64 |
| `ccc-i686` | i686 (32-bit x86) |

## Quick Start

Compile and run a simple C progr

## Diff History
- **v00.33.0**: Ingested from claudes-c-compiler-main