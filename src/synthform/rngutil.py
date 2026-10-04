"""Process-stable seeds.

random.Random hashes str parts with PYTHONHASHSEED, which changes between
processes. Hash the text ourselves and seed with an int.
"""

from __future__ import annotations

import hashlib


def stable_seed(*parts: object) -> int:
    text = "\0".join(str(part) for part in parts)
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big")
