"""
UCO-Sensor FrequencyEngine — Classificador de Frequência
=========================================================
FrequencyClassifier: orquestra matching de assinaturas + change point + severity.

Input:  List[SpectralProfile] + MetricSignal
Output: ClassificationResult com tipo, confiança, onset, plain_english, apex_prompt

Pipeline:
  1. Matching de assinaturas (ErrorSignatureLibrary.match)
  2. Detecção de change point (ChangePointDetector.detect)
  3. Score de severidade composta
  4. Formatação de outputs para múltiplas audiências
"""
from __future__ import annotations
import numpy as np
from typing import List, Optional, Dict, Any
import time

from core.data_structures import (
    MetricSignal, SpectralProfile, ClassificationResult,
    SignatureMatch, ChangePoint, PropagationFingerprint
)
from core.constants import (BAND_DESCRIPTIONS, BAND_NAMES, CHANNEL_IDX, CHANNEL_NAMES, EPSILON,
    COGNITIVE_BURST_THRESHOLD, GOD_CLASS_BURST_THRESHOLD,
    GOD_CLASS_HURST_MIN, GOD_CLASS_HURST_LATE_MIN, GOD_CLASS_PCI_MIN,
    GOD_CLASS_DI_STD_MIN, GOD_CLASS_CC_STD_MIN, BURST_WINDOW_MAX,
    BURST_NEUTRAL, N_STABLE_LOW, N_STABLE_MODERATE, MIN_SNAPSHOTS_SPECTRAL,
    GRADE_CONFIRMED_MIN_CONF, GRADE_LIKELY_MIN_CONF, GRADE_UNCERTAIN_MAX_CONF,
    HURST_MIN_LAG, HURST_N_POINTS)
from receptor.error_signatures import ErrorSignatureLibrary
from receptor.propagation_analyzer import PropagationAnalyzer
from receptor.change_point_detector import ChangePointDetector
from scipy.signal import hilbert


import warnings
warnings.filterwarnings("ignore", category=RuntimeWarning, module="scipy")

class FrequencyClassifier:
    """
    Receptor final: produz ClassificationResult a partir de SpectralProfiles.

    Parâmetros
    ----------
    library      : ErrorSignatureLibrary com as assinaturas pré-definidas
    cp_detector  : ChangePointDetector para localizar onset do erro
    min_confidence : confidence mínima para classificar (vs UNKNOWN_PATTERN)
    """

    def __init__(
        self,
        library: Optional[ErrorSignatureLibrary] = None,
        cp_detector: Optional[ChangePointDetector] = None,
        min_confidence: float = 0.28,
    ):
        self.library    = library or ErrorSignatureLibrary()
        self.cp_detector = cp_detector or ChangePointDetector(
            model="rbf", penalty=1.0, min_size=3
        )
        self.min_confidence       = min_confidence
        self.propagation_analyzer = PropagationAnalyzer()

    def classify(
        self,
        profiles: List[SpectralProfile],
        signal: MetricSignal,
    ) -> ClassificationResult:
        """
        Classifica o sinal e retorna um ClassificationResult completo.

        Passos:
          1. Matching de assinaturas (rule-based + embedding)
          2. Detecção de change point nos canais primários da melhor match
          3. Severidade composta
          4. Formatação de todos os outputs
        """
        # ── 1. Matching ──────────────────────────────────────────────────
        matches = self.library.match(profiles, min_confidence=self.min_confidence, signal=signal)

        if not matches:
            return self._unknown_result(signal, profiles)

        primary = matches[0]

        # ── 2. Change Point Detection ────────────────────────────────────
        cp = self.cp_detector.detect(signal, primary.matched_channels)

        # ── 2a. GAP-R04 + GAP-R01-partial: onset_confidence_context ────────
        # GAP-R04: onset nos primeiros 15% → possível artefato de janela curta
        # GAP-R01-partial: verificar se DI aumentou ANTES de CC (padrão GOD_CLASS)
        # usando os dados brutos do sinal (série temporal)
        if cp is None:
            onset_ctx = "NO_ONSET"
        else:
            onset_pct = cp.commit_idx / max(1, signal.n_original)
            onset_ctx = "RELIABLE" if onset_pct > 0.15 else "EARLY_WINDOW"

        # GAP-R01-partial: DI-first onset detection
        # Se DI começa a crescer antes de CC, confirma GOD_CLASS sobre TECH_DEBT
        # Detectável mesmo com shallow history quando DI varia
        try:
            DI_raw = signal.data_raw[CHANNEL_IDX['DI']]  # canal DI (idx 5)
            CC_raw_r = signal.data_raw[CHANNEL_IDX['CC']]  # canal CC (idx 1)
            n_half = max(5, len(DI_raw) // 3)
            # DI cresceu mais na 1ª metade do que CC? → GOD_CLASS onset pattern
            di_first_half  = float(DI_raw[n_half] - DI_raw[0])
            cc_first_half  = float(CC_raw_r[n_half] - CC_raw_r[0])
            di_leads_cc = (di_first_half > 0.05 and di_first_half > cc_first_half * 0.3)
        except Exception:
            di_leads_cc = False

        # ── 2b. Propagation Fingerprint — 4ª dimensão de scoring ──────────
        fp = self.propagation_analyzer.compute(signal, primary.matched_channels)

        # Discriminador GOD_CLASS vs COGNITIVE_EXPLOSION via onset spread
        # (o problema mais difícil na análise espectral sozinha)
        if primary.error_type in ("GOD_CLASS_FORMATION",
                                   "COGNITIVE_COMPLEXITY_EXPLOSION"):
            disc = self.propagation_analyzer.discriminate_god_vs_cognitive(signal)
            if disc != "AMBIGUOUS" and disc != primary.error_type:
                for i, hyp in enumerate(matches[1:], 1):
                    if hyp.error_type == disc:
                        matches[0], matches[i] = matches[i], matches[0]
                        primary = matches[0]
                        break

        # ── 2c. Hurst + PCI + Self-Cure ──────────────────────────────────────
        # Hurst sobre o canal H (índice 0) — raw data preservado em data_raw
        hurst_H = self._compute_hurst(signal.data_raw[CHANNEL_IDX['H']])

        # Late-window Hurst: computed over second half of signal
        # More sensitive to persistent degradation when onset is early in long windows
        # (early onset + long tail → full-window Hurst underestimates persistence)
        n_half = max(10, len(signal.data_raw[CHANNEL_IDX['H']]) // 2)
        hurst_H_late = self._compute_hurst(signal.data_raw[CHANNEL_IDX['H']][-n_half:])

        # PCI entre CC (índice 1) e H (índice 0)
        pci_CC_H = self._compute_pci(signal.data_raw[CHANNEL_IDX['CC']], signal.data_raw[CHANNEL_IDX['H']])

        # Self-cure probability derivada de Hurst + reversibilidade do onset
        self_cure, onset_rev = self._compute_self_cure(hurst_H, signal)

        # ── 2d. Physical Identity Override via Hurst + PCI ─────────────────
        #
        # Com 65–100 commits, TODA degradação concentra energia em ULF →
        # TECH_DEBT ganha por ser a assinatura ULF mais genérica.
        # A solução é usar as identidades físicas de cada tipo como override definitivo:
        #
        # As identidades são mutuamente exclusivas e derivadas da mineração:
        #   AI_CODE_BOMB:  PCI < 0.30  → H não é CC-driven (dead/dups dominam H)
        #   COGNITIVE:     Hurst < 0.72 AND PCI > 0.85  → spike transitório CC→H
        #   GOD_CLASS:     Hurst > 0.85 AND PCI > 0.85 AND Burst < 0.30
        #   DEAD_CODE:     Hurst ≈ 1.0 AND raw_std(dead) > raw_std(CC)
        #   LOOP_RISK:     n_channels_activated=1 (ISOLATED) AND ILR raw_std ≫ others
        #   DEP_CYCLE:     Hurst < 0.80 AND PCI < 0.45 (DSM_c/DI desacoplados de CC)
        #   TECH_DEBT:     Hurst > 0.95 AND PCI > 0.85 AND Burst < 0.30 (genuíno)
        #
        # Verificar raw_std dos canais para distinguir o que REALMENTE se moveu

        # Extrair raw_std por canal para identidades físicas
        ch_profiles_snap = {p.channel: p for p in profiles if "cross:" not in p.channel}
        raw_std = {ch: ch_profiles_snap[ch].raw_std for ch in ch_profiles_snap}

        # Burst Index — concentration of change (CC channel, adaptive window)
        # GAP-S05: window capped at 15 to handle long histories (N>300)
        # and shallow repos where small N makes N/4 too small to be meaningful
        H_raw  = signal.data_raw[CHANNEL_IDX['H']]
        CC_raw = signal.data_raw[CHANNEL_IDX['CC']]
        n_H = len(H_raw)
        # Adaptive window: min(N//4, 15) — captures 6-10 commit spikes at any N
        win = min(max(4, n_H // 4), BURST_WINDOW_MAX)
        diffs_CC = np.abs(np.diff(CC_raw))
        if len(diffs_CC) >= win:
            burst_H = float(max(
                diffs_CC[i:i+win].sum() for i in range(len(diffs_CC)-win+1)
            ) / (diffs_CC.sum() + 1e-10))
        else:
            burst_H = 0.0

        # GAP-S05: in shallow repos (N<30), burst is unreliable — all channels stable.
        # When ≥3 channels are stable AND burst≈0, use neutral burst (0.40)
        # to avoid penalizing COGNITIVE which should have high burst.
        n_stable_now = len(signal.stable_channels) if signal.stable_channels else 0
        if n_stable_now >= 3 and burst_H < 0.10:
            burst_H = BURST_NEUTRAL  # neutral: does not favour or penalise any type

        # ── HF/LF ratio from H channel SpectralProfile ───────────────────
        # Extract from profiles already computed by SpectralAnalyzer
        ch_H_profiles = [p for p in profiles if p.channel == "H" and "cross:" not in p.channel]
        if ch_H_profiles:
            be = ch_H_profiles[0].band_energies_relative
            hf_energy = be.get("HF", 0.0) + be.get("UHF", 0.0)
            lf_energy = be.get("ULF", 0.0) + be.get("LF", 0.0) + 1e-10
            hflf_ratio_H = float(hf_energy / lf_energy)
        else:
            hflf_ratio_H = 0.0

        # Verificar qual canal tem maior raw_std (canal dominante real)
        primary_movers = sorted(raw_std.items(), key=lambda x: -x[1])
        top_mover = primary_movers[0][0] if primary_movers else "H"

        # ── Identidades físicas (overrides definitivos) ────────────────────
        primary, matches = self._apply_identity_overrides(
            primary, matches, signal,
            hurst_H, hurst_H_late, pci_CC_H, burst_H, raw_std, di_leads_cc
        )

                # ── 3. Severidade composta ────────────────────────────────────────
        severity, severity_score = self._compute_severity(primary, signal, profiles)

        # ── 4. Banda dominante do conjunto de perfis ──────────────────────
        dominant_band = self._dominant_band_from_profiles(profiles)
        band_desc = BAND_DESCRIPTIONS.get(dominant_band, "")

        # ── 5. Evidência espectral consolidada ───────────────────────────
        spectral_evidence = self._consolidate_evidence(primary, profiles)

        # ── 6. Transforms UCO sugeridos ──────────────────────────────────
        transforms, delta_h = self._suggest_transforms(primary.error_type, signal)

        # ── 7. Formatação de outputs ─────────────────────────────────────
        plain_english = self._to_plain_english(
            primary, signal, cp, dominant_band, severity
        )
        tech_summary = self._to_technical(primary, signal, dominant_band, cp)
        apex_prompt  = self._format_apex_prompt(primary, signal, cp)

        # ── GAP-S03/S04/S06: qualidade do sinal e grau de classificação ─────
        sig_quality, grade, n_stable, is_spectrally_valid = self._compute_signal_quality(signal, primary)

        return ClassificationResult(
            module_id=signal.module_id,
            timestamp=float(signal.timestamps[-1]),
            is_spectrally_valid=is_spectrally_valid,   # GAP-V1
            primary_error=primary.error_type,
            primary_confidence=primary.confidence,
            severity=severity,
            severity_score=severity_score,
            hypotheses=matches[:3],
            change_point=cp,
            dominant_band=dominant_band,
            band_description=band_desc,
            spectral_evidence=spectral_evidence,
            plain_english=plain_english,
            technical_summary=tech_summary,
            apex_prompt=apex_prompt,
            suggested_transforms=transforms,
            potential_delta_h=delta_h,
            n_commits_analyzed=signal.n_original,
            analysis_timestamp=time.time(),
            hflf_ratio_H=round(hflf_ratio_H, 4),
            burst_index_H=round(burst_H, 4),
            hurst_H=round(hurst_H, 4),
            phase_coupling_CC_H=round(pci_CC_H, 4),
            onset_reversibility=round(onset_rev, 4),
            onset_confidence_context=onset_ctx,
            self_cure_probability=round(self_cure, 2),
            n_stable_channels=n_stable,
            spectral_signal_quality=sig_quality,
            classification_grade=grade,
        )

    def _apply_identity_overrides(
        self,
        primary: "SignatureMatch",
        matches: list,
        signal: "MetricSignal",
        hurst_H: float,
        hurst_H_late: float,
        pci_CC_H: float,
        burst_H: float,
        raw_std: dict,
        di_leads_cc: bool,
    ):
        """
        OPT-04: Identity override rules extracted from classify() to reduce CC.
        Applies 6 physics-based rules that can promote a hypothesis over the
        top signature match.
        Returns (primary, matches) — potentially reordered.
        """
        # GAP-A1: get adaptive params for this N-band
        try:
            _band      = get_n_band(signal.n_original)
            _params    = ADAPTIVE_PARAMS[_band]
            _burst_thr = _params['burst_thr']
        except Exception:
            _burst_thr = 0.70

        # ── Identidades físicas (overrides definitivos) ────────────────────
        # Cada regra usa combinação de Hurst, PCI, burst_H e raw_std dos canais
        override_type = None

        # GAP-N2: DI growth rate (secular trend — complements di_leads_cc onset)
        DI_raw_seq   = signal.data_raw[CHANNEL_IDX['DI']]
        _n_di        = len(DI_raw_seq)
        if _n_di >= 10:
            _di_growth = float(DI_raw_seq[-1] - DI_raw_seq[0]) / _n_di
            di_is_growing = _di_growth >  0.005   # GOD_CLASS em formação (>0.5%/commit)
            di_is_stable  = abs(_di_growth) < 0.001  # TECH_DEBT ou GOD_CLASS madura
        else:
            di_is_growing = di_is_stable = False

        # Extrair raw_std dos canais principais para todas as regras abaixo
        dead_std = raw_std.get("dead", 1.0)
        dups_std = raw_std.get("dups", 1.0)
        ilr_std  = raw_std.get("ILR",  1.0)
        cc_std   = raw_std.get("CC",   1.0)

        # GAP-V4: CC declining guard — CC que cai contradiz GOD_CLASS/COGNITIVE
        # Uses median of first/last third to avoid z-score spike artifacts (AI_BOMB false block)
        CC_raw_seq = signal.data_raw[CHANNEL_IDX['CC']]
        _n3       = max(5, len(CC_raw_seq) // 3)
        _cc_early = float(np.median(CC_raw_seq[:_n3]))
        _cc_late  = float(np.median(CC_raw_seq[-_n3:]))
        # Decline must be substantial: >1.0 in z-score space (avoids AI_BOMB micro-fluctuation)
        cc_is_declining = (_cc_early - _cc_late) > 1.0

        # 0. DEAD_CODE_DRIFT: Hurst=1.0 + PCI baixo + dead domina MUITO + ILR inativo
        #    Must check before AI_CODE_BOMB (which also has pci < 0.30)
        #    BUG-R3: dead_std > 2.0 guard — PCI baixo sem dead code real ≠ DEAD_CODE
        if (hurst_H > 0.92
                and pci_CC_H < 0.25
                and dead_std > 4.0             # dead code MUITO dominante
                and dead_std > 2.0             # BUG-R3: canal dead DEVE ter variado no raw
                and (ilr_std < 0.15 or ilr_std >= 0.99)  # ILR inativo: low std OR constant sentinel (1.0)
                and dups_std < dead_std * 0.5):  # dups < metade do dead
            override_type = "DEAD_CODE_DRIFT"

        # 1. AI_CODE_BOMB: PCI muito baixo → H não é CC-driven
        #    dead OU dups tem raw_std ALTO enquanto CC tem raw_std moderado

        elif (pci_CC_H < 0.30
                and (dead_std > 2.0 or dups_std > 2.0)
                and burst_H > 0.20        # 3-channel burst (measured ≈0.40)
                and 0.05 < ilr_std < 0.99):  # ILR moved AND not constant sentinel (1.0 = inactive)
            override_type = "AI_CODE_BOMB"

        # 2. COGNITIVE_EXPLOSION: dois caminhos de detecção
        #    Rota A: burst alto (threshold adaptativo por banda N) + PCI alto
        #    Rota B: H<0.75 + PCI>0.85 para históricos longos (N grande dilui burst)
        #    Nota: cc_std = raw_std['CC'] (pré-z-score); COGNITIVE≈5.9, TECH_DEBT≈9.0
        # 2. COGNITIVE_EXPLOSION: GAP-N4 — zona ambígua 0.70-0.85 requires PCI>0.92
        #    COGNITIVE_BURST_STRONG (0.85): certeza forte independe de PCI
        elif ((burst_H > (_burst_thr if _burst_thr is not None else 0.70)
               and pci_CC_H > 0.85
               and cc_std > 4.0
               and (hurst_H < 0.85 or burst_H > 0.90))
              or (hurst_H < 0.75
                  and pci_CC_H > 0.85
                  and cc_std > 3.0
                  and burst_H > 0.25
                  and not cc_is_declining)):
            override_type = "COGNITIVE_COMPLEXITY_EXPLOSION"

        # 2b. COGNITIVE via cc_hotspot_ratio (GAP-N1): função monstro em arquivo grande
        #     burst pode ser baixo se a complexidade se espalhrou por muitos commits
        elif (signal.cc_diff_cv > 0.60                 # GAP-D4: CC changes volatile
              and signal.n_functions_mean > 10.0        # GAP-D3: arquivo com muitas funções
              and pci_CC_H > 0.70
              and not cc_is_declining
              and primary.error_type in ("GOD_CLASS_FORMATION","TECH_DEBT_ACCUMULATION")):
            override_type = "COGNITIVE_COMPLEXITY_EXPLOSION"

        # 3. DEAD_CODE_DRIFT: Hurst≈1.0 + PCI baixo + dead domina
        elif (hurst_H > 0.95
              and pci_CC_H < 0.30
              and dead_std > cc_std * 1.5
              and top_mover == "dead"):
            override_type = "DEAD_CODE_DRIFT"

        # 4. LOOP_RISK: ILR é o canal que mudou (mesmo que raw_std seja pequeno
        #    em absoluto, ILR é o ÚNICO canal ativo — outros estão perto de 1.0 = inativo)
        #    Condição: ILR trend > 0 E dead/dups não se moveram (raw_std ≈ 1.0 = constante)
        elif (ilr_std < cc_std             # ILR pequeno, mas…
              and ilr_std > 0.05           # …existe sinal real (não constante)
              and (signal.data_raw[CHANNEL_IDX['ILR']].max() - signal.data_raw[CHANNEL_IDX['ILR']].min()) > 0.1  # ILR range > 0.1
              and dead_std < 2.0           # dead não domina
              and dups_std < 2.0):         # dups não domina
            override_type = "LOOP_RISK_INTRODUCTION"

        # 5. DEPENDENCY_CYCLE: hurst moderado-alto + PCI baixo + DSM_c moveu
        #    Hurst pode ser alto (crônico) porque ciclos se acumulam gradualmente
        #    Discriminador principal: PCI muito baixo (<0.45) + DSM_c ativo
        elif (hurst_H < 0.95
              and pci_CC_H < 0.45
              and raw_std.get("DSM_c", 0) > 0.05
              and raw_std.get("DI",    0) > 0.1
              and raw_std.get("dead",  0) < 2.0    # dead code não é o driver
              and raw_std.get("dups",  0) < 2.0):  # dups não são o driver
            override_type = "DEPENDENCY_CYCLE_INTRODUCTION"

        # 5a. DEPENDENCY_CYCLE (runtime): DSM_c elevado via proxies + H crônico + burst baixo
        #     GAP-N3: cobre ciclos via LocalProxy/TYPE_CHECKING invisíveis ao AST de imports
        elif (raw_std.get("DSM_c", 0) > 0.25          # DSM_c moveu (incl. runtime score)
              and hurst_H > 0.75                        # padrão crônico
              and burst_H < 0.55                        # não é explosão pontual
              and signal.n_classes_growth > 0.01        # GAP-D3: novas classes sendo criadas
              and primary.error_type in ("GOD_CLASS_FORMATION","TECH_DEBT_ACCUMULATION")):
            override_type = "DEPENDENCY_CYCLE_INTRODUCTION"

        # 5b. TECH_DEBT: DI estável + max_methods baixo + CC cresce = acumulação no mesmo domínio
        #     GAP-N2: discrimina TECH_DEBT de GOD_CLASS quando ambos têm H alto + PCI alto
        elif (di_is_stable
              and signal.max_methods_mean < 15.0    # GAP-D2: poucos métodos/classe
              and hurst_H > 0.85
              and burst_H < 0.60
              and not cc_is_declining
              and primary.error_type == "GOD_CLASS_FORMATION"):
            override_type = "TECH_DEBT_ACCUMULATION"

        # 6. GOD_CLASS: PCI alto + burst < COGNITIVE threshold + DI e CC se moveram
        #    GAP-N2: di_is_growing reforça GOD_CLASS; di_is_stable + max_methods baixo = TECH_DEBT
        #    GAP-N5: DI alto e estável = GOD_CLASS matura consolidada
        elif ((hurst_H > 0.80 or hurst_H_late > 0.85)
              and pci_CC_H > GOD_CLASS_PCI_MIN
              and burst_H < GOD_CLASS_BURST_THRESHOLD
              and primary.error_type == "TECH_DEBT_ACCUMULATION"):
            di_std     = raw_std.get("DI", 0)
            di_current = float(signal.data_raw[CHANNEL_IDX['DI']].mean())
            # GAP-N2: se DI cresce secularmente → GOD_CLASS
            if di_is_growing and cc_std > 1.0:
                override_type = "GOD_CLASS_FORMATION"
            # GAP-N5: DI alto e estável = GOD_CLASS já consolidada
            elif di_is_stable and di_current > 0.70 and cc_std > 1.0:
                override_type = "GOD_CLASS_FORMATION"
            # Original rules
            elif di_std > 0.5 and cc_std > 1.0:
                override_type = "GOD_CLASS_FORMATION"
            elif di_leads_cc and cc_std > 1.0:
                override_type = "GOD_CLASS_FORMATION"

        # Aplicar override se definido e diferente do atual
        # GAP-V4: CC declinante bloqueia overrides para GOD_CLASS e COGNITIVE
        if cc_is_declining and override_type in ("GOD_CLASS_FORMATION",
                                                   "COGNITIVE_COMPLEXITY_EXPLOSION"):
            override_type = None  # CC caindo contradiz acumulação/explosão

        # BUG-R1: REFACTORING_IN_PROGRESS falso positivo via H=0.5 degenerado
        # H=0.5 (série constante após GAP-V2) coincide com REFACTORING target=0.55
        _n_stable_check = len(signal.stable_channels) if signal.stable_channels else 0
        if (primary.error_type == "REFACTORING_IN_PROGRESS"
                and _n_stable_check >= 3
                and abs(hurst_H - 0.5) < 0.08):    # H degenerado ≈ 0.5
            # Reverter para segunda melhor hipótese
            if len(matches) > 1:
                primary = matches[1]
                override_type = None  # deixar segunda hipótese prevalecer

        if override_type and override_type != primary.error_type:
            for i, hyp in enumerate(matches[1:], 1):
                if hyp.error_type == override_type:
                    matches[0], matches[i] = matches[i], matches[0]
                    primary = matches[0]
                    break
        return primary, matches

    def _compute_signal_quality(
        self,
        signal: "MetricSignal",
        primary: "SignatureMatch",
    ):
        """
        OPT-04: Computa spectral_signal_quality, classification_grade, n_stable.
        Extraído de classify() para reduzir CC.
        Returns: (sig_quality: str, grade: str, n_stable: int)
        """
        n_stable = len(signal.stable_channels) if signal.stable_channels else 0
        n_snaps  = signal.n_original

        if n_snaps < MIN_SNAPSHOTS_SPECTRAL:
            sig_quality = "SHALLOW_HISTORY"
        elif n_stable >= N_STABLE_LOW:
            sig_quality = "LOW_SPECTRAL_SIGNAL"
        elif n_stable == N_STABLE_MODERATE:
            sig_quality = "MODERATE"
        else:
            sig_quality = "GOOD"

        if n_snaps < MIN_SNAPSHOTS_SPECTRAL:
            grade = "INSUFFICIENT"
        elif primary.confidence < GRADE_UNCERTAIN_MAX_CONF and n_stable >= N_STABLE_LOW:
            grade = "UNCERTAIN"
        elif primary.confidence < GRADE_LIKELY_MIN_CONF or n_stable >= N_STABLE_MODERATE:
            grade = "LIKELY"
        elif primary.confidence >= GRADE_CONFIRMED_MIN_CONF and n_stable <= 1:
            grade = "CONFIRMED"
        else:
            grade = "LIKELY"

        is_valid = (n_snaps >= MIN_SNAPSHOTS_SPECTRAL)  # GAP-V1
        return sig_quality, grade, n_stable, is_valid

    # ─── Hurst, PCI, Self-Cure ──────────────────────────────────────────────────

    def _compute_hurst(self, series: np.ndarray, max_lags: int = None) -> float:
        """
        Hurst Exponent via R/S Analysis (Hurst 1951).

        OPT-03: max_lags escalado com N em log-space para estimativa robusta.
        GAP-V2: guard para série constante (std≈0 → H=0.5, evita REFACTORING falso).
        GAP-V3: mínimo 4 pontos R/S válidos (era 3, instável com N pequeno).
        """
        n = len(series)
        if n < HURST_MIN_LAG * 2:
            return 0.5

        # GAP-V2: série degenerada (constante → std≈0 → R/S inválido)
        if series.std() < EPSILON:
            return 0.5  # não calcular R/S em série sem variância

        # Lags em log-space: captura estrutura de curto E longo alcance
        max_lag = max_lags if max_lags else min(n // 2, max(HURST_MIN_LAG * 5, n // 4))
        lag_arr = np.unique(
            np.logspace(np.log10(HURST_MIN_LAG),
                        np.log10(max(max_lag, HURST_MIN_LAG + 1)),
                        HURST_N_POINTS).astype(int)
        )

        rs_vals, lag_vals = [], []
        for lag in lag_arr:
            if lag >= n:
                continue
            sub  = series[:lag]
            dev  = np.cumsum(sub - sub.mean())
            R    = dev.max() - dev.min()
            S    = sub.std() + EPSILON
            if R > 0:
                rs_vals.append(np.log(R / S))
                lag_vals.append(np.log(lag))

        if len(rs_vals) < 4:   # GAP-V3: era 3, elevado para estabilidade numérica
            return 0.5
        return float(np.clip(np.polyfit(lag_vals, rs_vals, 1)[0], 0.0, 1.0))

    def _compute_pci(self, x: np.ndarray, y: np.ndarray) -> float:
        """
        Phase Coupling Index via Hilbert transform.
        PCI = |mean(e^{i·Δφ})| ∈ [0, 1]

        PCI > 0.90 → sinais em sincronia de fase: CC e H se movem juntos
          (GOD_CLASS, COGNITIVE_EXPLOSION)
        PCI < 0.25 → fases desacopladas: H dominado por outros canais
          (AI_CODE_BOMB — dead/dups dominam H; CC independente)

        Hilbert puro via numpy — sem scipy.signal.hilbert necessário aqui;
        usa FFT da numpy para evitar dependência opcional.
        """
        n = min(len(x), len(y))
        if n < 8:
            return 0.0
        try:
            x_, y_ = x[:n] - x[:n].mean(), y[:n] - y[:n].mean()
            phi_x  = np.angle(hilbert(x_))
            phi_y  = np.angle(hilbert(y_))
            pci    = float(np.abs(np.mean(np.exp(1j * (phi_x - phi_y)))))
            return float(np.clip(pci, 0.0, 1.0))
        except Exception:
            return 0.0

    def _compute_self_cure(self, hurst_H: float, signal: MetricSignal) -> float:
        """
        Probabilidade de auto-resolução sem intervenção humana [0–100%].

        Formula:
          base = max(0, 1 - hurst_H) × 100   [0–100]
          onset_factor: se H reverteu após o onset → aumenta probabilidade

        Exemplos calibrados:
          DEAD_CODE    hurst=1.00 → base=0%  → self_cure≈0%
          TECH_DEBT    hurst=0.99 → base=1%  → self_cure≈1%
          GOD_CLASS    hurst=0.92 → base=8%  → self_cure≈2% (irreversível na prática)
          AI_CODE_BOMB hurst=0.79 → base=21% → self_cure≈15% (limpeza parcial possível)
          COGNITIVE    hurst=0.60 → base=40% → self_cure≈25% (pode estabilizar)
          REFACTORING  hurst=0.50 → base=50% → self_cure≈50%
        """
        base = max(0.0, (1.0 - hurst_H) * 100.0)

        # Onset reversibility: H caiu após o pico? → indica que pode se resolver
        H_arr = signal.data_raw[CHANNEL_IDX['H']]
        n     = len(H_arr)
        reversibility = 0.0
        if n >= 12:
            onset_idx = int(n * 0.6)
            post      = H_arr[onset_idx:]
            if len(post) >= 3:
                peak  = float(post.max())
                final = float(post[-3:].mean())
                delta = peak - float(H_arr[:onset_idx].mean()) + 1e-10
                reversibility = float(np.clip((peak - final) / delta, 0, 1))
                base = base * (0.5 + 0.5 * reversibility)

        return float(np.clip(base, 0.0, 100.0)), reversibility

    # ─── Severidade ──────────────────────────────────────────────────────────

    def _compute_severity(
        self,
        match: SignatureMatch,
        signal: MetricSignal,
        profiles: Optional[List[SpectralProfile]] = None,
    ) -> tuple:
        """
        Severidade final via DUPLA CONFIRMAÇÃO — regra transposta do ASTM D6760.

        No CSL, uma anomalia só é CONFIRMADA quando dois atributos independentes
        concordam: FAT delay > 10% AND Energia < -6dB.

        Aqui:
          Atributo 1 — magnitude (z-score proxy): std dos canais primários
          Atributo 2 — fw_shift: deslocamento espectral (CSL: queda de f_w)
                       OU A_n: energia normalizada (CSL: queda de amplitude)

        Regra:
          CRITICAL confirma-se somente se AMBOS os atributos alertam.
          Se apenas um alerta → downgrade para WARNING (possível anomalia).
          Se nenhum alerta    → sinal saudável ou falso positivo.

        Isso reduz ~50% dos falsos positivos sem perder sensibilidade.
        """
        indices = [CHANNEL_NAMES.index(ch) for ch in match.matched_channels
                   if ch in CHANNEL_NAMES]
        magnitude = float(np.std(signal.data_raw[indices])) if indices else 1.0

        # ── Atributo 2: fw_shift e A_n dos perfis espectrais ─────────────
        # Extrair f_w dos canais primários se perfis disponíveis
        fw_shift_max = 0.0
        An_min       = 1.0
        if profiles:
            ch_profiles = {p.channel: p for p in profiles if "cross:" not in p.channel}
            for ch in match.matched_channels:
                if ch in ch_profiles:
                    p = ch_profiles[ch]
                    fw_shift_max = max(fw_shift_max, p.fw_shift)
                    An_min       = min(An_min, p.norm_spectrum_area)

        # ── Confirmação individual de cada atributo ───────────────────────
        # Atributo 1: z-score proxy (magnitude)
        z_confirms = magnitude > 2.0          # equivalente: FAT delay > 10%

        # Atributo 2: espectral (fw_shift OU A_n)
        # fw_shift > 0.20 → espectro perdeu HF → degradação estrutural
        # A_n < 0.70      → energia atual < 70% do baseline → sinal enfraquecido
        spectral_confirms = (fw_shift_max > 0.20) or (An_min < 0.70)

        base = match.severity_base

        # ── Amplificação (upward) ─────────────────────────────────────────
        if base == "INFO"    and magnitude > 2.0 and spectral_confirms: base = "WARNING"
        if base == "WARNING" and magnitude > 3.5 and spectral_confirms: base = "CRITICAL"

        # ── Regra de dupla confirmação: downgrade se apenas 1 atributo ────
        if base == "CRITICAL":
            if not (z_confirms and spectral_confirms):
                base = "WARNING"   # um atributo → possível anomalia, não confirmada

        if base == "WARNING":
            if not z_confirms and not spectral_confirms:
                base = "INFO"      # nenhum atributo → falso positivo
            elif magnitude < 0.5:
                base = "INFO"

        score = float(np.clip(match.confidence * min(magnitude, 4.0) / 4.0, 0.0, 1.0))
        return base, score

    # ─── Banda dominante ──────────────────────────────────────────────────────

    def _dominant_band_from_profiles(
        self, profiles: List[SpectralProfile]
    ) -> str:
        """Banda com maior frequência de ser dominante entre os canais individuais."""
        counts: Dict[str, int] = {b: 0 for b in BAND_NAMES}
        for p in profiles:
            if "cross:" not in p.channel:
                counts[p.dominant_band] = counts.get(p.dominant_band, 0) + 1
        return max(counts, key=counts.get) if any(counts.values()) else "MF"

    # ─── Evidência espectral ──────────────────────────────────────────────────

    def _consolidate_evidence(
        self,
        match: SignatureMatch,
        profiles: List[SpectralProfile],
    ) -> Dict[str, Any]:
        ch_profiles = {p.channel: p for p in profiles if "cross:" not in p.channel}
        summary: Dict[str, Any] = {
            "matched_band": match.matched_band,
            "temporal_pattern": match.temporal_pattern,
            "primary_channels": match.matched_channels,
        }
        summary.update(match.evidence)
        # Top-3 canais mais anômalos (maior desvio da entropia "estável")
        entropy_devs = {}
        for ch, p in ch_profiles.items():
            entropy_devs[ch] = abs(p.spectral_entropy - 0.85)
        top3 = sorted(entropy_devs.items(), key=lambda x: x[1], reverse=True)[:3]
        summary["most_anomalous_channels"] = [ch for ch, _ in top3]
        # T14d: add fw_shift and hflf_ratio per channel for primary channels
        for ch in (match.matched_channels or []):
            p = ch_profiles.get(ch)
            if p is None:
                continue
            summary[f"{ch}_fw_shift"] = float(p.fw_shift)
            be = p.band_energies_relative
            hf = be.get("HF", 0.0) + be.get("UHF", 0.0)
            lf = be.get("ULF", 0.0) + be.get("LF", 0.0) + 1e-10
            summary[f"{ch}_hflf_ratio"] = float(hf / lf)
        return summary

    # ─── Sugestões UCO ────────────────────────────────────────────────────────

    def _suggest_transforms(
        self, error_type: str, signal: MetricSignal
    ) -> tuple:
        """
        Mapa de transforms UCO recomendados por tipo de erro.
        O delta_h é uma estimativa conservadora.
        """
        transform_map = {
            "AI_CODE_BOMB":                 (["T02", "T01", "T09"], -6.5),
            "GOD_CLASS_FORMATION":          (["T07", "T05"], -3.0),
            "DEPENDENCY_CYCLE_INTRODUCTION":(["T07"], -2.0),
            "TECH_DEBT_ACCUMULATION":       (["T06", "T07", "T01", "T05"], -5.0),
            "LOOP_RISK_INTRODUCTION":       (["T02", "T07"], -4.0),
            "REFACTORING_IN_PROGRESS":      ([], 0.0),
            "DEAD_CODE_DRIFT":              (["T02", "T09"], -3.5),
            "COGNITIVE_COMPLEXITY_EXPLOSION":(["T07", "T01"], -4.5),
            "UNKNOWN_PATTERN":              ([], 0.0),
        }
        transforms, delta_h = transform_map.get(error_type, ([], 0.0))
        return transforms, delta_h

    # ─── Formatação de outputs ────────────────────────────────────────────────

    def _to_plain_english(
        self,
        match: SignatureMatch,
        signal: MetricSignal,
        cp: Optional[ChangePoint],
        band: str,
        severity: str,
    ) -> str:
        onset_str = ""
        if cp and cp.commit_hash:
            onset_str = (f" Este problema começou por volta do commit "
                         f"{cp.commit_hash[:8]} "
                         f"(confiança: {cp.confidence:.0%}).")

        band_desc = BAND_DESCRIPTIONS.get(band, band)
        return (
            f"[{severity}] O módulo '{signal.module_id}' apresenta "
            f"{match.description.lower()}.{onset_str} "
            f"O padrão de frequência identificado é: {band_desc}. "
            f"Ação recomendada: {match.recommended_action} "
            f"(confiança na classificação: {match.confidence:.0%})"
        )

    def _to_technical(
        self,
        match: SignatureMatch,
        signal: MetricSignal,
        band: str,
        cp: Optional[ChangePoint],
    ) -> str:
        cp_str = f"onset_commit_idx={cp.commit_idx}" if cp else "onset=N/A"
        return (
            f"ERROR_TYPE={match.error_type} | "
            f"CONFIDENCE={match.confidence:.4f} | "
            f"BAND={match.matched_band} | "
            f"CHANNELS={match.matched_channels} | "
            f"PATTERN={match.temporal_pattern} | "
            f"CORR={match.inter_channel_correlation if hasattr(match,'inter_channel_correlation') else 'N/A'} | "
            f"{cp_str} | "
            f"N_COMMITS={signal.n_original}"
        )

    def _format_apex_prompt(
        self,
        match: SignatureMatch,
        signal: MetricSignal,
        cp: Optional[ChangePoint],
    ) -> str:
        cp_hash = cp.commit_hash[:8] if cp and cp.commit_hash else "unknown"
        cp_ago  = (signal.n_original - cp.commit_idx) if cp else 0
        delta_h = abs(signal.data_raw[CHANNEL_IDX['H']].max() - signal.data_raw[CHANNEL_IDX['H']].min())
        return match.apex_prompt_template.format(
            module_id=signal.module_id,
            delta_h=delta_h,
            cp_hash=cp_hash,
            cp_ago=cp_ago,
            n_commits=signal.n_original,
        )

    # ─── Resultado para padrão desconhecido ──────────────────────────────────

    def _unknown_result(
        self,
        signal: MetricSignal,
        profiles: List[SpectralProfile],
    ) -> ClassificationResult:
        """BUG-C04 FIX: computa Hurst/PCI/Burst mesmo para UNKNOWN_PATTERN."""
        dominant_band = self._dominant_band_from_profiles(profiles)

        # Compute physics — urgência é válida mesmo sem tipo identificado
        H_raw  = signal.data_raw[CHANNEL_IDX['H']]
        CC_raw = signal.data_raw[CHANNEL_IDX['CC']]
        hurst_H = self._compute_hurst(H_raw)
        try:
            pci_CC_H = self._compute_pci(CC_raw, H_raw)
        except Exception:
            pci_CC_H = 0.0
        n_H   = len(H_raw)
        win   = min(max(4, n_H // 4), BURST_WINDOW_MAX)
        diffs = np.abs(np.diff(CC_raw))
        burst_H = (float(max(diffs[i:i+win].sum()
                             for i in range(max(1, len(diffs)-win+1)))
                         / (diffs.sum() + EPSILON))
                   if len(diffs) >= win else 0.0)
        self_cure, onset_rev = self._compute_self_cure(hurst_H, signal)

        n_stable = len(signal.stable_channels) if signal.stable_channels else 0
        n_snaps  = signal.n_original
        if n_snaps < MIN_SNAPSHOTS_SPECTRAL:
            sig_quality = "SHALLOW_HISTORY";     grade = "INSUFFICIENT"
        elif n_stable >= N_STABLE_LOW:
            sig_quality = "LOW_SPECTRAL_SIGNAL"; grade = "UNCERTAIN"
        elif n_stable >= N_STABLE_MODERATE:
            sig_quality = "MODERATE";            grade = "UNCERTAIN"
        else:
            sig_quality = "GOOD";                grade = "UNCERTAIN"
        return ClassificationResult(
            module_id=signal.module_id,
            is_spectrally_valid=False,  # GAP-V1: UNKNOWN is always invalid
            timestamp=float(signal.timestamps[-1]),
            primary_error="UNKNOWN_PATTERN",
            primary_confidence=0.0,
            severity="INFO",
            severity_score=0.0,
            hypotheses=[],
            change_point=None,
            dominant_band=dominant_band,
            band_description=BAND_DESCRIPTIONS.get(dominant_band, ""),
            spectral_evidence={"note": "Padrão não mapeado na biblioteca de assinaturas"},
            plain_english=(
                f"[INFO] O módulo '{signal.module_id}' apresenta comportamento anômalo "
                f"não mapeado na biblioteca de assinaturas atual. "
                f"Pode ser um novo padrão a ser catalogado via DBSCAN discovery."
            ),
            technical_summary="NO_MATCH: padrão fora da biblioteca atual",
            apex_prompt=(
                f"[UCO-SENSOR INFO] UNKNOWN_PATTERN em {signal.module_id}. "
                f"Nenhuma assinatura conhecida com confidence >= {self.min_confidence}. "
                f"Executar DEEP_SCAN para catalogar novo padrão via DBSCAN."
            ),
            suggested_transforms=[],
            potential_delta_h=0.0,
            n_commits_analyzed=signal.n_original,
            analysis_timestamp=time.time(),
            hurst_H=round(hurst_H, 4),
            phase_coupling_CC_H=round(pci_CC_H, 4),
            burst_index_H=round(burst_H, 4),
            onset_reversibility=round(onset_rev, 4),
            self_cure_probability=round(self_cure, 2),
            n_stable_channels=n_stable,
            spectral_signal_quality=sig_quality,
            classification_grade=grade,
        )
