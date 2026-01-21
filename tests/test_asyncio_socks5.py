import pytest
import asyncio
import socket
from unittest.mock import AsyncMock, MagicMock, patch

from gakido.asyncio_socks5 import (
    _parse_socks5_url,
    _socks5_greeting,
    _socks5_username_password_auth,
    _socks5_connect,
    _socks5_read_response,
    socks5_handshake_async,
)


def test_parse_socks5_url():
    assert _parse_socks5_url("socks5://proxy:1080") == ("proxy", 1080, None, None)
    assert _parse_socks5_url("socks5://user:pass@proxy:8080") == ("proxy", 8080, "user", "pass")
    assert _parse_socks5_url("socks5h://proxy") == ("proxy", 1080, None, None)
    with pytest.raises(ValueError):
        _parse_socks5_url("http://proxy:1080")
    with pytest.raises(ValueError):
        _parse_socks5_url("socks5://")


@pytest.mark.asyncio
async def test_socks5_greeting_no_auth():
    writer = MagicMock()
    writer.drain = AsyncMock()
    reader = MagicMock()
    reader.readexactly = AsyncMock(return_value=b"\x05\x00")

    await _socks5_greeting(writer, reader, None, None)

    writer.write.assert_called_once_with(b"\x05\x01\x00")


@pytest.mark.asyncio
async def test_socks5_greeting_with_auth_accept():
    writer = MagicMock()
    writer.drain = AsyncMock()
    reader = MagicMock()
    reader.readexactly = AsyncMock(side_effect=[b"\x05\x02", b"\x01\x00"])

    await _socks5_greeting(writer, reader, "user", "pass")

    # First call: greeting offering both auth methods
    assert writer.write.call_args_list[0][0][0] == b"\x05\x02\x00\x02"
    # Second call: username/password auth request
    auth_req = writer.write.call_args_list[1][0][0]
    assert auth_req.startswith(b"\x01")
    assert b"user" in auth_req
    assert b"pass" in auth_req


@pytest.mark.asyncio
async def test_socks5_greeting_server_rejects_all():
    writer = MagicMock()
    writer.drain = AsyncMock()
    reader = MagicMock()
    reader.readexactly = AsyncMock(return_value=b"\x05\xff")

    with pytest.raises(ConnectionError, match="rejected all auth methods"):
        await _socks5_greeting(writer, reader, None, None)


@pytest.mark.asyncio
async def test_socks5_username_password_auth_success():
    writer = MagicMock()
    writer.drain = AsyncMock()
    reader = MagicMock()
    reader.readexactly = AsyncMock(return_value=b"\x01\x00")

    await _socks5_username_password_auth(writer, reader, "user", "pass")

    # Verify request format: 0x01 + user_len + user + pass_len + pass
    call_args = writer.write.call_args[0][0]
    assert call_args.startswith(b"\x01")
    assert b"user" in call_args
    assert b"pass" in call_args


@pytest.mark.asyncio
async def test_socks5_username_password_auth_failure():
    writer = MagicMock()
    writer.drain = AsyncMock()
    reader = MagicMock()
    reader.readexactly = AsyncMock(return_value=b"\x01\x01")

    with pytest.raises(ConnectionError, match="authentication failed"):
        await _socks5_username_password_auth(writer, reader, "user", "wrong")


@pytest.mark.asyncio
@patch('socket.getaddrinfo')
async def test_socks5_connect_domainname(mock_getaddrinfo):
    mock_getaddrinfo.return_value = [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("127.0.0.1", 80))]
    writer = MagicMock()
    writer.drain = AsyncMock()
    reader = MagicMock()
    # Stage reads: header (4) + domain_len (1) + domain (4) + port (2)
    reader.readexactly = AsyncMock(side_effect=[
        b"\x05\x00\x00\x03",  # header indicating domainname
        b"\x04",              # domain length = 4
        b"host",              # domain bytes
        b"\x00\x50",          # port 80
    ])

    await _socks5_connect(writer, reader, "host", 80, resolve_hostname=True)

    # Verify request: VER CMD RSV ATYP len host port
    call_args = writer.write.call_args[0][0]
    assert call_args.startswith(b"\x05\x01\x00\x03\x04host")
    # Port 80 (0x0050) should be at the end
    assert call_args.endswith(b"\x00\x50")


@pytest.mark.asyncio
async def test_socks5_connect_ipv4():
    writer = MagicMock()
    writer.drain = AsyncMock()
    reader = MagicMock()
    # Simulate IPv4 address response: VER REP RSV ATYP (4 bytes IP) + port
    reader.readexactly = AsyncMock(side_effect=[
        b"\x05\x00\x00\x01",  # header
        b"\x7f\x00\x00\x01",  # 127.0.0.1
        b"\x00\x50",          # port 80
    ])

    await _socks5_connect(writer, reader, "localhost", 80, resolve_hostname=False)

    # Verify request used IPv4 ATYP (0x01) and 4-byte IP
    call_args = writer.write.call_args[0][0]
    assert call_args.startswith(b"\x05\x01\x00\x01")


@pytest.mark.asyncio
@patch('socket.getaddrinfo')
async def test_socks5_connect_error(mock_getaddrinfo):
    mock_getaddrinfo.return_value = [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("127.0.0.1", 80))]
    writer = MagicMock()
    writer.drain = AsyncMock()
    reader = MagicMock()
    # Stage reads: header (4) + domain_len (1) + domain (4) + port (2)
    reader.readexactly = AsyncMock(side_effect=[
        b"\x05\x01\x00\x03",  # header indicating domainname with error code 0x01
        b"\x04",              # domain length = 4
        b"host",              # domain bytes
        b"\x00\x50",          # port 80
    ])

    with pytest.raises(ConnectionError, match="General SOCKS server failure"):
        await _socks5_connect(writer, reader, "host", 80, resolve_hostname=True)


@pytest.mark.asyncio
async def test_socks5_read_response_domain():
    reader = MagicMock()
    reader.readexactly = AsyncMock(side_effect=[
        b"\x05\x00\x00\x03",  # header with ATYP=DOMAINNAME
        b"\x04",              # domain length = 4
        b"host",              # domain bytes
        b"\x00\x50",          # port 80
    ])

    result = await _socks5_read_response(reader)
    assert result == (0x05, 0x00, 0x00, 0x03, b"host", 80)


@pytest.mark.asyncio
async def test_socks5_read_response_ipv4():
    reader = MagicMock()
    reader.readexactly = AsyncMock(side_effect=[
        b"\x05\x00\x00\x01",  # header with ATYP=IPv4
        b"\x7f\x00\x00\x01",  # 127.0.0.1
        b"\x00\x50",          # port 80
    ])

    result = await _socks5_read_response(reader)
    assert result == (0x05, 0x00, 0x00, 0x01, b"\x7f\x00\x00\x01", 80)


@pytest.mark.asyncio
async def test_socks5_read_response_invalid_atyp():
    reader = MagicMock()
    reader.readexactly = AsyncMock(return_value=b"\x05\x00\x00\xff")

    with pytest.raises(ConnectionError, match="Unknown ATYP"):
        await _socks5_read_response(reader)


@pytest.mark.asyncio
@patch('socket.getaddrinfo')
async def test_socks5_handshake_async_no_auth(mock_getaddrinfo):
    mock_getaddrinfo.return_value = [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("127.0.0.1", 80))]
    writer = MagicMock()
    writer.drain = AsyncMock()
    reader = MagicMock()
    # Stage reads: greeting (2) + connect response staged (4+4+2)
    reader.readexactly = AsyncMock(side_effect=[
        b"\x05\x00",          # greeting response (no auth)
        b"\x05\x00\x00\x01",  # connect response header (IPv4)
        b"\x7f\x00\x00\x01",  # IPv4 127.0.0.1
        b"\x00\x50",          # port 80
    ])

    await socks5_handshake_async(writer, reader, "socks5://proxy:1080", "host", 80)

    # Verify greeting and connect were sent
    assert writer.write.call_count == 2
    assert writer.write.call_args_list[0][0][0] == b"\x05\x01\x00"  # greeting
    # For socks5:// (resolve_hostname=False), we send IPv4 ATYP (0x01) and IP
    connect_req = writer.write.call_args_list[1][0][0]
    assert connect_req.startswith(b"\x05\x01\x00\x01")  # VER CMD RSV ATYP=IPv4
    assert b"\x7f\x00\x00\x01" in connect_req  # 127.0.0.1
    assert connect_req.endswith(b"\x00\x50")  # port 80


@pytest.mark.asyncio
@patch('socket.getaddrinfo')
async def test_socks5_handshake_async_with_auth(mock_getaddrinfo):
    mock_getaddrinfo.return_value = [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("127.0.0.1", 80))]
    writer = MagicMock()
    writer.drain = AsyncMock()
    reader = MagicMock()
    # Stage reads: greeting (2) + auth (2) + connect response staged (4+4+2)
    reader.readexactly = AsyncMock(side_effect=[
        b"\x05\x02",          # greeting response (auth offered)
        b"\x01\x00",          # username/password auth success
        b"\x05\x00\x00\x01",  # connect response header (IPv4)
        b"\x7f\x00\x00\x01",  # IPv4 127.0.0.1
        b"\x00\x50",          # port 80
    ])

    await socks5_handshake_async(writer, reader, "socks5://user:pass@proxy:1080", "host", 80)

    # Verify greeting offered both auth methods
    assert writer.write.call_args_list[0][0][0] == b"\x05\x02\x00\x02"
    # Verify auth request was sent
    auth_req = writer.write.call_args_list[1][0][0]
    assert auth_req.startswith(b"\x01")
    assert b"user" in auth_req
    assert b"pass" in auth_req
    # Verify connect was sent with IPv4 ATYP
    connect_req = writer.write.call_args_list[2][0][0]
    assert connect_req.startswith(b"\x05\x01\x00\x01")  # VER CMD RSV ATYP=IPv4
    assert b"\x7f\x00\x00\x01" in connect_req  # 127.0.0.1
    assert connect_req.endswith(b"\x00\x50")  # port 80


@pytest.mark.asyncio
async def test_socks5_handshake_async_invalid_url():
    writer = MagicMock()
    reader = MagicMock()

    with pytest.raises(ValueError, match="Invalid SOCKS5 URL scheme"):
        await socks5_handshake_async(writer, reader, "http://proxy:1080", "host", 80)
