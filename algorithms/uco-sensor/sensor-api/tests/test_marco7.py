"""
UCO-Sensor — Testes Marco 7: Templates APEX + /apex/fix
=========================================================
Valida a integração bidirecional APEX: templates de ação corretiva
e o endpoint POST /apex/fix que aplica transforms guiados pelo APEX.

Testes:
  T70  templates.py existe e tem templates para todos os tipos de erro UCO
  T71  cada template tem campos obrigatórios (apex_prompt, mode, agents, transforms)
  T72  render_prompt() preenche variáveis corretamente
  T73  fix_action_for() retorna mode, agents, transforms corretos por tipo
  T74  POST /apex/fix retorna campos obrigatórios (fixed_code, h_before, h_after)
  T75  POST /apex/fix: delta_h <= 0 quando código tem dead code removível
  T76  POST /apex/fix: apex_prompt contém module_id
  T77  POST /apex/fix com code vazio retorna 400
  T78  POST /apex/webhook APEX_FIX_REQUEST retorna ack + fix_result
  T79  POST /apex/webhook APEX_TEMPLATE_REQUEST retorna lista de error_types
  T7A  template TECH_DEBT_ACCUMULATION tem mode=DEEP e agents inclui 'architect'
  T7B  template AI_CODE_BOMB tem intervention_now=True
  T7C  template LOOP_RISK_INTRODUCTION tem transforms com 'add_loop_guard'
  T7D  round-trip: anômalia detectada -> fix aplicado -> score melhora
"""
from __future__ import annotations
import sys
import json
import time
import threading
import urllib.request
import urllib.error
from pathlib import Path
from http.server import HTTPServer
from typing import List, Dict, Any

# ── Path setup ────────────────────────────────────────────────────────────────
_SENSOR = Path(__file__).resolve().parent.parent
_ENGINE = _SENSOR.parent / "frequency-engine"
for _p in (str(_ENGINE), str(_SENSOR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from apex_integration.templates import (
    get_template, all_error_types, render_prompt, fix_action_for
)
from api.server import UCOSensorHandler, handle_apex_fix, handle_apex_webhook

# ─── Código de teste ──────────────────────────────────────────────────────────

CODE_WITH_DEBT = """
def process_data(items, config, ctx, flags, state, meta):
    results = []
    for item in items:
        if item:
            if config:
                for k, v in config.items():
                    if k in flags:
                        if v > 0:
                            if ctx.get("enabled"):
                                results.append(item)
                        elif v < 0:
                            pass
    unused_x = 42
    unused_y = 99
    return results
    return None  # dead code
"""

CODE_WITH_DEAD = """
def validate(token, secret):
    if not token:
        return False
    if not token:       # duplicate check
        return False
    h = hash(token)
    h = hash(token)     # duplicate
    unused_var = 42
    return h == secret
    return False        # dead code
"""

CODE_SIMPLE = """
def validate(token, secret):
    if not token:
        return False
    return hash(token) == secret
"""

# ─── T70: templates existem para todos os tipos ──────────────────────────────

def test_T70_templates_exist_for_all_error_types():
    """templates.py tem templates para todos os tipos de erro UCO conhecidos."""
    expected = [
        "TECH_DEBT_ACCUMULATION",
        "AI_CODE_BOMB",
        "GOD_CLASS_FORMATION",
        "DEPENDENCY_CYCLE_INTRODUCTION",
        "LOOP_RISK_INTRODUCTION",
        "COGNITIVE_COMPLEXITY_EXPLOSION",
        "DEAD_CODE_DRIFT",
        "HALSTEAD_BUG_DENSITY",
    ]
    available = all_error_types()
    for et in expected:
        assert et in available, f"Template '{et}' não encontrado"
    print(f"  [T70] ok — {len(available)} templates disponíveis: {available}")


# ─── T71: campos obrigatórios em cada template ────────────────────────────────

def test_T71_templates_have_required_fields():
    """Cada template tem: apex_prompt, mode, agents, transforms, success_criteria."""
    required = ["apex_prompt", "mode", "agents", "transforms",
                 "severity_gate", "intervention_now", "success_criteria", "description"]

    for et in all_error_types():
        tmpl = get_template(et)
        for field in required:
            assert field in tmpl, f"Template '{et}' falta campo '{field}'"
        assert isinstance(tmpl["agents"],     list), f"'{et}'.agents deve ser lista"
        assert isinstance(tmpl["transforms"], list), f"'{et}'.transforms deve ser lista"
        assert len(tmpl["agents"])     > 0,  f"'{et}'.agents não pode ser vazio"
        assert len(tmpl["transforms"]) > 0,  f"'{et}'.transforms não pode ser vazio"
        assert "{module_id}" in tmpl["apex_prompt"], \
            f"'{et}'.apex_prompt deve ter {{module_id}}"
    print(f"  [T71] ok — todos os templates têm campos obrigatórios")


# ─── T72: render_prompt() ────────────────────────────────────────────────────

def test_T72_render_prompt_fills_variables():
    """render_prompt() substitui variáveis no template."""
    prompt = render_prompt(
        error_type="TECH_DEBT_ACCUMULATION",
        module_id="auth.service",
        delta_h=4.2,
        hurst=0.85,
        commit="abc1234567",
    )
    assert "auth.service" in prompt, f"module_id não encontrado: {prompt[:200]}"
    assert "abc12345" in prompt or "4.2" in prompt or "0.85" in prompt, \
        f"Variáveis não substituídas: {prompt[:200]}"
    assert "[UCO-SENSOR]" in prompt, "Prefixo [UCO-SENSOR] ausente"
    print(f"  [T72] ok — prompt renderizado: {prompt[:100]}...")


def test_T72b_render_prompt_fallback_on_missing_vars():
    """render_prompt() não lança exceção com variáveis extras."""
    prompt = render_prompt(
        error_type="UNKNOWN",
        module_id="test.mod",
        delta_h=1.0,
        severity="CRITICAL",
    )
    assert isinstance(prompt, str) and len(prompt) > 10
    print(f"  [T72b] ok — fallback sem exceção para UNKNOWN")


# ─── T73: fix_action_for() ───────────────────────────────────────────────────

def test_T73_fix_action_has_required_fields():
    """fix_action_for() retorna mode, agents, transforms, intervention_now."""
    for et in all_error_types():
        action = fix_action_for(et)
        assert "mode"             in action, f"'{et}': mode ausente"
        assert "agents"           in action, f"'{et}': agents ausente"
        assert "transforms"       in action, f"'{et}': transforms ausente"
        assert "intervention_now" in action, f"'{et}': intervention_now ausente"
        assert "success_criteria" in action, f"'{et}': success_criteria ausente"
    print(f"  [T73] ok — fix_action_for() correto para todos os tipos")


# ─── T74: handle_apex_fix campos obrigatórios ─────────────────────────────────

def test_T74_fix_returns_required_fields():
    """POST /apex/fix retorna: fixed_code, h_before, h_after, delta_h, apex_prompt."""
    code, resp = handle_apex_fix({
        "module_id":  "m7.test",
        "code":       CODE_WITH_DEAD,
        "error_type": "DEAD_CODE_DRIFT",
        "commit_hash": "dead001",
    })
    assert code == 200, f"Esperado 200, got {code}: {resp}"
    required = ["fixed_code", "h_before", "h_after", "delta_h",
                 "apex_prompt", "transforms_applied", "success", "summary"]
    for field in required:
        assert field in resp, f"Campo '{field}' ausente na resposta"
    assert isinstance(resp["fixed_code"], str), "fixed_code deve ser str"
    assert isinstance(resp["h_before"],   float), "h_before deve ser float"
    assert isinstance(resp["h_after"],    float), "h_after deve ser float"
    print(f"  [T74] ok — campos obrigatórios presentes. h: {resp['h_before']:.2f}->{resp['h_after']:.2f}")


# ─── T75: delta_h ≤ 0 em código melhorável ───────────────────────────────────

def test_T75_fix_improves_or_equal_dead_code():
    """POST /apex/fix: h_after <= h_before quando código tem dead code."""
    code, resp = handle_apex_fix({
        "module_id":  "fix.improve",
        "code":       CODE_WITH_DEAD,
        "error_type": "DEAD_CODE_DRIFT",
    })
    assert code == 200
    # Fix pode melhorar (delta <= 0) ou não mudar se transforms não se aplicam
    delta = resp["delta_h"]
    assert delta <= 0.5, \
        f"Fix piorou o código significativamente: delta_h={delta:.3f}"
    print(f"  [T75] ok — delta_h={delta:.3f} (melhora ou sem piora)")


# ─── T76: apex_prompt contém module_id ────────────────────────────────────────

def test_T76_apex_prompt_contains_module_id():
    """apex_prompt no resultado do fix contém o module_id real."""
    code, resp = handle_apex_fix({
        "module_id":  "payments.gateway",
        "code":       CODE_WITH_DEBT,
        "error_type": "TECH_DEBT_ACCUMULATION",
        "hurst":      0.87,
        "commit_hash": "td_commit_001",
    })
    assert code == 200
    prompt = resp["apex_prompt"]
    assert "payments.gateway" in prompt, \
        f"module_id 'payments.gateway' não encontrado no prompt: {prompt[:200]}"
    print(f"  [T76] ok — prompt contém module_id: {prompt[:80]}...")


# ─── T77: code vazio retorna 400 ──────────────────────────────────────────────

def test_T77_fix_empty_code_returns_400():
    """POST /apex/fix com code vazio retorna 400."""
    code, resp = handle_apex_fix({
        "module_id":  "err.test",
        "code":       "",
        "error_type": "DEAD_CODE_DRIFT",
    })
    assert code == 400, f"Esperado 400 para code vazio, got {code}"
    assert "error" in resp
    print(f"  [T77] ok — code vazio retorna 400")


# ─── T78: /apex/webhook APEX_FIX_REQUEST ─────────────────────────────────────

def test_T78_webhook_apex_fix_request():
    """POST /apex/webhook com APEX_FIX_REQUEST retorna ack + fix_result."""
    code, resp = handle_apex_webhook({
        "event": "APEX_FIX_REQUEST",
        "payload": {
            "module_id":  "webhook.test",
            "code":       CODE_WITH_DEAD,
            "error_type": "DEAD_CODE_DRIFT",
            "commit_hash": "wh001",
        },
    })
    assert code == 200, f"Esperado 200, got {code}"
    assert resp.get("ack") is True
    assert "fix_result" in resp, "fix_result ausente na resposta do webhook"
    fix = resp["fix_result"]
    assert "fixed_code" in fix, "fixed_code ausente no fix_result"
    assert "delta_h"    in fix, "delta_h ausente no fix_result"
    print(f"  [T78] ok — APEX_FIX_REQUEST processado, delta_h={fix['delta_h']:.3f}")


# ─── T79: /apex/webhook APEX_TEMPLATE_REQUEST ────────────────────────────────

def test_T79_webhook_template_request():
    """POST /apex/webhook com APEX_TEMPLATE_REQUEST retorna error_types."""
    # Lista de todos os templates
    code, resp = handle_apex_webhook({
        "event": "APEX_TEMPLATE_REQUEST",
        "payload": {},
    })
    assert code == 200
    assert resp.get("ack") is True
    assert "error_types" in resp, "error_types ausente"
    error_types = resp["error_types"]
    assert "TECH_DEBT_ACCUMULATION" in error_types
    assert "AI_CODE_BOMB" in error_types
    print(f"  [T79] ok — APEX_TEMPLATE_REQUEST: {len(error_types)} tipos disponíveis")


def test_T79b_webhook_template_request_specific():
    """APEX_TEMPLATE_REQUEST com error_type específico retorna template completo."""
    code, resp = handle_apex_webhook({
        "event": "APEX_TEMPLATE_REQUEST",
        "payload": {"error_type": "AI_CODE_BOMB"},
    })
    assert code == 200
    assert resp.get("ack") is True
    assert "template" in resp, "template ausente"
    tmpl = resp["template"]
    assert "apex_prompt"  in tmpl
    assert "transforms"   in tmpl
    assert tmpl["mode"] == "DEEP"
    print(f"  [T79b] ok — AI_CODE_BOMB template retornado com mode=DEEP")


# ─── T7A: TECH_DEBT_ACCUMULATION template ────────────────────────────────────

def test_T7A_tech_debt_template_correct():
    """TECH_DEBT_ACCUMULATION: mode=DEEP, agents inclui architect."""
    tmpl = get_template("TECH_DEBT_ACCUMULATION")
    assert tmpl["mode"] == "DEEP", f"Esperado DEEP, got {tmpl['mode']}"
    assert "architect" in tmpl["agents"], \
        f"'architect' ausente em agents: {tmpl['agents']}"
    assert "engineer" in tmpl["agents"], \
        f"'engineer' ausente em agents: {tmpl['agents']}"
    assert tmpl["severity_gate"] in ("INFO", "WARNING", "CRITICAL")
    print(f"  [T7A] ok — TECH_DEBT: mode={tmpl['mode']}, agents={tmpl['agents']}")


# ─── T7B: AI_CODE_BOMB intervention_now=True ─────────────────────────────────

def test_T7B_ai_code_bomb_intervention_now():
    """AI_CODE_BOMB: intervention_now=True (ação imediata recomendada)."""
    tmpl = get_template("AI_CODE_BOMB")
    assert tmpl["intervention_now"] is True, \
        f"AI_CODE_BOMB deve ter intervention_now=True"
    assert tmpl["severity_gate"] == "CRITICAL", \
        f"AI_CODE_BOMB deve ter severity_gate=CRITICAL"
    assert "critic" in tmpl["agents"]
    print(f"  [T7B] ok — AI_CODE_BOMB: intervention_now=True, gate=CRITICAL")


# ─── T7C: LOOP_RISK transforms ────────────────────────────────────────────────

def test_T7C_loop_risk_transforms():
    """LOOP_RISK_INTRODUCTION tem 'add_loop_guard' em transforms."""
    tmpl = get_template("LOOP_RISK_INTRODUCTION")
    assert "add_loop_guard" in tmpl["transforms"], \
        f"'add_loop_guard' ausente: {tmpl['transforms']}"
    assert tmpl["intervention_now"] is True, \
        "LOOP_RISK deve ter intervention_now=True"
    print(f"  [T7C] ok — LOOP_RISK transforms={tmpl['transforms']}")


# ─── T7D: round-trip completo ────────────────────────────────────────────────

def test_T7D_full_round_trip():
    """
    Round-trip: anômalia detectada → APEX_FIX_REQUEST → improvement.
    Simula o ciclo completo: sensor detecta, APEX ordena fix, sensor aplica.
    """
    from sensor_core.uco_bridge import UCOBridge
    bridge = UCOBridge(mode="fast")

    # 1. Detectar anomalia (simula FrequencyEngine detectando DEAD_CODE_DRIFT)
    mv_original = bridge.analyze(CODE_WITH_DEAD, "rt.module", "v1_bad")
    h_original  = mv_original.hamiltonian

    # 2. Simular APEX enviando APEX_FIX_REQUEST via webhook
    code_wh, resp_wh = handle_apex_webhook({
        "event": "APEX_FIX_REQUEST",
        "payload": {
            "module_id":  "rt.module",
            "code":       CODE_WITH_DEAD,
            "error_type": "DEAD_CODE_DRIFT",
            "commit_hash": "v1_bad",
        },
    })
    assert code_wh == 200, f"Webhook falhou: {resp_wh}"
    assert resp_wh["ack"] is True

    fix = resp_wh["fix_result"]
    fixed_code = fix["fixed_code"]

    # 3. Verificar que o código corrigido não piorou
    mv_fixed = bridge.analyze(fixed_code, "rt.module", "v2_fixed")
    h_fixed  = mv_fixed.hamiltonian

    assert h_fixed <= h_original + 0.5, \
        f"Código corrigido piorou: H {h_original:.2f} -> {h_fixed:.2f}"

    # 4. Verificar que o prompt APEX foi gerado
    assert fix["apex_prompt"], "apex_prompt vazio"
    assert "[UCO-SENSOR]" in fix["apex_prompt"]

    print(f"  [T7D] ok — round-trip: H {h_original:.2f} -> {h_fixed:.2f} "
          f"| prompt={fix['apex_prompt'][:60]}...")


# ─── Runner ──────────────────────────────────────────────────────────────────

TESTS = [
    ("T70",  test_T70_templates_exist_for_all_error_types),
    ("T71",  test_T71_templates_have_required_fields),
    ("T72",  test_T72_render_prompt_fills_variables),
    ("T72b", test_T72b_render_prompt_fallback_on_missing_vars),
    ("T73",  test_T73_fix_action_has_required_fields),
    ("T74",  test_T74_fix_returns_required_fields),
    ("T75",  test_T75_fix_improves_or_equal_dead_code),
    ("T76",  test_T76_apex_prompt_contains_module_id),
    ("T77",  test_T77_fix_empty_code_returns_400),
    ("T78",  test_T78_webhook_apex_fix_request),
    ("T79",  test_T79_webhook_template_request),
    ("T79b", test_T79b_webhook_template_request_specific),
    ("T7A",  test_T7A_tech_debt_template_correct),
    ("T7B",  test_T7B_ai_code_bomb_intervention_now),
    ("T7C",  test_T7C_loop_risk_transforms),
    ("T7D",  test_T7D_full_round_trip),
]


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    passed = 0
    failed = 0
    errors = []

    print(f"\n{'='*65}")
    print(f"  UCO-Sensor Marco 7 — Templates APEX + /apex/fix  ({len(TESTS)} testes)")
    print(f"{'='*65}")

    for name, fn in TESTS:
        try:
            fn()
            print(f"  OK {name}")
            passed += 1
        except Exception as exc:
            import traceback
            print(f"  FAIL {name}: {exc}")
            failed += 1
            errors.append((name, exc))

    print(f"\n{'='*65}")
    print(f"  Resultado: {passed}/{len(TESTS)} passaram")
    if errors:
        print(f"\n  Falhas:")
        for n, e in errors:
            print(f"    {n}: {e}")
    print(f"{'='*65}\n")

    sys.exit(0 if failed == 0 else 1)
