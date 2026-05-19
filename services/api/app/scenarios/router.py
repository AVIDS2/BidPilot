from fastapi import APIRouter, HTTPException

from .registry import get_scenario, list_scenarios
from .templates import get_sections_for_scenario, resolve_default_template

router = APIRouter(prefix="/scenarios", tags=["scenarios"])


@router.get("")
def get_scenarios() -> list[dict[str, str]]:
    return list_scenarios()


@router.get("/{scenario_key}")
def get_scenario_detail(scenario_key: str) -> dict[str, str]:
    pkg = get_scenario(scenario_key)
    if pkg is None:
        raise HTTPException(status_code=404, detail="Scenario not found")
    return {
        "key": pkg.key,
        "label": pkg.label,
        "description": pkg.description,
        "default_sections": ",".join(pkg.default_sections),
        "requirement_keywords": ",".join(pkg.requirement_keywords),
        "drafting_system_prompt": pkg.drafting_system_prompt,
    }


@router.get("/{scenario_key}/sections")
def get_scenario_sections(scenario_key: str) -> list[dict[str, str]]:
    try:
        return get_sections_for_scenario(scenario_key)
    except ValueError:
        raise HTTPException(status_code=404, detail="Scenario not found")


@router.get("/{scenario_key}/template")
def get_scenario_template(scenario_key: str) -> dict[str, str]:
    try:
        return resolve_default_template(scenario_key)
    except ValueError:
        raise HTTPException(status_code=404, detail="Scenario not found")
