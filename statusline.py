#!/usr/bin/env python3
"""
Claude Code statusline — true-color ANSI status bar.

Renders a single line with:
    ⚡ Sonnet-4.6 │ ctx 79.2K/204.8K [████░░░░░░] 38% │ 5h [████░░░░░░] 78% 1h01m │ 7d [█░░░░░░░░░] 12% 4d00h

Reads JSON state from stdin (Claude Code's statusline contract). Works in both
the Claude Code terminal CLI and the VS Code extension — both render true-color
ANSI escapes and use the same ~/.claude/settings.json.

No third-party dependencies. Python 3.8+.

License: MIT
"""

import json
import re
import sys
import time

# ── ANSI primitives ───────────────────────────────────────────────────────────

RESET = "\x1b[0m"

def _c(r, g, b, text):       return f"\x1b[38;2;{r};{g};{b}m{text}{RESET}"
def _bold(text):              return f"\x1b[1m{text}{RESET}"
def _dim(text):               return f"\x1b[2m{text}{RESET}"
def _dim_c(r, g, b, text):    return f"\x1b[2m\x1b[38;2;{r};{g};{b}m{text}{RESET}"

# Palette
def col_sep(t):    return _dim_c(100, 100, 120, t)    # dim violet-gray separators
def col_label(t):  return _dim_c(120, 140, 180, t)    # dim blue-gray labels
def col_model(t):  return _bold(_c(167, 139, 250, t)) # bright violet for model
def col_tokens(t): return _c(180, 185, 210, t)        # muted lavender for token counts
def col_time(t):   return _dim_c(140, 155, 175, t)    # dim for reset countdowns
def col_ok(t):     return _c(74, 222, 128, t)         # green
def col_warn(t):   return _c(251, 191, 36, t)         # amber
def col_err(t):    return _c(248, 113, 113, t)        # red

SEP = col_sep(" │ ")

# ── Gradient bar ──────────────────────────────────────────────────────────────

def _grad_color(pct: float):
    """Green → amber → red gradient based on percentage."""
    if pct <= 50:
        t = pct / 50
        return (int(34 + t * (251 - 34)), int(197 + t * (191 - 197)), int(94 + t * (36 - 94)))
    elif pct <= 80:
        t = (pct - 50) / 30
        return (int(251 + t * (249 - 251)), int(191 + t * (115 - 191)), int(36 + t * (22 - 36)))
    else:
        t = min(1.0, (pct - 80) / 20)
        return (int(249 + t * (239 - 249)), int(115 + t * (68 - 115)), int(22 + t * (68 - 22)))

def pct_c(pct: float, text: str) -> str:
    r, g, b = _grad_color(pct)
    return _c(r, g, b, text)

def bar(pct: float, width: int = 10) -> str:
    filled = max(0, min(width, round(pct / 100 * width)))
    inner = "█" * filled + "░" * (width - filled)
    r, g, b = _grad_color(pct)
    return col_sep("[") + _c(r, g, b, inner) + col_sep("]")

# ── Helpers ───────────────────────────────────────────────────────────────────

def _k(n: int) -> str:
    return f"{n / 1000:.1f}K" if n >= 1000 else str(n)

def _fmt_reset(resets_at: float) -> str:
    remaining = resets_at - time.time()
    if remaining <= 0:
        return col_ok("now")
    d = int(remaining // 86400)
    h = int((remaining % 86400) // 3600)
    m = int((remaining % 3600) // 60)
    if d > 0:
        return col_time(f"{d}d{h:02d}h")
    if h > 0:
        return col_time(f"{h}h{m:02d}m")
    return col_time(f"{m}m")

def _model_display(model_id: str, fallback: str) -> str:
    """claude-sonnet-4-6 → Sonnet-4.6, claude-opus-4-7 → Opus-4.7."""
    short = re.sub(r"-\d{8}$", "", model_id) if model_id else (fallback or "claude")
    m = re.match(r"claude-(opus|sonnet|haiku)-(\d+)(?:-(\d+))?", short, re.I)
    if m:
        name, maj, minor = m.group(1).capitalize(), m.group(2), m.group(3)
        return f"{name}-{maj}.{minor}" if minor else f"{name}-{maj}"
    return short

# ── Render ────────────────────────────────────────────────────────────────────

def render(data: dict) -> str:
    parts = []

    # Model
    model = data.get("model", {}) or {}
    display = _model_display(model.get("id", ""), model.get("display_name", ""))
    parts.append(col_label("⚡ ") + col_model(display))

    # Context window
    ctx = data.get("context_window", {}) or {}
    used_pct = ctx.get("used_percentage")
    used = ctx.get("current_tokens") or ctx.get("used")
    cap = ctx.get("max_tokens") or ctx.get("limit")
    if used_pct is not None:
        token_str = (col_tokens(f"{_k(used)}/{_k(cap)}") + " ") if used and cap else ""
        parts.append(
            col_label("ctx ")
            + token_str
            + bar(used_pct)
            + " "
            + pct_c(used_pct, f"{used_pct:.0f}%")
        )

    # Rate limits
    rl = data.get("rate_limits", {}) or {}
    for key, label in (("five_hour", "5h "), ("seven_day", "7d ")):
        window = rl.get(key)
        if not window:
            continue
        pct = window.get("used_percentage")
        resets_at = window.get("resets_at")
        if pct is None or resets_at is None:
            continue
        parts.append(
            col_label(label)
            + bar(pct)
            + " "
            + pct_c(pct, f"{pct:.0f}%")
            + " "
            + _fmt_reset(resets_at)
        )

    return SEP.join(parts)

# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    data = {}
    try:
        if not sys.stdin.isatty():
            raw = sys.stdin.read()
            if raw.strip():
                data = json.loads(raw)
    except Exception:
        pass
    print(render(data))


if __name__ == "__main__":
    main()
