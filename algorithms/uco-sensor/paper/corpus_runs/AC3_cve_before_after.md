# Sprint AC-3 — CVE-Anchored Before/After Audit (all 8 repos) + Scanner Refinement

> Direct answer to: "você procurou no histórico de commits de versões
> anteriores para comparar com a versão corrigida para verificar se nas
> versões anteriores o UCO Sensor identificou os erros?" AC-1/AC-2 only
> measured a generic, statistically uninformative onset→fix-keyword
> correlation (see `AC2_summary.md` §4). This round instead anchors on
> **documented, real CVEs/GHSAs** with known vulnerable-commit /
> fixed-commit pairs, diffs the actual SAST findings and the 9 structural
> metric channels between the two snapshots, and — per the explicit
> request — uses the confirmed gaps to add real detector rules
> (`SAST046`, `SAST047`) rather than only reporting them.

## Methodology

For each CVE: resolve `(vulnerable_sha, fixed_sha, file_path)` via the
GitHub Security Advisories API (native repo advisories or the global
`/advisories?ecosystem=pip&affects=<pkg>` endpoint), the fix PR's
`base.sha`/`merge_commit_sha`, or a commit-message search for the CVE ID
— then fetch both file snapshots via the Contents API and run
`sast.scanner.scan()` + `lang_adapters.registry.get_registry().analyze()`
on each (`paper/cve_diff_check.py`, generalized as a batch runner for this
round). No automatic pass/fail judgment beyond two explicit, disclosed
heuristics: a finding is **SAST signal** if the rule-ID set differs
between vuln/fixed; a metric is flagged if its relative delta exceeds
15%. Everything is also printed in full so a human can override the
heuristic — which mattered (see "Honest caveat" below).

## Repo coverage gap (disclosed up front)

Native GHSA records per repo: `flask`=3, `django`=0 (native), `fastapi`=1,
`matplotlib`=0, `celery`=0 (native), `scrapy`=11, `pandas`=0, `requests`=4.
Falling back to the **global** advisory index
(`/advisories?ecosystem=pip&affects=<pkg>`) recovered `django` (100+,
capped at one page) and `celery` (2), but **`matplotlib` and `pandas`
have zero indexed CVEs/GHSAs in either source** — there is nothing to
anchor a before/after diff on for those two repos with this method. This
round does not claim coverage for them; it is not a silent omission.

## Cases run (8 total: 2 from the earlier manual round + 6 new)

| Repo | CVE | File | Root cause | SAST diff | Metric Δ>15% | Verdict |
|---|---|---|---|---|---|---|
| `psf/requests` | CVE-2024-47081 | `utils.py` | `.netrc` host matched via `netloc.split(":")` instead of `.hostname` | none | none | **BLIND SPOT** |
| `psf/requests` | CVE-2023-32681 | `sessions.py` | `Proxy-Authorization` reattached after redirect without scheme check | none | none | **BLIND SPOT** |
| `psf/requests` | CVE-2024-35195 | `adapters.py` | `verify=False` cached and reused across redirects in same `Session` | none | `dsm_cyclic_ratio` +76%, `duplicate_block_count` +38% | weak/confounded SIGNAL† |
| `scrapy/scrapy` | CVE-2022-0577 | `redirect.py` | Cookie header carried across domain on redirect (logic absent pre-fix) | none | `cyclomatic_complexity` +11%, `halstead_bugs` +12% | **BLIND SPOT** |
| `pallets/flask` | CVE-2023-30861 | `sessions.py` | Missing `Vary: Cookie` → cache poisoning of session data | none | none | **BLIND SPOT** |
| `django/django` | CVE-2024-53908 | `json.py` | Oracle `HasKey` SQL built via string template, injectable | none | `duplicate_block_count` +18% | weak/confounded SIGNAL† |
| `celery/celery` | CVE-2021-23727 | `backends/base.py` | Untrusted deserialization of task failure result → command injection | none | none | **BLIND SPOT** |
| `fastapi/fastapi` | CVE-2021-32677 | `routing.py` | Missing CSRF protection on routing layer | none | none | **BLIND SPOT** |

**6/8 (75%) are clean blind spots** — zero SAST rule-set change, zero
metric channel moved meaningfully. **2/8 show a metric delta**, marked
†because both are confounded (see below) rather than clean evidence of
detection.

### Honest caveat on the 2 "signal" cases

Inspecting the actual diffs: the `django` CVE-2024-53908 fix is a real
refactor (one method split into `_as_sql_parts`/`_combine_sql_parts`,
+18 lines) and the `requests` CVE-2024-35195 fix adds a genuinely new
function (`_urllib3_request_context`, +27 lines) — both fixes bundle
substantial **accompanying structural change** with the security fix
itself. The metric deltas track that the file *grew/restructured*, not
that any channel diagnosed the *specific vulnerability*. A metric that
moves only because a fix happens to come with a refactor is not
diagnostic — it would move identically for a non-security refactor of
the same size. Treating these as confirmed detections would overclaim,
exactly the mistake AC-2 already corrected once for the onset-fix
metric; flagging it here instead.

**Net, more conservative reading: 6 clean blind spots, 0 confirmed clean
detections, 2 confounded non-cases.** This is a stronger version of the
single-repo finding from the prior round, now replicated across 6
different repos/teams/domains — the gap is systemic, not a `requests`
peculiarity.

## Refinement applied (not just reported)

Two of the four `requests`/`scrapy` redirect/credential-leak blind spots
share a precise, generalizable AST shape and became new rules in
`sast/scanner.py` (rule-ID namespace continues from `SAST045`, the
highest previously shipped):

- **`SAST046` — URL Host Extracted via `netloc.split()` Instead of
  `.hostname`** (CWE-1286, MEDIUM). Flags `<expr>.netloc.split(...)` —
  `.netloc` includes userinfo/IPv6 brackets a naive split mishandles,
  letting host-based checks (`.netrc` matching, allow/deny lists) be
  bypassed. Pinned against the *exact* vulnerable `requests/utils.py`
  shape (`ri.netloc.split(splitstr)[0]`) — fires on it, silent on the
  real fix (`urlparse(url).hostname`).
- **`SAST047` — Sensitive Header Re-sent on Redirect Without Origin
  Check** (CWE-200, MEDIUM). Flags a function that **removes and later
  re-assigns** the same sensitive header key (`Authorization`,
  `Proxy-Authorization`, `Cookie`, `Cookie2`) — the reattachment shape —
  without the function ever actually *conditioning* on a
  scheme/host/netloc-derived value (tracks variables assigned from such
  an attribute, not just bare attribute presence). This distinction
  matters: the real vulnerable `rebuild_proxies()` *does* read `scheme`,
  but only to index a dict — never compares it — so a naive
  "does it mention `scheme` anywhere" check would have produced a false
  negative on the exact bug it's meant to catch. The real fix guards
  with `scheme.startswith('https')`, which the rule recognizes.
  Requiring both removal *and* re-assignment of the same key (not just
  any touch) avoids false-firing on ordinary one-shot header-setting
  code.

Both rules were validated directly against the real GitHub-fetched
vulnerable/fixed snapshots (not just synthetic examples) before being
pinned in `tests/test_marco_m63.py` (TAC01-TAC14: 5 cases for SAST046, 9
for SAST047, including explicit false-positive-avoidance cases for
deletion-without-reassignment, one-shot header sets, and an
explicit-equality-guarded variant). Full suite: 2205 passed, 5 skipped,
0 regressions.

`scrapy`'s CVE-2022-0577 stays a blind spot even after the refinement —
deliberately. That vulnerability is the *absence* of any cookie-domain
check (the guard function didn't exist pre-fix), not a present-but-
unguarded reattachment; there is no AST node to anchor a presence-based
rule on in the vulnerable snapshot. Documented as a known limitation
rather than worked around with a weaker, over-firing heuristic.

## What this round validates / leaves open

* The CVE-anchored before/after method (vs. AC-1/AC-2's onset-keyword
  correlation) is the right level of rigor for this question — it
  produced a verdict the prior method could not have produced, found a
  real, generalizable gap, and let two real rules ship against it.
* `matplotlib` and `pandas` remain uncovered for lack of any indexed CVE
  to anchor on — not a gap this round closes; flagging for a future round
  if a different source (e.g. manually curated incident history) becomes
  available.
* SAST046/047 close 2 of 6 confirmed blind spots. The remaining 4 (Vary:
  Cookie cache poisoning, Oracle SQL template injection, deserialization-
  based command injection, missing CSRF protection) are each a different
  vulnerability class needing its own dedicated rule design — out of
  scope for this round, listed here so they aren't lost.
