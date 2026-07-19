#!/usr/bin/env python3
"""
federation.py — o protótipo de FEDERAÇÃO: pacotes de conhecimento VALIDADO, assinados,
circulando entre instâncias (o efeito de rede da visão do autor, desbloqueado pelo ledger
multi-dispositivo).

WHY THIS EXISTS:
  Cada instância do APEX aprende sozinha (vacinas, personas promovidas, rotinas comprovadas).
  A federação faz as experiências BEM-SUCEDIDAS de uma instância virarem insumo de
  auto-evolução de todas: um pacote carrega SOMENTE o que passou pelos gates (learning
  PROMOTED, vacinas promováveis >0.85, rotinas PROMOTED, grants aprovados), leva a PROVA
  (a cadeia de ledger do dispositivo de origem, verificável elo a elo) e é assinado
  (SHA-256; HMAC quando APEX_FED_KEY está definida nas duas pontas). Como memórias e cadeias
  são endereçadas por conteúdo/dispositivo, a fusão é por união determinística: o LOCAL vence
  em conflito, reimportar é idempotente, e N instâncias intercalam N cadeias íntegras.

WHEN TO USE:
  - export_pack(): ao fim de um ciclo com aprendizado validado — gera o pacote para publicar
    (staging/ -> commit no repositório, Drive, ou envio direto a outra instância).
  - verify_pack(pack): SEMPRE antes de considerar um pacote recebido (integridade + procedência).
  - import_pack(pack, approved=True): instala conhecimento de outra instância — exige o gate
    humano H5 (um pacote equipa habilidades e muda comportamento futuro; é exatamente o que
    H5 governa). Sem approved -> BLOCKED. Adulterado -> REJECTED antes de qualquer escrita.

WHAT IT IS NOT:
  Não é sincronização automática nem rede P2P — é o FORMATO e os gates. Quem transporta o
  pacote (commit, Drive, arquivo) é o usuário/host; quem aprova é o humano (H5).

WHAT IF IT FAILS:
  Stores ausentes exportam vazio (pacote honesto); verify falha fechado; import sem verify
  não existe (verify roda dentro do import). Nunca levanta exceção em uso normal.
"""
import hashlib
import hmac as _hmac
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))

PACK_SCHEMA = "fedpack/1.0"


def _base():
    return os.environ.get("APEX_METHOD_HOME") or os.path.expanduser("~/.apex-method")


def _sha(text):
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def _pack_sha(pack):
    # campos "_*" são decorativos (contagens de exibição) e ficam FORA do canônico assinado
    unsigned = {k: v for k, v in pack.items()
                if k not in ("sha256", "hmac") and not k.startswith("_")}
    return _sha(json.dumps(unsigned, sort_keys=True, ensure_ascii=False))


def _fed_key():
    return os.environ.get("APEX_FED_KEY", "")


def _collect_validated():
    """SOMENTE o que passou pelos gates — a federação nunca propaga hipótese não validada."""
    out = {"learning": [], "vaccines": [], "routines": [], "grants": []}
    try:                                    # learning: apenas PROMOTED (Ω >= 0.72, n >= 3)
        import learning, sqlite3
        s = learning.LearningStore()
        con = sqlite3.connect(s.db_path)
        for r in con.execute("SELECT sha,kind,subject,domain,successes,trials,status,mean,updated "
                             "FROM outcomes WHERE status='PROMOTED'"):
            out["learning"].append(dict(zip(("sha", "kind", "subject", "domain", "successes",
                                             "trials", "status", "mean", "updated"), r)))
        con.close()
    except Exception:
        pass
    try:                                    # vacinas: só as promováveis (>=2 usos, >0.85)
        import code_genetics
        st = code_genetics.durable_store()
        for sig, v in st.vaccines.items():
            if v.get("uses", 0) >= 2 and v["uses"] and (v["successes"] / v["uses"]) > 0.85:
                out["vaccines"].append(dict(v, sig=sig))
    except Exception:
        pass
    try:                                    # rotinas: só as PROMOTED no learning
        import routine_composer, learning
        for r in routine_composer.load_routines():
            if learning.score("routine", r.get("id", ""), "general")["status"] == "PROMOTED":
                out["routines"].append(r)
    except Exception:
        pass
    try:                                    # grants: aprovados e não revogados (equipamento real)
        import agent_registry
        revoked = set()
        for g in agent_registry.load_grants():
            if g.get("revoked"):
                revoked.add((g.get("agent_id"), g.get("skill_id")))
        for g in agent_registry.load_grants():
            if g.get("approved") and not g.get("revoked") \
                    and (g.get("agent_id"), g.get("skill_id")) not in revoked \
                    and (None, g.get("skill_id")) not in revoked:
                out["grants"].append(g)
    except Exception:
        pass
    return out


def _provenance():
    """A PROVA: a(s) cadeia(s) de ledger desta instância, verificáveis elo a elo no destino."""
    try:
        import memory, sqlite3
        con = sqlite3.connect(memory.DB_DEFAULT)
        rows = [dict(zip(("sha", "ts", "kind", "subject", "action", "evidence", "prev_sha",
                          "device"), r))
                for r in con.execute("SELECT sha,ts,kind,subject,action,evidence,prev_sha,"
                                     "COALESCE(device,'') FROM ledger ORDER BY ts ASC")]
        con.close()
        return rows
    except Exception:
        return []


def export_pack(name="knowledge-pack", path=None):
    """Gera o pacote federado assinado. Publique-o via staging/ -> commit, Drive, ou arquivo."""
    try:
        import memory
        device = memory._device_id()
    except Exception:
        device = "unknown"
    payload = {"schema": PACK_SCHEMA, "name": name, "device": device,
               "exported_at": time.time(), "validated": _collect_validated(),
               "provenance": _provenance()}
    payload["sha256"] = _pack_sha(payload)
    if _fed_key():
        payload["hmac"] = _hmac.new(_fed_key().encode(), payload["sha256"].encode(),
                                    hashlib.sha256).hexdigest()
    if path:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=1)
    v = payload["validated"]
    payload["_counts"] = {k: len(v[k]) for k in v}
    return payload


def verify_pack(pack):
    """Falha FECHADO: schema, assinatura SHA-256, HMAC (quando há chave) e a PROCEDÊNCIA —
    cada cadeia de ledger incluída é re-verificada elo a elo (ponteiro + hash de conteúdo)."""
    if pack.get("schema") != PACK_SCHEMA:
        return {"ok": False, "reason": f"schema desconhecido {pack.get('schema')!r}"}
    if _pack_sha(pack) != pack.get("sha256"):
        return {"ok": False, "reason": "assinatura sha256 não confere (pacote adulterado)"}
    if _fed_key():
        want = _hmac.new(_fed_key().encode(), pack["sha256"].encode(), hashlib.sha256).hexdigest()
        if not _hmac.compare_digest(want, pack.get("hmac", "")):
            return {"ok": False, "reason": "HMAC inválido (chave diferente ou pacote adulterado)"}
    try:
        import memory
        chains = {}
        for r in pack.get("provenance", []):
            chains.setdefault(r.get("device", ""), []).append(r)
        for device, ch in chains.items():
            prev = ""
            for r in sorted(ch, key=lambda x: x["ts"]):
                if r.get("prev_sha", "") != prev:
                    return {"ok": False, "reason": f"procedência: ponteiro quebrado (device {device[:8]})"}
                if memory.MemoryStore._ledger_hash(r["ts"], r["kind"], r["subject"], r["action"],
                                                   r["evidence"], r["prev_sha"],
                                                   r.get("device", "")) != r["sha"]:
                    return {"ok": False, "reason": f"procedência: hash de conteúdo não confere (device {device[:8]})"}
                prev = r["sha"]
    except Exception as e:
        return {"ok": False, "reason": f"verificação de procedência indisponível: {str(e)[:60]}"}
    return {"ok": True, "device": pack.get("device", "")[:8],
            "chains": len({r.get('device', '') for r in pack.get('provenance', [])}),
            "signed": bool(pack.get("hmac"))}


def import_pack(pack, approved=False):
    """Instala conhecimento de outra instância. Ordem inegociável: verify (fail-closed) ->
    H5 (approved=True) -> fusão LOCAL-VENCE (só entra o que não existe aqui; reimportar é
    idempotente) -> procedência anexada ao ledger local (cadeias intercaladas íntegras)."""
    v = verify_pack(pack)
    if not v["ok"]:
        return {"status": "REJECTED", "reason": v["reason"]}
    if not approved:
        return {"status": "BLOCKED",
                "reason": "importar conhecimento federado equipa habilidades e muda comportamento "
                          "futuro — exige aprovação humana (H5)"}
    val = pack.get("validated", {})
    out = {"status": "INSTALLED", "from_device": pack.get("device", "")[:8],
           "learning": 0, "vaccines": 0, "routines": 0, "grants": 0, "provenance": 0}
    try:                                    # learning: só (kind,subject,domain) ausente localmente
        import learning, sqlite3
        s = learning.LearningStore()
        con = sqlite3.connect(s.db_path)
        for r in val.get("learning", []):
            if not con.execute("SELECT 1 FROM outcomes WHERE sha=?", (r["sha"],)).fetchone():
                con.execute("INSERT INTO outcomes VALUES(?,?,?,?,?,?,?,?,?)",
                            (r["sha"], r["kind"], r["subject"], r["domain"], r["successes"],
                             r["trials"], r["status"], r["mean"], r["updated"]))
                out["learning"] += 1
        con.commit(); con.close()
    except Exception:
        pass
    try:                                    # vacinas: só sig ausente (o local vence)
        import code_genetics
        st = code_genetics.durable_store()
        for vc in val.get("vaccines", []):
            if vc["sig"] not in st.vaccines:
                st.vaccines[vc["sig"]] = {"fix": vc["fix"], "uses": vc["uses"],
                                          "successes": vc["successes"],
                                          "error": vc.get("error", "")}
                st._persist(vc["sig"])
                out["vaccines"] += 1
    except Exception:
        pass
    try:                                    # rotinas: só id ausente
        import routine_composer
        have = {r.get("id") for r in routine_composer.load_routines()}
        for r in val.get("routines", []):
            if r.get("id") not in have:
                routine_composer.save_routine(r)
                out["routines"] += 1
    except Exception:
        pass
    try:                                    # grants: identidade SEMÂNTICA (sem ts — o save_grant
        import agent_registry               # grava ts novo, e a idempotência exige ignorá-lo)
        def gid(g):
            return (g.get("skill_id"), g.get("agent_id"), bool(g.get("ext")),
                    bool(g.get("revoked")), g.get("source", ""))
        local = {gid(g) for g in agent_registry.load_grants()}
        for g in val.get("grants", []):
            if gid(g) not in local:
                agent_registry.save_grant(g["skill_id"], g.get("agent_id"),
                                          scripts=g.get("scripts"), source=g.get("source", ""),
                                          approved=True, ext=g.get("ext", False))
                out["grants"] += 1
    except Exception:
        pass
    try:                                    # procedência: cadeias do remetente entram intactas
        import memory
        st = memory.MemoryStore()
        before = st.stats()["ledger"]
        st.load_rows({"ledger": pack.get("provenance", [])})
        out["provenance"] = st.stats()["ledger"] - before
        out["ledger_ok_after"] = st.verify_ledger()["ok"]
    except Exception:
        pass
    return out


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    cmd = sys.argv[1] if len(sys.argv) > 1 else "export"
    if cmd == "export":
        out = sys.argv[2] if len(sys.argv) > 2 else "knowledge-pack.fed.json"
        p = export_pack(path=out)
        print(json.dumps({"written": out, "device": p["device"][:8],
                          "counts": p["_counts"], "sha": p["sha256"][:16],
                          "hmac": bool(p.get("hmac"))}, ensure_ascii=False, indent=1))
    elif cmd == "verify" and len(sys.argv) > 2:
        print(json.dumps(verify_pack(json.load(open(sys.argv[2], encoding="utf-8"))),
                         ensure_ascii=False, indent=1))
    elif cmd == "import" and len(sys.argv) > 2:
        print(json.dumps(import_pack(json.load(open(sys.argv[2], encoding="utf-8")),
                                     approved="--approved" in sys.argv),
                         ensure_ascii=False, indent=1))
