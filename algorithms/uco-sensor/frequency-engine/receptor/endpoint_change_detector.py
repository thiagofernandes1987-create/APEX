"""
EndpointChangeDetector
======================

Online detector for the question that PELT does not answer well:

    "Did the most recent snapshot move materially away from the prior regime?"

PELT requires observations on both sides of a breakpoint. A labelled PR placed
at the final sample therefore needs a different statistic. This detector uses
robust per-channel endpoint residuals against the previous regime.

The returned score is an effect size, not a probability.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

import numpy as np

from core.data_structures import MetricSignal


@dataclass
class EndpointChange:
    max_robust_z: float
    mean_top3_robust_z: float
    rms_robust_z: float
    affected_channels: List[str] = field(default_factory=list)
    channel_robust_z: Dict[str, float] = field(default_factory=dict)
    n_prior: int = 0


class EndpointChangeDetector:
    """Robust final-snapshot deviation detector.

    For each channel:
      z = |x_last - median(x_prior)| / robust_scale

    robust_scale is 1.4826*MAD, with a conservative standard-deviation fallback
    when MAD collapses. The detector deliberately does not emit a calibrated
    probability. affected_threshold is only an interpretability threshold;
    benchmark models receive the continuous effect sizes.
    """

    def __init__(self, affected_threshold: float = 3.5, min_prior: int = 8):
        self.affected_threshold = float(affected_threshold)
        self.min_prior = int(min_prior)

    def detect(self, signal: MetricSignal) -> EndpointChange:
        data = getattr(signal, "data_unscaled", None)
        if data is None:
            data = signal.data_raw

        arr = np.asarray(data, dtype=float)
        if arr.ndim != 2 or arr.shape[1] < self.min_prior + 1:
            return EndpointChange(
                max_robust_z=0.0,
                mean_top3_robust_z=0.0,
                rms_robust_z=0.0,
                n_prior=max(0, arr.shape[1] - 1 if arr.ndim == 2 else 0),
            )

        prior = arr[:, :-1]
        last = arr[:, -1]
        med = np.median(prior, axis=1)
        mad = np.median(np.abs(prior - med[:, None]), axis=1)
        robust = 1.4826 * mad
        std = np.std(prior, axis=1, ddof=1)

        magnitude_floor = np.maximum(np.abs(med) * 1e-6, 1e-9)
        scale = np.maximum.reduce([robust, 0.5 * std, magnitude_floor])

        z = np.abs(last - med) / scale
        z = np.where(np.isfinite(z), z, 0.0)

        names = list(signal.channel_names[: len(z)])
        per_channel = {name: float(val) for name, val in zip(names, z)}
        affected = [
            name for name, val in per_channel.items()
            if val >= self.affected_threshold
        ]

        ordered = np.sort(z)[::-1]
        top3 = ordered[: min(3, len(ordered))]
        return EndpointChange(
            max_robust_z=float(ordered[0] if len(ordered) else 0.0),
            mean_top3_robust_z=float(np.mean(top3) if len(top3) else 0.0),
            rms_robust_z=float(np.sqrt(np.mean(z ** 2)) if len(z) else 0.0),
            affected_channels=affected,
            channel_robust_z=per_channel,
            n_prior=int(prior.shape[1]),
        )
