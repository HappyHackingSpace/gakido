"""Tests for streaming response functionality."""
from __future__ import annotations

import asyncio
import socket
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from gakido import Client, AsyncClient, StreamingResponse, AsyncStreamingResponse


class ChunkedHandler(BaseHTTPRequestHandler):
    """HTTP handler that returns chunked responses."""

    def log_message(self, format, *args):
        pass  # Suppress logging

    def do_GET(self):
        if self.path == "/chunked":
            self.send_response(200)
            self.send_header("Transfer-Encoding", "chunked")
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            # Send chunked data
            for i in range(5):
                chunk = f"chunk{i}\n".encode()
                self.wfile.write(f"{len(chunk):x}\r\n".encode())
                self.wfile.write(chunk)
                self.wfile.write(b"\r\n")
            # Final chunk
            self.wfile.write(b"0\r\n\r\n")
        elif self.path == "/large":
            # Large response with known content-length
            data = b"x" * 100000  # 100KB
            self.send_response(200)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Content-Type", "application/octet-stream")
            self.end_headers()
            self.wfile.write(data)
        elif self.path == "/lines":
            # Multi-line response
            lines = "\n".join([f"line {i}" for i in range(10)])
            data = lines.encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(data)
        else:
            self.send_response(404)
            self.end_headers()


@pytest.fixture(scope="module")
def http_server():
    """Start a local HTTP server for testing."""
    server = HTTPServer(("127.0.0.1", 0), ChunkedHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever)
    thread.daemon = True
    thread.start()
    yield f"http://127.0.0.1:{port}"
    server.shutdown()


class TestSyncStreaming:
    """Tests for synchronous streaming responses."""

    def test_stream_returns_streaming_response(self, http_server):
        """stream() should return a StreamingResponse object."""
        client = Client()
        with client.stream("GET", f"{http_server}/lines") as response:
            assert isinstance(response, StreamingResponse)
            assert response.status_code == 200

    def test_iter_bytes_chunked(self, http_server):
        """iter_bytes() should yield chunks from chunked response."""
        client = Client()
        with client.stream("GET", f"{http_server}/chunked") as response:
            chunks = list(response.iter_bytes())
            # Should have received all chunks
            full_body = b"".join(chunks)
            assert b"chunk0" in full_body
            assert b"chunk4" in full_body

    def test_iter_bytes_content_length(self, http_server):
        """iter_bytes() should yield chunks from content-length response."""
        client = Client()
        with client.stream("GET", f"{http_server}/large") as response:
            total_size = 0
            chunk_count = 0
            for chunk in response.iter_bytes(chunk_size=8192):
                total_size += len(chunk)
                chunk_count += 1
            assert total_size == 100000
            assert chunk_count > 1  # Should be multiple chunks

    def test_iter_lines(self, http_server):
        """iter_lines() should yield lines from response."""
        client = Client()
        with client.stream("GET", f"{http_server}/lines") as response:
            lines = list(response.iter_lines())
            assert len(lines) == 10
            assert lines[0] == "line 0"
            assert lines[9] == "line 9"

    def test_read_full_body(self, http_server):
        """read() should return entire body."""
        client = Client()
        with client.stream("GET", f"{http_server}/large") as response:
            body = response.read()
            assert len(body) == 100000

    def test_context_manager_closes(self, http_server):
        """Context manager should close response."""
        client = Client()
        with client.stream("GET", f"{http_server}/lines") as response:
            pass
        assert response._closed

    def test_headers_accessible(self, http_server):
        """Response headers should be accessible before reading body."""
        client = Client()
        with client.stream("GET", f"{http_server}/lines") as response:
            assert "content-type" in response.headers
            assert response.headers["content-type"] == "text/plain"


class TestAsyncStreaming:
    """Tests for asynchronous streaming responses."""

    @pytest.mark.asyncio
    async def test_stream_returns_async_streaming_response(self, http_server):
        """stream() should return an AsyncStreamingResponse object."""
        client = AsyncClient()
        async with await client.stream("GET", f"{http_server}/lines") as response:
            assert isinstance(response, AsyncStreamingResponse)
            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_aiter_bytes_chunked(self, http_server):
        """aiter_bytes() should yield chunks from chunked response."""
        client = AsyncClient()
        async with await client.stream("GET", f"{http_server}/chunked") as response:
            chunks = []
            async for chunk in response.aiter_bytes():
                chunks.append(chunk)
            full_body = b"".join(chunks)
            assert b"chunk0" in full_body
            assert b"chunk4" in full_body

    @pytest.mark.asyncio
    async def test_aiter_bytes_content_length(self, http_server):
        """aiter_bytes() should yield chunks from content-length response."""
        client = AsyncClient()
        async with await client.stream("GET", f"{http_server}/large") as response:
            total_size = 0
            chunk_count = 0
            async for chunk in response.aiter_bytes(chunk_size=8192):
                total_size += len(chunk)
                chunk_count += 1
            assert total_size == 100000
            assert chunk_count > 1

    @pytest.mark.asyncio
    async def test_aiter_lines(self, http_server):
        """aiter_lines() should yield lines from response."""
        client = AsyncClient()
        async with await client.stream("GET", f"{http_server}/lines") as response:
            lines = []
            async for line in response.aiter_lines():
                lines.append(line)
            assert len(lines) == 10
            assert lines[0] == "line 0"
            assert lines[9] == "line 9"

    @pytest.mark.asyncio
    async def test_read_full_body(self, http_server):
        """read() should return entire body."""
        client = AsyncClient()
        async with await client.stream("GET", f"{http_server}/large") as response:
            body = await response.read()
            assert len(body) == 100000

    @pytest.mark.asyncio
    async def test_context_manager_closes(self, http_server):
        """Context manager should close response."""
        client = AsyncClient()
        async with await client.stream("GET", f"{http_server}/lines") as response:
            pass
        assert response._closed

    @pytest.mark.asyncio
    async def test_headers_accessible(self, http_server):
        """Response headers should be accessible before reading body."""
        client = AsyncClient()
        async with await client.stream("GET", f"{http_server}/lines") as response:
            assert "content-type" in response.headers
            assert response.headers["content-type"] == "text/plain"

    @pytest.mark.asyncio
    async def test_async_iteration_protocol(self, http_server):
        """AsyncStreamingResponse should support async iteration protocol."""
        client = AsyncClient()
        async with await client.stream("GET", f"{http_server}/lines") as response:
            chunks = []
            async for chunk in response:  # Uses __aiter__
                chunks.append(chunk)
            assert len(b"".join(chunks)) > 0


class TestStreamingResponseRepr:
    """Tests for StreamingResponse repr."""

    def test_sync_repr(self, http_server):
        """StreamingResponse should have useful repr."""
        client = Client()
        with client.stream("GET", f"{http_server}/lines") as response:
            assert "StreamingResponse" in repr(response)
            assert "200" in repr(response)

    @pytest.mark.asyncio
    async def test_async_repr(self, http_server):
        """AsyncStreamingResponse should have useful repr."""
        client = AsyncClient()
        async with await client.stream("GET", f"{http_server}/lines") as response:
            assert "AsyncStreamingResponse" in repr(response)
            assert "200" in repr(response)
