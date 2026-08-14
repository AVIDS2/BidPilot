def test_list_notifications_returns_empty(client) -> None:
    response = client.get("/notifications")

    assert response.status_code == 200
    assert response.json() == []


def test_mark_notification_read_is_noop(client) -> None:
    response = client.patch("/notifications/test-id/read")

    assert response.status_code == 204
    assert response.content == b""


def test_mark_all_notifications_read_is_noop(client) -> None:
    response = client.patch("/notifications/read-all")

    assert response.status_code == 204
    assert response.content == b""


def test_notification_preferences_default_and_update(client) -> None:
    initial = client.get("/notifications/preferences")

    assert initial.status_code == 200
    assert initial.json() == {
        "in_app_enabled": True,
        "email_enabled": True,
        "review_updates": True,
        "agent_updates": True,
        "radar_updates": True,
        "material_updates": True,
    }

    updated = client.patch(
        "/notifications/preferences",
        json={"email_enabled": False, "review_updates": False},
    )

    assert updated.status_code == 200
    assert updated.json()["email_enabled"] is False
    assert updated.json()["review_updates"] is False
    assert updated.json()["in_app_enabled"] is True
    assert client.get("/notifications/preferences").json() == updated.json()
