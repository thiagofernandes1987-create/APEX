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


# ─── AdvancedVector ──────────────────────────────────────────────────────────

@dataclass
class AdvancedVector:
    """
    6-channel advanced static-analysis vector  (M7.0).

    Formalizes signals computed by AdvancedAnalyzer (M1) that were previously
    computed on every request but never persisted — closing the 83% signal-loss
    gap identified in the M6.4 autopsy.

    Channels
    --------
    cognitive_cc_total  — module-level Cognitive Complexity (Campbell 2018)
    cognitive_cc_max    — highest Cognitive CC across all functions
    sqale_debt_minutes  — total SQALE technical debt (minutes to remediate)
    sqale_rating        — SQALE letter rating A (best) … E (worst)
    clone_count         — Type-2 AST clone groups detected
    fn_profile_count    — number of function profiles available (rich breakdown)

    References
    ----------
    Campbell, G.A. (2018). Cognitive Complexity. SonarSource SA.
    SQALE Method (2016). SQALE Technical Report, version 1.0.
    """
    cognitive_cc_total:  int   = 0
    cognitive_cc_max:    int   = 0
    sqale_debt_minutes:  int   = 0
    sqale_rating:        str   = "A"   # A=best … E=worst
    clone_count:         int   = 0
    fn_profile_count:    int   = 0

    # ── source attribution ────────────────────────────────────────────────────
    module_id:  str = ""
    language:   str = ""

    # ── constructors ──────────────────────────────────────────────────────────

    @classmethod
    def from_advanced_mv(
        cls,
        mv: Any,
        module_id: str = "",
        language:  str = "",
    ) -> "AdvancedVector":
        """
        Populate all 6 channels from a MetricVector enriched by AdvancedAnalyzer.

        AdvancedAnalyzer attaches its results as dynamic attributes via setattr,
        so we use getattr with safe defaults for any attribute that may be absent
        (e.g. when mode != "full" or when the source is not Python).
        """
        profiles = getattr(mv, "function_profiles", [])
        return cls(
            cognitive_cc_total=int(getattr(mv, "cognitive_complexity", 0)),
            cognitive_cc_max=int(getattr(mv, "cognitive_fn_max", 0)),
            sqale_debt_minutes=int(getattr(mv, "sqale_debt_minutes", 0)),
            sqale_rating=str(getattr(mv, "sqale_rating", "A")),
            clone_count=int(getattr(mv, "clone_count", 0)),
            fn_profile_count=len(profiles) if profiles else 0,
            module_id=module_id or getattr(mv, "module_id", ""),
            language=language or getattr(mv, "language", ""),
        )

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "AdvancedVector":
        """Deserialize from a JSON-compatible dict (SnapshotStore round-trip)."""
        return cls(
            cognitive_cc_total=int(d.get("cognitive_cc_total", 0)),
            cognitive_cc_max=int(d.get("cognitive_cc_max", 0)),
            sqale_debt_minutes=int(d.get("sqale_debt_minutes", 0)),
            sqale_rating=str(d.get("sqale_rating", "A")),
            clone_count=int(d.get("clone_count", 0)),
            fn_profile_count=int(d.get("fn_profile_count", 0)),
            module_id=str(d.get("module_id", "")),
            language=str(d.get("language", "")),
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def sqale_debt_hours(self) -> float:
        """Convert debt to hours (convenience helper)."""
        return round(self.sqale_debt_minutes / 60.0, 2)

    def __repr__(self) -> str:
        return (
            f"AdvancedVector(cog_cc={self.cognitive_cc_total}, "
            f"cog_max={self.cognitive_cc_max}, "
            f"sqale={self.sqale_rating}({self.sqale_debt_minutes}min), "
            f"clones={self.clone_count}, fns={self.fn_profile_count})"
        )


# ─── DiagnosticVector ────────────────────────────────────────────────────────

# Onset-reversibility mapping by temporal pattern  (heuristic calibration)
_REVERSIBILITY_BY_PATTERN: Dict[str, float] = {
    "spike":       0.80,   # spikes self-resolve after the transient
    "stable":      1.00,   # nothing to reverse
    "oscillating": 0.55,   # partial reversal possible
    "step":        0.35,   # step changes are structurally sticky
    "monotone":    0.15,   # monotone growth — needs active intervention
}


@dataclass
class DiagnosticVector:
    """
    8-channel spectral diagnostic vector  (M7.0).

    Formalizes the FrequencyEngine persistence/causalidade signals that were
    computed inside ClassificationResult but never surfaced beyond the
    /analyze response JSON — and therefore never persisted or trended.

    Channels
    --------
    dominant_frequency_H  — dominant Fourier frequency of H series [0.0–0.5 Hz_norm]
    spectral_entropy_H    — Shannon spectral entropy of H channel [0.0=periodic … 1.0=noise]
    phase_coupling_CC_H   — Phase Coupling Index (CC ↔ H via Hilbert) [0.0–1.0]
    burst_index           — temporal concentration of ΔH (acute vs chronic) [0.0–1.0]
    self_cure_probability — P(system self-corrects without intervention) [0.0–1.0]
    onset_reversibility   — ease of reversing the detected degradation [0.0–1.0]
    degradation_signature — primary FrequencyEngine error-type label
    frequency_anomaly_score— overall anomaly severity score [0.0–1.0]

    References
    ----------
    Hurst, H.E. (1951). Long-term storage capacity of reservoirs. ASCE Trans.
    Hilbert transform Phase Coupling Index: Lachaux et al. (1999). Hum. Brain Map.
    """
    dominant_frequency_H:   float = 0.0    # norm. freq. in H-series PSD
    spectral_entropy_H:     float = 0.5    # Shannon entropy [0=periodic, 1=noise]
    phase_coupling_CC_H:    float = 0.0    # Hilbert PCI CC↔H [0–1]
    burst_index:            float = 0.0    # acute-vs-chronic indicator [0–1]
    self_cure_probability:  float = 0.0    # P(auto-resolution) [0–1]
    onset_reversibility:    float = 0.5    # reversal ease [0–1]
    degradation_signature:  str   = "STABLE"   # primary_error label
    frequency_anomaly_score: float = 0.0   # severity_score [0–1]

    # ── source attribution ────────────────────────────────────────────────────
    module_id:   str = ""
    n_snapshots: int = 0

    # ── constructors ──────────────────────────────────────────────────────────

    @classmethod
    def from_classification_result(
        cls,
        result: Any,
        module_id: str = "",
        n_snapshots: int = 0,
    ) -> "DiagnosticVector":
        """
        Populate all 8 channels from a FrequencyEngine ClassificationResult.

        Uses getattr with safe defaults so this works regardless of which
        fields are present on the result object (forward/backward compat).
        """
        if result is None:
            return cls(module_id=module_id, n_snapshots=n_snapshots)

        # ── spectral_evidence dict extraction ─────────────────────────────────
        ev: Dict[str, Any] = getattr(result, "spectral_evidence", {}) or {}

        # dominant_frequency_H — from spectral_evidence if classifier exposed it,
        # otherwise fall back to hflf_ratio_H as a band-position proxy.
        dom_freq = float(ev.get("H_dominant_freq", ev.get("dominant_freq_H", 0.0)))

        # spectral_entropy_H — classifier may or may not expose it in evidence
        sp_entropy = float(ev.get("H_spectral_entropy", ev.get("spectral_entropy_H", 0.5)))
        sp_entropy = max(0.0, min(1.0, sp_entropy))

        # burst_index — use burst_index_H directly from ClassificationResult
        burst = float(getattr(result, "burst_index_H", 0.0))
        burst = max(0.0, min(1.0, burst))

        # phase_coupling_CC_H — direct field
        pci = float(getattr(result, "phase_coupling_CC_H", 0.0))
        pci = max(0.0, min(1.0, pci))

        # self_cure_probability — stored as [0–100] percentage → normalize to [0–1]
        scp_raw = float(getattr(result, "self_cure_probability", 0.0))
        scp = max(0.0, min(1.0, scp_raw / 100.0 if scp_raw > 1.0 else scp_raw))

        # onset_reversibility — direct field [0–1]
        rev = float(getattr(result, "onset_reversibility", 0.5))
        rev = max(0.0, min(1.0, rev))

        # degradation_signature
        sig = str(getattr(result, "primary_error", "STABLE"))

        # frequency_anomaly_score = severity_score [0–1]
        fas = float(getattr(result, "severity_score", 0.0))
        fas = max(0.0, min(1.0, fas))

        return cls(
            dominant_frequency_H=round(dom_freq, 6),
            spectral_entropy_H=round(sp_entropy, 4),
            phase_coupling_CC_H=round(pci, 4),
            burst_index=round(burst, 4),
            self_cure_probability=round(scp, 4),
            onset_reversibility=round(rev, 4),
            degradation_signature=sig,
            frequency_anomaly_score=round(fas, 4),
            module_id=module_id or getattr(result, "module_id", ""),
            n_snapshots=n_snapshots,
        )

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "DiagnosticVector":
        """Deserialize from a JSON-compatible dict (SnapshotStore round-trip)."""
        return cls(
            dominant_frequency_H=float(d.get("dominant_frequency_H", 0.0)),
            spectral_entropy_H=float(d.get("spectral_entropy_H", 0.5)),
            phase_coupling_CC_H=float(d.get("phase_coupling_CC_H", 0.0)),
            burst_index=float(d.get("burst_index", 0.0)),
            self_cure_probability=float(d.get("self_cure_probability", 0.0)),
            onset_reversibility=float(d.get("onset_reversibility", 0.5)),
            degradation_signature=str(d.get("degradation_signature", "STABLE")),
            frequency_anomaly_score=float(d.get("frequency_anomaly_score", 0.0)),
            module_id=str(d.get("module_id", "")),
            n_snapshots=int(d.get("n_snapshots", 0)),
        )

    def is_chronic(self) -> bool:
        """True when onset_reversibility < 0.20 — structural problem requiring intervention."""
        return self.onset_reversibility < 0.20

    def risk_tier(self) -> str:
        """
        3-tier risk classification based on anomaly score and reversibility.

        CRITICAL — frequency_anomaly_score ≥ 0.70 OR (score ≥ 0.40 AND chronic)
        WARNING  — frequency_anomaly_score ≥ 0.30 OR is_chronic
        STABLE   — below all thresholds
        """
        if self.frequency_anomaly_score >= 0.70:
            return "CRITICAL"
        if self.frequency_anomaly_score >= 0.40 and self.is_chronic():
            return "CRITICAL"
        if self.frequency_anomaly_score >= 0.30 or self.is_chronic():
            return "WARNING"
        return "STABLE"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def __repr__(self) -> str:
        return (
            f"DiagnosticVector(sig={self.degradation_signature}, "
            f"score={self.frequency_anomaly_score:.3f}, "
            f"burst={self.burst_index:.3f}, "
            f"pci={self.phase_coupling_CC_H:.3f}, "
            f"scp={self.self_cure_probability:.3f}, "
            f"rev={self.onset_reversibility:.3f})"
        )


# ─── ReliabilityVector (M7.3a) ───────────────────────────────────────────────

@dataclass
class ReliabilityVector:
    """
    10-channel reliability signal vector — M7.3a.

    Formalizes AST-IMP counters from _UCOVisitor into a typed, persistable
    vector. All channels feed directly from MetricVector attrs set by UCOBridge.

    Channels
    --------
    bare_except_count           : int   — ExceptHandler(type=None) occurrences
    swallowed_exception_count   : int   — except: pass (silent error discard)
    mutable_default_arg_count   : int   — def f(x=[]/{}/ set()) occurrences
    inconsistent_return_count   : int   — functions mixing Return(v) + fall-through
    shadow_builtin_count        : int   — assignments that shadow builtins
    global_mutation_count       : int   — global x + subsequent assignment
    empty_except_block_count    : int   — alias for swallowed_exception_count (CWE-390)
    resource_leak_risk          : int   — open() outside `with` (from SAST037 count)
    regex_redos_risk            : int   — SAST019 ReDoS pattern count
    infinite_recursion_risk     : float — ILR proxy from MetricVector

    CWE coverage
    ------------
    CWE-390: bare_except_count, swallowed_exception_count
    CWE-1220: mutable_default_arg_count
    CWE-394: inconsistent_return_count
    CWE-362: global_mutation_count
    CWE-772: resource_leak_risk
    CWE-1333: regex_redos_risk
    CWE-674: infinite_recursion_risk
    """

    # ── fields ───────────────────────────────────────────────────────────────
    bare_except_count:          int   = 0
    swallowed_exception_count:  int   = 0
    mutable_default_arg_count:  int   = 0
    inconsistent_return_count:  int   = 0
    shadow_builtin_count:       int   = 0
    global_mutation_count:      int   = 0
    empty_except_block_count:   int   = 0   # alias: swallowed_exception_count
    resource_leak_risk:         int   = 0
    regex_redos_risk:           int   = 0
    infinite_recursion_risk:    float = 0.0

    # ── metadata ─────────────────────────────────────────────────────────────
    module_id: str = ""
    language:  str = "python"

    # ── constructors ─────────────────────────────────────────────────────────

    @classmethod
    def from_mv(cls, mv, sast_result=None) -> "ReliabilityVector":
        """
        Build ReliabilityVector from a MetricVector (post-UCOBridge) and an
        optional SASTResult (to count resource-leak and ReDoS findings).

        Parameters
        ----------
        mv          : MetricVector — must have AST-IMP attrs attached by UCOBridge
        sast_result : SASTResult | None — scanner result for SAST037/SAST019 counts
        """
        resource_leak = 0
        redos_risk    = 0
        if sast_result is not None:
            for f in getattr(sast_result, "findings", []):
                if f.rule_id == "SAST037":
                    resource_leak += 1
                if f.rule_id == "SAST019":
                    redos_risk += 1

        swallowed = getattr(mv, "swallowed_exception_count", 0)
        return cls(
            bare_except_count         = getattr(mv, "bare_except_count", 0),
            swallowed_exception_count = swallowed,
            mutable_default_arg_count = getattr(mv, "mutable_default_arg_count", 0),
            inconsistent_return_count = getattr(mv, "inconsistent_return_count", 0),
            shadow_builtin_count      = getattr(mv, "shadow_builtin_count", 0),
            global_mutation_count     = getattr(mv, "global_mutation_count", 0),
            empty_except_block_count  = swallowed,      # alias
            resource_leak_risk        = resource_leak,
            regex_redos_risk          = redos_risk,
            infinite_recursion_risk   = round(
                min(1.0, getattr(mv, "infinite_loop_risk", 0.0)), 4
            ),
            module_id = getattr(mv, "module_id", ""),
            language  = getattr(mv, "language", "python"),
        )

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ReliabilityVector":
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in d.items() if k in known})

    # ── derived properties ────────────────────────────────────────────────────

    @property
    def total_issues(self) -> int:
        """Sum of all integer reliability issue counts."""
        return (
            self.bare_except_count
            + self.swallowed_exception_count
            + self.mutable_default_arg_count
            + self.inconsistent_return_count
            + self.shadow_builtin_count
            + self.global_mutation_count
            + self.resource_leak_risk
            + self.regex_redos_risk
        )

    def reliability_rating(self) -> str:
        """
        A–E rating based on total issue count and infinite_recursion_risk.

          A: 0 issues, ILR < 0.1
          B: 1–2 issues OR ILR 0.1–0.3
          C: 3–5 issues OR ILR 0.3–0.5
          D: 6–10 issues OR ILR > 0.5
          E: >10 issues OR bare_except > 3 OR global_mutation > 2
        """
        issues = self.total_issues
        ilr    = self.infinite_recursion_risk
        if issues > 10 or self.bare_except_count > 3 or self.global_mutation_count > 2:
            return "E"
        if issues >= 6 or ilr > 0.5:
            return "D"
        if issues >= 3 or ilr > 0.3:
            return "C"
        if issues >= 1 or ilr > 0.1:
            return "B"
        return "A"

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["total_issues"]       = self.total_issues
        d["reliability_rating"] = self.reliability_rating()
        return d

    def __repr__(self) -> str:
        return (
            f"ReliabilityVector("
            f"rating={self.reliability_rating()}, "
            f"issues={self.total_issues}, "
            f"bare_except={self.bare_except_count}, "
            f"swallowed={self.swallowed_exception_count}, "
            f"ilr={self.infinite_recursion_risk:.3f})"
        )


# ─── MaintainabilityVector (M7.3b) ───────────────────────────────────────────

@dataclass
class MaintainabilityVector:
    """
    9-channel maintainability signal vector — M7.3b.

    Aggregates structural quality signals derived from AST analysis.
    All channels are normalized to [0.0, 1.0] or bounded integers.

    Channels
    --------
    missing_docstring_ratio    : float — public fns without docstring / total public fns
    avg_function_args          : float — mean arg count per function
    long_function_ratio        : float — fns with LOC > 50 / total fns
    deeply_nested_ratio        : float — deeply_nested_comprehension_count / n_functions
    cognitive_cc_hotspot       : int   — max Cognitive CC across all functions
    boolean_param_count        : int   — params with default True/False
    magic_number_count         : int   — numeric literals ∉ {-1, 0, 1, 2} outside constants
    long_parameter_list        : int   — functions with > 5 parameters
    invariant_density          : float — (docstring_ratio + type_hint_proxy) / 2

    Thresholds (WARNING)
    --------------------
    missing_docstring_ratio > 0.5  → WARNING
    avg_function_args > 4.0        → WARNING
    long_function_ratio > 0.2      → WARNING
    deeply_nested_ratio > 0.1      → WARNING
    cognitive_cc_hotspot > 20      → CRITICAL
    boolean_param_count > 3        → WARNING
    magic_number_count > 10        → WARNING
    long_parameter_list > 2        → WARNING
    invariant_density < 0.3        → WARNING
    """

    # ── fields ───────────────────────────────────────────────────────────────
    missing_docstring_ratio:    float = 0.0
    avg_function_args:          float = 0.0
    long_function_ratio:        float = 0.0
    deeply_nested_ratio:        float = 0.0
    cognitive_cc_hotspot:       int   = 0
    boolean_param_count:        int   = 0
    magic_number_count:         int   = 0
    long_parameter_list:        int   = 0
    invariant_density:          float = 0.5

    # ── metadata ─────────────────────────────────────────────────────────────
    module_id: str = ""
    language:  str = "python"

    # ── constructors ─────────────────────────────────────────────────────────

    @classmethod
    def from_mv(cls, mv, source: str = "") -> "MaintainabilityVector":
        """
        Build MaintainabilityVector from MetricVector + (optionally) raw source.

        Parameters
        ----------
        mv     : MetricVector — must have AST-IMP attrs and n_functions
        source : raw Python source — enables magic_number, boolean_param,
                 docstring and long_function analysis via a lightweight AST pass
        """
        n_fns = max(1, getattr(mv, "n_functions", 1))

        # Default values (available from MetricVector without re-parse)
        deeply_nested_ratio = round(
            min(1.0, getattr(mv, "deeply_nested_comprehension_count", 0) / n_fns), 4
        )
        cognitive_hotspot = getattr(mv, "max_function_cc", 0)

        # Fields that require AST re-walk of source
        missing_doc_ratio   = 0.0
        avg_args            = 0.0
        long_fn_ratio       = 0.0
        bool_param_count    = 0
        magic_num_count     = 0
        long_param_list     = 0
        docstring_ratio     = 0.0

        if source:
            try:
                import ast as _ast
                tree = _ast.parse(source)
                lines = source.splitlines()
                (missing_doc_ratio, avg_args, long_fn_ratio,
                 bool_param_count, magic_num_count, long_param_list,
                 docstring_ratio) = _analyse_maintainability(tree, lines)
            except SyntaxError:
                pass

        # invariant_density: proxy = (docstring_ratio + 0.5*type_hint_proxy) / 1.5
        # type_hint_proxy uses loc-normalized assertions as a simplification
        loc = max(1, getattr(mv, "lines_of_code", 1))
        assert_proxy = min(1.0, getattr(mv, "syntactic_dead_code", 0) * 0.0)  # 0 — no assert count yet
        invariant_d = round(min(1.0, (docstring_ratio + assert_proxy) / max(1.0, 1.0)), 4)

        return cls(
            missing_docstring_ratio = round(missing_doc_ratio, 4),
            avg_function_args       = round(avg_args, 4),
            long_function_ratio     = round(long_fn_ratio, 4),
            deeply_nested_ratio     = deeply_nested_ratio,
            cognitive_cc_hotspot    = cognitive_hotspot,
            boolean_param_count     = bool_param_count,
            magic_number_count      = magic_num_count,
            long_parameter_list     = long_param_list,
            invariant_density       = invariant_d,
            module_id = getattr(mv, "module_id", ""),
            language  = getattr(mv, "language", "python"),
        )

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "MaintainabilityVector":
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in d.items() if k in known})

    # ── derived properties ────────────────────────────────────────────────────

    def maintainability_rating(self) -> str:
        """
        A–E Maintainability rating.

          A: no warnings
          B: 1–2 mild warnings
          C: 3–4 warnings OR cognitive_hotspot > 20
          D: 5+ warnings
          E: cognitive_hotspot > 30 OR missing_docstring_ratio > 0.8
        """
        hotspot = self.cognitive_cc_hotspot
        if hotspot > 30 or self.missing_docstring_ratio > 0.8:
            return "E"
        warnings = sum([
            self.missing_docstring_ratio > 0.5,
            self.avg_function_args > 4.0,
            self.long_function_ratio > 0.2,
            self.deeply_nested_ratio > 0.1,
            hotspot > 20,
            self.boolean_param_count > 3,
            self.magic_number_count > 10,
            self.long_parameter_list > 2,
            self.invariant_density < 0.3,
        ])
        if warnings >= 5:
            return "D"
        if warnings >= 3 or hotspot > 20:
            return "C"
        if warnings >= 1:
            return "B"
        return "A"

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["maintainability_rating"] = self.maintainability_rating()
        return d

    def __repr__(self) -> str:
        return (
            f"MaintainabilityVector("
            f"rating={self.maintainability_rating()}, "
            f"miss_doc={self.missing_docstring_ratio:.2f}, "
            f"cc_hot={self.cognitive_cc_hotspot}, "
            f"magic={self.magic_number_count})"
        )


# ─── AST helper for MaintainabilityVector ────────────────────────────────────

def _analyse_maintainability(tree, lines):
    """
    Single-pass AST analysis for MaintainabilityVector fields that require
    re-walking the source tree.

    Returns
    -------
    (missing_docstring_ratio, avg_function_args, long_function_ratio,
     boolean_param_count, magic_number_count, long_parameter_list,
     docstring_ratio)
    """
    import ast as _ast

    _MAGIC_EXEMPT = frozenset({-1, 0, 1, 2})

    total_fns       = 0
    public_fns      = 0
    fns_with_doc    = 0
    fns_long        = 0      # LOC > 50
    fns_long_params = 0      # > 5 params
    total_args      = 0
    bool_params     = 0
    magic_numbers   = 0

    for node in _ast.walk(tree):
        if not isinstance(node, (_ast.FunctionDef, _ast.AsyncFunctionDef)):
            continue
        total_fns += 1
        fn_name = node.name

        # docstring presence
        is_public = not fn_name.startswith("_")
        if is_public:
            public_fns += 1
            has_doc = (
                node.body
                and isinstance(node.body[0], _ast.Expr)
                and isinstance(node.body[0].value, _ast.Constant)
                and isinstance(node.body[0].value.value, str)
            )
            if has_doc:
                fns_with_doc += 1

        # function length (approx: end_lineno - lineno)
        fn_loc = (getattr(node, "end_lineno", node.lineno) - node.lineno + 1)
        if fn_loc > 50:
            fns_long += 1

        # args
        all_args = (
            node.args.args
            + node.args.posonlyargs
            + node.args.kwonlyargs
        )
        n_args = len(all_args)
        total_args += n_args
        if n_args > 5:
            fns_long_params += 1

        # boolean defaults (True/False)
        for default in node.args.defaults + node.args.kw_defaults:
            if default is None:
                continue
            if isinstance(default, _ast.Constant) and isinstance(default.value, bool):
                bool_params += 1

    # magic numbers: scan entire tree for numeric literals
    for node in _ast.walk(tree):
        if isinstance(node, _ast.Constant) and isinstance(node.value, (int, float)):
            if node.value not in _MAGIC_EXEMPT and not isinstance(node.value, bool):
                magic_numbers += 1

    n_fns  = max(1, total_fns)
    n_pub  = max(1, public_fns)

    missing_doc_ratio = round(1.0 - fns_with_doc / n_pub, 4) if public_fns > 0 else 0.0
    docstring_ratio   = round(fns_with_doc / n_pub, 4) if public_fns > 0 else 0.0
    avg_args          = round(total_args / n_fns, 4)
    long_fn_ratio     = round(fns_long / n_fns, 4)

    return (
        missing_doc_ratio,
        avg_args,
        long_fn_ratio,
        bool_params,
        magic_numbers,
        fns_long_params,
        docstring_ratio,
    )
