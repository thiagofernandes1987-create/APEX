"""
UCO-Sensor — SARIF 2.1.0 Builder
==================================
Builds rich SARIF 2.1.0 documents with:
  • Full rule catalog: 9 UCO channel rules + 13 SAST rules (22 total)
  • Accurate line/column from SASTFinding.line / SASTFinding.col
  • Logical locations (function name) from FunctionProfile data
  • CWE / OWASP tags embedded in rule properties
  • Artifact registry for clean URI management

SARIF spec: https://docs.oasis-open.org/sarif/sarif/v2.1.0/

Usage:
    from report.sarif import SARIFBuilder
    from sast.scanner import scan as sast_scan

    builder = SARIFBuilder(tool_version="1.0.0", repo="owner/repo")
    result = sast_scan(source_code)
    builder.add_sast_findings("src/auth.py", result)
    builder.add_uco_findings_from_profiles(
        "src/auth.py", mv.function_profiles, cc_threshold=10
    )
    sarif_dict = builder.build()
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

# ── Severity → SARIF level mappings ──────────────────────────────────────────

SAST_SEVERITY_TO_SARIF: Dict[str, str] = {
    "CRITICAL": "error",
    "HIGH":     "error",
    "MEDIUM":   "warning",
    "LOW":      "note",
    "INFO":     "none",
}

UCO_STATUS_TO_SARIF: Dict[str, str] = {
    "CRITICAL": "error",
    "WARNING":  "warning",
    "STABLE":   "note",
}

# ── Rule catalogs ─────────────────────────────────────────────────────────────

# 9 UCO channel rules — one per Hamiltonian channel
_UCO_RULES: List[Dict[str, Any]] = [
    {
        "id": "UCO001",
        "name": "CyclomaticComplexity",
        "shortDescription": "Cyclomatic complexity exceeds threshold",
        "fullDescription": (
            "McCabe cyclomatic complexity (CC) measures the number of linearly "
            "independent paths through source code. High CC (>10) increases bug "
            "probability and reduces testability. Refactor: extract functions, "
            "reduce branching, apply early-return patterns."
        ),
        "tags": ["quality", "complexity", "maintainability"],
        "precision": "high",
    },
    {
        "id": "UCO002",
        "name": "CognitiveComplexity",
        "shortDescription": "Cognitive complexity exceeds threshold (Campbell 2018)",
        "fullDescription": (
            "Cognitive complexity measures how difficult code is to understand "
            "(not to traverse). Nested control flow, Boolean operators, and "
            "recursive structures each add weight. Values >15 require refactoring."
        ),
        "tags": ["quality", "complexity", "readability"],
        "precision": "high",
    },
    {
        "id": "UCO003",
        "name": "InfiniteLoopRisk",
        "shortDescription": "Infinite loop risk detected",
        "fullDescription": (
            "Loops without a guaranteed termination condition (missing break/return, "
            "mutable loop variable in while-condition, sentinel never reachable). "
            "Detected via UCO spectral analysis of loop structures."
        ),
        "tags": ["reliability", "safety"],
        "precision": "medium",
    },
    {
        "id": "UCO004",
        "name": "DSMDensityHigh",
        "shortDescription": "Design structure matrix coupling density too high",
        "fullDescription": (
            "High DSM density indicates excessive inter-module coupling. "
            "Each module depends on too many others, violating the Single "
            "Responsibility Principle and making change propagation unpredictable."
        ),
        "tags": ["architecture", "coupling"],
        "precision": "medium",
    },
    {
        "id": "UCO005",
        "name": "DSMCyclicDependencies",
        "shortDescription": "Cyclic dependencies detected in design structure matrix",
        "fullDescription": (
            "Cyclic dependencies violate the Acyclic Dependencies Principle (ADP). "
            "Cycles prevent independent deployment, increase recompilation cascades, "
            "and make the codebase harder to reason about."
        ),
        "tags": ["architecture", "coupling"],
        "precision": "high",
    },
    {
        "id": "UCO006",
        "name": "DependencyInstability",
        "shortDescription": "Martin's instability metric exceeds 0.5",
        "fullDescription": (
            "Instability I = Ce / (Ca + Ce). I > 0.5 means the module has more "
            "efferent (outgoing) couplings than afferent (incoming) ones — it "
            "depends on many modules but few depend on it. Unstable modules are "
            "difficult to change without cascading breakage."
        ),
        "tags": ["architecture", "coupling"],
        "precision": "high",
    },
    {
        "id": "UCO007",
        "name": "SyntacticDeadCode",
        "shortDescription": "Syntactic dead code detected",
        "fullDescription": (
            "Unreachable code paths (code after return/raise), unused variables "
            "assigned but never read, or dead branches (always-false conditions). "
            "Dead code increases cognitive load and maintenance risk."
        ),
        "tags": ["quality", "maintainability"],
        "precision": "high",
    },
    {
        "id": "UCO008",
        "name": "DuplicateCodeBlocks",
        "shortDescription": "Duplicate code blocks (Type-2 clones) detected",
        "fullDescription": (
            "AST skeleton hash clone detection identifies structurally identical "
            "functions (parameter names and literals normalized). Duplicate blocks "
            "accumulate technical debt; refactor via extraction to shared utilities."
        ),
        "tags": ["quality", "duplication"],
        "precision": "high",
    },
    {
        "id": "UCO009",
        "name": "HalsteadBugPrediction",
        "shortDescription": "Halstead bug prediction exceeds threshold",
        "fullDescription": (
            "Halstead B = V / 3000 estimates the expected number of defects from "
            "program volume V. High B values indicate code that is complex enough "
            "to carry statistically significant defect risk."
        ),
        "tags": ["quality", "reliability"],
        "precision": "medium",
    },
]

# 13 SAST rules — mirrors sast/scanner.py RULES in exact order
_SAST_RULES: List[Dict[str, Any]] = [
    {
        "id": "SAST001", "name": "SQLInjection",
        "cwe": "CWE-89", "owasp": "A03:2021", "severity": "CRITICAL",
        "shortDescription": "SQL Injection via string formatting in execute()",
        "fullDescription": (
            "User-controlled data is concatenated or formatted into an SQL query "
            "string passed to cursor.execute(). An attacker can manipulate the "
            "query to exfiltrate, modify, or delete data. Use parameterised queries."
        ),
        "tags": ["security", "injection"],
    },
    {
        "id": "SAST002", "name": "OSCommandInjection",
        "cwe": "CWE-78", "owasp": "A03:2021", "severity": "HIGH",
        "shortDescription": "OS command injection via os.system/popen with variable",
        "fullDescription": (
            "A non-literal string is passed to os.system(), os.popen(), or "
            "similar shell-invoking functions. If user-controlled, an attacker "
            "can execute arbitrary system commands."
        ),
        "tags": ["security", "injection"],
    },
    {
        "id": "SAST003", "name": "UnsafeEval",
        "cwe": "CWE-95", "owasp": "A03:2021", "severity": "HIGH",
        "shortDescription": "Unsafe eval()/exec() with non-literal argument",
        "fullDescription": (
            "eval() or exec() is called with an argument that is not a string "
            "literal. Evaluating arbitrary code from untrusted input allows remote "
            "code execution."
        ),
        "tags": ["security", "injection"],
    },
    {
        "id": "SAST004", "name": "PickleDeserialization",
        "cwe": "CWE-502", "owasp": "A08:2021", "severity": "HIGH",
        "shortDescription": "Insecure pickle deserialization (arbitrary code execution risk)",
        "fullDescription": (
            "pickle.load() / pickle.loads() can execute arbitrary code embedded "
            "in the serialised payload. Never deserialise pickle data from "
            "untrusted sources. Use JSON or protobuf instead."
        ),
        "tags": ["security", "deserialization"],
    },
    {
        "id": "SAST005", "name": "YAMLUnsafeLoad",
        "cwe": "CWE-502", "owasp": "A08:2021", "severity": "MEDIUM",
        "shortDescription": "YAML unsafe load without safe Loader",
        "fullDescription": (
            "yaml.load() without Loader=yaml.SafeLoader (or yaml.safe_load()) "
            "can execute arbitrary Python code embedded in the YAML document. "
            "Replace with yaml.safe_load() for untrusted inputs."
        ),
        "tags": ["security", "deserialization"],
    },
    {
        "id": "SAST006", "name": "WeakHashAlgorithm",
        "cwe": "CWE-327", "owasp": "A02:2021", "severity": "MEDIUM",
        "shortDescription": "Use of cryptographically weak hash algorithm (MD5/SHA1)",
        "fullDescription": (
            "MD5 and SHA1 are deprecated for cryptographic use due to known "
            "collision attacks. Use SHA-256 or stronger for integrity checks, "
            "and bcrypt/Argon2 for password hashing."
        ),
        "tags": ["security", "cryptography"],
    },
    {
        "id": "SAST007", "name": "InsecureRandomness",
        "cwe": "CWE-338", "owasp": "A02:2021", "severity": "MEDIUM",
        "shortDescription": "Insecure random number generation (random module)",
        "fullDescription": (
            "The random module uses a Mersenne Twister PRNG which is predictable. "
            "For security tokens, session IDs, and cryptographic uses, use the "
            "secrets module: secrets.token_hex(), secrets.token_bytes()."
        ),
        "tags": ["security", "cryptography"],
    },
    {
        "id": "SAST008", "name": "HardcodedSecret",
        "cwe": "CWE-798", "owasp": "A07:2021", "severity": "HIGH",
        "shortDescription": "Hardcoded secret or credential in source",
        "fullDescription": (
            "A variable with a security-sensitive name (password, api_key, token, "
            "secret) is assigned a hardcoded string literal. Credentials in source "
            "code are exposed in version history and leak in repository forks. "
            "Load from environment variables or a secrets manager."
        ),
        "tags": ["security", "credentials"],
    },
    {
        "id": "SAST009", "name": "HardcodedPrivateKey",
        "cwe": "CWE-321", "owasp": "A02:2021", "severity": "CRITICAL",
        "shortDescription": "Hardcoded PEM private key material in source",
        "fullDescription": (
            "A PEM PRIVATE KEY block is embedded directly in the source file. "
            "This exposes the private key to anyone with read access to the "
            "repository. Rotate immediately and store in secrets management."
        ),
        "tags": ["security", "credentials", "cryptography"],
    },
    {
        "id": "SAST010", "name": "DebugModeEnabled",
        "cwe": "CWE-489", "owasp": "A05:2021", "severity": "MEDIUM",
        "shortDescription": "Debug mode enabled (Flask/app.run debug=True)",
        "fullDescription": (
            "Running a web application with debug=True exposes a Werkzeug "
            "debugger console that allows arbitrary code execution in the "
            "browser. Always set debug=False in production."
        ),
        "tags": ["security", "configuration"],
    },
    {
        "id": "SAST011", "name": "PathTraversal",
        "cwe": "CWE-22", "owasp": "A01:2021", "severity": "HIGH",
        "shortDescription": "Path traversal via open() with user-controlled path",
        "fullDescription": (
            "open() is called with a non-literal path argument. If the path is "
            "derived from user input, an attacker can read or write files outside "
            "the intended directory using '../' sequences. Validate and sanitise "
            "paths before use."
        ),
        "tags": ["security", "path-traversal"],
    },
    {
        "id": "SAST012", "name": "AssertForSecurity",
        "cwe": "CWE-617", "owasp": "A04:2021", "severity": "LOW",
        "shortDescription": "assert statement used for security enforcement",
        "fullDescription": (
            "assert statements are removed when Python is run with the -O "
            "(optimise) flag, disabling security checks silently. Replace "
            "assert-based guards with explicit if/raise statements."
        ),
        "tags": ["security", "reliability"],
    },
    {
        "id": "SAST013", "name": "SubprocessShellTrue",
        "cwe": "CWE-78", "owasp": "A03:2021", "severity": "HIGH",
        "shortDescription": "subprocess called with shell=True and variable command",
        "fullDescription": (
            "subprocess.run/call/Popen with shell=True passes the command to the "
            "OS shell for interpretation. Combined with a non-literal first "
            "argument, this allows shell injection. Use shell=False and pass "
            "a list of arguments."
        ),
        "tags": ["security", "injection"],
    },
]


# ── Helper: build a SARIF rule object from internal dict ─────────────────────

def _make_sarif_rule(rule_info: Dict[str, Any]) -> Dict[str, Any]:
    """Convert an internal rule-info dict to a SARIF 2.1.0 reportingDescriptor."""
    props: Dict[str, Any] = {
        "tags": rule_info.get("tags", []),
    }
    if "cwe" in rule_info:
        props["cwe"] = rule_info["cwe"]
    if "owasp" in rule_info:
        props["owasp"] = rule_info["owasp"]
    if "severity" in rule_info:
        props["problem.severity"] = rule_info["severity"].lower()
    props["precision"] = rule_info.get("precision", "medium")

    return {
        "id":   rule_info["id"],
        "name": rule_info["name"],
        "shortDescription": {"text": rule_info["shortDescription"]},
        "fullDescription":  {"text": rule_info.get("fullDescription", rule_info["shortDescription"])},
        "help": {
            "text":     rule_info["shortDescription"],
            "markdown": f"**{rule_info['id']}** — {rule_info['shortDescription']}",
        },
        "properties": props,
    }


# ── SARIFBuilder ──────────────────────────────────────────────────────────────

class SARIFBuilder:
    """
    Incremental SARIF 2.1.0 document builder.

    Parameters
    ----------
    tool_name : str
        Tool name embedded in the SARIF driver block.
    tool_version : str
        Semantic version of UCO-Sensor.
    info_uri : str
        Informational URI for the tool.
    repo : str
        Repository name (embedded in run properties).

    Rule catalog
    ------------
    22 rules total (9 UCO + 13 SAST). Rule indices are stable:
      0-8  → UCO001-UCO009
      9-21 → SAST001-SAST013
    """

    SCHEMA_URI = (
        "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/"
        "master/Schemata/sarif-schema-2.1.0.json"
    )

    def __init__(
        self,
        tool_name:    str = "UCO-Sensor",
        tool_version: str = "1.0.0",
        info_uri:     str = "https://github.com/thiagofernandes1987-create/APEX",
        repo:         str = "",
    ) -> None:
        self._tool_name    = tool_name
        self._tool_version = tool_version
        self._info_uri     = info_uri
        self._repo         = repo
        self._results:    List[Dict[str, Any]] = []
        self._artifacts:  Dict[str, int] = {}   # uri → artifact index

        # Build rule catalog + stable index map
        self._rules: List[Dict[str, Any]] = [
            _make_sarif_rule(r) for r in _UCO_RULES + _SAST_RULES
        ]
        self._rule_index: Dict[str, int] = {
            r["id"]: i for i, r in enumerate(self._rules)
        }

    # ── Catalog queries ───────────────────────────────────────────────────────

    @property
    def rule_ids(self) -> List[str]:
        """All rule IDs in catalog order (UCO001…UCO009, SAST001…SAST013)."""
        return [r["id"] for r in self._rules]

    def uco_rule_ids(self) -> List[str]:
        """Only the 9 UCO channel rule IDs."""
        return [r["id"] for r in _UCO_RULES]

    def sast_rule_ids(self) -> List[str]:
        """Only the 13 SAST rule IDs."""
        return [r["id"] for r in _SAST_RULES]

    def rule_count(self) -> int:
        return len(self._rules)

    def result_count(self) -> int:
        return len(self._results)

    # ── Artifact registry ─────────────────────────────────────────────────────

    def _register_artifact(self, uri: str) -> int:
        """Register a file URI and return its stable index."""
        if uri not in self._artifacts:
            self._artifacts[uri] = len(self._artifacts)
        return self._artifacts[uri]

    def _artifact_location(self, uri: str) -> Dict[str, Any]:
        return {
            "uri":       uri,
            "uriBaseId": "%SRCROOT%",
            "index":     self._register_artifact(uri),
        }

    # ── Adding SAST findings ──────────────────────────────────────────────────

    def add_sast_findings(self, file_uri: str, sast_result: Any) -> None:
        """
        Add all SASTFinding objects from a SASTResult to this SARIF document.

        Parameters
        ----------
        file_uri : str
            Relative URI of the scanned file (e.g. "src/auth.py").
        sast_result : SASTResult
            Result from sast.scanner.scan().
        """
        for finding in sast_result.findings:
            self._add_one_sast_finding(file_uri, finding)

    def _add_one_sast_finding(self, file_uri: str, finding: Any) -> None:
        rule_id = finding.rule_id
        level   = SAST_SEVERITY_TO_SARIF.get(finding.severity, "warning")
        # SARIF regions are 1-based; SASTFinding.col is 0-based
        line = max(1, finding.line)
        col  = max(1, finding.col + 1)   # convert 0-based → 1-based

        region: Dict[str, Any] = {
            "startLine":   line,
            "startColumn": col,
        }
        if finding.code_snippet:
            region["snippet"] = {"text": finding.code_snippet}

        result: Dict[str, Any] = {
            "ruleId":    rule_id,
            "ruleIndex": self._rule_index.get(rule_id, -1),
            "level":     level,
            "message": {
                "text": (
                    f"{finding.title}: {finding.description} "
                    f"[{finding.cwe_id} / {finding.owasp}] "
                    f"Remediation: {finding.remediation}"
                )
            },
            "locations": [{
                "physicalLocation": {
                    "artifactLocation": self._artifact_location(file_uri),
                    "region":           region,
                }
            }],
            "properties": {
                "cwe":          finding.cwe_id,
                "owasp":        finding.owasp,
                "debt_minutes": finding.debt_minutes,
                "severity":     finding.severity,
            },
        }
        self._results.append(result)

    # ── Adding UCO channel findings ───────────────────────────────────────────

    def add_uco_finding(
        self,
        file_uri:      str,
        rule_id:       str,
        message:       str,
        severity:      str = "WARNING",
        line:          int = 1,
        col:           int = 1,
        function_name: Optional[str] = None,
        end_line:      Optional[int] = None,
        end_col:       Optional[int] = None,
    ) -> None:
        """
        Add a single UCO channel quality finding.

        Parameters
        ----------
        file_uri : str
            Relative path of the file.
        rule_id : str
            One of UCO001–UCO009.
        message : str
            Human-readable description of the finding.
        severity : str
            UCO status: "CRITICAL" | "WARNING" | "STABLE".
        line : int
            1-based start line.
        col : int
            1-based start column.
        function_name : str | None
            Logical function context (populates logicalLocations).
        end_line : int | None
            Optional 1-based end line.
        end_col : int | None
            Optional 1-based end column.
        """
        level = UCO_STATUS_TO_SARIF.get(severity.upper(), "warning")

        region: Dict[str, Any] = {
            "startLine":   max(1, line),
            "startColumn": max(1, col),
        }
        if end_line is not None:
            region["endLine"] = end_line
        if end_col is not None:
            region["endColumn"] = end_col

        location: Dict[str, Any] = {
            "physicalLocation": {
                "artifactLocation": self._artifact_location(file_uri),
                "region":           region,
            }
        }
        if function_name:
            location["logicalLocations"] = [{
                "name":               function_name,
                "fullyQualifiedName": function_name,
                "kind":               "function",
            }]

        result: Dict[str, Any] = {
            "ruleId":    rule_id,
            "ruleIndex": self._rule_index.get(rule_id, -1),
            "level":     level,
            "message":   {"text": message},
            "locations": [location],
        }
        self._results.append(result)

    def add_uco_findings_from_profiles(
        self,
        file_uri:      str,
        function_profiles: List[Dict[str, Any]],
        cc_threshold:  int = 10,
        cog_threshold: int = 15,
    ) -> None:
        """
        Iterate FunctionProfile dicts and emit UCO001 (CC) / UCO002 (CogCC)
        findings for every function that exceeds the given thresholds.

        Parameters
        ----------
        file_uri : str
            Source file relative URI.
        function_profiles : list[dict]
            Output of FunctionProfile.to_dict() — fields used:
            name, lineno, cyclomatic_complexity, cognitive_complexity, risk_level.
        cc_threshold : int
            Cyclomatic complexity limit (default 10).
        cog_threshold : int
            Cognitive complexity limit (default 15).
        """
        for fp in function_profiles:
            name  = fp.get("name", "<unknown>")
            line  = int(fp.get("lineno", 1))
            cc    = int(fp.get("cyclomatic_complexity", 0))
            cog   = int(fp.get("cognitive_complexity", 0))
            risk  = fp.get("risk_level", "LOW")

            severity = "CRITICAL" if risk in ("CRITICAL", "HIGH") else "WARNING"

            if cc > cc_threshold:
                self.add_uco_finding(
                    file_uri=file_uri,
                    rule_id="UCO001",
                    message=(
                        f"Function '{name}' cyclomatic complexity {cc} "
                        f"exceeds threshold {cc_threshold}"
                    ),
                    severity=severity,
                    line=line,
                    function_name=name,
                )

            if cog > cog_threshold:
                self.add_uco_finding(
                    file_uri=file_uri,
                    rule_id="UCO002",
                    message=(
                        f"Function '{name}' cognitive complexity {cog} "
                        f"exceeds threshold {cog_threshold}"
                    ),
                    severity=severity,
                    line=line,
                    function_name=name,
                )

    # ── Build ─────────────────────────────────────────────────────────────────

    def build(self) -> Dict[str, Any]:
        """
        Assemble and return the complete SARIF 2.1.0 document as a dict.

        The document is JSON-serialisable (no non-serialisable types).
        """
        artifacts = [
            {
                "location": {"uri": uri, "uriBaseId": "%SRCROOT%"},
                "index": idx,
            }
            for uri, idx in sorted(self._artifacts.items(), key=lambda kv: kv[1])
        ]

        return {
            "$schema": self.SCHEMA_URI,
            "version": "2.1.0",
            "runs": [{
                "tool": {
                    "driver": {
                        "name":            self._tool_name,
                        "version":         self._tool_version,
                        "semanticVersion": self._tool_version,
                        "informationUri":  self._info_uri,
                        "rules":           self._rules,
                    }
                },
                "artifacts": artifacts,
                "results":   self._results,
                "properties": {
                    "repo":      self._repo,
                    "generator": "UCO-Sensor",
                },
            }],
        }

    def to_json(self, indent: int = 2) -> str:
        """Serialise the SARIF document to a pretty-printed JSON string."""
        return json.dumps(self.build(), indent=indent, default=str)
