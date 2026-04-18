"""
UCO-Sensor FrequencyEngine — Roteador de Output
================================================
SignalOutputRouter: formata ClassificationResult para múltiplas audiências.

Cada formato fala a linguagem da sua audiência:
  DEVELOPER  — JSON técnico com evidências espectrais completas
  SLACK      — Block Kit conversacional para canal de alertas
  SARIF      — Static Analysis Results Interchange Format (GitHub/VS Code)
  REGULATORY — JSON imutável com hash SHA-256 para compliance
  APEX       — Evento estruturado para o event_bus do APEX
  PROMETHEUS — Métricas no formato text exposition
  GITHUB     — GitHub Checks API (status check em PR)
  SUMMARY    — Texto humano multi-linha (CLI / logs)
"""
from __future__ import annotations
import json
import hashlib
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from enum import Enum

from core.constants import GRADE_CONFIRMED_MIN_CONF, GRADE_LIKELY_MIN_CONF
from core.data_structures import ClassificationResult


class OutputFormat(Enum):
    DEVELOPER  = "developer"
    SLACK      = "slack"
    SARIF      = "sarif"
    REGULATORY = "regulatory"
    APEX       = "apex"
    PROMETHEUS = "prometheus"
    GITHUB     = "github"
    SUMMARY    = "summary"


_SEVERITY_TO_SARIF = {"INFO": "note", "WARNING": "warning", "CRITICAL": "error"}
_SEVERITY_TO_GH    = {"INFO": "neutral", "WARNING": "action_required", "CRITICAL": "failure"}
_SEVERITY_EMOJI    = {"INFO": "ℹ️", "WARNING": "⚠️", "CRITICAL": "🚨"}

# Modo APEX sugerido por banda
_BAND_TO_APEX_MODE = {
    "ULF": "RESEARCH",
    "LF":  "DEEP",
    "MF":  "DEEP",
    "HF":  "FAST",
    "UHF": "FAST",
}


class SignalOutputRouter:
    """
    Transforma ClassificationResult em qualquer formato de output.

    Uso:
        router = SignalOutputRouter()
        payload = router.route(result, OutputFormat.SLACK)
        payload = router.route(result, OutputFormat.DEVELOPER)
    """

    def route(
        self,
        result: ClassificationResult,
        target: OutputFormat,
        include_hypotheses: bool = True,
    ) -> Any:
        dispatch = {
            OutputFormat.DEVELOPER:  self._to_developer,
            OutputFormat.SLACK:      self._to_slack,
            OutputFormat.SARIF:      self._to_sarif,
            OutputFormat.REGULATORY: self._to_regulatory,
            OutputFormat.APEX:       self._to_apex,
            OutputFormat.PROMETHEUS: self._to_prometheus,
            OutputFormat.GITHUB:     self._to_github,
            OutputFormat.SUMMARY:    self._to_summary,
        }
        return dispatch[target](result, include_hypotheses)

    # ─── Developer JSON ───────────────────────────────────────────────────────

    def _to_developer(self, r: ClassificationResult, _: bool) -> Dict:
        cp = None
        if r.change_point:
            cp = {
                "commit_idx":   r.change_point.commit_idx,
                "commit_hash":  r.change_point.commit_hash,
                "confidence":   round(r.change_point.confidence, 4),
                "magnitude":    round(r.change_point.magnitude, 4),
                "affected_channels": r.change_point.affected_channels,
            }

        hypotheses = []
        for h in r.hypotheses[:3]:
            hypotheses.append({
                "type":       h.error_type,
                "confidence": round(h.confidence, 4),
                "band":       h.matched_band,
                "pattern":    h.temporal_pattern,
            })


        # GAP-V1: flag de integridade espectral
        spectral_warning = None
        if not r.is_spectrally_valid:
            spectral_warning = (
                f"Resultado NÃO confiável (N={r.n_commits_analyzed} < 30). "
                f"Tipo '{r.primary_error}' é especulativo. "
                "Recomendação: git clone --depth=0 para diagnóstico confiável."
            )
        # GAP-I4: actionable suggestion when data is insufficient
        clone_action = {
            "command": "git clone --depth=0 <repo_url> <local_path>",
            "reason": f"N={r.n_commits_analyzed} insuficiente (mínimo=30)",
            "precision_gain": "INSUFFICIENT → LIKELY/CONFIRMED com N≥100",
        } if not r.is_spectrally_valid else None

        return {
            "uco_sensor": {
                "version": "0.2",
                "module_id": r.module_id,
                "analysis_timestamp": r.analysis_timestamp,
                "classification": {
                    "primary_error":    r.primary_error,
                    "confidence":       round(r.primary_confidence, 4),
                    "severity":         r.severity,
                    "severity_score":   round(r.severity_score, 4),
                },
                "frequency": {
                    "dominant_band":    r.dominant_band,
                    "band_description": r.band_description,
                },
                "onset":     cp,
                "hypotheses": hypotheses,
                "evidence":  r.spectral_evidence,
                "transforms": {
                    "suggested":   r.suggested_transforms,
                    "delta_h_est": r.potential_delta_h,
                },
                "meta": {
                    "n_commits_analyzed": r.n_commits_analyzed,
                    "action": r.hypotheses[0].recommended_action if r.hypotheses else "",
                },
                "persistence": {
                    "hurst_H":              r.hurst_H,
                    "phase_coupling_CC_H":  r.phase_coupling_CC_H,
                    "burst_index_H":        r.burst_index_H,
                    "hflf_ratio_H":         r.hflf_ratio_H,
                    "onset_reversibility":  r.onset_reversibility,
                    "onset_confidence":      r.onset_confidence_context,
                    "self_cure_probability": r.self_cure_probability,
                    "intervention_required": r.hurst_H > 0.85 or r.self_cure_probability < 5.0,
                    "n_stable_channels":     r.n_stable_channels,
                    "spectral_signal_quality": r.spectral_signal_quality,
                    "classification_grade":  r.classification_grade,
                    "is_spectrally_valid":   r.is_spectrally_valid,    # GAP-V1
                    "spectral_warning":      spectral_warning,          # GAP-V1
                    "clone_action":          clone_action,              # GAP-I4
                    "chronic": r.hurst_H > 0.90,
                    "acute":   r.burst_index_H > 0.45,
                },
            }
        }

    # ─── Slack Block Kit ──────────────────────────────────────────────────────

    def _to_slack(self, r: ClassificationResult, _: bool) -> Dict:
        emoji = _SEVERITY_EMOJI.get(r.severity, "❓")
        cp_str = ""
        if r.change_point and r.change_point.commit_hash:
            cp_str = f"\n*Onset:* `{r.change_point.commit_hash[:8]}`"

        fields = [
            {"type": "mrkdwn", "text": f"*Módulo:*\n`{r.module_id}`"},
            {"type": "mrkdwn", "text": f"*Tipo de erro:*\n{r.primary_error}"},
            {"type": "mrkdwn", "text": f"*Severidade:*\n{r.severity}"},
            {"type": "mrkdwn", "text": f"*Confiança:*\n{r.primary_confidence:.0%}"},
            {"type": "mrkdwn", "text": f"*Banda:*\n{r.dominant_band}"},
            {"type": "mrkdwn", "text": f"*Commits analisados:*\n{r.n_commits_analyzed}"},
        ]

        blocks = [
            {"type": "header",
             "text": {"type": "plain_text",
                      "text": f"{emoji} UCO-Sensor: {r.primary_error}"}},
            {"type": "section",
             "text": {"type": "mrkdwn",
                      "text": r.plain_english[:350] + cp_str}},
            {"type": "section", "fields": fields},
        ]

        if r.suggested_transforms:
            blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn",
                         "text": (f"*Transforms sugeridos:* `{'`, `'.join(r.suggested_transforms)}`"
                                  f"\n*ΔH potencial:* {r.potential_delta_h:+.1f}")},
            })

        return {"blocks": blocks}

    # ─── SARIF 2.1.0 ─────────────────────────────────────────────────────────

    def _to_sarif(self, r: ClassificationResult, _: bool) -> Dict:
        desc = r.hypotheses[0].description if r.hypotheses else r.primary_error
        return {
            "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
            "version": "2.1.0",
            "runs": [{
                "tool": {
                    "driver": {
                        "name": "UCO-Sensor FrequencyEngine",
                        "version": "0.2.0",
                        "informationUri": "https://github.com/apex-ecosystem/uco-sensor",
                        "rules": [{
                            "id": r.primary_error,
                            "name": r.primary_error.replace("_", ""),
                            "shortDescription": {"text": desc},
                            "properties": {
                                "dominant_band": r.dominant_band,
                                "severity": r.severity,
                            },
                        }],
                    }
                },
                "results": [{
                    "ruleId": r.primary_error,
                    "level": _SEVERITY_TO_SARIF.get(r.severity, "note"),
                    "message": {"text": r.plain_english},
                    "locations": [{
                        "logicalLocations": [{
                            "name": r.module_id,
                            "kind": "module",
                        }]
                    }],
                    "properties": {
                        "confidence":           r.primary_confidence,
                        "frequency_band":       r.dominant_band,
                        "change_point_idx":     r.change_point.commit_idx if r.change_point else None,
                        "suggested_transforms": r.suggested_transforms,
                        "spectral_evidence":    r.spectral_evidence,
                        "persistence": {
                            "hurst_H":             r.hurst_H,
                            "self_cure_pct":       r.self_cure_probability,
                            "onset_reversibility": r.onset_reversibility,
                            "burst_index_H":       r.burst_index_H,
                            "hflf_ratio_H":        r.hflf_ratio_H,
                        },
                    },
                }],
            }],
        }

    # ─── Regulatório imutável ─────────────────────────────────────────────────

    def _to_regulatory(self, r: ClassificationResult, _: bool) -> Dict:
        payload = {
            "report_type": "UCO_SENSOR_STRUCTURAL_AUDIT",
            "standard_compliance": ["DO-178C", "IEC-62304", "IEC-61508", "PCI-DSS"],
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "generator": "UCO-Sensor FrequencyEngine v0.2.0",
            "module_id": r.module_id,
            "finding": {
                "error_type":         r.primary_error,
                "confidence":         round(r.primary_confidence, 6),
                "severity":           r.severity,
                "severity_score":     round(r.severity_score, 6),
                "frequency_band":     r.dominant_band,
                "band_description":   r.band_description,
                "onset_commit_idx":   r.change_point.commit_idx if r.change_point else None,
                "onset_commit_hash":  r.change_point.commit_hash if r.change_point else None,
                "onset_confidence":   round(r.change_point.confidence, 6) if r.change_point else None,
            },
            "spectral_evidence":       r.spectral_evidence,
            "persistence_metrics": {
                "hurst_H":               r.hurst_H,
                "phase_coupling_CC_H":   r.phase_coupling_CC_H,
                "burst_index_H":         r.burst_index_H,
                "hflf_ratio_H":          r.hflf_ratio_H,
                "onset_reversibility":   r.onset_reversibility,
                "onset_confidence":      r.onset_confidence_context,
                "self_cure_probability": r.self_cure_probability,
                "spectral_signal_quality": r.spectral_signal_quality,
                "classification_grade":    r.classification_grade,
                "chronic":               r.hurst_H > 0.90,
                "intervention_mandatory": r.hurst_H > 0.85 or r.self_cure_probability < 5.0,
            },
            "hypotheses_considered": [
                {"type": h.error_type, "confidence": round(h.confidence, 6)}
                for h in r.hypotheses
            ],
            "commits_analyzed":        r.n_commits_analyzed,
            "plain_language_summary":  r.plain_english,
            "technical_evidence":      r.technical_summary,
            "recommended_action":
                r.hypotheses[0].recommended_action if r.hypotheses else "Review required",
        }
        # Hash imutável SHA-256
        payload_str = json.dumps(payload, sort_keys=True, default=str)
        payload["audit_hash"] = "sha256:" + hashlib.sha256(
            payload_str.encode("utf-8")
        ).hexdigest()
        return payload

    # ─── APEX Event Bus ───────────────────────────────────────────────────────

    def _to_apex(self, r: ClassificationResult, _: bool) -> Dict:
        return {
            "event": "UCO_ANOMALY_DETECTED",
            "version": "1.0",
            "payload": {
                "module_id":          r.module_id,
                "error_type":         r.primary_error,
                "severity":           r.severity,
                "frequency_band":     r.dominant_band,
                "confidence":         round(r.primary_confidence, 4),
                "change_point_commit": r.change_point.commit_hash if r.change_point else None,
                "apex_prompt":         r.apex_prompt,
                "suggested_mode":      _BAND_TO_APEX_MODE.get(r.dominant_band, "DEEP"),
                "suggested_agents":    self._suggest_agents(r.dominant_band, r.severity),
                "uco_transforms":      r.suggested_transforms,
                "delta_h_potential":   r.potential_delta_h,
                "persistence": {
                    "hurst_H":              r.hurst_H,
                    "phase_coupling_CC_H":  r.phase_coupling_CC_H,
                    "burst_index_H":        r.burst_index_H,
                    "hflf_ratio_H":         r.hflf_ratio_H,
                    "onset_reversibility":  r.onset_reversibility,
                    "onset_confidence":     r.onset_confidence_context,
                    "self_cure_pct":        r.self_cure_probability,
                    "spectral_signal_quality": r.spectral_signal_quality,
                    "classification_grade":    r.classification_grade,
                    "intervention_now":     r.hurst_H > 0.85,
                    "chronic":              r.hurst_H > 0.90,
                    "acute":                r.burst_index_H > 0.45,
                },
                "spectral_summary": {
                    "dominant_band":       r.dominant_band,
                    "primary_channels":
                        r.hypotheses[0].matched_channels if r.hypotheses else [],
                    "evidence":            r.spectral_evidence,
                },
            },
        }

    def _suggest_agents(self, band: str, severity: str):
        agents = ["critic", "engineer"]
        if severity == "CRITICAL":
            agents.append("diff_governance")
        if band in ("ULF", "LF"):
            agents.append("meta_learning_agent")
        return agents

    # ─── Prometheus ───────────────────────────────────────────────────────────

    def _to_prometheus(self, r: ClassificationResult, _: bool) -> str:
        labels = (
            f'module="{r.module_id}",'
            f'error_type="{r.primary_error}",'
            f'band="{r.dominant_band}",'
            f'severity="{r.severity}"'
        )
        lines = [
            "# HELP uco_sensor_anomaly_confidence Confidence da classificação [0,1]",
            "# TYPE uco_sensor_anomaly_confidence gauge",
            f"uco_sensor_anomaly_confidence{{{labels}}} {r.primary_confidence:.6f}",
            "# HELP uco_sensor_severity_score Score de severidade normalizado [0,1]",
            "# TYPE uco_sensor_severity_score gauge",
            f"uco_sensor_severity_score{{{labels}}} {r.severity_score:.6f}",
            "# HELP uco_sensor_commits_analyzed Commits analisados na janela",
            "# TYPE uco_sensor_commits_analyzed gauge",
            f"uco_sensor_commits_analyzed{{{labels}}} {r.n_commits_analyzed}",
        ]
        if r.change_point:
            lines += [
                "# HELP uco_sensor_onset_confidence Confiança do change point detectado",
                "# TYPE uco_sensor_onset_confidence gauge",
                f"uco_sensor_onset_confidence{{{labels}}} {r.change_point.confidence:.6f}",
            ]
        return "\n".join(lines) + "\n"

    # ─── GitHub Checks API ────────────────────────────────────────────────────

    def _to_github(self, r: ClassificationResult, _: bool) -> Dict:
        conclusion = _SEVERITY_TO_GH.get(r.severity, "neutral")
        module_path = r.module_id.replace(".", "/") + ".py"
        ann_level   = {"INFO": "notice", "WARNING": "warning", "CRITICAL": "failure"}

        return {
            "name": f"UCO-Sensor: {r.primary_error}",
            "status": "completed",
            "conclusion": conclusion,
            "output": {
                "title": (f"{r.severity}: {r.primary_error} "
                          f"({r.primary_confidence:.0%} confidence)"),
                "summary": r.plain_english,
                "text":    r.technical_summary,
                "annotations": [{
                    "path":             module_path,
                    "start_line":       1,
                    "end_line":         1,
                    "annotation_level": ann_level.get(r.severity, "notice"),
                    "message":          r.plain_english[:500],
                    "title":            r.primary_error,
                    "raw_details":      json.dumps(r.spectral_evidence, default=str),
                }],
            },
        }

    # ─── Summary texto legível ────────────────────────────────────────────────

    def _to_summary(self, r: ClassificationResult, _: bool) -> str:
        SEV = {"INFO": "\033[94m", "WARNING": "\033[93m", "CRITICAL": "\033[91m"}
        RESET = "\033[0m"
        c = SEV.get(r.severity, "")

        lines = [
            f"╔{'═'*63}╗",
            f"║  UCO-Sensor FrequencyEngine — {r.module_id:<31}║",
            f"╠{'═'*63}╣",
            f"║  {c}[{r.severity}]{RESET} {r.primary_error:<50}║",
            f"║  Confidence : {r.primary_confidence:.1%}   "
            f"Severity Score : {r.severity_score:.3f}             ║",
            f"║  Banda      : {r.dominant_band:<5}  "
            f"Commits : {r.n_commits_analyzed:<5}                          ║",
        ]

        if r.change_point:
            cp = r.change_point
            h = cp.commit_hash[:8] if cp.commit_hash else "N/A"
            lines.append(
                f"║  Onset      : commit {h}  conf={cp.confidence:.1%}"
                f"  mag={cp.magnitude:.2f}            ║"
            )

        lines += [
            f"╠{'═'*63}╣",
            f"║  {r.plain_english[:61]:<61}║",
            f"║  {r.plain_english[61:122]:<61}║" if len(r.plain_english) > 61 else f"║  {'':<61}║",
            f"╠{'═'*63}╣",
        ]

        for i, h in enumerate(r.hypotheses[:3]):
            lines.append(
                f"║  {i+1}. {h.error_type:<40} conf={h.confidence:.1%}  ║"
            )

        if r.suggested_transforms:
            lines.append(f"╠{'═'*63}╣")
            lines.append(
                f"║  Transforms : {str(r.suggested_transforms):<47}  ║"
            )
            lines.append(
                f"║  ΔH potencial: {r.potential_delta_h:+.1f}                                          ║"
            )

        lines.append(f"╚{'═'*63}╝")
        return "\n".join(lines)
