/// ELF file parsing for the x86-64 linker.
///
/// This module re-exports the shared ELF64 types and parser from `linker_common`,
/// plus provides x86-64-specific relocation constants. The actual parsing logic
/// lives in the shared module to avoid duplication with ARM and RISC-V.
// Re-export shared ELF constants for mod.rs and the emitter functions.
// Archive/linker-script functions are now called via linker_common.
pub use crate::backend::elf::{
    ELF_MAGIC, ELFCLASS64, ELFDATA2LSB, ET_EXEC, ET_DYN, EM_X86_64,
    SHT_PROGBITS, SHT_NOBITS, SHT_STRTAB, SHT_RELA,
    SHT_DYNAMIC, SHT_DYNSYM,
    SHT_INIT_ARRAY, SHT_FINI_ARRAY, SHT_GNU_HASH, SHT_GNU_VERSYM, SHT_GNU_VERNEED,
    SHF_WRITE, SHF_ALLOC, SHF_EXECINSTR, SHF_TLS,
    STB_GLOBAL, STB_WEAK,
    STT_OBJECT, STT_FUNC, STT_SECTION, STT_TLS, STT_GNU_IFUNC,
    SHN_UNDEF, SHN_ABS, SHN_COMMON,
    PT_LOAD, PT_DYNAMIC, PT_INTERP, PT_PHDR, PT_TLS, PT_GNU_STACK, PT_GNU_RELRO,
    PF_X, PF_W, PF_R,
    DT_NULL, DT_NEEDED, DT_PLTRELSZ, DT_PLTGOT, DT_STRTAB,
    DT_SYMTAB, DT_RELA, DT_RELASZ, DT_RELAENT, DT_STRSZ, DT_SYMENT,
    DT_JMPREL, DT_PLTREL, DT_GNU_HASH,
    is_thin_archive,
    parse_linker_script_entries, LinkerScriptEntry,
    LinkerSymbolAddresses, get_standard_linker_symbols,
    w16, w32, w64, write_bytes, wphdr,
};

use crate::backend::linker_common;

// x86-64 relocation types
pub const R_X86_64_NONE: u32 = 0;
pub const R_X86_64_64: u32 = 1;
pub const R_X86_64_PC32: u32 = 2;
pub const R_X86_64_GOT32: u32 = 3;
pub const R_X86_64_PLT32: u32 = 4;
pub const R_X86_64_GLOB_DAT: u32 = 6;
pub const R_X86_64_JUMP_SLOT: u32 = 7;
pub const R_X86_64_RELATIVE: u32 = 8;
pub const R_X86_64_GOTPCREL: u32 = 9;
pub const R_X86_64_32: u32 = 10;
pub const R_X86_64_32S: u32 = 11;
pub const R_X86_64_DTPMOD64: u32 = 16; // GD TLS model (not yet implemented; IE model used)
pub const R_X86_64_DTPOFF64: u32 = 17; // GD TLS model (not yet implemented; IE model used)
pub const R_X86_64_TPOFF64: u32 = 18;
pub const R_X86_64_GOTTPOFF: u32 = 22;
pub const R_X86_64_TPOFF32: u32 = 23;
pub const R_X86_64_PC64: u32 = 24;
pub const R_X86_64_GOTPCRELX: u32 = 41;
pub const R_X86_64_REX_GOTPCRELX: u32 = 42;
pub const R_X86_64_IRELATIVE: u32 = 37;

// DT_* constants now in shared module - re-export them
pub use crate::backend::elf::{
    DT_DEBUG, DT_INIT_ARRAY, DT_FINI_ARRAY,
    DT_INIT_ARRAYSZ, DT_FINI_ARRAYSZ,
    DT_SONAME, DT_RPATH, DT_RUNPATH, DT_RELACOUNT,
    DT_VERSYM, DT_VERNEED, DT_VERNEEDNUM,
};

pub const DF_BIND_NOW: i64 = 0x8;

// ── Type aliases ─────────────────────────────────────────────────────────
// Re-export shared types under the names the x86 linker already uses.

pub type SectionHeader = linker_common::Elf64Section;
pub type Symbol = linker_common::Elf64Symbol;
pub type Rela = linker_common::Elf64Rela;
pub type ElfObject = linker_common::Elf64Object;
pub type DynSymbol = linker_common::DynSymbol;

// ── Parsing functions ────────────────────────────────────────────────────
// Delegate to shared implementations.

pub fn parse_object(data: &[u8], source_name: &str) -> Result<ElfObject, String> {
    linker_common::parse_elf64_object(data, source_name, EM_X86_64)
}

pub fn parse_shared_library_symbols(data: &[u8], lib_name: &str) -> Result<Vec<DynSymbol>, String> {
    linker_common::parse_shared_library_symbols(data, lib_name)
}

pub fn parse_soname(data: &[u8]) -> Option<String> {
    linker_common::parse_soname(data)
}
