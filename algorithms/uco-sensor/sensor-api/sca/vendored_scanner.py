"""
UCO-Sensor — Vendored-Dependency SCA  (M9.4)
=============================================
A source-tree Software-Composition-Analysis axis for repositories that
**have no committed lockfile** but **vendor** (copy in) third-party
libraries that declare their own version in source.

Why this exists
---------------
Sprints AM–AO established that several corpus repos (notably the
PHP/Ruby/C#/Mobile category — WordPress, etc.) ship no
``composer.lock`` / ``Gemfile.lock`` / ``packages.lock.json`` anywhere,
so the manifest-based SCA bridge (M9.1, OSV-Scanner) cannot run.  The
deep-research synthesis (Sprint AR, ANGLE 2) pointed at *source-based*
SCA (V1SCAN / CENTRIS) as the way in.

This module takes the **low-false-positive** subset of that idea: rather
than fuzzy function-hashing (which V1SCAN shows yields ~71% FPs before
code-classification), it keys on the fact that a well-known vendored
library declares its **exact version** in a predictable file (e.g.
WordPress bundles ``rmccue/requests`` with a ``VERSION`` constant).  We:

1. Detect the vendored library + its declared version (a small, explicit
   registry of markers — no guessing).
2. Look up that package's advisories (GHSA, reusing the same allowed
   ``api.github.com`` endpoint as M9.3) and their machine-readable
   ``vulnerable_version_range``.
3. Decide *vulnerable* vs *clean* by proper range containment — reporting
   **clean** when the vendored version is already patched.

A *clean* verdict is a legitimate, validated SCA result for the corpus
(exactly as ``three.js``/``pytorch`` count as "SCA A, limpo"): the value
is that the tool produced a real dependency-exposure verdict over a real
resolved version, not that the repo is necessarily vulnerable.

The version-range logic (``version_in_range`` / ``verdict_for``) is pure
and unit-tested offline; network fetching is injected.

Public API
----------
    version_in_range("2.0.17", ">= 1.6.0, < 1.8.0")      -> False
    verdict_for("2.0.17", advisories)                    -> VendorVerdict
    scanner = VendoredScanner(fetcher=...)               # or token=...
    scanner.scan_package("composer", "rmccue/requests", "2.0.17")
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

# ── version parsing / comparison ──────────────────────────────────────────────

_NUM_RE = re.compile(r"\d+")


def _parse_version(v: str) -> Tuple[int, ...]:
    """
    Parse a dotted version into a tuple of ints for comparison.

    Strips a leading ``v`` and any pre-release/build suffix on each segment
    (``1.8.0-beta2`` → ``(1, 8, 0)``).  Missing segments compare as 0, so
    ``(1, 8)`` == ``(1, 8, 0)`` semantics hold via zero-padding at compare
    time.  Non-numeric junk yields an empty tuple (compares lowest).
    """
    v = v.strip().lstrip("vV")
    parts: List[int] = []
    for seg in v.split("."):
        m = _NUM_RE.match(seg)
        if not m:
            break
        parts.append(int(m.group()))
    return tuple(parts)


def _cmp(a: Tuple[int, ...], b: Tuple[int, ...]) -> int:
    """Compare two version tuples with zero-padding. -1/0/1."""
    n = max(len(a), len(b))
    a = a + (0,) * (n - len(a))
    b = b + (0,) * (n - len(b))
    return (a > b) - (a < b)


_COMP_RE = re.compile(r"(>=|<=|>|<|=|==)\s*([0-9][0-9A-Za-z.\-]*)")


def version_in_range(version: str, vrange: str) -> bool:
    """
    True iff *version* satisfies *vrange*.

    Accepts the GitHub-advisory grammar: comma-separated comparators, e.g.
    ``">= 1.6.0, < 1.8.0"``, ``"< 1.8.0"``, ``"= 2.0.1"``, ``"<= 3.4"``.
    An empty / unparseable range is treated as "not constrained" → False
    (we never flag on an unparseable range — fail safe toward clean).
    """
    if not vrange or not vrange.strip():
        return False
    comparators = _COMP_RE.findall(vrange)
    if not comparators:
        return False
    ver = _parse_version(version)
    if not ver:
        return False
    for op, bound_s in comparators:
        bound = _parse_version(bound_s)
        c = _cmp(ver, bound)
        ok = {
            ">=": c >= 0,
            "<=": c <= 0,
            ">": c > 0,
            "<": c < 0,
            "=": c == 0,
            "==": c == 0,
        }[op]
        if not ok:
            return False
    return True


# ── advisory → verdict ────────────────────────────────────────────────────────

_PKGCONFIG_RE = re.compile(
    r'<package\s+id="([^"]+)"\s+version="([^"]+)"', re.IGNORECASE
)
_PKGVERSION_RE = re.compile(
    r'<PackageVersion\s+Include="([^"]+)"\s+Version="([^"]+)"', re.IGNORECASE
)
_MSBUILD_VAR_RE = re.compile(r"\$\((\w+)\)")
_PROP_RE = re.compile(r"<(\w+)>([^<]+)</\1>")


def parse_packages_config(xml: str) -> Dict[str, str]:
    """
    Parse a NuGet **old-style** ``packages.config`` into ``{name: version}``.

    ``packages.config`` pins exact versions (``<package id="X" version="Y.Z"/>``)
    so it is, for SCA purposes, equivalent to a lockfile.  Sprint AX found
    this format went unscanned by earlier ``*.lock`` code-searches.
    """
    out: Dict[str, str] = {}
    for name, ver in _PKGCONFIG_RE.findall(xml or ""):
        if re.match(r"\d", ver.strip()):
            out[name] = ver.strip()
    return out


_CARGO_PKG_RE = re.compile(
    r'\[\[package\]\]\s*\nname = "([^"]+)"\s*\nversion = "([^"]+)"'
)


def parse_cargo_lock(toml_text: str) -> Dict[str, str]:
    """
    Parse a Rust ``Cargo.lock`` into ``{crate: version}``.

    ``Cargo.lock`` pins exact resolved versions per ``[[package]]`` stanza —
    a real lockfile for the ``cargo`` ecosystem.  Sprint AZ used this to give
    `ClickHouse` (whose root only had a `pyproject.toml`) a resolvable SCA
    axis via its `rust/workspace/Cargo.lock`.
    """
    out: Dict[str, str] = {}
    for name, ver in _CARGO_PKG_RE.findall(toml_text or ""):
        out[name] = ver
    return out


def parse_msbuild_cpm(packages_props: str, versions_props: str) -> Dict[str, str]:
    """
    Resolve NuGet **Central Package Management** into ``{name: version}``.

    ``Packages.props`` lists ``<PackageVersion Include="X" Version="$(XVer)"/>``
    where ``$(XVer)`` is defined in ``Versions.props`` as ``<XVer>1.2.3</XVer>``.
    Literal (non-indirected) versions are kept as-is.  Unresolved variables
    are dropped (never guessed) so a missing definition can't produce a wrong
    version → false positive.
    """
    varmap: Dict[str, str] = {}
    for name, ver in _PROP_RE.findall(versions_props or ""):
        v = ver.strip()
        if re.match(r"\d", v):
            varmap[name] = v
    out: Dict[str, str] = {}
    for pid, vexpr in _PKGVERSION_RE.findall(packages_props or ""):
        vexpr = vexpr.strip()
        m = _MSBUILD_VAR_RE.match(vexpr)
        if m:
            if m.group(1) in varmap:
                out[pid] = varmap[m.group(1)]
        elif re.match(r"\d", vexpr):
            out[pid] = vexpr
    return out


@dataclass(frozen=True)
class VendorHit:
    """One advisory that the vendored version actually falls into."""

    cve_id: Optional[str]
    ghsa_id: Optional[str]
    vulnerable_range: str
    package: str


@dataclass(frozen=True)
class VendorVerdict:
    """SCA verdict for one vendored (package, version)."""

    package: str
    version: str
    advisories_checked: int
    hits: List[VendorHit] = field(default_factory=list)

    @property
    def vulnerable(self) -> bool:
        return len(self.hits) > 0

    @property
    def rating(self) -> str:
        """Coarse rating mirroring the manifest SCA axis: 'A' clean … 'E'."""
        n = len(self.hits)
        if n == 0:
            return "A"
        if n == 1:
            return "C"
        if n < 4:
            return "D"
        return "E"


def _iter_pkg_vulns(advisory: Dict[str, Any], package: str):
    """Yield (vulnerable_version_range, vuln) for entries matching *package*."""
    for v in advisory.get("vulnerabilities") or []:
        pkg = ((v.get("package") or {}).get("name") or "").lower()
        if pkg == package.lower():
            yield v.get("vulnerable_version_range") or "", v


def verdict_for(
    version: str,
    advisories: List[Dict[str, Any]],
    package: str,
) -> VendorVerdict:
    """
    Decide the verdict for *package*@*version* against a list of GHSA
    advisory dicts.  Pure — no network.  A version is a *hit* only when it
    falls inside an advisory's ``vulnerable_version_range`` for that exact
    package (proper range containment, so patched versions read clean).
    """
    hits: List[VendorHit] = []
    for adv in advisories:
        for vrange, _v in _iter_pkg_vulns(adv, package):
            if version_in_range(version, vrange):
                hits.append(
                    VendorHit(
                        cve_id=adv.get("cve_id"),
                        ghsa_id=adv.get("ghsa_id"),
                        vulnerable_range=vrange,
                        package=package,
                    )
                )
    return VendorVerdict(
        package=package,
        version=version,
        advisories_checked=len(advisories),
        hits=hits,
    )


# ── scanner (network front-end, graceful offline) ─────────────────────────────

class VendoredScanner:
    """
    Queries GHSA for a package's advisories and produces a
    :class:`VendorVerdict` for a given vendored version.

    Parameters mirror :class:`sast.ghsa_fix_resolver.GHSAFixResolver`:
    inject a ``fetcher`` for offline tests, or pass a ``token``.
    """

    _URL = "https://api.github.com/advisories?ecosystem={eco}&affects={pkg}"

    def __init__(
        self,
        token: Optional[str] = None,
        fetcher: Optional[Callable[[str], Any]] = None,
    ) -> None:
        self._token = token
        self._fetcher = fetcher

    def available(self) -> bool:
        return self._fetcher is not None or bool(self._token)

    def _fetch(self, url: str) -> Any:
        if self._fetcher is not None:
            return self._fetcher(url)
        import json
        import urllib.request

        req = urllib.request.Request(url)
        req.add_header("Accept", "application/vnd.github+json")
        req.add_header("User-Agent", "uco-sensor-vendored-sca")
        if self._token:
            req.add_header("Authorization", f"Bearer {self._token}")
        with urllib.request.urlopen(req, timeout=30) as r:  # noqa: S310
            return json.loads(r.read().decode())

    def scan_package(
        self, ecosystem: str, package: str, version: str
    ) -> Optional[VendorVerdict]:
        """
        Return a :class:`VendorVerdict` for *package*@*version*, or ``None``
        when offline / the fetch fails (caller falls back).
        """
        if not self.available():
            return None
        from urllib.parse import quote

        try:
            payload = self._fetch(
                self._URL.format(eco=quote(ecosystem), pkg=quote(package))
            )
        except Exception:
            return None
        advisories = payload if isinstance(payload, list) else []
        return verdict_for(version, advisories, package)
