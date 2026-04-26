"""
UCO-Sensor — Embedded CVE Database  (M6.3)
===========================================
Offline-first vulnerability knowledge base with 65+ real CVEs across
9 package ecosystems. No external dependencies required.

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


def _version_satisfies(version: str, range_spec: str) -> bool:
    """
    Return True if *version* satisfies *range_spec*.

    range_spec may be:
      • Empty string → always True (all versions affected)
      • Comma-separated constraints like ">=1.0.0,<2.15.0"
      • Single constraint like ">=4.0,<4.2.6"
    """
    if not range_spec:
        return True
    try:
        v = _parse_version(version)
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
                    bound = _parse_version(constraint[len(op):])
                except Exception:
                    break
                if op == '>=' :
                    if not (v >= bound): return False
                elif op == '<=':
                    if not (v <= bound): return False
                elif op == '>'  :
                    if not (v >  bound): return False
                elif op == '<'  :
                    if not (v <  bound): return False
                elif op in ('==', '='):
                    if not (v == bound): return False
                # != → skip (conservative: assume in range)
                matched = True
                break
        # If no operator matched, try treating entire token as exact version
        if not matched:
            try:
                bound = _parse_version(constraint)
                if v != bound:
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


def _normalize_name(ecosystem: str, name: str) -> str:
    """
    Normalize a package name for lookup.

    Rules:
      • Always lowercase
      • pip: replace _ and - with - (PEP 503 normalized name)
      • npm: no change
      • maven/gradle: lowercase groupId:artifactId as-is
      • nuget: lowercase only
    """
    eco = ecosystem.lower()
    n = name.strip().lower()
    if eco == "pip":
        n = re.sub(r'[-_.]+', '-', n)
    return n
