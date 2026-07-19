#!/usr/bin/env python3
"""
rag_index.py — SOLID-STATE node RAG: o índice semântico multidimensional do repositório com
memórias cristalizadas, sync incremental e fusão de estados (a arquitetura do autor).

WHY THIS EXISTS:
  Toda instância nova paga o "imposto de remapeamento": re-ler o repositório para reconstruir
  contexto. Este índice é o ESTADO SÓLIDO que elimina esse imposto: nós vetoriais (IDF global
  char-n-gram) para módulos, catálogos, referências, áreas do repo, CAPACIDADES e — v1.47 —
  CAPÍTULOS/SEÇÕES extraídos do sumário de cada documento, cada nó carregando sua DIMENSÃO
  taxonômica (disciplina → especialização → modo). A busca devolve a visão MACRO: onde o nó
  vive na taxonomia, de quem depende / quem o afeta (matriz de imports + grafo de atração) e a
  seção de spec que o descreve — sem o LLM varrer a base a cada interação.

SOLID-STATE MECHANICS (v1.47, do documento de arquitetura):
  - sync(): gatilho INCREMENTAL — hash de conteúdo por nó; só o que mudou é re-vetorizado
    (com o IDF armazenado; um build() completo refaz o IDF global), o que sumiu é PODADO em
    cascata, e um nó removido cujo vetor case (cosseno >= 0.85) com um nó novo do mesmo tipo
    é tratado como RENOMEIO: vira alias, a identidade se preserva.
  - merge_index(other): fusão de estados divergentes entre instâncias — união endereçada por
    id/hash (o local vence em conflito; aliases se acumulam).
  - overview(): a MEMÓRIA CRISTALIZADA — um bloco DETERMINÍSTICO (sem timestamps) com o mapa
    macro do sistema, feito para ser o PREFIXO ESTÁVEL de prompt (alinhado a prompt-caching:
    prefixo idêntico = prefill em cache = economia de tokens/latência).

WHEN TO USE:
  overview() no INÍCIO de toda sessão (restaura o contexto global sem remapear);
  search("pergunta PT/EN") para localizar + ver impacto; sync() após qualquer edição;
  build() completo após mudanças estruturais grandes (refaz o IDF global).

WHAT IF IT FAILS:
  Índice ausente -> build() na hora. Clone local ausente -> nós de repo-area pulados.
  Motores irmãos ausentes -> busca sem enriquecimento (degrada, nunca levanta exceção).
"""
import hashlib
import json
import math
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))

HERE = os.path.dirname(__file__)
ROOT = os.path.dirname(HERE)
INDEX_PATH = os.path.join(ROOT, "catalog", "rag_index.json")

TOP_TERMS = 48          # sparse vector size per node (bounds the index file)
SUMMARY_CHARS = 480
SECTION_CHARS = 300
ALIAS_COSINE = 0.85     # removed->new same-type similarity that means RENAME, not delete+add
DRIFT_JACCARD = 0.30    # neighborhood overlap below this = SEMANTIC DRIFT (meaning changed)
DOCS = ("SKILL.md", "spec.md", "documentacao.md", "inventario.md", "requirements.txt")


def _sha(text):
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()[:16]


def _docstring(path):
    try:
        text = open(path, encoding="utf-8", errors="replace").read()
        m = re.search(r'"""(.*?)"""', text, re.S)
        return (m.group(1).strip() if m else text[:SUMMARY_CHARS])[:SUMMARY_CHARS]
    except Exception:
        return ""


def _md_body(path):
    try:
        text = open(path, encoding="utf-8", errors="replace").read()
        return re.sub(r"^---.*?---\s*", "", text, count=1, flags=re.S)   # skip frontmatter
    except Exception:
        return ""


def _json_meta(path):
    try:
        doc = json.load(open(path, encoding="utf-8"))
        if isinstance(doc, dict):
            meta = doc.get("_meta", {})
            note = meta.get("note", "") or doc.get("_doc", "")
            keys = ", ".join(list(doc)[:8])
            return f"{note} [keys: {keys}]"[:SUMMARY_CHARS]
        return f"list of {len(doc)} entries; first: {json.dumps(doc[0])[:200]}"[:SUMMARY_CHARS]
    except Exception:
        return ""


def _dim(text):
    """A dimensão taxonômica do nó: disciplina/especialização/modo (facetas canônicas PT/EN).
    Eixos sem sinal ficam de fora — o caminho é tão profundo quanto a evidência permite."""
    try:
        import taxonomy
        c = taxonomy.classify(text)
        parts = [c.get("domain"), c.get("subdomain"), c.get("intent")]
        return "/".join(p for p in parts if p) or "geral"
    except Exception:
        return "geral"


def _slug(title):
    return re.sub(r"[^a-z0-9]+", "-", (title or "").lower()).strip("-")[:60]


def _sections_of(fid, rel_path, body):
    """CAPÍTULOS pelo sumário: cada heading (##/###) vira um nó-folha autônomo, preservando a
    hierarquia (parent). O LLM acha a SEÇÃO certa, não o arquivo inteiro."""
    out = []
    heads = list(re.finditer(r"^(#{2,3})\s+(.+)$", body, re.M))
    for i, m in enumerate(heads):
        title = m.group(2).strip()
        start = m.end()
        end = heads[i + 1].start() if i + 1 < len(heads) else min(len(body), start + 4000)
        excerpt = " ".join(body[start:end].split())[:SECTION_CHARS]
        if not excerpt:
            continue
        out.append({"id": f"{fid}#{_slug(title)}", "type": "section",
                    "path": f"{rel_path}#{_slug(title)}", "parent": fid,
                    "summary": f"{title}: {excerpt}"})
    return out[:40]


# Top-level APEX repo areas (indexed as pointer nodes when a local clone exists).
REPO_AREAS = {
    "agents/": "the 213+ AGENT.md persona files (community + native + cs_*) the spawn contract loads",
    "algorithms/": "41 mined assets: UCO, UCO-Sensor (SAST/SCA/taint), third-party libraries (indexed, not copied)",
    "apex_boot/": "the compiled boot kernel: 111 lazy-load pages + sha8 manifest (module_registry maps them)",
    "skills/": "the 3,784 native APEX skills (apex_native_skills_index.json is the fast index)",
    "integrations/": "23 MCP servers/plugins by domain (engineering, legal, healthcare, science-physics...)",
    "diffs/": "the DIFF packs v00.33-36: evolution rules with FMEA/RPN (diffs_lib.json indexes them)",
    "meta/": "anchors registry + repo-level metadata",
    "tools/": "repo maintenance tooling (roster generator, executor linter, skill forge)",
    "reference-docs/": "long-form reference documentation of the APEX framework",
}


def _collect_nodes():
    nodes = []

    def add(nid, ntype, path, summary, parent=None):
        if summary:
            n = {"id": nid, "type": ntype, "path": path, "summary": summary}
            if parent:
                n["parent"] = parent
            nodes.append(n)
    for f in sorted(os.listdir(os.path.join(ROOT, "scripts"))):
        if f.endswith(".py"):
            add(f"script:{f[:-3]}", "script", f"scripts/{f}",
                _docstring(os.path.join(ROOT, "scripts", f)))
    for f in sorted(os.listdir(os.path.join(ROOT, "catalog"))):
        if f.endswith(".json"):
            add(f"catalog:{f[:-5]}", "catalog", f"catalog/{f}",
                _json_meta(os.path.join(ROOT, "catalog", f)))
    for f in sorted(os.listdir(os.path.join(ROOT, "references"))):
        if f.endswith(".md"):
            body = _md_body(os.path.join(ROOT, "references", f))
            fid = f"reference:{f[:-3]}"
            add(fid, "reference", f"references/{f}", " ".join(body.split())[:SUMMARY_CHARS])
            nodes.extend(_sections_of(fid, f"references/{f}", body))
    for f in DOCS:
        p = os.path.join(ROOT, f)
        if os.path.isfile(p):
            body = _md_body(p)
            fid = f"doc:{f}"
            add(fid, "doc", f, " ".join(body.split())[:SUMMARY_CHARS])
            if f.endswith(".md"):
                nodes.extend(_sections_of(fid, f, body))
    for f in sorted(os.listdir(os.path.join(ROOT, "tests"))):
        if f.endswith(".py"):
            add(f"test:{f[:-3]}", "test", f"tests/{f}",
                _docstring(os.path.join(ROOT, "tests", f)))
    for f in ("apex_llm.yaml", "llm_compat.json"):
        p = os.path.join(ROOT, "meta", f)
        if os.path.isfile(p):
            add(f"meta:{f}", "meta", f"meta/{f}",
                open(p, encoding="utf-8", errors="replace").read()[:SUMMARY_CHARS])
    # as 111 PÁGINAS DO BOOT como nós (v1.48): o registry embarcado dá o purpose (offline-safe);
    # com clone local, o cabeçalho do YAML enriquece o resumo.
    try:
        boot_root = None
        try:
            import repo_bridge
            boot_root = repo_bridge._local_root()
        except Exception:
            pass
        reg = json.load(open(os.path.join(ROOT, "catalog", "module_registry.json"),
                             encoding="utf-8"))
        for mrec in reg:
            mod = mrec.get("module")
            if not mod:
                continue
            rel = f"apex_boot/v00_39_1/pages/{mod}.yaml"
            head = ""
            if boot_root:
                p = os.path.join(boot_root, "apex_boot", "v00_39_1", "pages", f"{mod}.yaml")
                if os.path.isfile(p):
                    head = " ".join(open(p, encoding="utf-8", errors="replace")
                                    .read(900).split())[:220]
            add(f"boot:{mod}", "boot-page", rel,
                f"{mrec.get('purpose', '')} | executor={mrec.get('executor')} "
                f"tier={mrec.get('tier')} status={mrec.get('status')}"
                + (f" | {head}" if head else ""))
    except Exception:
        pass
    # repo-level pointer nodes + reference-docs com SEÇÕES (v1.48; clone local)
    try:
        import repo_bridge
        root = repo_bridge._local_root()
        if root:
            for rel, desc in REPO_AREAS.items():
                if os.path.isdir(os.path.join(root, rel.rstrip("/"))):
                    add(f"repo:{rel.rstrip('/')}", "repo-area", rel, desc)
            rd = os.path.join(root, "reference-docs")
            if os.path.isdir(rd):
                for cur, dks, files in os.walk(rd):
                    dks[:] = [d for d in dks if d not in (".git", "__pycache__")]
                    for f in sorted(files):
                        if not f.endswith(".md"):
                            continue
                        rel_p = os.path.relpath(os.path.join(cur, f), root).replace(os.sep, "/")
                        body = _md_body(os.path.join(cur, f))
                        fid = f"refdoc:{rel_p[len('reference-docs/'):-3]}"
                        add(fid, "refdoc", rel_p, " ".join(body.split())[:SUMMARY_CHARS])
                        nodes.extend(_sections_of(fid, rel_p, body))
    except Exception:
        pass
    # tool-use memory: every mapped CAPABILITY is its own node (how_to resolves commands)
    try:
        import capability_map
        for c in capability_map.load()["capabilities"]:
            add(f"capability:{c['id']}", "capability", c["path"],
                f"{c['name']}: {c['description']} | triggers: {c['triggers']} | "
                f"commands: {' ; '.join(c['commands'][:4])}")
    except Exception:
        pass
    for n in nodes:                                # hash + dimensão taxonômica por nó
        n["hash"] = _sha(n["summary"])
        n["dim"] = _dim(n["summary"])
    return nodes


def build(path=INDEX_PATH):
    """Build COMPLETO: coleta os nós, ajusta UM IDF global sobre todos os resumos, vetoriza e
    cristaliza. Use após mudanças estruturais; para edições pontuais, sync() é mais barato."""
    from _tfidf import CharEmbedder
    nodes = _collect_nodes()
    emb = CharEmbedder().fit([n["summary"] for n in nodes])
    for n in nodes:
        vec = emb.embed(n["summary"])
        top = sorted(vec.items(), key=lambda kv: -abs(kv[1]))[:TOP_TERMS]
        # RENORMALIZE after truncation: top-48 keeps ~28% of a char-ngram vector's mass, so
        # without this, identical texts scored cosine ~0.28 (broke alias detection at 0.85).
        tnorm = math.sqrt(sum(w * w for _g, w in top)) or 1.0
        n["terms"] = {g: round(w / tnorm, 4) for g, w in top}
    doc = {"_meta": {"note": ("SOLID-STATE node RAG: módulos, catálogos, referências, seções "
                              "por sumário, áreas do repo e capacidades — cada nó com hash, "
                              "dimensão taxonômica e vetor sob IDF GLOBAL. sync()=incremental; "
                              "merge_index()=fusão entre instâncias; overview()=memória "
                              "cristalizada (prefixo estável p/ prompt-caching)."),
                     "built_at": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()),
                     "count": len(nodes), "top_terms": TOP_TERMS,
                     "idf": {g: round(v, 4) for g, v in emb.idf.items()}},
           "aliases": {}, "nodes": nodes}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False)
    _CACHE.pop(path, None)
    return {"status": "OK", "path": path, "nodes": len(nodes)}


def rebuild(path=INDEX_PATH):
    return build(path=path)


_CACHE = {}


def load(path=INDEX_PATH):
    if path in _CACHE:
        return _CACHE[path]
    try:
        with open(path, encoding="utf-8") as f:
            doc = json.load(f)
    except Exception:
        build(path=path)
        with open(path, encoding="utf-8") as f:
            doc = json.load(f)
    _CACHE[path] = doc
    return doc


def _cosine_sparse(a, b):
    if len(b) < len(a):
        a, b = b, a
    return sum(v * b.get(t, 0.0) for t, v in a.items())


def sync(path=INDEX_PATH):
    """O GATILHO INCREMENTAL: re-vetoriza SÓ o que mudou (hash), poda o que sumiu (cascata:
    seções caem com o pai), e detecta RENOMEIO (nó removido ~= nó novo, cosseno >= 0.85 ->
    alias, identidade preservada). Usa o IDF armazenado — build() completo refaz o global."""
    doc = load(path)
    idf = doc["_meta"].get("idf", {})
    old = {n["id"]: n for n in doc["nodes"]}
    fresh = _collect_nodes()
    from collections import Counter
    from _tfidf import _char_ngrams

    def embed(summary):
        tf = Counter(_char_ngrams(summary))
        vec = {g: c * idf.get(g, 1.0) for g, c in tf.items()}
        top = sorted(vec.items(), key=lambda kv: -abs(kv[1]))[:TOP_TERMS]
        tnorm = math.sqrt(sum(w * w for _g, w in top)) or 1.0   # renormalized truncated vector
        return {g: round(w / tnorm, 4) for g, w in top}
    unchanged, reembedded, new_nodes, drifted = 0, 0, [], []
    for n in fresh:
        prev = old.pop(n["id"], None)
        if prev is not None and prev.get("hash") == n["hash"]:
            new_nodes.append(prev)
            unchanged += 1
        else:
            n["terms"] = embed(n["summary"])
            # DESVIO SEMÂNTICO (documento do autor): Jaccard entre a vizinhança de termos
            # antiga e a nova. Abaixo do limiar = o SIGNIFICADO mudou (não só o texto) —
            # a dimensão taxonômica já foi recalculada na coleta; o nó é sinalizado e o
            # retorno recomenda attraction_graph.rebuild() para realinhar a topologia.
            if prev is not None and prev.get("terms"):
                a, b = set(prev["terms"]), set(n["terms"])
                jac = len(a & b) / (len(a | b) or 1)
                if jac < DRIFT_JACCARD:
                    drifted.append({"id": n["id"], "jaccard": round(jac, 3),
                                    "dim_before": prev.get("dim"), "dim_after": n.get("dim")})
            new_nodes.append(n)
            reembedded += 1
    # o que restou em `old` sumiu -> alias (renomeio) ou poda em cascata
    aliases = dict(doc.get("aliases", {}))
    added = [n for n in new_nodes if n["id"] not in {i for i in aliases}]
    pruned = []
    for gone_id, gone in old.items():
        target = None
        # fast path: um renomeio SEM edição tem hash idêntico — alias direto, sem cosseno
        for n in added:
            if n["type"] == gone["type"] and n.get("hash") == gone.get("hash") \
                    and n["id"] != gone_id:
                target = n["id"]
                break
        gv = gone.get("terms", {})
        if target is None and gv:
            best, best_s = None, 0.0
            for n in added:
                if n["type"] != gone["type"] or n["id"] == gone_id:
                    continue
                s = _cosine_sparse(gv, n.get("terms", {}))
                if s > best_s:
                    best, best_s = n["id"], s
            if best_s >= ALIAS_COSINE:
                target = best
        if target:
            aliases[gone_id] = target              # renomeio: identidade preservada
        else:
            pruned.append(gone_id)                 # deleção real: poda (seções caem c/ o pai)
    doc = {"_meta": dict(doc["_meta"], count=len(new_nodes),
                         synced_at=time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())),
           "aliases": aliases, "nodes": new_nodes}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False)
    _CACHE[path] = doc
    out = {"status": "OK", "unchanged": unchanged, "reembedded": reembedded,
           "pruned": pruned, "aliases": {k: v for k, v in aliases.items()},
           "drifted": drifted}
    if drifted:
        out["recommend"] = ("desvio semântico detectado — rode attraction_graph.rebuild() "
                            "(e capability_map.rebuild() se ferramentas mudaram) para "
                            "realinhar a topologia à nova semântica")
    return out


def merge_index(other_doc, path=INDEX_PATH):
    """Fusão de estados DIVERGENTES entre instâncias: união endereçada por id — conflito de
    hash mantém o nó LOCAL (a máquina dona do arquivo vence); nós exclusivos do outro entram;
    aliases se acumulam. Determinístico e idempotente."""
    doc = load(path)
    mine = {n["id"]: n for n in doc["nodes"]}
    added = 0
    for n in other_doc.get("nodes", []):
        if n["id"] not in mine:
            mine[n["id"]] = n
            added += 1
    aliases = dict(other_doc.get("aliases", {}))
    aliases.update(doc.get("aliases", {}))         # local wins on conflict
    doc = {"_meta": dict(doc["_meta"], count=len(mine)), "aliases": aliases,
           "nodes": sorted(mine.values(), key=lambda n: n["id"])}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False)
    _CACHE[path] = doc
    return {"status": "OK", "added_from_other": added, "total": len(mine),
            "aliases": len(aliases)}


_DEPS_CACHE = {}


def _dependents(script_name):
    """Quem IMPORTA este módulo (impacto de mudança) — da matriz exata do pipeline_dsm."""
    if not _DEPS_CACHE:
        try:
            import pipeline_dsm
            deps = pipeline_dsm.import_graph()
            rev = {}
            for m, ds in deps.items():
                for d in ds:
                    rev.setdefault(d, []).append(m)
            _DEPS_CACHE.update(rev or {"_": []})
        except Exception:
            _DEPS_CACHE["_"] = []
    return sorted(_DEPS_CACHE.get(script_name, []))


def _enrich(node):
    """A visão MACRO por nó: dimensão taxonômica + quem afeta + vizinhos por atração + pai."""
    out = {"dim": node.get("dim", "geral")}
    if node.get("parent"):
        out["parent"] = node["parent"]
    if node["id"].startswith("script:"):
        dep = _dependents(node["id"].split(":", 1)[1])
        if dep:
            out["affects"] = dep[:6]
    try:
        import attraction_graph
        nb = attraction_graph.neighbors(node["id"], k=3)
        if nb:
            out["attracts"] = [e["id"] for e in nb]
    except Exception:
        pass
    return out


def search(query, k=5, node_type=None, path=INDEX_PATH, macro=True, dim=None):
    """Busca por aproximação (PT/EN) sobre o estado sólido. Cada hit volta com a visão macro:
    dimensão, quem afeta (imports reversos), o que atrai, e o pai (para seções). Aliases
    resolvem: buscar pelo nome antigo encontra o nó renomeado.

    v1.50 (fecha o item 3): `dim` filtra pela MATRIZ TAXONÔMICA — dim="mathematics" restringe
    à disciplina; dim="mathematics/simulation" desce à especialização (match por prefixo do
    caminho disciplina/especialização/modo). É o TagRAG do autor sem custo extra: as tags são
    as dimensões que cada nó já carrega."""
    doc = load(path)
    idf = doc["_meta"].get("idf", {})
    from collections import Counter
    from _tfidf import _char_ngrams
    tf = Counter(_char_ngrams(query))
    qv = {g: c * idf.get(g, 1.0) for g, c in tf.items()}
    norm = math.sqrt(sum(v * v for v in qv.values())) or 1.0
    qv = {g: v / norm for g, v in qv.items()}
    scored = []
    for n in doc["nodes"]:
        if node_type and n["type"] != node_type:
            continue
        if dim and not n.get("dim", "geral").startswith(dim):
            continue
        s = sum(w * qv.get(g, 0.0) for g, w in n["terms"].items())
        if s > 0:
            scored.append((s, n))
    scored.sort(key=lambda x: -x[0])
    out = []
    for s, n in scored[:k]:
        hit = {"id": n["id"], "type": n["type"], "path": n["path"],
               "score": round(s, 4), "summary": n["summary"][:160]}
        if macro:
            hit.update(_enrich(n))
        out.append(hit)
    return out


def resolve(node_id, path=INDEX_PATH):
    """Resolve um id através da tabela de aliases (renomeios preservam identidade)."""
    doc = load(path)
    seen = set()
    while node_id in doc.get("aliases", {}) and node_id not in seen:
        seen.add(node_id)
        node_id = doc["aliases"][node_id]
    return node_id


def overview(path=INDEX_PATH):
    """A MEMÓRIA CRISTALIZADA: o mapa macro DETERMINÍSTICO (sem timestamps — mesmo conteúdo =
    mesmo texto = prefixo cacheável no provedor). Carregue isto PRIMEIRO em toda sessão nova:
    restaura a visão global do sistema sem remapear nada."""
    doc = load(path)
    by_type, by_dim = {}, {}
    for n in doc["nodes"]:
        by_type[n["type"]] = by_type.get(n["type"], 0) + 1
        top = n.get("dim", "geral").split("/")[0]
        by_dim[top] = by_dim.get(top, 0) + 1
    core = []
    try:
        import pipeline_dsm
        d = json.load(open(pipeline_dsm.DSM_PATH, encoding="utf-8"))
        core = [m["module"] for m in d["module_dsm"]["load_bearing"][:5]]
    except Exception:
        pass
    lines = ["=== APEX SOLID-STATE OVERVIEW (memória cristalizada — carregue antes de remapear) ===",
             "nós por tipo: " + ", ".join(f"{t}={c}" for t, c in sorted(by_type.items())),
             "disciplinas: " + ", ".join(f"{d}={c}" for d, c in sorted(by_dim.items(), key=lambda x: -x[1])),
             "núcleo de sustentação (mudou? rode a suíte): " + ", ".join(core),
             "como navegar: rag_index.search('pergunta') -> nó + dimensão + impacto; "
             "capability_map.how_to('como faço X') -> comandos; "
             "attraction_graph.equip_for(need) -> o que se completa",
             "estado durável: swap_store.resume_due() diz se há memória mais nova que esta máquina"]
    return "\n".join(lines)


def solid_prefix(path=INDEX_PATH):
    """A CONVENÇÃO DE PREFIXO ESTÁVEL (v1.50 — alinha o runtime ao prompt caching do provedor):
    o KV-cache real vive no provedor e opera por correspondência EXATA de prefixo, token a
    token. Este helper monta o bloco cristalizado que deve abrir TODO prompt de sessão/spawn,
    SEMPRE na mesma ordem canônica e SEM nada volátil (zero timestamps, zero aleatoriedade):
      1. overview() — o mapa macro determinístico do sistema;
      2. o ambiente estável da máquina (linguagens/libs presentes — muda só quando o ambiente muda);
      3. as constantes de governança (H5, gate, honestidade).
    Conteúdo idêntico ⇒ prefixo idêntico ⇒ prefill em cache ⇒ economia de tokens/latência.
    REGRA DE MONTAGEM: [solid_prefix] + [contexto da tarefa (semi-estável)] + [pergunta volátil
    POR ÚLTIMO]. Qualquer edição no meio do prefixo invalida o cache dali em diante."""
    parts = [overview(path)]
    try:
        import capability_map
        env = capability_map.load()["environment"]
        tools = ",".join(sorted(t for t, ok in env["tools"].items() if ok))
        libs = ",".join(sorted(l for l, ok in env["libraries"].items() if ok))
        parts.append(f"ambiente estável: {env.get('python','?')} | tools: {tools} | libs: {libs}")
    except Exception:
        pass
    parts.append("governança: H5 (nada instala/executa sem aprovação humana) · gate do kernel "
                 "(nenhum passo pulado) · honestidade ([APPROX]/[CONJECTURA_FORMAL] sempre)")
    return "\n".join(parts)


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    if len(sys.argv) > 1 and sys.argv[1] == "prefix":
        print(solid_prefix())
        sys.exit(0)
    if len(sys.argv) > 1 and sys.argv[1] == "build":
        print(json.dumps(build(), indent=1))
    elif len(sys.argv) > 1 and sys.argv[1] == "sync":
        print(json.dumps(sync(), indent=1, ensure_ascii=False))
    elif len(sys.argv) > 1 and sys.argv[1] == "overview":
        print(overview())
    else:
        q = " ".join(sys.argv[1:]) or "como funciona a memória durável entre sessões?"
        for hit in search(q):
            extra = f" dim={hit.get('dim')}" + (f" affects={hit.get('affects')}" if hit.get("affects") else "")
            print(f"{hit['score']:.3f}  {hit['id']:44} {hit['path'][:36]:36}{extra}")
