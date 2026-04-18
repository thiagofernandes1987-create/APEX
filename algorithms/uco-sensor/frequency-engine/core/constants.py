"""
UCO-Sensor — Constantes Centralizadas
======================================
Fonte única de verdade para todas as constantes do sistema.
Elimina magic numbers (BUG-OPT-02 da autópsia v07).
"""
from typing import Tuple, Dict, List

# ─── Canais (ordem imutável — mudança quebra CHANNEL_IDX) ────────────────────
CHANNEL_NAMES: Tuple[str, ...] = (
    "H", "CC", "ILR", "DSM_d", "DSM_c", "DI", "dead", "dups", "bugs"
)
N_CHANNELS: int = len(CHANNEL_NAMES)

# BUG-C03: índices por nome — elimina data_raw[0], data_raw[5], etc.
CHANNEL_IDX: Dict[str, int] = {name: i for i, name in enumerate(CHANNEL_NAMES)}

# ─── Bandas de frequência (ciclos / commit-index normalizado) ─────────────────
FREQ_BANDS: Dict[str, Tuple[float, float]] = {
    "ULF": (0.00, 0.05),   # >20 commits/ciclo — tech debt secular
    "LF":  (0.05, 0.10),   # 10–20 commits — God Class / dead code drift
    "MF":  (0.10, 0.25),   # 4–10 commits — dependency cycles
    "HF":  (0.25, 0.50),   # 2–4 commits — AI bomb / loop risk
    "UHF": (0.50, 1.00),   # <2 commits — spike isolado
}
BAND_NAMES: List[str] = list(FREQ_BANDS.keys())
N_BANDS: int = len(BAND_NAMES)

BAND_DESCRIPTIONS: Dict[str, str] = {
    "ULF": "tendência secular (>20 commits/ciclo) — problema arquitetura",
    "LF":  "padrão de médio prazo (10–20 commits) — design debt acumulado",
    "MF":  "padrão por feature (4–10 commits) — problema de módulo",
    "HF":  "padrão por commit (2–4 commits) — mudança introduzida recentemente",
    "UHF": "ponto de anomalia (<2 commits) — spike isolado no último commit",
}

# ─── Embedding ────────────────────────────────────────────────────────────────
EMBEDDING_DIM: int = N_CHANNELS * N_BANDS   # 9 × 5 = 45

# ─── Pipeline — limites mínimos ───────────────────────────────────────────────
MIN_SAMPLES_FOR_SPECTRAL: int = 5    # mínimo absoluto para análise espectral
MIN_SAMPLES_FOR_PELT:     int = 10   # mínimo para change-point detection (PELT)
MIN_SNAPSHOTS_SPECTRAL:   int = 30   # mínimo recomendado (calibrado em 7 repos OSS)
MIN_NPERSEG:              int = 4    # mínimo Welch/STFT (abaixo → NaN scipy)
MIN_SAMPLES_FOR_WAVELET:  int = 16   # mínimo para DWT multi-level
MIN_SAMPLES_FOR_DBSCAN:   int = 10   # mínimo de amostras para DBSCAN clustering

# ─── Numeric stability ────────────────────────────────────────────────────────
EPSILON: float = 1e-10

# ─── Pesos de scoring dinâmico (GAP-S03) ─────────────────────────────────────
W_RULE_GOOD:  float = 0.55;  W_EMB_GOOD:  float = 0.30;  W_PERS_GOOD:  float = 0.15
W_RULE_MOD:   float = 0.42;  W_EMB_MOD:   float = 0.28;  W_PERS_MOD:   float = 0.30
W_RULE_LOW:   float = 0.30;  W_EMB_LOW:   float = 0.30;  W_PERS_LOW:   float = 0.40
W_RULE_NPERS: float = 0.65;  W_EMB_NPERS: float = 0.35   # sem persistence layer

# ─── Signal quality thresholds (GAP-S04) ─────────────────────────────────────
N_STABLE_MODERATE: int = 2
N_STABLE_LOW:      int = 3

# ─── Classification grade thresholds (GAP-S06) ───────────────────────────────
GRADE_CONFIRMED_MIN_CONF: float = 0.60
GRADE_LIKELY_MIN_CONF:    float = 0.40
GRADE_UNCERTAIN_MAX_CONF: float = 0.35

# ─── Estabilidade de canal (GAP-R03) ─────────────────────────────────────────
STABILITY_CV_THRESHOLD:    float = 0.03
STABILITY_RANGE_THRESHOLD: float = 0.05
STABILITY_WINDOW:          int   = 5

# ─── Burst Index (GAP-S01/S05) ────────────────────────────────────────────────
BURST_WINDOW_MAX: int   = 100  # GAP-A1: was 15 — cap too aggressive for N≥100, killed COGNITIVE detection
BURST_NEUTRAL:    float = 0.40

# ─── Hurst Exponent ───────────────────────────────────────────────────────────
HURST_MIN_LAG:  int = 4
HURST_N_POINTS: int = 20   # pontos em log-space para R/S analysis

# ─── Identity override thresholds ─────────────────────────────────────────────
COGNITIVE_BURST_THRESHOLD:  float = 0.70
GOD_CLASS_BURST_THRESHOLD:  float = 0.70
GOD_CLASS_HURST_MIN:        float = 0.80
GOD_CLASS_HURST_LATE_MIN:   float = 0.85
GOD_CLASS_PCI_MIN:          float = 0.85
GOD_CLASS_DI_STD_MIN:       float = 0.50
GOD_CLASS_CC_STD_MIN:       float = 1.00

# ─── Wavelet coefficients (Daubechies-4 e Haar) ───────────────────────────────
DB4_H0: Tuple[float, ...] = (
     0.48296291314469025,  0.83651630373780772,
     0.22414386804185735, -0.12940952255092145,
)
DB4_H1: Tuple[float, ...] = (
    -0.12940952255092145, -0.22414386804185735,
     0.83651630373780772, -0.48296291314469025,
)
HAAR_H0: Tuple[float, ...] = (0.7071067811865476,  0.7071067811865476)
HAAR_H1: Tuple[float, ...] = (0.7071067811865476, -0.7071067811865476)

# ─── Calibration profiles (GAP-S02 — medidos em 7 repos OSS) ─────────────────
HURST_PROFILES: Dict[str, Tuple[float, float]] = {
    "GOD_CLASS_FORMATION":            (0.85, 0.22),
    "TECH_DEBT_ACCUMULATION":         (0.85, 0.22),
    "AI_CODE_BOMB":                   (0.79, 0.10),
    "DEPENDENCY_CYCLE_INTRODUCTION":  (0.90, 0.15),
    "COGNITIVE_COMPLEXITY_EXPLOSION": (0.85, 0.18),
    "LOOP_RISK_INTRODUCTION":         (0.77, 0.10),
    "DEAD_CODE_DRIFT":                (1.00, 0.05),
    "REFACTORING_IN_PROGRESS":        (0.55, 0.18),
}

# ─── Diagnostic channel pairs ─────────────────────────────────────────────────
DIAGNOSTIC_PAIRS: Tuple[Tuple[str, str, str], ...] = (
    ("CC",    "DSM_d",  "god_class"),
    ("DSM_c", "DI",     "dep_cycle"),
    ("dead",  "dups",   "ai_bomb"),
    ("H",     "bugs",   "tech_debt"),
    ("ILR",   "DSM_c",  "loop_risk"),
)

# ─── GAP-A1: Sistema de 5 bandas de N — parâmetros adaptativos ────────────────
# Com N=5 e N=200 os mesmos pesos produzem resultados estatisticamente inconsistentes.
# Cada banda tem nperseg, pesos de camada, burst threshold e validade espectral.

N_HISTORY_BANDS: dict = {
    'NANO':   (5,   19),    # Deserto estatístico — só métricas brutas
    'SPARSE': (20,  39),    # Espectral instável — persistência domina
    'THIN':   (40,  79),    # Análise viável mas limitada
    'MEDIUM': (80,  149),   # Análise confiável
    'RICH':   (150, 9999),  # Análise completa
}

def get_n_band(n: int) -> str:
    """Retorna a banda N-adaptativa para um histórico de n commits."""
    for band, (lo, hi) in N_HISTORY_BANDS.items():
        if lo <= n <= hi:
            return band
    return 'RICH'

# Parâmetros por banda: w_pers/w_emb/w_spec = pesos matching layers
# nperseg_div: nperseg = max(4, N // nperseg_div)
# burst_thr: None = não usar burst override em banda NANO
# is_spectrally_valid: False impede emissão de tipo falso
ADAPTIVE_PARAMS: dict = {
    'NANO':   {
        'w_pers': 0.60, 'w_emb': 0.25, 'w_spec': 0.15,
        'nperseg_div': 4, 'burst_thr': None,  'valid': False,
        'burst_neutral': 0.40, 'hurst_lags': 8,
    },
    'SPARSE': {
        'w_pers': 0.45, 'w_emb': 0.25, 'w_spec': 0.30,
        'nperseg_div': 5, 'burst_thr': 0.82, 'valid': False,
        'burst_neutral': 0.40, 'hurst_lags': 8,
    },
    'THIN':   {
        'w_pers': 0.35, 'w_emb': 0.22, 'w_spec': 0.43,
        'nperseg_div': 5, 'burst_thr': 0.75, 'valid': True,
        'burst_neutral': 0.35, 'hurst_lags': 11,
    },
    'MEDIUM': {
        'w_pers': 0.20, 'w_emb': 0.20, 'w_spec': 0.60,
        'nperseg_div': 4, 'burst_thr': 0.70, 'valid': True,
        'burst_neutral': 0.30, 'hurst_lags': 22,
    },
    'RICH':   {
        'w_pers': 0.20, 'w_emb': 0.20, 'w_spec': 0.60,
        'nperseg_div': 3, 'burst_thr': 0.70, 'valid': True,
        'burst_neutral': 0.30, 'hurst_lags': 30,
    },
}

# GAP-A2: n_stable thresholds como ratio por banda
# Em vez de absoluto (LOW=3, MODERATE=2), escala com N
N_STABLE_THRESHOLDS: dict = {
    'NANO':   {'low': 9, 'moderate': 9},   # nunca rebaixa — N too small to judge
    'SPARSE': {'low': 5, 'moderate': 3},
    'THIN':   {'low': 4, 'moderate': 2},
    'MEDIUM': {'low': 3, 'moderate': 2},   # valores atuais v08
    'RICH':   {'low': 2, 'moderate': 1},   # com N grande 2 canais estáveis = normal
}

# Threshold COGNITIVE burst por banda (GAP-N4 composto)
COGNITIVE_BURST_STRONG: float = 0.85   # certeza forte (independe de PCI)
# Zona 0.70–0.85: COGNITIVE só confirmado se PCI também alto (ver GAP-N4)

