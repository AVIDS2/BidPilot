from __future__ import annotations

from .registry import get_scenario_or_raise


def resolve_default_template(scenario_key: str) -> dict[str, str]:
    """Resolve the default template for a scenario package."""
    package = get_scenario_or_raise(scenario_key)
    return {
        "scenario_key": package.key,
        "template_key": f"{package.key}-default",
        "default_sections": ",".join(package.default_sections),
        "drafting_system_prompt": package.drafting_system_prompt,
    }


def get_sections_for_scenario(scenario_key: str) -> list[dict[str, str]]:
    """Return the default section definitions for a scenario."""
    package = get_scenario_or_raise(scenario_key)
    return [
        {"section_key": key, "title": key.replace("-", " ").title()}
        for key in package.default_sections
    ]


def get_requirement_keywords(scenario_key: str) -> list[str]:
    """Return requirement extraction keywords for a scenario."""
    package = get_scenario_or_raise(scenario_key)
    return package.requirement_keywords


def get_drafting_prompt(scenario_key: str) -> str:
    """Return the system prompt for drafting in a scenario."""
    package = get_scenario_or_raise(scenario_key)
    return package.drafting_system_prompt
