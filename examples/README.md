# Examples

Worked examples of extending the core statusline. None of these are required — the core `statusline.py` is the product. These show patterns for going further.

## `extended.py` — adding a second line

A two-line statusline. Line 1 is the unmodified core (model + ctx + 5h + 7d). Line 2 adds custom segments for background services on the local box:

```
⚡ Sonnet-4.6 │ ctx 79.2K/204.8K [████░░░░░░] 38% │ 5h [████████░░] 78% 1h01m │ 7d [█░░░░░░░░░] 12% 4d00h
◉ Gemma ▶ busy 12✓ up 1h │ ◎ Gemini 3✓ │ ☰ MiniMax-M2.7 [████░░░░░░] 38% │ ⚡ MQTT ●
```

Or, if a fleet-status JSON is present, Line 2 becomes per-machine SSH/A2A health:

```
hostname │ MACHINE-A SSH ● A2A ● │ MACHINE-B SSH ● A2A ●
```

### Segments shown

| Segment | What it reports | Source |
|---|---|---|
| `◉ Gemma` | local Gemma worker — status, queue depth, completed-today, uptime | `~/.config/z9t/gemma/status.json` |
| `◎ Gemini` | Gemini CLI — done/error counts | `~/.config/z9t/gemma/gemini_results.jsonl` |
| `☰ MiniMax-Mxx` | MiniMax CLI — default model + latest session ctx % | `~/.minimax/config.toml`, `~/.minimax/sessions/` |
| `⚡ MQTT` | local mosquitto — pings via `mosquitto_pub` (1s timeout) | runs `mosquitto_pub -h localhost ...` |
| `MACHINE SSH ● A2A ●` | per-machine fleet health | `~/.config/z9t/fleet-status.json` |

The exact services here are specific to the author's setup. **What's reusable is the pattern**: read a JSON file or check a binary, then render a colored segment with the shared primitives (`col_ok`, `col_warn`, `col_err`, `bar`, `pct_c`, `SEP`) imported from the core file.

### Wire it in

Point `~/.claude/settings.json` at `extended.py` instead of the core script:

```json
{
  "statusLine": {
    "type": "command",
    "command": "python3 ~/.claude/claude-code-statusline/examples/extended.py",
    "refreshInterval": 15
  }
}
```

`extended.py` imports from the sibling `statusline.py` via a `sys.path` insert, so keep them in their original repo layout (sibling directories).

### Configuration

All filesystem paths are overridable via env vars — set them in your shell profile or in the `command` string itself. Defaults match the author's machine; override them for yours.

| Env var | Default |
|---|---|
| `STATUSLINE_GEMMA_DIR` | `~/.config/z9t/gemma` |
| `STATUSLINE_MINIMAX_BIN` | `~/.cargo/bin/minimax` |
| `STATUSLINE_MINIMAX_CONFIG` | `~/.minimax/config.toml` |
| `STATUSLINE_MINIMAX_SESSIONS` | `~/.minimax/sessions` |
| `STATUSLINE_GEMINI_BIN` | `~/.nvm/versions/node/v22.22.2/bin/gemini` |
| `STATUSLINE_FLEET_STATUS_PATH` | `~/.config/z9t/fleet-status.json` |
| `STATUSLINE_MQTT_HOST` | `localhost` |

Missing files / missing binaries degrade to a dim "stopped" indicator — they don't crash the statusline. So you can run `extended.py` unmodified to see Line 2's structure, even if you don't have any of the underlying services installed.

### Adapting for your own services

Easiest path: open `extended.py`, delete the segments you don't want, and copy one of the existing ones as a template for the segment you do want. Each segment is a function that returns a single ANSI-colored string; `main()` just joins them with `SEP`.

The pattern in each segment:
1. Build a dim label (`col_label("◉ MyService")`).
2. Try to read state (file, subprocess, network probe).
3. On success, append a status dot (`col_ok("●")` / `col_warn("●")` / `col_err("●")`) and any counters.
4. On any exception, fall through to a single error glyph — never crash the statusline.
