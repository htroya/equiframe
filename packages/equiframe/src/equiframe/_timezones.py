"""Private IANA loader: the locked tzdata package is authoritative on every host."""

import re
from functools import lru_cache
from importlib.resources import files
from zoneinfo import ZoneInfo


@lru_cache(maxsize=128)
def timezone(key: str) -> ZoneInfo:
    # Resolve only zone names, never arbitrary paths or other package resources.
    if re.fullmatch(r"[A-Za-z0-9_+-]+(?:/[A-Za-z0-9_+-]+)*", key) is None:
        raise ValueError("unknown IANA time zone: " + key)
    try:
        with files("tzdata.zoneinfo").joinpath(*key.split("/")).open("rb") as stream:
            return ZoneInfo.from_file(stream, key=key)
    except (OSError, ValueError) as exc:
        raise ValueError("unknown IANA time zone: " + key) from exc
