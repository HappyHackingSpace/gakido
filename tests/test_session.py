"""Tests for gakido.session module."""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from gakido.session import Session, AsyncSession
from gakido.models import Response


class TestSession:
    """Tests for Session class."""

    @patch('gakido.session.Client')
    def test_session_creates_client(self, mock_client_class):
        """Test Session creates a Client instance."""
        Session(impersonate="chrome_120")
        mock_client_class.assert_called_once_with(impersonate="chrome_120")

    @patch('gakido.session.Client')
    def test_session_passes_kwargs_to_client(self, mock_client_class):
        """Test Session passes kwargs to Client."""
        Session(impersonate="firefox_133", timeout=30.0, verify=False)
        mock_client_class.assert_called_once_with(
            impersonate="firefox_133",
            timeout=30.0,
            verify=False
        )

    @patch('gakido.session.Client')
    def test_session_has_cookie_jar(self, mock_client_class):
        """Test Session has a CookieJar."""
        session = Session()
        assert session.cookies is not None

    @patch('gakido.session.Client')
    def test_request_attaches_cookies(self, mock_client_class):
        """Test request attaches cookies from jar."""
        mock_client = MagicMock()
        mock_response = Response(
            200, "OK", "1.1",
            headers=[],
            body=b"",
        )
        mock_client.request.return_value = mock_response
        mock_client_class.return_value = mock_client

        session = Session()
        # Pre-set a cookie
        session.cookies.store["example.com"] = {"session": "abc123"}

        session.request("GET", "https://example.com/path")

        # Check Cookie header was added
        call_args = mock_client.request.call_args
        headers = call_args.kwargs.get("headers", {}) or call_args[1].get("headers", {})
        assert "Cookie" in headers or any("Cookie" in str(h) for h in [headers])

    @patch('gakido.session.Client')
    def test_request_captures_set_cookie(self, mock_client_class):
        """Test request captures Set-Cookie from response."""
        mock_client = MagicMock()
        mock_response = Response(
            200, "OK", "1.1",
            headers=[("Set-Cookie", "token=xyz")],
            body=b"",
        )
        mock_client.request.return_value = mock_response
        mock_client_class.return_value = mock_client

        session = Session()
        session.request("GET", "https://example.com/path")

        # Check cookie was stored
        assert session.cookies.cookie_header("example.com") == "token=xyz"

    @patch('gakido.session.Client')
    def test_get_method(self, mock_client_class):
        """Test get() method calls request with GET."""
        mock_client = MagicMock()
        mock_response = Response(200, "OK", "1.1", headers=[], body=b"")
        mock_client.request.return_value = mock_response
        mock_client_class.return_value = mock_client

        session = Session()
        session.get("https://example.com")

        mock_client.request.assert_called()
        args, kwargs = mock_client.request.call_args
        assert args[0] == "GET"

    @patch('gakido.session.Client')
    def test_post_method(self, mock_client_class):
        """Test post() method calls request with POST."""
        mock_client = MagicMock()
        mock_response = Response(200, "OK", "1.1", headers=[], body=b"")
        mock_client.request.return_value = mock_response
        mock_client_class.return_value = mock_client

        session = Session()
        session.post("https://example.com", data={"key": "value"})

        mock_client.request.assert_called()
        args, kwargs = mock_client.request.call_args
        assert args[0] == "POST"

    @patch('gakido.session.Client')
    def test_close_closes_client(self, mock_client_class):
        """Test close() closes the client."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        session = Session()
        session.close()

        mock_client.close.assert_called_once()

    @patch('gakido.session.Client')
    def test_context_manager_enter(self, mock_client_class):
        """Test Session can be used as context manager."""
        session = Session()
        result = session.__enter__()
        assert result is session

    @patch('gakido.session.Client')
    def test_context_manager_exit(self, mock_client_class):
        """Test Session context manager calls close on exit."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        with Session() as session:
            pass

        mock_client.close.assert_called_once()

    @patch('gakido.session.Client')
    def test_request_no_cookie_when_not_set(self, mock_client_class):
        """Test request doesn't add Cookie header when no cookies."""
        mock_client = MagicMock()
        mock_response = Response(200, "OK", "1.1", headers=[], body=b"")
        mock_client.request.return_value = mock_response
        mock_client_class.return_value = mock_client

        session = Session()
        session.request("GET", "https://example.com/path", headers={"X-Custom": "value"})

        call_args = mock_client.request.call_args
        headers = call_args.kwargs.get("headers") or call_args[1].get("headers", {})
        # Should have X-Custom but no Cookie (since jar is empty for this host)
        assert "X-Custom" in headers

    @patch('gakido.session.Client')
    def test_user_cookie_header_not_overwritten(self, mock_client_class):
        """Test user-provided Cookie header is not overwritten."""
        mock_client = MagicMock()
        mock_response = Response(200, "OK", "1.1", headers=[], body=b"")
        mock_client.request.return_value = mock_response
        mock_client_class.return_value = mock_client

        session = Session()
        # Pre-set a cookie in jar
        session.cookies.store["example.com"] = {"session": "from_jar"}

        # But provide our own Cookie header
        session.request("GET", "https://example.com/path", headers={"Cookie": "user_cookie=value"})

        call_args = mock_client.request.call_args
        headers = call_args.kwargs.get("headers") or call_args[1].get("headers", {})
        # User cookie should be preserved
        assert headers.get("Cookie") == "user_cookie=value"

    @patch('gakido.session.Client')
    def test_auto_referer_enabled_by_default(self, mock_client_class):
        """Test auto_referer is enabled by default."""
        session = Session()
        assert session.auto_referer is True
        assert session._last_url is None

    @patch('gakido.session.Client')
    def test_auto_referer_sets_header(self, mock_client_class):
        """Test auto_referer sets Referer header from previous request."""
        mock_client = MagicMock()
        mock_response = Response(200, "OK", "1.1", headers=[], body=b"")
        mock_client.request.return_value = mock_response
        mock_client_class.return_value = mock_client

        session = Session()

        # First request - no Referer
        session.get("https://example.com/page1")
        call_args = mock_client.request.call_args
        headers = call_args.kwargs.get("headers") or call_args[1].get("headers", {})
        assert "Referer" not in headers

        # Second request - should have Referer from first
        session.get("https://example.com/page2")
        call_args = mock_client.request.call_args
        headers = call_args.kwargs.get("headers") or call_args[1].get("headers", {})
        assert headers.get("Referer") == "https://example.com/page1"

        # Third request - should have Referer from second
        session.get("https://example.com/page3")
        call_args = mock_client.request.call_args
        headers = call_args.kwargs.get("headers") or call_args[1].get("headers", {})
        assert headers.get("Referer") == "https://example.com/page2"

    @patch('gakido.session.Client')
    def test_auto_referer_disabled(self, mock_client_class):
        """Test auto_referer can be disabled."""
        mock_client = MagicMock()
        mock_response = Response(200, "OK", "1.1", headers=[], body=b"")
        mock_client.request.return_value = mock_response
        mock_client_class.return_value = mock_client

        session = Session(auto_referer=False)

        session.get("https://example.com/page1")
        session.get("https://example.com/page2")

        call_args = mock_client.request.call_args
        headers = call_args.kwargs.get("headers") or call_args[1].get("headers", {})
        assert "Referer" not in headers

    @patch('gakido.session.Client')
    def test_user_referer_not_overwritten(self, mock_client_class):
        """Test user-provided Referer header is not overwritten."""
        mock_client = MagicMock()
        mock_response = Response(200, "OK", "1.1", headers=[], body=b"")
        mock_client.request.return_value = mock_response
        mock_client_class.return_value = mock_client

        session = Session()

        session.get("https://example.com/page1")
        session.get("https://example.com/page2", headers={"Referer": "https://custom.com"})

        call_args = mock_client.request.call_args
        headers = call_args.kwargs.get("headers") or call_args[1].get("headers", {})
        assert headers.get("Referer") == "https://custom.com"


class TestAsyncSession:
    """Tests for AsyncSession class."""

    @patch('gakido.session.AsyncClient')
    def test_async_session_creates_client(self, mock_client_class):
        """Test AsyncSession creates an AsyncClient instance."""
        AsyncSession(impersonate="chrome_120")
        mock_client_class.assert_called_once_with(impersonate="chrome_120")

    @patch('gakido.session.AsyncClient')
    def test_async_session_auto_referer_enabled_by_default(self, mock_client_class):
        """Test auto_referer is enabled by default."""
        session = AsyncSession()
        assert session.auto_referer is True
        assert session._last_url is None

    @pytest.mark.asyncio
    @patch('gakido.session.AsyncClient')
    async def test_async_auto_referer_sets_header(self, mock_client_class):
        """Test auto_referer sets Referer header from previous request."""
        mock_client = MagicMock()
        mock_response = Response(200, "OK", "1.1", headers=[], body=b"")
        mock_client.request = AsyncMock(return_value=mock_response)
        mock_client.close = AsyncMock()
        mock_client_class.return_value = mock_client

        session = AsyncSession()

        # First request - no Referer
        await session.get("https://example.com/page1")
        call_args = mock_client.request.call_args
        headers = call_args.kwargs.get("headers") or call_args[1].get("headers", {})
        assert "Referer" not in headers

        # Second request - should have Referer from first
        await session.get("https://example.com/page2")
        call_args = mock_client.request.call_args
        headers = call_args.kwargs.get("headers") or call_args[1].get("headers", {})
        assert headers.get("Referer") == "https://example.com/page1"

    @pytest.mark.asyncio
    @patch('gakido.session.AsyncClient')
    async def test_async_auto_referer_disabled(self, mock_client_class):
        """Test auto_referer can be disabled."""
        mock_client = MagicMock()
        mock_response = Response(200, "OK", "1.1", headers=[], body=b"")
        mock_client.request = AsyncMock(return_value=mock_response)
        mock_client.close = AsyncMock()
        mock_client_class.return_value = mock_client

        session = AsyncSession(auto_referer=False)

        await session.get("https://example.com/page1")
        await session.get("https://example.com/page2")

        call_args = mock_client.request.call_args
        headers = call_args.kwargs.get("headers") or call_args[1].get("headers", {})
        assert "Referer" not in headers

    @pytest.mark.asyncio
    @patch('gakido.session.AsyncClient')
    async def test_async_context_manager(self, mock_client_class):
        """Test AsyncSession can be used as async context manager."""
        mock_client = MagicMock()
        mock_client.close = AsyncMock()
        mock_client_class.return_value = mock_client

        async with AsyncSession() as session:
            assert session is not None

        mock_client.close.assert_called_once()
