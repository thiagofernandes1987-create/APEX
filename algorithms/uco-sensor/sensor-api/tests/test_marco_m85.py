"""
Marco 85 — M16.1: sinks de deserialização insegura (CWE-502) no taint
=====================================================================
Classe presente no corpus (transformers-style / pickle) que o motor de
taint não modelava. Adicionados sinks pickle/cPickle/marshal/dill/yaml/
torch/joblib `.load`/`.loads`. Validação before/after: um fluxo
`request.data → pickle.loads` dispara; o fix típico (trocar por
`json.loads`) **para de disparar** — o "parou de disparar" fiel da classe.
"""
from __future__ import annotations

from sast.taint_engine import TaintAnalyzer


def _d(src: str) -> dict:
    return TaintAnalyzer().analyze(src).to_dict()


def test_T85_pickle_loads_of_request_is_tainted_sink():
    src = ("from flask import request\nimport pickle\n"
           "def load():\n    blob = request.data\n    return pickle.loads(blob)\n")
    d = _d(src)
    assert d.get("sink_count", 0) >= 1
    assert d.get("taint_path_count", 0) >= 1


def test_T85_yaml_load_of_request_is_sink():
    src = ("from flask import request\nimport yaml\n"
           "def load():\n    return yaml.load(request.data)\n")
    assert _d(src).get("sink_count", 0) >= 1


def test_T85_before_after_pickle_to_json_stops_firing():
    vuln = ("from flask import request\nimport pickle\n"
            "def load():\n    return pickle.loads(request.data)\n")
    fixed = ("from flask import request\nimport json\n"
             "def load():\n    return json.loads(request.data)\n")
    dv, df = _d(vuln), _d(fixed)
    # dispara no vulnerável...
    assert dv.get("taint_path_count", 0) >= 1
    # ...e para no corrigido (json.loads não é sink de deserialização)
    assert df.get("taint_path_count", 0) == 0
    assert df.get("sink_count", 0) == 0


def test_T85_json_loads_is_not_a_deserialization_sink():
    src = ("from flask import request\nimport json\n"
           "def load():\n    return json.loads(request.data)\n")
    assert _d(src).get("sink_count", 0) == 0
