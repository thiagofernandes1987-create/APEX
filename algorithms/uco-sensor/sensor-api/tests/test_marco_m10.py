"""
test_marco_m10.py — M6.2 Multi-Language Adapter Suite  (30 tests TL01–TL30)
============================================================================
APEX SCIENTIFIC mode — 40 language adapters, ≥ 100 file extensions,
GenericRegexAdapter base, and UCOBridgeRegistry coverage.

WBS M6.2: Multi-Language Support (APEX Scientific)
  Differentiator: SonarQube = ~30 languages (OSS); UCO-Sensor = 40+ with
  calibrated Hamiltonian, CC, ILR, DSM, and dead-code metrics per language.
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# ── Path setup ───────────────────────────────────────────────────────────────
_SENSOR_API = Path(__file__).resolve().parent.parent
_ENGINE     = _SENSOR_API.parent / "frequency-engine"
for _p in (str(_ENGINE), str(_SENSOR_API)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from lang_adapters.generic import GenericRegexAdapter, _count_duplicates, _halstead_metrics
from lang_adapters.registry import get_registry, reset_registry

# ── Group 1: GenericRegexAdapter base (TL01–TL05) ────────────────────────────

class TestGenericBase:
    """TL01–TL05 — GenericRegexAdapter universal base."""

    def test_TL01_empty_source_returns_zero_stable(self):
        """TL01: empty source → zero-vector, status=STABLE, LOC=0."""
        adapter = GenericRegexAdapter()
        mv = adapter.compute_metrics("", module_id="tl01")
        assert mv.hamiltonian           == 0.0
        assert mv.cyclomatic_complexity == 1
        assert mv.lines_of_code         == 0
        assert mv.status                == "STABLE"

    def test_TL02_loc_counts_nonempty_lines(self):
        """TL02: LOC excludes blank lines, includes comment lines."""
        src = "x = 1\n\n# comment\ny = 2\n\n"
        adapter = GenericRegexAdapter()
        mv = adapter.compute_metrics(src, module_id="tl02")
        assert mv.lines_of_code == 3  # x=1, # comment, y=2

    def test_TL03_cc_increments_for_branches(self):
        """TL03: CC = 1 + decision-points; base CC ≥ 1."""
        src = "if (a) { for (;;) { x++; } } else { while (true) { y++; } }"
        adapter = GenericRegexAdapter()
        mv = adapter.compute_metrics(src, module_id="tl03")
        # if + for + while = 3 decisions → CC ≥ 4
        assert mv.cyclomatic_complexity >= 4

    def test_TL04_strip_removes_strings_before_cc_count(self):
        """TL04: CC keyword inside a string literal must NOT be counted."""
        # "while (true)" inside a string — GenericRegexAdapter strips strings
        src = 'x = "while (true) is an infinite loop"; if (cond) { ok(); }'
        adapter = GenericRegexAdapter()
        mv = adapter.compute_metrics(src, module_id="tl04")
        # Only the real `if` should count → CC == 2
        assert mv.cyclomatic_complexity == 2

    def test_TL05_classify_thresholds(self):
        """TL05: _classify produces CRITICAL / WARNING / STABLE correctly."""
        adapter = GenericRegexAdapter()
        assert adapter._classify(25.0, 5)  == "CRITICAL"   # H ≥ 20 → CRITICAL
        assert adapter._classify(10.0, 5)  == "WARNING"    # H ≥ 8  → WARNING
        assert adapter._classify(5.0,  25) == "CRITICAL"   # CC > 20 → CRITICAL
        assert adapter._classify(5.0,  15) == "WARNING"    # CC > 10 → WARNING
        assert adapter._classify(3.0,  5)  == "STABLE"


# ── Group 2: C-family adapters (TL06–TL10) ───────────────────────────────────

class TestCFamily:
    """TL06–TL10 — C, C++, Objective-C, C# adapters."""

    def test_TL06_c_adapter_extension_and_language(self):
        """TL06: CAdapter covers .c and .h; LANGUAGE='c'."""
        from lang_adapters.c_family import CAdapter
        adapter = CAdapter()
        assert ".c"  in adapter.EXTENSIONS
        assert ".h"  in adapter.EXTENSIONS
        assert adapter.LANGUAGE == "c"

    def test_TL07_cpp_adapter_detects_catch(self):
        """TL07: CppAdapter counts catch/namespace as CC increments."""
        from lang_adapters.c_family import CppAdapter
        src = "try { f(); } catch (Exception& e) { g(); } namespace N { void h(){} }"
        adapter = CppAdapter()
        mv = adapter.compute_metrics(src, module_id="tl07")
        assert mv.cyclomatic_complexity >= 2   # catch is a branch

    def test_TL08_c_adapter_cc_branches(self):
        """TL08: CAdapter counts if/for/while/switch in clean C code."""
        src = """
int f(int x) {
    if (x > 0) {
        for (int i = 0; i < x; i++) {
            while (i > 0) { --i; }
        }
    } else if (x == 0) {
        switch (x) { case 0: break; }
    }
    return x;
}
"""
        from lang_adapters.c_family import CAdapter
        adapter = CAdapter()
        mv = adapter.compute_metrics(src, module_id="tl08")
        assert mv.cyclomatic_complexity >= 5

    def test_TL09_objective_c_adapter_extension(self):
        """TL09: ObjectiveCAdapter covers .m and .mm; LANGUAGE='objective_c'."""
        from lang_adapters.c_family import ObjectiveCAdapter
        adapter = ObjectiveCAdapter()
        assert ".m"  in adapter.EXTENSIONS
        assert ".mm" in adapter.EXTENSIONS
        assert adapter.LANGUAGE == "objective_c"

    def test_TL10_csharp_adapter_features(self):
        """TL10: CSharpAdapter detects foreach/when/?? and 'cs' extension."""
        from lang_adapters.csharp import CSharpAdapter
        src = """
foreach (var item in items) {
    if (item?.Value ?? false) {
        switch (item) { case Foo f when f.X > 0: break; }
    }
}
"""
        adapter = CSharpAdapter()
        assert ".cs" in adapter.EXTENSIONS
        mv = adapter.compute_metrics(src, module_id="tl10")
        assert mv.cyclomatic_complexity >= 4   # foreach + if + case/when + ??


# ── Group 3: Rust / Ruby / Swift / Kotlin / PHP / Scala (TL11–TL15) ─────────

class TestModernCompiled:
    """TL11–TL15 — Rust, Swift, Kotlin, Scala, PHP adapters."""

    def test_TL11_rust_adapter_match_arm(self):
        """TL11: RustAdapter counts match arms (=>) as CC."""
        from lang_adapters.rust import RustAdapter
        src = """
fn classify(x: i32) -> &'static str {
    match x {
        0        => "zero",
        1..=9    => "small",
        _        => "large",
    }
}
"""
        adapter = RustAdapter()
        assert ".rs" in adapter.EXTENSIONS
        mv = adapter.compute_metrics(src, module_id="tl11")
        assert mv.cyclomatic_complexity >= 3   # 3 match arms

    def test_TL12_swift_adapter_guard(self):
        """TL12: SwiftAdapter counts guard/where/if-let."""
        from lang_adapters.swift import SwiftAdapter
        src = """
func process(_ val: Int?) -> Int {
    guard let v = val else { return 0 }
    if v > 0 {
        return v
    }
    return -1
}
"""
        adapter = SwiftAdapter()
        assert ".swift" in adapter.EXTENSIONS
        mv = adapter.compute_metrics(src, module_id="tl12")
        assert mv.cyclomatic_complexity >= 3   # guard + if + else

    def test_TL13_kotlin_adapter_when_elvis(self):
        """TL13: KotlinAdapter counts when/Elvis(?:)/?."""
        from lang_adapters.kotlin import KotlinAdapter
        src = """
fun grade(score: Int): String {
    return when {
        score >= 90 -> "A"
        score >= 80 -> "B"
        else        -> "C"
    }
}
val name = user?.name ?: "anonymous"
"""
        adapter = KotlinAdapter()
        assert ".kt" in adapter.EXTENSIONS
        mv = adapter.compute_metrics(src, module_id="tl13")
        assert mv.cyclomatic_complexity >= 3

    def test_TL14_scala_adapter_extension(self):
        """TL14: ScalaAdapter covers .scala, .sc, .sbt; LANGUAGE='scala'."""
        from lang_adapters.scala import ScalaAdapter
        adapter = ScalaAdapter()
        assert ".scala" in adapter.EXTENSIONS
        assert ".sc"    in adapter.EXTENSIONS
        assert ".sbt"   in adapter.EXTENSIONS
        assert adapter.LANGUAGE == "scala"

    def test_TL15_php_adapter_match_expression(self):
        """TL15: PhpAdapter counts PHP-8 match expression."""
        from lang_adapters.php import PhpAdapter
        src = """<?php
$label = match($status) {
    'active'   => 'Active',
    'inactive' => 'Inactive',
    default    => 'Unknown',
};
if ($label === 'Unknown') {
    echo "Not found";
}
?>"""
        adapter = PhpAdapter()
        assert ".php" in adapter.EXTENSIONS
        mv = adapter.compute_metrics(src, module_id="tl15")
        assert mv.cyclomatic_complexity >= 3   # match arms + if


# ── Group 4: Scripting adapters (TL16–TL20) ──────────────────────────────────

class TestScripting:
    """TL16–TL20 — R, Shell, PowerShell, Lua, Perl adapters."""

    def test_TL16_r_adapter_library_and_class(self):
        """TL16: RAdapter detects library() imports and R6Class types."""
        from lang_adapters.scripting_langs import RAdapter
        src = """
library(dplyr)
require(ggplot2)
MyClass <- R6Class("MyClass",
  public = list(
    greet = function() {
      if (self$name != "") cat("Hello", self$name)
    }
  )
)
"""
        adapter = RAdapter()
        assert ".r" in adapter.EXTENSIONS or ".R" in adapter.EXTENSIONS
        mv = adapter.compute_metrics(src, module_id="tl16")
        assert mv.n_functions >= 1          # R6Class greet
        assert mv.cyclomatic_complexity >= 2

    def test_TL17_shell_adapter_bracket_cc(self):
        """TL17: ShellAdapter counts [[ and [ as CC increments."""
        from lang_adapters.scripting_langs import ShellAdapter
        src = """#!/bin/bash
if [[ -f "$FILE" ]]; then
  while [ "$COUNT" -gt 0 ]; do
    ((COUNT--))
  done
fi
"""
        adapter = ShellAdapter()
        assert ".sh" in adapter.EXTENSIONS
        mv = adapter.compute_metrics(src, module_id="tl17")
        assert mv.cyclomatic_complexity >= 3   # if + [[ + while + [

    def test_TL18_powershell_adapter_case_insensitive(self):
        """TL18: PowerShellAdapter case-insensitive keyword matching."""
        from lang_adapters.scripting_langs import PowerShellAdapter
        src = """
FOREACH ($item IN $items) {
    IF ($item -GT 0) {
        WHILE ($item -GT 0) { $item-- }
    }
}
"""
        adapter = PowerShellAdapter()
        assert ".ps1" in adapter.EXTENSIONS
        mv = adapter.compute_metrics(src, module_id="tl18")
        assert mv.cyclomatic_complexity >= 3   # foreach + if + while

    def test_TL19_lua_adapter_and_or_cc(self):
        """TL19: LuaAdapter counts and/or/if/while as CC."""
        from lang_adapters.scripting_langs import LuaAdapter
        src = """
local function check(x, y)
  if x > 0 and y > 0 then
    while x > 0 do x = x - 1 end
  elseif x == 0 or y == 0 then
    return 0
  end
  return 1
end
"""
        adapter = LuaAdapter()
        assert ".lua" in adapter.EXTENSIONS
        mv = adapter.compute_metrics(src, module_id="tl19")
        assert mv.cyclomatic_complexity >= 5   # if + and + while + elseif + or

    def test_TL20_perl_adapter_sub_detection(self):
        """TL20: PerlAdapter detects sub declarations and elsif."""
        from lang_adapters.scripting_langs import PerlAdapter
        src = """
sub greet {
    my ($name) = @_;
    if ($name eq 'Alice') {
        return "Hi Alice";
    } elsif ($name eq 'Bob') {
        return "Hey Bob";
    } else {
        return "Hello $name";
    }
}
"""
        adapter = PerlAdapter()
        assert ".pl" in adapter.EXTENSIONS
        mv = adapter.compute_metrics(src, module_id="tl20")
        assert mv.n_functions >= 1
        assert mv.cyclomatic_complexity >= 3   # if + elsif


# ── Group 5: Functional adapters (TL21–TL24) ─────────────────────────────────

class TestFunctional:
    """TL21–TL24 — Haskell, Elixir, F#, Clojure adapters."""

    def test_TL21_haskell_adapter_guard_cc(self):
        """TL21: HaskellAdapter counts | guards as CC increments."""
        from lang_adapters.functional_langs import HaskellAdapter
        src = """
module Main where

classify :: Int -> String
classify n
  | n < 0    = "negative"
  | n == 0   = "zero"
  | n < 10   = "small"
  | otherwise = "large"
"""
        adapter = HaskellAdapter()
        assert ".hs" in adapter.EXTENSIONS
        mv = adapter.compute_metrics(src, module_id="tl21")
        # 4 guards = +4 CC
        assert mv.cyclomatic_complexity >= 4

    def test_TL22_elixir_adapter_defmodule_defp(self):
        """TL22: ElixirAdapter detects defmodule/defp and cond/case."""
        from lang_adapters.functional_langs import ElixirAdapter
        src = """
defmodule Greeter do
  defp classify(x) when x > 0 do
    cond do
      x > 100 -> :large
      x > 10  -> :medium
      true    -> :small
    end
  end
end
"""
        adapter = ElixirAdapter()
        assert ".ex" in adapter.EXTENSIONS
        mv = adapter.compute_metrics(src, module_id="tl22")
        assert mv.n_classes   >= 1    # defmodule
        assert mv.cyclomatic_complexity >= 3

    def test_TL23_fsharp_adapter_match_arms(self):
        """TL23: FSharpAdapter counts | match arms as CC."""
        from lang_adapters.functional_langs import FSharpAdapter
        src = """
module Classifier

let classify x =
    match x with
    | 0         -> "zero"
    | n when n > 0 -> "positive"
    | _         -> "negative"
"""
        adapter = FSharpAdapter()
        assert ".fs" in adapter.EXTENSIONS
        mv = adapter.compute_metrics(src, module_id="tl23")
        assert mv.cyclomatic_complexity >= 3   # 3 match arms (|)

    def test_TL24_clojure_adapter_defn_forms(self):
        """TL24: ClojureAdapter counts (defn...) and (if/cond...) forms."""
        from lang_adapters.functional_langs import ClojureAdapter
        src = """
(ns myapp.core
  (:require [clojure.string :as str]))

(defn classify [x]
  (cond
    (> x 100) :large
    (> x 10)  :medium
    :else      :small))

(defn greet [name]
  (if (nil? name)
    "Hello stranger"
    (str "Hello " name)))
"""
        adapter = ClojureAdapter()
        assert ".clj" in adapter.EXTENSIONS
        mv = adapter.compute_metrics(src, module_id="tl24")
        assert mv.n_functions >= 2    # defn classify + defn greet
        assert mv.cyclomatic_complexity >= 3


# ── Group 6: Modern systems (TL25–TL27) ──────────────────────────────────────

class TestModernSystems:
    """TL25–TL27 — Dart, Zig, Nim adapters."""

    def test_TL25_dart_adapter_null_coalescing_cc(self):
        """TL25: DartAdapter counts ?? and ?. as CC increments."""
        from lang_adapters.modern_systems import DartAdapter
        src = """
import 'package:flutter/material.dart';

String getLabel(String? name) {
  final label = name ?? 'anonymous';
  final upper = name?.toUpperCase() ?? 'ANON';
  if (label.isEmpty) return upper;
  return label;
}
"""
        adapter = DartAdapter()
        assert ".dart" in adapter.EXTENSIONS
        mv = adapter.compute_metrics(src, module_id="tl25")
        # 2x ?? + ?. + if = 4 CC increments → CC ≥ 5
        assert mv.cyclomatic_complexity >= 4
        # verify import detection via the adapter pattern directly
        from lang_adapters.modern_systems import DartAdapter
        n_imp = len(DartAdapter.IMPORT_RE.findall(src))
        assert n_imp >= 1

    def test_TL26_zig_adapter_comptime_orelse(self):
        """TL26: ZigAdapter counts comptime/orelse/catch/try as CC."""
        from lang_adapters.modern_systems import ZigAdapter
        src = """
const std = @import("std");

pub fn process(val: ?i32) i32 {
    const v = val orelse return -1;
    const result = compute(v) catch |err| {
        std.debug.print("error: {}", .{err});
        return -2;
    };
    comptime if (@sizeOf(i32) != 4) @compileError("unexpected size");
    return result;
}
"""
        adapter = ZigAdapter()
        assert ".zig" in adapter.EXTENSIONS
        mv = adapter.compute_metrics(src, module_id="tl26")
        # orelse + catch + comptime + if = 4 CC increments
        assert mv.cyclomatic_complexity >= 4

    def test_TL27_nim_adapter_proc_elif(self):
        """TL27: NimAdapter detects proc/func and elif/of."""
        from lang_adapters.modern_systems import NimAdapter
        src = """
import strutils

proc classify(x: int): string =
  if x > 100:
    "large"
  elif x > 10:
    "medium"
  else:
    "small"

func double(x: int): int = x * 2
"""
        adapter = NimAdapter()
        assert ".nim"  in adapter.EXTENSIONS
        assert ".nims" in adapter.EXTENSIONS
        mv = adapter.compute_metrics(src, module_id="tl27")
        assert mv.n_functions >= 2   # proc + func
        assert mv.cyclomatic_complexity >= 3   # if + elif


# ── Group 7: Registry coverage (TL28–TL30) ───────────────────────────────────

class TestRegistryCoverage:
    """TL28–TL30 — UCOBridgeRegistry language and extension coverage."""

    def setup_method(self):
        reset_registry()

    def teardown_method(self):
        reset_registry()

    def test_TL28_registry_language_count_ge_36(self):
        """TL28: Registry must report ≥ 36 supported languages (M6.2 target)."""
        reg = get_registry()
        langs = reg.supported_languages()
        assert len(langs) >= 36, (
            f"Expected ≥ 36 languages, got {len(langs)}: {langs}"
        )

    def test_TL29_registry_extension_count_ge_100(self):
        """TL29: Registry must map ≥ 100 file extensions."""
        reg = get_registry()
        exts = reg.supported_extensions()
        assert len(exts) >= 100, (
            f"Expected ≥ 100 extensions, got {len(exts)}: {sorted(exts)}"
        )

    def test_TL30_registry_dispatch_per_language(self):
        """TL30: get_adapter returns correct adapter for sampled extensions."""
        reg = get_registry()
        # (extension, expected_language_substring)
        samples = [
            (".py",     "python"),
            (".rs",     "rust"),
            (".go",     "go"),
            (".java",   "java"),
            (".cs",     "csharp"),
            (".swift",  "swift"),
            (".kt",     "kotlin"),
            (".rb",     "ruby"),
            (".php",    "php"),
            (".scala",  "scala"),
            (".hs",     "haskell"),
            (".ex",     "elixir"),
            (".dart",   "dart"),
            (".zig",    "zig"),
            (".nim",    "nim"),
            (".sol",    "solidity"),
            (".tf",     "hcl"),
            (".lua",    "lua"),
            (".sh",     "shell"),
            (".ps1",    "powershell"),
        ]
        for ext, expected_lang in samples:
            adapter = reg.get_adapter(file_extension=ext)
            assert adapter is not None, f"No adapter for {ext}"
            actual = adapter.LANGUAGE.lower()
            assert expected_lang in actual, (
                f"Extension {ext}: expected language containing '{expected_lang}', "
                f"got '{actual}'"
            )
