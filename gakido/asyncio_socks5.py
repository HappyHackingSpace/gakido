from __future__ import annotations

import socket
import struct
import urllib.parse


async def _socks5_greeting(writer, reader, username: str | None, password: str | None) -> None:
    """Send SOCKS5 greeting and choose auth method."""
    if username is not None:
        writer.write(b"\x05\x02\x00\x02")
    else:
        writer.write(b"\x05\x01\x00")
    await writer.drain()
    response = await reader.readexactly(2)
    if len(response) != 2 or response[0] != 0x05:
        raise ConnectionError("Invalid SOCKS5 greeting response")
    method = response[1]
    if method == 0x00:
        return
    elif method == 0x02:
        if username is None:
            raise ConnectionError("Server requested username/password auth but none provided")
        await _socks5_username_password_auth(writer, reader, username, password or "")
    elif method == 0xFF:
        raise ConnectionError("SOCKS5 server rejected all auth methods")
    else:
        raise ConnectionError(f"SOCKS5 server selected unsupported auth method: {method}")


async def _socks5_username_password_auth(writer, reader, username: str, password: str) -> None:
    """Perform SOCKS5 username/password authentication (RFC 1929)."""
    user_bytes = username.encode("utf-8")
    pass_bytes = password.encode("utf-8")
    request = bytes([0x01, len(user_bytes)]) + user_bytes + bytes([len(pass_bytes)]) + pass_bytes
    writer.write(request)
    await writer.drain()
    response = await reader.readexactly(2)
    if len(response) != 2 or response[0] != 0x01:
        raise ConnectionError("Invalid username/password auth response")
    if response[1] != 0x00:
        raise ConnectionError("SOCKS5 username/password authentication failed")


async def _socks5_connect(
    writer,
    reader,
    target_host: str,
    target_port: int,
    resolve_hostname: bool = False,
) -> None:
    """Send SOCKS5 CONNECT request for the target host:port."""
    atyp = 0x03  # DOMAINNAME
    addr_bytes = target_host.encode("utf-8")
    if not resolve_hostname:
        # Resolve to IP and use IPv4/IPv6 address type
        try:
            infos = socket.getaddrinfo(target_host, target_port, family=socket.AF_INET, proto=socket.IPPROTO_TCP)
        except socket.gaierror as exc:
            raise ConnectionError(f"Failed to resolve {target_host}: {exc}") from exc
        if not infos:
            raise ConnectionError(f"No address info for {target_host}")
        family, _, _, _, sockaddr = infos[0]
        ip_bytes = socket.inet_pton(family, sockaddr[0])
        atyp = 0x01 if family == socket.AF_INET else 0x04
        addr_bytes = ip_bytes
    # Build request
    request = bytes([0x05, 0x01, 0x00, atyp])
    if atyp == 0x03:
        request += bytes([len(addr_bytes)]) + addr_bytes
    else:
        request += addr_bytes
    request += struct.pack("!H", target_port)
    writer.write(request)
    await writer.drain()
    # Read response
    ver, rep, _, atyp_bnd, bnd_addr, bnd_port = await _socks5_read_response(reader)
    if ver != 0x05:
        raise ConnectionError(f"Invalid SOCKS5 response version: {ver}")
    if rep != 0x00:
        errors = {
            0x01: "General SOCKS server failure",
            0x02: "Connection not allowed by ruleset",
            0x03: "Network unreachable",
            0x04: "Host unreachable",
            0x05: "Connection refused",
            0x06: "TTL expired",
            0x07: "Command not supported",
            0x08: "Address type not supported",
        }
        msg = errors.get(rep, f"SOCKS5 error code {rep}")
        raise ConnectionError(f"SOCKS5 connect failed: {msg}")


async def _socks5_read_response(reader) -> tuple[int, int, int, int, bytes, int]:
    """Read SOCKS5 connect response and parse components."""
    header = await reader.readexactly(4)
    ver, rep, rsv, atyp = struct.unpack("!BBBB", header)
    if atyp == 0x01:
        addr = await reader.readexactly(4)
    elif atyp == 0x03:
        len_byte = await reader.readexactly(1)
        addr_len = len_byte[0]
        addr = await reader.readexactly(addr_len)
    elif atyp == 0x04:
        addr = await reader.readexactly(16)
    else:
        raise ConnectionError(f"Unknown ATYP {atyp} in SOCKS5 response")
    port_bytes = await reader.readexactly(2)
    port = struct.unpack("!H", port_bytes)[0]
    return ver, rep, rsv, atyp, addr, port


def _parse_socks5_url(url: str) -> tuple[str, int, str | None, str | None]:
    """Parse a socks5:// or socks5h:// URL into (host, port, username, password)."""
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ("socks5", "socks5h"):
        raise ValueError(f"Invalid SOCKS5 URL scheme: {parsed.scheme}")
    if not parsed.hostname:
        raise ValueError("SOCKS5 URL missing hostname")
    host = parsed.hostname
    port = parsed.port or 1080
    username = parsed.username
    password = parsed.password
    return host, port, username, password


async def socks5_handshake_async(
    writer,
    reader,
    proxy_url: str,
    target_host: str,
    target_port: int,
) -> None:
    """
    Perform a full SOCKS5 handshake over asyncio streams.
    Supports socks5:// (resolve locally) and socks5h:// (proxy resolves) schemes,
    and optional username/password authentication.
    """
    _, _, username, password = _parse_socks5_url(proxy_url)
    # Greeting and auth
    await _socks5_greeting(writer, reader, username, password)
    # Connect request
    resolve_hostname = proxy_url.startswith("socks5h://")
    await _socks5_connect(writer, reader, target_host, target_port, resolve_hostname=resolve_hostname)
