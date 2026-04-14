from __future__ import annotations

import json


class AnsiColors:
    RST = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    GRN = "\033[32m"
    YLW = "\033[33m"
    RED = "\033[31m"
    CYN = "\033[36m"


EVENT_PREFIX = "__STEAM_EVENT__"


def safe_symbol(unicode_symbol: str, fallback: str, *, stdout_encoding: str | None) -> str:
    encoding = stdout_encoding or "utf-8"
    try:
        unicode_symbol.encode(encoding)
        return unicode_symbol
    except Exception:
        return fallback


def ok_text(msg: str, *, green: str, reset: str, symbol: str) -> str:
    return f"{green}{symbol}{reset}  {msg}"


def warn_text(msg: str, *, yellow: str, reset: str, symbol: str) -> str:
    return f"{yellow}{symbol}{reset}  {msg}"


def err_text(msg: str, *, red: str, reset: str, symbol: str) -> str:
    return f"{red}{symbol}{reset}  {msg}"


def dim_text(msg: str, *, dim: str, reset: str) -> str:
    return f"{dim}{msg}{reset}"


def bold_text(msg: str, *, bold: str, reset: str) -> str:
    return f"{bold}{msg}{reset}"


def _emit(emit, text: str, **kwargs) -> None:
    try:
        emit(text, **kwargs)
    except TypeError:
        emit(text)


def emit_event(
    event_type: str,
    *,
    web_event_mode: bool,
    emit=print,
    event_prefix: str = EVENT_PREFIX,
    **payload,
) -> None:
    if not web_event_mode:
        return
    try:
        message = {"type": event_type, **payload}
        _emit(emit, f"{event_prefix}{json.dumps(message, ensure_ascii=False)}", flush=True)
    except Exception:
        return


def report_step(
    current: int,
    total: int,
    msg: str,
    *,
    emit=print,
    emit_event_fn=None,
    bold_fn=lambda text: text,
    color_cyan: str = "",
    color_reset: str = "",
) -> None:
    _emit(emit, f"\n{color_cyan}[{current}/{total}]{color_reset} {bold_fn(msg)}", flush=True)
    if emit_event_fn is not None:
        emit_event_fn("progress", current=current, total=total, label=msg)
