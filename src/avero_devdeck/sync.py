"""Small, deterministic helpers for the interactive GitHub update workflow."""

from __future__ import annotations

import base64
import binascii
import re


def parse_selection(raw: str, count: int) -> list[int]:
    """Return zero-based selected indexes from ``a``, ``n`` or number ranges."""
    value = raw.strip().lower()
    if value == "a":
        return list(range(count))
    if value in ("", "n"):
        return []
    selected: set[int] = set()
    try:
        for part in value.split(","):
            part = part.strip()
            if "-" in part:
                if part.count("-") != 1:
                    raise ValueError
                first, last = (int(piece.strip()) for piece in part.split("-", 1))
                if first < 1 or last > count or first > last:
                    raise ValueError
                selected.update(range(first - 1, last))
            else:
                number = int(part)
                if number < 1 or number > count:
                    raise ValueError
                selected.add(number - 1)
    except ValueError as exc:
        raise ValueError(f"Invalid selection. Choose 1-{count}, ranges, 'a', or 'n'.") from exc
    return sorted(selected)


def decode_remote_content(data: dict) -> bytes:
    """Decode a GitHub Contents API response, failing closed if it is incomplete."""
    if data.get("encoding") != "base64" or not isinstance(data.get("content"), str):
        raise ValueError("GitHub did not return comparable base64 file contents.")
    try:
        content = re.sub(r"\s+", "", data["content"])
        return base64.b64decode(content, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("GitHub returned invalid base64 file contents.") from exc


def is_content_changed(local_bytes: bytes, remote_data: dict) -> bool:
    """Compare exact file bytes so identical local files are never uploaded."""
    return local_bytes != decode_remote_content(remote_data)
