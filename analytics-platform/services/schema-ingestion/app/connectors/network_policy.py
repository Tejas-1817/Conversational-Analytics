"""Outbound network policy for customer database connections.

This module validates database hostnames before connector engines are created.
It performs no database connection and stores no credentials.
"""

from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass
from typing import Iterable


IPAddress = ipaddress.IPv4Address | ipaddress.IPv6Address
IPNetwork = ipaddress.IPv4Network | ipaddress.IPv6Network


class NetworkPolicyError(ValueError):
    """Raised when a database endpoint violates outbound network policy."""


@dataclass(frozen=True, slots=True)
class ResolvedDatabaseEndpoint:
    """A validated database endpoint and its resolved IP addresses."""

    host: str
    port: int
    addresses: tuple[IPAddress, ...]


def _parse_allowed_networks(
    cidrs: Iterable[str],
) -> tuple[IPNetwork, ...]:
    """Parse explicitly allowed private network ranges."""

    networks: list[IPNetwork] = []

    for raw_cidr in cidrs:
        cidr = str(raw_cidr).strip()

        if not cidr:
            continue

        try:
            networks.append(
                ipaddress.ip_network(
                    cidr,
                    strict=False,
                )
            )
        except ValueError as exc:
            raise NetworkPolicyError(
                f"Invalid allowed network range: {cidr!r}"
            ) from exc

    return tuple(networks)


def _is_explicitly_allowed(
    address: IPAddress,
    allowed_networks: tuple[IPNetwork, ...],
) -> bool:
    """Return whether an address belongs to an allowed CIDR."""

    return any(
        address.version == network.version
        and address in network
        for network in allowed_networks
    )


def _validate_address(
    address: IPAddress,
    *,
    allowed_networks: tuple[IPNetwork, ...],
    allow_loopback: bool,
) -> None:
    """Validate one resolved address."""

    if address.is_unspecified:
        raise NetworkPolicyError(
            f"Unspecified database address is not allowed: {address}"
        )

    if address.is_multicast:
        raise NetworkPolicyError(
            f"Multicast database address is not allowed: {address}"
        )

    if address.is_link_local:
        raise NetworkPolicyError(
            f"Link-local database address is not allowed: {address}"
        )

    if address.is_reserved:
        raise NetworkPolicyError(
            f"Reserved database address is not allowed: {address}"
        )

    if address.is_loopback:
        if allow_loopback:
            return

        raise NetworkPolicyError(
            f"Loopback database address is not allowed: {address}"
        )

    if address.is_private:
        if _is_explicitly_allowed(
            address,
            allowed_networks,
        ):
            return

        raise NetworkPolicyError(
            "Private database address is not in an allowed network: "
            f"{address}"
        )

    # Reject other non-global ranges, including special-use address space.
    if not address.is_global:
        if _is_explicitly_allowed(
            address,
            allowed_networks,
        ):
            return

        raise NetworkPolicyError(
            f"Non-global database address is not allowed: {address}"
        )


def validate_database_endpoint(
    host: str,
    port: int,
    *,
    allowed_private_cidrs: Iterable[str] = (),
    allow_loopback: bool = False,
) -> ResolvedDatabaseEndpoint:
    """Resolve and validate a customer database endpoint.

    Public IP addresses are accepted by default. Private addresses must belong
    to an explicitly allowed CIDR. Loopback access must be enabled separately
    for local development.
    """

    normalized_host = str(host or "").strip()

    if not normalized_host:
        raise NetworkPolicyError(
            "Database host is required."
        )

    if not isinstance(port, int) or not 1 <= port <= 65_535:
        raise NetworkPolicyError(
            "Database port must be between 1 and 65535."
        )

    # Remove brackets commonly used around IPv6 literals.
    if (
        normalized_host.startswith("[")
        and normalized_host.endswith("]")
    ):
        normalized_host = normalized_host[1:-1]

    # The host field must contain only a hostname or IP address.
    if any(
        character in normalized_host
        for character in ("/", "\\", "@", "?", "#")
    ):
        raise NetworkPolicyError(
            "Database host must be a hostname or IP address, not a URL."
        )

    allowed_networks = _parse_allowed_networks(
        allowed_private_cidrs
    )

    addresses: set[IPAddress] = set()

    try:
        # Avoid DNS lookup when the user supplied an IP literal.
        addresses.add(
            ipaddress.ip_address(normalized_host)
        )

    except ValueError:
        try:
            results = socket.getaddrinfo(
                normalized_host,
                port,
                type=socket.SOCK_STREAM,
            )
        except socket.gaierror as exc:
            raise NetworkPolicyError(
                f"Database hostname could not be resolved: "
                f"{normalized_host!r}"
            ) from exc

        for result in results:
            resolved_ip = result[4][0]

            # Remove an IPv6 scope identifier when present.
            resolved_ip = resolved_ip.split("%", 1)[0]

            try:
                addresses.add(
                    ipaddress.ip_address(resolved_ip)
                )
            except ValueError as exc:
                raise NetworkPolicyError(
                    f"DNS returned an invalid address: {resolved_ip!r}"
                ) from exc

    if not addresses:
        raise NetworkPolicyError(
            f"Database hostname resolved to no addresses: "
            f"{normalized_host!r}"
        )

    # Reject the entire hostname if any answer violates policy. This prevents a
    # hostname with both acceptable and internal addresses from bypassing it.
    for address in addresses:
        _validate_address(
            address,
            allowed_networks=allowed_networks,
            allow_loopback=allow_loopback,
        )

    ordered_addresses = tuple(
        sorted(
            addresses,
            key=lambda address: (
                address.version,
                int(address),
            ),
        )
    )

    return ResolvedDatabaseEndpoint(
        host=normalized_host,
        port=port,
        addresses=ordered_addresses,
    )