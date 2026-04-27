"""
UCO-Sensor — Extended Metric Vectors  (M6.4)
=============================================
Formalizes the 30+ signals identified in the M6.4 signal-gap analysis that
were being computed but discarded before reaching the MetricVector schema.

Four new dataclasses complement MetricVector without altering its 9-channel
schema — preserving full backward compatibility with all existing consumers.

Vectors
-------
HalsteadVector  (6 channels)
    Volume (V), Difficulty (D), Effort (E), TimeToImplement (T),
    ProgramLevel (L), TokenCount (N).  All derived from Halstead 1977.

StructuralVector  (7 channels)
    MaxFunctionCC, CCHotspotRatio, MaxMethodsPerClass, NFunctions,
    NClasses, CommentDensity, TestRatio.  Shape and OO metrics.

SecurityVector  (10 channels)
    SASTCritical, SASTHigh, SASTMedium, SASTLow, SASTSecurityRating,
    SASTDebtMinutes, SCAVulnerableDeps, SCACVSSMax, SCADebtMinutes,
    IaCMisconfigCount (+IaCPrivilegeScore from M6.4 IaC scanner).

VelocityVector  (4 channels)
    HamiltonianVelocity, CCVelocity, DegradationHurst, RegressionRate.
    Temporal / trend metrics.

References
----------
Halstead, M.H. (1977). Elements of Software Science. Elsevier.
McCabe, T.J.  (1976). A complexity measure. IEEE TSE, 2(4), 308-320.
Martin, R.C.  (2000). Design Principles and Design Patterns.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, Optional


# ─── HalsteadVector ──────────────────────────────────────────────────────────

@dataclass
class HalsteadVector:
    """
    6-channel Halstead Software Science vector.

    Channels
    --------
    volume            V = N * log2(n)     — program size in bits
    difficulty        D = (n1/2)*(N2/n2)  — mental effort to understand
    effort            E = D * V           — implementation effort (elementary ops)
    time_to_implement T = E / 18          — estimated time in seconds (Halstead)
    program_level     L = 1 / D           — inverse difficulty (higher = cleaner)
    token_count       N = N1 + N2         — total tokens (raw program length)
    """
    volume:            float = 0.0   # V
    difficulty:        float = 0.0   # D
    effort:            float = 0.0   # E
    time_to_implement: float = 0.0   # T = E/18  [seconds]
    program_level:     float = 0.0   # L = 1/D
    token_count:       int   = 0     # N = N1 + N2

    # ── source attribution ────────────────────────────────────────────────────
    module_id:   str = ""
    language:    str = ""

    # ── constructors ──────────────────────────────────────────────────────────

    @classmethod
    def from_primitives(
        cls,
        n1: int,        # distinct operators
        n2: int,        # distinct operands
        N1: int,        # total operators
        N2: int,        # total operands
        module_id: str = "",
        language:  str = "",
    ) -> "HalsteadVector":
        """Compute all 6 channels from raw Halstead primitives."""
        n1  = max(1, n1)
        n2  = max(1, n2)
        N1  = max(1, N1)
        N2  = max(1, N2)
        vocab  = n1 + n2
        length = N1 + N2
        V = length * math.log2(vocab)
        D = (n1 / 2) * (N2 / n2)
        E = D * V
        T = E / 18.0
        L = 1.0 / max(1e-9, D)
        N = length
        return cls(
            volume=round(V, 4),
            difficulty=round(D, 4),
            effort=round(E, 4),
            time_to_implement=round(T, 4),
            program_level=round(L, 6),
            token_count=N,
            module_id=module_id,
            language=language,
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def __repr__(self) -> str:
        return (
            f"HalsteadVector(V={self.volume:.1f}, D={self.difficulty:.2f}, "
            f"E={self.effort:.1f}, T={self.time_to_implement:.1f}s, "
            f"L={self.program_level:.4f}, N={self.token_count})"
        )


# ─── StructuralVector ────────────────────────────────────────────────────────

@dataclass
class StructuralVector:
    """
    7-channel structural / OO shape vector.

    Channels
    --------
    max_function_cc      — CC of the most complex function in the module
    cc_hotspot_ratio     — max_fn_cc / (avg_fn_cc × 3) capped at 1.0
    max_methods_per_class— largest method count in any single class
    n_functions          — total function/method definitions
    n_classes            — total class/struct/interface definitions
    comment_density      — comment lines / total lines  [0.0–1.0]
    test_ratio           — test functions / total functions [0.0–1.0]
    """
    max_function_cc:       int   = 1
    cc_hotspot_ratio:      float = 0.0
    max_methods_per_class: int   = 0
    n_functions:           int   = 0
    n_classes:             int   = 0
    comment_density:       float = 0.0
    test_ratio:            float = 0.0

    # ── source attribution ────────────────────────────────────────────────────
    module_id: str = ""
    language:  str = ""

    # ── constructors ──────────────────────────────────────────────────────────

    @classmethod
    def from_counts(
        cls,
        max_function_cc:        int,
        fn_cc_list:             list,
        max_methods_per_class:  int,
        n_functions:            int,
        n_classes:              int,
        source:                 str = "",
        module_id:              str = "",
        language:               str = "",
    ) -> "StructuralVector":
        """Compute all 7 channels from raw structural counts."""
        # CC hotspot ratio: how dominant is the worst function?
        if fn_cc_list and len(fn_cc_list) > 1:
            avg_fn_cc = sum(fn_cc_list) / len(fn_cc_list)
            hotspot = min(1.0, max_function_cc / max(1, avg_fn_cc * 3))
        else:
            hotspot = 0.0

        # Comment density from source lines
        comment_density = 0.0
        test_ratio      = 0.0
        if source and source.strip():
            all_lines = source.splitlines()
            total     = max(1, len(all_lines))
            cmt_lines = sum(
                1 for ln in all_lines
                if ln.strip().startswith(("#", "//", "--", "/*", "*", "'''", '"""'))
            )
            comment_density = min(1.0, cmt_lines / total)

            # Test ratio: functions whose name starts with test_/Test/spec/it(
            test_fns = sum(
                1 for ln in all_lines
                if any(kw in ln for kw in ("def test_", "func Test", "it(", "describe(", "test("))
            )
            if n_functions > 0:
                test_ratio = min(1.0, test_fns / n_functions)

        return cls(
            max_function_cc=max(1, max_function_cc),
            cc_hotspot_ratio=round(hotspot, 4),
            max_methods_per_class=max_methods_per_class,
            n_functions=n_functions,
            n_classes=n_classes,
            comment_density=round(comment_density, 4),
            test_ratio=round(test_ratio, 4),
            module_id=module_id,
            language=language,
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def __repr__(self) -> str:
        return (
            f"StructuralVector(max_fn_cc={self.max_function_cc}, "
            f"hotspot={self.cc_hotspot_ratio:.3f}, "
            f"fns={self.n_functions}, cls={self.n_classes}, "
            f"comment_density={self.comment_density:.3f})"
        )


# ─── SecurityVector ──────────────────────────────────────────────────────────

# SQALE debt constants (minutes per finding) — aligned with sast/scanner.py
_SQALE_CRITICAL = 240
_SQALE_HIGH     = 120
_SQALE_MEDIUM   =  60
_SQALE_LOW      =  30


@dataclass
class SecurityVector:
    """
    10-channel aggregated security posture vector.

    Channels
    --------
    sast_critical       — SAST findings at CRITICAL severity
    sast_high           — SAST findings at HIGH severity
    sast_medium         — SAST findings at MEDIUM severity
    sast_low            — SAST findings at LOW severity
    sast_security_rating— SQALE security rating [A=1 … E=5]
    sast_debt_minutes   — total SAST remediation debt (minutes)
    sca_vulnerable_deps — count of dependencies with known CVEs
    sca_cvss_max        — highest CVSS score among all SCA findings
    sca_debt_minutes    — total SCA remediation debt (minutes)
    iac_misconfig_count — IaC misconfiguration findings
    iac_privilege_score — max privilege-escalation score [0.0–1.0]
    """
    sast_critical:        int   = 0
    sast_high:            int   = 0
    sast_medium:          int   = 0
    sast_low:             int   = 0
    sast_security_rating: int   = 1      # A=1, B=2, C=3, D=4, E=5
    sast_debt_minutes:    int   = 0
    sca_vulnerable_deps:  int   = 0
    sca_cvss_max:         float = 0.0
    sca_debt_minutes:     int   = 0
    iac_misconfig_count:  int   = 0
    iac_privilege_score:  float = 0.0    # 0.0 = no privilege risk, 1.0 = highest

    # ── source attribution ────────────────────────────────────────────────────
    module_id:   str = ""
    scan_root:   str = ""

    # ── constructors ──────────────────────────────────────────────────────────

    @classmethod
    def from_sast_result(
        cls,
        sast_result: Any,
        module_id: str = "",
    ) -> "SecurityVector":
        """Populate SAST channels from a SASTResult object."""
        sv = cls(module_id=module_id)
        if sast_result is None:
            return sv

        sev_map = {}
        debt = 0
        for finding in getattr(sast_result, "findings", []):
            sev = getattr(finding, "severity", "LOW").upper()
            sev_map[sev] = sev_map.get(sev, 0) + 1
            debt += getattr(finding, "debt_minutes", 0)

        sv.sast_critical = sev_map.get("CRITICAL", 0)
        sv.sast_high     = sev_map.get("HIGH",     0)
        sv.sast_medium   = sev_map.get("MEDIUM",   0)
        sv.sast_low      = sev_map.get("LOW",      0)
        sv.sast_debt_minutes = debt
        sv.sast_security_rating = cls._rating(sv.sast_critical, sv.sast_high)
        return sv

    @classmethod
    def from_sca_result(
        cls,
        sca_result: Any,
        module_id: str = "",
    ) -> "SecurityVector":
        """Populate SCA channels from an SCAResult object."""
        sv = cls(module_id=module_id)
        if sca_result is None:
            return sv

        findings = getattr(sca_result, "findings", [])
        sv.sca_vulnerable_deps = len({
            f"{getattr(f, 'dependency', {}).get('name', '')}:{getattr(f, 'dependency', {}).get('version', '')}"
            for f in findings
        })
        cvss_scores = [
            getattr(f, "cvss_score", 0.0)
            for f in findings
        ]
        sv.sca_cvss_max = max(cvss_scores, default=0.0)
        sv.sca_debt_minutes = sum(
            getattr(f, "debt_minutes", 0) for f in findings
        )
        return sv

    @classmethod
    def from_iac_result(
        cls,
        iac_result: Any,
        module_id: str = "",
    ) -> "SecurityVector":
        """Populate IaC channels from an IaCScanResult object."""
        sv = cls(module_id=module_id)
        if iac_result is None:
            return sv

        sv.iac_misconfig_count = getattr(iac_result, "total_findings", 0)
        sv.iac_privilege_score = getattr(iac_result, "max_privilege_score", 0.0)
        return sv

    @classmethod
    def merge(cls, *vectors: "SecurityVector") -> "SecurityVector":
        """Merge multiple SecurityVectors into one aggregate."""
        merged = cls()
        for sv in vectors:
            merged.sast_critical       += sv.sast_critical
            merged.sast_high           += sv.sast_high
            merged.sast_medium         += sv.sast_medium
            merged.sast_low            += sv.sast_low
            merged.sast_debt_minutes   += sv.sast_debt_minutes
            merged.sca_vulnerable_deps += sv.sca_vulnerable_deps
            merged.sca_cvss_max         = max(merged.sca_cvss_max, sv.sca_cvss_max)
            merged.sca_debt_minutes    += sv.sca_debt_minutes
            merged.iac_misconfig_count += sv.iac_misconfig_count
            merged.iac_privilege_score  = max(merged.iac_privilege_score, sv.iac_privilege_score)
        merged.sast_security_rating = cls._rating(merged.sast_critical, merged.sast_high)
        return merged

    @staticmethod
    def _rating(critical: int, high: int) -> int:
        """SQALE-style A–E rating (1–5) based on SAST finding severity counts."""
        if critical > 0:
            return 5   # E — project is blocked
        if high >= 3:
            return 4   # D — significant risk
        if high >= 1:
            return 3   # C — needs attention
        return 2 if (critical + high) == 0 else 1

    def total_debt_minutes(self) -> int:
        return self.sast_debt_minutes + self.sca_debt_minutes

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def __repr__(self) -> str:
        return (
            f"SecurityVector(rating={self.sast_security_rating}, "
            f"sast=[C:{self.sast_critical}/H:{self.sast_high}/M:{self.sast_medium}/L:{self.sast_low}], "
            f"sca_vulns={self.sca_vulnerable_deps}, cvss_max={self.sca_cvss_max:.1f}, "
            f"iac={self.iac_misconfig_count}, priv={self.iac_privilege_score:.2f})"
        )


# ─── VelocityVector ──────────────────────────────────────────────────────────

@dataclass
class VelocityVector:
    """
    4-channel temporal-velocity / degradation trend vector.

    Channels
    --------
    hamiltonian_velocity  — ΔH per snapshot (positive = increasing complexity)
    cc_velocity           — ΔCC per snapshot
    degradation_hurst     — Hurst exponent H∈[0,1] — 0.5=random, >0.5=persistent trend
    regression_rate       — fraction of snapshots where a metric worsened
    """
    hamiltonian_velocity: float = 0.0
    cc_velocity:          float = 0.0
    degradation_hurst:    float = 0.5   # default: random walk
    regression_rate:      float = 0.0

    # ── source attribution ────────────────────────────────────────────────────
    module_id:   str = ""
    n_snapshots: int = 0

    # ── constructors ──────────────────────────────────────────────────────────

    @classmethod
    def from_forecast(
        cls,
        forecast: Any,
        module_id: str = "",
        n_snapshots: int = 0,
    ) -> "VelocityVector":
        """Populate from a DegradationForecast object (sensor_core/predictor.py)."""
        vv = cls(module_id=module_id, n_snapshots=n_snapshots)
        if forecast is None:
            return vv

        vv.hamiltonian_velocity = getattr(forecast, "velocity_h_per_snapshot", 0.0)
        vv.degradation_hurst    = getattr(forecast, "hurst_exponent", 0.5)
        # regression_rate and cc_velocity populated separately from trend data
        return vv

    @classmethod
    def from_trend(
        cls,
        trend: Any,
        hurst: float = 0.5,
        module_id: str = "",
        n_snapshots: int = 0,
    ) -> "VelocityVector":
        """Populate from a TrendAnalysis object (governance/trend_engine.py)."""
        vv = cls(
            module_id=module_id,
            n_snapshots=n_snapshots,
            degradation_hurst=hurst,
        )
        if trend is None:
            return vv

        # slope_pct as velocity proxy
        slope_pct = getattr(trend, "slope_pct", 0.0)
        vv.hamiltonian_velocity = round(slope_pct, 4)

        direction = getattr(trend, "direction", "stable")
        if direction == "degrading":
            vv.regression_rate = min(1.0, abs(slope_pct) / 100.0)
        return vv

    @classmethod
    def from_metric_series(
        cls,
        h_series: list,
        cc_series: list,
        module_id: str = "",
    ) -> "VelocityVector":
        """Compute velocity and regression rate directly from metric time-series."""
        vv = cls(module_id=module_id, n_snapshots=len(h_series))
        if len(h_series) < 2:
            return vv

        # Simple linear velocity (last - first) / n
        n = len(h_series)
        vv.hamiltonian_velocity = round((h_series[-1] - h_series[0]) / n, 6)

        if len(cc_series) >= 2:
            vv.cc_velocity = round((cc_series[-1] - cc_series[0]) / len(cc_series), 6)

        # Regression rate: fraction of consecutive pairs that worsened
        regressions = sum(
            1 for i in range(1, n)
            if h_series[i] > h_series[i - 1]
        )
        vv.regression_rate = round(regressions / (n - 1), 4)

        # Hurst exponent via R/S analysis (simplified — requires ≥8 points)
        if n >= 8:
            vv.degradation_hurst = round(cls._hurst_rs(h_series), 4)

        return vv

    @staticmethod
    def _hurst_rs(series: list) -> float:
        """
        Simplified R/S (rescaled range) Hurst exponent estimator.

        Returns H ∈ (0, 1):
          H > 0.5 → persistent trend (likely to continue degrading)
          H = 0.5 → random walk
          H < 0.5 → mean-reverting
        """
        import math as _math
        n = len(series)
        if n < 4:
            return 0.5
        mean = sum(series) / n
        deviations = [x - mean for x in series]
        cumulative = []
        s = 0.0
        for d in deviations:
            s += d
            cumulative.append(s)
        R = max(cumulative) - min(cumulative)
        variance = sum(d ** 2 for d in deviations) / n
        S = _math.sqrt(variance) if variance > 0 else 1.0
        if S == 0:
            return 0.5
        rs = R / S
        if rs <= 0:
            return 0.5
        # H = log(R/S) / log(n/2)
        H = _math.log(rs) / _math.log(n / 2)
        return max(0.01, min(0.99, H))

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def __repr__(self) -> str:
        return (
            f"VelocityVector(Δh={self.hamiltonian_velocity:+.4f}, "
            f"Δcc={self.cc_velocity:+.4f}, "
            f"hurst={self.degradation_hurst:.3f}, "
            f"regr={self.regression_rate:.3f})"
        )
