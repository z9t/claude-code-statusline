# claude-code-statusline

A clean, single-file [Claude Code](https://claude.com/claude-code) statusline that shows what actually matters: model, context-window usage, and rate-limit windows — with true-color gradient bars.

Works in both the **terminal CLI** and the **VS Code extension** (they share the same config).

```
⚡ Sonnet-4.6 │ ctx 79.2K/204.8K [████░░░░░░] 38% │ 5h [████████░░] 78% 1h01m │ 7d [█░░░░░░░░░] 12% 4d00h
```

- **Model**  — short, readable name (e.g. `claude-sonnet-4-6` → `Sonnet-4.6`)
- **ctx**    — current/max tokens, % of context used
- **5h**     — Claude Code's rolling 5-hour usage window, % used + time until reset
- **7d**     — rolling 7-day usage window, % used + time until reset

Bars fade green → amber → red as usage climbs. Sections gracefully disappear when the harness doesn't supply that data (e.g. no rate limits → no `5h`/`7d` segments).

## Requirements

- Claude Code (terminal CLI **or** VS Code extension)
- Python 3.8+ available on `PATH`
- A terminal/editor that renders 24-bit ANSI color (every modern terminal and VS Code do)

No third-party Python packages — stdlib only.

## Install

### 1. Get the script

```sh
git clone https://github.com/<your-user>/claude-code-statusline.git ~/.claude/claude-code-statusline
chmod +x ~/.claude/claude-code-statusline/statusline.py
```

(Or copy `statusline.py` anywhere you like — just point `settings.json` at it.)

### 2. Wire it into Claude Code

Edit `~/.claude/settings.json` and add:

```json
{
  "statusLine": {
    "type": "command",
    "command": "python3 ~/.claude/claude-code-statusline/statusline.py",
    "refreshInterval": 15
  }
}
```

`refreshInterval` is in seconds. 15 keeps the rate-limit countdowns feeling live without being chatty.

### 3. Restart Claude Code

The statusline updates next time the harness re-renders.

## VS Code

The Claude Code VS Code extension reads the **same** `~/.claude/settings.json` as the CLI. Once you've added the `statusLine` block above, the bar renders inside the Claude panel — no extra setup. Both VS Code's integrated terminal and the extension's chat view support 24-bit ANSI color.

If your VS Code is on a machine where `python3` isn't on `PATH` (common on Windows), use `python` instead:

```json
{
  "statusLine": {
    "type": "command",
    "command": "python C:\\path\\to\\claude-code-statusline\\statusline.py",
    "refreshInterval": 15
  }
}
```

## How it works

Claude Code pipes a JSON object to the statusline command's stdin every `refreshInterval` seconds. The script reads it, builds a colorized string, and prints one line. That's the entire contract.

Fields the script reads (all optional — missing fields just hide their segment):

```
{
  "model":          { "id": "...", "display_name": "..." },
  "context_window": { "used_percentage": ..., "current_tokens": ..., "max_tokens": ... },
  "rate_limits":    {
    "five_hour":  { "used_percentage": ..., "resets_at": <unix-seconds> },
    "seven_day":  { "used_percentage": ..., "resets_at": <unix-seconds> }
  }
}
```

## Customizing

The script is one file with no dependencies — fork it and edit. The interesting knobs:

- **Palette** (`col_*` functions near the top) — RGB triples for each color role
- **Gradient breakpoints** (`_grad_color`) — where the bar transitions green→amber→red
- **Bar width** — the `width` arg to `bar(...)`, default 10 cells
- **Adding segments** — append to `parts` in `render(...)`. Each segment is just an ANSI-colored string; sections are joined by `SEP`.

## License

MIT — see `LICENSE`.
