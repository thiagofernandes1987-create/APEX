"""
test_marco_m25.py — IaC+ FASE 8: rule expansion + Ansible/Pulumi/CDK (30 tests TI01-TI30)
==========================================================================================
Validates the IaC+ deliverable (FASE 8 → v3.1.2):

  TI01-TI06  Dockerfile rules D011-D020
  TI07-TI14  Kubernetes rules K013-K025
  TI15-TI20  Terraform rules T013-T025
  TI21-TI24  Ansible playbook scanner (A001-A008)
  TI25-TI27  Pulumi scanner (P001-P005)
  TI28-TI30  AWS CDK scanner (CDK001-CDK005)
"""
from __future__ import annotations

import sys
import textwrap
import unittest
from pathlib import Path

_TESTS_DIR  = Path(__file__).resolve().parent
_SENSOR_DIR = _TESTS_DIR.parent
_ENGINE_DIR = _SENSOR_DIR.parent / "frequency-engine"
for _p in [str(_ENGINE_DIR), str(_SENSOR_DIR)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from iac.iac_scanner import (
    IaCScanner,
    _DOCKERFILE_RULES, _COMPOSE_RULES, _K8S_RULES, _TERRAFORM_RULES,
    _HELM_RULES, _ANSIBLE_RULES, _PULUMI_RULES, _CDK_RULES,
)


def _scan(name: str, content: str):
    s = IaCScanner()
    r = s.scan_files({name: textwrap.dedent(content).lstrip("\n")})
    return {f.rule_id for f in r.findings}


class TestDockerfileExpansion(unittest.TestCase):

    def test_TI01_d011_apt_install_without_no_recommends(self):
        """TI01: apt-get install without --no-install-recommends fires D011."""
        ids = _scan("Dockerfile", """
            FROM ubuntu:24.04
            USER app
            HEALTHCHECK CMD curl -f http://x || exit 1
            RUN apt-get install -y nginx
        """)
        self.assertIn("IAC-D011", ids)

    def test_TI02_d012_curl_pipe_shell(self):
        """TI02: curl ... | sh detected as supply-chain risk."""
        ids = _scan("Dockerfile", """
            FROM ubuntu:24.04
            USER app
            HEALTHCHECK CMD true
            RUN curl -sSL https://example.com/install.sh | sh
        """)
        self.assertIn("IAC-D012", ids)

    def test_TI03_d016_chmod_777(self):
        """TI03: chmod 777 in RUN is HIGH severity."""
        ids = _scan("Dockerfile", """
            FROM ubuntu:24.04
            USER app
            HEALTHCHECK CMD true
            RUN chmod 777 /tmp/app
        """)
        self.assertIn("IAC-D016", ids)

    def test_TI04_d018_multiple_run_layers(self):
        """TI04: ≥3 separate RUN instructions trigger D018 layer bloat."""
        ids = _scan("Dockerfile", """
            FROM ubuntu:24.04
            USER app
            HEALTHCHECK CMD true
            RUN apt-get update --no-install-recommends
            RUN apt-get install -y --no-install-recommends nginx
            RUN apt-get clean
        """)
        self.assertIn("IAC-D018", ids)

    def test_TI05_d019_copy_dot_dot(self):
        """TI05: COPY . . — leaks dev files when .dockerignore absent."""
        ids = _scan("Dockerfile", """
            FROM ubuntu:24.04
            USER app
            HEALTHCHECK CMD true
            COPY . .
        """)
        self.assertIn("IAC-D019", ids)

    def test_TI06_d018_does_not_fire_with_one_run(self):
        """TI06: a single RUN layer is fine — D018 stays silent."""
        ids = _scan("Dockerfile", """
            FROM ubuntu:24.04
            USER app
            HEALTHCHECK CMD true
            RUN apt-get update --no-install-recommends \\
             && apt-get install -y --no-install-recommends nginx \\
             && apt-get clean
        """)
        self.assertNotIn("IAC-D018", ids)


class TestKubernetesExpansion(unittest.TestCase):

    _BARE_DEPLOY = """
        apiVersion: apps/v1
        kind: Deployment
        spec:
          template:
            spec:
              containers:
              - name: app
                image: nginx:1.25
    """

    def test_TI07_k013_no_liveness_probe(self):
        """TI07: container without livenessProbe → K013."""
        ids = _scan("deployment.yaml", self._BARE_DEPLOY)
        self.assertIn("IAC-K013", ids)

    def test_TI08_k014_no_readiness_probe(self):
        """TI08: container without readinessProbe → K014."""
        ids = _scan("deployment.yaml", self._BARE_DEPLOY)
        self.assertIn("IAC-K014", ids)

    def test_TI09_k015_automount_default_true(self):
        """TI09: workload without automountServiceAccountToken=false → K015."""
        ids = _scan("deployment.yaml", self._BARE_DEPLOY)
        self.assertIn("IAC-K015", ids)

    def test_TI10_k016_cluster_admin_binding(self):
        """TI10: ClusterRoleBinding to cluster-admin is CRITICAL (K016)."""
        ids = _scan("rbac.yaml", """
            apiVersion: rbac.authorization.k8s.io/v1
            kind: ClusterRoleBinding
            metadata:
              namespace: prod
            roleRef:
              kind: ClusterRole
              name: cluster-admin
              apiGroup: rbac.authorization.k8s.io
            subjects:
            - kind: ServiceAccount
              name: app
              namespace: prod
        """)
        self.assertIn("IAC-K016", ids)

    def test_TI11_k018_image_pull_policy_never(self):
        """TI11: imagePullPolicy: Never flagged (K018)."""
        ids = _scan("deployment.yaml", """
            apiVersion: apps/v1
            kind: Deployment
            spec:
              template:
                spec:
                  containers:
                  - name: app
                    image: nginx:1.25
                    imagePullPolicy: Never
        """)
        self.assertIn("IAC-K018", ids)

    def test_TI12_k020_ingress_without_tls(self):
        """TI12: Ingress without TLS block → K020."""
        ids = _scan("ingress.yaml", """
            apiVersion: networking.k8s.io/v1
            kind: Ingress
            metadata:
              namespace: prod
        """)
        self.assertIn("IAC-K020", ids)

    def test_TI13_k024_emptydir_for_persistent_data(self):
        """TI13: emptyDir volume flagged (K024)."""
        ids = _scan("pod.yaml", """
            apiVersion: v1
            kind: Pod
            spec:
              containers:
              - name: app
                image: nginx:1.25
              volumes:
              - name: data
                emptyDir: {}
        """)
        self.assertIn("IAC-K024", ids)

    def test_TI14_k025_even_replica_count(self):
        """TI14: replicas: 2 (even) → K025."""
        ids = _scan("deployment.yaml", """
            apiVersion: apps/v1
            kind: Deployment
            spec:
              replicas: 2
              template:
                spec:
                  containers:
                  - name: app
                    image: nginx:1.25
        """)
        self.assertIn("IAC-K025", ids)


class TestTerraformExpansion(unittest.TestCase):

    def test_TI15_t013_cloudfront_allow_all(self):
        """TI15: viewer_protocol_policy = allow-all triggers T013."""
        ids = _scan("main.tf", """
            resource "aws_cloudfront_distribution" "x" {
              viewer_protocol_policy = "allow-all"
            }
        """)
        self.assertIn("IAC-T013", ids)

    def test_TI16_t015_rds_backup_zero(self):
        """TI16: RDS backup_retention_period = 0 → T015."""
        ids = _scan("main.tf", """
            resource "aws_db_instance" "x" {
              backup_retention_period = 0
            }
        """)
        self.assertIn("IAC-T015", ids)

    def test_TI17_t017_imdsv1_optional(self):
        """TI17: http_tokens = "optional" (IMDSv1) → T017."""
        ids = _scan("main.tf", """
            resource "aws_instance" "x" {
              metadata_options {
                http_tokens = "optional"
              }
            }
        """)
        self.assertIn("IAC-T017", ids)

    def test_TI18_t018_kms_rotation_disabled(self):
        """TI18: enable_key_rotation = false on KMS key → T018."""
        ids = _scan("kms.tf", """
            resource "aws_kms_key" "x" {
              enable_key_rotation = false
            }
        """)
        self.assertIn("IAC-T018", ids)

    def test_TI19_t020_no_guardduty(self):
        """TI19: TF with AWS resources but no aws_guardduty_detector → T020."""
        ids = _scan("infra.tf", """
            resource "aws_s3_bucket" "x" {
              bucket = "logs"
              versioning { enabled = true }
            }
        """)
        self.assertIn("IAC-T020", ids)

    def test_TI20_t020_silent_when_guardduty_present(self):
        """TI20: presence of aws_guardduty_detector suppresses T020."""
        ids = _scan("infra.tf", """
            resource "aws_s3_bucket" "x" {
              bucket = "logs"
              versioning { enabled = true }
            }
            resource "aws_guardduty_detector" "main" {
              enable = true
            }
        """)
        self.assertNotIn("IAC-T020", ids)


class TestAnsibleScanner(unittest.TestCase):

    def test_TI21_a001_become_without_user(self):
        """TI21: become: yes without become_user fires A001."""
        ids = _scan("playbook.yml", """
            - hosts: web
              become: yes
              tasks:
              - name: install
                apt:
                  name: nginx
                  state: present
        """)
        self.assertIn("IAC-A001", ids)

    def test_TI22_a005_world_writable_mode(self):
        """TI22: mode: '0777' detected (A005)."""
        ids = _scan("playbook.yml", """
            - hosts: web
              become: no
              tasks:
              - name: install
                apt:
                  name: nginx
                  state: present
              - name: open file
                file:
                  path: /tmp/x
                  mode: '0777'
        """)
        self.assertIn("IAC-A005", ids)

    def test_TI23_a006_validate_certs_disabled(self):
        """TI23: validate_certs: no flags TLS-validation bypass (A006)."""
        ids = _scan("playbook.yml", """
            - hosts: web
              tasks:
              - name: fetch
                uri:
                  url: https://api.example
                  validate_certs: no
        """)
        self.assertIn("IAC-A006", ids)

    def test_TI24_ansible_dispatch_via_content_sniffer(self):
        """TI24: a YAML file whose name isn't `playbook.yml` still routes to Ansible."""
        ids = _scan("roles/web/tasks/main.yml", """
            - hosts: localhost
              tasks:
              - name: install
                apt:
                  name: nginx
                  state: present
              - name: setup
                file:
                  path: /tmp/x
                  mode: '0777'
        """)
        self.assertIn("IAC-A005", ids)


class TestPulumiScanner(unittest.TestCase):

    def test_TI25_p001_public_read_bucket(self):
        """TI25: publicReadAccess: true flagged (P001)."""
        ids = _scan("index.ts", """
            import * as aws from "@pulumi/aws";
            const bucket = new aws.s3.Bucket("b", {
              publicReadAccess: true,
            });
        """)
        self.assertIn("IAC-P001", ids)

    def test_TI26_p002_hardcoded_secret(self):
        """TI26: hardcoded accessKey in Pulumi source (P002)."""
        ids = _scan("index.ts", """
            import * as pulumi from "@pulumi/pulumi";
            const accessKey = "AKIAFAKEEXAMPLE12345";
        """)
        self.assertIn("IAC-P002", ids)

    def test_TI27_p005_yaml_without_description(self):
        """TI27: Pulumi.yaml without description triggers P005."""
        ids = _scan("Pulumi.yaml", """
            name: my-stack
            runtime: nodejs
        """)
        self.assertIn("IAC-P005", ids)


class TestCDKScanner(unittest.TestCase):

    def test_TI28_cdk001_bucket_without_enforce_ssl(self):
        """TI28: S3 Bucket without enforceSSL → CDK001."""
        ids = _scan("stack.ts", """
            import * as s3 from "aws-cdk-lib/aws-s3";
            const bucket = new s3.Bucket(this, "MyBucket", {});
        """)
        self.assertIn("IAC-CDK001", ids)

    def test_TI29_cdk_clean_suppresses_findings(self):
        """TI29: Bucket with enforceSSL+encryption suppresses CDK001+CDK002."""
        ids = _scan("stack.ts", """
            import * as s3 from "aws-cdk-lib/aws-s3";
            const bucket = new s3.Bucket(this, "MyBucket", {
              enforceSSL: true,
              encryption: s3.BucketEncryption.S3_MANAGED,
            });
        """)
        self.assertNotIn("IAC-CDK001", ids)
        self.assertNotIn("IAC-CDK002", ids)

    def test_TI30_cdk004_anyipv4_ingress(self):
        """TI30: addIngressRule(Peer.anyIpv4(), ...) → CDK004."""
        ids = _scan("stack.ts", """
            import * as ec2 from "aws-cdk-lib/aws-ec2";
            sg.addIngressRule(ec2.Peer.anyIpv4(), ec2.Port.tcp(22));
        """)
        self.assertIn("IAC-CDK004", ids)


class TestRuleInventory(unittest.TestCase):
    """One-shot sanity guard: 100+ rules across 8 scanners."""

    def test_TI_rule_count_total(self):
        all_rules = (
            _DOCKERFILE_RULES + _COMPOSE_RULES + _K8S_RULES + _TERRAFORM_RULES
            + _HELM_RULES + _ANSIBLE_RULES + _PULUMI_RULES + _CDK_RULES
        )
        self.assertGreaterEqual(
            len(all_rules), 100,
            f"IaC+ target ≥100 rules, got {len(all_rules)}",
        )


if __name__ == "__main__":
    unittest.main()
