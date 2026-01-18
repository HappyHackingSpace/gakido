from __future__ import annotations

from collections.abc import Iterable


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
        merged[name.lower()] = (name, value)
    if user_headers:
        for name, value in user_headers.items():
            merged[name.lower()] = (name, value)

    ordered: list[tuple[str, str]] = []
    for name in order:
        key = name.lower()
        if key in merged:
            ordered.append(merged.pop(key))
    # Append anything unspecified to preserve user intent.
    ordered.extend(merged.values())
    return ordered
