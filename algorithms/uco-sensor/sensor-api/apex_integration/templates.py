"""
UCO-Sensor — APEX Prompt Templates
=====================================
Templates pré-construídos para cada tipo de anomalia UCO.
Usados pelo agente `engineer` do APEX para guiar ações corretivas.

Cada template contém:
  apex_prompt        — instrução direta para o agente APEX
  mode               — modo de execução APEX (FAST | DEEP | RESEARCH | SCIENTIFIC)
  agents             — lista de agentes APEX recomendados
  transforms         — transforms UCO aplicáveis
  severity_gate      — severidade mínima para acionar
  intervention_now   — se intervenção imediata é recomendada
  description        — descrição humana do problema
  success_criteria   — critério de sucesso pós-fix

Uso:
    from apex_integration.templates import get_template, all_error_types
    tmpl = get_template("TECH_DEBT_ACCUMULATION")
    print(tmpl["apex_prompt"].format(module_id="auth.service", delta_h="+4.2"))
"""
from __future__ import annotations
from typing import Dict, Any, List, Optional


# ─── Templates por tipo de anomalia ──────────────────────────────────────────

_TEMPLATES: Dict[str, Dict[str, Any]] = {

    "TECH_DEBT_ACCUMULATION": {
        "description": (
            "Acúmulo gradual de complexidade em ULF (Ultra Low Frequency) — "
            "Hurst H > 0.75 indica tendência irreversível sem refactoring ativo."
        ),
        "apex_prompt": (
            "[UCO-SENSOR] Módulo `{module_id}` detectou TECH_DEBT_ACCUMULATION. "
            "ΔH={delta_h} | Hurst={hurst:.2f} | Onset: commit {commit}. "
            "Ação: Decompor `{module_id}` em funções menores, extrair responsabilidades, "
            "remover dead code acumulado. Target: ΔH < -3 após refactoring."
        ),
        "mode":            "DEEP",
        "agents":          ["engineer", "critic", "architect"],
        "transforms": [
            "extract_functions",
            "remove_dead_code",
            "simplify_logic",
            "split_class",
        ],
        "severity_gate":   "WARNING",
        "intervention_now": False,
        "success_criteria": "H cai ≥ 3 pontos; CC reduz ≥ 20%; zero dead code",
        "uco_channels":    ["H", "CC", "HB"],
    },

    "AI_CODE_BOMB": {
        "description": (
            "Step function em H e CC — típico de inserção em bloco de código gerado "
            "por AI sem revisão. Onset abrupto em 1-2 commits."
        ),
        "apex_prompt": (
            "[UCO-SENSOR] ALERTA CRÍTICO: `{module_id}` — AI_CODE_BOMB detectado. "
            "ΔH={delta_h} em commit {commit} (step function). "
            "Código AI-generated sem revisão introduzido. "
            "Ação IMEDIATA: revisar commit {commit}, extrair lógica reutilizável, "
            "adicionar testes unitários para cada função introduzida."
        ),
        "mode":            "DEEP",
        "agents":          ["critic", "engineer", "meta_reasoning"],
        "transforms": [
            "extract_functions",
            "add_type_hints",
            "remove_duplicate_blocks",
            "simplify_logic",
        ],
        "severity_gate":   "CRITICAL",
        "intervention_now": True,
        "success_criteria": "H retorna ao baseline pré-commit; CC ≤ 10; zero duplicatas",
        "uco_channels":    ["H", "CC", "DSM"],
    },

    "GOD_CLASS_FORMATION": {
        "description": (
            "Classe acumulando múltiplas responsabilidades — DSM densidade cresce "
            "gradualmente. CC médio alto. Onset lento (MF-ULF)."
        ),
        "apex_prompt": (
            "[UCO-SENSOR] `{module_id}` forma GOD_CLASS. "
            "DSM density={dsm_density:.2f} | CC={cc} | ΔH={delta_h}. "
            "Ação: Identificar responsabilidades distintas e extrair para "
            "classes/módulos separados. Aplicar Single Responsibility Principle."
        ),
        "mode":            "DEEP",
        "agents":          ["architect", "engineer", "critic"],
        "transforms": [
            "split_class",
            "extract_functions",
            "introduce_interface",
            "reduce_dsm_density",
        ],
        "severity_gate":   "WARNING",
        "intervention_now": False,
        "success_criteria": "DSM density < 0.3; cada classe < 200 LOC; CC médio < 8",
        "uco_channels":    ["DSM", "DI", "CC"],
    },

    "DEPENDENCY_CYCLE_INTRODUCTION": {
        "description": (
            "Ciclos de dependência introduzidos — DSM cyclic ratio aumenta. "
            "Acoplamento circular impede testabilidade e manutenção."
        ),
        "apex_prompt": (
            "[UCO-SENSOR] `{module_id}` — DEPENDENCY_CYCLE_INTRODUCTION. "
            "DSM cyclic ratio={dsm_cyclic:.2f} | Onset: commit {commit}. "
            "Ação: Identificar e quebrar ciclos via injeção de dependência ou "
            "extração de interface comum."
        ),
        "mode":            "DEEP",
        "agents":          ["architect", "engineer"],
        "transforms": [
            "break_dependency_cycle",
            "introduce_interface",
            "invert_dependency",
        ],
        "severity_gate":   "WARNING",
        "intervention_now": False,
        "success_criteria": "DSM cyclic ratio = 0; DI < 0.7",
        "uco_channels":    ["DSM_cyclic", "DI"],
    },

    "LOOP_RISK_INTRODUCTION": {
        "description": (
            "ILR (Infinite Loop Risk) sobe abruptamente — while True, recursão "
            "sem base case, ou loop sem guard de timeout introduzido."
        ),
        "apex_prompt": (
            "[UCO-SENSOR] `{module_id}` — LOOP_RISK detectado. "
            "ILR={ilr:.2f} | Onset: commit {commit}. "
            "Ação IMEDIATA: adicionar timeout guard, base case ou limite de iterações "
            "em todos os loops de risco identificados pelo UCO."
        ),
        "mode":            "FAST",
        "agents":          ["engineer", "critic"],
        "transforms": [
            "add_loop_guard",
            "add_timeout",
            "add_iteration_limit",
        ],
        "severity_gate":   "WARNING",
        "intervention_now": True,
        "success_criteria": "ILR = 0 em todos os módulos afetados",
        "uco_channels":    ["ILR"],
    },

    "COGNITIVE_COMPLEXITY_EXPLOSION": {
        "description": (
            "CC (Cyclomatic Complexity) explode em MF/HF — funções com muitos "
            "branches, nesting profundo. Difícil testar e manter."
        ),
        "apex_prompt": (
            "[UCO-SENSOR] `{module_id}` — COGNITIVE_COMPLEXITY_EXPLOSION. "
            "CC={cc} | ΔCC={delta_cc} | ΔH={delta_h}. "
            "Ação: Extrair funções, substituir condicionais por polimorfismo, "
            "reduzir nesting. Target: CC ≤ 10 por função."
        ),
        "mode":            "DEEP",
        "agents":          ["engineer", "architect"],
        "transforms": [
            "extract_functions",
            "simplify_conditionals",
            "reduce_nesting",
            "early_return",
        ],
        "severity_gate":   "WARNING",
        "intervention_now": False,
        "success_criteria": "CC ≤ 10 por função; H reduz ≥ 30%",
        "uco_channels":    ["CC", "H"],
    },

    "DEAD_CODE_DRIFT": {
        "description": (
            "dead_code acumula gradualmente — código nunca executado, "
            "variáveis não usadas, imports desnecessários."
        ),
        "apex_prompt": (
            "[UCO-SENSOR] `{module_id}` — DEAD_CODE_DRIFT. "
            "dead_code={dead} blocos | ΔH={delta_h}. "
            "Ação: Remover todo código morto identificado pelo AST scan do UCO."
        ),
        "mode":            "FAST",
        "agents":          ["engineer"],
        "transforms": [
            "remove_dead_code",
            "remove_unused_imports",
            "remove_unused_variables",
        ],
        "severity_gate":   "INFO",
        "intervention_now": False,
        "success_criteria": "dead_code = 0; H reduz proporcionalmente",
        "uco_channels":    ["SDC"],
    },

    "HALSTEAD_BUG_DENSITY": {
        "description": (
            "Halstead Bug Estimate alto — fórmula E/3000 indica densidade "
            "de bugs elevada. Correlaciona com operadores/operandos únicos."
        ),
        "apex_prompt": (
            "[UCO-SENSOR] `{module_id}` — HALSTEAD_BUG_DENSITY. "
            "halstead_bugs={halstead:.3f} | ΔH={delta_h}. "
            "Ação: Simplificar expressões complexas, extrair lógica repetida, "
            "adicionar testes unitários nas áreas de maior densidade."
        ),
        "mode":            "DEEP",
        "agents":          ["engineer", "critic"],
        "transforms": [
            "simplify_expressions",
            "extract_constants",
            "simplify_logic",
        ],
        "severity_gate":   "WARNING",
        "intervention_now": False,
        "success_criteria": "halstead_bugs < 0.15; cobertura de testes > 80%",
        "uco_channels":    ["HB"],
    },

    # ── Template genérico (fallback) ──────────────────────────────────────────
    "UNKNOWN": {
        "description": "Anomalia UCO não classificada — análise manual recomendada.",
        "apex_prompt": (
            "[UCO-SENSOR] `{module_id}` — anomalia detectada. "
            "Severity={severity} | ΔH={delta_h}. "
            "Ação: Revisar métricas UCO e aplicar transforms recomendados."
        ),
        "mode":            "RESEARCH",
        "agents":          ["researcher", "critic", "engineer"],
        "transforms":      ["simplify_logic", "remove_dead_code"],
        "severity_gate":   "WARNING",
        "intervention_now": False,
        "success_criteria": "UCO Score melhora ≥ 10 pontos",
        "uco_channels":    ["H", "CC"],
    },
}


# ─── API pública ──────────────────────────────────────────────────────────────

def get_template(error_type: str) -> Dict[str, Any]:
    """
    Retorna o template APEX para o tipo de erro dado.
    Fallback para UNKNOWN se não encontrado.
    """
    return _TEMPLATES.get(error_type, _TEMPLATES["UNKNOWN"]).copy()


def all_error_types() -> List[str]:
    """Lista todos os tipos de erro com template (exceto UNKNOWN)."""
    return [k for k in _TEMPLATES if k != "UNKNOWN"]


def render_prompt(
    error_type: str,
    module_id:  str = "unknown.module",
    delta_h:    float = 0.0,
    hurst:      float = 0.0,
    commit:     str   = "unknown",
    cc:         int   = 1,
    delta_cc:   int   = 0,
    dsm_density: float = 0.0,
    dsm_cyclic: float = 0.0,
    ilr:        float = 0.0,
    dead:       int   = 0,
    halstead:   float = 0.0,
    severity:   str   = "WARNING",
    **kwargs,
) -> str:
    """
    Renderiza o apex_prompt do template com os valores reais da análise.

    Args:
        error_type: tipo de erro UCO
        module_id:  identificador do módulo
        delta_h:    variação do Hamiltoniano
        hurst:      expoente de Hurst (persistência)
        commit:     hash do commit de onset
        **kwargs:   campos adicionais passados via .format()

    Returns:
        Prompt formatado pronto para o APEX engineer agent.
    """
    tmpl   = get_template(error_type)
    raw    = tmpl["apex_prompt"]
    sign   = "+" if delta_h >= 0 else ""
    try:
        return raw.format(
            module_id=module_id,
            delta_h=f"{sign}{delta_h:.2f}",
            hurst=hurst,
            commit=commit[:8] if commit else "unknown",
            cc=cc,
            delta_cc=f"{'+' if delta_cc >= 0 else ''}{delta_cc}",
            dsm_density=dsm_density,
            dsm_cyclic=dsm_cyclic,
            ilr=ilr,
            dead=dead,
            halstead=halstead,
            severity=severity,
            **kwargs,
        )
    except KeyError:
        return raw  # retorna template bruto se .format() falhar


def fix_action_for(error_type: str) -> Dict[str, Any]:
    """
    Retorna a ação de fix recomendada para um tipo de erro:
    {mode, agents, transforms, intervention_now, success_criteria}
    """
    tmpl = get_template(error_type)
    return {
        "mode":             tmpl["mode"],
        "agents":           tmpl["agents"],
        "transforms":       tmpl["transforms"],
        "intervention_now": tmpl["intervention_now"],
        "success_criteria": tmpl["success_criteria"],
        "uco_channels":     tmpl.get("uco_channels", []),
    }
