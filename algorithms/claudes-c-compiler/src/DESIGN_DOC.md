# CCC Design Document

This document describes the architecture and implementation of CCC
(Claude's C Compiler). For building, usage, and status information, see
[README.md](README.md). Each `src/` subdirectory also has its own
`README.md` with detailed per-module documentation.

---

## Table of Contents

1. [High-Level Pipeline](#high-level-pipeline)
2. [Source Tree](#source-tree)
3. [Compilation Pipeline (Data Flow)](#compilation-pipeline-data-flow)
4. [Key Design Decisions](#key-design-decisions)
5. [Design Philosophy](#design-philosophy)
6. [Assembler and Linker Architecture](#assembler-and-linker-architecture)
7. [Sub-Module Documentation](#sub-module-documentation)

---

## High-Level Pipeline

The compiler is a multi-phase pipeline. Each phase is a separate Rust module
with a well-defined input/output interface. The entire flow -- from C source
to ELF executable -- is handled internally with no external tools.

```
    +---------------------------------------------------------------------+
    |                        C Source Files (.c, .h)                       |
    +----------------------------------+----------------------------------+
                                       |
    +----------------------------------v----------------------------------+
    |                    FRONTEND (src/frontend/)                         |
    |                                                                    |
    |  +--------------+    +-------+    +--------+    +--------------+   |
    |  | Preprocessor |---»| Lexer |---»| Parser |---»|     Sema     |   |
    |  |              |    |       |    |        |    |              |   |
    |  | macro expand,|    |tokens |    |spanned |    | type check,  |   |
    |  | #include,    |    | with  |    |  AST   |    | const eval,  |   |
    |  | #ifdef       |    | spans |    |        |    | symbol table |   |
    |  +--------------+    +-------+    +--------+    +------+-------+   |
    +------------------------------------------------------------+-------+
                                                                 |
                                          AST + SemaResult (TypeContext,
                                          expr types, const values)
                                                                 |
    +------------------------------------------------------------v-------+
    |                    IR SUBSYSTEM (src/ir/)                           |
    |                                                                    |
    |  +------------------+         +------------------------------+     |
    |  |   IR Lowering    |--------»|          mem2reg             |     |
    |  |                  |         |                              |     |
    |  | AST -> alloca-   |         | SSA promotion via dominator  |     |
    |  | based IR (every  |         | frontiers; insert phi nodes, |     |
    |  | local is a stack |         | rename values                |     |
    |  | slot)            |         |                              |     |
    |  +------------------+         +--------------+---------------+     |
    +----------------------------------------------+---------------------+
                                                   |  SSA IR
    +----------------------------------------------v---------------------+
    |               OPTIMIZATION PASSES (src/passes/)                    |
    |                                                                    |
    |  Phase 0: Inlining + post-inline cleanup                           |
    |    (inline -> mem2reg -> constant_fold -> copy_prop -> simplify    |
    |     -> constant_fold -> copy_prop -> resolve_asm)                  |
    |           |                                                        |
    |  Main Loop (up to 3 iterations, dirty-tracked):                    |
    |    cfg_simplify -> copy_prop -> div_by_const -> narrow -> simplify |
    |    -> constant_fold -> gvn -> licm -> iv_strength_reduce           |
    |    -> if_convert -> copy_prop -> dce -> cfg_simplify -> ipcp       |
    |           |                                                        |
    |  Dead static elimination                                           |
    |           |                                                        |
    |  Phi Elimination (SSA -> register copies)                          |
    +----------------------------------+---------------------------------+
                                       |  non-SSA IR
    +----------------------------------v---------------------------------+
    |                    BACKEND (src/backend/)                           |
    |                                                                    |
    |  +---------------------------------------------------------+      |
    |  |              Code Generation (ArchCodegen trait)          |      |
    |  |                                                          |      |
    |  |  +----------+  +----------+  +----------+  +----------+ |      |
    |  |  |  x86-64  |  |   i686   |  |  AArch64 |  | RISC-V64 | |      |
    |  |  | SysV ABI |  |  cdecl   |  | AAPCS64  |  |  LP64D   | |      |
    |  |  +----+-----+  +----+-----+  +----+-----+  +----+-----+ |      |
    |  +-------+-------------+------------+---------------+-------+      |
    |          |             |            |               |               |
    |  +-------v-------------v------------v---------------v-------+      |
    |  |              Peephole Optimizer (per-arch)                |      |
    |  |  store/load forwarding, dead stores, copy prop, branches |      |
    |  +-------+-------------+------------+---------------+-------+      |
    |          |             |            |               |               |
    |  +-------v-------------v------------v---------------v-------+      |
    |  |             Builtin Assembler (per-arch)                  |      |
    |  |  parse asm text -> encode instructions -> write ELF .o   |      |
    |  +-------+-------------+------------+---------------+-------+      |
    |          |             |            |               |               |
    |  +-------v-------------v------------v---------------v-------+      |
    |  |              Builtin Linker (per-arch)                    |      |
    |  |  read .o + CRT + libs -> resolve symbols -> write ELF    |      |
    |  +-------+-------------+------------+---------------+-------+      |
    +----------+-------------+------------+---------------+---------------+
               |             |            |               |
               v             v            v               v
             ELF           ELF          ELF             ELF
```

---

## Source Tree

```
src/
  frontend/                  C source -> typed AST
    preprocessor/            Macro expansion, #include, #ifdef, #pragma once
    lexer/                   Tokenization with source locations
    parser/                  Recursive descent, produces spanned AST
    sema/                    Type checking, symbol table, const evaluation

  ir/                        Target-independent SSA IR
    lowering/                AST -> alloca-based IR
    mem2reg/                 SSA promotion (dominator tree, phi insertion)

  passes/                    SSA optimization passes
    constant_fold            Constant folding and propagation
    copy_prop                Copy propagation
    dce                      Dead code elimination
    gvn                      Global value numbering
    licm                     Loop-invariant code motion
    simplify                 Algebraic simplification
    cfg_simplify             CFG cleanup, branch threading
    inline                   Function inlining (always_inline + small static)
    if_convert               Diamond if-conversion to select (cmov/csel)
    narrow                   Integer narrowing (eliminate promotion overhead)
    div_by_const             Division strength reduction (mul+shift)
    ipcp                     Interprocedural constant propagation
    iv_strength_reduce       Induction variable strength reduction
    loop_analysis            Shared natural loop detection (used by LICM, IVSR)
    dead_statics             Dead static function/global elimination
    resolve_asm              Post-inline asm symbol resolution

  backend/                   IR -> assembly -> machine code -> ELF
    traits.rs                ArchCodegen trait with shared default implementations
    generation.rs            IR instruction dispatch to trait methods
    liveness.rs              Live interval computation for register allocation
    regalloc.rs              Linear scan register allocator
    state.rs                 Shared codegen state (stack slots, register cache)
    stack_layout/            Stack frame layout with liveness-based slot packing
    call_abi.rs              Unified ABI classification (caller + callee)
    cast.rs                  Shared cast and float operation classification
    f128_softfloat.rs        IEEE binary128 soft-float (ARM + RISC-V)
    inline_asm.rs            Shared inline assembly framework
    common.rs                Data sections, external tool fallback invocation
    x86_common.rs            Shared x86/i686 register names, condition codes
    elf/                     ELF constants, archive reading, shared types
    elf_writer_common.rs     Common ELF object file writing utilities
    linker_common/           Shared linker types (symbols, dynamic linking, EH frame)
    asm_preprocess.rs        Assembly text preprocessing (macro expansion, conditionals)
    asm_expr.rs              Assembly expression evaluation
    peephole_common.rs       Shared peephole optimizer utilities (word matching, line store)
    x86/
      codegen/               x86-64 code generation (SysV AMD64 ABI) + peephole
      assembler/             Builtin x86-64 assembler (parser, encoder, ELF writer)
      linker/                Builtin x86-64 linker (dynamic linking, PLT/GOT, TLS)
    i686/
      codegen/               i686 code generation (cdecl, ILP32) + peephole
      assembler/             Builtin i686 assembler (reuses x86 parser, 32-bit encoder)
      linker/                Builtin i686 linker (32-bit ELF, R_386 relocations)
    arm/
      codegen/               AArch64 code generation (AAPCS64) + peephole
      assembler/             Builtin AArch64 assembler (parser, encoder, ELF writer)
      linker/                Builtin AArch64 linker (static + dynamic linking, IFUNC/TLS)
    riscv/
      codegen/               RISC-V 64 code generation (LP64D) + peephole
      assembler/             Builtin RV64 assembler (parser, encoder, RV64C compress)
      linker/                Builtin RV64 linker (dynamic linking)

  common/                    Shared types, symbol table, diagnostics
  driver/                    CLI parsing, pipeline orchestration
```

---

## Compilation Pipeline (Data Flow)

Each phase transforms the program into a progressively lower-level
representation. The concrete Rust types flowing between phases are:

```
  &str  (C source text)
    |
    |  Preprocessor::preprocess()
    v
  String  (expanded text with line markers)
    |
    |  Lexer::tokenize()
    v
  Vec<Token>  (each Token = { kind: TokenKind, span: Span })
    |
    |  Parser::parse()
    v
  TranslationUnit  (AST: Vec<ExternalDecl> with source spans)
    |
    |  SemanticAnalyzer::analyze()
    v
  TranslationUnit + SemaResult
    |   SemaResult bundles:
    |     - functions: FxHashMap<String, FunctionInfo>
    |     - type_context: TypeContext (struct layouts, typedefs, enums)
    |     - expr_types: FxHashMap<ExprId, CType>
    |     - const_values: FxHashMap<ExprId, IrConst>
    |
    |  Lowerer::lower()
    v
  IrModule  (alloca-based IR: every local is a stack slot)
    |
    |  promote_allocas()  (mem2reg)
    v
  IrModule  (SSA form: phi nodes, virtual registers)
    |
    |  run_passes()  (up to 3 iterations with dirty tracking)
    v
  IrModule  (optimized SSA)
    |
    |  eliminate_phis()
    v
  IrModule  (non-SSA: phi nodes lowered to register copies)
    |
    |  Target::generate_assembly_with_opts_and_debug()  (ArchCodegen dispatch)
    v
  String  (target-specific assembly text)
    |
    |  Builtin assembler  (parse -> encode -> ELF .o)
    v
  ELF object file (.o)
    |
    |  Builtin linker  (resolve symbols -> apply relocs -> write ELF)
    v
  ELF executable
```

---

## Key Design Decisions

- **SSA IR**: The IR uses SSA form with phi nodes, constructed via mem2reg over
  alloca-based lowering. This is the same approach as LLVM.

- **Trait-based backends**: All four backends implement the `ArchCodegen` trait
  (~185 methods). Shared logic (call ABI classification, inline asm framework,
  f128 soft-float) lives in default trait methods and shared modules.

- **Linear scan register allocation**: Loop-aware liveness analysis feeds a
  linear scan allocator (callee-saved + caller-saved) on all four backends.
  Register-allocated values bypass stack slots entirely.

- **Text-to-text preprocessor**: The preprocessor operates on raw text, emitting
  GCC-style `# line "file"` markers for source location tracking. Include guard
  detection avoids re-processing headers.

- **Peephole optimization**: Each backend has a post-codegen peephole optimizer
  that eliminates redundant patterns (store/load forwarding, dead stores, copy
  propagation) from the stack-based code generator. The x86 peephole is the most
  mature with 15 distinct pass functions.

- **Builtin assembler and linker**: Each architecture has a native assembler
  (AT&T/ARM/RV syntax parser, instruction encoder, ELF object writer) and a
  native linker (symbol resolution, relocation application, ELF executable
  writer). No external toolchain is required.

- **Dual type system**: CType represents C-level types (preserving `int` vs
  `long` distinctions for type checking), while IrType is a flat machine-level
  enumeration (`I8`..`I128`, `U8`..`U128`, `F32`, `F64`, `F128`, `Ptr`,
  `Void`). The lowering phase bridges between them.

---

## Design Philosophy

- **Separation of concerns through representations.** Each major phase works on
  its own representation: the frontend on text/tokens/AST, the IR subsystem on
  alloca-based IR, the optimizer on SSA IR, and the backend on non-SSA IR. Phase
  boundaries are explicit ownership transfers, not shared mutable state.

- **Alloca-then-promote for SSA construction.** Rather than constructing SSA
  directly during AST lowering (which interleaves C semantics with SSA
  bookkeeping), the lowerer emits simple alloca/load/store sequences. The
  mem2reg pass then promotes these to SSA independently. This is the same
  strategy LLVM uses and cleanly separates the two concerns.

- **Trait-based backend abstraction.** The `ArchCodegen` trait (~185 methods)
  captures the interface between the shared code generation framework and
  architecture-specific instruction emission. Default implementations express
  algorithms once (e.g., the 7-phase call sequence in `emit_call`), while backends supply
  only the architecture-specific primitives.

- **Zero external dependencies for compilation.** The entire compilation
  pipeline -- from C source to ELF executable -- is self-contained. No lexer
  generators, parser generators, register allocator libraries, external
  assemblers, or external linkers are required. Every component is implemented
  from scratch using only general-purpose Rust crates.

---

## Assembler and Linker Architecture

The builtin assembler and linker are the default when compiling without
the `gcc_assembler` or `gcc_linker` Cargo features. The selection is done
at compile time via `#[cfg(feature = "...")]` -- there are no runtime
environment variables.

### Builtin Assembler

Each assembler follows a three-stage pipeline:

```
  Assembly text (String)
       |
       |  Parser
       v
  Vec<AsmStatement>  (parsed instructions, directives, labels)
       |
       |  Encoder
       v
  Vec<u8>  (encoded machine code bytes + relocation entries)
       |
       |  ELF Writer
       v
  ELF object file (.o)
```

| Architecture | Parser | Encoder | Extra Features |
|-------------|--------|---------|---------------|
| x86-64 | AT&T syntax, shared | REX prefixes, ModR/M, SIB | SSE/AES-NI encoding |
| i686 | Reuses x86 parser | No REX, 32-bit operands | ELFCLASS32, Elf32_Rel |
| AArch64 | ARM assembly syntax | Fixed 32-bit encoding | imm12 auto-shift |
| RISC-V | RV assembly syntax | Fixed 32-bit encoding | RV64C compression |

### Builtin Linker

Each linker reads ELF object files and static archives, resolves symbols,
applies relocations, and writes a complete ELF executable:

| Architecture | Link Mode | Key Relocations | Special Features |
|-------------|-----------|-----------------|-----------------|
| x86-64 | Dynamic | R_X86_64_64, PC32, PLT32, GOTPCREL | PLT/GOT, TLS |
| i686 | Dynamic | R_386_32, PC32, PLT32, GOTPC, GOTOFF | 32-bit ELF, `.rel` |
| AArch64 | Static + Dynamic | ADR_PREL_PG_HI21, ADD_ABS_LO12_NC, CALL26 | PLT/GOT, IFUNC/IPLT, TLS |
| RISC-V | Dynamic | HI20, LO12_I, LO12_S, CALL, PCREL_HI20 | TLS GD→LE relaxation |

### GCC Fallback

When compiled with the `gcc_assembler` and/or `gcc_linker` Cargo features,
the compiler delegates to the GCC cross-compiler toolchain for the
corresponding stages. A warning is printed when the fallback is used. This
mode is useful for debugging: compile a binary with GCC features and compare
byte-level output against the standalone binary.

---

## Sub-Module Documentation

Each compiler subsystem has its own detailed design document:

| Module | README |
|--------|--------|
| Frontend (preprocessor, lexer, parser, sema) | [`src/frontend/README.md`](src/frontend/README.md) |
| IR subsystem (lowering, mem2reg) | [`src/ir/README.md`](src/ir/README.md) |
| Optimization passes | [`src/passes/README.md`](src/passes/README.md) |
| Backend (codegen, assembler, linker) | [`src/backend/README.md`](src/backend/README.md) |
| Common (types, diagnostics, source) | [`src/common/README.md`](src/common/README.md) |
| Driver (CLI, pipeline) | [`src/driver/README.md`](src/driver/README.md) |

Per-architecture backend documentation:

| Architecture | Overview | Code Generation | Assembler | Linker |
|-------------|----------|----------------|-----------|--------|
| x86-64 | [`x86/README.md`](src/backend/x86/README.md) | [`x86/codegen/README.md`](src/backend/x86/codegen/README.md) | [`x86/assembler/README.md`](src/backend/x86/assembler/README.md) | [`x86/linker/README.md`](src/backend/x86/linker/README.md) |
| i686 | [`i686/README.md`](src/backend/i686/README.md) | [`i686/codegen/README.md`](src/backend/i686/codegen/README.md) | [`i686/assembler/README.md`](src/backend/i686/assembler/README.md) | [`i686/linker/README.md`](src/backend/i686/linker/README.md) |
| AArch64 | [`arm/README.md`](src/backend/arm/README.md) | [`arm/codegen/README.md`](src/backend/arm/codegen/README.md) | [`arm/assembler/README.md`](src/backend/arm/assembler/README.md) | [`arm/linker/README.md`](src/backend/arm/linker/README.md) |
| RISC-V 64 | [`riscv/README.md`](src/backend/riscv/README.md) | [`riscv/codegen/README.md`](src/backend/riscv/codegen/README.md) | [`riscv/assembler/README.md`](src/backend/riscv/assembler/README.md) | [`riscv/linker/README.md`](src/backend/riscv/linker/README.md) |

The x86-64 peephole optimizer has its own detailed documentation: [`src/backend/x86/codegen/peephole/README.md`](src/backend/x86/codegen/peephole/README.md).
