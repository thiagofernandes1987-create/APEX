"""
UCO-Sensor FrequencyEngine — Biblioteca de Assinaturas de Erro
================================================================
ErrorSignatureLibrary: 8 assinaturas espectrais pré-definidas + matching.

Cada ErrorSignature é a "impressão digital espectral" de uma classe de
problema de qualidade de software — análogo às frequências de ressonância
de defeitos mecânicos no SHM (Structural Health Monitoring).

A assinatura é definida por:
  1. Quais canais UCO são afetados (canais primários)
  2. Em qual banda de frequência o padrão se manifesta
  3. Qual o padrão temporal esperado (spike, monotone, step, oscillating)
  4. Qual a correlação esperada entre os canais afetados
  5. O vetor de embedding de 45 dimensões [9 canais × 5 bandas]

Matching em duas camadas:
  Camada 1 — Rule-based (sempre, ~0.5ms):
    Score = 0.60 × (energia relativa na banda correta)
          + 0.25 × (compatibilidade de padrão temporal)
          + 0.15 × (coerência cross-canal se disponível)

  Camada 2 — DTW (casos ambíguos, ~5ms):
    Compara o embedding espectral atual contra os templates de assinatura
    usando similaridade de cosseno. Refinamento quando camada 1 retorna
    múltiplos matches com confidence próximas.
"""
from __future__ import annotations
import numpy as np
from scipy.signal import hilbert as _hilbert
from dataclasses import dataclass, field
from typing import List, Dict, Optional

from core.data_structures import SpectralProfile, SignatureMatch
from core.constants import (
    CHANNEL_NAMES, CHANNEL_IDX,
    get_n_band, ADAPTIVE_PARAMS, N_STABLE_THRESHOLDS, FREQ_BANDS, BAND_NAMES, N_CHANNELS, N_BANDS, EMBEDDING_DIM
)


@dataclass
class ErrorSignature:
    """Template espectral de um tipo de erro de software."""
    error_type: str
    description: str
    severity_base: str              # "INFO" | "WARNING" | "CRITICAL"

    primary_channels: List[str]     # canais afetados (nomes)
    dominant_band: str              # banda onde o padrão é mais forte
    secondary_band: Optional[str]   # banda secundária (ou None)

    temporal_pattern: str           # "spike"|"monotone"|"step"|"oscillating"|"correlated_rise"
    inter_channel_correlation: str  # "positive"|"negative"|"independent"

    root_cause: str
    recommended_action: str
    apex_prompt_template: str

    # Embedding de 45 dims (preenchido por _build_embedding)
    embedding: np.ndarray = field(default_factory=lambda: np.zeros(EMBEDDING_DIM))

    def _build_embedding(self) -> None:
        """
        Constrói o vetor de embedding de 45 dimensões.

        embedding[canal_idx * N_BANDS + banda_idx] = intensidade esperada
          1.0 = canal primário na banda dominante
          0.5 = canal primário na banda secundária
          0.0 = ausente
        """
        emb = np.zeros(EMBEDDING_DIM, dtype=np.float64)
        band_list = BAND_NAMES

        dom_idx = band_list.index(self.dominant_band) if self.dominant_band in band_list else 2
        sec_idx = band_list.index(self.secondary_band) if self.secondary_band and \
                  self.secondary_band in band_list else -1

        for ch in self.primary_channels:
            if ch not in CHANNEL_NAMES:
                continue
            ch_idx = CHANNEL_NAMES.index(ch)
            emb[ch_idx * N_BANDS + dom_idx] = 1.0
            if sec_idx >= 0:
                emb[ch_idx * N_BANDS + sec_idx] = 0.5

        self.embedding = emb


# ─── As 8 assinaturas pré-definidas ─────────────────────────────────────────

import warnings
warnings.filterwarnings("ignore", category=RuntimeWarning, module="scipy")

def _build_signatures() -> List[ErrorSignature]:
    """OPT-04: delegated to structural + behavioral groups."""
    sigs = _signatures_structural() + _signatures_behavioral()
    for sig in sigs:
        sig._build_embedding()
    return sigs


def _signatures_structural() -> List[ErrorSignature]:
    """AI_CODE_BOMB · GOD_CLASS · DEPENDENCY_CYCLE · TECH_DEBT."""
    return [
    # ── 1. AI_CODE_BOMB ────────────────────────────────────────────────
    ErrorSignature(
        error_type="AI_CODE_BOMB",
        description="Código AI-generated introduzido em massa sem revisão estrutural",
        severity_base="CRITICAL",
        primary_channels=["dead", "dups", "ILR"],
        dominant_band="MF",        # step-change sustentado aparece em MF/LF — física correta
        secondary_band="LF",
        temporal_pattern="step",   # não spike — o plateau permanece alto após onset
        inter_channel_correlation="positive",
        root_cause=(
            "Vibe coding sessions introduzem dead code, duplicatas e loops sem "
            "break condition simultaneamente. O padrão é um step-change sustentado "
            "(não transiente) em MF/LF — diferenciado de DEP_CYCLE pelos canais "
            "específicos (dead+dups+ILR) e de LOOP_RISK pela correlação cruzada alta "
            "entre dead e dups."
        ),
        recommended_action=(
            "Revisar commits após o onset detectado. "
            "Aplicar UCO T02 (unreachable removal) + T09 (unused vars). "
            "Verificar condições de saída em todos os loops introduzidos."
        ),
        apex_prompt_template=(
            "[UCO-SENSOR CRITICAL] AI_CODE_BOMB em {module_id}. "
            "H_delta={delta_h:.1f}. Canais: dead_code, dups, ILR em step MF. "
            "Onset: commit {cp_hash} ({cp_ago} commits atrás). "
            "Analisar commits recentes de IA e propor DIFF de limpeza estrutural."
        ),
    ),

    # ── 2. GOD_CLASS_FORMATION ────────────────────────────────────────
    ErrorSignature(
        error_type="GOD_CLASS_FORMATION",
        description="Classe ou módulo assumindo progressivamente múltiplas responsabilidades",
        severity_base="WARNING",
        primary_channels=["CC", "DSM_d", "DI"],
        dominant_band="MF",
        secondary_band="LF",
        temporal_pattern="correlated_rise",
        inter_channel_correlation="positive",
        root_cause=(
            "Cada sprint adiciona uma responsabilidade ao módulo. CC cresce com os casos. "
            "DSM_d cresce porque o módulo passa a depender de mais componentes. "
            "DI cresce por desequilíbrio fan-in/fan-out. Padrão LF = ritmo de sprint."
        ),
        recommended_action=(
            "Aplicar Extract Class pattern nos clusters de responsabilidade identificados. "
            "Usar análise DSM para identificar quais dependências pertencem a cada subclasse."
        ),
        apex_prompt_template=(
            "[UCO-SENSOR WARNING] GOD_CLASS_FORMATION em {module_id}. "
            "CC + DSM_density em correlação positiva LF por {n_commits} commits. "
            "Analisar coesão e propor decomposição em subclasses via Extract Class."
        ),
    ),

    # ── 3. DEPENDENCY_CYCLE_INTRODUCTION ──────────────────────────────
    ErrorSignature(
        error_type="DEPENDENCY_CYCLE_INTRODUCTION",
        description="Ciclo de dependência introduzido entre módulos",
        severity_base="CRITICAL",
        primary_channels=["DSM_c", "DI"],
        dominant_band="MF",
        secondary_band="LF",
        temporal_pattern="step",
        inter_channel_correlation="positive",
        root_cause=(
            "Durante integração de componentes desenvolvidos em paralelo, "
            "A importa B e B importa A. DSM_c sobe (SCC não-trivial). "
            "DI sobe por dependências bidirecionais. Padrão MF = ritmo de feature."
        ),
        recommended_action=(
            "Identificar ciclo via DSM. Inverter dependência menos crítica "
            "ou introduzir interface abstrata. Aplicar Dependency Inversion Principle."
        ),
        apex_prompt_template=(
            "[UCO-SENSOR CRITICAL] DEPENDENCY_CYCLE em {module_id}. "
            "DSM_cyclic + dep_instability em step-change MF. "
            "Mapear ciclo completo e propor inversão de dependência."
        ),
    ),

    # ── 4. TECH_DEBT_ACCUMULATION ─────────────────────────────────────
    ErrorSignature(
        error_type="TECH_DEBT_ACCUMULATION",
        description="Dívida técnica acumulando progressivamente em múltiplas dimensões",
        severity_base="WARNING",
        primary_channels=["H", "bugs", "CC"],
        dominant_band="ULF",
        secondary_band=None,
        temporal_pattern="monotone",
        inter_channel_correlation="positive",
        root_cause=(
            "Nenhum commit individual é catastrófico — cada um adiciona 'só um pouco'. "
            "H cresce linearmente ou pior. halstead.bugs_estimate cresce junto. "
            "Padrão ULF = acumulação durante meses sem refatoração sistemática."
        ),
        recommended_action=(
            "Planejar sprint de refatoração. Priorizar módulos por H_normalized. "
            "Estabelecer threshold máximo de H_normalized por módulo no processo de review."
        ),
        apex_prompt_template=(
            "[UCO-SENSOR WARNING] TECH_DEBT_ACCUMULATION em {module_id}. "
            "Tendência secular ULF: H, CC, halstead_bugs crescendo por {n_commits} commits. "
            "Estimar custo de reparo e propor roadmap de refatoração priorizado."
        ),
    ),

    ]


def _signatures_behavioral() -> List[ErrorSignature]:
    """LOOP_RISK · REFACTORING · DEAD_CODE_DRIFT · COGNITIVE."""
    return [
    # ── 5. LOOP_RISK_INTRODUCTION ─────────────────────────────────────
    ErrorSignature(
        error_type="LOOP_RISK_INTRODUCTION",
        description="Risco de loop infinito introduzido abruptamente — ILR isolado",
        severity_base="CRITICAL",
        primary_channels=["ILR"],
        dominant_band="HF",
        secondary_band="UHF",
        temporal_pattern="step",
        inter_channel_correlation="independent",
        root_cause=(
            "Adição de lógica de retry, polling ou processamento iterativo sem "
            "garantir condição de saída explícita. ILR sobe abruptamente enquanto "
            "outros canais permanecem estáveis — diferencial chave vs AI_CODE_BOMB."
        ),
        recommended_action=(
            "Revisar todos os loops introduzidos nos commits recentes. "
            "Adicionar break conditions, max_iterations, ou timeout guards. "
            "UCO T02 pode identificar o loop específico."
        ),
        apex_prompt_template=(
            "[UCO-SENSOR CRITICAL] LOOP_RISK em {module_id}. "
            "ILR step-change HF isolado (outros canais estáveis). "
            "Identificar loop específico e propor guard condition explícita."
        ),
    ),

    # ── 6. REFACTORING_IN_PROGRESS ────────────────────────────────────
    ErrorSignature(
        error_type="REFACTORING_IN_PROGRESS",
        description="Refatoração em andamento — padrão transitório esperado, não alerta",
        severity_base="INFO",
        primary_channels=["H", "CC", "DSM_d"],
        dominant_band="MF",
        secondary_band="LF",
        temporal_pattern="oscillating",
        inter_channel_correlation="negative",
        root_cause=(
            "Durante refatoração, o código frequentemente piora antes de melhorar. "
            "Extract Method aumenta CC temporariamente. Move Class perturba DSM. "
            "O padrão oscilante MF é a 'assinatura de trabalho em progresso'."
        ),
        recommended_action=(
            "Monitorar convergência: H deve cair após N commits de refatoração. "
            "Se H não cair em 2 sprints, a refatoração não está avançando — reavaliar."
            "Resetar baseline após conclusão com 'uco-sensor baseline commit'."
        ),
        apex_prompt_template=(
            "[UCO-SENSOR INFO] REFACTORING_IN_PROGRESS em {module_id}. "
            "Padrão oscilante MF em H/CC/DSM — comportamento normal de refatoração. "
            "Confirmar tendência convergente (H deve cair) ou alertar se estagnado."
        ),
    ),

    # ── 7. DEAD_CODE_DRIFT ────────────────────────────────────────────
    ErrorSignature(
        error_type="DEAD_CODE_DRIFT",
        description="Dead code acumulando silenciosamente ao longo do tempo",
        severity_base="WARNING",
        primary_channels=["dead"],
        dominant_band="MF",
        secondary_band="LF",
        temporal_pattern="monotone",
        inter_channel_correlation="independent",
        root_cause=(
            "APIs são modificadas mas implementações antigas não são removidas. "
            "Features desativadas mas código permanece. Diferente do AI_CODE_BOMB "
            "onde dups e ILR sobem junto. Aqui APENAS dead_code cresce monotonicamente."
        ),
        recommended_action=(
            "Aplicar UCO T02 (unreachable_after_terminal_removal) e "
            "T09 (python_unused_var_detector). Revisar contratos de API obsoletos."
        ),
        apex_prompt_template=(
            "[UCO-SENSOR WARNING] DEAD_CODE_DRIFT em {module_id}. "
            "dead_code em crescimento monotone LF por {n_commits} commits. "
            "Identificar APIs obsoletas e propor cleanup sistemático."
        ),
    ),

    # ── 8. COGNITIVE_COMPLEXITY_EXPLOSION ────────────────────────────
    ErrorSignature(
        error_type="COGNITIVE_COMPLEXITY_EXPLOSION",
        description="Explosão localizada de complexidade ciclomática — função ou classe",
        severity_base="CRITICAL",
        primary_channels=["CC", "H"],
        dominant_band="MF",
        secondary_band="HF",
        temporal_pattern="spike",
        inter_channel_correlation="positive",
        root_cause=(
            "Função ou método acumula condicionais rapidamente — if/elif em cascata "
            "em vez de Extract Method ou polimorfismo. Diferencial de GOD_CLASS: "
            "COGNITIVE_EXPLOSION é mais rápido (MF/HF) e afeta CC mais que DSM_d."
        ),
        recommended_action=(
            "Aplicar Extract Method nas funções com CC > 20. "
            "Introduzir early return patterns para reduzir aninhamento. "
            "Considerar Strategy pattern para múltiplos casos condicionais."
        ),
        apex_prompt_template=(
            "[UCO-SENSOR CRITICAL] COGNITIVE_EXPLOSION em {module_id}. "
            "CC spike MF/HF com H correlacionado. Identificar função com CC > 20 "
            "e propor decomposição com Extract Method."
        ),
    ),
    ]


# ─── ErrorSignatureLibrary ────────────────────────────────────────────────────

class ErrorSignatureLibrary:
    """
    Biblioteca de assinaturas de erro com matching rule-based e por embedding.

    Matching em duas camadas:
      1. Rule-based: rápido, interpretável, zero treinamento.
         Score combina energia na banda correta + padrão temporal + cross-coherência.

      2. Embedding similarity: cosine similarity entre o vetor de features atual
         e o embedding de cada assinatura. Refinamento para casos ambíguos.
    """

    def __init__(self, signatures: Optional[List[ErrorSignature]] = None):
        self.signatures = signatures or _build_signatures()

    # ─── Matching principal ──────────────────────────────────────────────

    def match(
        self,
        profiles: List[SpectralProfile],
        min_confidence: float = 0.25,
        signal: Optional["MetricSignal"] = None,
    ) -> List[SignatureMatch]:
        """
        Executa matching em 3 camadas:
          Camada 1: rule-based (energy + temporal + cross-coherence)
          Camada 2: embedding similarity
          Camada 3: persistence score (Hurst + PCI + Burst) — nova camada física

        signal é opcional para backward-compatibility; quando fornecido,
        habilita a Camada 3 que usa os dados brutos do sinal.
        """
        # Indexar profiles por canal
        ch_profiles  = {p.channel: p for p in profiles if "cross:" not in p.channel}
        cross_profiles = {p.channel: p for p in profiles if "cross:" in p.channel}

        # Construir embedding do estado atual
        current_emb = self._build_current_embedding(ch_profiles)

        # Camada 3: métricas de persistência e acuidade (se signal disponível)
        persistence_scores = {}
        if signal is not None:
            persistence_scores = self._compute_persistence_scores(signal)

        # GAP-S03: peso dinâmico da camada de persistência
        # GAP-A1/A2: pesos e thresholds adaptativos à banda N
        n_stable = len(getattr(signal, "stable_channels", []) or [])
        n_snaps  = getattr(signal, 'n_original', 30)
        # Get N-band adaptive params
        try:
            _band    = get_n_band(n_snaps)
            _ap      = ADAPTIVE_PARAMS[_band]
            _stab    = N_STABLE_THRESHOLDS[_band]
            _low     = _stab['low']
            _mod     = _stab['moderate']
        except Exception:
            _ap = {'w_pers': 0.20, 'w_emb': 0.20, 'w_spec': 0.60}
            _low, _mod = 3, 2

        if persistence_scores:
            if n_stable >= _low:
                # LOW_SPECTRAL_SIGNAL: persistência domina (regra espectral fraca)
                w_rule = _ap['w_spec'] * 0.50
                w_emb  = _ap['w_emb']
                w_pers = _ap['w_pers'] + 0.20
            elif n_stable >= _mod:
                # MODERATE: balancear
                w_rule = _ap['w_spec'] * 0.75
                w_emb  = _ap['w_emb']
                w_pers = _ap['w_pers'] + 0.10
            else:
                # GOOD: regra espectral prevalece com pesos da banda
                w_rule = _ap['w_spec']
                w_emb  = _ap['w_emb']
                w_pers = _ap['w_pers']
        else:
            w_rule = _ap['w_spec'] + _ap['w_pers']
            w_emb  = _ap['w_emb']
            w_pers = 0.0

        matches = []
        for sig in self.signatures:
            # Camada 1: rule-based
            rule_score = self._rule_score(sig, ch_profiles, cross_profiles, signal=signal)

            # Camada 2: embedding similarity
            emb_score = self._embedding_similarity(sig.embedding, current_emb)

            # Camada 3: persistence score para este tipo de erro
            pers_score = persistence_scores.get(sig.error_type, 0.5)

            # Combinar com pesos dinâmicos (GAP-S03)
            if w_pers > 0:
                combined = w_rule * rule_score + w_emb * emb_score + w_pers * pers_score
            else:
                combined = w_rule * rule_score + w_emb * emb_score

            if combined >= min_confidence:
                # Coletar evidências espectrais
                evidence = self._collect_evidence(sig, ch_profiles, cross_profiles)

                matches.append(SignatureMatch(
                    error_type=sig.error_type,
                    description=sig.description,
                    confidence=round(combined, 4),
                    matched_band=sig.dominant_band,
                    matched_channels=sig.primary_channels,
                    temporal_pattern=sig.temporal_pattern,
                    severity_base=sig.severity_base,
                    evidence=evidence,
                    recommended_action=sig.recommended_action,
                    apex_prompt_template=sig.apex_prompt_template,
                ))

        return sorted(matches, key=lambda m: m.confidence, reverse=True)

    # ─── Métodos de scoring ──────────────────────────────────────────────

    def _compute_persistence_scores(self, signal: "MetricSignal") -> Dict[str, float]:
        """
        Camada 3 de scoring: métricas de persistência e acuidade física.

        Para cada tipo de assinatura, retorna um score [0–1] de quão bem
        as métricas físicas do sinal se alinham com o perfil esperado.

        Métricas usadas:
          hurst_H     — Hurst Exponent via R/S Analysis (persistência)
          pci_CC_H    — Phase Coupling Index CC×H (sincronização)
          burst_H     — Burst Index (concentração temporal)
          hflf_H      — HF/LF ratio do canal H (distribuição espectral)

        Perfis esperados (calibrados na mineração de padrões):
          GOD_CLASS:   hurst>0.90, pci>0.90, burst<0.30, hflf<0.05
          TECH_DEBT:   hurst>0.95, pci>0.90, burst<0.30, hflf<0.04
          AI_CODE_BOMB:hurst<0.85, pci<0.35, burst>0.30, hflf<0.15
          DEP_CYCLE:   hurst<0.80, pci<0.45, burst<0.35, hflf<0.10
          COGNITIVE:   hurst<0.72, pci>0.85, burst>0.45, hflf<0.05
          LOOP_RISK:   hurst<0.85, pci<0.75, burst<0.25, hflf>0.10
          DEAD_CODE:   hurst>0.92, pci<0.25, burst<0.25, hflf>0.30
          REFACTORING: hurst<0.60, pci<0.70, burst<0.35, hflf<0.10
        """

        H_raw  = signal.data_raw[CHANNEL_IDX['H']]
        CC_raw = signal.data_raw[CHANNEL_IDX['CC']]
        n = len(H_raw)

        # ── Hurst Exponent (R/S Analysis) ─────────────────────────────
        def _hurst(ts, max_lags=20):
            n_ = len(ts)
            if n_ < 8: return 0.5
            rs_v, l_v = [], []
            for lag in range(4, min(n_//2, max_lags+4)):
                sub = ts[:lag]; m = sub.mean()
                dev = np.cumsum(sub - m); R = dev.max()-dev.min(); S = sub.std()+1e-10
                if R > 0: rs_v.append(np.log(R/S)); l_v.append(np.log(lag))
            if len(rs_v) < 3: return 0.5
            return float(np.clip(np.polyfit(l_v, rs_v, 1)[0], 0.0, 1.0))

        hurst_H = _hurst(H_raw)

        # ── Phase Coupling Index CC×H (Hilbert transform) ─────────────
        try:
            x_, y_ = CC_raw - CC_raw.mean(), H_raw - H_raw.mean()
            phi_x  = np.angle(_hilbert(x_))
            phi_y  = np.angle(_hilbert(y_))
            pci_CC_H = float(np.abs(np.mean(np.exp(1j * (phi_x - phi_y)))))
        except Exception:
            pci_CC_H = 0.5

        # ── Burst Index (CC channel, N/4 window — consistent with FrequencyClassifier) ──
        # Using same computation as classify(): CC channel, window = N/4
        # CC is more discriminant: COGNITIVE spikes CC massively (burst=0.95)
        # while GOD_CLASS/TECH_DEBT spread CC over many commits (burst=0.36-0.59)
        CC_raw_ = signal.data_raw[CHANNEL_IDX['CC']]
        diffs   = np.abs(np.diff(CC_raw_))
        total   = diffs.sum() + 1e-10
        win     = max(4, n // 4)
        if len(diffs) >= win:
            burst_H = float(max(diffs[i:i+win].sum() for i in range(len(diffs)-win+1)) / total)
        else:
            burst_H = 0.0

        # ── HF/LF ratio from SpectralProfile for H channel ─────────────
        # Extract from profiles indirectly via channel means
        # (SpectralProfile.band_energies_relative is already computed)
        # We use a proxy: variance of H in short windows vs. total
        short_win = max(4, n // 4)
        local_vars = [np.var(H_raw[i:i+short_win]) for i in range(0, n-short_win, short_win//2)]
        hflf_H = float(np.min(local_vars) / (np.max(local_vars) + 1e-10)) if local_vars else 0.5
        # Low proxy = energy concentrated in a burst (high HF/LF for dead code pattern)
        # Note: this is inverted — 0 = concentrated (like dead code drift)

        # ── Score per signature type ────────────────────────────────────
        # Each score measures alignment with expected profile via Gaussian membership
        def gauss(val, target, sigma):
            return float(np.exp(-0.5 * ((val - target) / sigma) ** 2))

        def profile_score(h_target, h_sigma, pci_target, pci_sigma, burst_target, burst_sigma):
            s_h     = gauss(hurst_H,   h_target,     h_sigma)
            s_pci   = gauss(pci_CC_H,  pci_target,   pci_sigma)
            s_burst = gauss(burst_H,   burst_target, burst_sigma)
            return float((s_h + s_pci + s_burst) / 3.0)

        scores = self._persistence_profiles(
            hurst_H, pci_CC_H, burst_H, hflf_H)
        return scores
    def _persistence_profiles(
        self,
        hurst_H: float,
        pci_CC_H: float,
        burst_H: float,
        hflf_H: float,
    ) -> Dict[str, float]:
        """OPT-04: Gaussian persistence profiles calibrated on 7 OSS repos."""
        import math as _math

        def gauss(val, target, sigma):
            """Gaussian similarity [0,1]."""
            return float(_math.exp(-0.5 * ((val - target) / max(sigma, 1e-6))**2))

        def profile_score(h_t, h_s, pci_t, pci_s, burst_t, burst_s):
            """Combined Gaussian score for the three physics dimensions."""
            return (0.50 * gauss(hurst_H, h_t, h_s) +
                    0.30 * gauss(pci_CC_H, pci_t, pci_s) +
                    0.20 * gauss(burst_H, burst_t, burst_s))

        scores = {
            # ── Calibrado em dados reais — 7 repos OSS, 14 módulos ────────────
            # Medições: H/PCI/Burst por tipo GT em flask, scrapy, requests,
            #           celery, django, fastapi, pandas
            # GOD_CLASS   H=0.81±0.20  PCI=0.87±0.29  Burst=0.40±0.29
            # TECH_DEBT   H=0.83±0.24  PCI=0.78±0.31  Burst=0.26±0.37
            # COGNITIVE   H=0.91±0.11  PCI=0.78±0.38  Burst=0.54±0.35
            # DEP_CYCLE   H=1.00       PCI=1.00        Burst=0.38
            # Decisões: sigmas muito mais largos (alta variância em OSS real);
            # COGNITIVE H-target: 0.60→0.85 (OSS maduro é sempre crônico)
            "GOD_CLASS_FORMATION":           profile_score(0.85, 0.22, 0.87, 0.20, 0.40, 0.30),
            "TECH_DEBT_ACCUMULATION":        profile_score(0.85, 0.22, 0.80, 0.22, 0.30, 0.30),
            "AI_CODE_BOMB":                  profile_score(0.79, 0.10, 0.11, 0.12, 0.40, 0.15),
            "DEPENDENCY_CYCLE_INTRODUCTION": profile_score(0.90, 0.15, 0.85, 0.20, 0.38, 0.15),
            "COGNITIVE_COMPLEXITY_EXPLOSION":profile_score(0.85, 0.18, 0.85, 0.20, 0.55, 0.30),
            "LOOP_RISK_INTRODUCTION":        profile_score(0.77, 0.10, 0.62, 0.18, 0.32, 0.12),
            "DEAD_CODE_DRIFT":               profile_score(1.00, 0.05, 0.15, 0.12, 0.38, 0.15),
            "REFACTORING_IN_PROGRESS":       profile_score(0.55, 0.18, 0.55, 0.22, 0.40, 0.20),
        }
        return scores

    def _rule_score_spectral(
        self,
        sig: "ErrorSignature",
        ch_profiles: dict,
        signal=None,
    ) -> tuple:
        """Componentes 1 (energia de banda) + 2 (temporal) do _rule_score."""
        import numpy as np
        # ── Componente 1: energia na banda correta ──────────────────────────
        # Usa raw_std (pré-z-score) como peso de signal strength — discrimina
        # canais que realmente se moveram vs canais com variância artefactual.
        band_scores = []
        for ch in sig.primary_channels:
            if ch not in ch_profiles:
                continue
            profile = ch_profiles[ch]
            be = profile.band_energies_relative
            dom_energy = be.get(sig.dominant_band, 0.0)
            # raw_std > 0.5 → canal se moveu significativamente em valores reais
            raw_std_ch = float(getattr(profile, 'raw_std', 1.0))
            signal_weight = min(1.0, max(0.1, raw_std_ch / 5.0))
            band_scores.append(dom_energy * signal_weight)
        energy_score = float(np.mean(band_scores)) if band_scores else 0.0

        # ── Componente 2: compatibilidade temporal ──────────────────────────
        temporal_scores = []
        for ch in sig.primary_channels:
            if ch not in ch_profiles:
                continue
            ts = self._temporal_compatibility(
                sig.temporal_pattern,
                ch_profiles[ch].temporal_pattern,
                ch_profiles[ch].spectral_entropy,
            )
            # GAP-R03: suppress if channel is stable
            stable = getattr(signal, 'stable_channels', []) or []
            if ch in stable:
                ts = 0.5  # neutralized
            temporal_scores.append(ts)
        temporal_score = float(np.mean(temporal_scores)) if temporal_scores else 0.0

        return energy_score, temporal_score

    def _rule_score(
        self,
        sig: "ErrorSignature",
        ch_profiles: dict,
        cross_profiles: dict,
        signal=None,
    ) -> float:
        """Rule score: spectral (comp1+comp2) + cross-coherence + bonuses."""
        import numpy as np
        energy_score, temporal_score = self._rule_score_spectral(sig, ch_profiles, signal)

        # ── Componente 3: coerência cross-canal ─────────────────────────────
        cross_score = 0.5  # default neutro
        stable = getattr(signal, 'stable_channels', []) or []
        if sig.primary_channels and len(sig.primary_channels) >= 2:
            cross_key = f"cross:{sig.primary_channels[0]}_{sig.primary_channels[1]}"
            alt_key   = f"cross:{sig.primary_channels[1]}_{sig.primary_channels[0]}"
            cp = cross_profiles.get(cross_key) or cross_profiles.get(alt_key)
            ch_a = sig.primary_channels[0]
            ch_b = sig.primary_channels[1] if len(sig.primary_channels) > 1 else ""
            both_stable = ch_a in stable and ch_b in stable
            if cp and not both_stable and cp.coherence is not None:
                # coherence is ndarray — take peak value as scalar
                import numpy as _np
                peak_coh = float(_np.max(cp.coherence))
            else:
                peak_coh = 0.5  # GAP-R03: suppressed
            cross_score = peak_coh

        # ── Signal Strength Weighting (via raw_std — pre-z-score) ─────────
        # raw_std > 1.0 → channel moved significantly in original units
        raw_stds = [float(getattr(ch_profiles[ch], 'raw_std', 1.0))
                    for ch in sig.primary_channels if ch in ch_profiles]
        if raw_stds:
            mean_raw_std  = float(np.mean(raw_stds))
            # Scale: raw_std 0.1..10 → signal_strength 0.1..1.0
            signal_strength = max(0.1, min(1.0, mean_raw_std / 3.0))
        else:
            signal_strength = 1.0
        energy_score  *= (0.3 + 0.7 * signal_strength)
        temporal_score *= (0.5 + 0.5 * signal_strength)

        # ── Bônus para exclusividade de canais ───────────────────────────────
        exclusivity_bonus = 0.0
        if sig.primary_channels:
            other_actives = sum(
                1 for ch, p in ch_profiles.items()
                if ch not in sig.primary_channels
                   and sum(p.band_energies_relative.values()) > 0.15
            )
            if other_actives == 0:
                exclusivity_bonus = 0.05

        # ── Bônus de isolamento para assinaturas de canal único ──────────────
        isolation_bonus = 0.0
        if len(sig.primary_channels) == 1:
            solo_ch = sig.primary_channels[0]
            if solo_ch in ch_profiles:
                others_quiet = all(
                    sum(ch_profiles[ch].band_energies_relative.values()) < 0.10
                    for ch in ch_profiles if ch != solo_ch
                )
                if others_quiet:
                    isolation_bonus = 0.08

        return min(1.0, 0.50 * energy_score + 0.25 * temporal_score +
                   0.25 * cross_score + exclusivity_bonus + isolation_bonus)

    def _temporal_compatibility(
        self,
        expected: str,
        observed: str,
        entropy: float,
    ) -> float:
        """Compatibilidade entre padrão temporal esperado e observado [0–1]."""
        if expected == observed:
            return 1.0
        compat = {
            ("monotone",   "correlated_rise"): 0.80,
            ("correlated_rise", "monotone"):   0.80,
            ("step",       "monotone"):        0.70,
            ("monotone",   "step"):            0.70,
            ("spike",      "oscillating"):     0.55,
            ("oscillating","spike"):           0.55,
            ("stable",     "monotone"):        0.35,
            ("stable",     "oscillating"):     0.40,
        }
        base = compat.get((expected, observed), 0.30)
        # High entropy → pattern less reliable → penalize
        entropy_factor = 1.0 - 0.4 * max(0.0, entropy - 0.6)
        return float(base * entropy_factor)

    def _embedding_similarity(
        self,
        sig_embedding: "np.ndarray",
        current_embedding: "np.ndarray",
    ) -> float:
        """Cosine similarity entre embeddings [0–1]."""
        import numpy as np
        a, b = np.asarray(sig_embedding), np.asarray(current_embedding)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a < 1e-10 or norm_b < 1e-10:
            return 0.0
        cosine = float(np.dot(a, b) / (norm_a * norm_b))
        return float(np.clip((cosine + 1.0) / 2.0, 0.0, 1.0))

    def _build_current_embedding(self, ch_profiles: dict) -> "np.ndarray":
        """Constrói embedding 45-dim do estado atual a partir dos SpectralProfiles."""
        import numpy as np
        from core.constants import CHANNEL_NAMES, BAND_NAMES, N_CHANNELS, N_BANDS
        emb = np.zeros(N_CHANNELS * N_BANDS, dtype=np.float64)
        for ch_idx, ch_name in enumerate(CHANNEL_NAMES):
            if ch_name not in ch_profiles:
                continue
            be = ch_profiles[ch_name].band_energies_relative
            for band_idx, band_name in enumerate(BAND_NAMES):
                emb[ch_idx * N_BANDS + band_idx] = be.get(band_name, 0.0)
        return emb

    def _collect_evidence(
        self,
        sig: "ErrorSignature",
        ch_profiles: dict,
        cross_profiles: dict,
    ) -> dict:
        """Coleta evidências espectrais que suportam o match."""
        evidence = {}
        for ch in sig.primary_channels:
            if ch not in ch_profiles:
                continue
            profile = ch_profiles[ch]
            be = profile.band_energies_relative
            evidence[f"{ch}_dominant_band"]  = profile.dominant_band
            evidence[f"{ch}_band_{sig.dominant_band}"] = be.get(sig.dominant_band, 0.0)
            evidence[f"{ch}_fw_shift"] = max(
                0.0,
                sum(be.get(b, 0.0) for b in ("ULF", "LF"))
                - sum(be.get(b, 0.0) for b in ("HF", "UHF"))
            )
        # Cross-coherence evidence
        if len(sig.primary_channels) >= 2:
            ch_a, ch_b = sig.primary_channels[0], sig.primary_channels[1]
            for key in (f"cross:{ch_a}_{ch_b}", f"cross:{ch_b}_{ch_a}"):
                if key in cross_profiles:
                    coh = cross_profiles[key].coherence
                    evidence["peak_coherence"] = float(coh.max()) if coh is not None else 0.0
                    break
        return evidence

