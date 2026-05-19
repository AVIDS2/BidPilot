from app.scenarios.templates import resolve_default_template


def test_resolve_default_template() -> None:
    template = resolve_default_template("bidpilot")
    assert template["scenario_key"] == "bidpilot"
