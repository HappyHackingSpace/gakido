from __future__ import annotations

from collections.abc import Iterable


def _sanitize_header(name: str, value: str) -> tuple[str, str]:
    """
    Sanitize header name and value to prevent HTTP header injection (CRLF injection).
    Strips CR, LF, and null bytes from both name and value.
    """
    # Remove \r, \n, and \x00 from header name and value
    clean_name = name.replace("\r", "").replace("\n", "").replace("\x00", "")
    clean_value = value.replace("\r", "").replace("\n", "").replace("\x00", "")
    return clean_name, clean_value


def canonicalize_headers(
    default_headers: Iterable[tuple[str, str]],
    user_headers: dict[str, str] | None,
    order: Iterable[str],
) -> list[tuple[str, str]]:
    """
    Merge user headers with defaults while respecting a deterministic order.
    Later entries in the order list will override earlier ones when duplicates
    exist. Unspecified headers are appended in user-specified insertion order.
    """
    merged: dict[str, tuple[str, str]] = {}
    for name, value in default_headers:
        name, value = _sanitize_header(name, value)
        merged[name.lower()] = (name, value)
    if user_headers:
        for name, value in user_headers.items():
            name, value = _sanitize_header(name, value)
            merged[name.lower()] = (name, value)

    ordered: list[tuple[str, str]] = []
    for name in order:
        key = name.lower()
        if key in merged:
            ordered.append(merged.pop(key))
    # Append anything unspecified to preserve user intent.
    ordered.extend(merged.values())
    return ordered
