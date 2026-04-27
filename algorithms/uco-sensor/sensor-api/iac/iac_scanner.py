"""
UCO-Sensor — IaC Misconfiguration Scanner  (M6.4)
==================================================
Offline-first Infrastructure-as-Code security scanner.

Ecosystems supported
--------------------
  Dockerfile           — container image build instructions
  docker-compose.yml   — Docker Compose service definitions
  Kubernetes YAML      — Pod, Deployment, StatefulSet, DaemonSet, Job, CronJob
  Terraform .tf        — HashiCorp Configuration Language resource blocks
  Helm values.yaml     — Helm chart default values

Rule categories
---------------
  PRIVILEGE   — privilege escalation, root user, SYS_ADMIN caps, securityContext
  NETWORK     — exposed sensitive ports, hostNetwork, hostPort
  SECRET      — plaintext secrets, env-var passwords, hard-coded tokens
  RESOURCE    — missing CPU/memory limits, missing liveness probes
  IMAGE       — mutable :latest tag, privileged containers
  STORAGE     — writable root FS, hostPath volumes, world-readable mounts
  CONFIG      — missing namespaces, missing labels, missing replicas limits

Each finding contributes to `iac_misconfig_count` and `iac_privilege_score`
in SecurityVector.

No external dependencies — pure Python stdlib (re, json, pathlib).
YAML is parsed with the stdlib `re`-based scanner for k8s and Helm files;
a best-effort regex extractor is used for Terraform HCL.

References
----------
CIS Docker Benchmark v1.6 (2022)
CIS Kubernetes Benchmark v1.8 (2023)
NSA/CISA Kubernetes Hardening Guide (2023)
Terraform Security Best Practices — HashiCorp (2024)
"""
from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple


# ─── Severity & SQALE ────────────────────────────────────────────────────────

_SQALE: Dict[str, int] = {
    "CRITICAL": 240,
    "HIGH":     120,
    "MEDIUM":    60,
    "LOW":       30,
}

# Privilege score per severity — how much does a finding escalate privilege risk?
_PRIV_SCORE: Dict[str, float] = {
    "CRITICAL": 1.0,
    "HIGH":     0.6,
    "MEDIUM":   0.3,
    "LOW":      0.1,
}


# ─── Data structures ─────────────────────────────────────────────────────────

@dataclass
class IaCFinding:
    """A single IaC misconfiguration finding."""
    rule_id:      str    # e.g. "IAC001"
    category:     str    # PRIVILEGE | NETWORK | SECRET | RESOURCE | IMAGE | STORAGE | CONFIG
    severity:     str    # CRITICAL | HIGH | MEDIUM | LOW
    title:        str
    description:  str
    source_file:  str
    line_number:  int    = 0
    debt_minutes: int    = field(init=False)
    priv_score:   float  = field(init=False)

    def __post_init__(self) -> None:
        self.debt_minutes = _SQALE.get(self.severity, 30)
        self.priv_score   = _PRIV_SCORE.get(self.severity, 0.1)

    def to_dict(self) -> Dict:
        return {
            "rule_id":      self.rule_id,
            "category":     self.category,
            "severity":     self.severity,
            "title":        self.title,
            "description":  self.description,
            "source_file":  self.source_file,
            "line_number":  self.line_number,
            "debt_minutes": self.debt_minutes,
        }


@dataclass
class IaCScanResult:
    """Aggregate result for one IaC scan session."""
    findings:          List[IaCFinding] = field(default_factory=list)
    files_scanned:     int = 0
    scan_duration_ms:  float = 0.0
    root:              str = ""

    @property
    def total_findings(self) -> int:
        return len(self.findings)

    @property
    def max_privilege_score(self) -> float:
        """Highest privilege-escalation score among all findings [0.0–1.0]."""
        if not self.findings:
            return 0.0
        return max(f.priv_score for f in self.findings)

    @property
    def status(self) -> str:
        sevs = {f.severity for f in self.findings}
        if "CRITICAL" in sevs:
            return "CRITICAL"
        if "HIGH" in sevs:
            return "HIGH"
        if "MEDIUM" in sevs:
            return "MEDIUM"
        if "LOW" in sevs:
            return "LOW"
        return "PASS"

    def summary(self) -> Dict:
        by_sev: Dict[str, int] = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
        by_cat: Dict[str, int] = {}
        for f in self.findings:
            by_sev[f.severity] = by_sev.get(f.severity, 0) + 1
            by_cat[f.category] = by_cat.get(f.category, 0) + 1
        debt = sum(f.debt_minutes for f in self.findings)
        return {
            "status":            self.status,
            "total_findings":    self.total_findings,
            "by_severity":       by_sev,
            "by_category":       by_cat,
            "total_debt_minutes":debt,
            "files_scanned":     self.files_scanned,
            "scan_duration_ms":  round(self.scan_duration_ms, 2),
        }

    def to_dict(self) -> Dict:
        return {
            **self.summary(),
            "findings": [f.to_dict() for f in self.findings],
            "root":     self.root,
        }


# ─── Rule catalogue ──────────────────────────────────────────────────────────
#
# Format: (rule_id, category, severity, title, description, regex_pattern)
# Patterns are matched line-by-line against the file content.
# ─────────────────────────────────────────────────────────────────────────────

# ── Dockerfile rules ─────────────────────────────────────────────────────────
_DOCKERFILE_RULES: List[Tuple] = [
    (
        "IAC-D001", "PRIVILEGE", "HIGH",
        "Container runs as root",
        "No USER instruction found — container defaults to root. Add 'USER nonroot'.",
        None,   # special: absence rule, handled separately
    ),
    (
        "IAC-D002", "IMAGE", "MEDIUM",
        "Mutable :latest tag",
        "Using ':latest' image tag makes builds non-reproducible. Pin to a digest or exact version.",
        re.compile(r'^\s*FROM\s+\S+:latest', re.IGNORECASE | re.MULTILINE),
    ),
    (
        "IAC-D003", "IMAGE", "LOW",
        "Base image tag is missing",
        "FROM without a tag defaults to :latest. Specify an explicit version.",
        re.compile(r'^\s*FROM\s+[^\s:]+\s*$', re.MULTILINE),
    ),
    (
        "IAC-D004", "SECRET", "CRITICAL",
        "Hardcoded password/secret in ENV",
        "ENV instruction contains a variable whose name or value looks like a secret. Use Docker secrets or build args.",
        re.compile(
            r'^\s*ENV\s+.*?(?:PASSWORD|SECRET|TOKEN|API_KEY|PRIVATE_KEY|ACCESS_KEY)\s*=\s*\S+',
            re.IGNORECASE | re.MULTILINE,
        ),
    ),
    (
        "IAC-D005", "SECRET", "HIGH",
        "Hardcoded password/secret in ARG",
        "ARG with a secret-like name may leak into image layer metadata.",
        re.compile(
            r'^\s*ARG\s+(?:PASSWORD|SECRET|TOKEN|API_KEY|PRIVATE_KEY|ACCESS_KEY)',
            re.IGNORECASE | re.MULTILINE,
        ),
    ),
    (
        "IAC-D006", "PRIVILEGE", "HIGH",
        "Privileged capability added via --cap-add SYS_ADMIN",
        "SYS_ADMIN gives near-root capabilities to the container.",
        re.compile(r'--cap-add\s+(?:SYS_ADMIN|ALL)', re.IGNORECASE),
    ),
    (
        "IAC-D007", "NETWORK", "MEDIUM",
        "Sensitive port exposed (22/2375/2376)",
        "Exposing SSH or Docker daemon ports increases attack surface.",
        re.compile(r'^\s*EXPOSE\s+(?:22|2375|2376)\b', re.MULTILINE),
    ),
    (
        "IAC-D008", "CONFIG", "LOW",
        "No HEALTHCHECK defined",
        "Containers without HEALTHCHECK cannot be automatically restarted on failure.",
        None,   # absence rule
    ),
    (
        "IAC-D009", "SECRET", "HIGH",
        "Plaintext secret copied into image",
        "COPY or ADD of files matching *.pem, *.key, id_rsa, *.p12 bakes secrets into the image.",
        re.compile(
            r'^\s*(?:COPY|ADD)\s+.*?(?:\.pem|\.key|id_rsa|\.p12|\.pfx|\.crt|\.cer)',
            re.IGNORECASE | re.MULTILINE,
        ),
    ),
    (
        "IAC-D010", "STORAGE", "MEDIUM",
        "ADD used instead of COPY",
        "ADD has implicit tar extraction and URL fetching — prefer COPY for local files.",
        re.compile(r'^\s*ADD\s+(?!https?://)', re.MULTILINE),
    ),
]

# ── docker-compose rules ─────────────────────────────────────────────────────
_COMPOSE_RULES: List[Tuple] = [
    (
        "IAC-C001", "PRIVILEGE", "CRITICAL",
        "Privileged container in Compose",
        "privileged: true grants all Linux capabilities to the container.",
        re.compile(r'^\s*privileged\s*:\s*true', re.IGNORECASE | re.MULTILINE),
    ),
    (
        "IAC-C002", "NETWORK", "HIGH",
        "Host network mode in Compose",
        "network_mode: host bypasses Docker network isolation.",
        re.compile(r'network_mode\s*:\s*["\']?host["\']?', re.IGNORECASE),
    ),
    (
        "IAC-C003", "SECRET", "CRITICAL",
        "Hardcoded secret in environment block",
        "Plaintext passwords/secrets in environment: block are committed to source control.",
        re.compile(
            r'^\s+(?:PASSWORD|SECRET|TOKEN|API_KEY|PRIVATE_KEY|ACCESS_KEY)\s*:\s*\S+',
            re.IGNORECASE | re.MULTILINE,
        ),
    ),
    (
        "IAC-C004", "STORAGE", "HIGH",
        "Host path mounted as volume",
        "Mounting host directories (/etc, /var, /proc) can expose sensitive data.",
        re.compile(
            r'^\s+-\s+["\']?/(?:etc|var|proc|sys|dev|root|home)',
            re.IGNORECASE | re.MULTILINE,
        ),
    ),
    (
        "IAC-C005", "IMAGE", "MEDIUM",
        "Mutable :latest image tag in Compose",
        "Using :latest in Compose makes deployments non-reproducible.",
        re.compile(r'image\s*:\s*\S+:latest', re.IGNORECASE),
    ),
    (
        "IAC-C006", "PRIVILEGE", "HIGH",
        "SYS_ADMIN capability added in Compose",
        "cap_add: SYS_ADMIN provides near-root access.",
        re.compile(r'SYS_ADMIN', re.MULTILINE),
    ),
    (
        "IAC-C007", "RESOURCE", "MEDIUM",
        "No memory limit defined in Compose",
        "Services without memory limits can exhaust host resources.",
        None,   # absence rule
    ),
    (
        "IAC-C008", "NETWORK", "MEDIUM",
        "Sensitive host port exposed in Compose",
        "Port 22 (SSH) or Docker daemon ports exposed on host.",
        re.compile(r'["\']?(?:0\.0\.0\.0:)?(?:22|2375|2376):', re.MULTILINE),
    ),
]

# ── Kubernetes rules ──────────────────────────────────────────────────────────
_K8S_RULES: List[Tuple] = [
    (
        "IAC-K001", "PRIVILEGE", "CRITICAL",
        "Privileged container in k8s Pod",
        "securityContext.privileged: true grants all capabilities to the container.",
        re.compile(r'privileged\s*:\s*true', re.IGNORECASE),
    ),
    (
        "IAC-K002", "PRIVILEGE", "HIGH",
        "Container runs as root UID",
        "runAsUser: 0 runs the container as root. Use a non-zero UID.",
        re.compile(r'runAsUser\s*:\s*0\b'),
    ),
    (
        "IAC-K003", "PRIVILEGE", "HIGH",
        "allowPrivilegeEscalation not disabled",
        "allowPrivilegeEscalation: false should be set in every container securityContext.",
        None,   # absence rule
    ),
    (
        "IAC-K004", "NETWORK", "HIGH",
        "hostNetwork enabled",
        "hostNetwork: true removes network namespace isolation.",
        re.compile(r'hostNetwork\s*:\s*true'),
    ),
    (
        "IAC-K005", "NETWORK", "HIGH",
        "hostPID enabled",
        "hostPID: true lets containers see all host processes.",
        re.compile(r'hostPID\s*:\s*true'),
    ),
    (
        "IAC-K006", "SECRET", "CRITICAL",
        "Hardcoded secret in env valueFrom is missing — plaintext value used",
        "Environment variable contains a plaintext secret. Use secretKeyRef.",
        re.compile(
            r'name\s*:\s*(?:PASSWORD|SECRET|TOKEN|API_KEY|PRIVATE_KEY)[^\n]*\n\s+value\s*:\s*\S+',
            re.IGNORECASE | re.DOTALL,
        ),
    ),
    (
        "IAC-K007", "RESOURCE", "MEDIUM",
        "No resource limits defined for container",
        "Containers without CPU/memory limits can exhaust node resources.",
        None,   # absence rule (handled per-container)
    ),
    (
        "IAC-K008", "STORAGE", "HIGH",
        "hostPath volume used",
        "hostPath volumes mount host filesystem directories — avoid in production.",
        re.compile(r'hostPath\s*:'),
    ),
    (
        "IAC-K009", "PRIVILEGE", "MEDIUM",
        "Capability SYS_ADMIN added",
        "Adding SYS_ADMIN grants extensive kernel privileges.",
        re.compile(r'SYS_ADMIN'),
    ),
    (
        "IAC-K010", "IMAGE", "MEDIUM",
        "Mutable :latest image tag in k8s",
        "Using :latest with imagePullPolicy: IfNotPresent can lead to drift.",
        re.compile(r'image\s*:\s*\S+:latest'),
    ),
    (
        "IAC-K011", "CONFIG", "LOW",
        "No namespace specified",
        "Resources without explicit namespace deploy to 'default' — use dedicated namespaces.",
        None,   # absence rule
    ),
    (
        "IAC-K012", "STORAGE", "MEDIUM",
        "readOnlyRootFilesystem not enabled",
        "readOnlyRootFilesystem: true prevents container from writing to its root FS.",
        None,   # absence rule
    ),
]

# ── Terraform rules ───────────────────────────────────────────────────────────
_TERRAFORM_RULES: List[Tuple] = [
    (
        "IAC-T001", "NETWORK", "HIGH",
        "Security group allows SSH from 0.0.0.0/0",
        "Inbound SSH (port 22) open to the internet is a critical attack vector.",
        re.compile(
            r'from_port\s*=\s*22[^\n]*\n(?:[^\n]*\n){0,3}[^\n]*cidr_blocks\s*=\s*\[["\']0\.0\.0\.0/0["\']',
            re.DOTALL,
        ),
    ),
    (
        "IAC-T002", "NETWORK", "CRITICAL",
        "Security group allows all traffic (0.0.0.0/0 on port 0)",
        "A wildcard ingress rule allows all inbound traffic.",
        re.compile(
            r'from_port\s*=\s*0[^\n]*\n(?:[^\n]*\n){0,3}[^\n]*cidr_blocks\s*=\s*\[["\']0\.0\.0\.0/0["\']',
            re.DOTALL,
        ),
    ),
    (
        "IAC-T003", "STORAGE", "HIGH",
        "S3 bucket is publicly accessible",
        "acl = \"public-read\" or \"public-read-write\" exposes bucket contents to the internet.",
        re.compile(r'acl\s*=\s*["\']public-(?:read|read-write)["\']', re.IGNORECASE),
    ),
    (
        "IAC-T004", "STORAGE", "HIGH",
        "S3 bucket versioning disabled",
        "Without versioning, deleted/overwritten objects cannot be recovered.",
        None,   # absence rule: versioning block absent
    ),
    (
        "IAC-T005", "SECRET", "CRITICAL",
        "Hardcoded credentials in Terraform",
        "AWS access_key / secret_key hardcoded in provider or resource block.",
        re.compile(
            r'(?:access_key|secret_key|password|private_key)\s*=\s*["\'][A-Za-z0-9+/=]{8,}["\']',
            re.IGNORECASE,
        ),
    ),
    (
        "IAC-T006", "PRIVILEGE", "HIGH",
        "IAM policy allows iam:PassRole to *",
        "Overly permissive PassRole enables privilege escalation in AWS.",
        re.compile(r'iam:PassRole'),
    ),
    (
        "IAC-T007", "PRIVILEGE", "CRITICAL",
        "IAM policy allows * actions on * resources",
        "Admin-equivalent policy grants unrestricted AWS access.",
        re.compile(r'"Action"\s*:\s*"\*"'),
    ),
    (
        "IAC-T008", "NETWORK", "MEDIUM",
        "RDS instance publicly accessible",
        "publicly_accessible = true exposes the database to the internet.",
        re.compile(r'publicly_accessible\s*=\s*true', re.IGNORECASE),
    ),
    (
        "IAC-T009", "STORAGE", "MEDIUM",
        "EBS volume not encrypted",
        "encrypted = false on aws_ebs_volume leaves data at rest unprotected.",
        re.compile(r'encrypted\s*=\s*false', re.IGNORECASE),
    ),
    (
        "IAC-T010", "CONFIG", "MEDIUM",
        "Terraform state backend not configured",
        "Without a remote backend, state files are local and not shared securely.",
        None,   # absence rule
    ),
    (
        "IAC-T011", "NETWORK", "HIGH",
        "Security group allows RDP from 0.0.0.0/0",
        "Inbound RDP (port 3389) open to the internet.",
        re.compile(
            r'from_port\s*=\s*3389[^\n]*\n(?:[^\n]*\n){0,3}[^\n]*cidr_blocks\s*=\s*\[["\']0\.0\.0\.0/0["\']',
            re.DOTALL,
        ),
    ),
    (
        "IAC-T012", "PRIVILEGE", "HIGH",
        "EC2 instance has IAM role with broad permissions",
        "aws_iam_instance_profile attached without least-privilege policy review.",
        re.compile(r'iam_instance_profile\s*='),
    ),
]

# ── Helm / values.yaml rules ─────────────────────────────────────────────────
_HELM_RULES: List[Tuple] = [
    (
        "IAC-H001", "PRIVILEGE", "CRITICAL",
        "Helm values enable privileged containers",
        "securityContext.privileged: true found in Helm values.",
        re.compile(r'privileged\s*:\s*true', re.IGNORECASE),
    ),
    (
        "IAC-H002", "NETWORK", "HIGH",
        "Helm values disable network policy",
        "networkPolicy.enabled: false leaves pods without ingress/egress restrictions.",
        re.compile(r'networkPolicy\s*:[^\n]*\n\s+enabled\s*:\s*false', re.DOTALL),
    ),
    (
        "IAC-H003", "SECRET", "CRITICAL",
        "Plaintext secret in Helm values",
        "Helm values.yaml contains what looks like a plaintext password or token.",
        re.compile(
            r'(?:password|secret|token|apiKey|privateKey)\s*:\s*["\']?\S{6,}["\']?',
            re.IGNORECASE,
        ),
    ),
    (
        "IAC-H004", "IMAGE", "MEDIUM",
        "Helm image tag is 'latest'",
        "image.tag: latest makes Helm releases non-reproducible.",
        re.compile(r'tag\s*:\s*["\']?latest["\']?', re.IGNORECASE),
    ),
    (
        "IAC-H005", "RESOURCE", "MEDIUM",
        "Helm values missing resource limits",
        "resources.limits is absent — containers may exhaust node resources.",
        None,   # absence rule
    ),
    (
        "IAC-H006", "CONFIG", "LOW",
        "Helm replicaCount is 1 (no HA)",
        "Single replica has no fault tolerance. Set replicaCount ≥ 2 for HA.",
        re.compile(r'replicaCount\s*:\s*1\b'),
    ),
]


# ─── IaCScanner ──────────────────────────────────────────────────────────────

class IaCScanner:
    """
    Offline-first IaC misconfiguration scanner.

    Usage
    -----
    scanner = IaCScanner()
    result  = scanner.scan_path("/repo/infra")
    result  = scanner.scan_files({"Dockerfile": "...", "k8s/pod.yaml": "..."})
    """

    # File names that trigger scanning (case-insensitive)
    _DOCKERFILE_NAMES: frozenset = frozenset({
        "dockerfile", "dockerfile.dev", "dockerfile.prod",
        "dockerfile.test", "dockerfile.ci",
    })
    _COMPOSE_NAMES: frozenset = frozenset({
        "docker-compose.yml", "docker-compose.yaml",
        "docker-compose.dev.yml", "docker-compose.prod.yml",
        "compose.yml", "compose.yaml",
    })
    _HELM_NAMES: frozenset = frozenset({
        "values.yaml", "values.yml",
    })
    _TF_EXTENSIONS: frozenset = frozenset({".tf", ".tfvars"})
    _K8S_KEYWORDS: frozenset = frozenset({
        "pod", "deployment", "statefulset", "daemonset",
        "job", "cronjob", "replicaset",
    })

    _SKIP_DIRS: frozenset = frozenset({
        ".git", "__pycache__", "node_modules", ".venv", "venv",
        ".terraform", ".tox", "dist", "build", "vendor",
    })

    def scan_path(self, root: str = ".") -> IaCScanResult:
        """Walk `root` recursively and scan all recognized IaC files."""
        t0 = time.perf_counter()
        result = IaCScanResult(root=root)
        root_path = Path(root)
        if not root_path.exists():
            result.scan_duration_ms = 0.0
            return result

        for path in root_path.rglob("*"):
            if not path.is_file():
                continue
            # Skip unwanted directories
            if any(skip in path.parts for skip in self._SKIP_DIRS):
                continue
            try:
                content = path.read_text(encoding="utf-8", errors="replace")
            except (OSError, PermissionError):
                continue

            findings = self._dispatch(str(path), content)
            result.findings.extend(findings)
            if findings is not None:  # at least attempted to scan
                result.files_scanned += 1

        result.scan_duration_ms = (time.perf_counter() - t0) * 1000
        return result

    def scan_files(self, files: Dict[str, str]) -> IaCScanResult:
        """
        Scan a dict of {filename: content} without touching the filesystem.

        Used by the REST API (/scan-iac mode="files").
        """
        t0 = time.perf_counter()
        result = IaCScanResult(root="<in-memory>")
        for filename, content in files.items():
            if not content or not content.strip():
                continue
            findings = self._dispatch(filename, content)
            result.findings.extend(findings)
            result.files_scanned += 1
        result.scan_duration_ms = (time.perf_counter() - t0) * 1000
        return result

    # ─── Dispatcher ──────────────────────────────────────────────────────────

    def _dispatch(self, filename: str, content: str) -> List[IaCFinding]:
        """Route a file to the correct scanner based on name/extension."""
        name = Path(filename).name.lower()
        ext  = Path(filename).suffix.lower()

        if name in self._DOCKERFILE_NAMES:
            return self._scan_dockerfile(content, filename)
        if name in self._COMPOSE_NAMES:
            return self._scan_compose(content, filename)
        if name in self._HELM_NAMES and self._looks_like_helm(content):
            return self._scan_helm(content, filename)
        if ext in self._TF_EXTENSIONS:
            return self._scan_terraform(content, filename)
        if ext in (".yaml", ".yml") and self._looks_like_k8s(content):
            return self._scan_k8s(content, filename)
        return []

    # ─── Dockerfile scanner ───────────────────────────────────────────────────

    def _scan_dockerfile(self, content: str, src: str) -> List[IaCFinding]:
        findings: List[IaCFinding] = []
        lines = content.splitlines()

        has_user       = any(re.match(r'^\s*USER\s+\S', ln, re.IGNORECASE) for ln in lines)
        has_healthcheck= any(re.match(r'^\s*HEALTHCHECK\b', ln, re.IGNORECASE) for ln in lines)

        for rule in _DOCKERFILE_RULES:
            rid, cat, sev, title, desc, pat = rule

            # Absence rules
            if rid == "IAC-D001" and not has_user:
                findings.append(IaCFinding(rid, cat, sev, title, desc, src, 0))
                continue
            if rid == "IAC-D008" and not has_healthcheck:
                findings.append(IaCFinding(rid, cat, sev, title, desc, src, 0))
                continue
            if pat is None:
                continue

            for m in pat.finditer(content):
                lineno = content[: m.start()].count("\n") + 1
                findings.append(IaCFinding(rid, cat, sev, title, desc, src, lineno))
                break   # one finding per rule per file

        return findings

    # ─── docker-compose scanner ───────────────────────────────────────────────

    def _scan_compose(self, content: str, src: str) -> List[IaCFinding]:
        findings: List[IaCFinding] = []
        has_memory_limit = bool(re.search(r'memory\s*:', content, re.IGNORECASE))

        for rule in _COMPOSE_RULES:
            rid, cat, sev, title, desc, pat = rule

            if rid == "IAC-C007" and not has_memory_limit:
                findings.append(IaCFinding(rid, cat, sev, title, desc, src, 0))
                continue
            if pat is None:
                continue

            for m in pat.finditer(content):
                lineno = content[: m.start()].count("\n") + 1
                findings.append(IaCFinding(rid, cat, sev, title, desc, src, lineno))
                break

        return findings

    # ─── Kubernetes YAML scanner ──────────────────────────────────────────────

    def _scan_k8s(self, content: str, src: str) -> List[IaCFinding]:
        findings: List[IaCFinding] = []

        has_allow_priv_esc  = bool(re.search(r'allowPrivilegeEscalation\s*:', content))
        has_resource_limits = bool(re.search(r'limits\s*:', content))
        has_namespace       = bool(re.search(r'^\s*namespace\s*:', content, re.MULTILINE))
        has_readonly_rootfs = bool(re.search(r'readOnlyRootFilesystem\s*:\s*true', content))

        for rule in _K8S_RULES:
            rid, cat, sev, title, desc, pat = rule

            if rid == "IAC-K003" and not has_allow_priv_esc:
                findings.append(IaCFinding(rid, cat, sev, title, desc, src, 0))
                continue
            if rid == "IAC-K007" and not has_resource_limits:
                findings.append(IaCFinding(rid, cat, sev, title, desc, src, 0))
                continue
            if rid == "IAC-K011" and not has_namespace:
                findings.append(IaCFinding(rid, cat, sev, title, desc, src, 0))
                continue
            if rid == "IAC-K012" and not has_readonly_rootfs:
                findings.append(IaCFinding(rid, cat, sev, title, desc, src, 0))
                continue
            if pat is None:
                continue

            for m in pat.finditer(content):
                lineno = content[: m.start()].count("\n") + 1
                findings.append(IaCFinding(rid, cat, sev, title, desc, src, lineno))
                break

        return findings

    # ─── Terraform scanner ────────────────────────────────────────────────────

    def _scan_terraform(self, content: str, src: str) -> List[IaCFinding]:
        findings: List[IaCFinding] = []

        has_versioning = bool(re.search(r'versioning\s*\{', content, re.IGNORECASE))
        has_backend    = bool(re.search(r'backend\s+["\w]', content, re.IGNORECASE))

        for rule in _TERRAFORM_RULES:
            rid, cat, sev, title, desc, pat = rule

            if rid == "IAC-T004" and not has_versioning:
                # Only flag if we find an S3 bucket resource
                if re.search(r'resource\s+"aws_s3_bucket"', content):
                    findings.append(IaCFinding(rid, cat, sev, title, desc, src, 0))
                continue
            if rid == "IAC-T010" and not has_backend:
                if re.search(r'terraform\s*\{', content):
                    findings.append(IaCFinding(rid, cat, sev, title, desc, src, 0))
                continue
            if pat is None:
                continue

            for m in pat.finditer(content):
                lineno = content[: m.start()].count("\n") + 1
                findings.append(IaCFinding(rid, cat, sev, title, desc, src, lineno))
                break

        return findings

    # ─── Helm values.yaml scanner ─────────────────────────────────────────────

    def _scan_helm(self, content: str, src: str) -> List[IaCFinding]:
        findings: List[IaCFinding] = []
        has_limits = bool(re.search(r'limits\s*:', content, re.IGNORECASE))

        for rule in _HELM_RULES:
            rid, cat, sev, title, desc, pat = rule

            if rid == "IAC-H005" and not has_limits:
                findings.append(IaCFinding(rid, cat, sev, title, desc, src, 0))
                continue
            if pat is None:
                continue

            for m in pat.finditer(content):
                lineno = content[: m.start()].count("\n") + 1
                findings.append(IaCFinding(rid, cat, sev, title, desc, src, lineno))
                break

        return findings

    # ─── Heuristics ──────────────────────────────────────────────────────────

    def _looks_like_k8s(self, content: str) -> bool:
        """True if the YAML file looks like a Kubernetes manifest."""
        return bool(re.search(
            r'^\s*(?:apiVersion|kind)\s*:',
            content,
            re.MULTILINE | re.IGNORECASE,
        ))

    def _looks_like_helm(self, content: str) -> bool:
        """True if the YAML file is likely a Helm values.yaml."""
        # Has typical Helm keys: image, replicaCount, ingress, service
        helm_keys = sum(
            1 for k in ("image", "replicaCount", "ingress", "service", "tag", "pullPolicy")
            if re.search(rf'^\s*{k}\s*:', content, re.MULTILINE)
        )
        return helm_keys >= 2
