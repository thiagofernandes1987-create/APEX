"""
UCO-Sensor — GHSA Fix-Commit Resolver  (M9.3)
==============================================
Resolves the *real fix commit* of a known vulnerability directly from the
GitHub Security Advisory (GHSA) database, instead of guessing it via
commit-message search.

Motivation
----------
The CVE-anchored SAST methodology needs the exact fix commit to diff the
vulnerable vs. patched file.  Earlier sprints located it with the GitHub
Search Commits API (`<CVE-ID> repo:owner/name`).  That fails whenever the
project does **not** cite the CVE in its commit message — confirmed for
SVN-backed (Apache httpd) and GitLab-backed (Wireshark) projects, and for
several GitHub-native Java projects (spring-boot, kafka, elasticsearch)
whose security fixes land without a CVE reference in the message.

The GHSA / OSV databases, however, curate a ``references`` list that often
contains a direct ``github.com/<owner>/<name>/commit/<sha>`` link to the
fix.  This module extracts that link.  Empirically validated this session:
``CVE-2023-20883`` (spring-boot DoS) → GHSA-xf96-w227-r7c4 →
``commit/418dd1ba5bdad79b55a043000164bfcbda2acd78`` — the exact fix, which
the commit-message search had NOT surfaced.

Design
------
* Pure parsing (``extract_fix_commits``) is separated from network I/O
  (``resolve``) so the extraction logic is unit-testable offline against a
  real captured advisory payload — the same contract as
  ``sast/sca_bridge.py``.
* Never raises on a missing/edge payload: returns an empty result.
* ``resolve`` degrades gracefully (returns ``None``) when no HTTP fetcher /
  token is available, so import and call never crash in offline CI.

Public API
----------
    refs = extract_fix_commits(advisory_dict, repo="spring-projects/spring-boot")
        -> list[FixRef]   (sha + url, deduped, order-preserving)

    resolver = GHSAFixResolver(token=os.environ.get("GITHUB_TOKEN"))
    resolver.available()                      -> bool
    resolver.resolve("CVE-2023-20883",
                     repo="spring-projects/spring-boot")
        -> list[FixRef]   (empty when unresolved; never raises)
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import quote

# github.com/<owner>/<name>/commit/<40-hex>  (also tolerates /commits/)
_COMMIT_RE = re.compile(
    r"github\.com/(?P<repo>[^/\s]+/[^/\s]+)/commits?/(?P<sha>[0-9a-fA-F]{7,40})"
)


@dataclass(frozen=True)
class FixRef:
    """A resolved fix-commit reference."""

    repo: str
    sha: str
    url: str


def _iter_reference_urls(advisory: Dict[str, Any]):
    """
    Yield every reference URL in a GHSA/OSV advisory payload, tolerating both
    shapes seen in the wild:

    * GitHub REST advisories: ``references`` is a list[str].
    * OSV / some GHSA exports: ``references`` is a list[{"url": ...}].
    """
    refs = advisory.get("references") or []
    for r in refs:
        if isinstance(r, str):
            yield r
        elif isinstance(r, dict):
            url = r.get("url")
            if isinstance(url, str):
                yield url


def extract_fix_commits(
    advisory: Dict[str, Any],
    repo: Optional[str] = None,
) -> List[FixRef]:
    """
    Extract fix-commit references from an advisory payload.

    Parameters
    ----------
    advisory
        A GHSA/OSV advisory dict (must carry a ``references`` field).
    repo
        Optional ``owner/name`` filter — when given, only commits in that
        repository are returned (case-insensitive).  This is what lets the
        caller ignore fix links that point at a *dependency's* repo rather
        than the target project.

    Returns
    -------
    list[FixRef]
        Deduplicated by (repo, sha), preserving first-seen order.  Empty when
        nothing matches — never raises.
    """
    want = repo.lower() if repo else None
    seen = set()
    out: List[FixRef] = []
    for url in _iter_reference_urls(advisory):
        m = _COMMIT_RE.search(url)
        if not m:
            continue
        found_repo = m.group("repo")
        sha = m.group("sha")
        if want is not None and found_repo.lower() != want:
            continue
        key = (found_repo.lower(), sha.lower())
        if key in seen:
            continue
        seen.add(key)
        out.append(FixRef(repo=found_repo, sha=sha, url=url))
    return out


class GHSAFixResolver:
    """
    Network front-end over the GitHub Advisories REST API with a graceful
    offline mode.

    Parameters
    ----------
    token
        A GitHub token (the public ``/advisories`` endpoint benefits from
        auth for rate limits).  When ``None`` and no ``fetcher`` is given,
        :meth:`resolve` returns ``None`` (offline mode).
    fetcher
        Optional ``Callable[[str], dict|list]`` used instead of the built-in
        urllib fetch — injected by tests to avoid real network access.
    """

    _ADVISORIES_URL = "https://api.github.com/advisories?cve_id={cve}"

    def __init__(
        self,
        token: Optional[str] = None,
        fetcher: Optional[Callable[[str], Any]] = None,
    ) -> None:
        self._token = token
        self._fetcher = fetcher

    def available(self) -> bool:
        """True when a fetch path exists (injected fetcher or a token)."""
        return self._fetcher is not None or bool(self._token)

    def _fetch(self, url: str) -> Any:
        if self._fetcher is not None:
            return self._fetcher(url)
        import urllib.request

        req = urllib.request.Request(url)
        req.add_header("Accept", "application/vnd.github+json")
        req.add_header("User-Agent", "uco-sensor-ghsa-resolver")
        if self._token:
            req.add_header("Authorization", f"Bearer {self._token}")
        with urllib.request.urlopen(req, timeout=30) as r:  # noqa: S310
            return json.loads(r.read().decode())

    def resolve(self, cve_id: str, repo: Optional[str] = None) -> Optional[List[FixRef]]:
        """
        Resolve the fix commit(s) for *cve_id*, optionally filtered to *repo*.

        Returns
        -------
        list[FixRef]
            Possibly empty when the advisory exists but carries no commit
            reference for *repo*.
        None
            Offline (no fetcher/token) or the fetch failed — the caller
            should fall back to commit-message search.
        """
        if not self.available():
            return None
        try:
            payload = self._fetch(self._ADVISORIES_URL.format(cve=quote(cve_id)))
        except Exception:
            return None
        # The advisories endpoint returns a list; take advisories in order and
        # merge their fix refs (dedup handled by extract_fix_commits per call).
        advisories = payload if isinstance(payload, list) else [payload]
        seen = set()
        out: List[FixRef] = []
        for adv in advisories:
            if not isinstance(adv, dict):
                continue
            for ref in extract_fix_commits(adv, repo=repo):
                key = (ref.repo.lower(), ref.sha.lower())
                if key not in seen:
                    seen.add(key)
                    out.append(ref)
        return out
