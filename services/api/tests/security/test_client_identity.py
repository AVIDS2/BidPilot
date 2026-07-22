from __future__ import annotations

import pytest
from starlette.requests import Request

from app.security.client_identity import (
    ClientIdentityConfigurationError,
    get_client_identity_fingerprint,
    get_client_ip,
    parse_trusted_proxy_cidrs,
    request_is_from_trusted_proxy,
)


def _request(peer: str, headers: dict[str, str] | None = None) -> Request:
    encoded_headers = [
        (name.lower().encode("latin-1"), value.encode("latin-1"))
        for name, value in (headers or {}).items()
    ]
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/health",
            "headers": encoded_headers,
            "client": (peer, 32100),
            "scheme": "http",
            "server": ("testserver", 80),
        }
    )


def test_untrusted_peer_cannot_override_client_identity_with_forwarded_header() -> None:
    request = _request(
        "198.51.100.10",
        {"X-Forwarded-For": "203.0.113.55", "X-Real-IP": "203.0.113.56"},
    )

    assert get_client_ip(request, environment={"DOCPILOT_TRUSTED_PROXY_CIDRS": "10.0.0.0/8"}) == "198.51.100.10"


def test_trusted_proxy_can_forward_the_client_identity() -> None:
    request = _request("10.1.2.3", {"X-Forwarded-For": "203.0.113.55, 10.1.2.3"})
    environment = {"DOCPILOT_TRUSTED_PROXY_CIDRS": "10.0.0.0/8"}

    assert request_is_from_trusted_proxy(request, environment=environment) is True
    assert get_client_ip(request, environment=environment) == "203.0.113.55"
    assert get_client_identity_fingerprint(request, environment=environment) != "203.0.113.55"


def test_trusted_proxy_can_fall_back_to_x_real_ip() -> None:
    request = _request("192.0.2.10", {"X-Real-IP": "2001:db8::5"})

    assert get_client_ip(
        request,
        environment={"DOCPILOT_TRUSTED_PROXY_CIDRS": "192.0.2.10/32"},
    ) == "2001:db8::5"


def test_non_ip_test_peer_does_not_trust_forwarded_headers() -> None:
    request = _request("testclient", {"X-Forwarded-For": "203.0.113.55"})

    assert get_client_ip(
        request,
        environment={"DOCPILOT_TRUSTED_PROXY_CIDRS": "127.0.0.1/32"},
    ) == "testclient"


def test_invalid_trusted_proxy_configuration_is_rejected() -> None:
    with pytest.raises(ClientIdentityConfigurationError):
        parse_trusted_proxy_cidrs("not-an-ip-range")
