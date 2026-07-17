"""M1 — proveniência determinística de arquivos e configurações."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

from ..contracts import GateEnvelope, ModuleContext


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json_hash(value: Any) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_manifest(paths: Iterable[Path], context: ModuleContext) -> GateEnvelope:
    candidate_paths = list(paths)
    if not candidate_paths:
        return GateEnvelope.blocked(
            "M1.PROVENANCE",
            "M1",
            "Manifesto não foi criado porque nenhuma fonte foi informada.",
            "Forneça ao menos um arquivo de entrada para estabelecer proveniência.",
            run_id=context.run_id,
        )
    files: list[dict[str, Any]] = []
    missing: list[str] = []
    for raw_path in candidate_paths:
        path = raw_path.resolve()
        if not path.is_file():
            missing.append(str(path))
            continue
        files.append(
            {
                "path": str(path),
                "size_bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    if missing:
        return GateEnvelope.blocked(
            "M1.PROVENANCE",
            "M1",
            "Manifesto não foi criado porque há entradas ausentes.",
            "Arquivos ausentes: " + ", ".join(missing),
            run_id=context.run_id,
        )
    manifest = {
        "files": sorted(files, key=lambda item: item["path"]),
        "config_sha256": canonical_json_hash(dict(context.config)),
    }
    return GateEnvelope.passed(
        "M1.PROVENANCE",
        "M1",
        f"Manifesto criado para {len(files)} arquivo(s).",
        metrics={"manifest": manifest, "manifest_sha256": canonical_json_hash(manifest)},
        run_id=context.run_id,
    )
