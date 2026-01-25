from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Iterator
from typing import TYPE_CHECKING

from .compression import decode_body

if TYPE_CHECKING:
    import socket
    import ssl


class StreamingResponse:
    """
    Streaming HTTP response that yields chunks without loading entire body into memory.
    
    Use iter_bytes() or iter_lines() to consume the response body incrementally.
    The response must be closed after use to release the connection.
    """

    def __init__(
        self,
        status_code: int,
        reason: str,
        http_version: str,
        headers: list[tuple[str, str]],
        sock: socket.socket | ssl.SSLSocket,
        content_length: int | None,
        chunked: bool,
        content_encoding: str,
        auto_decompress: bool,
        chunk_size: int = 8192,
    ) -> None:
        self.status_code = status_code
        self.reason = reason
        self.http_version = http_version
        self.raw_headers: list[tuple[str, str]] = headers
        self._sock = sock
        self._content_length = content_length
        self._chunked = chunked
        self._content_encoding = content_encoding
        self._auto_decompress = auto_decompress
        self._chunk_size = chunk_size
        self._closed = False
        self._bytes_read = 0

    @property
    def headers(self) -> dict[str, str]:
        out: dict[str, str] = {}
        for name, value in self.raw_headers:
            out[name.lower()] = value
        return out

    def iter_bytes(self, chunk_size: int | None = None) -> Iterator[bytes]:
        """
        Iterate over response body in chunks.
        
        Args:
            chunk_size: Size of chunks to yield (default: 8192)
            
        Yields:
            Raw bytes chunks from the response body
        """
        if self._closed:
            raise RuntimeError("Response has been closed")
        
        size = chunk_size or self._chunk_size
        
        if self._chunked:
            yield from self._iter_chunked(size)
        elif self._content_length is not None:
            yield from self._iter_content_length(size)
        else:
            yield from self._iter_until_close(size)

    def _iter_chunked(self, chunk_size: int) -> Iterator[bytes]:
        """Iterate over chunked transfer encoding."""
        buffer = b""
        
        while True:
            # Read chunk size line
            line = self._readline()
            if not line:
                break
            try:
                size = int(line.strip(), 16)
            except ValueError:
                break
            
            if size == 0:
                # Final chunk, consume trailing CRLF
                self._readline()
                break
            
            # Read chunk data
            remaining = size
            while remaining > 0:
                to_read = min(remaining, chunk_size)
                data = self._read_exact(to_read)
                if not data:
                    break
                remaining -= len(data)
                
                if self._auto_decompress and self._content_encoding:
                    buffer += data
                else:
                    yield data
            
            # Consume CRLF after chunk
            self._read_exact(2)
        
        # Decompress accumulated buffer if needed
        if self._auto_decompress and self._content_encoding and buffer:
            yield decode_body(buffer, self._content_encoding)

    def _iter_content_length(self, chunk_size: int) -> Iterator[bytes]:
        """Iterate with known content length."""
        assert self._content_length is not None
        remaining = self._content_length
        buffer = b""
        
        while remaining > 0:
            to_read = min(remaining, chunk_size)
            data = self._sock.recv(to_read)
            if not data:
                break
            remaining -= len(data)
            
            if self._auto_decompress and self._content_encoding:
                buffer += data
            else:
                yield data
        
        # Decompress accumulated buffer if needed
        if self._auto_decompress and self._content_encoding and buffer:
            yield decode_body(buffer, self._content_encoding)

    def _iter_until_close(self, chunk_size: int) -> Iterator[bytes]:
        """Iterate until connection closes."""
        buffer = b""
        
        while True:
            try:
                data = self._sock.recv(chunk_size)
            except TimeoutError:
                break
            if not data:
                break
            
            if self._auto_decompress and self._content_encoding:
                buffer += data
            else:
                yield data
        
        # Decompress accumulated buffer if needed
        if self._auto_decompress and self._content_encoding and buffer:
            yield decode_body(buffer, self._content_encoding)

    def iter_lines(self, chunk_size: int | None = None, decode: str = "utf-8") -> Iterator[str]:
        """
        Iterate over response body line by line.
        
        Args:
            chunk_size: Size of chunks to read (default: 8192)
            decode: Character encoding for decoding bytes to str (default: utf-8)
            
        Yields:
            Lines from the response body (without line endings)
        """
        pending = b""
        for chunk in self.iter_bytes(chunk_size):
            pending += chunk
            while b"\n" in pending:
                line, pending = pending.split(b"\n", 1)
                yield line.rstrip(b"\r").decode(decode, errors="replace")
        
        # Yield any remaining content
        if pending:
            yield pending.rstrip(b"\r").decode(decode, errors="replace")

    def read(self) -> bytes:
        """Read entire response body into memory. Use with caution for large responses."""
        return b"".join(self.iter_bytes())

    def _readline(self) -> bytes:
        """Read a line from the socket."""
        buf = bytearray()
        while True:
            ch = self._sock.recv(1)
            if not ch:
                break
            buf.extend(ch)
            if buf.endswith(b"\r\n"):
                break
        return bytes(buf)

    def _read_exact(self, n: int) -> bytes:
        """Read exactly n bytes from the socket."""
        remaining = n
        chunks: list[bytes] = []
        while remaining > 0:
            chunk = self._sock.recv(remaining)
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        return b"".join(chunks)

    def close(self) -> None:
        """Close the response and release resources."""
        if not self._closed:
            self._closed = True
            try:
                self._sock.close()
            except Exception:
                pass

    def __enter__(self) -> StreamingResponse:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def __iter__(self) -> Iterator[bytes]:
        return self.iter_bytes()

    def __repr__(self) -> str:
        return f"<StreamingResponse [{self.status_code}]>"


class AsyncStreamingResponse:
    """
    Async streaming HTTP response that yields chunks without loading entire body into memory.
    
    Use aiter_bytes() or aiter_lines() to consume the response body incrementally.
    The response must be closed after use to release the connection.
    """

    def __init__(
        self,
        status_code: int,
        reason: str,
        http_version: str,
        headers: list[tuple[str, str]],
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        content_length: int | None,
        chunked: bool,
        content_encoding: str,
        auto_decompress: bool,
        chunk_size: int = 8192,
    ) -> None:
        self.status_code = status_code
        self.reason = reason
        self.http_version = http_version
        self.raw_headers: list[tuple[str, str]] = headers
        self._reader = reader
        self._writer = writer
        self._content_length = content_length
        self._chunked = chunked
        self._content_encoding = content_encoding
        self._auto_decompress = auto_decompress
        self._chunk_size = chunk_size
        self._closed = False

    @property
    def headers(self) -> dict[str, str]:
        out: dict[str, str] = {}
        for name, value in self.raw_headers:
            out[name.lower()] = value
        return out

    async def aiter_bytes(self, chunk_size: int | None = None) -> AsyncIterator[bytes]:
        """
        Async iterate over response body in chunks.
        
        Args:
            chunk_size: Size of chunks to yield (default: 8192)
            
        Yields:
            Raw bytes chunks from the response body
        """
        if self._closed:
            raise RuntimeError("Response has been closed")
        
        size = chunk_size or self._chunk_size
        
        if self._chunked:
            async for chunk in self._aiter_chunked(size):
                yield chunk
        elif self._content_length is not None:
            async for chunk in self._aiter_content_length(size):
                yield chunk
        else:
            async for chunk in self._aiter_until_close(size):
                yield chunk

    async def _aiter_chunked(self, chunk_size: int) -> AsyncIterator[bytes]:
        """Async iterate over chunked transfer encoding."""
        buffer = b""
        
        while True:
            line = await self._reader.readline()
            if not line:
                break
            try:
                size = int(line.strip(), 16)
            except ValueError:
                break
            
            if size == 0:
                await self._reader.readline()
                break
            
            remaining = size
            while remaining > 0:
                to_read = min(remaining, chunk_size)
                data = await self._reader.read(to_read)
                if not data:
                    break
                remaining -= len(data)
                
                if self._auto_decompress and self._content_encoding:
                    buffer += data
                else:
                    yield data
            
            # Consume CRLF after chunk
            await self._reader.readexactly(2)
        
        if self._auto_decompress and self._content_encoding and buffer:
            yield decode_body(buffer, self._content_encoding)

    async def _aiter_content_length(self, chunk_size: int) -> AsyncIterator[bytes]:
        """Async iterate with known content length."""
        assert self._content_length is not None
        remaining = self._content_length
        buffer = b""
        
        while remaining > 0:
            to_read = min(remaining, chunk_size)
            data = await self._reader.read(to_read)
            if not data:
                break
            remaining -= len(data)
            
            if self._auto_decompress and self._content_encoding:
                buffer += data
            else:
                yield data
        
        if self._auto_decompress and self._content_encoding and buffer:
            yield decode_body(buffer, self._content_encoding)

    async def _aiter_until_close(self, chunk_size: int) -> AsyncIterator[bytes]:
        """Async iterate until connection closes."""
        buffer = b""
        
        while True:
            data = await self._reader.read(chunk_size)
            if not data:
                break
            
            if self._auto_decompress and self._content_encoding:
                buffer += data
            else:
                yield data
        
        if self._auto_decompress and self._content_encoding and buffer:
            yield decode_body(buffer, self._content_encoding)

    async def aiter_lines(self, chunk_size: int | None = None, decode: str = "utf-8") -> AsyncIterator[str]:
        """
        Async iterate over response body line by line.
        
        Args:
            chunk_size: Size of chunks to read (default: 8192)
            decode: Character encoding for decoding bytes to str (default: utf-8)
            
        Yields:
            Lines from the response body (without line endings)
        """
        pending = b""
        async for chunk in self.aiter_bytes(chunk_size):
            pending += chunk
            while b"\n" in pending:
                line, pending = pending.split(b"\n", 1)
                yield line.rstrip(b"\r").decode(decode, errors="replace")
        
        if pending:
            yield pending.rstrip(b"\r").decode(decode, errors="replace")

    async def read(self) -> bytes:
        """Read entire response body into memory. Use with caution for large responses."""
        chunks = []
        async for chunk in self.aiter_bytes():
            chunks.append(chunk)
        return b"".join(chunks)

    async def close(self) -> None:
        """Close the response and release resources."""
        if not self._closed:
            self._closed = True
            try:
                self._writer.close()
                await self._writer.wait_closed()
            except Exception:
                pass

    async def __aenter__(self) -> AsyncStreamingResponse:
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.close()

    def __aiter__(self) -> AsyncIterator[bytes]:
        return self.aiter_bytes()

    def __repr__(self) -> str:
        return f"<AsyncStreamingResponse [{self.status_code}]>"
