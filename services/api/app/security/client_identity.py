"""Resolve a client address without trusting spoofable forwarding headers."""

from __future__ import annotations

import ipaddress
import hashlib
import os
from collections.abc import Mapping

from fastapi import Request


TRUSTED_PROXY_CIDRS_ENV = "DOCPILOT_TRUSTED_PROXY_CIDRS"


class ClientIdentityConfigurationError(ValueError):
    """The trusted-proxy configuration is missing or malformed."""


def parse_trusted_proxy_cidrs(value: str | None) -> tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...]:
    """Parse a comma-separated list of trusted proxy addresses or networks."""
    if not value:
        return ()

    networks: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = []
    for raw_network in value.split(","):
        candidate = raw_network.strip()
        if not candidate:
            continue
        try:
            networks.append(ipaddress.ip_network(candidate, strict=False))
        except ValueError:
            raise ClientIdentityConfigurationError(
                f"{TRUSTED_PROXY_CIDRS_ENV} contains an invalid CIDR or IP address"
            ) from None
    return tuple(networks)


def configured_trusted_proxy_cidrs(
    environment: Mapping[str, str] | None = None,
) -> tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...]:
    source = os.environ if environment is None else environment
    return parse_trusted_proxy_cidrs(source.get(TRUSTED_PROXY_CIDRS_ENV))


def require_trusted_proxy_configuration(
    environment: Mapping[str, str] | None = None,
) -> tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...]:
    networks = configured_trusted_proxy_cidrs(environment)
    if not networks:
        raise ClientIdentityConfigurationError(
            f"{TRUSTED_PROXY_CIDRS_ENV} is required when production proxy headers are enabled"
        )
    return networks


def _valid_ip(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return str(ipaddress.ip_address(value.strip()))
    except ValueError:
        return None


def _first_forwarded_ip(value: str | None) -> str | None:
    if not value:
        return None
    for candidate in value.split(","):
        parsed = _valid_ip(candidate)
        if parsed:
            return parsed
    return None


def request_is_from_trusted_proxy(
    request: Request,
    *,
    environment: Mapping[str, str] | None = None,
) -> bool:
    direct_peer = _valid_ip(request.client.host if request.client else None)
    if direct_peer is None:
        return False
    peer_address = ipaddress.ip_address(direct_peer)
    return any(peer_address in network for network in configured_trusted_proxy_cidrs(environment))


def get_client_ip(
    request: Request,
    *,
    environment: Mapping[str, str] | None = None,
) -> str:
    """Return the direct peer unless that peer is a configured trusted proxy.

    `X-Forwarded-For` and `X-Real-IP` are intentionally ignored for all other
    peers. The reverse proxy must overwrite these headers before forwarding to
    the API; accepting them from arbitrary callers would allow quota evasion.
    """
    direct_peer = request.client.host if request.client else "unknown"
    if not request_is_from_trusted_proxy(request, environment=environment):
        return direct_peer

    forwarded_ip = _first_forwarded_ip(request.headers.get("X-Forwarded-For"))
    if forwarded_ip:
        return forwarded_ip
    real_ip = _valid_ip(request.headers.get("X-Real-IP"))
    return real_ip or direct_peer


def get_client_identity_fingerprint(
    request: Request,
    *,
    environment: Mapping[str, str] | None = None,
) -> str:
    """Return a stable internal rate-limit key without persisting the raw IP."""
    client_ip = get_client_ip(request, environment=environment)
    return hashlib.sha256(client_ip.encode("utf-8")).hexdigest()
