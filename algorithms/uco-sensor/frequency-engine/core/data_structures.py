"""
UCO-Sensor FrequencyEngine — Core Data Structures
===================================================
Todas as dataclasses que fluem pelo pipeline transmissor→receptor.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
import numpy as np


# ─── Entrada bruta do UCO ────────────────────────────────────────────────────

@dataclass
class MetricVector:
    """
    Snapshot de métricas UCO de um módulo em um commit específico.
    Saída direta do UCO.analyze() → entrada do Transmissor.
    
    Os 9 canais de sinal:
      [0] H        → Hamiltoniano total
      [1] CC       → Cyclomatic Complexity
      [2] ILR      → Infinite Loop Risk [0,1]
      [3] DSM_d    → DSM Density
      [4] DSM_c    → DSM Cyclic Ratio
      [5] DI       → Dependency Instability
      [6] dead     → Syntactic Dead Code
      [7] dups     → Duplicate Block Count
      [8] bugs     → Halstead Bugs Estimate
    """
    module_id: str
    commit_hash: str
    timestamp: float

    # 9 canais de sinal
    hamiltonian: float = 0.0
    cyclomatic_complexity: int = 0
    infinite_loop_risk: float = 0.0
    dsm_density: float = 0.0
    dsm_cyclic_ratio: float = 0.0
    dependency_instability: float = 0.0
    syntactic_dead_code: int = 0
    duplicate_block_count: int = 0
    halstead_bugs: float = 0.0
    window_position: float = 0.5   # BUG-R4: temporal position 0.0=oldest 1.0=newest

    # Metadados extras
    language: str = "unknown"
    lines_of_code: int = 0
    status: str = "STABLE"
    transform_chain: List[str] = field(default_factory=list)

    def to_array(self) -> np.ndarray:
        """Converte para vetor numpy [9] na ordem canônica dos canais."""
        return np.array([
            float(self.hamiltonian),
            float(self.cyclomatic_complexity),
            float(self.infinite_loop_risk),
            float(self.dsm_density),
            float(self.dsm_cyclic_ratio),
            float(self.dependency_instability),
            float(self.syntactic_dead_code),
            float(self.duplicate_block_count),
            float(self.halstead_bugs),
        ], dtype=np.float64)


# ─── Sinal preparado pelo Transmissor ────────────────────────────────────────

@dataclass
class MetricSignal:
    """
    Tensor de sinal [9 × N] normalizado e janelado.
    Output do MetricSignalBuilder (Transmissor).
    Input do SpectralAnalyzer (Receptor).
    
    Propriedades garantidas:
    - data[i] tem média ≈ 0 e std ≈ 1 (z-score normalizado)
    - Canais constantes têm data[i] = zeros
    - Amostras espaçadas uniformemente em [0,1]
    - Janelamento Hann aplicado para zero leakage espectral
    """
    data: np.ndarray            # shape: (9, N)
    data_raw: np.ndarray        # shape: (9, N) — antes do janelamento, após normalização
    timestamps: np.ndarray      # shape: (N,) — commit-index normalizado [0,1]

    # GAP-D1: phase analysis via window_position
    cc_phase_delta:     float = 0.0   # CC late-median minus early-median (z-scored)
    di_phase_delta:     float = 0.0   # DI late-median minus early-median
    cc_early:           float = 0.0   # CC median in first third of history
    cc_late:            float = 0.0   # CC median in last third of history

    # GAP-D2: max_methods series features
    max_methods_mean:   float = 0.0   # mean max_methods_per_class across history
    max_methods_growth: float = 0.0   # (last - first) / N per commit

    # GAP-D3: n_functions / n_classes series
    n_functions_mean:   float = 0.0   # mean n_functions across history
    n_functions_growth: float = 0.0   # (last - first) / N per commit
    n_classes_growth:   float = 0.0   # n_classes (last - first) / N per commit

    # GAP-D4: CC diff coefficient of variation (volatility of CC changes)
    cc_diff_cv:         float = 0.0   # std(|Δcc|) / (mean(|Δcc|) + ε)
    commit_hashes: List[str] = field(default_factory=list)
    module_id: str = ""
    sample_rate: float = 1.0        # amostras por unidade de tempo normalizada
    n_original: int = 0             # número de snapshots originais (antes de interpolar)
    channel_names: List[str] = field(default_factory=lambda: [
        "H", "CC", "ILR", "DSM_d", "DSM_c", "DI", "dead", "dups", "bugs"
    ])
    channel_means: np.ndarray = field(default_factory=lambda: np.zeros(9))
    channel_stds: np.ndarray = field(default_factory=lambda: np.ones(9))
    window_fn: str = "hann"
    # GAP-R03: canais com variância rolling < threshold (série estabilizada)
    # cross-coherência suprimida para estes canais em _rule_score()
    stable_channels: List[str] = field(default_factory=list)

    @property
    def n_samples(self) -> int:
        return self.data.shape[1]

    @property
    def n_channels(self) -> int:
        return self.data.shape[0]

    def get_channel(self, name: str) -> np.ndarray:
        idx = self.channel_names.index(name)
        return self.data[idx]

    def get_channel_raw(self, name: str) -> np.ndarray:
        idx = self.channel_names.index(name)
        return self.data_raw[idx]


# ─── Análise espectral de um canal ───────────────────────────────────────────

@dataclass
class SpectralProfile:
    """
    Análise espectral completa de um único canal (ou par de canais cruzados).
    Output do SpectralAnalyzer por canal.
    """
    module_id: str
    channel: str                        # nome do canal ou "cross:A_B"

    # Domínio de frequência — Welch PSD
    frequencies: np.ndarray             # shape: (K,) — eixo de frequências
    power_spectrum: np.ndarray          # shape: (K,) — PSD por frequência
    dominant_freq: float                # frequência com maior potência
    dominant_power: float

    # Entropia espectral de Shannon
    spectral_entropy: float             # 0=periódico, 1=ruído branco

    # STFT — localização tempo-frequência
    stft_freqs: np.ndarray             # shape: (F,)
    stft_times: np.ndarray             # shape: (T,)
    stft_magnitude: np.ndarray          # shape: (F, T) — |STFT|

    # Decomposição Wavelet (Haar com 5 níveis)
    wavelet_energies: np.ndarray        # shape: (6,) — energia por nível [approx, d5..d1]
    wavelet_level_names: List[str]

    # Energia por banda de frequência
    band_energies: Dict[str, float]     # {"ULF": e, "LF": e, "MF": e, "HF": e, "UHF": e}
    band_energies_relative: Dict[str, float]  # normalizado para somar 1
    dominant_band: str                  # banda com maior energia relativa

    # Padrão temporal inferido da entropia + forma da PSD
    temporal_pattern: str               # "spike"|"monotone"|"oscillating"|"step"|"stable"

    # Para cruzamento de canais (se channel == "cross:*")
    coherence: Optional[np.ndarray] = None   # coerência espectral [0,1]
    phase_lag_commits: Optional[float] = None  # defasagem em commits

    # Estatísticas básicas do sinal no tempo
    signal_mean: float = 0.0
    signal_std: float = 0.0
    signal_trend: float = 0.0          # slope de regressão linear (positivo=crescendo)

    # ── CSL: Lozovsky & Churkin (2024) — atributos espectrais validados ─────
    weighted_mean_freq: float = 0.0    # f_w = Σ(f·PSD)/Σ(PSD) — centro de massa espectral
    fw_shift: float = 0.0              # (0.25 - fw) / 0.25 — deslocamento para esquerda (>0.20 = anomalia)
    norm_spectrum_area: float = 1.0    # A_n = A_atual / A_baseline (<0.70 = anomalia confirmada)

    # ── Signal Strength — raw pre-normalization std ───────────────────────────
    # Utilizado para weighting de cross-coerência: evita amplificação de micro-variância
    # (noise floor fix: canal com σ_raw pequeno não infla coerência cruzada)
    raw_std: float = 1.0               # std bruto antes de z-score — preservado do channel_stds


# ─── Resultado da classificação ──────────────────────────────────────────────

@dataclass
class SignatureMatch:
    """Match de um sinal contra uma assinatura de erro."""
    error_type: str
    description: str
    confidence: float                   # [0.0, 1.0]
    matched_band: str
    matched_channels: List[str]
    temporal_pattern: str
    severity_base: str                  # INFO|WARNING|CRITICAL
    evidence: Dict[str, float]          # features espectrais que sustentam o match
    recommended_action: str
    apex_prompt_template: str


@dataclass
class ChangePoint:
    """Ponto de mudança detectado pelo PELT."""
    commit_idx: int                     # índice no vetor de commits
    commit_hash: Optional[str]
    confidence: float
    magnitude: float                    # magnitude da mudança
    affected_channels: List[str]


@dataclass
class ClassificationResult:
    """Output final do FrequencyClassifier — o que sai do Receptor."""
    module_id: str
    timestamp: float

    # Classificação primária
    primary_error: str
    primary_confidence: float
    severity: str                       # INFO|WARNING|CRITICAL
    severity_score: float               # [0.0, 1.0]

    # Top-3 hipóteses
    hypotheses: List[SignatureMatch]

    # Localização temporal do onset
    change_point: Optional[ChangePoint]

    # Análise espectral resumida
    dominant_band: str
    band_description: str
    spectral_evidence: Dict[str, Any]

    # Outputs humanos
    plain_english: str
    technical_summary: str
    apex_prompt: str

    # Sugestões de correção via UCO
    suggested_transforms: List[str]
    potential_delta_h: float

    # Metadados do sinal analisado
    n_commits_analyzed: int
    analysis_timestamp: float = 0.0

    # ── Métricas de persistência e causalidade (descobertas na mineração) ──────
    # Derivadas de Hurst R/S Analysis e Phase Coupling Index (Hilbert transform)
    # Permitem ao APEX prever se o problema é estruturalmente persistente

    hflf_ratio_H: float = 0.0
    # HF/LF energy ratio do canal H: energia(HF+UHF) / energia(ULF+LF)
    # > 0.30 → DEAD_CODE_DRIFT (oscilações irregulares em HF sobre tendência)
    # < 0.05 → GOD_CLASS / TECH_DEBT (crescimento suave, energia totalmente em LF)
    # 0.10–0.15 → LOOP_RISK (step cria HF moderado)
    # Derivado diretamente de SpectralProfile.band_energies_relative do canal H

    burst_index_H: float = 0.0
    # Concentração temporal da mudança no canal H [0–1]
    # = max_rolling_sum(diff_H, window=N/8) / total_diff_H
    # > 0.50 → evento AGUDO e concentrado (COGNITIVE_EXPLOSION=0.67, AI_CODE_BOMB=0.42)
    # < 0.25 → degradação CRÔNICA e distribuída (GOD_CLASS=0.19, TECH_DEBT=0.23)
    # Chave para distinguir GOD_CLASS (burst baixo) de COGNITIVE (burst alto)

    hurst_H: float = 0.5
    # Exponente de Hurst do canal H (Hamilton energy):
    # > 0.90 → CRÔNICO: não regride sem intervenção ativa (DEAD_CODE, TECH_DEBT, GOD_CLASS)
    # 0.55–0.85 → AGUDO com persistência (AI_CODE_BOMB, LOOP_RISK, DEP_CYCLE)
    # < 0.55 → TRANSITÓRIO: pode se resolver sozinho (REFACTORING)

    phase_coupling_CC_H: float = 0.0
    # Phase Coupling Index entre CC e H (via Hilbert transform):
    # > 0.90 → H dominado por CC (GOD_CLASS, COGNITIVE_EXPLOSION)
    # < 0.25 → H dominado por outros canais (AI_CODE_BOMB, DEAD_CODE — CC mal se move)

    onset_reversibility: float = 0.0

    # GAP-R04: confiança do onset baseada na posição relativa na janela
    # "RELIABLE"     — onset após 15% da série (detectado dentro da história)
    # "EARLY_WINDOW" — onset nos primeiros 15% (possível artefato de janela curta)
    # "NO_ONSET"     — nenhum change point detectado
    onset_confidence_context: str = "UNKNOWN"

    # GAP-V1: flag de integridade espectral
    is_spectrally_valid: bool = True
    # False quando grade == INSUFFICIENT (N < MIN_SNAPSHOTS_SPECTRAL).
    # Indica que o tipo detectado é especulativo — não há série temporal suficiente.
    # Quão reversível é o onset detectado [0–1]:
    # 0.0 → irreversível (GOD_CLASS=0.02, COGNITIVE=0.01, TECH_DEBT=0.06)
    # 0.5 → parcialmente reversível (AI_CODE_BOMB=0.07, DEP_CYCLE=0.06)
    # >0.15 → reversível (LOOP_RISK=0.23 — ILR pode ser corrigido rapidamente)
    # Derivado de: max(0, peak_H - final_H) / (peak_H - pre_onset_mean)

    self_cure_probability: float = 0.0
    # Probabilidade estimada de auto-resolução sem intervenção humana [0–100%]:
    # formula: max(0, (1 - hurst_H) × 100) × onset_reversibility_factor
    # Exemplos calibrados: DEAD_CODE ≈ 0%, GOD_CLASS ≈ 2%, COGNITIVE ≈ 10%
    # Útil para priorização: módulos com < 5% devem ser intervenção imediata

    # ── GAP-S03/S04: qualidade do sinal espectral ────────────────────────
    n_stable_channels: int = 0
    # Número de canais com variância rolling < threshold (série estabilizada).
    # Canal estável = sinal espectral suprimido (cross-coherência zerada).
    # 0–1: sinal bom  |  2: sinal moderado  |  ≥3: LOW_SPECTRAL_SIGNAL

    spectral_signal_quality: str = "GOOD"
    # "GOOD"              — ≤1 canal estável, análise espectral confiável
    # "MODERATE"          — 2 canais estáveis, resultados com reserva
    # "LOW_SPECTRAL_SIGNAL" — ≥3 canais estáveis, persistência domina
    # "SHALLOW_HISTORY"   — N < 30 snapshots, história insuficiente

    # ── GAP-S06: grau de confiança final ─────────────────────────────────
    classification_grade: str = "CONFIRMED"
    # "CONFIRMED"   — conf ≥ 60% e sinal bom
    # "LIKELY"      — conf 40–60% ou sinal moderado
    # "UNCERTAIN"   — conf < 40% ou LOW_SPECTRAL_SIGNAL
    # "INSUFFICIENT"— N < 30 (histórico insuficiente para classificação)


# ─── Propagation Fingerprint ────────────────────────────────────────────────────

@dataclass
class PropagationFingerprint:
    """
    Impressão digital de propagação de sinal entre canais UCO.

    Derivado da física de ondas CSL: diferentes defeitos têm velocidades
    e padrões de propagação distintos. Aqui, "propagação" é o delay de
    onset entre canais primários de uma assinatura de erro.

    Três padrões fundamentais mensuráveis:

    ISOLATED (spread=0, n_channels=1):
      Apenas 1 canal se move. Outros ficam estáveis.
      → LOOP_RISK (só ILR), DEAD_CODE_DRIFT (só dead)

    SIMULTANEOUS (spread ≤ 2 commits):
      Todos os canais disparam ao mesmo tempo.
      → AI_CODE_BOMB, DEP_CYCLE, COGNITIVE_EXPLOSION, REFACTORING

    CASCADED_SLOW (spread > 10 commits):
      Os canais disparam em sequência ao longo de muitos commits.
      → GOD_CLASS (DI→CC→DSM_d, spread≈21), TECH_DEBT (bugs→CC→H, spread≈45)

    A chave diferenciadora mais poderosa:
      GOD_CLASS vs COGNITIVE_EXPLOSION:
        GOD_CLASS   → CASCADED_SLOW (DI lidera CC por ~16 commits)
        COGNITIVE   → SIMULTANEOUS  (CC e H disparam juntos)
    """
    # Padrão geral
    propagation_pattern: str       # "ISOLATED" | "SIMULTANEOUS" | "CASCADED_FAST" | "CASCADED_SLOW"
    onset_spread_commits: int      # commits entre o canal que dispara primeiro e o último

    # Ordem temporal de onset dos canais primários
    channel_onset_order: List[str]    # ex: ["DI", "CC", "DSM_d"]
    channel_onset_indices: List[int]  # índice de onset no sinal normalizado

    # Canal que lidera (primeiro a mudar) — diagnóstico causal
    leading_channel: Optional[str]
    lagging_channel: Optional[str]

    # Número de canais primários com onset detectável
    n_channels_activated: int

    # Velocidade de propagação normalizada
    # propagation_velocity = n_channels_activated / max(1, onset_spread_commits)
    # Alta velocidade (>0.5): evento agudo (bomb, ciclo)
    # Baixa velocidade (<0.1): degradação crônica (god class, tech debt)
    propagation_velocity: float


# ─── Output de descoberta DBSCAN ─────────────────────────────────────────────

@dataclass
class SignatureCandidate:
    """Nova assinatura descoberta automaticamente via DBSCAN."""
    candidate_id: str
    cluster_label: int
    n_samples: int
    centroid_embedding: np.ndarray      # shape: (45,)
    dominant_channels: List[str]        # 3 canais com maior peso no centróide
    dominant_band: str
    example_modules: List[str]          # módulos onde foi observado
    estimated_temporal_pattern: str
    requires_human_review: bool = True
    approved: bool = False
    approved_as_type: Optional[str] = None
# NOTE: f_w fields appended below SpectralProfile — injected by SpectralAnalyzer
