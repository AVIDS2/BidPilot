from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ScenarioPackage:
    """Metadata for a scenario package."""

    key: str
    label: str
    description: str
    default_sections: list[str]
    requirement_keywords: list[str]
    drafting_system_prompt: str
    export_filename_pattern: str = "{project_name}-deliverable.docx"


_PACKAGES: dict[str, ScenarioPackage] = {
    "bidpilot": ScenarioPackage(
        key="bidpilot",
        label="BidPilot",
        description="Bid response and presales proposal generation",
        default_sections=[
            "exec-summary",
            "technical-approach",
            "pricing-summary",
            "past-performance",
            "staffing-plan",
        ],
        requirement_keywords=["shall", "must", "required", "mandatory", "compliance"],
        drafting_system_prompt="You are a professional proposal writer. Write clear, evidence-backed sections in markdown. Cite specific evidence where appropriate.",
    ),
    "contractpilot": ScenarioPackage(
        key="contractpilot",
        label="ContractPilot",
        description="Contract review and compliance analysis",
        default_sections=[
            "scope-of-work",
            "terms-and-conditions",
            "service-level-agreements",
            "payment-terms",
            "compliance-requirements",
            "risk-assessment",
        ],
        requirement_keywords=["shall", "must", "obligation", "liable", "indemnify", "warranty", "termination", "penalty"],
        drafting_system_prompt="You are a contract analyst. Identify key obligations, risks, and compliance requirements. Write clear, structured analysis in markdown with specific clause references.",
    ),
}


def list_scenarios() -> list[dict[str, str]]:
    return [{"key": p.key, "label": p.label, "description": p.description} for p in _PACKAGES.values()]


def get_scenario(key: str) -> ScenarioPackage | None:
    return _PACKAGES.get(key)


def get_scenario_or_raise(key: str) -> ScenarioPackage:
    pkg = _PACKAGES.get(key)
    if pkg is None:
        raise ValueError(f"Unknown scenario package: {key}")
    return pkg
