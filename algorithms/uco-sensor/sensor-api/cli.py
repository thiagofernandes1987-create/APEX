#!/usr/bin/env python3
"""
UCO-Sensor CLI
==============
Interface de linha de comando para o UCO-Sensor.

Comandos:
  scan          — escaneia snapshot de um repositório local
  scan-github   — clona e escaneia repositórios do GitHub
  git-history   — análise temporal via histórico de commits git
  analyze       — analisa um único arquivo
  serve         — inicia o servidor HTTP da API
  key           — gerencia API keys

Uso:
  uco-sensor scan ./meu-projeto
  uco-sensor scan ./meu-projeto --format json > report.json
  uco-sensor scan ./meu-projeto --format sarif > results.sarif
  uco-sensor git-history ./meu-projeto
  uco-sensor git-history ./meu-projeto --commits 90 --format json
  uco-sensor scan-github thiagofernandes1987-create
  uco-sensor scan-github thiagofernandes1987-create --history 60
  uco-sensor scan-github thiagofernandes1987-create --repos apex,uco-sensor
  uco-sensor scan-github https://github.com/user/repo --format json
  uco-sensor analyze src/auth.py
  uco-sensor serve --port 8080 --auth --apex-url https://apex.example.com
  uco-sensor key create --name ci_pipeline --quota 1000
  uco-sensor key list
  uco-sensor key revoke uco_abc12345
"""
from __future__ import annotations
import sys
import os
import json
import argparse
import time
from pathlib import Path

# Path setup
_CLI_DIR = Path(__file__).resolve().parent
_ENGINE  = _CLI_DIR.parent / "frequency-engine"
for _p in (str(_ENGINE), str(_CLI_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)


# ─── Formatters de output ────────────────────────────────────────────────────

def _print_header():
    print(f"\033[96m╔══════════════════════════════════╗\033[0m")
    print(f"\033[96m║      UCO-Sensor  v0.3.0          ║\033[0m")
    print(f"\033[96m╚══════════════════════════════════╝\033[0m")


def _status_color(status: str) -> str:
    colors = {"CRITICAL": "\033[91m", "WARNING": "\033[93m", "STABLE": "\033[92m"}
    reset  = "\033[0m"
    return f"{colors.get(status, '')}{status}{reset}"


# ─── Comando: scan ───────────────────────────────────────────────────────────

def cmd_scan(args):
    """Escaneia um repositório local."""
    from scan.repo_scanner import RepoScanner
    from sensor_storage.snapshot_store import SnapshotStore

    root = Path(args.path).resolve()
    if not root.exists():
        print(f"\033[91mErro: '{args.path}' não existe.\033[0m", file=sys.stderr)
        sys.exit(1)

    store = None
    if args.db:
        store = SnapshotStore(args.db)

    commit_hash = args.commit or f"scan_{int(time.time())}"

    if args.format == "text" and not args.quiet:
        _print_header()
        print(f"  Escaneando: {root}")
        print(f"  Commit    : {commit_hash}")
        if args.max_files:
            print(f"  Max files : {args.max_files}")
        print()

    scanner = RepoScanner(
        root=str(root),
        commit_hash=commit_hash,
        store=store,
        max_files=args.max_files or 0,
        include_tests=not args.no_tests,
        exclude=args.exclude or [],
        top_n=args.top or 20,
        max_workers=args.workers or 4,
    )

    result = scanner.scan(verbose=(args.format == "text" and not args.quiet))

    # Output
    if args.format == "json":
        print(json.dumps(result.to_dict(), indent=2, default=str))

    elif args.format == "sarif":
        sarif = _result_to_sarif(result)
        print(json.dumps(sarif, indent=2))

    elif args.format == "summary":
        data = result.to_dict()
        print(json.dumps({
            "project_status": data["project_status"],
            "uco_score":      data["uco_score"],
            "files_scanned":  data["files"]["scanned"],
            "critical":       data["status_counts"]["critical"],
            "warning":        data["status_counts"]["warning"],
            "stable":         data["status_counts"]["stable"],
            "top_critical": [
                {"path": f["path"], "hamiltonian": f["metrics"]["hamiltonian"]}
                for f in data["top_critical"][:5]
            ],
        }, indent=2))

    else:  # text
        if not args.quiet:
            print(result.summary(top_n=args.top or 10))

    # Código de saída: 1 se CRITICAL (útil em CI)
    if args.fail_on_critical and result.project_status == "CRITICAL":
        sys.exit(1)
    if args.fail_on_warning and result.project_status in ("WARNING", "CRITICAL"):
        sys.exit(1)


def _result_to_sarif(result) -> dict:
    """Converte ScanResult para SARIF 2.1.0."""
    sarif_results = []
    for fr in result.file_results:
        if fr.status == "STABLE" or not fr.ok:
            continue
        level = "error" if fr.status == "CRITICAL" else "warning"
        m = fr.metrics
        sarif_results.append({
            "ruleId": f"UCO-{fr.status}",
            "level":  level,
            "message": {
                "text": (
                    f"UCO-Sensor {fr.status}: "
                    f"H={m.get('hamiltonian',0):.2f}, "
                    f"CC={m.get('cyclomatic_complexity',0)}, "
                    f"ILR={m.get('infinite_loop_risk',0):.2f}"
                )
            },
            "locations": [{
                "physicalLocation": {
                    "artifactLocation": {"uri": fr.path},
                    "region": {"startLine": 1},
                }
            }],
        })

    return {
        "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json",
        "version": "2.1.0",
        "runs": [{
            "tool": {
                "driver": {
                    "name":    "UCO-Sensor",
                    "version": "0.3.0",
                    "rules": [
                        {"id": "UCO-CRITICAL", "name": "CriticalQualitySignal",
                         "shortDescription": {"text": "UCO critical threshold exceeded"}},
                        {"id": "UCO-WARNING",  "name": "WarningQualitySignal",
                         "shortDescription": {"text": "UCO warning threshold exceeded"}},
                    ],
                }
            },
            "results": sarif_results,
            "properties": {
                "uco_score":      result.uco_score,
                "project_status": result.project_status,
                "commit_hash":    result.commit_hash,
            },
        }],
    }


# ─── Comando: scan-github ────────────────────────────────────────────────────

def _github_api(url: str, token: str | None = None) -> list | dict | None:
    """Faz GET na GitHub API v3 com tratamento de erros e rate-limit."""
    import urllib.request, urllib.error
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "UCO-Sensor/0.3.0"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        if e.code == 403:
            print(f"\033[93m  ⚠  GitHub rate-limit atingido. Use --token para aumentar o limite.\033[0m",
                  file=sys.stderr)
        elif e.code == 404:
            print(f"\033[91m  ✗  Recurso não encontrado: {url}\033[0m", file=sys.stderr)
        else:
            print(f"\033[91m  ✗  GitHub API error {e.code}: {url}\033[0m", file=sys.stderr)
        return None
    except Exception as e:
        print(f"\033[91m  ✗  Erro de rede: {e}\033[0m", file=sys.stderr)
        return None


def _github_list_repos(username: str, token: str | None = None) -> list[dict]:
    """Retorna lista de repos públicos de um usuário GitHub (máx 300)."""
    repos = []
    page  = 1
    while True:
        url  = f"https://api.github.com/users/{username}/repos?per_page=100&sort=updated&page={page}"
        data = _github_api(url, token)
        if not data or not isinstance(data, list):
            break
        repos.extend(data)
        if len(data) < 100:
            break
        page += 1
    return repos


def _github_clone(clone_url: str, dest: Path, token: str | None = None) -> bool:
    """Clona um repositório com --depth=1. Retorna True se OK."""
    import subprocess
    # Injeta token na URL se fornecido (para repos privados)
    if token and clone_url.startswith("https://"):
        clone_url = clone_url.replace("https://", f"https://{token}@", 1)
    try:
        proc = subprocess.run(
            ["git", "clone", "--depth=1", "--quiet", clone_url, str(dest)],
            capture_output=True, text=True, timeout=120,
        )
        return proc.returncode == 0
    except FileNotFoundError:
        print("\033[91m  ✗  'git' não encontrado. Instale o Git e tente novamente.\033[0m",
              file=sys.stderr)
        return False
    except subprocess.TimeoutExpired:
        print(f"\033[93m  ⚠  Timeout ao clonar {clone_url}\033[0m", file=sys.stderr)
        return False


def _print_repo_bar(idx: int, total: int, name: str, score: float | None,
                    status: str | None, elapsed: float) -> None:
    """Imprime uma linha de progresso por repo."""
    bar_w  = 20
    filled = bar_w if score is not None else 0
    bar    = "█" * filled + "░" * (bar_w - filled)
    sc_str = f"{score:5.1f}" if score is not None else "  N/A"
    colors = {"CRITICAL": "\033[91m", "WARNING": "\033[93m", "STABLE": "\033[92m"}
    st_str = f"{colors.get(status,'')}{status or 'ERROR':8}\033[0m" if status else "\033[91mERROR   \033[0m"
    print(f"  [{idx:>2}/{total}] {name:<30} {bar}  Score:{sc_str}  {st_str}  {elapsed:.1f}s")


def cmd_scan_github(args):
    """Clona e escaneia repositórios do GitHub."""
    import tempfile, shutil, urllib.parse
    from scan.repo_scanner import RepoScanner

    target: str = args.target

    # ── Resolver target → lista de (nome, clone_url) ─────────────────────────
    repos_to_scan: list[tuple[str, str]] = []   # (nome, clone_url)

    if target.startswith("https://github.com/"):
        # URL direta de repo
        parts = target.rstrip("/").split("/")
        if len(parts) >= 5:
            repo_name = parts[-1]
            repos_to_scan.append((repo_name, target + ".git" if not target.endswith(".git") else target))
        else:
            # URL de usuário → listar repos
            username = parts[-1]
            _repos = _github_list_repos(username, args.token)
            repos_to_scan = [(r["name"], r["clone_url"]) for r in _repos if not r.get("fork")]
    else:
        # Username direto
        username = target
        _repos = _github_list_repos(username, args.token)
        if _repos is None or len(_repos) == 0:
            print(f"\033[91m  ✗  Nenhum repositório encontrado para '{username}'.\033[0m", file=sys.stderr)
            sys.exit(1)
        repos_to_scan = [(r["name"], r["clone_url"]) for r in _repos if not r.get("fork")]

    # Filtrar por --repos se fornecido
    if args.repos:
        filter_set = {r.strip().lower() for r in args.repos.split(",")}
        repos_to_scan = [(n, u) for n, u in repos_to_scan if n.lower() in filter_set]

    if not repos_to_scan:
        print("\033[91m  ✗  Nenhum repositório para escanear após filtros.\033[0m", file=sys.stderr)
        sys.exit(1)

    total = len(repos_to_scan)

    # ── Header ────────────────────────────────────────────────────────────────
    if args.format == "text":
        _print_header()
        owner = target.split("/")[-1].rstrip(".git") if "github.com" in target else target
        print(f"  GitHub   : @{owner}")
        print(f"  Repos    : {total}")
        print(f"  Formato  : {args.format}")
        if args.token:
            print(f"  Auth     : token ****")
        print()

    # ── Scan de cada repo ─────────────────────────────────────────────────────
    all_results: list[dict] = []
    workdir = Path(tempfile.mkdtemp(prefix="uco_github_"))
    has_critical = False

    try:
        for idx, (repo_name, clone_url) in enumerate(repos_to_scan, 1):
            t0   = time.perf_counter()
            dest = workdir / repo_name

            if args.format == "text":
                print(f"  [{idx:>2}/{total}] Clonando  {repo_name:<30} ", end="", flush=True)

            cloned = _github_clone(clone_url, dest, args.token)
            if not cloned:
                if args.format == "text":
                    print(f"\033[91m✗ falha no clone\033[0m")
                all_results.append({"repo": repo_name, "ok": False, "error": "clone_failed"})
                continue

            # Scan (snapshot ou temporal)
            try:
                history_n = getattr(args, "history", 0) or 0

                if history_n > 0:
                    # Modo temporal — usa GitHistoryScanner
                    from scan.git_history_scanner import GitHistoryScanner
                    hist_scanner = GitHistoryScanner(
                        root=str(dest),
                        n_commits=history_n,
                        min_commits=getattr(args, "min_commits", 5),
                        max_files=args.max_files or 0,
                        max_workers=args.workers or 4,
                        verbose=False,
                    )
                    hist_result = hist_scanner.scan()
                    elapsed     = time.perf_counter() - t0
                    status      = hist_result.project_status

                    entry = {
                        "repo":      repo_name,
                        "clone_url": clone_url,
                        "ok":        True,
                        "mode":      "temporal",
                        "uco_score": max(0.0, 100 - len(hist_result.critical_files)*10
                                        - len(hist_result.warning_files)*3),
                        "status":    status,
                        "files":     hist_result.n_files,
                        "loc":       0,
                        "critical":  len(hist_result.critical_files),
                        "warning":   len(hist_result.warning_files),
                        "stable":    len(hist_result.stable_files),
                        "n_commits": hist_result.n_commits,
                        "avg_H":     0.0,
                        "avg_CC":    0.0,
                        "by_language": {},
                        "top_critical": [
                            {"path": r.path, "pattern": r.primary_error,
                             "hurst": r.hurst, "onset": r.onset_commit,
                             "hamiltonian": 0, "cc": 0}
                            for r in hist_result.critical_files[:5]
                        ],
                        "elapsed_s": round(elapsed, 2),
                    }
                else:
                    # Modo snapshot — RepoScanner padrão
                    scanner = RepoScanner(
                        root=str(dest),
                        commit_hash=f"github_{repo_name}",
                        max_files=args.max_files or 0,
                        include_tests=not args.no_tests,
                        top_n=args.top or 10,
                        max_workers=args.workers or 4,
                    )
                    result  = scanner.scan(verbose=False)
                    elapsed = time.perf_counter() - t0
                    status  = result.project_status

                    entry = {
                        "repo":       repo_name,
                        "clone_url":  clone_url,
                        "ok":         True,
                        "mode":       "snapshot",
                        "uco_score":  result.uco_score,
                        "status":     status,
                        "files":      result.files_scanned,
                        "loc":        result.total_loc,
                        "critical":   result.critical_count,
                        "warning":    result.warning_count,
                        "stable":     result.stable_count,
                        "avg_H":      round(result.avg_hamiltonian, 3),
                        "avg_CC":     round(result.avg_cyclomatic_complexity, 2),
                        "by_language": result.by_language,
                        "top_critical": [
                            {"path": fr.path,
                             "hamiltonian": fr.metrics.get("hamiltonian", 0),
                             "cc": fr.metrics.get("cyclomatic_complexity", 0)}
                            for fr in result.file_results
                            if fr.status == "CRITICAL" and fr.ok
                        ][:5],
                        "elapsed_s":  round(elapsed, 2),
                    }

                if status == "CRITICAL":
                    has_critical = True

                all_results.append(entry)

                if args.format == "text":
                    _print_repo_bar(idx, total, repo_name, result.uco_score,
                                    result.project_status, elapsed)

                # APEX — publica UCO_ANOMALY_DETECTED para repos CRITICAL
                if args.apex_url and result.project_status == "CRITICAL":
                    _apex_notify_repo(args, repo_name, entry)

                # Salvar relatório individual
                if args.output_dir:
                    out_dir = Path(args.output_dir)
                    out_dir.mkdir(parents=True, exist_ok=True)
                    report_file = out_dir / f"{repo_name}_uco.json"
                    report_file.write_text(json.dumps(entry, indent=2, default=str))

            except Exception as e:
                elapsed = time.perf_counter() - t0
                if args.format == "text":
                    print(f"\033[91m✗ erro no scan: {e}\033[0m")
                all_results.append({"repo": repo_name, "ok": False, "error": str(e)})
            finally:
                # Limpa clone após scan para economizar disco
                shutil.rmtree(dest, ignore_errors=True)

    finally:
        shutil.rmtree(workdir, ignore_errors=True)

    # ── Output final ──────────────────────────────────────────────────────────
    if args.format == "json":
        print(json.dumps({"repos": all_results}, indent=2, default=str))

    elif args.format == "sarif":
        print(json.dumps(_github_results_to_sarif(all_results), indent=2))

    elif args.format == "summary":
        ok_repos  = [r for r in all_results if r.get("ok")]
        print(json.dumps({
            "repos_scanned":   len(ok_repos),
            "repos_critical":  sum(1 for r in ok_repos if r["status"] == "CRITICAL"),
            "repos_warning":   sum(1 for r in ok_repos if r["status"] == "WARNING"),
            "repos_stable":    sum(1 for r in ok_repos if r["status"] == "STABLE"),
            "avg_uco_score":   round(sum(r["uco_score"] for r in ok_repos) / max(1, len(ok_repos)), 1),
            "total_files":     sum(r["files"] for r in ok_repos),
            "total_loc":       sum(r["loc"] for r in ok_repos),
            "repos":           [{k: v for k, v in r.items() if k != "top_critical"} for r in ok_repos],
        }, indent=2))

    else:  # text
        _print_github_summary(all_results)

    if args.fail_on_critical and has_critical:
        sys.exit(1)


def _apex_notify_repo(args, repo_name: str, entry: dict) -> None:
    """Envia UCO_ANOMALY_DETECTED para o APEX EventBus para um repo CRITICAL."""
    try:
        from apex_integration.event_bus import ApexEventBus
        bus = ApexEventBus(
            transport="webhook",
            webhook_url=args.apex_url,
            api_key=getattr(args, "apex_key", None) or None,
            severity_gate="CRITICAL",
        )
        event = {
            "event_type":    "UCO_ANOMALY_DETECTED",
            "source":        "uco-sensor-github",
            "repository":    repo_name,
            "severity":      "CRITICAL",
            "uco_score":     entry["uco_score"],
            "avg_H":         entry["avg_H"],
            "critical_files": entry["critical"],
            "top_issues":    entry["top_critical"],
            "suggested_mode": "APEX_REVIEW",
            "timestamp":     time.time(),
        }
        bus.publish(event, severity="CRITICAL")
    except Exception as e:
        print(f"\033[93m  ⚠  APEX notify falhou para {repo_name}: {e}\033[0m", file=sys.stderr)


def _github_results_to_sarif(all_results: list[dict]) -> dict:
    """Converte resultados de scan-github para SARIF 2.1.0."""
    sarif_results = []
    for repo in all_results:
        if not repo.get("ok"):
            continue
        for issue in repo.get("top_critical", []):
            sarif_results.append({
                "ruleId": "UCO-CRITICAL",
                "level":  "error",
                "message": {
                    "text": (
                        f"UCO-Sensor CRITICAL in {repo['repo']}: "
                        f"H={issue['hamiltonian']:.2f}, CC={issue['cc']}"
                    )
                },
                "locations": [{
                    "physicalLocation": {
                        "artifactLocation": {"uri": f"{repo['repo']}/{issue['path']}"},
                        "region": {"startLine": 1},
                    }
                }],
            })
    return {
        "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json",
        "version": "2.1.0",
        "runs": [{
            "tool": {
                "driver": {
                    "name":    "UCO-Sensor",
                    "version": "0.3.0",
                    "rules": [
                        {"id": "UCO-CRITICAL", "name": "CriticalQualitySignal",
                         "shortDescription": {"text": "UCO critical threshold exceeded"}},
                        {"id": "UCO-WARNING",  "name": "WarningQualitySignal",
                         "shortDescription": {"text": "UCO warning threshold exceeded"}},
                    ],
                }
            },
            "results": sarif_results,
        }],
    }


def _print_github_summary(all_results: list[dict]) -> None:
    """Imprime o sumário final do scan-github em modo texto."""
    ok_repos  = [r for r in all_results if r.get("ok")]
    err_repos = [r for r in all_results if not r.get("ok")]
    critical  = [r for r in ok_repos if r["status"] == "CRITICAL"]
    warning   = [r for r in ok_repos if r["status"] == "WARNING"]
    stable    = [r for r in ok_repos if r["status"] == "STABLE"]
    avg_score = sum(r["uco_score"] for r in ok_repos) / max(1, len(ok_repos))
    total_files = sum(r["files"] for r in ok_repos)
    total_loc   = sum(r["loc"] for r in ok_repos)

    print(f"\n{'═'*65}")
    print(f"  UCO-Sensor — GitHub Scan Summary")
    print(f"{'═'*65}")
    print(f"  Repos escaneados : {len(ok_repos)}/{len(all_results)}")
    print(f"  Arquivos         : {total_files:,}")
    print(f"  Linhas de código : {total_loc:,}")
    print(f"  UCO Score médio  : {avg_score:.1f}/100")
    print()

    status_lines = []
    if stable:
        status_lines.append(f"  \033[92m✓ STABLE  ({len(stable):2} repos)\033[0m")
    if warning:
        status_lines.append(f"  \033[93m⚠ WARNING ({len(warning):2} repos)\033[0m")
    if critical:
        status_lines.append(f"  \033[91m✗ CRITICAL({len(critical):2} repos)\033[0m")
    for line in status_lines:
        print(line)

    # Top issues críticos
    all_critical_files = []
    for r in ok_repos:
        for f in r.get("top_critical", []):
            all_critical_files.append((r["repo"], f["path"], f["hamiltonian"], f["cc"]))
    all_critical_files.sort(key=lambda x: x[2], reverse=True)

    if all_critical_files:
        print(f"\n  Top arquivos CRITICAL (H mais alto):")
        print(f"  {'Repo':<25} {'Arquivo':<35} {'H':>8}  {'CC':>5}")
        print(f"  {'─'*76}")
        for repo, path, h, cc in all_critical_files[:10]:
            short_path = path[-33:] if len(path) > 33 else path
            print(f"  \033[91m{repo:<25} {short_path:<35} {h:>8.2f}  {cc:>5}\033[0m")

    # Repos com erro
    if err_repos:
        print(f"\n  \033[93mRepositórios com erro ({len(err_repos)}):\033[0m")
        for r in err_repos:
            print(f"    ✗ {r['repo']}: {r.get('error','?')}")

    # Tabela por repo
    print(f"\n  {'Repo':<30} {'Score':>6}  {'Status':<10} {'Files':>7} {'LOC':>8}  {'Langs'}")
    print(f"  {'─'*75}")
    for r in sorted(ok_repos, key=lambda x: x["uco_score"]):
        colors = {"CRITICAL": "\033[91m", "WARNING": "\033[93m", "STABLE": "\033[92m"}
        c    = colors.get(r["status"], "")
        langs = ", ".join(list(r.get("by_language", {}).keys())[:3])
        print(f"  {c}{r['repo']:<30} {r['uco_score']:>6.1f}  {r['status']:<10} "
              f"{r['files']:>7} {r['loc']:>8}  {langs}\033[0m")

    print(f"{'═'*65}\n")


# ─── Comando: git-history ────────────────────────────────────────────────────

def cmd_git_history(args):
    """Análise temporal de um repositório via histórico de commits git."""
    from scan.git_history_scanner import GitHistoryScanner

    root = Path(args.path).resolve()
    if not root.exists():
        print(f"\033[91mErro: '{args.path}' não existe.\033[0m", file=sys.stderr)
        sys.exit(1)

    if args.format == "text" and not args.quiet:
        _print_header()
        print(f"  Repositório : {root}")
        print(f"  Commits     : últimos {args.commits}")
        print(f"  Min commits : {args.min_commits} por arquivo")
        if args.max_files:
            print(f"  Max files   : {args.max_files}")
        print()

    scanner = GitHistoryScanner(
        root=str(root),
        n_commits=args.commits,
        min_commits=args.min_commits,
        max_files=args.max_files or 0,
        max_workers=args.workers or 4,
        verbose=(args.format == "text" and not args.quiet),
    )

    try:
        result = scanner.scan()
    except RuntimeError as e:
        print(f"\033[91m{e}\033[0m", file=sys.stderr)
        sys.exit(1)

    # Output
    if args.format == "json":
        print(json.dumps(result.to_dict(), indent=2, default=str))

    elif args.format == "summary":
        d = result.to_dict()
        print(json.dumps({
            "project_status": d["project_status"],
            "n_commits":      d["n_commits"],
            "n_files":        d["n_files"],
            "critical":       d["critical"],
            "warning":        d["warning"],
            "top_critical": [
                {"path": r["path"], "pattern": r["primary_error"],
                 "hurst": r["hurst"], "onset_commit": r["onset_commit"]}
                for r in d["file_results"]
                if r["severity"] == "CRITICAL"
            ][:5],
        }, indent=2))

    else:  # text
        if not args.quiet:
            print(result.summary(top_n=args.top or 10))

        # Publicar eventos APEX para CRITICALs
        if args.apex_url and result.critical_files:
            _apex_notify_history(args, result)

    if args.fail_on_critical and result.project_status == "CRITICAL":
        sys.exit(1)


def _apex_notify_history(args, result) -> None:
    """Publica UCO_ANOMALY_DETECTED para cada arquivo CRITICAL encontrado."""
    try:
        from apex_integration.event_bus import ApexEventBus
        bus = ApexEventBus(
            transport="webhook",
            webhook_url=args.apex_url,
            api_key=getattr(args, "apex_key", None) or None,
            severity_gate="CRITICAL",
        )
        for fr in result.critical_files[:10]:
            event = {
                "event_type":    "UCO_ANOMALY_DETECTED",
                "source":        "uco-sensor-git-history",
                "module_id":     fr.path,
                "severity":      "CRITICAL",
                "primary_error": fr.primary_error,
                "hurst":         fr.hurst,
                "self_cure_pct": round(fr.self_cure_probability * 100, 1),
                "onset_commit":  fr.onset_commit,
                "n_commits":     fr.n_commits,
                "suggested_mode": "APEX_REVIEW",
                "timestamp":     time.time(),
            }
            bus.publish(event, severity="CRITICAL")
        print(f"\033[92m  ✓ APEX: {len(result.critical_files)} eventos UCO_ANOMALY_DETECTED publicados\033[0m")
    except Exception as e:
        print(f"\033[93m  ⚠  APEX notify falhou: {e}\033[0m", file=sys.stderr)


# ─── Comando: analyze ────────────────────────────────────────────────────────

def cmd_analyze(args):
    """Analisa um único arquivo."""
    from lang_adapters.registry import get_registry

    path = Path(args.file)
    if not path.exists():
        print(f"\033[91mErro: '{args.file}' não existe.\033[0m", file=sys.stderr)
        sys.exit(1)

    source = path.read_text(encoding="utf-8", errors="replace")
    registry = get_registry()
    mv = registry.analyze(
        source=source,
        file_extension=path.suffix or ".py",
        module_id=str(path),
        commit_hash=args.commit or "local",
    )

    if args.format == "json":
        print(json.dumps({
            "file":     str(path),
            "language": mv.language,
            "status":   mv.status,
            "loc":      getattr(mv, "lines_of_code", 0),
            "metrics": {
                "hamiltonian":            mv.hamiltonian,
                "cyclomatic_complexity":  mv.cyclomatic_complexity,
                "infinite_loop_risk":     mv.infinite_loop_risk,
                "dsm_density":            mv.dsm_density,
                "dsm_cyclic_ratio":       mv.dsm_cyclic_ratio,
                "dependency_instability": mv.dependency_instability,
                "syntactic_dead_code":    mv.syntactic_dead_code,
                "duplicate_block_count":  mv.duplicate_block_count,
                "halstead_bugs":          mv.halstead_bugs,
            },
        }, indent=2))
    else:
        _print_header()
        print(f"  Arquivo  : {path}")
        print(f"  Linguagem: {mv.language}")
        print(f"  Status   : {_status_color(mv.status)}")
        print(f"  LOC      : {getattr(mv, 'lines_of_code', 0)}")
        print()
        print(f"  {'Canal':<30} {'Valor':>10}")
        print(f"  {'─'*42}")
        metrics = [
            ("Hamiltoniano (H)",          mv.hamiltonian),
            ("Cyclomatic Complexity (CC)", mv.cyclomatic_complexity),
            ("Infinite Loop Risk (ILR)",   mv.infinite_loop_risk),
            ("DSM Density",               mv.dsm_density),
            ("Dependency Instability",    mv.dependency_instability),
            ("Dead Code (linhas)",        mv.syntactic_dead_code),
            ("Duplicate Blocks",          mv.duplicate_block_count),
            ("Halstead Bugs",             mv.halstead_bugs),
        ]
        for name, val in metrics:
            print(f"  {name:<30} {val:>10.4f}")

    if args.fail_on_critical and mv.status == "CRITICAL":
        sys.exit(1)


# ─── Comando: serve ──────────────────────────────────────────────────────────

def cmd_serve(args):
    """Inicia o servidor HTTP."""
    from http.server import HTTPServer
    import api.server as srv

    srv._config.db_path      = args.db or ":memory:"
    srv._config.auth_enabled = args.auth
    srv._config.admin_key    = os.environ.get("UCO_ADMIN_KEY", "")
    srv._config.verbose      = args.verbose

    if args.db:
        from sensor_storage.snapshot_store import SnapshotStore
        srv._store = SnapshotStore(args.db)

    if args.apex_url:
        from apex_integration.connector import ApexConnector, set_connector
        connector = ApexConnector.from_config(
            webhook_url=args.apex_url,
            api_key=args.apex_key or None,
            severity_gate="CRITICAL",
            enabled=True,
        )
        set_connector(connector)
        srv._connector = connector

    host = args.host or "0.0.0.0"
    port = args.port or 8080

    server = HTTPServer((host, port), srv.UCOSensorHandler)
    print(f"\033[96m[UCO-Sensor v0.3.0]\033[0m Rodando em http://{host}:{port}")
    print(f"  DB       : {args.db or ':memory:'}")
    print(f"  Auth     : {args.auth}")
    if args.apex_url:
        print(f"  APEX     : {args.apex_url}")
    print(f"  Docs     : http://{host}:{port}/docs")
    print(f"\033[90m  Ctrl+C para parar\033[0m\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n\033[90m[UCO-Sensor] Encerrando...\033[0m")
        server.shutdown()


# ─── Comando: key ────────────────────────────────────────────────────────────

def cmd_key(args):
    """Gerencia API keys."""
    from sensor_storage.snapshot_store import SnapshotStore

    db = args.db or "uco_sensor.db"
    store = SnapshotStore(db)

    if args.key_action == "create":
        key = store.create_key(
            name=args.name or "",
            quota_day=args.quota or 0,
        )
        print(f"\033[92m✓ API Key criada:\033[0m")
        print(f"  Key    : \033[93m{key}\033[0m")
        print(f"  Prefix : {key[:12]}")
        print(f"  Quota  : {args.quota or 'ilimitada'} chamadas/dia")
        print(f"\033[90m  ⚠️  Guarde esta chave com segurança — não será exibida novamente.\033[0m")

    elif args.key_action == "list":
        keys = store.list_keys()
        if not keys:
            print("  Nenhuma API key cadastrada.")
            return
        print(f"  {'Prefix':<15} {'Nome':<20} {'Quota':<8} {'Hoje':<8} {'Total':<10} {'Ativa'}")
        print(f"  {'─'*70}")
        for k in keys:
            active = "\033[92m✓\033[0m" if k["active"] else "\033[91m✗\033[0m"
            quota  = str(k["quota_day"]) if k["quota_day"] else "∞"
            print(f"  {k['key_prefix']:<15} {k['name']:<20} {quota:<8} "
                  f"{k['calls_today']:<8} {k['calls_total']:<10} {active}")

    elif args.key_action == "revoke":
        if not args.prefix:
            print("\033[91mErro: --prefix obrigatório para revogar.\033[0m", file=sys.stderr)
            sys.exit(1)
        ok = store.revoke_key(args.prefix)
        if ok:
            print(f"\033[92m✓ Chave '{args.prefix}' revogada.\033[0m")
        else:
            print(f"\033[91m✗ Chave '{args.prefix}' não encontrada ou já revogada.\033[0m")
            sys.exit(1)


# ─── Parser principal ─────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="uco-sensor",
        description="UCO-Sensor — Spectral Code Quality Analysis",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  uco-sensor scan ./meu-projeto
  uco-sensor scan ./meu-projeto --format json > report.json
  uco-sensor scan ./meu-projeto --format sarif | gh sarif upload /dev/stdin
  uco-sensor scan-github thiagofernandes1987-create
  uco-sensor scan-github thiagofernandes1987-create --repos apex,uco-sensor --format json
  uco-sensor analyze src/auth.py
  uco-sensor serve --port 8080 --db uco.db --auth
  uco-sensor key create --name ci --quota 500
  uco-sensor key list
        """,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # ── scan ──────────────────────────────────────────────────────────────────
    p_scan = sub.add_parser("scan", help="Escaneia um repositório")
    p_scan.add_argument("path",           help="Caminho do repositório/diretório")
    p_scan.add_argument("--commit",       help="Hash do commit")
    p_scan.add_argument("--format",       choices=["text","json","sarif","summary"],
                        default="text",   help="Formato de saída (default: text)")
    p_scan.add_argument("--db",           help="Arquivo SQLite para persistência")
    p_scan.add_argument("--max-files",    type=int, default=0,
                        help="Máximo de arquivos (0=sem limite)")
    p_scan.add_argument("--no-tests",     action="store_true",
                        help="Excluir arquivos de teste")
    p_scan.add_argument("--exclude",      nargs="*", help="Padrões glob de exclusão")
    p_scan.add_argument("--top",          type=int, default=10,
                        help="Top N módulos no relatório")
    p_scan.add_argument("--workers",      type=int, default=4,
                        help="Threads de análise paralela")
    p_scan.add_argument("--fail-on-critical", action="store_true",
                        help="Exit code 1 se houver arquivos CRITICAL (para CI)")
    p_scan.add_argument("--fail-on-warning",  action="store_true",
                        help="Exit code 1 se houver arquivos WARNING ou CRITICAL")
    p_scan.add_argument("--quiet", "-q",  action="store_true",
                        help="Suprimir progresso")
    p_scan.set_defaults(func=cmd_scan)

    # ── scan-github ───────────────────────────────────────────────────────────
    p_gh = sub.add_parser(
        "scan-github",
        help="Clona e escaneia repositórios do GitHub",
        description=(
            "Escaneia repositórios públicos (ou privados com --token) do GitHub.\n\n"
            "Exemplos:\n"
            "  uco-sensor scan-github thiagofernandes1987-create\n"
            "  uco-sensor scan-github thiagofernandes1987-create --repos apex,uco-sensor\n"
            "  uco-sensor scan-github https://github.com/user/repo --format json\n"
            "  uco-sensor scan-github user --format sarif > results.sarif\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p_gh.add_argument("target",
                      help="Username GitHub (ex: thiagofernandes1987-create) ou URL completa de repo")
    p_gh.add_argument("--repos",       help="Filtrar repos específicos (csv: repo1,repo2)")
    p_gh.add_argument("--token",       help="GitHub Personal Access Token (aumenta rate-limit e acessa repos privados)")
    p_gh.add_argument("--format",      choices=["text","json","sarif","summary"],
                      default="text",  help="Formato de saída (default: text)")
    p_gh.add_argument("--output-dir",  help="Salvar relatório JSON por repo neste diretório")
    p_gh.add_argument("--max-files",   type=int, default=0,
                      help="Máximo de arquivos por repo (0=sem limite)")
    p_gh.add_argument("--no-tests",    action="store_true", help="Excluir arquivos de teste")
    p_gh.add_argument("--top",         type=int, default=10, help="Top N arquivos no relatório")
    p_gh.add_argument("--workers",     type=int, default=4,  help="Threads de análise paralela")
    p_gh.add_argument("--history",     type=int, default=0,
                      help="Ativar análise temporal: número de commits por repo (ex: 60). "
                           "0=snapshot apenas (default)")
    p_gh.add_argument("--min-commits", type=int, default=5,
                      help="Mínimo de commits por arquivo para análise temporal (default: 5)")
    p_gh.add_argument("--fail-on-critical", action="store_true",
                      help="Exit code 1 se algum repo for CRITICAL (útil em CI)")
    p_gh.add_argument("--apex-url",    help="URL do APEX event bus (publica UCO_ANOMALY_DETECTED para repos CRITICAL)")
    p_gh.add_argument("--apex-key",    help="API key APEX")
    p_gh.set_defaults(func=cmd_scan_github)

    # ── git-history ───────────────────────────────────────────────────────────
    p_hist = sub.add_parser(
        "git-history",
        help="Análise temporal via histórico de commits git",
        description=(
            "Analisa a evolução temporal do código via histórico git.\n"
            "Detecta QUANDO os padrões foram introduzidos, Hurst (persistência)\n"
            "e probabilidade de auto-recuperação.\n\n"
            "Exemplos:\n"
            "  uco-sensor git-history ./meu-projeto\n"
            "  uco-sensor git-history ./meu-projeto --commits 90\n"
            "  uco-sensor git-history ./meu-projeto --format json > history.json\n"
            "  uco-sensor git-history ./meu-projeto --apex-url https://apex.example.com\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p_hist.add_argument("path",             help="Caminho do repositório git local")
    p_hist.add_argument("--commits",        type=int, default=60,
                        help="Número de commits a analisar (default: 60)")
    p_hist.add_argument("--min-commits",    type=int, default=5,
                        help="Mínimo de commits por arquivo (default: 5)")
    p_hist.add_argument("--format",         choices=["text","json","summary"],
                        default="text",     help="Formato de saída (default: text)")
    p_hist.add_argument("--max-files",      type=int, default=0,
                        help="Máximo de arquivos a analisar (0=sem limite)")
    p_hist.add_argument("--top",            type=int, default=10)
    p_hist.add_argument("--workers",        type=int, default=4)
    p_hist.add_argument("--fail-on-critical", action="store_true")
    p_hist.add_argument("--quiet", "-q",    action="store_true")
    p_hist.add_argument("--apex-url",       help="URL APEX — publica UCO_ANOMALY_DETECTED para arquivos CRITICAL")
    p_hist.add_argument("--apex-key",       help="API key APEX")
    p_hist.set_defaults(func=cmd_git_history)

    # ── analyze ───────────────────────────────────────────────────────────────
    p_analyze = sub.add_parser("analyze", help="Analisa um único arquivo")
    p_analyze.add_argument("file",        help="Arquivo a analisar")
    p_analyze.add_argument("--commit",    help="Hash do commit")
    p_analyze.add_argument("--format",    choices=["text","json"], default="text")
    p_analyze.add_argument("--fail-on-critical", action="store_true")
    p_analyze.set_defaults(func=cmd_analyze)

    # ── serve ─────────────────────────────────────────────────────────────────
    p_serve = sub.add_parser("serve", help="Inicia o servidor HTTP")
    p_serve.add_argument("--host",      default="0.0.0.0")
    p_serve.add_argument("--port",      type=int, default=8080)
    p_serve.add_argument("--db",        help="Arquivo SQLite")
    p_serve.add_argument("--auth",      action="store_true",
                         help="Habilitar validação de API key")
    p_serve.add_argument("--apex-url",  help="URL do APEX event bus")
    p_serve.add_argument("--apex-key",  help="API key APEX")
    p_serve.add_argument("--verbose",   action="store_true")
    p_serve.set_defaults(func=cmd_serve)

    # ── key ───────────────────────────────────────────────────────────────────
    p_key = sub.add_parser("key", help="Gerencia API keys")
    p_key.add_argument("key_action",    choices=["create","list","revoke"])
    p_key.add_argument("--name",        help="Nome da chave (para create)")
    p_key.add_argument("--quota",       type=int, help="Chamadas/dia (para create)")
    p_key.add_argument("--prefix",      help="Prefixo da chave (para revoke)")
    p_key.add_argument("--db",          default="uco_sensor.db")
    p_key.set_defaults(func=cmd_key)

    return parser


def main():
    parser = build_parser()
    args   = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
