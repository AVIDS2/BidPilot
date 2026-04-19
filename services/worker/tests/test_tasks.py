from app.tasks import ping


def test_ping_task() -> None:
    assert ping() == "pong"
