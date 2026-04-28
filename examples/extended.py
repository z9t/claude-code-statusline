#!/usr/bin/env python3
"""
Extended statusline — Line 1 (Claude) + Line 2 (custom fleet/agent segments).

This is the author's personal extension of the core statusline. It's checked
in as a worked example of how to add your own segments while reusing the core
file's color primitives, gradient bars, and rendering helpers.

Line 1: identical to the core statusline (model + ctx + 5h + 7d).
Line 2: status of background agents/services on the local box —
    ◉ Gemma ▶ busy 12✓ up 1h │ ◎ Gemini 3✓ │ ☰ MiniMax-M2.7 [████░░░░░░] 38% │ ⚡ MQTT ● │ HOST │ MACHINE SSH ● A2A ●

The exact services here (Gemma worker, Gemini CLI cache, MiniMax sessions,
mosquitto, an SSH/A2A fleet snapshot) are specific to the author's setup.
What's reusable is the pattern: read state from a JSON file or check a
binary, then render a colored segment with the shared primitives.

Wire this into Claude Code by pointing settings.json at it instead of the
core script:

    "command": "python3 ~/.claude/claude-code-statusline/examples/extended.py"

All filesystem paths can be overridden via env vars (see the CONFIG block).
Missing files / missing binaries degrade to a dim "stopped" indicator
instead of crashing.
"""

import json
import os
import re
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Import the core statusline as a sibling module.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from statusline import (  # noqa: E402
    SEP,
    bar,
    col_dim,
    col_err,
    col_label,
    col_ok,
    col_tokens,
    col_warn,
    pct_c,
    render as render_claude_line,
)

# ── CONFIG (override via env vars) ────────────────────────────────────────────

GEMMA_DIR         = Path(os.environ.get("STATUSLINE_GEMMA_DIR",         str(Path.home() / ".config/z9t/gemma")))
MINIMAX_BIN       = Path(os.environ.get("STATUSLINE_MINIMAX_BIN",       str(Path.home() / ".cargo/bin/minimax")))
MINIMAX_CONFIG    = Path(os.environ.get("STATUSLINE_MINIMAX_CONFIG",    str(Path.home() / ".minimax/config.toml")))
MINIMAX_SESSIONS  = Path(os.environ.get("STATUSLINE_MINIMAX_SESSIONS",  str(Path.home() / ".minimax/sessions")))
GEMINI_BIN        = Path(os.environ.get("STATUSLINE_GEMINI_BIN",        str(Path.home() / ".nvm/versions/node/v22.22.2/bin/gemini")))
FLEET_STATUS_PATH = Path(os.environ.get("STATUSLINE_FLEET_STATUS_PATH", str(Path.home() / ".config/z9t/fleet-status.json")))
MQTT_HOST         = os.environ.get("STATUSLINE_MQTT_HOST", "localhost")

# ── Helpers ───────────────────────────────────────────────────────────────────

def _k(n: int) -> str:
    return f"{n / 1000:.1f}K" if n >= 1000 else str(n)

def _fmt_uptime(uptime_s: int) -> str:
    if uptime_s >= 3600:
        return f"{uptime_s // 3600}h"
    if uptime_s >= 60:
        return f"{uptime_s // 60}m"
    return f"{uptime_s}s"

# ── Segments ──────────────────────────────────────────────────────────────────

def gemma_segment() -> str:
    """Local Gemma worker — reads its status.json (queue depth, completed, uptime)."""
    status_path = GEMMA_DIR / "status.json"
    label = col_label("◉ Gemma")
    if not status_path.exists():
        return label + " " + col_dim("○ stopped")
    try:
        d = json.loads(status_path.read_text())
        status = d.get("status", "stopped")
        queue = d.get("queue_depth", 0)
        done = d.get("completed_today", 0)
        esc = d.get("escalations_pending", 0)
        up = _fmt_uptime(d.get("uptime_seconds", 0))

        dot = {"idle": col_ok("●"), "busy": col_warn("▶")}.get(status, col_err("○"))
        stat_str = (
            col_ok(status) if status == "idle"
            else col_warn(status) if status == "busy"
            else col_err(status)
        )
        seg = f"{label} {dot} {stat_str} {col_ok(str(done) + '✓')} {col_dim('up ' + up)}"
        if queue:
            seg += " " + col_warn(f"{queue}q")
        if esc:
            seg += " " + col_err(f"⚠{esc}")
        return seg
    except Exception:
        return label + " " + col_err("?")


def gemini_segment() -> str:
    """Gemini CLI — counts done/error records in a results jsonl."""
    label = col_label("◎ Gemini")
    results = GEMMA_DIR / "gemini_results.jsonl"
    if not GEMINI_BIN.exists():
        return label + " " + col_err("✗")
    if not results.exists():
        return label + " " + col_dim("●")
    try:
        records = [json.loads(l) for l in results.read_text().strip().splitlines() if l.strip()]
        done = sum(1 for r in records if r.get("status") == "done")
        err = sum(1 for r in records if r.get("status") in ("error", "timeout"))
        seg = label + " " + col_ok(f"{done}✓")
        if err:
            seg += " " + col_err(f"{err}✗")
        return seg
    except Exception:
        return label + " " + col_err("?")


def minimax_segment() -> str:
    """MiniMax CLI — reads default model from config and shows latest session ctx %."""
    label = col_label("☰ MiniMax")
    if not MINIMAX_BIN.exists():
        return label + " " + col_err("✗")
    try:
        if not MINIMAX_CONFIG.exists():
            return label + " " + col_dim("●")
        text = MINIMAX_CONFIG.read_text()
        match = re.search(r'default_text_model\s*=\s*"([^"]+)"', text)
        model = match.group(1) if match else "?"
        label = col_label(f"☰ {model}")

        if MINIMAX_SESSIONS.exists():
            sessions = sorted(MINIMAX_SESSIONS.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
            if sessions:
                sess = json.loads(sessions[0].read_text())
                used = sess.get("tokens_used") or sess.get("input_tokens", 0)
                cap = sess.get("context_size") or sess.get("max_tokens", 200_000)
                if used and cap:
                    pct = used / cap * 100
                    return (
                        label + " "
                        + col_tokens(f"{_k(used)}/{_k(cap)}") + " "
                        + bar(pct, width=8) + " "
                        + pct_c(pct, f"{pct:.0f}%")
                    )
        return label + " " + col_dim("●")
    except Exception:
        return label + " " + col_err("?")


def mqtt_segment() -> str:
    """Local mosquitto — pings via mosquitto_pub with 1s timeout."""
    label = col_label("⚡ MQTT")
    try:
        r = subprocess.run(
            ["mosquitto_pub", "-h", MQTT_HOST, "-t", "z9t/_ping", "-m", "1", "-q", "0"],
            capture_output=True, timeout=1,
        )
        return label + " " + (col_ok("●") if r.returncode == 0 else col_err("✗"))
    except Exception:
        return label + " " + col_err("✗")

# ── Fleet snapshot ────────────────────────────────────────────────────────────

def _load_fleet_status() -> tuple[dict, float | None]:
    if not FLEET_STATUS_PATH.exists():
        return {}, None
    try:
        payload = json.loads(FLEET_STATUS_PATH.read_text())
    except Exception:
        return {}, None
    generated_at = payload.get("generated_at")
    if not generated_at:
        return payload, None
    try:
        ts = datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
        age_sec = (datetime.now(timezone.utc) - ts).total_seconds()
        return payload, max(0.0, age_sec)
    except Exception:
        return payload, None


def _status_dot(ok, *, warn=False, stale=False) -> str:
    if stale or warn:
        return col_warn("●")
    if ok:
        return col_ok("●")
    return col_err("●")


def _ssh_status_dot(row: dict, stale: bool) -> str:
    ssh_windows = row.get("ssh_windows")
    ssh_wsl = row.get("ssh_wsl")
    if ssh_windows is not None or ssh_wsl is not None:
        if (ssh_windows or {}).get("ok"):
            return _status_dot(True, stale=stale)
        if (ssh_wsl or {}).get("ok"):
            return _status_dot(True, warn=True, stale=stale)
        return _status_dot(False, stale=stale)
    ssh = row.get("ssh") or {}
    return _status_dot(ssh.get("ok"), stale=stale, warn="no ssh" in ssh.get("detail", "").lower())


def _fleet_machine_segment(row: dict, stale: bool) -> str:
    name = col_label(row.get("name", "?").upper())
    ssh_dot = _ssh_status_dot(row, stale)
    a2a = row.get("a2a") or {}
    a2a_warn = bool(a2a.get("ok")) and row.get("a2a_capability", "none") != "full-agent"
    a2a_dot = _status_dot(a2a.get("ok"), warn=a2a_warn or stale)
    return f"{name} {col_label('SSH')} {ssh_dot} {col_label('A2A')} {a2a_dot}"


def fleet_line() -> str:
    payload, age_sec = _load_fleet_status()
    host = col_label(socket.gethostname())
    if not payload:
        # No fleet snapshot — fall back to the agent segments.
        return SEP.join([gemma_segment(), gemini_segment(), minimax_segment(), mqtt_segment()])
    stale = age_sec is None or age_sec > 150
    age_label = col_warn(f"{int(age_sec // 60)}m stale") if stale and age_sec is not None else None
    rows = [r for r in payload.get("results") or [] if r.get("allowed", False)]
    parts = [host] + [_fleet_machine_segment(r, stale) for r in rows]
    if age_label:
        parts.append(age_label)
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
    print(render_claude_line(data))
    print(fleet_line())


if __name__ == "__main__":
    main()
