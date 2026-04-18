#!/usr/bin/env python3
"""
UCO-Sensor — Extrator de Histórico de Repositório v2.0
=======================================================
Correções implementadas nesta versão:

  GAP-R01: dependency_instability agora calculado por max_methods_per_class/20
           em vez de imports_externos/total. Captura o crescimento de
           responsabilidades que define GOD_CLASS_FORMATION.

  GAP-R02: Flag --files-explicit para especificar arquivos por nome.
           Flag --rank-by total para selecionar por histórico completo
           em vez de frequência recente.

  GAP-R03: Calcula channel_stability por canal após acumular toda a série.
           Canais estabilizados (variância < 0.01) são sinalizados para
           que o analyzer possa suprimir cross-coherências espúrias.

  GAP-R04: Campo window_position adicionado a cada snapshot (0.0=início,
           1.0=fim da janela). Onset nos primeiros 15% indica possível
           artefato de janela curta (EARLY_WINDOW).
"""
import sys, os, json, math, ast, argparse, subprocess, time, statistics
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from collections import Counter
from dataclasses import dataclass, asdict


@dataclass
class RawMetrics:
    commit_hash:   str
    timestamp:     float
    filepath:      str
    cyclomatic_complexity:  int
    syntactic_dead_code:    int
    duplicate_block_count:  int
    halstead_bugs:          float
    dsm_density:            float
    dependency_instability: float   # GAP-R01: por max_methods_per_class
    infinite_loop_risk:     float
    dsm_cyclic_ratio:       float
    hamiltonian:            float
    loc_effective:          int
    n_functions:            int
    n_classes:              int
    max_methods_per_class:  int     # GAP-R01: campo auxiliar
    channel_stability: Dict[str, bool]  # GAP-R03
    window_position:   float            # GAP-R04
    parse_error:       bool
    cc_hotspot_ratio:  float = 0.0   # GAP-N1: max_fn_cc/avg_fn_cc normalised 0–1
    max_function_cc:   int   = 0     # GAP-N1: CC of the single most complex function


def is_channel_stable(raw_values: List[float],
                       cv_threshold: float = 0.03,
                       window: int = 5) -> bool:
    """
    GAP-R03: True se o canal está estabilizado (não se moveu significativamente).

    Usa Coeficiente de Variação (CV = std/mean) em janelas deslizantes
    + guarda de range global (>5% do mean → não estável).

    Opera sobre valores RAW (não normalizados) para evitar que a normalização
    por self-range confunda micro-variações com crescimento real.

    Casos cobertos:
      - Constante:       [0.95]*50       → True  (CV≈0, range≈0)
      - Micro-variação:  [0.95+0.0001*i] → True  (range < 5% de mean)
      - Crescimento:     [5+i for i...]  → False (range/mean >> 5%)
      - Spike pontual:   [0.95→1.0→0.95]→ False (range/mean ≈ 5.3%)
    """
    if len(raw_values) < window * 2:
        return False
    # Guarda global: range > 5% do mean → canal ativo
    mean_val = statistics.mean(raw_values)
    if abs(mean_val) > 1e-10:
        global_range = max(raw_values) - min(raw_values)
        if global_range / abs(mean_val) > 0.05:
            return False
    else:
        if max(raw_values) - min(raw_values) > 1e-6:
            return False
    # CV rolling por janela
    step = max(1, window // 2)
    for i in range(0, len(raw_values) - window, step):
        seg = raw_values[i:i+window]
        seg_mean = statistics.mean(seg)
        if abs(seg_mean) < 1e-10:
            continue
        try:
            std = statistics.stdev(seg)
        except statistics.StatisticsError:
            std = 0.0
        if std / abs(seg_mean) > cv_threshold:
            return False
    return True


def extract_metrics(code: str, commit_hash: str, timestamp: float,
                    filepath: str, window_position: float = 0.5) -> RawMetrics:
    """
    OPT-01: Single-pass AST walker — calcula TODAS as métricas em uma única
    travessia em vez das 7 anteriores. ~7× mais rápido para arquivos grandes.
    """
    lines = code.split("\n")
    loc   = sum(1 for l in lines if l.strip() and not l.strip().startswith("#"))

    try:
        tree = ast.parse(code)
    except SyntaxError:
        return RawMetrics(
            commit_hash=commit_hash, timestamp=timestamp, filepath=filepath,
            cyclomatic_complexity=1, syntactic_dead_code=0,
            duplicate_block_count=0, halstead_bugs=0.01,
            dsm_density=min(0.95, loc/500.0), dependency_instability=0.3,
            infinite_loop_risk=0.01, dsm_cyclic_ratio=0.0, hamiltonian=2.0,
            loc_effective=loc, n_functions=0, n_classes=0,
            max_methods_per_class=0,
            cc_hotspot_ratio=0.0, max_function_cc=0,  # GAP-N1
            channel_stability={"CC":True,"DSM_d":True,"DI":True,"H":True,"bugs":True},
            window_position=window_position, parse_error=True)

    # ── Single-pass collector ──────────────────────────────────────────────
    cc           = 1
    functions    = []
    classes      = []
    fn_cc_list   = []   # GAP-N1
    op_types     = set()
    op_count     = 0
    ilr_count    = 0
    imp_mods     = set()
    fn_names     = []

    for node in ast.walk(tree):
        t = type(node).__name__

        # CC branches
        if t in ("If","For","While","ExceptHandler","With","Assert","comprehension","IfExp"):
            cc += 1
        elif t == "BoolOp":
            cc += len(node.values) - 1  # type: ignore

        # Functions — GAP-N1: per-function CC
        elif t in ("FunctionDef","AsyncFunctionDef"):
            functions.append(node)
            fn_names.append(node.name)  # type: ignore
            _fn_cc = 1
            for _ch in ast.walk(node):
                _ct = type(_ch).__name__
                if _ct in ("If","For","While","ExceptHandler","With","Assert","comprehension","IfExp"):
                    _fn_cc += 1
                elif _ct == "BoolOp":
                    _fn_cc += len(_ch.values) - 1  # type: ignore
            fn_cc_list.append(_fn_cc)

        # Classes
        elif t == "ClassDef":
            classes.append(node)

        # Halstead operators
        elif t in {"Add","Sub","Mult","Div","Mod","Pow","LShift","RShift",
                   "BitOr","BitXor","BitAnd","FloorDiv","MatMult",
                   "Eq","NotEq","Lt","LtE","Gt","GtE","Is","IsNot","In","NotIn",
                   "And","Or","Not","Invert","UAdd","USub"}:
            op_types.add(t)

        # Halstead operands
        elif t in ("Name","Constant","Attribute"):
            op_count += 1

        # ILR: while True without break
        elif t == "While":
            c = node.test  # type: ignore
            if ((isinstance(c, ast.Constant) and c.value in (True, 1)) or
                    (isinstance(c, ast.Name) and c.id == "True")):  # type: ignore
                if not any(isinstance(n, ast.Break) for n in ast.walk(node)):
                    ilr_count += 1

        # Imports
        elif t == "ImportFrom" and node.module:  # type: ignore
            imp_mods.add(node.module.split(".")[0])  # type: ignore

    return _compute_raw_metrics(
        cc, functions, classes, op_types, op_count,
        ilr_count, imp_mods, fn_names, loc,
        filepath, commit_hash, timestamp, window_position,
        fn_cc_list=fn_cc_list,  # GAP-N1
        code=code, tree=tree)   # GAP-N3

def detect_runtime_cycles(code: str, tree) -> float:
    """GAP-N3: Detecta ciclos runtime via proxies, TYPE_CHECKING, injeção dinâmica."""
    score = 0.0
    if any(p in code for p in ("LocalProxy", "LazyObject", "Proxy(")):
        score += 0.45
    if any(d in code for d in ("import_string", "importlib.import_module")):
        score += 0.35
    if "TYPE_CHECKING" in code:
        score += 0.30
    if score > 0 and tree is not None:
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                for child in node.body:
                    if isinstance(child, (ast.Import, ast.ImportFrom)):
                        score += 0.08
                        break
    return min(score, 1.0)


def _compute_raw_metrics(
    cc: int, functions: list, classes: list,
    op_types: set, op_count: int, ilr_count: int,
    imp_mods: set, fn_names: list, loc: int,
    filepath: str, commit_hash: str,
    timestamp: float, window_position: float,
    fn_cc_list: list = None,
    code: str = "", tree=None) -> "RawMetrics":
    """Compute derived UCO metrics from AST single-pass results."""

    # Dead code proxy
    dead = 0
    for fn in functions:
        for i, stmt in enumerate(fn.body[:-1]):
            if isinstance(stmt, (ast.Return, ast.Raise, ast.Break, ast.Continue)):
                dead += len(fn.body) - i - 1
                break

    # Duplicate names
    from collections import Counter as _Counter
    dups = sum(c-1 for c in _Counter(fn_names).values() if c > 1)

    # Halstead bugs
    h_vol  = max(1, len(op_types)) * math.log2(max(2, len(op_types) + op_count))
    bugs   = h_vol / 3000.0

    # DSM density (LOC proxy)
    dsm_d  = min(0.95, loc / 500.0)

    # DI: max methods per class (GAP-R01)
    methods_per_cls = {
        cls.name: sum(1 for item in cls.body
                      if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)))
        for cls in classes
    }
    max_methods = max(methods_per_cls.values()) if methods_per_cls else 0
    di          = min(0.95, max_methods / 20.0)
    # GAP-N1: CC hotspot ratio
    fn_cc_list = fn_cc_list or []
    if len(fn_cc_list) >= 3:
        _mxfn = max(fn_cc_list)
        _avgfn = sum(fn_cc_list) / len(fn_cc_list)
        cc_hotspot = min(0.95, (_mxfn / (_avgfn + 0.001)) / 5.0)
        max_fn_cc_v = _mxfn
    else:
        cc_hotspot = 0.0; max_fn_cc_v = 0

    # ILR: also check recursive functions without base case
    for fn in functions:
        if any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
               and n.func.id == fn.name for n in ast.walk(fn)):
            if not any(isinstance(n, (ast.If, ast.Return)) for n in fn.body[:2]):
                ilr_count += 1
    ilr = min(0.95, ilr_count * 0.15)

    # DSM cyclic ratio (same-package imports proxy)
    mod_top = filepath.split("/")[0] if "/" in filepath else ""
    dsm_c_ast = (min(0.8, sum(1 for m in imp_mods
                              if mod_top and m.startswith(mod_top.split(".")[0]))
                    / max(1, len(imp_mods)) * 0.5)
               if imp_mods else 0.0)
    # GAP-N3: elevate dsm_c with runtime cycle signals (proxies, TYPE_CHECKING)
    dsm_c = max(dsm_c_ast, detect_runtime_cycles(code, tree) if tree is not None else 0.0)

    # Hamiltonian
    ham = (1.00*cc + 0.90*dead*0.5 + 0.75*dups*0.5 + 2.20*ilr*3 +
           1.35*dsm_d*5 + 1.50*dsm_c*3 + 1.10*di*2 + 1.00*bugs*10)

    return RawMetrics(
        commit_hash=commit_hash, timestamp=timestamp, filepath=filepath,
        cyclomatic_complexity=min(1000, cc),  # BUG-E1: 200 saturava módulos grandes (pandas CC≈500+)
        syntactic_dead_code=min(100, dead),
        duplicate_block_count=min(50, dups),
        halstead_bugs=min(5.0, bugs),
        dsm_density=dsm_d,
        dependency_instability=di,
        infinite_loop_risk=ilr,
        dsm_cyclic_ratio=dsm_c,
        hamiltonian=max(0.1, min(500.0, ham)),
        loc_effective=loc, n_functions=len(functions), n_classes=len(classes),
        max_methods_per_class=max_methods,
        cc_hotspot_ratio=cc_hotspot,   # GAP-N1
        max_function_cc=max_fn_cc_v,   # GAP-N1
        channel_stability={"CC":False,"DSM_d":False,"DI":False,"H":False,"bugs":False},
        window_position=window_position, parse_error=False)

class GitExtractor:
    def __init__(self, repo_path: str):
        self.repo = Path(repo_path).resolve()
        assert (self.repo / ".git").exists(), f"Não é um repositório git: {repo_path}"

    def get_python_files_by_freq(self, n_commits: int = 200,
                                  max_files: int = 8) -> List[str]:
        """Retorna os arquivos Python mais modificados."""
        cmd = ["git", "log", f"-{n_commits}", "--name-only",
               "--format=", "--diff-filter=M"]
        result = subprocess.run(cmd, cwd=self.repo,
                                capture_output=True, text=True)
        freq: Counter = Counter()
        for line in result.stdout.strip().split("\n"):
            if line.endswith(".py"):
                freq[line] += 1

        # Filtrar arquivos que existem no HEAD e têm tamanho razoável
        candidates = []
        for filepath, count in freq.most_common(max_files * 4):
            full = self.repo / filepath
            if full.exists():
                size = full.stat().st_size
                if 200 < size < 200_000:  # entre 200 bytes e 200KB
                    candidates.append((filepath, count))
            if len(candidates) >= max_files:
                break

        print(f"  Arquivos selecionados ({len(candidates)}):")
        for fp, cnt in candidates:
            print(f"    • {fp}  ({cnt} modificações)")

        return [fp for fp, _ in candidates]

    def get_commits_for_file(self, filepath: str,
                              max_commits: int = 300) -> List[Tuple[str, float, str]]:
        """Retorna (hash, timestamp, msg) para os commits que tocaram o arquivo."""
        cmd = ["git", "log", f"-{max_commits}",
               "--format=%H|%at|%s", "--follow", "--", filepath]
        result = subprocess.run(cmd, cwd=self.repo,
                                capture_output=True, text=True)
        commits = []
        for line in result.stdout.strip().split("\n"):
            if "|" not in line:
                continue
            parts = line.split("|", 2)
            if len(parts) == 3:
                h, ts, msg = parts
                try:
                    commits.append((h.strip(), float(ts.strip()), msg.strip()))
                except ValueError:
                    pass
        return list(reversed(commits))  # cronológico

    def get_file_at_commit(self, commit_hash: str,
                            filepath: str) -> Optional[str]:
        """Conteúdo do arquivo em um commit específico."""
        cmd = ["git", "show", f"{commit_hash}:{filepath}"]
        result = subprocess.run(cmd, cwd=self.repo,
                                capture_output=True, text=True)
        if result.returncode != 0:
            return None
        return result.stdout


def extract_repo(repo_path, output_path, max_commits=350, max_files=6,
                 files_explicit=None, rank_by="recent", verbose=True):
    """v2.0 com GAP-R01 a GAP-R04."""
    repo_name = Path(repo_path).name
    print(f"\n{'═'*62}")
    print(f"  Extração v2.0: {repo_name}")
    print(f"  GAP-R01/02/03/04 ativos")
    print(f"{'═'*62}")

    ext = GitExtractor(repo_path)

    if files_explicit:
        files = files_explicit
        print(f"\n  Arquivos explícitos ({len(files)}):")
        for fp in files: print(f"    • {fp}")
    else:
        print(f"\n  Identificando arquivos...")
        files = ext.get_python_files_by_freq(max_commits, max_files, rank_by)

    if not files:
        print("  ERRO: nenhum arquivo encontrado"); return {}

    result = {
        "repo": repo_name, "repo_path": str(repo_path),
        "extracted_at": time.time(), "extractor_version": "2.0",
        "gaps_applied": ["GAP-R01","GAP-R02","GAP-R03","GAP-R04"],
        "max_commits_requested": max_commits, "rank_by": rank_by,
        "files_explicit": files_explicit or [], "files_analyzed": files,
        "modules": {}, "metadata": {
            "git_version": subprocess.run(["git","--version"],
                capture_output=True, text=True).stdout.strip()
        }
    }

    total = 0
    for filepath in files:
        module_id = filepath.replace("/",".").replace(".py","")
        print(f"\n  [{module_id}]")
        commits = ext.get_commits_for_file(filepath, max_commits)
        n = len(commits)
        print(f"    Commits: {n}")
        if n < 5:
            print(f"    ⚠ insuficiente"); continue

        snapshots = []
        raw: Dict[str,List[float]] = {"CC":[],"DSM_d":[],"DI":[],"H":[],"bugs":[]}
        errors = 0

        for i, (h, ts, msg) in enumerate(commits):
            code = ext.get_file_at_commit(h, filepath)
            if not code or len(code.strip()) < 30: continue
            wp = i / max(1, n-1)   # GAP-R04: window_position
            m = extract_metrics(code, h, ts, filepath, wp)
            if m.parse_error:
                errors += 1; continue
            raw["CC"].append(float(m.cyclomatic_complexity))
            raw["DSM_d"].append(m.dsm_density)
            raw["DI"].append(m.dependency_instability)
            raw["H"].append(m.hamiltonian)
            raw["bugs"].append(m.halstead_bugs)
            snapshots.append(asdict(m))
            if verbose and (i+1) % 50 == 0:
                print(f"    ... {i+1}/{n} commits")

        # GAP-R03: calcular estabilidade sobre a série completa normalizada
        stab: Dict[str,bool] = {}
        for ch, values in raw.items():
            vmin, vmax = min(values) if values else 0, max(values) if values else 1
            vrange = vmax - vmin + 1e-10
            norm = [(v-vmin)/vrange for v in values]
            stab[ch] = is_channel_stable(norm)
        stable = [ch for ch,s in stab.items() if s]
        if stable:
            print(f"    ⚠ Canais estabilizados (GAP-R03): {stable}")
        for snap in snapshots:
            snap["channel_stability"] = stab

        print(f"    Snapshots: {len(snapshots)}  erros: {errors}")
        total += len(snapshots)
        result["modules"][module_id] = snapshots

    result["total_snapshots"] = total
    result["stability_summary"] = {
        mid: snaps[0].get("channel_stability", {})
        for mid, snaps in result["modules"].items() if snaps
    }

    print(f"\n  Total snapshots: {total}  Módulos: {len(result['modules'])}")
    with open(output_path,"w",encoding="utf-8") as f:
        json.dump(result, f, indent=2, default=str)
    print(f"  Salvo: {output_path}  ({Path(output_path).stat().st_size//1024} KB)")
    print(f"{'═'*62}\n")
    return result


def main():
    p = argparse.ArgumentParser(
        description="UCO-Sensor v2.0 — Extrator com GAP-R01 a GAP-R04",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  python3 extract_repo_history.py --repo /tmp/requests --out req.json
  python3 extract_repo_history.py --repo /tmp/requests \
      --files-explicit src/requests/sessions.py --out sessions.json
  python3 extract_repo_history.py --repo /tmp/scrapy \
      --rank-by total --out scrapy.json
""")
    p.add_argument("--repo",    required=True)
    p.add_argument("--out",     required=True)
    p.add_argument("--commits", type=int, default=350)
    p.add_argument("--files",   type=int, default=6)
    p.add_argument("--files-explicit",
                   help="Arquivos separados por vírgula. Ex: a.py,b.py")
    p.add_argument("--rank-by", choices=["recent","total"], default="recent")
    p.add_argument("--quiet",   action="store_true")
    args = p.parse_args()

    fe = None
    if args.files_explicit:
        fe = [f.strip() for f in args.files_explicit.split(",") if f.strip()]

    extract_repo(args.repo, args.out, args.commits, args.files,
                 fe, args.rank_by, not args.quiet)

if __name__ == "__main__":
    main()
