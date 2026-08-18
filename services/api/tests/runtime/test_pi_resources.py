from app.runtime.pi_adapter import _pi_resources, _pi_sandbox


def test_pi_resources_only_expose_server_owned_extensions_and_skill_metadata() -> None:
    resources = _pi_resources()

    assert resources["extensions"] == ["bidpilot-governance", "bidpilot-skills"]
    assert resources["skills"]
    assert all(set(skill) == {"name", "description"} for skill in resources["skills"])
    assert all("content" not in skill and "path" not in skill for skill in resources["skills"])


def test_pi_cloud_sandbox_never_maps_full_access_to_host_tools() -> None:
    sandbox = _pi_sandbox()

    assert sandbox == {
        "profile": "governed_cloud",
        "hostTools": "disabled",
        "network": "bridge_only",
        "maxToolInputBytes": 128 * 1024,
        "maxToolObservationBytes": 512 * 1024,
    }
