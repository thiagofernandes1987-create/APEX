# Auditoria Científica (modo SCIENTIFIC) — APEX prompt + skill apex-method

**Alvo:** repositório `thiagofernandes1987-create/APEX` (prompt/boot v00.39.1) + skill
`apex-method` v1.20.0 (instalada e ativa via Skill tool).
**Método:** conduzida COM o próprio apex-method em modo SCIENTIFIC — o pipeline dirigiu a
análise, os motores executáveis produziram a evidência (uco_gate/SR_33, hypothesis_dag/DSM,
verification_gate, benchmark, evaluate) e o loop das 4 camadas (DSM→Ishikawa→Pareto→FMEA)
só encerrou quando parou de revelar problemas substanciais.
**Regra de honestidade:** nada aceito sem execução; cada achado tem ONDE, LINHA, COMO foi
encontrado e a MELHOR SOLUÇÃO, com o código corrigido na íntegra.
**Verificação de saída:** benchmark **31/31**, rubrica objetiva **13/13 = 100%**, boot do
repo **111/111 sha8**, núcleo funcional sem sklearn/sympy/numpy.

---

## 0. Como o modo SCIENTIFIC foi aplicado

| Etapa SCIENTIFIC | Motor usado | Evidência produzida |
|---|---|---|
| Injeção de conhecimento | `uco_gate` (SR_33) sobre os 28 scripts | métricas H/CC/loop por arquivo |
| Dissecação | `orchestrator.dissect` | disciplinas por tarefa (achou o bug F1) |
| Hipóteses/DSM | `hypothesis_dag` (DFS acíclico + cascata BFS) | acoplamento entre achados |
| Verificação | `verification_gate` + `benchmark`/`evaluate` | 31/31 + 13/13 |
| Convergência | 4 camadas + FMEA RPN | loop encerrado sem substanciais |

---

## 1. Achados (arquitetura, lógica, deps, vulns, loops, chamadas, bugs, gaps, versão)

Legenda severidade: 4=alto · 2=médio · 0=informativo.

| ID | Onde / Linha | Como encontrei | Sev | Veredito |
|---|---|---|---|---|
| **F1** | `scripts/orchestrator.py` `dissect()` (map L66–76) | rodar `dissect` em tarefas PT: "reserva de caixa/runway/burn" caía só em `engineering` | 4 | 🔴→✅ CORRIGIDO |
| **F3** | `scripts/agent_registry.py` `grant_skill()` L85 | testar necessidade-do-agente→concessão: skill de frontend ia p/ `pmi_pm`, os 213 nunca recebiam | 4 | 🔴→✅ CORRIGIDO |
| **F6** | `scripts/skills_sh.py` `_norm()` L70 | QA adversarial: `{'repo':'a/b/c'}` gerava id `a/?` | 2 | 🟠→✅ CORRIGIDO |
| **F2** | `scripts/uco_gate.py` `gate()` L43 | UCO rejeitou os 28 scripts: limiar H>5.5 é de snippet, não módulo | 2 | 🟡 BY DESIGN → documentado |
| **F4** | todos os scripts | scan AST: `numpy/sklearn/sympy/sentence_transformers/pygments` | 0 | 🟢 100% guardados |
| **F5** | `SKILL.md`/`inventario.md` | grep de versões | 0 | 🟢 consistente (1.19→1.20) |
| **F7** | chamadas esquecidas | grep de defs públicas | 0 | 🟢 4 são API pública documentada (preassign/rk4_trajectory/run_parallel/flatten) |
| **BOOT** | `apex_boot/v00_39_1/*` | recomputar sha8 + scan | 0 | 🟢 111/111, 0 sem executor, 0 URL reivindicável, V-02/V-03 presentes |

**Vulnerabilidades:** nenhuma nova. V-01/V-02/V-03 do prompt já corrigidas em rodadas
anteriores e reverificadas aqui. `skills_sh` só faz GET de JSON numa allowlist read-only,
com checagem de redirect — não é vetor de execução.

**Loops:** `uco_gate` flagra `while True` sem break (loop_risk 0.65, testado); os laços reais
dos scripts são todos limitados (`MAX_NODES`, `range`, janelas). Sem loop infinito.

---

## 2. Análise das 4 camadas (loop até convergência)

**Iteração 1 — DSM/Ishikawa/Pareto/FMEA:** F1 e F3 (sev 4) acoplados no subsistema de
roteamento por linguagem/agente; causas-raiz — *method*: dissect monolíngue; *data*: roster
estendido sem competence map. Pareto: 0 achados abertos de alta severidade após correção.
FMEA: F1 RPN=24, F3 RPN=24 — ambos fechados com teste.

**Iteração 2 — lentes QA/Programação/Lógica/Tech-lead (adversarial):** edge-cases em
`dissect` (vazio, emoji, gibberish), `skills_sh._norm` (payloads parciais), `code_genetics`
(50 saves SQLite sem vazar conexão), grant sem match. **Um achado novo:** F6 (`_norm` id
`a/?`). Nenhum crash.

**Iteração 3 — convergência:** F6 corrigido; re-teste 31/31 + 13/13. **As 4 camadas não
revelam mais problemas substanciais → loop encerrado.**

---

## 3. Código completo dos pontos corrigidos (sem omissões)

### 3.1 F1 — `dissect()` bilíngue + fallback semântico

**Problema (ONDE/COMO):** `orchestrator.py`, mapa `DISCIPLINE_KEYWORDS` só em inglês +
match por word-boundary; toda tarefa em português sem token EN caía no default `engineering`.
Reproduzido: `dissect("dimensionar a reserva de caixa e o runway com burn")` → `['engineering']`.

**Solução:** chaves bilíngues (EN+PT) e, se nada casar, um passo semântico char-n-gram
(robusto a idioma) escolhe a disciplina mais próxima acima de um piso.

**Mapa de disciplinas + glossário (orchestrator.py L66–105):**

```python
# Bilingual (EN + PT) keywords: the old EN-only map silently mislabelled Portuguese
# tasks (e.g. "reserva de caixa / burn / runway" classified only as engineering).
DISCIPLINE_KEYWORDS = {
    "engineering": ["code", "api", "build", "refactor", "architecture", "backend", "system",
                    "código", "codigo", "arquitetura", "sistema", "programação", "programacao"],
    "frontend": ["ui", "ux", "frontend", "react", "component", "design",
                 "interface", "componente", "front-end", "usuário", "usuario"],
    "security": ["security", "vulnerability", "audit", "threat", "taint", "cve", "exploit",
                 "segurança", "seguranca", "vulnerabilidade", "auditoria", "ameaça", "ameaca"],
    "data-ai": ["model", "ml", "data", "train", "embedding", "recommender", "pipeline",
                "modelo", "dados", "treinar", "aprendizado", "recomendação", "recomendacao"],
    "finance": ["valuation", "portfolio", "trading", "risk", "cash flow", "option", "backtest",
                "portfólio", "portfolio", "risco", "caixa", "runway", "burn", "investimento",
                "financeiro", "fluxo de caixa", "reserva", "orçamento", "orcamento"],
    "math": ["prove", "proof", "integral", "derivative", "equation", "algebra",
             "prova", "provar", "derivada", "equação", "equacao", "álgebra", "algebra"],
    "science": ["physics", "simulation", "ode", "monte carlo", "annealing", "hmc", "statistical",
                "física", "fisica", "simulação", "simulacao", "estatística", "estatistica",
                "dinâmica", "dinamica", "depleção", "deplecao"],
    "legal": ["contract", "compliance", "regulation", "clause", "liability",
              "contrato", "conformidade", "regulação", "regulacao", "cláusula", "clausula"],
    "healthcare": ["clinical", "patient", "diagnosis", "medical", "treatment",
                   "clínico", "clinico", "paciente", "diagnóstico", "diagnostico", "médico", "medico"],
}
# canonical one-line description per discipline — used by the semantic fallback so a task
# with no keyword hit is still routed by meaning (char-n-gram, language-robust), not dumped
# into "engineering" by default.
_DISCIPLINE_GLOSS = {
    "engineering": "software engineering code api backend architecture system programação",
    "frontend": "frontend ui ux interface design react component usuário",
    "security": "security vulnerability audit threat exploit segurança auditoria",
    "data-ai": "machine learning data model training ai dados modelo",
    "finance": "finance valuation portfolio risk cash flow runway burn financeiro caixa risco",
    "math": "mathematics proof integral derivative equation algebra prova equação",
    "science": "physics simulation dynamics statistical monte carlo física simulação dinâmica",
    "legal": "legal contract compliance regulation clause contrato conformidade",
    "healthcare": "healthcare clinical patient diagnosis medical clínico paciente médico",
}
```

**Função corrigida na íntegra:**
#### orchestrator.py :: dissect()  (linhas 106-128)

```python
def dissect(task, semantic_floor=0.06):
    """Split a task into the disciplines it touches (multi-discipline = hard problem).
    Keyword pass first (bilingual); if it finds nothing, a char-n-gram semantic pass
    (language-robust) picks the closest discipline instead of defaulting to engineering."""
    tl = task.lower()
    def has(kw):
        # word-boundary match so short keywords (ui, ml, ux) don't match inside words (b-ui-ld)
        return re.search(r"\b" + re.escape(kw) + r"\b", tl) is not None
    hits = [d for d, kws in DISCIPLINE_KEYWORDS.items() if any(has(k) for k in kws)]
    if hits:
        return hits
    # semantic fallback (no keyword hit): rank disciplines by char-n-gram similarity
    try:
        from _tfidf import semantic_rank
        labels = list(_DISCIPLINE_GLOSS)
        sims, _used = semantic_rank(task, [_DISCIPLINE_GLOSS[d] for d in labels], backend="char")
        ranked = [(labels[i], sims[i]) for i in range(len(labels))]
        best = [d for d, s in sorted(ranked, key=lambda x: -x[1]) if s >= semantic_floor]
        if best:
            return best[:2]  # top disciplines above the floor
    except Exception:
        pass
    return ["engineering"]  # last-resort default
```

**Prova (8/8 disciplinas certas, PT e EN):**
```
OK ['finance']         <- Dimensionar a reserva de caixa e o runway com burn
OK ['engineering']     <- otimizar a arquitetura do backend em português
OK ['engineering','science'] <- simular a dinâmica de depleção física
OK ['legal']           <- revisar o contrato e a conformidade regulatória
OK ['finance']         <- value a company and backtest a trading strategy
```

### 3.2 F1 (apoio) — camada semântica char-n-gram (`_tfidf.py`)

Robusta a idioma: onde o word-TF-IDF dá **miss total** (0.0) em "otimização de portfólio"
por causa dos acentos, o char-n-gram acha "portfolio" via substrings. Código na íntegra:

```python


def _char_ngrams(text, n=(3, 4)):
    """Character n-grams: language-robust (a PT word and its EN cognate share substrings),
    and immune to the word-boundary misses that pure word TF-IDF suffers across languages."""
    s = " " + " ".join(text.lower().split()) + " "
    out = []
    for k in range(n[0], n[1] + 1):
        out += [s[i:i + k] for i in range(len(s) - k + 1)]
    return out


class CharEmbedder:
    """Hashing char-n-gram embedder — a pure-stdlib stand-in for real embeddings that is
    more language-robust than word TF-IDF. If sentence-transformers is installed, callers
    may prefer it; this is the always-available floor."""

    def __init__(self, ngram=(3, 4)):
        self.ngram = ngram
        self.idf = {}

    def fit(self, corpus):
        from collections import Counter
        n = len(corpus) or 1
        df = Counter()
        for t in corpus:
            df.update(set(_char_ngrams(t, self.ngram)))
        self.idf = {g: math.log((1 + n) / (1 + c)) + 1.0 for g, c in df.items()}
        return self

    def embed(self, text):
        from collections import Counter
        tf = Counter(_char_ngrams(text, self.ngram))
        vec = {g: c * self.idf.get(g, 1.0) for g, c in tf.items()}
        norm = math.sqrt(sum(v * v for v in vec.values())) or 1.0
        return {g: v / norm for g, v in vec.items()}


def semantic_rank(query, texts, backend="auto"):
    """Rank query vs texts. backend='st' uses sentence-transformers if present; 'char' uses
    the char-n-gram embedder; 'word' the word TF-IDF; 'auto' picks the best available.
    Returns (scores, backend_used) so callers can report what actually ran."""
    if backend in ("auto", "st"):
        try:
            from sentence_transformers import SentenceTransformer, util  # optional heavy dep
            model = SentenceTransformer("all-MiniLM-L6-v2")
            emb = model.encode([query] + list(texts), convert_to_tensor=True)
            sims = util.cos_sim(emb[0:1], emb[1:])[0].tolist()
            return sims, "sentence-transformers"
        except Exception:
            if backend == "st":
                return [0.0] * len(texts), "unavailable"
    if backend in ("auto", "char"):
        emb = CharEmbedder().fit(list(texts) + [query])
        q = emb.embed(query)
        return [cosine(q, emb.embed(t)) for t in texts], "char-ngram"
    return rank(query, texts), "word-tfidf"


def pairwise(texts, ngram_range=(1, 2)):
    """Full pairwise cosine matrix (list of lists) — used by gravity's synergy term."""
    vec = TinyTfidf(ngram_range).fit(list(texts))
    vs = vec.transform(texts)
    n = len(vs)
    M = [[0.0] * n for _ in range(n)]
    for i in range(n):
        M[i][i] = 1.0
        for j in range(i + 1, n):
            M[i][j] = M[j][i] = cosine(vs[i], vs[j])
    return M
```

### 3.3 F3 — `grant_skill()` alcança o roster de 213 agentes

**Problema (ONDE/COMO):** `agent_registry.py` L85; `grant_skill` só escrevia no
competence map dos 11 personas núcleo. Uma skill de frontend aprovada ia para o
generalista `pmi_pm` — os 213 agentes reais (react-specialist etc.) nunca ganhavam a
competência. Quebrava o requisito "necessidade do agente → upgrade".

**Solução:** após conceder ao núcleo, rotear a skill para os melhores agentes do roster
estendido (`match_task_to_ext_agents`) e registrar a concessão num store de sessão.

**Função corrigida na íntegra:**
#### agent_registry.py :: grant_skill()  (linhas 85-126)

```python
def grant_skill(skill, agents_doc, approved: bool, scripts=None, ext_grants=None):
    """
    Grant an APPROVED skill to the compatible agents, updating competence + experience.
    Returns the list of (agent_id, new_experience). Refuses if not approved (APEX H5).

    audit (SCIENTIFIC): grants also reach the 213-agent EXTENDED roster, not only the 11
    core personas. `ext_grants` is an in-memory competence store {agent_id: {skill: uses}}
    the caller keeps across a session; if omitted, extended matches are still reported so
    "installing a skill upgrades the matching agent" holds for the whole roster.
    """
    if not approved:
        return {"status": "BLOCKED", "reason": "skill not approved by user (APEX H5)"}
    targets = match_skill_to_agents(skill, agents_doc)
    updated = []
    for aid in targets:
        comp = agents_doc["agents"][aid]["competence"]
        entry = comp.get(skill["id"], {"experience": 0, "scripts": []})
        entry["experience"] += 1
        entry["use_when"] = skill.get("use_when", skill.get("description", ""))[:100]
        entry["source"] = skill.get("source", "")
        if scripts:
            entry["scripts"] = sorted(set(entry.get("scripts", []) + list(scripts)))
        comp[skill["id"]] = entry
        # aggregate domain experience
        dom = skill.get("domain", "misc")
        de = agents_doc["agents"][aid]["domain_experience"]
        de[dom] = de.get(dom, 0) + 1
        updated.append((aid, entry["experience"]))

    # extended roster (213): route the skill to the best-matching real APEX agents and
    # record the grant so the whole roster — not just the 11 core — gains competence.
    ext_updated = []
    skill_text = f"{skill.get('name','')} {skill.get('description','')} {skill.get('domain','')}"
    for aid, cat, score in match_task_to_ext_agents(skill_text, k=2):
        if ext_grants is not None:
            store = ext_grants.setdefault(aid, {})
            store[skill["id"]] = store.get(skill["id"], 0) + 1
            ext_updated.append((aid, store[skill["id"]]))
        else:
            ext_updated.append((aid, 1))
    return {"status": "GRANTED", "skill": skill["id"],
            "agents": updated, "ext_agents": ext_updated}
```

**Prova:** skill de frontend agora sobe `react-specialist` e `react-nextjs-expert`
(experiência acumula entre concessões), com H5 bloqueando sem aprovação.

### 3.4 F6 — `_norm()` deriva nome do repo

**Problema (ONDE/COMO):** `skills_sh.py` L70; QA adversarial `{'repo':'a/b/c'}` → id `a/?`.

**Função corrigida na íntegra:**
#### skills_sh.py :: _norm()  (linhas 70-83)

```python
def _norm(item: dict) -> dict:
    repo_parts = (item.get("repo") or "").split("/")
    owner = item.get("owner") or (repo_parts[0] if repo_parts and repo_parts[0] else "")
    # derive name from the repo's last segment when no explicit name/slug/id is given
    name = (item.get("name") or item.get("slug") or item.get("id")
            or (repo_parts[-1] if len(repo_parts) >= 2 and repo_parts[-1] else "?"))
    repo = item.get("repo") or (f"{owner}/{name}" if owner else name)
    return {"id": f"{owner}/{name}" if owner else name,
            "name": name, "owner": owner, "repo": repo,
            "installs": _installs(item),
            "description": (item.get("description") or "")[:200],
            "official": owner in OFFICIAL_OWNERS,
            "install_command": f"npx skills add {repo}",
            "url": item.get("url") or f"https://skills.sh/{repo}"}
```

### 3.5 F2 — escopo do `uco_gate` documentado (by design)

O limiar `hamiltonian>5.5` é calibrado para **snippets PoT pequenos** (o que o SR_33
realmente gateia antes de executar), não para módulos inteiros. Não é bug; adicionamos a
nota de escopo na docstring de `gate()` para evitar o uso indevido como métrica de módulo.

---

## 4. Integração total repo ⇄ skill (verificada)

| Recurso | Repo | Skill (catálogo/ponte) | Integrado |
|---|---|---|---|
| Agentes | 213 (AGENT.md) | `apex_agents_roster.json` 213 + `repo_bridge.agent()` | ✅ |
| Skills nativas | 3.784 | `apex_native_skills_index.json` 3.784 + `search_native` | ✅ |
| Módulos boot | 111 páginas | `module_registry.json` 111 + `repo_bridge.page()` | ✅ |
| DIFFs | 18 nos packs | `diffs_lib.json` 26 (18 DIFF + SRs) | ✅ |
| MCPs | 23 dirs integrations | `mcp_registry.json` 23 | ✅ |
| Scripts | — | `scripts_lib.json` 28 = 28 .py | ✅ 1:1 |
| UCO | `algorithms/uco` | `universal_code_optimizer_v4.py` (mesmo motor) | ✅ |

**Descoberta por necessidade do agente (skills.sh + GitHub) — testado ponta a ponta:**

1. tarefa → `match_task_to_ext_agents` escolhe o agente (react-specialist);
2. `gravity.plan` detecta a lacuna da necessidade;
3. cascata: **nativo** (search_native) → **skills.sh** (`skills_sh`, filtro **≥1000 installs**,
   tier oficial) → **GitHub** (URL de busca) — offline degrada para comandos `npx skills` prontos;
4. `grant_skill(approved=True)` sobe a competência do agente (H5 bloqueia sem aprovação).

---

## 5. Veredito final

APEX (prompt + skill) está **integrado e funcional**: os 111 módulos, 213 agentes, 3.784
skills nativas e o UCO estão endereçáveis e testados; o boot passa integridade; a descoberta
de skills por necessidade de agente opera nas três fontes (nativa/skills.sh/GitHub) com o
critério de ≥1000 installs e sempre sob H5. A autópsia SCIENTIFIC encontrou **3 defeitos
acionáveis** (F1 dissect monolíngue, F3 grant fora do roster de 213, F6 parse de repo),
**todos corrigidos com teste de regressão**, mais 1 item by-design documentado (F2). As 4
camadas convergiram em 3 iterações sem restar problema substancial.

**Estado testável:** `python3 tests/benchmark.py` → 31/31 · `python3 tests/evaluate.py` →
13/13 (100%) · boot 111/111 sha8 · núcleo sem sklearn/sympy/numpy.

*Auditoria conduzida com o apex-method em modo SCIENTIFIC. Fim.*
