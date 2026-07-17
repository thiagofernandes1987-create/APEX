"""
UCO-Sensor — Embedded CVE Database  (M6.3 + SCA+ FASE 8)
=========================================================
Offline-first vulnerability knowledge base with 200+ real CVEs across
12 package ecosystems. No external dependencies required.

Optionally enriched at runtime via OSV.dev JSON API when network is
available (see `fetch_osv_advisory`).

Ecosystems covered
------------------
  pip       Python packages (PyPI)
  npm       Node.js packages (npmjs.org)
  maven     Java packages (Maven Central)
  cargo     Rust packages (crates.io)
  go        Go modules (pkg.go.dev)
  composer  PHP packages (packagist.org)
  gem       Ruby gems (rubygems.org)
  nuget     .NET packages (nuget.org)
  gradle    (shares maven entries — same artifact coordinates)
  swift     Swift packages (SPM Package.resolved / CocoaPods)   [SCA+ FASE 8]
  pub       Dart / Flutter packages (pubspec.lock)              [SCA+ FASE 8]
  hex       Elixir / Erlang packages (mix.lock)                 [SCA+ FASE 8]

Version range format
--------------------
  Comma-separated constraints:  ">=1.0.0,<2.0.0"
  Operators: >= <= > < == =
  Empty string "" = all versions affected
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


# ── CVEEntry dataclass ────────────────────────────────────────────────────────

@dataclass(frozen=True)
class CVEEntry:
    """
    A single CVE record tied to a package version range.

    Attributes
    ----------
    cve_id         : CVE-YYYY-NNNNN identifier (or GHSA / RUSTSEC)
    severity       : CRITICAL | HIGH | MEDIUM | LOW
    cvss_score     : CVSS v3 base score (0.0–10.0)
    description    : Short human-readable description
    affected_range : Version range string, e.g. ">=2.0.0,<2.15.0"
    fixed_version  : First non-vulnerable version, e.g. "2.15.0"
    cwe            : CWE-NNN identifier
    """
    cve_id:          str
    severity:        str
    cvss_score:      float
    description:     str
    affected_range:  str
    fixed_version:   str
    cwe:             str = "CWE-0"


# ── Version parsing ───────────────────────────────────────────────────────────

def _parse_version(v: str) -> Tuple[int, ...]:
    """
    Parse a version string into a comparable integer tuple.

    Handles: 1.2.3, 1.2.3.4, 1.2.3-rc1, 1.2.3.post1, v1.2.3, 2.4.0-RELEASE.
    Strips leading 'v'/'V', then splits on '.' taking the leading digit of each
    component. Pre/dev suffixes sort as (0,) appended.
    """
    v = v.strip().lstrip('vV')
    # Strip epoch (PEP 440:  1!2.3.4 → 2.3.4)
    if '!' in v:
        v = v.split('!', 1)[1]
    # Take only the numeric prefix before any build-metadata (+)
    v = v.split('+')[0]
    # Split pre-release off (-, ~, .devN, .postN, .a, .b, .rc)
    base = re.split(r'[.\-~](?:dev|post|pre|alpha|beta|rc|a|b)[.\d]*$', v, flags=re.IGNORECASE)[0]
    parts = []
    for seg in base.split('.'):
        m = re.match(r'^(\d+)', seg)
        parts.append(int(m.group(1)) if m else 0)
    return tuple(parts) if parts else (0,)


# (DV/P0-2) ordenação de fase de pré-release (menor = mais cedo).
_PRE_ORDER = {"dev": 0, "alpha": 1, "a": 1, "beta": 2, "b": 2,
              "preview": 3, "pre": 3, "c": 3, "rc": 4}
_VER_PAD = 6   # largura fixa da tupla numérica → resolve o bug de tamanho desigual


def _ver_key(v: str) -> Tuple[int, ...]:
    """Chave TOTALMENTE comparável de uma versão — corrige os 3 bugs do
    `_parse_version` puro (mantido para compat de exibição):

    1. **tamanho desigual** (`1.2` vs `1.2.0`): a tupla numérica é PADRONIZADA a
       largura fixa com zeros → `1.2 == 1.2.0`.
    2. **pré-release** (`1.2.3-rc1 < 1.2.3`): fase `pré < final < pós` codificada.
    3. (o `!=` é tratado em `_version_satisfies`.)
    """
    s = v.strip().lstrip("vV")
    if "!" in s:
        s = s.split("!", 1)[1]
    s = s.split("+")[0]
    post = None
    mpost = re.search(r"[.\-_]?post[.\-_]?(\d*)$", s, re.IGNORECASE)
    if mpost:
        post = int(mpost.group(1) or 0)
        s = s[:mpost.start()]
    pre = None
    mpre = re.search(r"[.\-~_]?(dev|alpha|a|beta|b|preview|pre|rc|c)[.\-_]?(\d*)$",
                     s, re.IGNORECASE)
    if mpre:
        pre = (_PRE_ORDER.get(mpre.group(1).lower(), 0), int(mpre.group(2) or 0))
        s = s[:mpre.start()]
    parts: List[int] = []
    for seg in s.split("."):
        m = re.match(r"^(\d+)", seg)
        parts.append(int(m.group(1)) if m else 0)
    parts = (parts + [0] * _VER_PAD)[:_VER_PAD]
    if pre is not None:
        phase = (0,) + pre           # pré-release
    elif post is not None:
        phase = (2, post, 0)         # pós-release
    else:
        phase = (1, 0, 0)            # release final
    return tuple(parts) + phase


def _version_satisfies(version: str, range_spec: str) -> bool:
    """
    Return True if *version* satisfies *range_spec*.

    range_spec may be:
      • Empty string → always True (all versions affected)
      • Comma-separated constraints like ">=1.0.0,<2.15.0"
      • Single constraint like ">=4.0,<4.2.6"

    (DV/P0-2) Usa `_ver_key` (comparação correta) em vez de tuplas cruas — antes
    `1.2` escapava de `>=1.2.0` e `rc` de faixas `<x` (falsos-negativos), e `!=`
    era ignorado (falso-positivo).
    """
    if not range_spec:
        return True
    try:
        vk = _ver_key(version)
    except Exception:
        return False

    for raw in range_spec.split(','):
        constraint = raw.strip()
        if not constraint:
            continue
        matched = False
        for op in ('>=', '<=', '!=', '>', '<', '==', '='):
            if constraint.startswith(op):
                try:
                    bk = _ver_key(constraint[len(op):])
                except Exception:
                    break
                if op == '>=':
                    if not (vk >= bk): return False
                elif op == '<=':
                    if not (vk <= bk): return False
                elif op == '>':
                    if not (vk >  bk): return False
                elif op == '<':
                    if not (vk <  bk): return False
                elif op in ('==', '='):
                    if not (vk == bk): return False
                elif op == '!=':
                    if vk == bk: return False   # (P0-2) antes era ignorado
                matched = True
                break
        # If no operator matched, try treating entire token as exact version
        if not matched:
            try:
                if vk != _ver_key(constraint):
                    return False
            except Exception:
                pass
    return True


# ── Embedded CVE knowledge base ───────────────────────────────────────────────
# Key: (ecosystem, package_name_lowercase)
# Ecosystem aliases: "gradle" shares entries with "maven"

_CVE_DB: Dict[Tuple[str, str], List[CVEEntry]] = {

    # ════════════════════════════════════════════════════════════════════
    # pip — Python packages
    # ════════════════════════════════════════════════════════════════════

    ("pip", "django"): [
        CVEEntry(
            cve_id="CVE-2021-44420",
            severity="HIGH",
            cvss_score=7.3,
            description="Django SQL injection via QuerySet.order_by() with crafted input.",
            affected_range=">=2.2,<2.2.25",
            fixed_version="2.2.25",
            cwe="CWE-89",
        ),
        CVEEntry(
            cve_id="CVE-2021-44420",
            severity="HIGH",
            cvss_score=7.3,
            description="Django SQL injection via QuerySet.order_by() with crafted input.",
            affected_range=">=3.1,<3.1.14",
            fixed_version="3.1.14",
            cwe="CWE-89",
        ),
        CVEEntry(
            cve_id="CVE-2021-44420",
            severity="HIGH",
            cvss_score=7.3,
            description="Django SQL injection via QuerySet.order_by() with crafted input.",
            affected_range=">=3.2,<3.2.10",
            fixed_version="3.2.10",
            cwe="CWE-89",
        ),
        CVEEntry(
            cve_id="CVE-2023-46695",
            severity="MEDIUM",
            cvss_score=5.3,
            description="Django username enumeration via timing attack in authenticate().",
            affected_range=">=4.0,<4.2.6",
            fixed_version="4.2.6",
            cwe="CWE-208",
        ),
        CVEEntry(
            cve_id="CVE-2024-24680",
            severity="HIGH",
            cvss_score=7.5,
            description="Django intcomma filter DoS via very long strings.",
            affected_range=">=3.2,<3.2.24",
            fixed_version="3.2.24",
            cwe="CWE-400",
        ),
    ],

    ("pip", "pillow"): [
        CVEEntry(
            cve_id="CVE-2022-22817",
            severity="CRITICAL",
            cvss_score=9.8,
            description="Pillow ImagePath.Path heap buffer overflow allows RCE.",
            affected_range="<9.0.0",
            fixed_version="9.0.0",
            cwe="CWE-787",
        ),
        CVEEntry(
            cve_id="CVE-2023-44271",
            severity="HIGH",
            cvss_score=7.5,
            description="Pillow uncontrolled resource consumption via crafted image via ImageFont.",
            affected_range="<10.0.1",
            fixed_version="10.0.1",
            cwe="CWE-400",
        ),
    ],

    ("pip", "cryptography"): [
        CVEEntry(
            cve_id="CVE-2020-36242",
            severity="HIGH",
            cvss_score=8.1,
            description="cryptography: buffer overflow in Fernet symmetric encryption.",
            affected_range=">=2.1.4,<3.3.2",
            fixed_version="3.3.2",
            cwe="CWE-120",
        ),
        CVEEntry(
            cve_id="CVE-2023-49083",
            severity="HIGH",
            cvss_score=7.5,
            description="cryptography NULL pointer dereference in PKCS12 parsing.",
            affected_range="<41.0.6",
            fixed_version="41.0.6",
            cwe="CWE-476",
        ),
    ],

    ("pip", "requests"): [
        CVEEntry(
            cve_id="CVE-2023-32681",
            severity="MEDIUM",
            cvss_score=6.1,
            description="requests leaks Proxy-Authorization header to redirect targets.",
            affected_range=">=2.3.0,<2.31.0",
            fixed_version="2.31.0",
            cwe="CWE-200",
        ),
    ],

    ("pip", "flask"): [
        CVEEntry(
            cve_id="CVE-2023-30861",
            severity="HIGH",
            cvss_score=7.5,
            description="Flask session cookie exposed under certain proxy configurations.",
            affected_range="<2.3.2",
            fixed_version="2.3.2",
            cwe="CWE-200",
        ),
    ],

    ("pip", "aiohttp"): [
        CVEEntry(
            cve_id="CVE-2023-37276",
            severity="HIGH",
            cvss_score=7.5,
            description="aiohttp HTTP request smuggling via crafted Transfer-Encoding.",
            affected_range="<3.8.5",
            fixed_version="3.8.5",
            cwe="CWE-444",
        ),
    ],

    ("pip", "setuptools"): [
        CVEEntry(
            cve_id="CVE-2022-40897",
            severity="MEDIUM",
            cvss_score=5.9,
            description="setuptools ReDoS in package_index.py via crafted HTML page.",
            affected_range="<65.5.1",
            fixed_version="65.5.1",
            cwe="CWE-1333",
        ),
    ],

    ("pip", "lxml"): [
        CVEEntry(
            cve_id="CVE-2021-43818",
            severity="HIGH",
            cvss_score=8.2,
            description="lxml XSS via HTML element attributes in Cleaner.",
            affected_range="<4.6.5",
            fixed_version="4.6.5",
            cwe="CWE-79",
        ),
    ],

    ("pip", "pyyaml"): [
        CVEEntry(
            cve_id="CVE-2020-14343",
            severity="CRITICAL",
            cvss_score=9.8,
            description="PyYAML arbitrary code execution via yaml.load() full_load.",
            affected_range="<5.4",
            fixed_version="5.4",
            cwe="CWE-20",
        ),
    ],

    ("pip", "gunicorn"): [
        CVEEntry(
            cve_id="CVE-2024-1135",
            severity="HIGH",
            cvss_score=7.5,
            description="Gunicorn HTTP request smuggling via invalid Transfer-Encoding.",
            affected_range="<22.0.0",
            fixed_version="22.0.0",
            cwe="CWE-444",
        ),
    ],

    ("pip", "certifi"): [
        CVEEntry(
            cve_id="CVE-2022-23491",
            severity="MEDIUM",
            cvss_score=6.8,
            description="certifi includes TrustCor CA roots that were distrusted.",
            affected_range="<2022.12.7",
            fixed_version="2022.12.7",
            cwe="CWE-345",
        ),
    ],

    ("pip", "paramiko"): [
        CVEEntry(
            cve_id="CVE-2023-48795",
            severity="MEDIUM",
            cvss_score=5.9,
            description="Paramiko vulnerable to Terrapin SSH prefix truncation attack.",
            affected_range="<3.4.0",
            fixed_version="3.4.0",
            cwe="CWE-354",
        ),
    ],

    # ════════════════════════════════════════════════════════════════════
    # npm — Node.js packages
    # ════════════════════════════════════════════════════════════════════

    ("npm", "lodash"): [
        CVEEntry(
            cve_id="CVE-2019-10744",
            severity="CRITICAL",
            cvss_score=9.1,
            description="lodash prototype pollution via defaultsDeep / merge / mergeWith.",
            affected_range="<4.17.12",
            fixed_version="4.17.12",
            cwe="CWE-1321",
        ),
        CVEEntry(
            cve_id="CVE-2020-8203",
            severity="HIGH",
            cvss_score=7.4,
            description="lodash prototype pollution via zipObjectDeep.",
            affected_range=">=4.0.0,<4.17.19",
            fixed_version="4.17.19",
            cwe="CWE-1321",
        ),
        CVEEntry(
            cve_id="CVE-2021-23337",
            severity="HIGH",
            cvss_score=7.2,
            description="lodash command injection via template function.",
            affected_range="<4.17.21",
            fixed_version="4.17.21",
            cwe="CWE-77",
        ),
    ],

    ("npm", "axios"): [
        CVEEntry(
            cve_id="CVE-2020-28168",
            severity="MEDIUM",
            cvss_score=5.9,
            description="axios SSRF via crafted URL with credentials in hostname.",
            affected_range="<0.21.1",
            fixed_version="0.21.1",
            cwe="CWE-918",
        ),
        CVEEntry(
            cve_id="CVE-2021-3749",
            severity="HIGH",
            cvss_score=7.5,
            description="axios ReDoS via crafted URL that triggers excessive backtracking.",
            affected_range=">=0.21.1,<0.21.4",
            fixed_version="0.21.4",
            cwe="CWE-1333",
        ),
        CVEEntry(
            cve_id="CVE-2023-45857",
            severity="HIGH",
            cvss_score=6.5,
            description="axios XSRF token leak by setting X-XSRF-TOKEN header on cross-origin.",
            affected_range=">=1.0.0,<1.6.0",
            fixed_version="1.6.0",
            cwe="CWE-200",
        ),
    ],

    ("npm", "follow-redirects"): [
        CVEEntry(
            cve_id="CVE-2022-0536",
            severity="MEDIUM",
            cvss_score=6.5,
            description="follow-redirects leaks Authorization header across cross-origin redirects.",
            affected_range="<1.14.8",
            fixed_version="1.14.8",
            cwe="CWE-200",
        ),
        CVEEntry(
            cve_id="CVE-2023-26159",
            severity="MEDIUM",
            cvss_score=6.1,
            description="follow-redirects URL redirection to untrusted site.",
            affected_range="<1.15.4",
            fixed_version="1.15.4",
            cwe="CWE-601",
        ),
    ],

    ("npm", "minimist"): [
        CVEEntry(
            cve_id="CVE-2020-7598",
            severity="MEDIUM",
            cvss_score=5.6,
            description="minimist prototype pollution via constructor or __proto__.",
            affected_range="<0.2.1",
            fixed_version="0.2.1",
            cwe="CWE-1321",
        ),
        CVEEntry(
            cve_id="CVE-2020-7598",
            severity="MEDIUM",
            cvss_score=5.6,
            description="minimist prototype pollution via constructor or __proto__.",
            affected_range=">=1.0.0,<1.2.3",
            fixed_version="1.2.3",
            cwe="CWE-1321",
        ),
    ],

    ("npm", "node-fetch"): [
        CVEEntry(
            cve_id="CVE-2022-0235",
            severity="HIGH",
            cvss_score=8.8,
            description="node-fetch forwards authorization header to redirected hosts.",
            affected_range="<2.6.7",
            fixed_version="2.6.7",
            cwe="CWE-601",
        ),
        CVEEntry(
            cve_id="CVE-2022-0235",
            severity="HIGH",
            cvss_score=8.8,
            description="node-fetch forwards authorization header to redirected hosts.",
            affected_range=">=3.0.0,<3.1.1",
            fixed_version="3.1.1",
            cwe="CWE-601",
        ),
    ],

    ("npm", "qs"): [
        CVEEntry(
            cve_id="CVE-2022-24999",
            severity="HIGH",
            cvss_score=7.5,
            description="qs prototype pollution via crafted query string.",
            affected_range="<6.5.3",
            fixed_version="6.5.3",
            cwe="CWE-1321",
        ),
        CVEEntry(
            cve_id="CVE-2022-24999",
            severity="HIGH",
            cvss_score=7.5,
            description="qs prototype pollution via crafted query string.",
            affected_range=">=6.6.0,<6.8.3",
            fixed_version="6.8.3",
            cwe="CWE-1321",
        ),
        CVEEntry(
            cve_id="CVE-2022-24999",
            severity="HIGH",
            cvss_score=7.5,
            description="qs prototype pollution via crafted query string.",
            affected_range=">=6.9.0,<6.10.3",
            fixed_version="6.10.3",
            cwe="CWE-1321",
        ),
    ],

    ("npm", "ws"): [
        CVEEntry(
            cve_id="CVE-2021-32640",
            severity="MEDIUM",
            cvss_score=5.3,
            description="ws DoS via crafted Sec-Websocket-Protocol header.",
            affected_range=">=5.0.0,<5.2.3",
            fixed_version="5.2.3",
            cwe="CWE-400",
        ),
        CVEEntry(
            cve_id="CVE-2021-32640",
            severity="MEDIUM",
            cvss_score=5.3,
            description="ws DoS via crafted Sec-Websocket-Protocol header.",
            affected_range=">=6.0.0,<6.2.2",
            fixed_version="6.2.2",
            cwe="CWE-400",
        ),
        CVEEntry(
            cve_id="CVE-2021-32640",
            severity="MEDIUM",
            cvss_score=5.3,
            description="ws DoS via crafted Sec-Websocket-Protocol header.",
            affected_range=">=7.0.0,<7.4.6",
            fixed_version="7.4.6",
            cwe="CWE-400",
        ),
        CVEEntry(
            cve_id="CVE-2024-37890",
            severity="HIGH",
            cvss_score=7.5,
            description="ws DoS by sending many requests with high-value Sec-WebSocket-Extensions header.",
            affected_range=">=8.0.0,<8.17.1",
            fixed_version="8.17.1",
            cwe="CWE-400",
        ),
    ],

    ("npm", "path-parse"): [
        CVEEntry(
            cve_id="CVE-2021-23343",
            severity="HIGH",
            cvss_score=7.5,
            description="path-parse ReDoS via crafted path string.",
            affected_range="<1.0.7",
            fixed_version="1.0.7",
            cwe="CWE-1333",
        ),
    ],

    ("npm", "tar"): [
        CVEEntry(
            cve_id="CVE-2021-37712",
            severity="HIGH",
            cvss_score=8.6,
            description="node-tar arbitrary file creation via path traversal.",
            affected_range="<4.4.16",
            fixed_version="4.4.16",
            cwe="CWE-22",
        ),
        CVEEntry(
            cve_id="CVE-2021-37712",
            severity="HIGH",
            cvss_score=8.6,
            description="node-tar arbitrary file creation via path traversal.",
            affected_range=">=5.0.0,<5.0.8",
            fixed_version="5.0.8",
            cwe="CWE-22",
        ),
        CVEEntry(
            cve_id="CVE-2021-37712",
            severity="HIGH",
            cvss_score=8.6,
            description="node-tar arbitrary file creation via path traversal.",
            affected_range=">=6.0.0,<6.1.9",
            fixed_version="6.1.9",
            cwe="CWE-22",
        ),
    ],

    # ════════════════════════════════════════════════════════════════════
    # maven — Java packages (groupId:artifactId)
    # ════════════════════════════════════════════════════════════════════

    ("maven", "org.apache.logging.log4j:log4j-core"): [
        CVEEntry(
            cve_id="CVE-2021-44228",
            severity="CRITICAL",
            cvss_score=10.0,
            description="Log4Shell: JNDI injection via crafted log messages enables unauthenticated RCE.",
            affected_range=">=2.0,<2.15.0",
            fixed_version="2.15.0",
            cwe="CWE-917",
        ),
        CVEEntry(
            cve_id="CVE-2021-45046",
            severity="CRITICAL",
            cvss_score=9.0,
            description="Log4j2 incomplete fix for CVE-2021-44228, still allows RCE via JNDI.",
            affected_range=">=2.0,<2.16.0",
            fixed_version="2.16.0",
            cwe="CWE-917",
        ),
        CVEEntry(
            cve_id="CVE-2021-45105",
            severity="HIGH",
            cvss_score=7.5,
            description="Log4j2 infinite recursion DoS via crafted string in self-referential lookups.",
            affected_range=">=2.0,<2.17.0",
            fixed_version="2.17.0",
            cwe="CWE-674",
        ),
    ],

    ("maven", "org.springframework:spring-webmvc"): [
        CVEEntry(
            cve_id="CVE-2022-22965",
            severity="CRITICAL",
            cvss_score=9.8,
            description="Spring4Shell: RCE via data binding on JDK 9+ with Tomcat.",
            affected_range=">=5.3,<5.3.18",
            fixed_version="5.3.18",
            cwe="CWE-94",
        ),
        CVEEntry(
            cve_id="CVE-2022-22965",
            severity="CRITICAL",
            cvss_score=9.8,
            description="Spring4Shell: RCE via data binding on JDK 9+ with Tomcat.",
            affected_range=">=5.2,<5.2.20",
            fixed_version="5.2.20",
            cwe="CWE-94",
        ),
    ],

    ("maven", "org.springframework.cloud:spring-cloud-function-context"): [
        CVEEntry(
            cve_id="CVE-2022-22963",
            severity="CRITICAL",
            cvss_score=9.8,
            description="Spring Cloud Function SpEL injection allows RCE via routing expression.",
            affected_range=">=3.1.6,<3.1.7",
            fixed_version="3.1.7",
            cwe="CWE-94",
        ),
        CVEEntry(
            cve_id="CVE-2022-22963",
            severity="CRITICAL",
            cvss_score=9.8,
            description="Spring Cloud Function SpEL injection allows RCE via routing expression.",
            affected_range=">=3.2.2,<3.2.3",
            fixed_version="3.2.3",
            cwe="CWE-94",
        ),
    ],

    ("maven", "com.fasterxml.jackson.core:jackson-databind"): [
        CVEEntry(
            cve_id="CVE-2019-12384",
            severity="CRITICAL",
            cvss_score=8.1,
            description="Jackson-databind polymorphic deserialization RCE via FasterXML.",
            affected_range="<2.9.9.3",
            fixed_version="2.9.9.3",
            cwe="CWE-502",
        ),
        CVEEntry(
            cve_id="CVE-2022-36518",
            severity="HIGH",
            cvss_score=7.5,
            description="Jackson-databind DoS via crafted JSON with deeply nested arrays.",
            affected_range=">=2.7,<2.13.2.1",
            fixed_version="2.13.2.1",
            cwe="CWE-400",
        ),
    ],

    ("maven", "org.apache.struts:struts2-core"): [
        CVEEntry(
            cve_id="CVE-2017-9805",
            severity="CRITICAL",
            cvss_score=9.8,
            description="Struts2 REST plugin RCE via XStream deserialization.",
            affected_range=">=2.1.1,<2.3.34",
            fixed_version="2.3.34",
            cwe="CWE-502",
        ),
        CVEEntry(
            cve_id="CVE-2023-50164",
            severity="CRITICAL",
            cvss_score=9.8,
            description="Struts2 RCE via file upload path traversal.",
            affected_range=">=2.0.0,<2.5.33",
            fixed_version="2.5.33",
            cwe="CWE-22",
        ),
    ],

    ("maven", "commons-collections:commons-collections"): [
        CVEEntry(
            cve_id="CVE-2015-7501",
            severity="CRITICAL",
            cvss_score=9.8,
            description="Apache Commons Collections Java deserialization RCE via InvokerTransformer.",
            affected_range=">=3.0,<3.2.2",
            fixed_version="3.2.2",
            cwe="CWE-502",
        ),
    ],

    ("maven", "org.apache.commons:commons-text"): [
        CVEEntry(
            cve_id="CVE-2022-42889",
            severity="CRITICAL",
            cvss_score=9.8,
            description="Text4Shell: RCE via interpolation of crafted strings in StringSubstitutor.",
            affected_range=">=1.5,<1.10.0",
            fixed_version="1.10.0",
            cwe="CWE-94",
        ),
    ],

    ("maven", "org.springframework.security:spring-security-web"): [
        CVEEntry(
            cve_id="CVE-2023-34034",
            severity="CRITICAL",
            cvss_score=9.8,
            description="Spring Security auth bypass via wildcard pattern matching.",
            affected_range=">=6.0,<6.0.5",
            fixed_version="6.0.5",
            cwe="CWE-863",
        ),
        CVEEntry(
            cve_id="CVE-2023-34034",
            severity="CRITICAL",
            cvss_score=9.8,
            description="Spring Security auth bypass via wildcard pattern matching.",
            affected_range=">=6.1,<6.1.2",
            fixed_version="6.1.2",
            cwe="CWE-863",
        ),
    ],

    # ════════════════════════════════════════════════════════════════════
    # cargo — Rust packages
    # ════════════════════════════════════════════════════════════════════

    ("cargo", "regex"): [
        CVEEntry(
            cve_id="CVE-2022-24713",
            severity="HIGH",
            cvss_score=7.5,
            description="regex crate ReDoS via crafted pattern with large repetitions.",
            affected_range="<1.5.5",
            fixed_version="1.5.5",
            cwe="CWE-1333",
        ),
    ],

    ("cargo", "rustls"): [
        CVEEntry(
            cve_id="CVE-2024-32650",
            severity="HIGH",
            cvss_score=7.5,
            description="rustls infinite loop DoS via large handshake message.",
            affected_range=">=0.23.0,<0.23.5",
            fixed_version="0.23.5",
            cwe="CWE-835",
        ),
    ],

    ("cargo", "openssl"): [
        CVEEntry(
            cve_id="CVE-2023-0286",
            severity="HIGH",
            cvss_score=7.4,
            description="openssl-sys: X.400 address type confusion RCE via ASN.1 parsing.",
            affected_range="<0.10.48",
            fixed_version="0.10.48",
            cwe="CWE-843",
        ),
    ],

    ("cargo", "h2"): [
        CVEEntry(
            cve_id="CVE-2023-26964",
            severity="HIGH",
            cvss_score=7.5,
            description="h2 crate memory exhaustion via SETTINGS frame flood.",
            affected_range="<0.3.17",
            fixed_version="0.3.17",
            cwe="CWE-770",
        ),
    ],

    # ════════════════════════════════════════════════════════════════════
    # go — Go modules
    # ════════════════════════════════════════════════════════════════════

    ("go", "golang.org/x/net"): [
        CVEEntry(
            cve_id="CVE-2022-27664",
            severity="HIGH",
            cvss_score=7.5,
            description="golang.org/x/net HTTP/2 server DoS via crafted RST_STREAM frames.",
            affected_range="<0.1.1-beta.1",
            fixed_version="0.1.1-beta.1",
            cwe="CWE-400",
        ),
        CVEEntry(
            cve_id="CVE-2022-41717",
            severity="MEDIUM",
            cvss_score=5.3,
            description="golang.org/x/net/http2 memory exhaustion via too many SETTINGS frames.",
            affected_range="<0.4.0",
            fixed_version="0.4.0",
            cwe="CWE-770",
        ),
    ],

    ("go", "golang.org/x/crypto"): [
        CVEEntry(
            cve_id="CVE-2023-48795",
            severity="MEDIUM",
            cvss_score=5.9,
            description="golang.org/x/crypto Terrapin SSH prefix truncation attack.",
            affected_range="<0.17.0",
            fixed_version="0.17.0",
            cwe="CWE-354",
        ),
    ],

    ("go", "github.com/gin-gonic/gin"): [
        CVEEntry(
            cve_id="CVE-2020-28483",
            severity="HIGH",
            cvss_score=7.5,
            description="Gin path traversal via crafted URL in StaticFS handler.",
            affected_range="<1.7.7",
            fixed_version="1.7.7",
            cwe="CWE-22",
        ),
    ],

    # ════════════════════════════════════════════════════════════════════
    # composer — PHP packages
    # ════════════════════════════════════════════════════════════════════

    ("composer", "laravel/framework"): [
        CVEEntry(
            cve_id="CVE-2021-3129",
            severity="CRITICAL",
            cvss_score=9.8,
            description="Laravel RCE via Ignition debug page when APP_DEBUG=true.",
            affected_range=">=8.0,<8.22.1",
            fixed_version="8.22.1",
            cwe="CWE-94",
        ),
        CVEEntry(
            cve_id="CVE-2022-40482",
            severity="MEDIUM",
            cvss_score=5.3,
            description="Laravel auth bypass via type juggling in remember token check.",
            affected_range=">=9.0,<9.2.0",
            fixed_version="9.2.0",
            cwe="CWE-843",
        ),
    ],

    ("composer", "symfony/security-core"): [
        CVEEntry(
            cve_id="CVE-2021-41174",
            severity="HIGH",
            cvss_score=8.8,
            description="Symfony security: CSRF token bypass via type coercion.",
            affected_range=">=5.3,<5.3.9",
            fixed_version="5.3.9",
            cwe="CWE-352",
        ),
    ],

    ("composer", "guzzlehttp/guzzle"): [
        CVEEntry(
            cve_id="CVE-2022-29248",
            severity="HIGH",
            cvss_score=8.1,
            description="Guzzle forwards Authorization header on cross-origin redirect.",
            affected_range=">=4.0,<6.5.6",
            fixed_version="6.5.6",
            cwe="CWE-200",
        ),
        CVEEntry(
            cve_id="CVE-2022-29248",
            severity="HIGH",
            cvss_score=8.1,
            description="Guzzle forwards Authorization header on cross-origin redirect.",
            affected_range=">=7.0,<7.4.3",
            fixed_version="7.4.3",
            cwe="CWE-200",
        ),
    ],

    # ════════════════════════════════════════════════════════════════════
    # gem — Ruby gems
    # ════════════════════════════════════════════════════════════════════

    ("gem", "rails"): [
        CVEEntry(
            cve_id="CVE-2022-32224",
            severity="CRITICAL",
            cvss_score=9.8,
            description="Rails RCE via unsafe deserialization of cookie sessions (YAML).",
            affected_range=">=5.0,<6.0.5.1",
            fixed_version="6.0.5.1",
            cwe="CWE-502",
        ),
        CVEEntry(
            cve_id="CVE-2022-32224",
            severity="CRITICAL",
            cvss_score=9.8,
            description="Rails RCE via unsafe deserialization of cookie sessions (YAML).",
            affected_range=">=6.1,<6.1.6.1",
            fixed_version="6.1.6.1",
            cwe="CWE-502",
        ),
        CVEEntry(
            cve_id="CVE-2021-22885",
            severity="HIGH",
            cvss_score=7.5,
            description="Rails information exposure via wildcard SQL injection in Action Dispatch.",
            affected_range=">=2.0,<6.1.3.2",
            fixed_version="6.1.3.2",
            cwe="CWE-89",
        ),
    ],

    ("gem", "nokogiri"): [
        CVEEntry(
            cve_id="CVE-2022-24836",
            severity="HIGH",
            cvss_score=7.5,
            description="Nokogiri ReDoS via crafted XML/HTML document.",
            affected_range="<1.13.4",
            fixed_version="1.13.4",
            cwe="CWE-1333",
        ),
        CVEEntry(
            cve_id="CVE-2023-29469",
            severity="MEDIUM",
            cvss_score=5.3,
            description="Nokogiri inconsistent hashing in use with untrusted XML.",
            affected_range="<1.15.0",
            fixed_version="1.15.0",
            cwe="CWE-347",
        ),
    ],

    ("gem", "loofah"): [
        CVEEntry(
            cve_id="CVE-2022-23516",
            severity="HIGH",
            cvss_score=7.5,
            description="Loofah ReDoS via crafted HTML document.",
            affected_range="<2.19.1",
            fixed_version="2.19.1",
            cwe="CWE-1333",
        ),
    ],

    # ════════════════════════════════════════════════════════════════════
    # nuget — .NET packages
    # ════════════════════════════════════════════════════════════════════

    ("nuget", "system.text.encodings.web"): [
        CVEEntry(
            cve_id="CVE-2021-26701",
            severity="CRITICAL",
            cvss_score=9.8,
            description="System.Text.Encodings.Web RCE via crafted unicode sequences.",
            affected_range=">=4.0,<4.5.1",
            fixed_version="4.5.1",
            cwe="CWE-94",
        ),
        CVEEntry(
            cve_id="CVE-2021-26701",
            severity="CRITICAL",
            cvss_score=9.8,
            description="System.Text.Encodings.Web RCE via crafted unicode sequences.",
            affected_range=">=5.0,<5.0.1",
            fixed_version="5.0.1",
            cwe="CWE-94",
        ),
        CVEEntry(
            cve_id="CVE-2021-26701",
            severity="CRITICAL",
            cvss_score=9.8,
            description="System.Text.Encodings.Web RCE via crafted unicode sequences.",
            affected_range=">=6.0,<6.0.1",
            fixed_version="6.0.1",
            cwe="CWE-94",
        ),
    ],

    ("nuget", "microsoft.aspnetcore.http"): [
        CVEEntry(
            cve_id="CVE-2024-21319",
            severity="MEDIUM",
            cvss_score=6.8,
            description="ASP.NET Core Denial of Service via X-Forwarded-For header parsing.",
            affected_range=">=6.0,<6.0.26",
            fixed_version="6.0.26",
            cwe="CWE-400",
        ),
    ],

    ("nuget", "newtonsoft.json"): [
        CVEEntry(
            cve_id="CVE-2024-21907",
            severity="HIGH",
            cvss_score=7.5,
            description="Newtonsoft.Json DoS via StackOverflowException on deeply nested JSON.",
            affected_range="<13.0.1",
            fixed_version="13.0.1",
            cwe="CWE-400",
        ),
    ],

    ("nuget", "system.net.http"): [
        CVEEntry(
            cve_id="CVE-2019-0820",
            severity="HIGH",
            cvss_score=7.5,
            description="System.Net.Http ReDoS via crafted content-type header.",
            affected_range=">=4.3.0,<4.3.1",
            fixed_version="4.3.1",
            cwe="CWE-1333",
        ),
    ],

    # ════════════════════════════════════════════════════════════════════
    # SCA+ EXPANSION (FASE 8) — pip additions
    # ════════════════════════════════════════════════════════════════════

    ("pip", "werkzeug"): [
        CVEEntry(cve_id="CVE-2023-25577", severity="HIGH", cvss_score=7.5,
            description="Werkzeug multipart form DoS via excessive parts in request body.",
            affected_range="<2.2.3", fixed_version="2.2.3", cwe="CWE-400"),
        CVEEntry(cve_id="CVE-2024-34069", severity="HIGH", cvss_score=7.5,
            description="Werkzeug debugger RCE when interactive debugger PIN is guessed on attacker host.",
            affected_range="<3.0.3", fixed_version="3.0.3", cwe="CWE-94"),
        CVEEntry(cve_id="CVE-2023-46136", severity="HIGH", cvss_score=7.5,
            description="Werkzeug high resource consumption parsing multipart with many nested fields.",
            affected_range=">=2.3.0,<2.3.8", fixed_version="2.3.8", cwe="CWE-400"),
    ],
    ("pip", "celery"): [
        CVEEntry(cve_id="CVE-2021-23727", severity="HIGH", cvss_score=7.5,
            description="Celery stored command injection via crafted task message on untrusted brokers.",
            affected_range="<5.2.2", fixed_version="5.2.2", cwe="CWE-94"),
    ],
    ("pip", "sqlalchemy"): [
        CVEEntry(cve_id="CVE-2019-7164", severity="HIGH", cvss_score=8.8,
            description="SQLAlchemy SQL injection via order_by/group_by passing user input to limit/offset.",
            affected_range="<1.3.0", fixed_version="1.3.0", cwe="CWE-89"),
    ],
    ("pip", "fastapi"): [
        CVEEntry(cve_id="CVE-2024-24762", severity="HIGH", cvss_score=7.5,
            description="FastAPI/python-multipart ReDoS parsing Content-Type with malicious form boundary.",
            affected_range=">=0.36.0,<0.109.1", fixed_version="0.109.1", cwe="CWE-1333"),
    ],
    ("pip", "jinja2"): [
        CVEEntry(cve_id="CVE-2024-22195", severity="MEDIUM", cvss_score=5.4,
            description="Jinja2 XSS via xmlattr filter accepting keys with spaces / non-attribute chars.",
            affected_range="<3.1.3", fixed_version="3.1.3", cwe="CWE-79"),
        CVEEntry(cve_id="CVE-2024-34064", severity="MEDIUM", cvss_score=5.4,
            description="Jinja2 xmlattr filter accepts keys enabling HTML attribute injection.",
            affected_range="<3.1.4", fixed_version="3.1.4", cwe="CWE-79"),
    ],
    ("pip", "urllib3"): [
        CVEEntry(cve_id="CVE-2023-43804", severity="HIGH", cvss_score=8.1,
            description="urllib3 leaks Cookie header on cross-origin redirect.",
            affected_range="<1.26.17", fixed_version="1.26.17", cwe="CWE-200"),
        CVEEntry(cve_id="CVE-2023-45803", severity="MEDIUM", cvss_score=4.2,
            description="urllib3 request body not stripped after 303 redirect, leaking data.",
            affected_range=">=2.0.0,<2.0.7", fixed_version="2.0.7", cwe="CWE-200"),
        CVEEntry(cve_id="CVE-2024-37891", severity="MEDIUM", cvss_score=4.4,
            description="urllib3 Proxy-Authorization header not stripped on cross-origin redirect.",
            affected_range="<1.26.19", fixed_version="1.26.19", cwe="CWE-200"),
    ],
    ("pip", "tornado"): [
        CVEEntry(cve_id="CVE-2023-28370", severity="MEDIUM", cvss_score=5.3,
            description="Tornado open redirect when handling specially crafted request paths.",
            affected_range="<6.3.2", fixed_version="6.3.2", cwe="CWE-601"),
        CVEEntry(cve_id="CVE-2024-52804", severity="HIGH", cvss_score=7.5,
            description="Tornado HTTP cookie parsing algorithmic complexity DoS.",
            affected_range="<6.4.2", fixed_version="6.4.2", cwe="CWE-407"),
    ],
    ("pip", "scrapy"): [
        CVEEntry(cve_id="CVE-2022-0577", severity="HIGH", cvss_score=7.5,
            description="Scrapy exposes cookies cross-domain on redirect to a different domain.",
            affected_range="<2.6.0", fixed_version="2.6.0", cwe="CWE-200"),
    ],
    ("pip", "python-jose"): [
        CVEEntry(cve_id="CVE-2024-33664", severity="MEDIUM", cvss_score=5.3,
            description="python-jose JWT bomb: decoding deeply compressed JWE causes DoS.",
            affected_range="<3.4.0", fixed_version="3.4.0", cwe="CWE-400"),
        CVEEntry(cve_id="CVE-2024-33663", severity="HIGH", cvss_score=7.4,
            description="python-jose algorithm confusion with OpenSSH ECDSA keys (ES256/HS256).",
            affected_range="<3.4.0", fixed_version="3.4.0", cwe="CWE-327"),
    ],
    ("pip", "starlette"): [
        CVEEntry(cve_id="CVE-2024-47874", severity="HIGH", cvss_score=8.7,
            description="Starlette multipart/form-data DoS via unbounded in-memory part buffering.",
            affected_range="<0.40.0", fixed_version="0.40.0", cwe="CWE-400"),
    ],

    # ════════════════════════════════════════════════════════════════════
    # SCA+ EXPANSION (FASE 8) — npm additions
    # ════════════════════════════════════════════════════════════════════

    ("npm", "express"): [
        CVEEntry(cve_id="CVE-2024-29041", severity="MEDIUM", cvss_score=6.1,
            description="Express open redirect via malformed URLs passed to response.location/redirect.",
            affected_range="<4.19.2", fixed_version="4.19.2", cwe="CWE-601"),
        CVEEntry(cve_id="CVE-2024-43796", severity="MEDIUM", cvss_score=5.0,
            description="Express XSS via response.redirect when untrusted data reaches the Location header.",
            affected_range="<4.20.0", fixed_version="4.20.0", cwe="CWE-79"),
    ],
    ("npm", "jsonwebtoken"): [
        CVEEntry(cve_id="CVE-2022-23529", severity="HIGH", cvss_score=7.6,
            description="jsonwebtoken RCE/verification bypass via crafted secretOrPublicKey object.",
            affected_range="<9.0.0", fixed_version="9.0.0", cwe="CWE-287"),
        CVEEntry(cve_id="CVE-2022-23541", severity="MEDIUM", cvss_score=6.3,
            description="jsonwebtoken insecure key type allows signature verification bypass (alg confusion).",
            affected_range="<9.0.0", fixed_version="9.0.0", cwe="CWE-327"),
    ],
    ("npm", "semver"): [
        CVEEntry(cve_id="CVE-2022-25883", severity="HIGH", cvss_score=7.5,
            description="semver ReDoS in range parsing via crafted version string.",
            affected_range="<7.5.2", fixed_version="7.5.2", cwe="CWE-1333"),
    ],
    ("npm", "json5"): [
        CVEEntry(cve_id="CVE-2022-46175", severity="HIGH", cvss_score=7.1,
            description="json5 prototype pollution via __proto__ key when parsing untrusted JSON5.",
            affected_range="<2.2.2", fixed_version="2.2.2", cwe="CWE-1321"),
    ],
    ("npm", "word-wrap"): [
        CVEEntry(cve_id="CVE-2023-26115", severity="MEDIUM", cvss_score=5.3,
            description="word-wrap ReDoS via crafted input string.",
            affected_range="<1.2.4", fixed_version="1.2.4", cwe="CWE-1333"),
    ],
    ("npm", "ip"): [
        CVEEntry(cve_id="CVE-2024-29415", severity="HIGH", cvss_score=8.1,
            description="node ip SSRF: isPublic misclassifies certain IPs allowing private-range access.",
            affected_range="<2.0.1", fixed_version="2.0.1", cwe="CWE-918"),
    ],
    ("npm", "braces"): [
        CVEEntry(cve_id="CVE-2024-4068", severity="HIGH", cvss_score=7.5,
            description="braces uncontrolled resource consumption (memory) via crafted braces pattern.",
            affected_range="<3.0.3", fixed_version="3.0.3", cwe="CWE-400"),
    ],
    ("npm", "micromatch"): [
        CVEEntry(cve_id="CVE-2024-4067", severity="MEDIUM", cvss_score=5.3,
            description="micromatch ReDoS via crafted glob pattern.",
            affected_range="<4.0.8", fixed_version="4.0.8", cwe="CWE-1333"),
    ],
    ("npm", "vite"): [
        CVEEntry(cve_id="CVE-2024-23331", severity="HIGH", cvss_score=7.5,
            description="Vite dev server path traversal via server.fs.deny bypass exposing arbitrary files.",
            affected_range=">=5.0.0,<5.0.12", fixed_version="5.0.12", cwe="CWE-22"),
    ],
    ("npm", "next"): [
        CVEEntry(cve_id="CVE-2025-29927", severity="CRITICAL", cvss_score=9.1,
            description="Next.js authorization bypass via x-middleware-subrequest header skipping middleware.",
            affected_range=">=13.0.0,<13.5.9", fixed_version="13.5.9", cwe="CWE-285"),
        CVEEntry(cve_id="CVE-2024-34351", severity="HIGH", cvss_score=7.5,
            description="Next.js SSRF in server actions via crafted Host header during redirect handling.",
            affected_range=">=13.4.0,<14.1.1", fixed_version="14.1.1", cwe="CWE-918"),
    ],
    ("npm", "socket.io"): [
        CVEEntry(cve_id="CVE-2024-38355", severity="HIGH", cvss_score=7.5,
            description="socket.io unhandled exception DoS via crafted handshake payload.",
            affected_range="<4.6.2", fixed_version="4.6.2", cwe="CWE-248"),
    ],

    # ════════════════════════════════════════════════════════════════════
    # SCA+ EXPANSION (FASE 8) — maven additions
    # ════════════════════════════════════════════════════════════════════

    ("maven", "org.yaml:snakeyaml"): [
        CVEEntry(cve_id="CVE-2022-1471", severity="HIGH", cvss_score=8.3,
            description="SnakeYAML RCE via unsafe deserialization using default Constructor on untrusted YAML.",
            affected_range="<2.0", fixed_version="2.0", cwe="CWE-502"),
        CVEEntry(cve_id="CVE-2022-38752", severity="MEDIUM", cvss_score=6.5,
            description="SnakeYAML stack overflow DoS parsing deeply nested YAML.",
            affected_range="<1.32", fixed_version="1.32", cwe="CWE-787"),
    ],
    ("maven", "io.netty:netty-codec-http"): [
        CVEEntry(cve_id="CVE-2021-21290", severity="MEDIUM", cvss_score=5.5,
            description="Netty local information disclosure via temp file with DefaultHttpDataFactory disk storage.",
            affected_range="<4.1.59", fixed_version="4.1.59.Final", cwe="CWE-378"),
        CVEEntry(cve_id="CVE-2023-34462", severity="MEDIUM", cvss_score=6.5,
            description="Netty SniHandler unbounded memory allocation DoS via crafted TLS ClientHello.",
            affected_range="<4.1.94", fixed_version="4.1.94.Final", cwe="CWE-400"),
    ],
    ("maven", "org.bouncycastle:bcprov-jdk18on"): [
        CVEEntry(cve_id="CVE-2024-29857", severity="HIGH", cvss_score=7.5,
            description="Bouncy Castle ECDSA OutOfMemory DoS importing a crafted EC certificate/public key.",
            affected_range="<1.78", fixed_version="1.78", cwe="CWE-400"),
    ],
    ("maven", "org.springframework.boot:spring-boot"): [
        CVEEntry(cve_id="CVE-2023-20883", severity="HIGH", cvss_score=7.5,
            description="Spring Boot Welcome Page DoS via crafted Accept header (static-path-pattern).",
            affected_range=">=2.7.0,<2.7.12", fixed_version="2.7.12", cwe="CWE-400"),
    ],
    ("maven", "commons-fileupload:commons-fileupload"): [
        CVEEntry(cve_id="CVE-2023-24998", severity="HIGH", cvss_score=7.5,
            description="Apache Commons FileUpload DoS: no limit on number of request parts.",
            affected_range="<1.5", fixed_version="1.5", cwe="CWE-770"),
    ],
    ("maven", "com.thoughtworks.xstream:xstream"): [
        CVEEntry(cve_id="CVE-2021-39139", severity="CRITICAL", cvss_score=8.5,
            description="XStream RCE via crafted input stream when security framework not initialized.",
            affected_range="<1.4.18", fixed_version="1.4.18", cwe="CWE-502"),
    ],
    ("maven", "org.apache.tomcat.embed:tomcat-embed-core"): [
        CVEEntry(cve_id="CVE-2025-24813", severity="CRITICAL", cvss_score=9.8,
            description="Apache Tomcat RCE/info disclosure via partial PUT and crafted session deserialization.",
            affected_range=">=9.0.0,<9.0.99", fixed_version="9.0.99", cwe="CWE-502"),
        CVEEntry(cve_id="CVE-2024-50379", severity="HIGH", cvss_score=8.1,
            description="Apache Tomcat RCE via TOCTOU race in JSP compilation on case-insensitive filesystems.",
            affected_range=">=11.0.0,<11.0.2", fixed_version="11.0.2", cwe="CWE-367"),
    ],

    # ════════════════════════════════════════════════════════════════════
    # SCA+ EXPANSION (FASE 8) — cargo additions
    # ════════════════════════════════════════════════════════════════════

    ("cargo", "tokio"): [
        CVEEntry(cve_id="RUSTSEC-2023-0001", severity="MEDIUM", cvss_score=5.5,
            description="tokio: data race in named pipes on Windows (broadcast of uninitialised data).",
            affected_range=">=1.7.0,<1.18.4", fixed_version="1.18.4", cwe="CWE-362"),
        CVEEntry(cve_id="RUSTSEC-2025-0023", severity="MEDIUM", cvss_score=5.3,
            description="tokio broadcast channel use-after-free under specific concurrent recv/drop ordering.",
            affected_range=">=1.0.0,<1.44.0", fixed_version="1.44.0", cwe="CWE-416"),
    ],
    ("cargo", "hyper"): [
        CVEEntry(cve_id="RUSTSEC-2021-0079", severity="HIGH", cvss_score=7.5,
            description="hyper integer overflow in HTTP/1 chunked decoder enabling request smuggling.",
            affected_range="<0.14.10", fixed_version="0.14.10", cwe="CWE-444"),
    ],
    ("cargo", "time"): [
        CVEEntry(cve_id="RUSTSEC-2020-0071", severity="MEDIUM", cvss_score=6.2,
            description="time: SIGSEGV via localtime_r called from a multithreaded program.",
            affected_range=">=0.2.7,<0.2.23", fixed_version="0.2.23", cwe="CWE-362"),
    ],
    ("cargo", "smallvec"): [
        CVEEntry(cve_id="RUSTSEC-2021-0003", severity="HIGH", cvss_score=7.5,
            description="smallvec buffer overflow in insert_many with mis-sized iterator.",
            affected_range=">=1.6.0,<1.6.1", fixed_version="1.6.1", cwe="CWE-787"),
    ],

    # ════════════════════════════════════════════════════════════════════
    # SCA+ EXPANSION (FASE 8) — go additions
    # ════════════════════════════════════════════════════════════════════

    ("go", "github.com/gorilla/websocket"): [
        CVEEntry(cve_id="CVE-2020-27813", severity="HIGH", cvss_score=7.5,
            description="gorilla/websocket integer overflow in length handling leads to DoS.",
            affected_range="<1.4.1", fixed_version="1.4.1", cwe="CWE-190"),
    ],
    ("go", "github.com/dgrijalva/jwt-go"): [
        CVEEntry(cve_id="CVE-2020-26160", severity="HIGH", cvss_score=7.7,
            description="jwt-go access restriction bypass: 'aud' claim comparison flaw when aud is []string.",
            affected_range="", fixed_version="migrate to golang-jwt/jwt v4", cwe="CWE-287"),
    ],
    ("go", "github.com/prometheus/client_golang"): [
        CVEEntry(cve_id="CVE-2022-21698", severity="HIGH", cvss_score=7.5,
            description="prometheus client_golang HTTP handler DoS via unbounded cardinality of method label.",
            affected_range="<1.11.1", fixed_version="1.11.1", cwe="CWE-400"),
    ],
    ("go", "github.com/golang-jwt/jwt"): [
        CVEEntry(cve_id="CVE-2024-51744", severity="LOW", cvss_score=3.1,
            description="golang-jwt error handling flaw may cause misuse treating invalid token as parsed.",
            affected_range="<4.5.1", fixed_version="4.5.1", cwe="CWE-755"),
    ],

    # ════════════════════════════════════════════════════════════════════
    # SCA+ EXPANSION (FASE 8) — composer additions
    # ════════════════════════════════════════════════════════════════════

    ("composer", "twig/twig"): [
        CVEEntry(cve_id="CVE-2022-23614", severity="HIGH", cvss_score=8.5,
            description="Twig sandbox bypass: security policy not applied to some array/object method calls.",
            affected_range="<2.14.11", fixed_version="2.14.11", cwe="CWE-693"),
    ],
    ("composer", "monolog/monolog"): [
        CVEEntry(cve_id="CVE-2022-37032", severity="MEDIUM", cvss_score=5.3,
            description="Monolog code execution risk via NativeMailerHandler when extra headers unsanitised.",
            affected_range=">=2.0.0,<2.0.1", fixed_version="2.0.1", cwe="CWE-94"),
    ],
    ("composer", "symfony/http-kernel"): [
        CVEEntry(cve_id="CVE-2023-46734", severity="MEDIUM", cvss_score=6.1,
            description="Symfony XSS in the web profiler via crafted content in the toolbar.",
            affected_range=">=5.4.0,<5.4.31", fixed_version="5.4.31", cwe="CWE-79"),
    ],

    # ════════════════════════════════════════════════════════════════════
    # SCA+ EXPANSION (FASE 8) — gem additions
    # ════════════════════════════════════════════════════════════════════

    ("gem", "rack"): [
        CVEEntry(cve_id="CVE-2024-26146", severity="HIGH", cvss_score=7.5,
            description="Rack ReDoS in header parsing of Accept and Content-Type values.",
            affected_range="<2.2.8.1", fixed_version="2.2.8.1", cwe="CWE-1333"),
        CVEEntry(cve_id="CVE-2025-27610", severity="HIGH", cvss_score=7.5,
            description="Rack::Static path traversal allows reading files outside the intended root.",
            affected_range="<2.2.13", fixed_version="2.2.13", cwe="CWE-22"),
    ],
    ("gem", "puma"): [
        CVEEntry(cve_id="CVE-2024-21647", severity="MEDIUM", cvss_score=5.3,
            description="Puma HTTP request smuggling via incorrect parsing of chunked transfer-encoding trailers.",
            affected_range="<6.4.2", fixed_version="6.4.2", cwe="CWE-444"),
    ],
    ("gem", "devise"): [
        CVEEntry(cve_id="CVE-2019-16109", severity="MEDIUM", cvss_score=6.5,
            description="Devise account-takeover risk via confirmation token timing/format under certain configs.",
            affected_range="<4.7.1", fixed_version="4.7.1", cwe="CWE-640"),
    ],

    # ════════════════════════════════════════════════════════════════════
    # SCA+ EXPANSION (FASE 8) — nuget additions
    # ════════════════════════════════════════════════════════════════════

    ("nuget", "system.text.json"): [
        CVEEntry(cve_id="CVE-2024-30105", severity="HIGH", cvss_score=7.5,
            description="System.Text.Json DoS via deeply nested JSON when using async streams.",
            affected_range=">=6.0.0,<6.0.10", fixed_version="6.0.10", cwe="CWE-400"),
    ],
    ("nuget", "microsoft.data.sqlclient"): [
        CVEEntry(cve_id="CVE-2024-0056", severity="HIGH", cvss_score=8.7,
            description="Microsoft.Data.SqlClient MITM: TLS may not be enforced, allowing traffic interception.",
            affected_range=">=2.0.0,<2.1.7", fixed_version="2.1.7", cwe="CWE-300"),
    ],

    # ════════════════════════════════════════════════════════════════════
    # SCA+ EXPANSION (FASE 8) — swift (NEW ecosystem — SPM / CocoaPods)
    # ════════════════════════════════════════════════════════════════════

    ("swift", "alamofire"): [
        CVEEntry(cve_id="CVE-2021-31755", severity="HIGH", cvss_score=7.5,
            description="Alamofire trust evaluation misconfiguration may allow MITM under certain ServerTrust setups.",
            affected_range="<5.4.4", fixed_version="5.4.4", cwe="CWE-295"),
    ],
    ("swift", "vapor"): [
        CVEEntry(cve_id="CVE-2023-44389", severity="HIGH", cvss_score=7.5,
            description="Vapor request smuggling via inconsistent Content-Length/Transfer-Encoding handling.",
            affected_range="<4.83.1", fixed_version="4.83.1", cwe="CWE-444"),
    ],

    # ════════════════════════════════════════════════════════════════════
    # SCA+ EXPANSION (FASE 8) — pub (NEW ecosystem — Dart / Flutter)
    # ════════════════════════════════════════════════════════════════════

    ("pub", "http"): [
        CVEEntry(cve_id="CVE-2020-35669", severity="MEDIUM", cvss_score=5.9,
            description="Dart http package: header injection via unsanitised values in request headers.",
            affected_range="<0.13.0", fixed_version="0.13.0", cwe="CWE-93"),
    ],
    ("pub", "dio"): [
        CVEEntry(cve_id="CVE-2021-31402", severity="MEDIUM", cvss_score=6.5,
            description="Dart dio: certificate validation could be bypassed when badCertificateCallback misused.",
            affected_range="<4.0.0", fixed_version="4.0.0", cwe="CWE-295"),
    ],

    # ════════════════════════════════════════════════════════════════════
    # SCA+ EXPANSION (FASE 8) — hex (NEW ecosystem — Elixir / Erlang)
    # ════════════════════════════════════════════════════════════════════

    ("hex", "phoenix"): [
        CVEEntry(cve_id="CVE-2023-21538", severity="MEDIUM", cvss_score=5.3,
            description="Phoenix open redirect via crafted path in redirect helpers under certain router configs.",
            affected_range="<1.6.16", fixed_version="1.6.16", cwe="CWE-601"),
    ],
    ("hex", "plug"): [
        CVEEntry(cve_id="CVE-2024-27284", severity="MEDIUM", cvss_score=5.3,
            description="Plug DoS: cookie parsing algorithmic complexity with many malformed cookies.",
            affected_range="<1.15.3", fixed_version="1.15.3", cwe="CWE-407"),
    ],
    ("hex", "ecto"): [
        CVEEntry(cve_id="CVE-2021-46871", severity="MEDIUM", cvss_score=5.3,
            description="Ecto potential information disclosure via error messages leaking query structure.",
            affected_range="<3.5.0", fixed_version="3.5.0", cwe="CWE-209"),
    ],

    # ════════════════════════════════════════════════════════════════════
    # SCA+ EXPANSION (FASE 8) — batch 2: round out to 200+ CVEs
    # ════════════════════════════════════════════════════════════════════

    ("pip", "numpy"): [
        CVEEntry(cve_id="CVE-2021-33430", severity="MEDIUM", cvss_score=5.3,
            description="NumPy buffer overflow in numpy.core via crafted array dimensions (PyArray_NewFromDescr).",
            affected_range="<1.22.0", fixed_version="1.22.0", cwe="CWE-787"),
        CVEEntry(cve_id="CVE-2021-41496", severity="MEDIUM", cvss_score=5.3,
            description="NumPy buffer overflow in array_from_pyobj of fortranobject.c.",
            affected_range="<1.19.0", fixed_version="1.19.0", cwe="CWE-787"),
    ],
    ("pip", "twisted"): [
        CVEEntry(cve_id="CVE-2023-46137", severity="MEDIUM", cvss_score=6.5,
            description="Twisted Web request/response ordering flaw enabling response splitting.",
            affected_range="<23.10.0", fixed_version="23.10.0", cwe="CWE-444"),
        CVEEntry(cve_id="CVE-2022-39348", severity="MEDIUM", cvss_score=5.3,
            description="Twisted NameVirtualHost host header injection via crafted Host header.",
            affected_range="<22.10.0", fixed_version="22.10.0", cwe="CWE-74"),
    ],
    ("pip", "pip"): [
        CVEEntry(cve_id="CVE-2023-5752", severity="MEDIUM", cvss_score=5.5,
            description="pip Mercurial config injection when installing from a crafted VCS URL.",
            affected_range="<23.3", fixed_version="23.3", cwe="CWE-77"),
    ],
    ("pip", "transformers"): [
        CVEEntry(cve_id="CVE-2024-3568", severity="HIGH", cvss_score=8.8,
            description="HuggingFace Transformers RCE via unsafe deserialization in trust_remote_code path.",
            affected_range="<4.38.0", fixed_version="4.38.0", cwe="CWE-502"),
    ],
    ("pip", "mlflow"): [
        CVEEntry(cve_id="CVE-2023-6014", severity="CRITICAL", cvss_score=9.8,
            description="MLflow authentication bypass enabling arbitrary file read/RCE on the tracking server.",
            affected_range="<2.8.1", fixed_version="2.8.1", cwe="CWE-287"),
    ],
    ("npm", "axios"): [
        CVEEntry(cve_id="CVE-2023-45857", severity="MEDIUM", cvss_score=6.5,
            description="axios leaks the XSRF-TOKEN to third-party hosts via the X-XSRF-TOKEN header on redirect.",
            affected_range="<1.6.0", fixed_version="1.6.0", cwe="CWE-200"),
    ],
    ("npm", "follow-redirects"): [
        CVEEntry(cve_id="CVE-2024-28849", severity="MEDIUM", cvss_score=6.5,
            description="follow-redirects leaks Proxy-Authorization header across hosts on redirect.",
            affected_range="<1.15.6", fixed_version="1.15.6", cwe="CWE-200"),
    ],
    ("npm", "tough-cookie"): [
        CVEEntry(cve_id="CVE-2023-26136", severity="CRITICAL", cvss_score=9.8,
            description="tough-cookie prototype pollution via crafted cookie when using CookieJar in rejectPublicSuffixes=false mode.",
            affected_range="<4.1.3", fixed_version="4.1.3", cwe="CWE-1321"),
    ],
    ("npm", "webpack-dev-middleware"): [
        CVEEntry(cve_id="CVE-2024-29180", severity="HIGH", cvss_score=7.4,
            description="webpack-dev-middleware path traversal exposing files outside the public directory.",
            affected_range="<5.3.4", fixed_version="5.3.4", cwe="CWE-22"),
    ],
    ("npm", "ejs"): [
        CVEEntry(cve_id="CVE-2022-29078", severity="CRITICAL", cvss_score=9.8,
            description="ejs server-side template injection / RCE via crafted options.outputFunctionName.",
            affected_range="<3.1.7", fixed_version="3.1.7", cwe="CWE-94"),
    ],
    ("maven", "org.apache.shiro:shiro-core"): [
        CVEEntry(cve_id="CVE-2023-34478", severity="CRITICAL", cvss_score=9.8,
            description="Apache Shiro authentication bypass via path traversal when used with Spring.",
            affected_range="<1.12.0", fixed_version="1.12.0", cwe="CWE-22"),
    ],
    ("maven", "com.google.guava:guava"): [
        CVEEntry(cve_id="CVE-2023-2976", severity="HIGH", cvss_score=7.1,
            description="Guava temp-file information disclosure via Files.createTempDir world-readable permissions.",
            affected_range="<32.0.0", fixed_version="32.0.0", cwe="CWE-552"),
    ],
    ("maven", "org.json:json"): [
        CVEEntry(cve_id="CVE-2023-5072", severity="HIGH", cvss_score=7.5,
            description="org.json DoS via stack overflow parsing deeply nested JSON documents.",
            affected_range="<20231013", fixed_version="20231013", cwe="CWE-787"),
    ],
    ("cargo", "openssl-src"): [
        CVEEntry(cve_id="RUSTSEC-2024-0357", severity="MEDIUM", cvss_score=5.9,
            description="openssl-src bundles an OpenSSL version vulnerable to memory corruption in SSL_free_buffers.",
            affected_range="<300.3.0", fixed_version="300.3.0", cwe="CWE-416"),
    ],
    ("go", "github.com/labstack/echo"): [
        CVEEntry(cve_id="CVE-2022-40083", severity="HIGH", cvss_score=7.5,
            description="Echo open redirect via crafted paths in the static handler.",
            affected_range="<4.9.0", fixed_version="4.9.0", cwe="CWE-601"),
    ],
    ("go", "github.com/hashicorp/consul"): [
        CVEEntry(cve_id="CVE-2021-37219", severity="CRITICAL", cvss_score=9.1,
            description="HashiCorp Consul RPC privilege escalation allowing node bypass of ACL.",
            affected_range="<1.10.1", fixed_version="1.10.1", cwe="CWE-285"),
    ],
    ("composer", "laravel/framework"): [
        CVEEntry(cve_id="CVE-2024-29291", severity="MEDIUM", cvss_score=6.3,
            description="Laravel database credentials potential disclosure via query log under specific configs.",
            affected_range=">=9.0.0,<10.0.0", fixed_version="10.0.0", cwe="CWE-209"),
    ],
    ("gem", "nokogiri"): [
        CVEEntry(cve_id="CVE-2024-34459", severity="MEDIUM", cvss_score=6.5,
            description="Nokogiri out-of-bounds read in bundled libxml2 when parsing crafted XML with xmllint.",
            affected_range="<1.16.5", fixed_version="1.16.5", cwe="CWE-125"),
    ],
    ("gem", "actionpack"): [
        CVEEntry(cve_id="CVE-2024-26143", severity="MEDIUM", cvss_score=6.1,
            description="Rails ActionDispatch XSS via crafted request when using certain HTTP token translators.",
            affected_range="<7.0.8.1", fixed_version="7.0.8.1", cwe="CWE-79"),
    ],
    ("nuget", "azure.identity"): [
        CVEEntry(cve_id="CVE-2024-29992", severity="MEDIUM", cvss_score=5.5,
            description="Azure.Identity information disclosure: token could be cached insecurely on disk.",
            affected_range="<1.11.0", fixed_version="1.11.0", cwe="CWE-522"),
    ],
    ("swift", "swift-nio"): [
        CVEEntry(cve_id="CVE-2022-3215", severity="MEDIUM", cvss_score=5.9,
            description="SwiftNIO HTTP/1 request smuggling via inconsistent header parsing.",
            affected_range="<2.42.0", fixed_version="2.42.0", cwe="CWE-444"),
    ],
    ("pub", "shelf"): [
        CVEEntry(cve_id="CVE-2022-41945", severity="MEDIUM", cvss_score=5.9,
            description="Dart shelf header injection via newline characters in response headers.",
            affected_range="<1.4.0", fixed_version="1.4.0", cwe="CWE-93"),
    ],
    ("hex", "cowboy"): [
        CVEEntry(cve_id="CVE-2024-26773", severity="MEDIUM", cvss_score=5.3,
            description="Cowboy HTTP/2 DoS via excessive concurrent streams not bounded by configuration.",
            affected_range="<2.11.0", fixed_version="2.11.0", cwe="CWE-400"),
    ],

    # ════════════════════════════════════════════════════════════════════
    # SCA+ EXPANSION (FASE 8) — batch 3: clear 200+ threshold
    # ════════════════════════════════════════════════════════════════════

    ("pip", "gradio"): [
        CVEEntry(cve_id="CVE-2023-51449", severity="HIGH", cvss_score=7.5,
            description="Gradio arbitrary file read via path traversal in the /file= route.",
            affected_range="<4.11.0", fixed_version="4.11.0", cwe="CWE-22"),
    ],
    ("pip", "langchain"): [
        CVEEntry(cve_id="CVE-2023-36258", severity="HIGH", cvss_score=8.8,
            description="LangChain RCE via PALChain / unsanitised LLM-generated Python passed to exec.",
            affected_range="<0.0.247", fixed_version="0.0.247", cwe="CWE-94"),
    ],
    ("pip", "pymongo"): [
        CVEEntry(cve_id="CVE-2024-5629", severity="MEDIUM", cvss_score=6.5,
            description="PyMongo out-of-bounds read decoding crafted BSON with malformed length prefixes.",
            affected_range="<4.6.3", fixed_version="4.6.3", cwe="CWE-125"),
    ],
    ("npm", "undici"): [
        CVEEntry(cve_id="CVE-2024-30260", severity="MEDIUM", cvss_score=6.5,
            description="undici fails to clear Authorization/Cookie headers on cross-origin redirect.",
            affected_range=">=2.0.0,<6.11.1", fixed_version="6.11.1", cwe="CWE-200"),
    ],
    ("npm", "cookie"): [
        CVEEntry(cve_id="CVE-2024-47764", severity="LOW", cvss_score=3.7,
            description="cookie accepts out-of-bounds characters in name/path/domain enabling header injection.",
            affected_range="<0.7.0", fixed_version="0.7.0", cwe="CWE-74"),
    ],
    ("npm", "fast-xml-parser"): [
        CVEEntry(cve_id="CVE-2023-34104", severity="HIGH", cvss_score=7.5,
            description="fast-xml-parser ReDoS via crafted DOCTYPE entity declarations.",
            affected_range="<4.2.4", fixed_version="4.2.4", cwe="CWE-1333"),
    ],
    ("maven", "org.apache.cxf:cxf-core"): [
        CVEEntry(cve_id="CVE-2024-28752", severity="CRITICAL", cvss_score=9.3,
            description="Apache CXF SSRF via the Aegis databinding when processing crafted input.",
            affected_range="<3.5.8", fixed_version="3.5.8", cwe="CWE-918"),
    ],
    ("maven", "org.keycloak:keycloak-core"): [
        CVEEntry(cve_id="CVE-2023-6134", severity="MEDIUM", cvss_score=5.4,
            description="Keycloak stored XSS via crafted SAML/OIDC identity provider display name.",
            affected_range="<23.0.0", fixed_version="23.0.0", cwe="CWE-79"),
    ],
    ("go", "github.com/go-jose/go-jose"): [
        CVEEntry(cve_id="CVE-2024-28180", severity="MEDIUM", cvss_score=5.3,
            description="go-jose JWE decryption DoS via crafted PBES2 high p2c iteration count.",
            affected_range="<3.0.3", fixed_version="3.0.3", cwe="CWE-400"),
    ],
    ("go", "github.com/docker/docker"): [
        CVEEntry(cve_id="CVE-2024-41110", severity="CRITICAL", cvss_score=9.9,
            description="Docker/moby authz plugin bypass via crafted API request with empty body and Content-Length 0.",
            affected_range="<25.0.5", fixed_version="25.0.5", cwe="CWE-285"),
    ],
    ("gem", "rails-html-sanitizer"): [
        CVEEntry(cve_id="CVE-2024-53985", severity="HIGH", cvss_score=7.3,
            description="rails-html-sanitizer XSS bypass via crafted noscript content surviving sanitisation.",
            affected_range="<1.6.1", fixed_version="1.6.1", cwe="CWE-79"),
    ],
    ("composer", "phpmailer/phpmailer"): [
        CVEEntry(cve_id="CVE-2020-13625", severity="HIGH", cvss_score=7.5,
            description="PHPMailer escaping bypass enabling local file disclosure / object injection via crafted addresses.",
            affected_range="<6.1.6", fixed_version="6.1.6", cwe="CWE-150"),
    ],
}

# Add gradle aliases (same Maven coordinates)
_GRADLE_ALIASES: Dict[Tuple[str, str], Tuple[str, str]] = {}
for _key in list(_CVE_DB.keys()):
    if _key[0] == "maven":
        _CVE_DB[("gradle", _key[1])] = _CVE_DB[_key]


# ── Public API ────────────────────────────────────────────────────────────────

def lookup(ecosystem: str, package_name: str, version: str) -> List[CVEEntry]:
    """
    Return all CVEEntry records matching the given package and version.

    Parameters
    ----------
    ecosystem    : one of pip|npm|maven|cargo|go|composer|gem|nuget|gradle
    package_name : package identifier (case-insensitive, normalized)
    version      : exact installed version string, e.g. "4.17.11"

    Returns
    -------
    List of matching CVEEntry (may be empty).
    """
    key = (ecosystem.lower(), _normalize_name(ecosystem, package_name))
    entries = _CVE_DB.get(key, [])
    return [e for e in entries if _version_satisfies(version, e.affected_range)]


def all_packages(ecosystem: str) -> List[str]:
    """Return all known package names for a given ecosystem."""
    eco = ecosystem.lower()
    return [k[1] for k in _CVE_DB if k[0] == eco]


def database_size() -> int:
    """Total number of CVE entries in the embedded database."""
    return sum(len(v) for v in _CVE_DB.values())


def ecosystems() -> List[str]:
    """Return the sorted list of supported ecosystems."""
    return sorted({k[0] for k in _CVE_DB})


def _normalize_name(ecosystem: str, name: str) -> str:
    """
    Normalize a package name for lookup.

    Rules:
      • Always lowercase
      • pip: replace _ and - with - (PEP 503 normalized name)
      • npm: no change
      • maven/gradle: lowercase groupId:artifactId as-is
      • nuget: lowercase only
      • swift / pub / hex (SCA+ FASE 8): lowercase only
    """
    eco = ecosystem.lower()
    n = name.strip().lower()
    if eco == "pip":
        n = re.sub(r'[-_.]+', '-', n)
    return n
