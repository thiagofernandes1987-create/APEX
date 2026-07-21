#!/usr/bin/env python3
"""translation.py — gloss PT→EN determinístico (v1.63): traduzir a ENTRADA antes do dissect.

POR QUE (pedido do autor, baixo custo / alto ROI): o router (TF-IDF) e o match de agentes são
LÉXICOS e enviesados a inglês — uma tarefa em PT some (a fraqueza cross-language da §12). Em vez
de depender só de gatilhos bilíngues espalhados, normalizamos a entrada para um EN-gloss ANTES de
classificar/rotear. Determinístico, stdlib, offline, idempotente para inglês (token desconhecido
passa direto). Não é tradução de máquina — é um GLOSS termo-a-termo dos termos técnicos/de domínio
mais frequentes, exatamente o que o roteamento precisa.

USO:
  to_english("dimensionar viga de concreto e verificar flexão")
    -> ("size beam of concrete and verify bending", changed=True)
  is_probably_pt("build a landing page")  -> False   (no-op para EN)
"""
import re
import unicodedata

# PT -> EN: verbos de intenção + substantivos de domínio de alta frequência. Curado para os
# domínios que o corpus prova relevantes (engenharia, jurídico, finanças, frontend, matemática,
# segurança) + verbos genéricos. Mantido enxuto de propósito: precisão > cobertura.
PT_EN = {
    # verbos / intenção
    "dimensionar": "size", "dimensione": "size", "dimensionamento": "sizing",
    "calcular": "calculate", "calcule": "calculate", "calculo": "calculation",
    "resolver": "solve", "resolva": "solve", "integrar": "integrate", "integre": "integrate",
    "simular": "simulate", "simule": "simulate", "verificar": "verify", "verifique": "verify",
    "auditar": "audit", "audite": "audit", "auditoria": "audit", "revisar": "review",
    "revise": "review", "analisar": "analyze", "analise": "analyze", "otimizar": "optimize",
    "otimize": "optimize", "melhorar": "improve", "melhore": "improve", "criar": "create",
    "crie": "create", "construir": "build", "construa": "build", "desenvolver": "develop",
    "desenvolva": "develop", "implementar": "implement", "implemente": "implement",
    "corrigir": "fix", "corrija": "fix", "ajustar": "adjust", "ajuste": "adjust",
    "pesquisar": "research", "pesquise": "research", "projetar": "design", "projete": "design",
    "estimar": "estimate", "estime": "estimate", "avaliar": "evaluate", "avalie": "evaluate",
    "traduzir": "translate", "classificar": "classify", "prever": "forecast",
    # engenharia / estrutural
    "viga": "beam", "vigas": "beams", "concreto": "concrete", "aco": "steel", "laje": "slab",
    "pilar": "column", "coluna": "column", "fundacao": "foundation", "carga": "load",
    "momento": "moment", "flexao": "bending", "cisalhamento": "shear", "tensao": "stress",
    "armadura": "rebar", "estrutural": "structural", "estrutura": "structure",
    "dimensionamento": "sizing", "esforco": "force", "estaca": "pile", "solo": "soil",
    "recalque": "settlement", "engenharia": "engineering",
    # matematica
    "equacao": "equation", "equacoes": "equations", "derivada": "derivative",
    "integral": "integral", "matriz": "matrix", "oscilador": "oscillator",
    "harmonico": "harmonic", "numerico": "numerical", "convergencia": "convergence",
    "energia": "energy", "conservacao": "conservation",
    # juridico
    "contrato": "contract", "contratos": "contracts", "clausula": "clause",
    "clausulas": "clauses", "abusiva": "abusive", "abusivas": "abusive", "locacao": "lease",
    "aluguel": "rent", "juros": "interest", "mora": "default", "multa": "penalty",
    "conformidade": "compliance", "juridico": "legal", "processo": "lawsuit",
    "peticao": "petition", "advogado": "lawyer", "vencimento": "maturity",
    # financas
    "financeiro": "financial", "financeira": "financial", "avaliacao": "valuation",
    "fluxo": "flow", "caixa": "cash", "investimento": "investment", "risco": "risk",
    "orcamento": "budget", "receita": "revenue", "lucro": "profit", "custo": "cost",
    "imposto": "tax", "carteira": "portfolio", "acao": "stock", "acoes": "stocks",
    # frontend / software
    "pagina": "page", "tela": "screen", "botao": "button", "formulario": "form",
    "interface": "interface", "responsiva": "responsive", "responsivo": "responsive",
    "animacao": "animation", "animacoes": "animations", "transicao": "transition",
    "gradiente": "gradient", "cor": "color", "cores": "colors", "fonte": "font",
    "site": "website", "sistema": "system", "aplicativo": "app", "banco": "database",
    "dados": "data", "consulta": "query", "desempenho": "performance",
    # seguranca
    "seguranca": "security", "vulnerabilidade": "vulnerability", "ameaca": "threat",
    "invasao": "intrusion", "senha": "password", "criptografia": "encryption",
    # conectivos comuns (removidos do gloss, mas listados p/ clareza — passam direto)
}

# marcadores fortes de PT (para o no-op em EN): stopwords/afixos que quase não aparecem em EN
_PT_MARKERS = re.compile(r"\b(que|nao|com|para|uma|dos|das|pelo|pela|como|ção|ções|"
                         r"você|voce|isto|esta|este|seja|então|entao)\b", re.I)


def _fold(text):
    return "".join(c for c in unicodedata.normalize("NFKD", text or "")
                   if not unicodedata.combining(c))


def is_probably_pt(text):
    """Heurística barata: há marcadores de PT? (evita glossar texto já em inglês)."""
    if not isinstance(text, str):
        return False
    folded = _fold(text).lower()
    if _PT_MARKERS.search(text) or _PT_MARKERS.search(folded):
        return True
    # ou: ao menos 2 tokens que são chaves conhecidas do gloss
    toks = re.findall(r"[a-z]+", folded)
    return sum(1 for t in toks if t in PT_EN) >= 2


def to_english(text):
    """Gloss termo-a-termo PT->EN. Retorna (texto_glossado, changed). Idempotente p/ EN:
    tokens desconhecidos passam direto; preserva números, pontuação e a ordem das palavras."""
    if not isinstance(text, str) or not text.strip():
        return (text if isinstance(text, str) else "", False)
    changed = False
    out = []
    # tokeniza preservando separadores para não destruir a frase
    for tok in re.split(r"(\W+)", text):
        low = _fold(tok).lower()
        if low in PT_EN:
            repl = PT_EN[low]
            # preserva capitalização inicial
            out.append(repl.capitalize() if tok[:1].isupper() else repl)
            changed = True
        else:
            out.append(tok)
    return ("".join(out), changed)


def normalize_for_routing(text):
    """O ponto de uso do roteamento: só glossa se parecer PT (no-op barato p/ EN)."""
    if is_probably_pt(text):
        g, changed = to_english(text)
        if changed:
            return g
    return text


if __name__ == "__main__":
    for t in ["dimensionar viga de concreto e verificar flexão no estado limite último",
              "auditar contrato de locação quanto a cláusulas abusivas",
              "build a landing page with animations",
              "valuation de fluxo de caixa e risco de investimento"]:
        g, ch = to_english(t)
        print(f"PT? {is_probably_pt(t)!s:5} changed={ch!s:5} | {t}\n         -> {g}\n")
