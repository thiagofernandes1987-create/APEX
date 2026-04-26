"""
UCO-Sensor — C-family Adapters  (M6.2)
========================================
Covers: C (.c .h), C++ (.cpp .cc .cxx .hpp .hxx .h++ .c++ .cp .inl),
        Objective-C (.m .mm).

All three share:
  • C-style comments: // and /* */
  • #include for imports
  • Brace-delimited blocks for dead-code detection
  • while(1)/for(;;) as infinite-loop patterns

C++ adds: catch / template / operator overloads / namespace
Objective-C adds: @interface @implementation @selector messaging syntax
"""
from __future__ import annotations
import re
from .generic import GenericRegexAdapter


class CAdapter(GenericRegexAdapter):
    """C language adapter (.c, .h)."""

    LANGUAGE   = "c"
    EXTENSIONS = (".c", ".h")

    # C: #include "..." or #include <...>
    IMPORT_RE = re.compile(
        r'^\s*#\s*include\s*[<"]',
        re.MULTILINE,
    )

    # C functions: type name( — includes pointer types like char *foo(
    FUNCTION_RE = re.compile(
        r'\b(?:void|int|long|short|char|float|double|unsigned|signed|size_t'
        r'|uint8_t|uint16_t|uint32_t|uint64_t|int8_t|int16_t|int32_t|int64_t'
        r'|bool|_Bool|auto|static|inline|extern)\s+\*?\s*[a-zA-Z_]\w*\s*\(',
        re.MULTILINE,
    )

    # C structs, unions, enums, typedefs
    CLASS_RE = re.compile(
        r'\b(?:struct|union|enum|typedef\s+struct|typedef\s+union)\s+[a-zA-Z_]\w*',
        re.MULTILINE,
    )

    # C CC: if, else if, for, while, do, switch, case, ?, &&, ||
    CC_RE = re.compile(
        r'\b(?:if|else\s+if|for|while|do|switch|case|goto)\b'
        r'|&&|\|\||\?(?!\?)',
        re.MULTILINE,
    )

    # C infinite loops: while(1), while(true), for(;;)
    INFINITE_LOOP_RE = re.compile(
        r'\bwhile\s*\(\s*(?:1|true|TRUE)\s*\)'
        r'|\bfor\s*\(\s*;;\s*\)',
        re.MULTILINE,
    )

    TERMINAL_RE = re.compile(
        r'^\s*(?:return|goto|break|continue|exit|abort)\b',
        re.MULTILINE,
    )

    def _comment_prefix(self) -> str:
        return '//'


class CppAdapter(CAdapter):
    """C++ language adapter (.cpp, .cc, .cxx, .hpp, .hxx, .h++, .c++, .cp, .inl)."""

    LANGUAGE   = "cpp"
    EXTENSIONS = (".cpp", ".cc", ".cxx", ".hpp", ".hxx", ".h++", ".c++", ".cp", ".inl")

    # C++ adds: catch, template, namespace, new, delete, throw, constexpr
    CC_RE = re.compile(
        r'\b(?:if|else\s+if|for|while|do|switch|case|catch|goto'
        r'|co_await|co_yield)\b'
        r'|&&|\|\||\?(?!\?)',
        re.MULTILINE,
    )

    # C++ classes/structs/templates/namespaces
    CLASS_RE = re.compile(
        r'\b(?:class|struct|union|enum(?:\s+class)?|namespace|template)\s+[a-zA-Z_]\w*',
        re.MULTILINE,
    )

    # C++ functions: also handles return types with :: and templates
    FUNCTION_RE = re.compile(
        r'\b(?:void|int|long|short|char|float|double|unsigned|signed|bool|auto'
        r'|size_t|std::\w+|string|vector|map|set|list|pair|unique_ptr|shared_ptr'
        r'|explicit|virtual|override|static|inline|constexpr|const)\s+'
        r'\*?\s*(?:\w+::)*[a-zA-Z_]\w*\s*\(',
        re.MULTILINE,
    )

    TERMINAL_RE = re.compile(
        r'^\s*(?:return|throw|goto|break|continue|exit|abort|std::terminate)\b',
        re.MULTILINE,
    )


class ObjectiveCAdapter(CAdapter):
    """Objective-C adapter (.m, .mm)."""

    LANGUAGE   = "objective_c"
    EXTENSIONS = (".m", ".mm")

    # ObjC imports: #import and #include
    IMPORT_RE = re.compile(
        r'^\s*#\s*(?:import|include)\s*[<"]',
        re.MULTILINE,
    )

    # ObjC CC: C conditions + @try/@catch + nil checks
    CC_RE = re.compile(
        r'\b(?:if|else\s+if|for|while|do|switch|case|@catch|@finally)\b'
        r'|&&|\|\||\?(?!\?)',
        re.MULTILINE,
    )

    # ObjC methods: - (returntype) methodName:  or + (returntype) methodName:
    FUNCTION_RE = re.compile(
        r'^[-+]\s*\([^)]+\)\s*[a-zA-Z_]\w*',
        re.MULTILINE,
    )

    # ObjC classes: @interface, @implementation, @protocol
    CLASS_RE = re.compile(
        r'@(?:interface|implementation|protocol)\s+[a-zA-Z_]\w*',
        re.MULTILINE,
    )

    TERMINAL_RE = re.compile(
        r'^\s*(?:return|@throw|break|continue|exit|abort)\b',
        re.MULTILINE,
    )
