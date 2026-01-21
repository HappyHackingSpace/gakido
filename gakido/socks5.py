from __future__ import annotations

import socket
import struct
import urllib.parse


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


def _socks5_greeting(sock: socket.socket, username: str | None, password: str | None) -> None:
    """Send SOCKS5 greeting and choose auth method."""
    if username is not None:
        # Offer username/password auth (0x02) and no auth (0x00)
        sock.sendall(b"\x05\x02\x00\x02")
    else:
        # Only offer no auth
        sock.sendall(b"\x05\x01\x00")
    response = sock.recv(2)
    if len(response) != 2 or response[0] != 0x05:
        raise ConnectionError("Invalid SOCKS5 greeting response")
    method = response[1]
    if method == 0x00:
        # No auth required
        return
    elif method == 0x02:
        if username is None:
            raise ConnectionError("Server requested username/password auth but none provided")
        _socks5_username_password_auth(sock, username, password or "")
    elif method == 0xFF:
        raise ConnectionError("SOCKS5 server rejected all auth methods")
    else:
        raise ConnectionError(f"SOCKS5 server selected unsupported auth method: {method}")


def _socks5_username_password_auth(sock: socket.socket, username: str, password: str) -> None:
    """Perform SOCKS5 username/password authentication (RFC 1929)."""
    user_bytes = username.encode("utf-8")
    pass_bytes = password.encode("utf-8")
    request = bytes([0x01, len(user_bytes)]) + user_bytes + bytes([len(pass_bytes)]) + pass_bytes
    sock.sendall(request)
    response = sock.recv(2)
    if len(response) != 2 or response[0] != 0x01:
        raise ConnectionError("Invalid username/password auth response")
    if response[1] != 0x00:
        raise ConnectionError("SOCKS5 username/password authentication failed")


def _socks5_connect(
    sock: socket.socket,
    target_host: str,
    target_port: int,
    resolve_hostname: bool = False,
) -> None:
    """
    Send SOCKS5 CONNECT request for the target host:port.
    If resolve_hostname is False (socks5://), we send IP address (requires pre-resolution).
    If resolve_hostname is True (socks5h://), we send the hostname directly.
    """
    # Build request
    # VER CMD RSV ATYP DST.ADDR DST.PORT
    # VER=0x05, CMD=0x01 (CONNECT), RSV=0x00
    atyp = 0x03  # DOMAINNAME
    addr_bytes = target_host.encode("utf-8")
    if not resolve_hostname:
        # Resolve to IP and use IPv4/IPv6 address type
        try:
            # getaddrinfo returns IPv4/IPv6; we prefer IPv4 for simplicity
            infos = socket.getaddrinfo(target_host, target_port, family=socket.AF_INET, proto=socket.IPPROTO_TCP)
        except socket.gaierror as exc:
            raise ConnectionError(f"Failed to resolve {target_host}: {exc}") from exc
        if not infos:
            raise ConnectionError(f"No address info for {target_host}")
            # Use IPv4
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
    sock.sendall(request)
    # Read response: VER REP RSV ATYP BND.ADDR BND.PORT
    response = _socks5_read_response(sock)
    ver, rep, _, atyp_bnd, bnd_addr, bnd_port = response
    if ver != 0x05:
        raise ConnectionError(f"Invalid SOCKS5 response version: {ver}")
    if rep != 0x00:
        # Map common error codes
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
    # We don't need the bound address; just ensure it's parsable
    # (for completeness we could parse it, but not required)


def _socks5_read_response(sock: socket.socket) -> tuple[int, int, int, int, bytes, int]:
    """Read SOCKS5 connect response and parse components."""
    # First 4 bytes: VER REP RSV ATYP
    header = sock.recv(4)
    if len(header) != 4:
        raise ConnectionError("Incomplete SOCKS5 response header")
    ver, rep, rsv, atyp = struct.unpack("!BBBB", header)
    if atyp == 0x01:
        # IPv4: 4 bytes
        addr = sock.recv(4)
        if len(addr) != 4:
            raise ConnectionError("Incomplete IPv4 address in SOCKS5 response")
    elif atyp == 0x03:
        # Domain name: first byte is length, then that many bytes
        len_byte = sock.recv(1)
        if len(len_byte) != 1:
            raise ConnectionError("Missing domain length in SOCKS5 response")
        addr_len = len_byte[0]
        addr = sock.recv(addr_len)
        if len(addr) != addr_len:
            raise ConnectionError("Incomplete domain name in SOCKS5 response")
    elif atyp == 0x04:
        # IPv6: 16 bytes
        addr = sock.recv(16)
        if len(addr) != 16:
            raise ConnectionError("Incomplete IPv6 address in SOCKS5 response")
    else:
        raise ConnectionError(f"Unknown ATYP {atyp} in SOCKS5 response")
    port_bytes = sock.recv(2)
    if len(port_bytes) != 2:
        raise ConnectionError("Incomplete port in SOCKS5 response")
    port = struct.unpack("!H", port_bytes)[0]
    return ver, rep, rsv, atyp, addr, port


def socks5_handshake(
    sock: socket.socket,
    proxy_url: str,
    target_host: str,
    target_port: int,
) -> None:
    """
    Perform a full SOCKS5 handshake over the given connected socket.
    Supports socks5:// (resolve locally) and socks5h:// (proxy resolves) schemes,
    and optional username/password authentication.
    """
    proxy_host, proxy_port, username, password = _parse_socks5_url(proxy_url)
    # At this point, sock should already be connected to proxy_host:proxy_port
    # Greeting and auth
    _socks5_greeting(sock, username, password)
    # Connect request
    resolve_hostname = proxy_url.startswith("socks5h://")
    _socks5_connect(sock, target_host, target_port, resolve_hostname=resolve_hostname)
