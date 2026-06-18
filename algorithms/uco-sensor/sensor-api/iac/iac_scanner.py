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
    # ── IaC+ FASE 8 — Dockerfile rules D011-D020 ─────────────────────────────
    (
        "IAC-D011", "IMAGE", "LOW",
        "apt-get install without --no-install-recommends",
        "RUN apt-get install -y without --no-install-recommends bloats the image. Add the flag and pin versions.",
        re.compile(r'^\s*RUN\s+.*apt-get\s+install\s+(?:(?!--no-install-recommends).)*$',
                   re.IGNORECASE | re.MULTILINE),
    ),
    (
        "IAC-D012", "IMAGE", "LOW",
        "Curl piped directly to shell (supply-chain risk)",
        "Piping curl|sh executes untrusted scripts. Download, verify checksum, then execute.",
        re.compile(r'^\s*RUN\s+.*curl\s+[^|]+\|\s*(?:sh|bash)\b',
                   re.IGNORECASE | re.MULTILINE),
    ),
    (
        "IAC-D013", "IMAGE", "LOW",
        "wget used without checksum verification",
        "wget downloads followed by execution should be paired with sha256sum/gpg --verify.",
        re.compile(r'^\s*RUN\s+.*wget\s+\S+(?!.*(?:sha256sum|gpg))',
                   re.IGNORECASE | re.MULTILINE),
    ),
    (
        "IAC-D014", "IMAGE", "LOW",
        "WORKDIR with relative path",
        "WORKDIR should be an absolute path to avoid CWD confusion across stages.",
        re.compile(r'^\s*WORKDIR\s+(?!/|\$)\S+', re.IGNORECASE | re.MULTILINE),
    ),
    (
        "IAC-D015", "PRIVILEGE", "MEDIUM",
        "sudo used inside Dockerfile",
        "sudo inside an image is an anti-pattern — set USER non-root + chown explicitly.",
        re.compile(r'^\s*RUN\s+.*\bsudo\b', re.IGNORECASE | re.MULTILINE),
    ),
    (
        "IAC-D016", "PRIVILEGE", "HIGH",
        "chmod 777 used in Dockerfile",
        "World-writable permissions inside the image expose any process to tampering.",
        re.compile(r'^\s*RUN\s+.*\bchmod\s+(?:-R\s+)?(?:0?777)\b',
                   re.IGNORECASE | re.MULTILINE),
    ),
    (
        "IAC-D017", "IMAGE", "MEDIUM",
        "Image built from non-official registry",
        "FROM with a non-official registry (user-namespaced or third-party) should be vetted.",
        re.compile(r'^\s*FROM\s+(?:[a-z0-9.-]+\.[a-z]{2,}|[a-z0-9-]+/[a-z0-9-]+)/',
                   re.IGNORECASE | re.MULTILINE),
    ),
    (
        "IAC-D018", "IMAGE", "LOW",
        "Multiple sequential RUN instructions",
        "Multiple RUN layers bloat the image. Chain commands with && in a single RUN.",
        None,   # absence/structural rule, handled in scanner
    ),
    (
        "IAC-D019", "IMAGE", "MEDIUM",
        "COPY . . without .dockerignore",
        "COPY . . without an accompanying .dockerignore leaks dev files / .git / .env into the image.",
        re.compile(r'^\s*COPY\s+\.\s+\.\s*$', re.MULTILINE),
    ),
    (
        "IAC-D020", "IMAGE", "LOW",
        "Image tag uses :latest in multi-stage FROM AS",
        "Multi-stage builds with :latest bases re-fetch new images on every build; pin the tag.",
        re.compile(r'^\s*FROM\s+\S+:latest\s+AS\s+\S+',
                   re.IGNORECASE | re.MULTILINE),
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
    # ── IaC+ FASE 8 — Kubernetes rules K013-K025 ─────────────────────────────
    (
        "IAC-K013", "CONFIG", "MEDIUM",
        "No livenessProbe configured",
        "Pods without livenessProbe can hang silently with no auto-restart.",
        None,   # absence rule
    ),
    (
        "IAC-K014", "CONFIG", "MEDIUM",
        "No readinessProbe configured",
        "Pods without readinessProbe receive traffic before they are ready.",
        None,   # absence rule
    ),
    (
        "IAC-K015", "PRIVILEGE", "HIGH",
        "automountServiceAccountToken not disabled",
        "automountServiceAccountToken defaults to true; explicitly set false for pods that don't call the K8s API.",
        None,   # absence rule
    ),
    (
        "IAC-K016", "PRIVILEGE", "CRITICAL",
        "ClusterRoleBinding to cluster-admin",
        "Binding to cluster-admin grants all cluster permissions — use a least-privilege role instead.",
        re.compile(r'name\s*:\s*cluster-admin\b'),
    ),
    (
        "IAC-K017", "RESOURCE", "MEDIUM",
        "No PodDisruptionBudget defined",
        "Without a PDB, voluntary disruptions can evict all replicas simultaneously.",
        None,   # absence/inverse rule, handled in scanner
    ),
    (
        "IAC-K018", "IMAGE", "MEDIUM",
        "imagePullPolicy: Never in production",
        "imagePullPolicy: Never makes pods depend on a local image — flag for review in production manifests.",
        re.compile(r'imagePullPolicy\s*:\s*Never\b'),
    ),
    (
        "IAC-K019", "NETWORK", "MEDIUM",
        "No NetworkPolicy in this namespace",
        "Absence of NetworkPolicy means default-allow east-west traffic; create restrictive policies.",
        None,   # absence/inverse rule, handled in scanner
    ),
    (
        "IAC-K020", "NETWORK", "HIGH",
        "Ingress without TLS",
        "Ingress block without spec.tls allows plaintext traffic from the load balancer.",
        re.compile(r'^\s*kind:\s*Ingress\b', re.MULTILINE),
    ),
    (
        "IAC-K021", "RESOURCE", "MEDIUM",
        "Resource requests missing",
        "requests.cpu/memory absent — the scheduler has no hint and packing is poor.",
        None,   # absence rule
    ),
    (
        "IAC-K022", "PRIVILEGE", "MEDIUM",
        "seccompProfile not set",
        "Without seccompProfile (RuntimeDefault or Localhost), syscalls are not restricted.",
        None,   # absence rule
    ),
    (
        "IAC-K023", "PRIVILEGE", "LOW",
        "appArmorProfile / AppArmor annotation missing",
        "Setting container.apparmor.security.beta.kubernetes.io/<name>=runtime/default adds another layer of confinement.",
        None,   # absence rule
    ),
    (
        "IAC-K024", "STORAGE", "MEDIUM",
        "emptyDir used for persistent data",
        "emptyDir is ephemeral and lost on pod restart — use a PVC for persistent state.",
        re.compile(r'^\s*emptyDir\s*:\s*\{?\}?\s*$', re.MULTILINE),
    ),
    (
        "IAC-K025", "RESOURCE", "LOW",
        "Even replica count for stateful workloads",
        "Stateful sets / quorum systems prefer odd replicas to avoid split-brain.",
        re.compile(r'^\s*replicas\s*:\s*(?:2|4|6|8|10)\s*$', re.MULTILINE),
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
    # ── IaC+ FASE 8 — Terraform rules T013-T025 ──────────────────────────────
    (
        "IAC-T013", "NETWORK", "HIGH",
        "CloudFront distribution without HTTPS enforcement",
        "viewer_protocol_policy should be 'redirect-to-https' or 'https-only'.",
        re.compile(r'viewer_protocol_policy\s*=\s*["\']allow-all["\']',
                   re.IGNORECASE),
    ),
    (
        "IAC-T014", "NETWORK", "MEDIUM",
        "Lambda function without VPC configuration",
        "aws_lambda_function without vpc_config has unrestricted egress to the internet.",
        re.compile(r'resource\s+["\']aws_lambda_function["\']'),
    ),
    (
        "IAC-T015", "STORAGE", "HIGH",
        "RDS instance without backup retention",
        "backup_retention_period not set or set to 0 — point-in-time restore impossible.",
        re.compile(r'backup_retention_period\s*=\s*0\b'),
    ),
    (
        "IAC-T016", "STORAGE", "HIGH",
        "S3 bucket without server-side encryption",
        "aws_s3_bucket without server_side_encryption_configuration stores plaintext.",
        re.compile(r'resource\s+["\']aws_s3_bucket["\']'),
    ),
    (
        "IAC-T017", "PRIVILEGE", "HIGH",
        "EC2 instance without IMDSv2 enforcement",
        "metadata_options.http_tokens must be 'required' (IMDSv2) to mitigate SSRF→credential theft.",
        re.compile(r'http_tokens\s*=\s*["\']optional["\']'),
    ),
    (
        "IAC-T018", "SECRET", "MEDIUM",
        "KMS key without rotation",
        "aws_kms_key with enable_key_rotation=false (or missing) keeps the same key indefinitely.",
        re.compile(r'enable_key_rotation\s*=\s*false', re.IGNORECASE),
    ),
    (
        "IAC-T019", "CONFIG", "MEDIUM",
        "CloudTrail not enabled / not multi-region",
        "aws_cloudtrail should set is_multi_region_trail=true for full audit coverage.",
        re.compile(r'is_multi_region_trail\s*=\s*false', re.IGNORECASE),
    ),
    (
        "IAC-T020", "CONFIG", "LOW",
        "GuardDuty not enabled",
        "aws_guardduty_detector resource missing — threat detection disabled.",
        None,   # absence rule, handled in scanner
    ),
    (
        "IAC-T021", "NETWORK", "HIGH",
        "Security group egress open to 0.0.0.0/0",
        "Egress to the entire internet defeats VPC segmentation and allows C2 channels.",
        re.compile(
            r'type\s*=\s*["\']egress["\'][^\n]*\n(?:[^\n]*\n){0,5}[^\n]*cidr_blocks\s*=\s*\[["\']0\.0\.0\.0/0["\']',
            re.DOTALL,
        ),
    ),
    (
        "IAC-T022", "CONFIG", "MEDIUM",
        "Load Balancer without access logs",
        "aws_lb without access_logs.enabled = true loses forensic trail.",
        re.compile(r'resource\s+["\']aws_lb["\']'),
    ),
    (
        "IAC-T023", "SECRET", "MEDIUM",
        "SNS topic without encryption",
        "aws_sns_topic without kms_master_key_id sends notifications unencrypted at rest.",
        re.compile(r'resource\s+["\']aws_sns_topic["\']'),
    ),
    (
        "IAC-T024", "STORAGE", "MEDIUM",
        "DynamoDB table without encryption at rest",
        "aws_dynamodb_table without server_side_encryption block uses the default AWS-owned key only.",
        re.compile(r'resource\s+["\']aws_dynamodb_table["\']'),
    ),
    (
        "IAC-T025", "NETWORK", "HIGH",
        "Public-facing ALB / CloudFront without WAF",
        "Public load balancers and CloudFront distributions should have aws_wafv2_web_acl associated.",
        re.compile(
            r'resource\s+["\'](?:aws_lb|aws_cloudfront_distribution)["\']'
        ),
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

# ── IaC+ FASE 8 — Ansible playbook rules A001-A008 ────────────────────────────
_ANSIBLE_RULES: List[Tuple] = [
    (
        "IAC-A001", "PRIVILEGE", "HIGH",
        "Ansible task uses become: yes without become_user",
        "Privilege escalation without an explicit become_user defaults to root.",
        re.compile(r'^\s*become\s*:\s*(?:yes|true)\b', re.MULTILINE),
    ),
    (
        "IAC-A002", "SECRET", "CRITICAL",
        "Plaintext password in vars / no-log missing",
        "Password-like variable defined without ``no_log: true`` is logged by Ansible.",
        re.compile(r'^\s*(?:password|secret|api_key|token)\s*:\s*\S+',
                   re.IGNORECASE | re.MULTILINE),
    ),
    (
        "IAC-A003", "SECRET", "HIGH",
        "Use of vault-less inline credentials",
        "Sensitive values should live in ansible-vault, not in playbook source.",
        re.compile(r'aws_access_key|aws_secret_key|gcp_credentials',
                   re.IGNORECASE),
    ),
    (
        "IAC-A004", "NETWORK", "MEDIUM",
        "shell / command without changed_when",
        "Tasks using shell/command should set changed_when to avoid spurious 'changed' state.",
        re.compile(r'^\s*(?:shell|command)\s*:', re.MULTILINE),
    ),
    (
        "IAC-A005", "PRIVILEGE", "MEDIUM",
        "Unrestricted file mode (mode: '0777')",
        "World-writable files created by Ansible expose data to any local user.",
        re.compile(r"mode\s*:\s*['\"]?0?777['\"]?"),
    ),
    (
        "IAC-A006", "NETWORK", "MEDIUM",
        "validate_certs: no in network/uri module",
        "Disabling TLS validation allows on-path attackers to MITM the request.",
        re.compile(r'validate_certs\s*:\s*(?:no|false)\b', re.IGNORECASE),
    ),
    (
        "IAC-A007", "CONFIG", "LOW",
        "no_log not used on tasks handling secrets",
        "Tasks that touch sensitive vars should set ``no_log: true``.",
        re.compile(r'no_log\s*:\s*(?:no|false)\b', re.IGNORECASE),
    ),
    (
        "IAC-A008", "IMAGE", "LOW",
        "Package install without state: present",
        "yum/apt/dnf/package modules without explicit ``state:`` may surprise on upgrade.",
        re.compile(r'^\s*(?:apt|yum|dnf|package)\s*:(?:(?!state).)*$',
                   re.MULTILINE | re.DOTALL),
    ),
]

# ── IaC+ FASE 8 — Pulumi rules P001-P005 ──────────────────────────────────────
_PULUMI_RULES: List[Tuple] = [
    (
        "IAC-P001", "STORAGE", "HIGH",
        "Pulumi S3 bucket with publicReadAccess",
        "publicReadAccess / publicAccessBlock disabled exposes objects to the internet.",
        re.compile(r'publicReadAccess\s*:\s*true|publicAccessBlock\s*:\s*false',
                   re.IGNORECASE),
    ),
    (
        "IAC-P002", "SECRET", "CRITICAL",
        "Hardcoded secret in Pulumi config",
        "Sensitive values should live in pulumi config --secret, not in TS/JS source.",
        re.compile(
            r'(?:accessKey|secretKey|password|apiKey)\s*[:=]\s*["\'][A-Za-z0-9+/=]{8,}["\']',
            re.IGNORECASE,
        ),
    ),
    (
        "IAC-P003", "NETWORK", "HIGH",
        "Pulumi SecurityGroup with 0.0.0.0/0 ingress",
        "Ingress block opens a port to the entire internet — restrict cidrBlocks.",
        re.compile(
            r'cidrBlocks?\s*:\s*\[\s*["\']0\.0\.0\.0/0["\']'
        ),
    ),
    (
        "IAC-P004", "PRIVILEGE", "MEDIUM",
        "IAM policy with Action: '*'",
        "Policy granting Action: '*' or Resource: '*' violates least privilege.",
        re.compile(r'Action\s*:\s*["\']\\*["\']|"Resource"\s*:\s*"\\*"'),
    ),
    (
        "IAC-P005", "CONFIG", "LOW",
        "Pulumi.yaml missing description",
        "Stacks without a description make ownership / purpose unclear in pulumi console.",
        None,   # absence rule
    ),
]

# ── IaC+ FASE 8 — AWS CDK rules CDK001-CDK005 ────────────────────────────────
_CDK_RULES: List[Tuple] = [
    (
        "IAC-CDK001", "STORAGE", "HIGH",
        "CDK S3 Bucket created without enforceSSL",
        "Bucket constructor must set enforceSSL: true to require HTTPS for all requests.",
        # Anchor on the constructor call; scanner-level post-check below
        # confirms enforceSSL absence in the same file.
        re.compile(r'new\s+s3\.Bucket\s*\('),
    ),
    (
        "IAC-CDK002", "STORAGE", "HIGH",
        "CDK S3 Bucket without server-side encryption",
        "S3 Bucket should set encryption: BucketEncryption.KMS_MANAGED or S3_MANAGED.",
        re.compile(r'new\s+s3\.Bucket\s*\('),
    ),
    (
        "IAC-CDK003", "PRIVILEGE", "CRITICAL",
        "CDK IAM Policy with PolicyStatement Effect: ALLOW + '*' resource",
        "PolicyStatement with resources: ['*'] grants over-broad permissions.",
        re.compile(r'resources\s*:\s*\[\s*["\']\\*["\']\s*\]'),
    ),
    (
        "IAC-CDK004", "NETWORK", "HIGH",
        "CDK SecurityGroup.addIngressRule with anyIpv4",
        "addIngressRule(Peer.anyIpv4(), …) opens the port to the whole internet.",
        re.compile(r'addIngressRule\s*\(\s*ec2\.Peer\.anyIpv4\(\)'),
    ),
    (
        "IAC-CDK005", "CONFIG", "MEDIUM",
        "CDK Lambda with default logging only",
        "Lambda construct should set logRetention to RetentionDays.<value> to avoid CW Logs sprawl.",
        re.compile(r'new\s+lambda\.Function\s*\('),
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

    # ── IaC+ FASE 8 — file matchers for Ansible / Pulumi / CDK ───────────────
    _ANSIBLE_NAMES: frozenset = frozenset({
        "playbook.yml", "playbook.yaml",
        "site.yml", "site.yaml",
        "main.yml", "main.yaml",
    })
    _PULUMI_NAMES: frozenset = frozenset({
        "pulumi.yaml", "pulumi.yml",
        "index.ts", "index.js",
    })
    _CDK_NAMES: frozenset = frozenset({
        "cdk.json",
    })

    _SKIP_DIRS: frozenset = frozenset({
        ".git", "__pycache__", "node_modules", ".venv", "venv",
        ".terraform", ".tox", "dist", "build", "vendor",
        "cdk.out",
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
        # IaC+ FASE 8: cdk.json triggers CDK scan on sibling .ts/.py files
        if name in self._CDK_NAMES:
            return self._scan_cdk(content, filename)
        # IaC+ FASE 8: Pulumi by file name or content sniffer
        if name in self._PULUMI_NAMES or self._looks_like_pulumi(content):
            return self._scan_pulumi(content, filename)
        # IaC+ FASE 8: TS/JS/Python with aws_cdk imports → CDK
        if ext in (".ts", ".js", ".py") and self._looks_like_cdk(content):
            return self._scan_cdk(content, filename)
        # IaC+ FASE 8: Ansible — YAML with tasks/hosts/playbook shape
        if (name in self._ANSIBLE_NAMES
                or (ext in (".yaml", ".yml") and self._looks_like_ansible(content))):
            return self._scan_ansible(content, filename)
        if ext in (".yaml", ".yml") and self._looks_like_k8s(content):
            return self._scan_k8s(content, filename)
        return []

    # ─── Dockerfile scanner ───────────────────────────────────────────────────

    def _scan_dockerfile(self, content: str, src: str) -> List[IaCFinding]:
        findings: List[IaCFinding] = []
        lines = content.splitlines()

        has_user       = any(re.match(r'^\s*USER\s+\S', ln, re.IGNORECASE) for ln in lines)
        has_healthcheck= any(re.match(r'^\s*HEALTHCHECK\b', ln, re.IGNORECASE) for ln in lines)
        # IaC+ D018: 3+ separate top-level RUN instructions = layer bloat
        run_count      = sum(1 for ln in lines
                             if re.match(r'^\s*RUN\b', ln, re.IGNORECASE))

        for rule in _DOCKERFILE_RULES:
            rid, cat, sev, title, desc, pat = rule

            # Absence / structural rules
            if rid == "IAC-D001" and not has_user:
                findings.append(IaCFinding(rid, cat, sev, title, desc, src, 0))
                continue
            if rid == "IAC-D008" and not has_healthcheck:
                findings.append(IaCFinding(rid, cat, sev, title, desc, src, 0))
                continue
            if rid == "IAC-D018":
                if run_count >= 3:
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
        # IaC+ FASE 8 absence-rule probes
        has_liveness   = bool(re.search(r'livenessProbe\s*:', content))
        has_readiness  = bool(re.search(r'readinessProbe\s*:', content))
        has_automount_off = bool(re.search(
            r'automountServiceAccountToken\s*:\s*false', content))
        has_pdb        = bool(re.search(r'kind\s*:\s*PodDisruptionBudget',
                                        content, re.IGNORECASE))
        has_netpol     = bool(re.search(r'kind\s*:\s*NetworkPolicy',
                                        content, re.IGNORECASE))
        has_requests   = bool(re.search(r'requests\s*:', content))
        has_seccomp    = bool(re.search(r'seccompProfile\s*:', content))
        has_apparmor   = bool(re.search(
            r'container\.apparmor\.security\.beta\.kubernetes\.io', content))
        # K017/K019/K023 only meaningful when at least one workload exists
        has_workload   = bool(re.search(
            r'^\s*kind\s*:\s*(?:Deployment|StatefulSet|DaemonSet|Pod)\b',
            content, re.MULTILINE))

        # Probes / resources / seccomp / apparmor: only emit findings when
        # the file actually contains a container spec (avoid false-positives
        # on Services, ConfigMaps, …).
        has_containers = bool(re.search(r'^\s*containers\s*:', content,
                                        re.MULTILINE))

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
            # ── IaC+ FASE 8 new absence rules ────────────────────────────────
            if rid == "IAC-K013" and has_containers and not has_liveness:
                findings.append(IaCFinding(rid, cat, sev, title, desc, src, 0))
                continue
            if rid == "IAC-K014" and has_containers and not has_readiness:
                findings.append(IaCFinding(rid, cat, sev, title, desc, src, 0))
                continue
            if rid == "IAC-K015" and has_workload and not has_automount_off:
                findings.append(IaCFinding(rid, cat, sev, title, desc, src, 0))
                continue
            if rid == "IAC-K017" and has_workload and not has_pdb:
                findings.append(IaCFinding(rid, cat, sev, title, desc, src, 0))
                continue
            if rid == "IAC-K019" and has_workload and not has_netpol:
                findings.append(IaCFinding(rid, cat, sev, title, desc, src, 0))
                continue
            if rid == "IAC-K021" and has_containers and not has_requests:
                findings.append(IaCFinding(rid, cat, sev, title, desc, src, 0))
                continue
            if rid == "IAC-K022" and has_containers and not has_seccomp:
                findings.append(IaCFinding(rid, cat, sev, title, desc, src, 0))
                continue
            if rid == "IAC-K023" and has_workload and not has_apparmor:
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
        # IaC+ FASE 8 — T020 absence probe
        has_guardduty  = bool(re.search(r'resource\s+["\']aws_guardduty_detector["\']',
                                        content))
        has_aws_resources = bool(re.search(
            r'resource\s+["\']aws_[a-z0-9_]+["\']', content))

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
            if rid == "IAC-T020" and has_aws_resources and not has_guardduty:
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

    # ─── IaC+ FASE 8: Ansible / Pulumi / CDK scanners ────────────────────────

    def _scan_ansible(self, content: str, src: str) -> List[IaCFinding]:
        """Scan an Ansible playbook / role file (YAML)."""
        findings: List[IaCFinding] = []
        for rule in _ANSIBLE_RULES:
            rid, cat, sev, title, desc, pat = rule
            if pat is None:
                continue
            for m in pat.finditer(content):
                lineno = content[: m.start()].count("\n") + 1
                findings.append(IaCFinding(rid, cat, sev, title, desc, src, lineno))
                break
        return findings

    def _scan_pulumi(self, content: str, src: str) -> List[IaCFinding]:
        """
        Scan a Pulumi program (TS/JS/Python) or stack config.

        P005 (absence of description) is only applied to YAML stacks
        (Pulumi.yaml / Pulumi.<stack>.yaml).
        """
        findings: List[IaCFinding] = []
        is_yaml = src.lower().endswith((".yaml", ".yml"))
        has_description = bool(re.search(r'^\s*description\s*:', content, re.MULTILINE))

        for rule in _PULUMI_RULES:
            rid, cat, sev, title, desc, pat = rule
            if rid == "IAC-P005":
                if is_yaml and not has_description:
                    findings.append(IaCFinding(rid, cat, sev, title, desc, src, 0))
                continue
            if pat is None:
                continue
            for m in pat.finditer(content):
                lineno = content[: m.start()].count("\n") + 1
                findings.append(IaCFinding(rid, cat, sev, title, desc, src, lineno))
                break
        return findings

    def _scan_cdk(self, content: str, src: str) -> List[IaCFinding]:
        """
        Scan an AWS CDK app written in TypeScript / JavaScript / Python.

        CDK001 (no enforceSSL) and CDK002 (no encryption) require an absence
        check across the file, not just a regex hit at the constructor.
        """
        findings: List[IaCFinding] = []
        has_enforce_ssl = bool(re.search(r'enforceSSL\s*:\s*true', content))
        has_encryption  = bool(re.search(r'encryption\s*:', content))
        has_log_retention = bool(re.search(r'logRetention\s*:', content))

        for rule in _CDK_RULES:
            rid, cat, sev, title, desc, pat = rule
            if pat is None:
                continue
            for m in pat.finditer(content):
                lineno = content[: m.start()].count("\n") + 1
                if rid == "IAC-CDK001" and has_enforce_ssl:
                    break
                if rid == "IAC-CDK002" and has_encryption:
                    break
                if rid == "IAC-CDK005" and has_log_retention:
                    break
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

    # ── IaC+ FASE 8 — content sniffers for Ansible / Pulumi / CDK ────────────

    def _looks_like_ansible(self, content: str) -> bool:
        """
        True if a YAML file looks like an Ansible playbook.

        Heuristic: a list of plays at the top level with ``hosts:`` AND one
        of ``tasks:`` / ``roles:`` / ``become:``.
        """
        if not re.search(r'^- (?:hosts|name)\s*:', content, re.MULTILINE):
            return False
        return bool(re.search(r'^\s+(?:tasks|roles|become)\s*:', content,
                              re.MULTILINE))

    def _looks_like_pulumi(self, content: str) -> bool:
        """True when a TS/JS/YAML file references ``@pulumi/`` packages or runtime."""
        return bool(re.search(
            r'(?:@pulumi/|pulumi\.(?:Config|StackReference))', content
        ))

    def _looks_like_cdk(self, content: str) -> bool:
        """True when source imports the AWS CDK libraries."""
        return bool(re.search(
            # TS/JS: from "aws-cdk-lib/..."  or  @aws-cdk/...
            # Py:    import aws_cdk           or  from aws_cdk import ...
            r'aws-cdk-lib|@aws-cdk/|\baws_cdk\b',
            content,
        ))
