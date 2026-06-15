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
