import uuid


def _encode_field(name: str, value: str) -> bytes:
    return (
        f'Content-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode()
    )


def _encode_file(name: str, filename: str, content: bytes, content_type: str | None) -> bytes:
    ct = content_type or "application/octet-stream"
    headers = (
        f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'
        f"Content-Type: {ct}\r\n\r\n"
    ).encode()
    return headers + content + b"\r\n"


def build_multipart(
    data: dict[str, str] | None,
    files: dict[str, bytes | tuple[str, bytes, str | None]],
) -> tuple[str, bytes]:
    """
    Build a multipart/form-data body.
    `files` values can be bytes or (filename, bytes, content_type|None).
    """
    boundary = uuid.uuid4().hex
    body_chunks: list[bytes] = []
    if data:
        for k, v in data.items():
            body_chunks.append(f"--{boundary}\r\n".encode("ascii"))
            body_chunks.append(_encode_field(k, v))
    for field, val in files.items():
        body_chunks.append(f"--{boundary}\r\n".encode("ascii"))
        if isinstance(val, bytes):
            body_chunks.append(_encode_file(field, field, val, None))
        else:
            filename, content, ctype = val
            body_chunks.append(_encode_file(field, filename, content, ctype))
    body_chunks.append(f"--{boundary}--\r\n".encode("ascii"))
    body = b"".join(body_chunks)
    content_type = f"multipart/form-data; boundary={boundary}"
    return content_type, body
