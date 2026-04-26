"""
UCO-Sensor — UCOBridgeRegistry  (M6.2 — 40 languages)
=======================================================
Central adapter registry with auto-dispatch by file extension.

Languages supported (40 total):
  Tier 1 — AST-based (tree-sitter):
    Python (.py .pyw .pyi)
    JavaScript (.js .jsx .mjs .cjs)
    TypeScript (.ts .tsx)
    Java (.java)
    Go (.go)

  Tier 2 — Regex-based (GenericRegexAdapter subclasses):
    C           (.c .h)
    C++         (.cpp .cc .cxx .hpp .hxx .h++ .c++ .cp .inl)
    Objective-C (.m .mm)
    C#          (.cs)
    Rust        (.rs)
    Ruby        (.rb .rake .gemspec .ru .rbw)
    Swift       (.swift)
    Kotlin      (.kt .kts)
    PHP         (.php .phtml .php3 .php4 .php5 .phps .phar)
    Scala       (.scala .sc .sbt)
    Groovy      (.groovy .gradle .gvy .gy)
    R           (.r .R .rmd .Rmd .rscript)
    Shell/Bash  (.sh .bash .zsh .ksh .fish .command)
    PowerShell  (.ps1 .psm1 .psd1 .pssc)
    Lua         (.lua)
    Perl        (.pl .pm .t .cgi .plx)
    MATLAB      (.matlab .octave)
    Haskell     (.hs .lhs)
    Erlang      (.erl .hrl)
    Elixir      (.ex .exs)
    F#          (.fs .fsx .fsi)
    OCaml       (.ml .mli)
    Clojure     (.clj .cljs .cljc .edn)
    Dart        (.dart)
    Julia       (.jl)
    Zig         (.zig)
    Nim         (.nim .nims)
    Crystal     (.cr)
    D           (.d .di)
    VB.NET      (.vb)
    Assembly    (.asm .s .S .nasm .nas)
    COBOL       (.cob .cbl .cpy .cobol)
    Fortran     (.f .for .f77 .f90 .f95 .f03 .f08)
    Tcl         (.tcl .tk .tclsh)
    Solidity    (.sol)
    HCL         (.hcl .tf .tfvars)

Fallback: unknown extensions → PythonAdapter (minimal mode).
"""
from __future__ import annotations
import sys
import threading
from pathlib import Path
from typing import Optional, Dict, List

from .base import LanguageAdapter

_ROOT = Path(__file__).resolve().parent.parent.parent / "frequency-engine"
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core.data_structures import MetricVector


# ── Extension → adapter-class-name mapping ────────────────────────────────────

_EXT_MAP: Dict[str, str] = {
    # ── Tier 1: AST-based ────────────────────────────────────────────────────
    ".py":      "PythonAdapter",
    ".pyw":     "PythonAdapter",
    ".pyi":     "PythonAdapter",
    ".js":      "JavaScriptAdapter",
    ".jsx":     "JavaScriptAdapter",
    ".mjs":     "JavaScriptAdapter",
    ".cjs":     "JavaScriptAdapter",
    ".ts":      "JavaScriptAdapter",
    ".tsx":     "JavaScriptAdapter",
    ".java":    "JavaAdapter",
    ".go":      "GoAdapter",

    # ── C family ─────────────────────────────────────────────────────────────
    ".c":       "CAdapter",
    ".h":       "CAdapter",
    ".cpp":     "CppAdapter",
    ".cc":      "CppAdapter",
    ".cxx":     "CppAdapter",
    ".hpp":     "CppAdapter",
    ".hxx":     "CppAdapter",
    ".h++":     "CppAdapter",
    ".c++":     "CppAdapter",
    ".cp":      "CppAdapter",
    ".inl":     "CppAdapter",
    ".m":       "ObjectiveCAdapter",
    ".mm":      "ObjectiveCAdapter",

    # ── C# ───────────────────────────────────────────────────────────────────
    ".cs":      "CSharpAdapter",

    # ── Rust ─────────────────────────────────────────────────────────────────
    ".rs":      "RustAdapter",

    # ── Ruby ─────────────────────────────────────────────────────────────────
    ".rb":      "RubyAdapter",
    ".rake":    "RubyAdapter",
    ".gemspec": "RubyAdapter",
    ".ru":      "RubyAdapter",
    ".rbw":     "RubyAdapter",

    # ── Swift ─────────────────────────────────────────────────────────────────
    ".swift":   "SwiftAdapter",

    # ── Kotlin ───────────────────────────────────────────────────────────────
    ".kt":      "KotlinAdapter",
    ".kts":     "KotlinAdapter",

    # ── PHP ───────────────────────────────────────────────────────────────────
    ".php":     "PhpAdapter",
    ".phtml":   "PhpAdapter",
    ".php3":    "PhpAdapter",
    ".php4":    "PhpAdapter",
    ".php5":    "PhpAdapter",
    ".phps":    "PhpAdapter",
    ".phar":    "PhpAdapter",

    # ── Scala / Groovy ────────────────────────────────────────────────────────
    ".scala":   "ScalaAdapter",
    ".sc":      "ScalaAdapter",
    ".sbt":     "ScalaAdapter",
    ".groovy":  "GroovyAdapter",
    ".gradle":  "GroovyAdapter",
    ".gvy":     "GroovyAdapter",
    ".gy":      "GroovyAdapter",

    # ── Scripting ────────────────────────────────────────────────────────────
    ".r":       "RAdapter",
    ".R":       "RAdapter",
    ".rmd":     "RAdapter",
    ".Rmd":     "RAdapter",
    ".rscript": "RAdapter",
    ".sh":      "ShellAdapter",
    ".bash":    "ShellAdapter",
    ".zsh":     "ShellAdapter",
    ".ksh":     "ShellAdapter",
    ".fish":    "ShellAdapter",
    ".command": "ShellAdapter",
    ".ps1":     "PowerShellAdapter",
    ".psm1":    "PowerShellAdapter",
    ".psd1":    "PowerShellAdapter",
    ".pssc":    "PowerShellAdapter",
    ".lua":     "LuaAdapter",
    ".pl":      "PerlAdapter",
    ".pm":      "PerlAdapter",
    ".t":       "PerlAdapter",
    ".cgi":     "PerlAdapter",
    ".plx":     "PerlAdapter",
    ".matlab":  "MatlabAdapter",
    ".octave":  "MatlabAdapter",

    # ── Functional ───────────────────────────────────────────────────────────
    ".hs":      "HaskellAdapter",
    ".lhs":     "HaskellAdapter",
    ".erl":     "ErlangAdapter",
    ".hrl":     "ErlangAdapter",
    ".ex":      "ElixirAdapter",
    ".exs":     "ElixirAdapter",
    ".fs":      "FSharpAdapter",
    ".fsx":     "FSharpAdapter",
    ".fsi":     "FSharpAdapter",
    ".ml":      "OCamlAdapter",
    ".mli":     "OCamlAdapter",
    ".clj":     "ClojureAdapter",
    ".cljs":    "ClojureAdapter",
    ".cljc":    "ClojureAdapter",
    ".edn":     "ClojureAdapter",

    # ── Modern systems ────────────────────────────────────────────────────────
    ".dart":    "DartAdapter",
    ".jl":      "JuliaAdapter",
    ".zig":     "ZigAdapter",
    ".nim":     "NimAdapter",
    ".nims":    "NimAdapter",
    ".cr":      "CrystalAdapter",
    ".d":       "DAdapter",
    ".di":      "DAdapter",

    # ── Domain / legacy ───────────────────────────────────────────────────────
    ".vb":      "VBNetAdapter",
    ".asm":     "AssemblyAdapter",
    ".s":       "AssemblyAdapter",
    ".S":       "AssemblyAdapter",
    ".nasm":    "AssemblyAdapter",
    ".nas":     "AssemblyAdapter",
    ".cob":     "CobolAdapter",
    ".cbl":     "CobolAdapter",
    ".cpy":     "CobolAdapter",
    ".cobol":   "CobolAdapter",
    ".f":       "FortranAdapter",
    ".for":     "FortranAdapter",
    ".f77":     "FortranAdapter",
    ".f90":     "FortranAdapter",
    ".f95":     "FortranAdapter",
    ".f03":     "FortranAdapter",
    ".f08":     "FortranAdapter",
    ".tcl":     "TclAdapter",
    ".tk":      "TclAdapter",
    ".tclsh":   "TclAdapter",
    ".sol":     "SolidityAdapter",
    ".hcl":     "HCLAdapter",
    ".tf":      "HCLAdapter",
    ".tfvars":  "HCLAdapter",
}

# ── Language display names ────────────────────────────────────────────────────

_LANGUAGE_NAMES: List[str] = [
    # Tier 1
    "python", "javascript", "typescript", "java", "go",
    # C family
    "c", "cpp", "objective_c",
    # Other compiled
    "csharp", "rust", "swift", "kotlin", "dart", "d",
    # JVM scripting
    "scala", "groovy",
    # Scripting / dynamic
    "ruby", "php", "lua", "perl", "r", "shell", "powershell", "matlab",
    # Functional
    "haskell", "erlang", "elixir", "fsharp", "ocaml", "clojure",
    # Modern systems
    "julia", "zig", "nim", "crystal",
    # Domain / legacy
    "vbnet", "assembly", "cobol", "fortran", "tcl", "solidity", "hcl",
]


def _load_adapter_by_name(class_name: str) -> LanguageAdapter:
    """Instantiate an adapter by class name. Raises ValueError on unknown name."""
    pkg = Path(__file__).resolve().parent
    if str(pkg.parent) not in sys.path:
        sys.path.insert(0, str(pkg.parent))

    # ── Tier 1: AST-based ────────────────────────────────────────────────────
    if class_name == "PythonAdapter":
        from lang_adapters.python_adapter import PythonAdapter
        return PythonAdapter(mode="full")

    if class_name == "JavaScriptAdapter":
        from lang_adapters.javascript import JavaScriptAdapter
        return JavaScriptAdapter()

    if class_name == "JavaAdapter":
        from lang_adapters.java import JavaAdapter
        return JavaAdapter()

    if class_name == "GoAdapter":
        from lang_adapters.golang import GoAdapter
        return GoAdapter()

    # ── C family ─────────────────────────────────────────────────────────────
    if class_name in ("CAdapter", "CppAdapter", "ObjectiveCAdapter"):
        from lang_adapters.c_family import CAdapter, CppAdapter, ObjectiveCAdapter
        return {"CAdapter": CAdapter, "CppAdapter": CppAdapter,
                "ObjectiveCAdapter": ObjectiveCAdapter}[class_name]()

    # ── C# ───────────────────────────────────────────────────────────────────
    if class_name == "CSharpAdapter":
        from lang_adapters.csharp import CSharpAdapter
        return CSharpAdapter()

    # ── Rust ─────────────────────────────────────────────────────────────────
    if class_name == "RustAdapter":
        from lang_adapters.rust import RustAdapter
        return RustAdapter()

    # ── Ruby ─────────────────────────────────────────────────────────────────
    if class_name == "RubyAdapter":
        from lang_adapters.ruby import RubyAdapter
        return RubyAdapter()

    # ── Swift ─────────────────────────────────────────────────────────────────
    if class_name == "SwiftAdapter":
        from lang_adapters.swift import SwiftAdapter
        return SwiftAdapter()

    # ── Kotlin ───────────────────────────────────────────────────────────────
    if class_name == "KotlinAdapter":
        from lang_adapters.kotlin import KotlinAdapter
        return KotlinAdapter()

    # ── PHP ───────────────────────────────────────────────────────────────────
    if class_name == "PhpAdapter":
        from lang_adapters.php import PhpAdapter
        return PhpAdapter()

    # ── Scala / Groovy ────────────────────────────────────────────────────────
    if class_name in ("ScalaAdapter", "GroovyAdapter"):
        from lang_adapters.scala import ScalaAdapter, GroovyAdapter
        return ScalaAdapter() if class_name == "ScalaAdapter" else GroovyAdapter()

    # ── Scripting ────────────────────────────────────────────────────────────
    if class_name in ("RAdapter", "ShellAdapter", "PowerShellAdapter",
                      "LuaAdapter", "PerlAdapter", "MatlabAdapter"):
        from lang_adapters.scripting_langs import (
            RAdapter, ShellAdapter, PowerShellAdapter,
            LuaAdapter, PerlAdapter, MatlabAdapter,
        )
        _s = {
            "RAdapter": RAdapter, "ShellAdapter": ShellAdapter,
            "PowerShellAdapter": PowerShellAdapter, "LuaAdapter": LuaAdapter,
            "PerlAdapter": PerlAdapter, "MatlabAdapter": MatlabAdapter,
        }
        return _s[class_name]()

    # ── Functional ───────────────────────────────────────────────────────────
    if class_name in ("HaskellAdapter", "ErlangAdapter", "ElixirAdapter",
                      "FSharpAdapter", "OCamlAdapter", "ClojureAdapter"):
        from lang_adapters.functional_langs import (
            HaskellAdapter, ErlangAdapter, ElixirAdapter,
            FSharpAdapter, OCamlAdapter, ClojureAdapter,
        )
        _f = {
            "HaskellAdapter": HaskellAdapter, "ErlangAdapter": ErlangAdapter,
            "ElixirAdapter": ElixirAdapter, "FSharpAdapter": FSharpAdapter,
            "OCamlAdapter": OCamlAdapter, "ClojureAdapter": ClojureAdapter,
        }
        return _f[class_name]()

    # ── Modern systems ────────────────────────────────────────────────────────
    if class_name in ("DartAdapter", "JuliaAdapter", "ZigAdapter",
                      "NimAdapter", "CrystalAdapter", "DAdapter"):
        from lang_adapters.modern_systems import (
            DartAdapter, JuliaAdapter, ZigAdapter,
            NimAdapter, CrystalAdapter, DAdapter,
        )
        _m = {
            "DartAdapter": DartAdapter, "JuliaAdapter": JuliaAdapter,
            "ZigAdapter": ZigAdapter, "NimAdapter": NimAdapter,
            "CrystalAdapter": CrystalAdapter, "DAdapter": DAdapter,
        }
        return _m[class_name]()

    # ── Domain / legacy ───────────────────────────────────────────────────────
    if class_name in ("VBNetAdapter", "AssemblyAdapter", "CobolAdapter",
                      "FortranAdapter", "TclAdapter", "SolidityAdapter",
                      "HCLAdapter"):
        from lang_adapters.domain_langs import (
            VBNetAdapter, AssemblyAdapter, CobolAdapter,
            FortranAdapter, TclAdapter, SolidityAdapter, HCLAdapter,
        )
        _d = {
            "VBNetAdapter": VBNetAdapter, "AssemblyAdapter": AssemblyAdapter,
            "CobolAdapter": CobolAdapter, "FortranAdapter": FortranAdapter,
            "TclAdapter": TclAdapter, "SolidityAdapter": SolidityAdapter,
            "HCLAdapter": HCLAdapter,
        }
        return _d[class_name]()

    raise ValueError(f"Unknown adapter class: {class_name!r}")


# ── Registry class ────────────────────────────────────────────────────────────

class UCOBridgeRegistry:
    """
    Central registry with lazy-loaded adapters, dispatched by file extension.

    Thread-safe: adapters are cached per class name with double-checked locking.
    Unknown extensions fall back to PythonAdapter (minimal mode).
    """

    def __init__(self) -> None:
        self._adapters: Dict[str, LanguageAdapter] = {}
        self._lock = threading.Lock()

    def get_adapter(self, file_extension: str) -> LanguageAdapter:
        ext = file_extension.lower()
        if not ext.startswith("."):
            ext = f".{ext}"
        class_name = _EXT_MAP.get(ext, "PythonAdapter")

        # Fast path (no lock when already cached)
        if class_name in self._adapters:
            return self._adapters[class_name]

        with self._lock:
            if class_name not in self._adapters:
                try:
                    self._adapters[class_name] = _load_adapter_by_name(class_name)
                except Exception:
                    from lang_adapters.python_adapter import PythonAdapter
                    self._adapters[class_name] = PythonAdapter(mode="minimal")

        return self._adapters[class_name]

    def analyze(
        self,
        source:         str,
        file_extension: str           = ".py",
        module_id:      str           = "unknown",
        commit_hash:    str           = "0000000",
        timestamp:      Optional[float] = None,
    ) -> MetricVector:
        """
        Analyse source and return MetricVector using the correct adapter.

        Args:
            source:         Source code as string.
            file_extension: File extension (".py", ".rs", ".sol", …).
            module_id:      Module / file identifier.
            commit_hash:    VCS commit hash.
            timestamp:      Unix timestamp (defaults to now).

        Returns:
            MetricVector with 9 UCO channels populated.
        """
        adapter = self.get_adapter(file_extension)
        return adapter.compute_metrics(
            source         = source,
            module_id      = module_id,
            commit_hash    = commit_hash,
            timestamp      = timestamp,
            file_extension = file_extension,
        )

    def supported_extensions(self) -> List[str]:
        """Sorted list of all registered file extensions."""
        return sorted(_EXT_MAP.keys())

    def supported_languages(self) -> List[str]:
        """Ordered list of all supported language display names (40 total)."""
        return list(_LANGUAGE_NAMES)

    def language_for(self, file_extension: str) -> str:
        """Return display name of the language for a given extension."""
        ext = file_extension.lower().lstrip(".")
        # Build reverse map on demand
        _quick: Dict[str, str] = {
            "py": "python", "pyw": "python", "pyi": "python",
            "js": "javascript", "jsx": "javascript",
            "mjs": "javascript", "cjs": "javascript",
            "ts": "typescript", "tsx": "typescript",
            "java": "java", "go": "go",
            "c": "c", "h": "c",
            "cpp": "cpp", "cc": "cpp", "cxx": "cpp",
            "hpp": "cpp", "hxx": "cpp", "h++": "cpp",
            "c++": "cpp", "cp": "cpp", "inl": "cpp",
            "m": "objective_c", "mm": "objective_c",
            "cs": "csharp",
            "rs": "rust",
            "rb": "ruby", "rake": "ruby", "gemspec": "ruby",
            "ru": "ruby", "rbw": "ruby",
            "swift": "swift",
            "kt": "kotlin", "kts": "kotlin",
            "php": "php", "phtml": "php", "php3": "php",
            "php4": "php", "php5": "php", "phps": "php", "phar": "php",
            "scala": "scala", "sc": "scala", "sbt": "scala",
            "groovy": "groovy", "gradle": "groovy",
            "gvy": "groovy", "gy": "groovy",
            "r": "r", "rmd": "r", "rscript": "r",
            "sh": "shell", "bash": "shell", "zsh": "shell",
            "ksh": "shell", "fish": "shell", "command": "shell",
            "ps1": "powershell", "psm1": "powershell",
            "psd1": "powershell", "pssc": "powershell",
            "lua": "lua",
            "pl": "perl", "pm": "perl", "t": "perl",
            "cgi": "perl", "plx": "perl",
            "matlab": "matlab", "octave": "matlab",
            "hs": "haskell", "lhs": "haskell",
            "erl": "erlang", "hrl": "erlang",
            "ex": "elixir", "exs": "elixir",
            "fs": "fsharp", "fsx": "fsharp", "fsi": "fsharp",
            "ml": "ocaml", "mli": "ocaml",
            "clj": "clojure", "cljs": "clojure",
            "cljc": "clojure", "edn": "clojure",
            "dart": "dart",
            "jl": "julia",
            "zig": "zig",
            "nim": "nim", "nims": "nim",
            "cr": "crystal",
            "d": "d", "di": "d",
            "vb": "vbnet",
            "asm": "assembly", "s": "assembly",
            "nasm": "assembly", "nas": "assembly",
            "cob": "cobol", "cbl": "cobol",
            "cpy": "cobol", "cobol": "cobol",
            "f": "fortran", "for": "fortran",
            "f77": "fortran", "f90": "fortran",
            "f95": "fortran", "f03": "fortran", "f08": "fortran",
            "tcl": "tcl", "tk": "tcl", "tclsh": "tcl",
            "sol": "solidity",
            "hcl": "hcl", "tf": "hcl", "tfvars": "hcl",
        }
        return _quick.get(ext, "unknown")


# ── Singleton ─────────────────────────────────────────────────────────────────

_REGISTRY: Optional[UCOBridgeRegistry] = None
_REGISTRY_LOCK = threading.Lock()


def get_registry() -> UCOBridgeRegistry:
    """
    Return the global UCOBridgeRegistry singleton (thread-safe, lazy init).

    BUG-03: double-checked locking prevents race during multi-threaded startup.
    """
    global _REGISTRY
    if _REGISTRY is None:
        with _REGISTRY_LOCK:
            if _REGISTRY is None:
                _REGISTRY = UCOBridgeRegistry()
    return _REGISTRY


def reset_registry() -> None:
    """
    Force recreation of the singleton on next get_registry() call.

    Used in tests and when adapters are dynamically registered.
    """
    global _REGISTRY
    with _REGISTRY_LOCK:
        _REGISTRY = None
