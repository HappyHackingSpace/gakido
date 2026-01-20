"""Tests for gakido.multipart module."""

import pytest
from gakido.multipart import build_multipart, _encode_field, _encode_file


class TestEncodeField:
    """Tests for _encode_field helper."""

    def test_encode_simple_field(self):
        """Test encoding a simple form field."""
        result = _encode_field("name", "John")
        assert b'Content-Disposition: form-data; name="name"' in result
        assert b"John" in result
        assert result.endswith(b"\r\n")

    def test_encode_field_with_special_chars(self):
        """Test encoding field with special characters in value."""
        result = _encode_field("message", "Hello & World!")
        assert b"Hello & World!" in result


class TestEncodeFile:
    """Tests for _encode_file helper."""

    def test_encode_file_basic(self):
        """Test encoding a file."""
        result = _encode_file("upload", "test.txt", b"content", "text/plain")
        assert b'Content-Disposition: form-data; name="upload"; filename="test.txt"' in result
        assert b"Content-Type: text/plain" in result
        assert b"content" in result

    def test_encode_file_default_content_type(self):
        """Test encoding file with no content type uses octet-stream."""
        result = _encode_file("file", "data.bin", b"\x00\x01", None)
        assert b"Content-Type: application/octet-stream" in result

    def test_encode_file_binary_content(self):
        """Test encoding file with binary content."""
        binary = bytes(range(256))
        result = _encode_file("binary", "data.bin", binary, None)
        assert binary in result


class TestBuildMultipart:
    """Tests for build_multipart function."""

    def test_build_with_only_files(self):
        """Test building multipart with only files."""
        files = {"doc": b"file content"}
        content_type, body = build_multipart(None, files)

        assert content_type.startswith("multipart/form-data; boundary=")
        assert b"file content" in body
        assert b'name="doc"' in body

    def test_build_with_data_and_files(self):
        """Test building multipart with both data and files."""
        data = {"field1": "value1", "field2": "value2"}
        files = {"upload": b"file content"}
        content_type, body = build_multipart(data, files)

        assert b"value1" in body
        assert b"value2" in body
        assert b"file content" in body
        assert content_type.startswith("multipart/form-data; boundary=")

    def test_build_with_file_tuple(self):
        """Test building multipart with file as (filename, content, type) tuple."""
        files = {"doc": ("report.pdf", b"PDF content", "application/pdf")}
        content_type, body = build_multipart(None, files)

        assert b'filename="report.pdf"' in body
        assert b"Content-Type: application/pdf" in body
        assert b"PDF content" in body

    def test_build_with_file_tuple_no_content_type(self):
        """Test file tuple with None content type."""
        files = {"doc": ("file.bin", b"binary", None)}
        content_type, body = build_multipart(None, files)

        assert b"Content-Type: application/octet-stream" in body

    def test_boundary_is_unique(self):
        """Test each call generates unique boundary."""
        files = {"f": b"content"}
        ct1, _ = build_multipart(None, files)
        ct2, _ = build_multipart(None, files)

        # Extract boundaries
        b1 = ct1.split("boundary=")[1]
        b2 = ct2.split("boundary=")[1]
        assert b1 != b2

    def test_body_ends_with_closing_boundary(self):
        """Test body ends with closing boundary."""
        files = {"f": b"content"}
        content_type, body = build_multipart(None, files)

        boundary = content_type.split("boundary=")[1]
        assert body.endswith(f"--{boundary}--\r\n".encode())

    def test_multiple_files(self):
        """Test building multipart with multiple files."""
        files = {
            "file1": b"content1",
            "file2": ("name2.txt", b"content2", "text/plain"),
            "file3": b"content3",
        }
        content_type, body = build_multipart(None, files)

        assert b"content1" in body
        assert b"content2" in body
        assert b"content3" in body
        assert b'name="file1"' in body
        assert b'name="file2"' in body
        assert b'name="file3"' in body

    def test_empty_files_dict(self):
        """Test building with empty files dict."""
        content_type, body = build_multipart(None, {})
        # Should still have closing boundary
        assert b"--" in body

    def test_data_only_no_files(self):
        """Test building with data only (files required but can be empty)."""
        data = {"key": "value"}
        content_type, body = build_multipart(data, {})

        # Data fields should be included
        assert b"value" in body

    def test_special_characters_in_filename(self):
        """Test filename with special characters."""
        files = {"f": ("file name.txt", b"content", "text/plain")}
        content_type, body = build_multipart(None, files)

        assert b'filename="file name.txt"' in body
