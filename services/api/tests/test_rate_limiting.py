"""Test API rate limiting."""

import os


def test_rate_limit_env_var_is_parsed():
    """DOCPILOT_RATE_LIMIT env var should be parseable as 'N/minute'."""
    val = os.environ.get("DOCPILOT_RATE_LIMIT", "60/minute")
    count, unit = val.split("/")
    assert unit == "minute"
    assert int(count) > 0


def test_normal_traffic_within_configured_limit(client):
    """65 requests should all pass when rate limit is set high (test mode)."""
    responses = []
    for _ in range(65):
        resp = client.get("/health")
        responses.append(resp.status_code)
    assert all(s == 200 for s in responses), (
        f"Expected all 200, got {set(responses)}"
    )
