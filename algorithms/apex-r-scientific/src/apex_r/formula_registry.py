"""Registro canônico de fórmulas, hipóteses e força de evidência do APEX-R."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Mapping


class FormulaEvidence(str, Enum):
    PROVED = "PROVED"
    TESTED = "TESTED"
    REPRODUCED = "REPRODUCED"
    EXTERNALLY_VALIDATED = "EXTERNALLY_VALIDATED"
    PRELIMINARY = "PRELIMINARY"
    NOT_DEMONSTRATED = "NOT_DEMONSTRATED"


@dataclass(frozen=True)
class FormulaSpec:
    formula_id: str
    module_id: str
    name: str
    expression: str
    variables: Mapping[str, str]
    assumptions: tuple[str, ...]
    applicability_domain: str
    source_section: str
    evidence: FormulaEvidence
    implementation: str | None = None
    implementation_notes: str | None = None
    external_validation: str | None = None

    def __post_init__(self) -> None:
        required = (
            self.formula_id,
            self.module_id,
            self.name,
            self.expression,
            self.applicability_domain,
            self.source_section,
        )
        if not all(value.strip() for value in required):
            raise ValueError("Os campos textuais obrigatórios da fórmula não podem ser vazios")
        if not self.assumptions:
            raise ValueError("Toda fórmula deve declarar ao menos uma hipótese")
        if self.evidence is FormulaEvidence.EXTERNALLY_VALIDATED and not self.external_validation:
            raise ValueError("EXTERNALLY_VALIDATED exige referência ao artefato de validação")

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["evidence"] = self.evidence.value
        return data


FORMULAS: tuple[FormulaSpec, ...] = (
    FormulaSpec(
        "M0.FIM.LOCAL",
        "M0",
        "Matriz de Informação de Fisher local",
        "F(theta) = J(theta)^T Sigma^(-1) J(theta)",
        {"J": "Jacobiana normalizada dos observáveis", "Sigma": "covariância do erro"},
        (
            "O desenho experimental e o modelo de erro estão declarados.",
            "Parâmetros e observáveis foram normalizados antes de interpretar condicionamento.",
        ),
        "Diagnóstico local; deve ser combinado com rank, espectro, perfis e posterior.",
        "Documento Técnico Corrigido, seção 5",
        FormulaEvidence.NOT_DEMONSTRATED,
    ),
    FormulaSpec(
        "M2.DELTA_G_FROM_KD",
        "M2",
        "Energia livre padrão a partir de Kd",
        "DeltaG0 = R T ln(Kd / C0)",
        {"R": "J mol^-1 K^-1", "T": "K", "Kd": "mol L^-1", "C0": "1 mol L^-1"},
        (
            "Kd é uma constante de dissociação física, não um score bruto de docking.",
            "Kd e C0 usam a mesma unidade antes do logaritmo.",
        ),
        "Equilíbrio termodinâmico no estado padrão declarado.",
        "Documento Técnico Corrigido, seção 6.1",
        FormulaEvidence.TESTED,
        "apex_r.modules.molecular.delta_g_from_kd",
    ),
    FormulaSpec(
        "M2.CALIBRATION.LINEAR",
        "M2",
        "Calibração supervisionada de afinidade",
        "pK_hat = beta0 + beta1 s_dock + beta_physchem x + u_target + epsilon",
        {"pK_hat": "adimensional", "s_dock": "unidade declarada pelo método"},
        (
            "Coeficientes são estimados por dataset, split e protocolo versionados.",
            "O domínio de aplicabilidade e a incerteza preditiva são reportados.",
        ),
        "Predição empírica; proíbe coeficientes universais embutidos.",
        "Documento Técnico Corrigido, seção 6.2",
        FormulaEvidence.PRELIMINARY,
        "apex_r.modules.molecular.calibrate_linear",
        "O incremento atual implementa apenas beta0 + beta1*x por OLS; covariáveis, efeito de alvo e validação externa permanecem pendentes.",
    ),
    FormulaSpec(
        "M3.WK2",
        "M3",
        "Windkessel de dois elementos",
        "C dP/dt = Qin - (P - Pv)/R",
        {"C": "volume/pressão", "P": "pressão", "Qin": "volume/tempo", "R": "pressão tempo/volume"},
        (
            "R e C são positivos.",
            "O modelo é WK2 e não representa impedância, inércia ou autorregulação ativa.",
        ),
        "Hemodinâmica lumped de baixa fidelidade declarada.",
        "Documento Técnico Corrigido, seção 9",
        FormulaEvidence.TESTED,
        "apex_r.modules.hemodynamics.pressure_derivative",
    ),
    FormulaSpec(
        "M4.MASS_BALANCE",
        "M4",
        "Balanço de massa compartimental",
        "dA_i/dt = input_i + sum_j k_ji A_j - sum_j k_ij A_i - k_elim,i A_i",
        {"A": "quantidade", "k": "tempo^-1", "input": "quantidade/tempo"},
        (
            "Transferências internas usam a mesma base de quantidade.",
            "Clearance é convertido em fluxo de massa usando a concentração apropriada.",
        ),
        "Núcleo compartimental; não valida sozinho um modelo PBPK fisiológico completo.",
        "Documento Técnico Corrigido, seção 8 e tabela 9",
        FormulaEvidence.TESTED,
        "apex_r.modules.pbpk.derivative",
    ),
    FormulaSpec(
        "M5.HILL",
        "M5A",
        "Resposta de Hill",
        "E(C) = E0 + Emax C^h / (EC50^h + C^h)",
        {"C": "mesma unidade de EC50", "E": "escala de efeito declarada", "h": "adimensional"},
        (
            "C e EC50 são positivos e usam a mesma unidade.",
            "A concentração é a exposição relevante no sítio de efeito.",
        ),
        "PD estática; atraso exige compartimento de efeito ou modelo indireto.",
        "Documento Técnico Corrigido, seção 10.1",
        FormulaEvidence.NOT_DEMONSTRATED,
    ),
    FormulaSpec(
        "M6.BLISS",
        "M6",
        "Independência de Bliss",
        "E_Bliss = E_A + E_B - E_A E_B",
        {"E_A": "efeito normalizado [0,1]", "E_B": "efeito normalizado [0,1]"},
        (
            "Os efeitos estão normalizados em [0,1] e orientados na mesma direção.",
            "A independência probabilística é o modelo nulo apropriado.",
        ),
        "Métrica de referência; em exposição dinâmica deve ser avaliada ponto a ponto.",
        "Documento Técnico Corrigido, seção 10.2 e tabela 11",
        FormulaEvidence.NOT_DEMONSTRATED,
    ),
    FormulaSpec(
        "M9.ACE",
        "M9",
        "Efeito causal médio",
        "ACE = E[Y | do(X=x1)] - E[Y | do(X=x0)]",
        {"X": "intervenção definida", "Y": "desfecho", "ACE": "unidade de Y"},
        (
            "A consulta é identificável sob o SCM/D-SCM declarado.",
            "Feedback não é tratado como DAG estático; usa D-SCM ou grafo desenrolado no tempo.",
        ),
        "Consulta causal condicionada às hipóteses de identificação e positividade.",
        "Documento Técnico Corrigido, seção 7",
        FormulaEvidence.NOT_DEMONSTRATED,
    ),
)


def list_formulas() -> tuple[FormulaSpec, ...]:
    return FORMULAS


def get_formula(formula_id: str) -> FormulaSpec:
    normalized = formula_id.upper()
    for formula in FORMULAS:
        if formula.formula_id.upper() == normalized:
            return formula
    raise KeyError(f"Fórmula desconhecida: {formula_id}")
