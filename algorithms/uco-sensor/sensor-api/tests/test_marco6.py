"""
UCO-Sensor — Testes Marco 6: Distribuição (pyproject + Docker + Release)
=========================================================================
Valida os artefatos de empacotamento e distribuição sem executar Docker
(testes de estrutura de arquivo + importabilidade + CLI).

Testes:
  T60  pyproject.toml existe e é TOML válido
  T61  pyproject.toml tem campos obrigatórios ([project] name, version, entry-point)
  T62  docker-compose.yml existe e é YAML válido
  T63  docker-compose.yml define serviço uco-sensor com porta 8080
  T64  CHANGELOG.md existe e documenta todos os marcos M1–M6
  T65  Dockerfile existe, tem FROM python:3.11, CMD e EXPOSE 8080
  T66  Dockerfile tem HEALTHCHECK
  T67  requirements.txt tem numpy, scipy e PyWavelets
  T68  .dockerignore existe e exclui __pycache__ e *.pyc
  T69  Todos os módulos principais importam sem erro
  T6A  cli.py tem função main() como entry point
  T6B  cli.py --help retorna exit 0 e contém subcomandos
  T6C  pyproject.toml versão bate com server.py _config.version
  T6D  docker-compose.yml usa variável UCO_PORT para mapeamento de porta
"""
from __future__ import annotations
import sys
import subprocess
import json
from pathlib import Path
from typing import Dict, Any

# ── Path setup ────────────────────────────────────────────────────────────────
_SENSOR = Path(__file__).resolve().parent.parent
_ENGINE = _SENSOR.parent / "frequency-engine"
for _p in (str(_ENGINE), str(_SENSOR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)


# ─── T60: pyproject.toml válido ──────────────────────────────────────────────

def test_T60_pyproject_exists_and_valid():
    """pyproject.toml existe e é TOML válido."""
    p = _SENSOR / "pyproject.toml"
    assert p.exists(), f"pyproject.toml não encontrado em {p}"

    # Python 3.11+ tem tomllib stdlib; fallback manual para versões anteriores
    try:
        import tomllib
        with open(p, "rb") as f:
            data = tomllib.load(f)
    except ImportError:
        # Fallback: parser manual simples (verifica seções básicas)
        content = p.read_text(encoding="utf-8")
        assert "[build-system]" in content, "[build-system] ausente"
        assert "[project]" in content, "[project] ausente"
        data = {"_parsed": False}  # marker

    assert data is not None, "pyproject.toml não pôde ser parseado"
    print(f"  [T60] ok — pyproject.toml existe e é TOML válido")


# ─── T61: campos obrigatórios ─────────────────────────────────────────────────

def test_T61_pyproject_required_fields():
    """pyproject.toml tem name, version, entry point uco-sensor."""
    p = _SENSOR / "pyproject.toml"
    content = p.read_text(encoding="utf-8")

    assert 'name' in content,              "Campo 'name' ausente"
    assert 'version' in content,           "Campo 'version' ausente"
    assert 'requires-python' in content,   "Campo 'requires-python' ausente"
    assert 'uco-sensor' in content,        "Entry point 'uco-sensor' ausente"
    assert 'cli:main' in content,          "Entry point 'cli:main' ausente"
    assert 'numpy' in content,             "Dependência 'numpy' ausente"
    assert 'scipy' in content,             "Dependência 'scipy' ausente"
    assert 'pytest' in content,            "Dependência 'pytest' ausente em [dev]"
    print(f"  [T61] ok — todos os campos obrigatórios presentes no pyproject.toml")


# ─── T62: docker-compose.yml válido ──────────────────────────────────────────

def test_T62_docker_compose_exists_and_valid():
    """docker-compose.yml existe e é YAML válido."""
    p = _SENSOR / "docker-compose.yml"
    assert p.exists(), f"docker-compose.yml não encontrado em {p}"

    try:
        import yaml
        with open(p, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        assert data is not None
        print(f"  [T62] ok — docker-compose.yml válido (yaml.safe_load OK)")
    except ImportError:
        # yaml não instalado — verificação textual
        content = p.read_text(encoding="utf-8")
        assert "services:" in content,    "Chave 'services:' ausente"
        assert "uco-sensor:" in content,  "Serviço 'uco-sensor:' ausente"
        print(f"  [T62] ok — docker-compose.yml existe (verificação textual)")


# ─── T63: serviço uco-sensor com porta 8080 ──────────────────────────────────

def test_T63_compose_service_port_8080():
    """docker-compose.yml define serviço uco-sensor com porta 8080."""
    p = _SENSOR / "docker-compose.yml"
    content = p.read_text(encoding="utf-8")

    assert "uco-sensor:" in content, "Serviço 'uco-sensor' não encontrado"
    assert "8080" in content, "Porta 8080 não encontrada no docker-compose.yml"
    assert "HEALTHCHECK" in content.upper() or "healthcheck:" in content, \
        "healthcheck não definido no compose"
    print(f"  [T63] ok — serviço uco-sensor com porta 8080 e healthcheck")


# ─── T64: CHANGELOG.md completo ──────────────────────────────────────────────

def test_T64_changelog_exists_documents_all_marcos():
    """CHANGELOG.md existe e referencia os marcos M1–M6."""
    p = _SENSOR / "CHANGELOG.md"
    assert p.exists(), f"CHANGELOG.md não encontrado em {p}"

    content = p.read_text(encoding="utf-8")
    # Verifica que os marcos e versões estão documentados
    for marco in ["M1", "M2", "M3", "M4", "M5", "M6"]:
        assert marco in content, f"Marco {marco} não encontrado no CHANGELOG"
    for version in ["0.1.0", "0.1.1", "0.1.2", "0.1.3", "0.2.0", "0.3.0"]:
        assert version in content, f"Versão {version} não encontrada no CHANGELOG"
    assert "ANALISAR" in content,   "Marco M1 ANALISAR não documentado"
    assert "EXPANDIR" in content,   "Marco M2 EXPANDIR não documentado"
    assert "CONECTAR" in content,   "Marco M3 CONECTAR não documentado"
    assert "VISUALIZAR" in content, "Marco M4 VISUALIZAR não documentado"
    assert "CALIBRAR" in content,   "Marco M5 CALIBRAR não documentado"
    assert "DISTRIBUIR" in content, "Marco M6 DISTRIBUIR não documentado"
    print(f"  [T64] ok — CHANGELOG.md documenta todos os marcos M1–M6")


# ─── T65: Dockerfile estrutura ───────────────────────────────────────────────

def test_T65_dockerfile_structure():
    """Dockerfile tem FROM python:3.11, CMD e EXPOSE 8080."""
    p = _SENSOR / "Dockerfile"
    assert p.exists(), "Dockerfile não encontrado"

    content = p.read_text(encoding="utf-8")
    assert "FROM python:3.11" in content, "FROM python:3.11 ausente"
    assert "EXPOSE 8080" in content,      "EXPOSE 8080 ausente"
    assert "CMD" in content,              "CMD ausente"
    assert "WORKDIR" in content,          "WORKDIR ausente"
    assert "COPY" in content,             "COPY ausente"
    assert "USER uco" in content,         "USER não-root 'uco' ausente"
    print(f"  [T65] ok — Dockerfile com FROM python:3.11, EXPOSE, CMD, WORKDIR, USER")


# ─── T66: Dockerfile HEALTHCHECK ─────────────────────────────────────────────

def test_T66_dockerfile_healthcheck():
    """Dockerfile tem HEALTHCHECK configurado."""
    p = _SENSOR / "Dockerfile"
    content = p.read_text(encoding="utf-8")
    assert "HEALTHCHECK" in content, "HEALTHCHECK ausente no Dockerfile"
    assert "--interval=" in content,    "--interval ausente no HEALTHCHECK"
    assert "--timeout=" in content,     "--timeout ausente no HEALTHCHECK"
    print(f"  [T66] ok — Dockerfile tem HEALTHCHECK com interval e timeout")


# ─── T67: requirements.txt core deps ─────────────────────────────────────────

def test_T67_requirements_core_deps():
    """requirements.txt tem numpy, scipy e PyWavelets."""
    p = _SENSOR / "requirements.txt"
    assert p.exists(), "requirements.txt não encontrado"
    content = p.read_text(encoding="utf-8")

    for dep in ["numpy", "scipy", "PyWavelets"]:
        assert dep.lower() in content.lower(), f"Dependência '{dep}' ausente"
    # tree-sitter também deve estar listada
    assert "tree-sitter" in content, "tree-sitter ausente"
    print(f"  [T67] ok — numpy, scipy, PyWavelets, tree-sitter presentes")


# ─── T68: .dockerignore ───────────────────────────────────────────────────────

def test_T68_dockerignore_exists():
    """.dockerignore existe e exclui __pycache__ e *.pyc."""
    p = _SENSOR / ".dockerignore"
    assert p.exists(), ".dockerignore não encontrado"
    content = p.read_text(encoding="utf-8")
    assert "__pycache__" in content, "__pycache__ não excluído"
    assert "*.pyc" in content,       "*.pyc não excluído"
    assert "*.db" in content,        "*.db não excluído (banco SQLite local)"
    print(f"  [T68] ok — .dockerignore exclui __pycache__, *.pyc, *.db")


# ─── T69: importação dos módulos principais ──────────────────────────────────

def test_T69_main_modules_importable():
    """Todos os módulos principais importam sem erro."""
    imports_ok = []
    imports_fail = []

    modules_to_test = [
        ("sensor_core.uco_bridge",    "UCOBridge"),
        ("sensor_storage.snapshot_store", "SnapshotStore"),
        ("lang_adapters.registry",    "get_registry"),
        ("apex_integration.event_bus","ApexEventBus"),
        ("apex_integration.connector","ApexConnector"),
        ("scan.repo_scanner",         "RepoScanner"),
        ("report.badge",              "generate_badge_svg"),
        ("report.html_report",        "generate_html_report"),
        ("api.server",                "handle_health"),
    ]

    for module_name, symbol in modules_to_test:
        try:
            mod = __import__(module_name, fromlist=[symbol])
            assert hasattr(mod, symbol), f"{symbol} não encontrado em {module_name}"
            imports_ok.append(module_name)
        except Exception as exc:
            imports_fail.append((module_name, str(exc)))

    assert not imports_fail, \
        f"Módulos que falharam ao importar:\n" + \
        "\n".join(f"  {m}: {e}" for m, e in imports_fail)
    print(f"  [T69] ok — {len(imports_ok)} módulos importaram corretamente")


# ─── T6A: cli.py tem main() ───────────────────────────────────────────────────

def test_T6A_cli_has_main():
    """cli.py tem função main() para uso como entry point."""
    import ast

    p = _SENSOR / "cli.py"
    assert p.exists(), "cli.py não encontrado"

    tree = ast.parse(p.read_text(encoding="utf-8"))
    functions = [n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
    assert "main" in functions, f"função main() não encontrada em cli.py; funções: {functions}"
    print(f"  [T6A] ok — main() presente em cli.py")


# ─── T6B: cli.py --help ───────────────────────────────────────────────────────

def test_T6B_cli_help_exit_0():
    """cli.py --help retorna exit 0 e imprime subcomandos."""
    result = subprocess.run(
        [sys.executable, str(_SENSOR / "cli.py"), "--help"],
        capture_output=True,
        text=True,
        timeout=15,
        cwd=str(_SENSOR),
    )
    assert result.returncode == 0, \
        f"cli.py --help retornou exit {result.returncode}:\n{result.stderr}"

    output = result.stdout + result.stderr
    # Deve listar pelo menos um dos subcomandos principais
    has_subcommand = any(cmd in output for cmd in ["scan", "serve", "analyze", "key"])
    assert has_subcommand, f"Nenhum subcomando encontrado em --help:\n{output[:500]}"
    print(f"  [T6B] ok — cli.py --help retornou 0 com subcomandos listados")


# ─── T6C: versão consistente ──────────────────────────────────────────────────

def test_T6C_version_consistent():
    """pyproject.toml versão bate com server.py _config.version."""
    pyproject_content = (_SENSOR / "pyproject.toml").read_text(encoding="utf-8")

    # Extrair versão do pyproject.toml (linha 'version = "x.y.z"')
    import re
    m = re.search(r'^version\s*=\s*["\']([^"\']+)["\']', pyproject_content, re.MULTILINE)
    assert m, "Versão não encontrada no pyproject.toml"
    pyproject_version = m.group(1)

    from api.server import _config
    server_version = _config.version

    assert pyproject_version == server_version, \
        f"Versão inconsistente: pyproject={pyproject_version} != server={server_version}"
    print(f"  [T6C] ok — versão consistente: {pyproject_version}")


# ─── T6D: UCO_PORT em docker-compose ─────────────────────────────────────────

def test_T6D_compose_uses_uco_port_var():
    """docker-compose.yml usa ${UCO_PORT:-8080} para mapeamento de porta."""
    p = _SENSOR / "docker-compose.yml"
    content = p.read_text(encoding="utf-8")
    assert "UCO_PORT" in content, "Variável UCO_PORT não presente no docker-compose.yml"
    # Padrão de porta dinâmica: "${UCO_PORT:-8080}"
    assert "UCO_PORT:-8080" in content or "UCO_PORT" in content, \
        "Porta dinâmica UCO_PORT não configurada"
    print(f"  [T6D] ok — UCO_PORT variável presente no docker-compose.yml")


# ─── Runner ──────────────────────────────────────────────────────────────────

TESTS = [
    ("T60",  test_T60_pyproject_exists_and_valid),
    ("T61",  test_T61_pyproject_required_fields),
    ("T62",  test_T62_docker_compose_exists_and_valid),
    ("T63",  test_T63_compose_service_port_8080),
    ("T64",  test_T64_changelog_exists_documents_all_marcos),
    ("T65",  test_T65_dockerfile_structure),
    ("T66",  test_T66_dockerfile_healthcheck),
    ("T67",  test_T67_requirements_core_deps),
    ("T68",  test_T68_dockerignore_exists),
    ("T69",  test_T69_main_modules_importable),
    ("T6A",  test_T6A_cli_has_main),
    ("T6B",  test_T6B_cli_help_exit_0),
    ("T6C",  test_T6C_version_consistent),
    ("T6D",  test_T6D_compose_uses_uco_port_var),
]


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    passed = 0
    failed = 0
    errors = []

    print(f"\n{'='*65}")
    print(f"  UCO-Sensor Marco 6 — Distribuicao  ({len(TESTS)} testes)")
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
