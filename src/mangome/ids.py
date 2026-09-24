from __future__ import annotations

import secrets
import time

# Crockford Base32. ULID-compatible text layout without an external dependency.
_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def _encode(value: int, length: int) -> str:
    chars = ["0"] * length
    for i in range(length - 1, -1, -1):
        chars[i] = _ALPHABET[value & 31]
        value >>= 5
    return "".join(chars)


def new_id() -> str:
    """Return a monotonic-sortable ULID-shaped identifier.

    This is sufficient for MangoMe entity identity: 48-bit millisecond time +
    80 bits of cryptographic randomness, encoded as 26 Crockford-base32 chars.
    """
    timestamp_ms = int(time.time() * 1000) & ((1 << 48) - 1)
    randomness = secrets.randbits(80)
    return _encode(timestamp_ms, 10) + _encode(randomness, 16)
