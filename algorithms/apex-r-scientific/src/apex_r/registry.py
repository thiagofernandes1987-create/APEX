"""Catálogo canônico dos módulos APEX-R e seu estado real de implementação."""

from __future__ import annotations

from .contracts import ModuleDescriptor, ModuleReadiness


MODULES: tuple[ModuleDescriptor, ...] = (
    ModuleDescriptor("M0", "Identificabilidade", "Desenho experimental e identificabilidade", ModuleReadiness.ACTIVE, ("M1",)),
    ModuleDescriptor("M1", "Configuração e proveniência", "Manifestos, hashes e rastreabilidade", ModuleReadiness.ACTIVE),
    ModuleDescriptor("M2", "Camada molecular", "Afinidade, energia livre e calibração", ModuleReadiness.ACTIVE, ("M1",)),
    ModuleDescriptor("M2.5", "CausalDSM", "Rede causal e propagação mecanística", ModuleReadiness.SCAFFOLDED, ("M2",)),
    ModuleDescriptor("M3", "Hemodinâmica", "Modelos Windkessel e respostas a estímulos", ModuleReadiness.ACTIVE, ("M1",)),
    ModuleDescriptor("M4", "PBPK + Bayes", "Balanço de massa e farmacocinética fisiológica", ModuleReadiness.ACTIVE, ("M1", "M2")),
    ModuleDescriptor("M5A", "PD estática", "Relações concentração-efeito", ModuleReadiness.PLANNED, ("M4",)),
    ModuleDescriptor("M5B", "PD dinâmica", "Resposta temporal e tolerância", ModuleReadiness.PLANNED, ("M4",)),
    ModuleDescriptor("M6", "Sinergia", "Modelos de referência para combinações", ModuleReadiness.PLANNED, ("M5A",)),
    ModuleDescriptor("M7", "Risco e decisão", "Decisão multicritério e margens de segurança", ModuleReadiness.PLANNED, ("M4", "M5A")),
    ModuleDescriptor("M8", "Otimização robusta", "Otimização sob restrições e incerteza", ModuleReadiness.PLANNED, ("M7",)),
    ModuleDescriptor("M9", "Incerteza", "Sensibilidade, incerteza e contrafactuais", ModuleReadiness.PLANNED, ("M8",)),
    ModuleDescriptor("M10", "Relatório", "Relatório técnico reproduzível", ModuleReadiness.SCAFFOLDED, ("M11",)),
    ModuleDescriptor("M11", "Validação em camadas", "Validação matemática, computacional e empírica", ModuleReadiness.SCAFFOLDED),
    ModuleDescriptor("PCL", "Perfil pré-clínico", "Tradução pré-clínica PCL-0 a PCL-5", ModuleReadiness.SCAFFOLDED, ("M4", "M7"), True),
)


def list_modules() -> tuple[ModuleDescriptor, ...]:
    return MODULES


def get_module(module_id: str) -> ModuleDescriptor:
    normalized = module_id.upper()
    for descriptor in MODULES:
        if descriptor.module_id.upper() == normalized:
            return descriptor
    raise KeyError(f"Módulo desconhecido: {module_id}")
