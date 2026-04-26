"""
UCO-Sensor — Domain-specific Language Adapters  (M6.2)
=======================================================
Covers:
  VB.NET      (.vb)
  Assembly    (.asm .s .S .nasm)
  COBOL       (.cob .cbl .cpy .cobol)
  Fortran     (.f .for .f90 .f95 .f03 .f08 .f77)
  Tcl         (.tcl .tk)
  Solidity    (.sol)
  HCL/Terraform (.hcl .tf)

These languages serve critical roles in enterprise, embedded, blockchain,
and infrastructure domains. UCO metrics are calibrated to their unique
structural characteristics.
"""
from __future__ import annotations
import re
from .generic import GenericRegexAdapter


# ── VB.NET ────────────────────────────────────────────────────────────────────

class VBNetAdapter(GenericRegexAdapter):
    """
    VB.NET adapter for .vb files.

    VB.NET-specific calibration:
      • `If/ElseIf/Else/End If`, `For/Next`, `For Each/Next`,
        `While/End While`, `Do While/Loop`, `Select Case/End Select`
      • `AndAlso`, `OrElse`, `And`, `Or` = +1 CC each
      • `Try/Catch/Finally` = +1 CC
      • `Imports` = dependency
      • `Sub`, `Function`, `Property Get/Set` = callables
      • `Class`, `Module`, `Interface`, `Structure`, `Enum` = types
      • `Do While True` / `Do ... Loop` = ILR when no `Exit Do`
      • Comments: `'` (single-quote only)
    """
    LANGUAGE   = "vbnet"
    EXTENSIONS = (".vb",)

    LINE_COMMENT_RE  = re.compile(r"'[^\n]*",              re.MULTILINE)
    BLOCK_COMMENT_RE = re.compile(r'(?!x)x',              re.MULTILINE)
    STRING_RE        = re.compile(r'"(?:[^"]|"")*"',       re.DOTALL)

    CC_RE = re.compile(
        r'\b(?:If|ElseIf|For|For\s+Each|While|Do\s+While|Do\s+Until'
        r'|Select\s+Case|Case|Catch|AndAlso|OrElse|And|Or)\b',
        re.MULTILINE | re.IGNORECASE,
    )

    IMPORT_RE = re.compile(
        r'^\s*Imports\s+[a-zA-Z_]',
        re.MULTILINE | re.IGNORECASE,
    )

    FUNCTION_RE = re.compile(
        r'^\s*(?:Public|Private|Protected|Friend|Shared|Overrides|Overridable'
        r'|MustOverride|Static|Async)?\s*'
        r'(?:Sub|Function|Property)\s+[a-zA-Z_]\w*',
        re.MULTILINE | re.IGNORECASE,
    )

    CLASS_RE = re.compile(
        r'^\s*(?:Public|Private|Friend|MustInherit|NotInheritable|Partial)?\s*'
        r'(?:Class|Module|Interface|Structure|Enum)\s+[a-zA-Z_]\w*',
        re.MULTILINE | re.IGNORECASE,
    )

    INFINITE_LOOP_RE = re.compile(
        r'\bDo\s+While\s+True\b'
        r'|\bDo\b(?:(?!Loop).)*\bLoop\b',
        re.MULTILINE | re.IGNORECASE | re.DOTALL,
    )

    BREAK_RE = re.compile(
        r'\b(?:Return|Exit\s+(?:Sub|Function|Do|For|While|Try)|Throw|End)\b',
        re.MULTILINE | re.IGNORECASE,
    )

    TERMINAL_RE = re.compile(
        r'^\s*(?:Return|Exit\s+\w+|Throw|End\s+\w+)\b',
        re.MULTILINE | re.IGNORECASE,
    )

    def _comment_prefix(self) -> str:
        return "'"


# ── Assembly ──────────────────────────────────────────────────────────────────

class AssemblyAdapter(GenericRegexAdapter):
    """
    Assembly adapter for .asm, .s, .S, .nasm files.

    Assembly-specific calibration:
      • Branching: `jmp`, `je`, `jne`, `jz`, `jnz`, `jl`, `jle`, `jg`, `jge`
        `jb`, `jbe`, `ja`, `jae`, `js`, `jns`, `jo`, `jno`, `jc`, `jnc` = CC
      • Infinite loops: unconditional `jmp` to a label that precedes it
        (detected by pattern `jmp\\s+\\w+` without a nearby `ret`/`hlt`)
      • `call` = function invocation (not a branch but counted for DI)
      • `section .text`, `segment .text`, `PROC`, `ENDP` = structural
      • Comments: `;` (x86/NASM), `@` and `//` (ARM)
      • `%include`, `INCLUDE` = imports
      • LOC is primary complexity signal; CC approximation via branch count
    """
    LANGUAGE   = "assembly"
    EXTENSIONS = (".asm", ".s", ".S", ".nasm", ".nas")

    LINE_COMMENT_RE  = re.compile(r';[^\n]*|@[^\n]*',     re.MULTILINE)
    BLOCK_COMMENT_RE = re.compile(r'/\*.*?\*/',            re.DOTALL)
    STRING_RE        = re.compile(
        r'"(?:[^"\\]|\\.)*"'
        r"|'(?:[^'\\]|\\.)*'",
        re.DOTALL,
    )

    CC_RE = re.compile(
        r'\b(?:j[a-zA-Z]{1,3})\s+\w+'   # all jXX branch instructions
        r'|\bcbz\b|\bcbnz\b|\btbz\b|\btbnz\b'   # ARM conditional branches
        r'|\bb\.\w+\s',                  # ARM b.cond
        re.MULTILINE | re.IGNORECASE,
    )

    IMPORT_RE = re.compile(
        r'^\s*(?:%include|INCLUDE|\.include|\.import)\b',
        re.MULTILINE | re.IGNORECASE,
    )

    FUNCTION_RE = re.compile(
        r'^\s*(?:[a-zA-Z_]\w*:(?!\s*=)'  # label at column 0
        r'|(?:PROC|proc)\s+[a-zA-Z_]\w*)',
        re.MULTILINE,
    )

    CLASS_RE = re.compile(
        r'^\s*(?:section|segment|SEGMENT|SECTION)\s+\.\w+',
        re.MULTILINE | re.IGNORECASE,
    )

    INFINITE_LOOP_RE = re.compile(
        r'\bjmp\s+[a-zA-Z_]\w*',         # any unconditional jmp (approximation)
        re.MULTILINE | re.IGNORECASE,
    )

    BREAK_RE = re.compile(
        r'\b(?:ret|hlt|iret|iretd|iretq|bx\s+lr|RET|HLT)\b',
        re.MULTILINE,
    )

    TERMINAL_RE = re.compile(
        r'^\s*(?:ret|hlt|iret)\b',
        re.MULTILINE | re.IGNORECASE,
    )

    def _comment_prefix(self) -> str:
        return ';'


# ── COBOL ─────────────────────────────────────────────────────────────────────

class CobolAdapter(GenericRegexAdapter):
    """
    COBOL adapter for .cob, .cbl, .cpy, .cobol files.

    COBOL-specific calibration:
      • `IF/THEN/ELSE/END-IF`, `EVALUATE/WHEN/ALSO/END-EVALUATE` = CC
      • `PERFORM ... UNTIL`, `PERFORM ... VARYING`, `PERFORM n TIMES` = CC
      • `AND`, `OR`, `NOT` in conditions = +1 CC
      • `COPY`, `CALL` (external program) = imports
      • `PARAGRAPH.` (period-terminated paragraphs) = functions
      • `DIVISION`, `SECTION` = structural units (class proxy)
      • `PERFORM FOREVER` / `PERFORM ... UNTIL 1 = 1` = ILR
      • Comments: `*` in column 7 (fixed-format) or `*>` (free-format)
    """
    LANGUAGE   = "cobol"
    EXTENSIONS = (".cob", ".cbl", ".cpy", ".cobol")

    LINE_COMMENT_RE  = re.compile(r'^\*>?[^\n]*|^\s{6}\*[^\n]*', re.MULTILINE)
    BLOCK_COMMENT_RE = re.compile(r'(?!x)x',                      re.MULTILINE)
    STRING_RE        = re.compile(
        r'"[^"]*"'
        r"|'[^']*'",
        re.DOTALL,
    )

    CC_RE = re.compile(
        r'\b(?:IF|THEN|ELSE|EVALUATE|WHEN|ALSO|PERFORM|VARYING|UNTIL|TIMES)\b'
        r'|\bAND\b|\bOR\b|\bNOT\b',
        re.MULTILINE | re.IGNORECASE,
    )

    IMPORT_RE = re.compile(
        r'^\s*(?:COPY|CALL)\s+["\']?[a-zA-Z_\-]\w*',
        re.MULTILINE | re.IGNORECASE,
    )

    FUNCTION_RE = re.compile(
        r'^[A-Z][A-Z0-9\-]*\.\s*$',       # paragraph name (period-terminated)
        re.MULTILINE,
    )

    CLASS_RE = re.compile(
        r'\b(?:IDENTIFICATION\s+DIVISION|DATA\s+DIVISION'
        r'|PROCEDURE\s+DIVISION|ENVIRONMENT\s+DIVISION'
        r'|[A-Z][A-Z0-9\-]+\s+SECTION)\b',
        re.MULTILINE | re.IGNORECASE,
    )

    INFINITE_LOOP_RE = re.compile(
        r'\bPERFORM\s+FOREVER\b'
        r'|\bPERFORM\s+UNTIL\s+1\s*=\s*1\b',
        re.MULTILINE | re.IGNORECASE,
    )

    TERMINAL_RE = re.compile(
        r'^\s*(?:STOP\s+RUN|GO\s+TO|EXIT\s+PROGRAM|GOBACK)\b',
        re.MULTILINE | re.IGNORECASE,
    )

    def _comment_prefix(self) -> str:
        return '*'


# ── Fortran ───────────────────────────────────────────────────────────────────

class FortranAdapter(GenericRegexAdapter):
    """
    Fortran adapter for .f, .for, .f77, .f90, .f95, .f03, .f08 files.

    Fortran-specific calibration:
      • `IF/THEN/ELSEIF/ELSE/END IF`, `DO/END DO`, `SELECT CASE/END SELECT`
      • `.AND.`, `.OR.`, `.NOT.`, `.EQV.`, `.NEQV.` = +1 CC each
      • `DO` without index (Fortran 77: `DO 10`) = loop = +1 CC
      • `USE` module = import
      • `SUBROUTINE`, `FUNCTION`, `PROGRAM`, `ENTRY` = callables
      • `MODULE`, `INTERFACE`, `TYPE` = type declarations
      • `DO WHILE (.TRUE.)` = ILR
      • Comments: `!` (free-format F90+), `C`/`c` or `*` in col 1 (fixed)
    """
    LANGUAGE   = "fortran"
    EXTENSIONS = (".f", ".for", ".f77", ".f90", ".f95", ".f03", ".f08")

    LINE_COMMENT_RE  = re.compile(r'![^\n]*|^[Cc\*][^\n]*', re.MULTILINE)
    BLOCK_COMMENT_RE = re.compile(r'(?!x)x',                re.MULTILINE)
    STRING_RE        = re.compile(
        r"'[^'\n]*'"
        r'|"[^"\n]*"',
        re.DOTALL,
    )

    CC_RE = re.compile(
        r'\b(?:IF|ELSEIF|ELSE\s+IF|DO|DO\s+WHILE|SELECT\s+CASE|CASE)\b'
        r'|\.AND\.|\.OR\.|\.NOT\.|\.EQV\.|\.NEQV\.',
        re.MULTILINE | re.IGNORECASE,
    )

    IMPORT_RE = re.compile(
        r'^\s*USE\s+[a-zA-Z_]',
        re.MULTILINE | re.IGNORECASE,
    )

    FUNCTION_RE = re.compile(
        r'^\s*(?:SUBROUTINE|FUNCTION|PROGRAM|ENTRY|RECURSIVE\s+(?:SUBROUTINE|FUNCTION))\s+[a-zA-Z_]\w*',
        re.MULTILINE | re.IGNORECASE,
    )

    CLASS_RE = re.compile(
        r'^\s*(?:MODULE|INTERFACE|TYPE(?!\s+IS)|ABSTRACT\s+INTERFACE)\s+[a-zA-Z_]\w*',
        re.MULTILINE | re.IGNORECASE,
    )

    INFINITE_LOOP_RE = re.compile(
        r'\bDO\s+WHILE\s*\(\s*\.TRUE\.\s*\)'
        r'|\bDO\b(?!\s+\w+\s*=)',    # DO without index variable = infinite
        re.MULTILINE | re.IGNORECASE,
    )

    TERMINAL_RE = re.compile(
        r'^\s*(?:RETURN|STOP|END\s+(?:SUBROUTINE|FUNCTION|PROGRAM)|GOTO)\b',
        re.MULTILINE | re.IGNORECASE,
    )

    def _comment_prefix(self) -> str:
        return '!'


# ── Tcl ───────────────────────────────────────────────────────────────────────

class TclAdapter(GenericRegexAdapter):
    """
    Tcl/Tk adapter for .tcl, .tk files.

    Tcl-specific calibration:
      • `if/elseif`, `while`, `for`, `foreach`, `switch` = CC
      • `&&`, `||`, `?` in expr = +1 CC
      • `package require`, `source`, `load` = imports
      • `proc` = function declaration
      • `namespace eval` = class/module proxy
      • `while {1}` / `while {true}` = ILR
      • Comments: `#` only (Tcl has no block comments)
    """
    LANGUAGE   = "tcl"
    EXTENSIONS = (".tcl", ".tk", ".tclsh")

    LINE_COMMENT_RE  = re.compile(r'#[^\n]*',    re.MULTILINE)
    BLOCK_COMMENT_RE = re.compile(r'(?!x)x',     re.MULTILINE)
    STRING_RE        = re.compile(
        r'"(?:[^"\\]|\\.)*"'
        r'|\{[^{}]*\}',              # braced strings (best-effort, no nesting)
        re.DOTALL,
    )

    CC_RE = re.compile(
        r'\b(?:if|elseif|while|for|foreach|switch)\b'
        r'|&&|\|\|',
        re.MULTILINE,
    )

    IMPORT_RE = re.compile(
        r'^\s*(?:package\s+require|source|load)\s+',
        re.MULTILINE,
    )

    FUNCTION_RE = re.compile(
        r'^\s*proc\s+(?:[a-zA-Z_:]\w*::)*[a-zA-Z_]\w*\s+\{',
        re.MULTILINE,
    )

    CLASS_RE = re.compile(
        r'^\s*namespace\s+eval\s+[a-zA-Z_:]\w*',
        re.MULTILINE,
    )

    INFINITE_LOOP_RE = re.compile(
        r'\bwhile\s+\{1\}'
        r'|\bwhile\s+\{true\}'
        r'|\bwhile\s+true\b',
        re.MULTILINE,
    )

    TERMINAL_RE = re.compile(
        r'^\s*(?:return|error|break|continue|exit)\b',
        re.MULTILINE,
    )

    def _comment_prefix(self) -> str:
        return '#'


# ── Solidity ──────────────────────────────────────────────────────────────────

class SolidityAdapter(GenericRegexAdapter):
    """
    Solidity adapter for .sol files (smart contracts).

    Solidity-specific calibration:
      • `if/else`, `for`, `while`, `do`, `require`, `revert` = CC
      • `&&`, `||`, ternary `?:` = +1 CC
      • `require(cond, msg)` and `if (!cond) revert(...)` are equivalent — both counted
      • `modifier` with condition = +1 CC
      • `import` = dependency (ABI coupling)
      • `function`, `fallback`, `receive`, `constructor` = callables
      • `contract`, `abstract contract`, `interface`, `library`, `struct`, `enum` = types
      • `while (true)` = ILR (dangerous in EVM — gas exhaustion)
      • Security: `assembly {}` blocks counted as elevated ILR
      • Comments: `//` (line), `/* */` (block), `///` (NatSpec)
    """
    LANGUAGE   = "solidity"
    EXTENSIONS = (".sol",)

    LINE_COMMENT_RE  = re.compile(r'//[^\n]*',   re.MULTILINE)
    BLOCK_COMMENT_RE = re.compile(r'/\*.*?\*/',  re.DOTALL)
    STRING_RE        = re.compile(
        r'"(?:[^"\\]|\\.)*"'
        r"|'(?:[^'\\]|\\.)*'",
        re.DOTALL,
    )

    CC_RE = re.compile(
        r'\b(?:if|else\s+if|for|while|do|require|revert|try|catch)\b'
        r'|&&|\|\||\?(?!\?)',
        re.MULTILINE,
    )

    IMPORT_RE = re.compile(
        r'^\s*import\s+["\']',
        re.MULTILINE,
    )

    FUNCTION_RE = re.compile(
        r'\b(?:function|fallback|receive|constructor)\s*(?:[a-zA-Z_]\w*)?\s*\(',
        re.MULTILINE,
    )

    CLASS_RE = re.compile(
        r'\b(?:contract|abstract\s+contract|interface|library|struct|enum)\s+[a-zA-Z_]\w*',
        re.MULTILINE,
    )

    INFINITE_LOOP_RE = re.compile(
        r'\bwhile\s*\(\s*true\s*\)'
        r'|\bassembly\s*\{',        # inline assembly = elevated risk
        re.MULTILINE,
    )

    TERMINAL_RE = re.compile(
        r'^\s*(?:return|revert|selfdestruct|require(?=\s*\(false))\b',
        re.MULTILINE,
    )

    def _comment_prefix(self) -> str:
        return '//'


# ── HCL / Terraform ───────────────────────────────────────────────────────────

class HCLAdapter(GenericRegexAdapter):
    """
    HCL (HashiCorp Configuration Language) adapter for .hcl, .tf files.

    Used by Terraform, Packer, Vault, Consul configurations.

    HCL-specific calibration:
      • `count`, `for_each` on resources = loop complexity = +1 CC
      • `for` expressions in locals = +1 CC
      • `if` in conditional expressions = +1 CC
      • `dynamic` blocks = structural complexity = +1 CC
      • `&&`, `||`, `? :` in expressions = +1 CC
      • `module`, `data` = dependency references (imports)
      • `resource`, `module`, `output`, `variable` = structural declarations
      • No functions in traditional sense — `locals` blocks proxy for functions
      • Circular dependency = DSM cyclic ratio signal
      • Comments: `#` (line), `//` (line), `/* */` (block)
    """
    LANGUAGE   = "hcl"
    EXTENSIONS = (".hcl", ".tf", ".tfvars")

    LINE_COMMENT_RE  = re.compile(r'(?:#|//)[^\n]*',  re.MULTILINE)
    BLOCK_COMMENT_RE = re.compile(r'/\*.*?\*/',        re.DOTALL)
    STRING_RE        = re.compile(
        r'"(?:[^"\\$]|\\.|\$\{[^}]*\})*"',   # HCL interpolation ${...}
        re.DOTALL,
    )

    CC_RE = re.compile(
        r'\b(?:for|if|count|for_each|dynamic)\b'
        r'|&&|\|\||\?(?!\?)',
        re.MULTILINE,
    )

    IMPORT_RE = re.compile(
        r'^\s*(?:module|data)\s+"[^"]+"\s+"[^"]+"\s*\{',
        re.MULTILINE,
    )

    FUNCTION_RE = re.compile(
        r'^\s*locals\s*\{',          # locals block = function proxy
        re.MULTILINE,
    )

    CLASS_RE = re.compile(
        r'^\s*(?:resource|module|output|variable|provider|terraform)\s*"[^"]*"',
        re.MULTILINE,
    )

    INFINITE_LOOP_RE = re.compile(
        r'(?!x)x',                   # HCL has no infinite loops
        re.MULTILINE,
    )

    TERMINAL_RE = re.compile(
        r'(?!x)x',                   # HCL has no terminals
        re.MULTILINE,
    )

    def _comment_prefix(self) -> str:
        return '#'
