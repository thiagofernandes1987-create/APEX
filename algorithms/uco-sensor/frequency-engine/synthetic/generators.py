"""
UCO-Sensor FrequencyEngine — Geradores de Dados Sintéticos
==========================================================
Gera séries temporais sintéticas realistas para cada tipo de erro.

Cada gerador produz List[MetricVector] que exibe as características
espectrais esperadas pela assinatura correspondente.

Os dados sintéticos têm:
  - Componente de sinal (padrão de erro específico)
  - Ruído gaussiano (realismo — métricas reais sempre têm ruído)
  - Valores base realistas para cada métrica UCO
  - N configurável (default 60 commits = história de ~3 sprints)

Uso nos testes:
  history = generate_ai_code_bomb(n=60, onset=45)
  result  = engine.analyze(history)
  assert result.primary_error == "AI_CODE_BOMB"
"""
from __future__ import annotations
import numpy as np
from typing import List, Optional, Callable
import time

from core.data_structures import MetricVector
from core.constants import CHANNEL_NAMES


def _make_timestamps(n: int, base_ts: float = 1700000000.0) -> List[float]:
    """Gera timestamps simulando commits irregulares (1-6 horas entre commits)."""
    rng = np.random.default_rng(42)
    intervals = rng.uniform(3600, 21600, size=n)   # 1h–6h entre commits
    ts = base_ts + np.cumsum(intervals)
    return ts.tolist()


def _make_commits(n: int, prefix: str = "abc") -> List[str]:
    rng = np.random.default_rng(hash(prefix) % (2**31))
    return [f"{prefix}{rng.integers(0, 0xFFFFFF):06x}" for _ in range(n)]


def _mv(
    module_id: str,
    commit_hash: str,
    timestamp: float,
    h: float = 5.0,
    cc: int = 5,
    ilr: float = 0.02,
    dsm_d: float = 0.20,
    dsm_c: float = 0.05,
    di: float = 0.30,
    dead: int = 2,
    dups: int = 1,
    bugs: float = 0.10,
    noise_std: float = 0.0,
    rng: Optional[np.random.Generator] = None,
) -> MetricVector:
    """Constrói MetricVector com ruído gaussiano opcional."""
    if rng is None:
        rng = np.random.default_rng()
    n = lambda x, s=noise_std: float(max(0.0, x + rng.normal(0, s)))
    return MetricVector(
        module_id=module_id,
        commit_hash=commit_hash,
        timestamp=timestamp,
        hamiltonian=n(h, s=noise_std * 0.5),
        cyclomatic_complexity=max(1, int(round(n(cc, s=noise_std)))),
        infinite_loop_risk=float(np.clip(n(ilr, s=noise_std * 0.05), 0, 1)),
        dsm_density=float(np.clip(n(dsm_d, s=noise_std * 0.05), 0, 1)),
        dsm_cyclic_ratio=float(np.clip(n(dsm_c, s=noise_std * 0.05), 0, 1)),
        dependency_instability=float(np.clip(n(di, s=noise_std * 0.1), 0, 3)),
        syntactic_dead_code=max(0, int(round(n(dead, s=noise_std)))),
        duplicate_block_count=max(0, int(round(n(dups, s=noise_std * 0.5)))),
        halstead_bugs=float(max(0, n(bugs, s=noise_std * 0.1))),
        language="python",
        lines_of_code=max(50, int(round(n(300, s=30)))),
        status="STABLE" if h < 10 else "WARNING" if h < 20 else "CRITICAL",
    )


# ─── 1. AI_CODE_BOMB ─────────────────────────────────────────────────────────

def generate_ai_code_bomb(
    n: int = 60,
    onset: int = 40,
    module_id: str = "auth.token_validator",
    noise: float = 0.5,
    seed: int = 1,
) -> List[MetricVector]:
    """
    AI_CODE_BOMB: spike súbito e mantido em dead, dups e ILR no commit `onset`.
    
    Padrão: HF — energia concentrada na segunda metade do sinal.
    Correlação: dead, dups e ILR sobem simultânea e fortemente.
    
    Nota sobre o gerador: usamos incremento suave (não inteiros aleatórios)
    para que o spike apareça como step-change HF limpo e não como oscilação MF.
    """
    rng = np.random.default_rng(seed)
    commits = _make_commits(n, "bomb")
    timestamps = _make_timestamps(n)
    history = []

    for i in range(n):
        in_bomb = i >= onset
        # Spike limpo: valor fixo alto + pequeno ruído uniforme (sem inteiros que oscilem)
        dead_base  = rng.uniform(0.8, 1.5)
        dups_base  = rng.uniform(0.5, 1.0)
        dead  = dead_base + (rng.uniform(14.0, 18.0) if in_bomb else 0.0)
        dups  = dups_base + (rng.uniform(7.0,  11.0) if in_bomb else 0.0)
        ilr   = rng.uniform(0.01, 0.03) + (rng.uniform(0.38, 0.52) if in_bomb else 0.0)
        h     = 5.0 + dead * 0.4 + dups * 0.3 + ilr * 8.0

        history.append(_mv(
            module_id=module_id, commit_hash=commits[i], timestamp=timestamps[i],
            h=h, cc=int(5 + rng.integers(0, 3)), ilr=float(np.clip(ilr, 0, 1)),
            dsm_d=float(rng.uniform(0.18, 0.25)), dsm_c=float(rng.uniform(0.03, 0.08)),
            di=float(rng.uniform(0.25, 0.40)),
            dead=int(round(dead)), dups=int(round(max(0.0, dups))),
            bugs=max(0.05, h * 0.015), noise_std=noise * 0.2, rng=rng,
        ))

    return history


# ─── 2. GOD_CLASS_FORMATION ──────────────────────────────────────────────────

def generate_god_class(
    n: int = 60,
    module_id: str = "core.service_manager",
    noise: float = 0.4,
    seed: int = 2,
) -> List[MetricVector]:
    """
    GOD_CLASS: CC, DSM_d e DI crescem correlacionadamente em LF.
    
    Padrão: LF — gradual, ritmo de sprint (~10-15 commits por ciclo).
    Correlação: positiva entre CC, DSM_d, DI.
    """
    rng = np.random.default_rng(seed)
    commits = _make_commits(n, "god")
    timestamps = _make_timestamps(n)
    history = []

    for i in range(n):
        # Crescimento linear com ondulações (ritmo LF)
        t = i / n
        lf_cycle = np.sin(2 * np.pi * t * 3)   # ~3 ciclos em n commits = LF
        cc   = int(8  + 22 * t + 2 * lf_cycle + rng.normal(0, 1))
        dsm_d = float(np.clip(0.20 + 0.35 * t + 0.03 * lf_cycle + rng.normal(0, 0.02), 0, 1))
        di    = float(np.clip(0.30 + 0.40 * t + 0.05 * lf_cycle + rng.normal(0, 0.03), 0, 3))
        h     = 5.0 + cc * 0.4 + dsm_d * 8.0 + di * 2.0

        history.append(_mv(
            module_id=module_id, commit_hash=commits[i], timestamp=timestamps[i],
            h=h, cc=max(3, cc), ilr=float(rng.uniform(0.01, 0.04)),
            dsm_d=dsm_d, dsm_c=float(rng.uniform(0.03, 0.08)), di=di,
            dead=int(rng.integers(1, 4)), dups=int(rng.integers(0, 2)),
            bugs=max(0.05, h * 0.012), noise_std=noise * 0.5, rng=rng,
        ))

    return history


# ─── 3. DEPENDENCY_CYCLE ─────────────────────────────────────────────────────

def generate_dependency_cycle(
    n: int = 60,
    onset: int = 35,
    module_id: str = "infra.event_bus",
    noise: float = 0.4,
    seed: int = 3,
) -> List[MetricVector]:
    """
    DEPENDENCY_CYCLE: step-change em DSM_c e DI no commit `onset`.
    
    Padrão: MF — step abrupto mas mantido (não spike transitório).
    Correlação: positiva entre DSM_c e DI.
    """
    rng = np.random.default_rng(seed)
    commits = _make_commits(n, "cyc")
    timestamps = _make_timestamps(n)
    history = []

    for i in range(n):
        has_cycle = i >= onset
        dsm_c = float(rng.uniform(0.02, 0.06)) + (rng.uniform(0.28, 0.42) if has_cycle else 0)
        di    = float(rng.uniform(0.20, 0.35)) + (rng.uniform(0.30, 0.45) if has_cycle else 0)
        cc    = int(8 + rng.integers(0, 5))
        h     = 5.0 + cc * 0.3 + dsm_c * 15.0 + di * 3.0

        history.append(_mv(
            module_id=module_id, commit_hash=commits[i], timestamp=timestamps[i],
            h=h, cc=cc, ilr=float(rng.uniform(0.01, 0.04)),
            dsm_d=float(rng.uniform(0.22, 0.32)), dsm_c=dsm_c, di=di,
            dead=int(rng.integers(1, 4)), dups=int(rng.integers(0, 2)),
            bugs=max(0.05, h * 0.010), noise_std=noise * 0.4, rng=rng,
        ))

    return history


# ─── 4. TECH_DEBT ────────────────────────────────────────────────────────────

def generate_tech_debt(
    n: int = 80,
    module_id: str = "legacy.data_processor",
    noise: float = 0.6,
    seed: int = 4,
) -> List[MetricVector]:
    """
    TECH_DEBT: H, bugs e CC crescem lentamente e monotonamente — tendência ULF.
    
    Padrão: ULF — secular, sem reversão, alta variância mas trend positivo.
    """
    rng = np.random.default_rng(seed)
    commits = _make_commits(n, "debt")
    timestamps = _make_timestamps(n)
    history = []

    for i in range(n):
        t = i / n
        # Crescimento quadrático lento + ruído alto
        h    = 8.0 + 25.0 * t**1.5 + rng.normal(0, 1.5)
        cc   = int(10 + 30 * t + rng.normal(0, 2))
        bugs = max(0.1, 0.15 + 0.60 * t + rng.normal(0, 0.05))

        history.append(_mv(
            module_id=module_id, commit_hash=commits[i], timestamp=timestamps[i],
            h=max(5, h), cc=max(5, cc), ilr=float(rng.uniform(0.01, 0.05)),
            dsm_d=float(np.clip(0.25 + 0.15 * t + rng.normal(0, 0.03), 0, 1)),
            dsm_c=float(rng.uniform(0.04, 0.10)), di=float(rng.uniform(0.30, 0.50)),
            dead=int(3 + 8 * t + rng.integers(0, 3)),
            dups=int(1 + 4 * t + rng.integers(0, 2)),
            bugs=bugs, noise_std=noise * 0.3, rng=rng,
        ))

    return history


# ─── 5. LOOP_RISK ────────────────────────────────────────────────────────────

def generate_loop_risk(
    n: int = 50,
    onset: int = 40,
    module_id: str = "workers.retry_handler",
    noise: float = 0.3,
    seed: int = 5,
) -> List[MetricVector]:
    """
    LOOP_RISK: ILR sobe abruptamente no commit `onset`. Outros canais ESTÁVEIS.
    
    Diagnóstico diferencial de AI_CODE_BOMB: APENAS ILR muda.
    Padrão: HF — step-change isolado em alta frequência.
    """
    rng = np.random.default_rng(seed)
    commits = _make_commits(n, "loop")
    timestamps = _make_timestamps(n)
    history = []

    for i in range(n):
        has_loop = i >= onset
        ilr = float(rng.uniform(0.01, 0.04)) + (rng.uniform(0.40, 0.70) if has_loop else 0)
        cc  = int(7 + rng.integers(0, 4))
        h   = 5.0 + cc * 0.3 + ilr * 12.0

        history.append(_mv(
            module_id=module_id, commit_hash=commits[i], timestamp=timestamps[i],
            h=h, cc=cc, ilr=float(np.clip(ilr, 0, 1)),
            dsm_d=float(rng.uniform(0.15, 0.22)), dsm_c=float(rng.uniform(0.02, 0.06)),
            di=float(rng.uniform(0.25, 0.38)),
            dead=int(rng.integers(1, 3)), dups=int(rng.integers(0, 2)),
            bugs=max(0.05, h * 0.010), noise_std=noise * 0.4, rng=rng,
        ))

    return history


# ─── 6. REFACTORING ──────────────────────────────────────────────────────────

def generate_refactoring(
    n: int = 60,
    refactor_start: int = 20,
    refactor_end: int = 50,
    module_id: str = "api.request_parser",
    noise: float = 0.5,
    seed: int = 6,
) -> List[MetricVector]:
    """
    REFACTORING: H e CC oscilam durante refatoração (sobem, depois caem).
    
    Padrão: MF — oscilante, padrão em reversão (correlação negativa H×CC).
    """
    rng = np.random.default_rng(seed)
    commits = _make_commits(n, "refac")
    timestamps = _make_timestamps(n)
    history = []

    for i in range(n):
        t_norm = (i - refactor_start) / max(1, refactor_end - refactor_start)
        if i < refactor_start:
            cc = int(25 + rng.integers(0, 3))
            h  = 18.0 + rng.normal(0, 1.5)
        elif i < refactor_end:
            # Oscilação: sobe temporariamente antes de cair
            osc = np.sin(2 * np.pi * t_norm * 2)
            cc  = int(max(5, 25 + 8 * t_norm * osc - 15 * max(0, t_norm - 0.5)))
            h   = max(5, 18.0 + 6 * osc - 12 * max(0, t_norm - 0.5))
        else:
            # Pós-refatoração: estabilizado em nível mais baixo
            cc = int(10 + rng.integers(0, 3))
            h  = 7.0 + rng.normal(0, 1.0)

        dsm_d = float(np.clip(0.30 - 0.15 * max(0, (i - refactor_start) / n), 0, 1))
        history.append(_mv(
            module_id=module_id, commit_hash=commits[i], timestamp=timestamps[i],
            h=max(4, h), cc=max(3, cc), ilr=float(rng.uniform(0.01, 0.04)),
            dsm_d=dsm_d, dsm_c=float(rng.uniform(0.02, 0.07)), di=float(rng.uniform(0.20, 0.40)),
            dead=int(max(0, 5 - int(i > refactor_start) * 3 + rng.integers(0, 2))),
            dups=int(max(0, 3 - int(i > refactor_start) * 2 + rng.integers(0, 2))),
            bugs=max(0.05, abs(h) * 0.010), noise_std=noise * 0.4, rng=rng,
        ))

    return history


# ─── 7. DEAD_CODE_DRIFT ──────────────────────────────────────────────────────

def generate_dead_code_drift(
    n: int = 70,
    module_id: str = "billing.invoice_handler",
    noise: float = 0.4,
    seed: int = 7,
) -> List[MetricVector]:
    """
    DEAD_CODE_DRIFT: dead_code cresce monotonamente. Outros canais ESTÁVEIS.
    
    Diagnóstico diferencial de AI_CODE_BOMB: APENAS dead cresce.
    Padrão: LF/ULF — gradual, sem correlação com outros canais.
    """
    rng = np.random.default_rng(seed)
    commits = _make_commits(n, "dead")
    timestamps = _make_timestamps(n)
    history = []

    for i in range(n):
        t = i / n
        dead = int(2 + 28 * t + rng.normal(0, 1.5))   # cresce de 2 a 30
        cc   = int(8 + rng.integers(0, 4))
        h    = 5.0 + cc * 0.3 + dead * 0.35

        history.append(_mv(
            module_id=module_id, commit_hash=commits[i], timestamp=timestamps[i],
            h=max(4, h), cc=cc, ilr=float(rng.uniform(0.01, 0.03)),
            dsm_d=float(rng.uniform(0.18, 0.24)), dsm_c=float(rng.uniform(0.02, 0.05)),
            di=float(rng.uniform(0.25, 0.35)),
            dead=max(0, dead), dups=int(rng.integers(0, 2)),
            bugs=max(0.05, h * 0.010), noise_std=noise * 0.3, rng=rng,
        ))

    return history


# ─── 8. COGNITIVE_EXPLOSION ───────────────────────────────────────────────────

def generate_cognitive_explosion(
    n: int = 55,
    onset: int = 42,
    module_id: str = "rules.business_logic",
    noise: float = 0.5,
    seed: int = 8,
) -> List[MetricVector]:
    """
    COGNITIVE_EXPLOSION: CC e H sobem rapidamente em MF/HF.
    
    Diferencial de GOD_CLASS: mais rápido (MF/HF) e afeta CC mais que DSM_d.
    """
    rng = np.random.default_rng(seed)
    commits = _make_commits(n, "cog")
    timestamps = _make_timestamps(n)
    history = []

    for i in range(n):
        exploding = i >= onset
        # Spike rápido em CC — acelerado mas não instantâneo como AI_CODE_BOMB
        t_after = max(0, i - onset) / max(1, n - onset)
        cc   = int(8 + rng.integers(0, 3)) + (int(18 * t_after**0.5) if exploding else 0)
        h    = 5.0 + cc * 0.5 + rng.normal(0, 1.0)

        history.append(_mv(
            module_id=module_id, commit_hash=commits[i], timestamp=timestamps[i],
            h=max(4, h), cc=max(3, cc), ilr=float(rng.uniform(0.01, 0.04)),
            dsm_d=float(rng.uniform(0.18, 0.26)), dsm_c=float(rng.uniform(0.02, 0.07)),
            di=float(rng.uniform(0.25, 0.38)),
            dead=int(rng.integers(1, 4)), dups=int(rng.integers(0, 2)),
            bugs=max(0.05, h * 0.012), noise_std=noise * 0.4, rng=rng,
        ))

    return history


# ─── Mapa completo ────────────────────────────────────────────────────────────

ALL_GENERATORS = {
    "AI_CODE_BOMB":                 generate_ai_code_bomb,
    "GOD_CLASS_FORMATION":          generate_god_class,
    "DEPENDENCY_CYCLE_INTRODUCTION":generate_dependency_cycle,
    "TECH_DEBT_ACCUMULATION":       generate_tech_debt,
    "LOOP_RISK_INTRODUCTION":       generate_loop_risk,
    "REFACTORING_IN_PROGRESS":      generate_refactoring,
    "DEAD_CODE_DRIFT":              generate_dead_code_drift,
    "COGNITIVE_COMPLEXITY_EXPLOSION":generate_cognitive_explosion,
}


def generate_all() -> dict:
    """Gera dados para todos os tipos de erro. Retorna {error_type: history}."""
    return {name: gen() for name, gen in ALL_GENERATORS.items()}
