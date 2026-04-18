"""
UCO-Sensor FrequencyEngine — DBSCAN Discovery
==============================================
DBSCANDiscovery: descobre padrões de erro novos (não cobertos pelas 8 assinaturas
canônicas) a partir de embeddings espectrais via clustering DBSCAN.

Fundamento matemático:
  DBSCAN (Density-Based Spatial Clustering of Applications with Noise) —
  Ester et al., KDD 1996.

  Dado conjunto de pontos X = {x_i ∈ R^45}, dois hiper-parâmetros:
    eps     : raio de vizinhança (ε-ball)
    min_pts : mínimo de pontos para um core-point

  Algoritmo:
    1. Um ponto x é core-point se |N_ε(x)| ≥ min_pts
    2. x e y são diretamente density-reachable se x é core-point e y ∈ N_ε(x)
    3. Um cluster é o fecho transitivo de density-reachability
    4. Pontos não atingíveis por nenhum core-point são ruído (label=-1)

  Vantagens sobre k-means para descoberta de assinaturas:
    • Não requer número de clusters pré-definido
    • Detecta clusters de forma arbitrária (assinaturas têm geometrias variadas)
    • Ruído explícito (módulos inclassificáveis não contaminam clusters)
    • O(N log N) com kd-tree; aqui O(N²) aceitável para N ≤ 5000 módulos

  Filtro de novidade:
    Centróide de cluster é novo se distância coseno a TODOS os embeddings de
    assinaturas existentes > novelty_threshold. Clusters "já vistos" são
    descartados — apenas padrões genuinamente novos chegam à revisão humana.

Implementação numpy-puro (sem sklearn) — consistente com wavelet_engine.py e
change_point_detector.py. Única dependência: numpy.
"""
from __future__ import annotations
import numpy as np
from typing import List, Optional, Dict, Tuple
from dataclasses import dataclass, field

from core.data_structures import SpectralProfile, SignatureCandidate
from core.constants import CHANNEL_NAMES, BAND_NAMES, N_CHANNELS, N_BANDS


# ─── DBSCAN numpy-puro ───────────────────────────────────────────────────────

def _cosine_distance(a: np.ndarray, b: np.ndarray) -> float:
    """Distância coseno ∈ [0, 2]. 0 = idênticos, 2 = opostos."""
    na = np.linalg.norm(a)
    nb = np.linalg.norm(b)
    if na < 1e-12 or nb < 1e-12:
        return 1.0   # sinal nulo → distância neutra
    return float(1.0 - np.dot(a, b) / (na * nb))


def _pairwise_cosine(X: np.ndarray) -> np.ndarray:
    """
    Matriz de distâncias coseno NxN em numpy puro.

    X shape: (N, D)
    Retorna D shape: (N, N) com D[i,j] = cosine_dist(X[i], X[j])

    Implementação vetorizada: cos_dist = 1 - (X @ X.T) / (||X_i|| · ||X_j||)
    """
    norms = np.linalg.norm(X, axis=1, keepdims=True)           # (N, 1)
    norms = np.where(norms < 1e-12, 1.0, norms)
    X_normed = X / norms                                         # (N, D) unit-normed
    similarity = X_normed @ X_normed.T                          # (N, N) ∈ [-1, 1]
    similarity = np.clip(similarity, -1.0, 1.0)
    return (1.0 - similarity).astype(np.float64)                # cosine distance


def _dbscan(
    X: np.ndarray,
    eps: float = 0.35,
    min_pts: int = 2,
) -> np.ndarray:
    """
    DBSCAN sobre matriz de distâncias pre-computada.

    Parâmetros
    ----------
    X       : (N, D) tensor de embeddings
    eps     : raio ε para ε-vizinhança (distância coseno)
    min_pts : mínimo de vizinhos para core-point

    Retorna
    -------
    labels : (N,) array int — cluster label por ponto. -1 = ruído.
    """
    N = len(X)
    if N == 0:
        return np.array([], dtype=int)

    D = _pairwise_cosine(X)    # (N, N)

    # Vizinhos de cada ponto dentro do eps-ball
    neighbors: List[List[int]] = [
        list(np.where(D[i] <= eps)[0])
        for i in range(N)
    ]

    labels = np.full(N, -1, dtype=int)
    cluster_id = 0

    for i in range(N):
        if labels[i] != -1:
            continue
        if len(neighbors[i]) < min_pts:
            # Ruído (por ora — pode ser borda depois)
            continue

        # Novo cluster: expandir de i
        labels[i] = cluster_id
        seeds = list(neighbors[i])

        si = 0
        while si < len(seeds):
            q = seeds[si]
            si += 1

            if labels[q] == -1:
                labels[q] = cluster_id   # borda ou core

            if len(neighbors[q]) < min_pts:
                continue   # ponto de borda — não expande

            # Core-point: adicionar vizinhos não visitados
            for r in neighbors[q]:
                if labels[r] == -1:
                    labels[r] = cluster_id
                    seeds.append(r)

        cluster_id += 1

    return labels


# ─── Extração de embedding 45-dim de List[SpectralProfile] ───────────────────

def _embedding_from_profiles(profiles: List[SpectralProfile]) -> np.ndarray:
    """
    Constrói embedding 45-dim [9 canais × 5 bandas] a partir de perfis espectrais.

    Para cada canal individual (não cross-channel), extrai energias relativas
    por banda e preenche o vetor de embedding.

    Mesma lógica de ErrorSignatureLibrary._current_embedding() para consistência
    no filtro de novidade.
    """
    emb = np.zeros(N_CHANNELS * N_BANDS, dtype=np.float64)

    # Indexar perfis por canal
    ch_profiles: Dict[str, SpectralProfile] = {}
    for p in profiles:
        if not p.channel.startswith("cross:"):
            ch_profiles[p.channel] = p

    for ch_idx, ch_name in enumerate(CHANNEL_NAMES):
        if ch_name not in ch_profiles:
            continue
        be_rel = ch_profiles[ch_name].band_energies_relative
        for band_idx, band_name in enumerate(BAND_NAMES):
            emb[ch_idx * N_BANDS + band_idx] = be_rel.get(band_name, 0.0)

    # Normalizar para norma unitária
    norm = np.linalg.norm(emb)
    if norm > 1e-12:
        emb /= norm

    return emb


# ─── DBSCANDiscovery ──────────────────────────────────────────────────────────

class DBSCANDiscovery:
    """
    Descobre assinaturas de erro novas via DBSCAN sobre embeddings espectrais.

    Workflow:
      1. Recebe List[List[SpectralProfile]] (um conjunto por módulo)
      2. Extrai embedding 45-dim de cada conjunto
      3. Roda DBSCAN para agrupar módulos com padrões similares
      4. Para cada cluster: computa centróide + canais dominantes
      5. Filtra clusters que já são cobertos pelas assinaturas existentes
      6. Retorna List[SignatureCandidate] com requires_human_review=True

    Parâmetros
    ----------
    eps             : raio ε da ε-vizinhança DBSCAN (distância coseno).
                      0.35 calibrado para que embeddings de mesma assinatura
                      fiquem no mesmo cluster (intra-sig dist ≈ 0.15–0.25).
    min_pts         : mínimo de módulos para formar cluster (default 2).
                      min_pts=2 adequado para datasets pequenos (< 100 módulos).
    novelty_threshold: distância coseno mínima ao centróide de assinatura
                      existente para considerar cluster como novo.
                      0.30 = 30% diferença vetorial ≈ padrão genuinamente novo.
    """

    def __init__(
        self,
        eps: float = 0.35,
        min_pts: int = 2,
        novelty_threshold: float = 0.30,
        min_cluster_size: Optional[int] = None,   # alias para min_pts (compatibilidade)
    ):
        self.eps               = eps
        # min_cluster_size é alias para min_pts — usado pelos testes
        self.min_pts           = min_cluster_size if min_cluster_size is not None else min_pts
        self.novelty_threshold = novelty_threshold

    # ─── API pública ─────────────────────────────────────────────────────────

    def discover(
        self,
        all_profile_sets: List[List[SpectralProfile]],
        existing_embeddings: Optional[np.ndarray] = None,
        module_ids: Optional[List[str]] = None,
    ) -> List[SignatureCandidate]:
        """
        Executa descoberta de assinaturas novas.

        Parâmetros
        ----------
        all_profile_sets    : um List[SpectralProfile] por módulo
        existing_embeddings : (K, 45) array de embeddings das assinaturas canônicas.
                              None → sem filtro de novidade.
        module_ids          : nomes dos módulos correspondentes a all_profile_sets.

        Retorna
        -------
        List[SignatureCandidate] — apenas clusters com padrões genuinamente novos.
        """
        if not all_profile_sets:
            return []

        N = len(all_profile_sets)
        if module_ids is None:
            module_ids = [f"module_{i}" for i in range(N)]

        # 1. Extrair embeddings 45-dim de cada módulo
        embeddings = np.stack(
            [_embedding_from_profiles(ps) for ps in all_profile_sets],
            axis=0,
        )  # shape: (N, 45)

        # Descartar embeddings nulos (módulos com sinal insuficiente)
        valid_mask = np.linalg.norm(embeddings, axis=1) > 1e-10
        if valid_mask.sum() < self.min_pts:
            return []

        X_valid = embeddings[valid_mask]
        ids_valid = [module_ids[i] for i in range(N) if valid_mask[i]]
        profiles_valid = [all_profile_sets[i] for i in range(N) if valid_mask[i]]

        # 2. DBSCAN
        labels = _dbscan(X_valid, eps=self.eps, min_pts=self.min_pts)

        # 3. Agrupar por cluster
        cluster_ids = set(labels) - {-1}
        if not cluster_ids:
            return []

        candidates: List[SignatureCandidate] = []

        for cid in sorted(cluster_ids):
            mask = labels == cid
            cluster_embs = X_valid[mask]
            cluster_mids = [ids_valid[i] for i, m in enumerate(mask) if m]
            cluster_profs = [profiles_valid[i] for i, m in enumerate(mask) if m]

            # 4. Centróide do cluster
            centroid = cluster_embs.mean(axis=0)
            centroid_norm = np.linalg.norm(centroid)
            if centroid_norm > 1e-12:
                centroid = centroid / centroid_norm

            # 5. Filtro de novidade
            if existing_embeddings is not None and len(existing_embeddings) > 0:
                dists = np.array([
                    _cosine_distance(centroid, existing_embeddings[k])
                    for k in range(len(existing_embeddings))
                ])
                if dists.min() < self.novelty_threshold:
                    continue   # cluster coberto por assinatura existente

            # 6. Canais dominantes (top-3 componentes do centróide)
            dominant_channels = self._dominant_channels(centroid)

            # 7. Banda dominante (máxima energia acumulada no centróide)
            dominant_band = self._dominant_band(centroid)

            # 8. Padrão temporal mais comum no cluster
            temporal_pattern = self._most_common_temporal_pattern(cluster_profs)

            candidate = SignatureCandidate(
                candidate_id=f"CANDIDATE_{cid:03d}",
                cluster_label=int(cid),
                n_samples=int(mask.sum()),
                centroid_embedding=centroid,
                dominant_channels=dominant_channels,
                dominant_band=dominant_band,
                example_modules=cluster_mids[:5],   # max 5 exemplos
                estimated_temporal_pattern=temporal_pattern,
                requires_human_review=True,
                approved=False,
                approved_as_type=None,
            )
            candidates.append(candidate)

        return candidates

    def summary(self, candidates: List[SignatureCandidate]) -> str:
        """Resumo legível da descoberta para logs/verbose mode."""
        if not candidates:
            return "[DBSCANDiscovery] Nenhum padrão novo encontrado."

        lines = [
            f"[DBSCANDiscovery] {len(candidates)} candidato(s) novo(s):",
        ]
        for c in candidates:
            lines.append(
                f"  • {c.candidate_id}: n={c.n_samples}  "
                f"canais={c.dominant_channels}  "
                f"banda={c.dominant_band}  "
                f"padrão={c.estimated_temporal_pattern}  "
                f"exemplos={c.example_modules[:2]}"
            )
        lines.append("  → requires_human_review=True em todos os candidatos")
        return "\n".join(lines)

    # ─── Helpers internos ────────────────────────────────────────────────────

    def _dominant_channels(self, centroid: np.ndarray) -> List[str]:
        """
        Retorna os 3 canais com maior peso acumulado no centróide.
        Peso do canal i = soma das energias em todas as 5 bandas.
        """
        channel_weights = np.array([
            centroid[i * N_BANDS: (i + 1) * N_BANDS].sum()
            for i in range(N_CHANNELS)
        ])
        top3 = np.argsort(channel_weights)[::-1][:3]
        return [CHANNEL_NAMES[i] for i in top3]

    def _dominant_band(self, centroid: np.ndarray) -> str:
        """
        Banda com maior energia acumulada no centróide.
        Energia da banda b = soma sobre todos os 9 canais.
        """
        band_weights = np.array([
            centroid[b::N_BANDS].sum()   # step=N_BANDS → índices da mesma banda
            for b in range(N_BANDS)
        ])
        return BAND_NAMES[int(np.argmax(band_weights))]

    def _most_common_temporal_pattern(
        self,
        profile_sets: List[List[SpectralProfile]],
    ) -> str:
        """Padrão temporal mais frequente entre todos os canais do cluster."""
        from collections import Counter
        patterns: List[str] = []
        for profs in profile_sets:
            for p in profs:
                if not p.channel.startswith("cross:") and p.temporal_pattern:
                    patterns.append(p.temporal_pattern)
        if not patterns:
            return "unknown"
        return Counter(patterns).most_common(1)[0][0]
