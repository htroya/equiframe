"""Safe runtime failure summaries and bounded, value-free debug frames."""

from __future__ import annotations

import json
import logging
import re

_LOG = logging.getLogger("equiframe.diagnostics")
_LOG.addHandler(logging.NullHandler())
_NAME = re.compile(r"[A-Za-z_][A-Za-z_0-9.]{0,127}\Z")


def report_failure(error: BaseException, message: str) -> str:
    """Return an authored public message; never stringify the caught exception.

    Debug output contains owned module/function/line metadata only. Exception
    values, source lines, filenames, locals and external callback names are
    excluded, including when an exception's __str__ itself is unsafe.
    """
    try:
        enabled = _LOG.isEnabledFor(logging.DEBUG)
    except Exception:
        return message
    if enabled:
        try:
            _debug_frames(error)
        except Exception:
            # Logging is best effort; a caller's failing handler must not
            # expose values or replace the original operational outcome.
            return message
    return message


def _debug_frames(error: BaseException) -> None:
    frames: list[tuple[str, str, int]] = []
    cursor = error.__traceback__
    while cursor is not None and len(frames) < 32:
        frame = cursor.tb_frame
        module = frame.f_globals.get("__name__")
        function = frame.f_code.co_name
        if (
            type(module) is str
            and module.startswith("equiframe.")
            and _NAME.fullmatch(module)
            and _NAME.fullmatch(function)
        ):
            frames.append((module, function, cursor.tb_lineno))
        else:
            frames.append(("external", "callback", 0))
        cursor = cursor.tb_next
    _LOG.debug("Operation failed; safe frames=%s", json.dumps(frames, ensure_ascii=True))
