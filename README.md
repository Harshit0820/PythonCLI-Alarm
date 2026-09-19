# Pocket Alarm

Terminal alarm clock for macOS and Linux: a Python CLI with JSON file storage (stdlib only, no database, no web UI).

> **Important: `add` does not ring by itself**
>
> | Step | What it does |
> |------|----------------|
> | `add`, `list`, `enable`, … | **Save** alarm definitions to a JSON file on disk. |
> | `run` (or `start`) | **Scheduler** — must stay running in a terminal. This process waits until the next alarm time, then rings. |
>
> If you only run `add` and close the terminal, nothing will ever ring. Open a terminal, run `python3 -m pocket_alarm run`, and leave it open while you want alarms to be active.

## Features

- Add alarms in 24-hour or 12-hour time, optional labels, repeat schedules
- List, enable, disable, and remove alarms by id
- Foreground scheduler (`run`) with snooze and dismiss
- Countdown `timer` (does not use the JSON alarm list)
- macOS audio via `afplay` / `say`, with terminal bell fallback
- `test-sound` to verify audio without waiting for an alarm
- Configurable data file path (env var or flag)

## Requirements

- **Python 3.10+** (see `requires-python` in `pyproject.toml`)
- **macOS or Linux** with a terminal
- **Audio (macOS):** `afplay` and `say` are used when available; if they fail or are missing, the app falls back to the terminal bell (often silent unless enabled in Terminal settings)

## Install

### Option A — run from the repo (no install)

```bash
cd "/path/to/alarm-clock"
python3 -m pocket_alarm --help
```

### Option B — editable install with console script

Modern macOS Python is [PEP 668](https://peps.python.org/pep-0668/) “externally managed,” so a bare `pip install -e .` on the system interpreter usually fails. Use a virtual environment:

```bash
cd "/path/to/alarm-clock"
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .
pocket-alarm --help
```

After install, use either `pocket-alarm …` or `python3 -m pocket_alarm …`.

## Quickstart

Two parts: **(1)** define alarms, **(2)** keep the scheduler running.

```bash
cd "/path/to/alarm-clock"

# Optional: confirm your Mac can play the alarm sound
python3 -m pocket_alarm test-sound

# 1) Schedule an alarm (pick a time 1–2 minutes ahead of now, minute precision)
python3 -m pocket_alarm add 7:30am --label "Get up" --repeat once

# 2) Start the scheduler — leave this terminal open until it rings
python3 -m pocket_alarm run
```

When the clock reaches the alarm minute, the terminal shows a ringing banner and plays sound. Press **Enter** to snooze or **`d` then Enter** to dismiss.

To try an immediate ring without the JSON alarm list, use the countdown timer (still no `run` required):

```bash
python3 -m pocket_alarm timer 10s --label "Test"
```

## Command reference

Global flags (before the subcommand):

| Flag | Description |
|------|-------------|
| `--data-file PATH` | Alarms JSON file (overrides env; default `~/.config/pocket-alarm/alarms.json`) |
| `--sound PATH` | Audio file for `afplay` when ringing or running `test-sound` |
| `--volume FLOAT` | `afplay` volume `0.0`–`1.0` (default `1.0`) |

| Command | Purpose | Flags / arguments | Example |
|---------|---------|-------------------|---------|
| `add` | Create an alarm | `TIME`; `--label`, `-l`; `--repeat`, `-r` (default `once`); `--disabled` | `python3 -m pocket_alarm add 07:30 -l Work --repeat weekdays` |
| `list` | Show all alarms | — | `python3 -m pocket_alarm list` |
| `remove` | Delete an alarm | `ID` (exact id or unique prefix, min 3 characters) | `python3 -m pocket_alarm remove abc12345` |
| `enable` | Turn an alarm on | `ID` (exact or unique prefix, min 3 characters) | `python3 -m pocket_alarm enable abc12345` |
| `disable` | Turn an alarm off | `ID` (exact or unique prefix, min 3 characters) | `python3 -m pocket_alarm disable abc12345` |
| `run` | **Run the scheduler** (blocks until Ctrl+C) | `--snooze MIN` (default `5`); `--quiet` | `python3 -m pocket_alarm run --snooze 10` |
| `start` | Same as `run` | Same as `run` | `python3 -m pocket_alarm start` |
| `timer` | Countdown, then ring (not stored in JSON) | `DURATION`; `--label`, `-l` (default `Timer`); `--snooze MIN` (default `5`) | `python3 -m pocket_alarm timer 5m -l Tea` |
| `test-sound` | Play alarm audio once or more | `--loops N` (default `1`) | `python3 -m pocket_alarm test-sound --loops 2` |

Examples with global flags:

```bash
python3 -m pocket_alarm --data-file ~/my-alarms.json list
python3 -m pocket_alarm --sound /System/Library/Sounds/Hero.aiff test-sound
python3 -m pocket_alarm --volume 0.8 run
```

## Time and repeat formats

### Time (`add`)

| Form | Examples |
|------|----------|
| 24-hour | `07:30`, `7:30`, `23:59`, `0:00` |
| 12-hour | `7:30am`, `7:30 am`, `7:30PM`, `12:00pm` |

Times are **minute precision** only (no seconds on `add`).

### Repeat (`add --repeat`)

| Value | Meaning |
|-------|---------|
| `once` | Default; next occurrence at that clock time, then disabled after dismiss |
| `daily` | Every day |
| `weekdays` | Monday–Friday (also accepts `weekday`, `mon-fri`, `monfri`) |
| `mon,wed,fri` | Specific days (comma or `/` separated; names `mon` … `sun`) |

Aliases for once: `one-shot`, `onetime`. For daily: `everyday`.

### Duration (`timer`)

Examples: `30s`, `5m`, `1h`, `1h30m` (combined units in one string).

## While an alarm is ringing

The scheduler prints a banner and loops sound until you respond:

| Input | Action |
|-------|--------|
| **Enter** | Snooze for the default minutes (`--snooze` on `run`, default 5) |
| **`d` + Enter** | Dismiss (also `dismiss`, `q`, `quit`) |
| **`s 10` + Enter** | Snooze 10 minutes (or a bare number, e.g. `10`) |
| **Ctrl+C** | Stop the entire `run` loop (not the same as dismiss) |

After you **dismiss** a **`once`** alarm, it is **disabled** automatically (still in the file until you `remove` it). Repeating alarms stay enabled.

Snooze during `run` is held in memory only for that process; it is not written to JSON.

## Data file

| Mechanism | Location |
|-----------|----------|
| Default | `~/.config/pocket-alarm/alarms.json` |
| Environment | `POCKET_ALARM_DATA_FILE=/path/to/alarms.json` |
| CLI | `--data-file /path/to/alarms.json` |

Precedence: `--data-file` → `POCKET_ALARM_DATA_FILE` → default.

Example JSON (array of alarms):

```json
[
  {
    "id": "a1b2c3d4",
    "hour": 7,
    "minute": 30,
    "label": "Get up",
    "repeat": "daily",
    "days": [],
    "enabled": true
  }
]
```

For `repeat: "custom"`, `days` holds weekday indices (`0` = Monday … `6` = Sunday).

## Sound and troubleshooting

### “My alarm didn’t ring”

1. **Is `run` (or `start`) still running?** Adding an alarm only updates JSON. You need a terminal with `python3 -m pocket_alarm run` open before the alarm minute.
2. **Is the alarm enabled?** Run `list` and check the **Enabled** column (`enable` / `disable`).
3. **Timing:** Alarms fire at **local** `HH:MM:00`–`HH:MM:59`. Start `run` before that minute ends. Use **Next fire** in `list` to confirm the computed time.
4. **Volume / audio:** System volume up; run `python3 -m pocket_alarm test-sound`. Try a known file: `python3 -m pocket_alarm --sound /System/Library/Sounds/Hero.aiff test-sound`.
5. **Terminal bell:** If you only hear nothing and no `afplay`, enable the terminal bell in Terminal/iTerm preferences or rely on `test-sound` confirming `afplay`.

### Custom sound

```bash
python3 -m pocket_alarm --sound /path/to/file.aiff run
```

Built-in default picks the first available system `.aiff` (e.g. Sosumi on macOS). Not all macOS versions ship the same filenames.

## Project structure

```
alarm-clock/
├── pyproject.toml          # package metadata and pocket-alarm entry point
├── pocket_alarm/
│   ├── __main__.py         # python -m pocket_alarm
│   ├── cli.py              # argparse and subcommands
│   ├── config.py           # default paths and POCKET_ALARM_DATA_FILE
│   ├── models.py           # Alarm dataclass and JSON mapping
│   ├── parsing.py          # time, repeat, and duration parsing
│   ├── scheduling.py       # next fire time (minute granularity)
│   ├── storage.py          # load/save JSON, find by id
│   └── ringer.py           # sleep until, play sound, snooze/dismiss UI
└── tests/                  # unit tests (unittest)
```

## Development / tests

```bash
cd "/path/to/alarm-clock"
python3 -m unittest discover -s tests -v
```

## Limitations

- **Minute precision** on `add`; use `timer` for sub-minute countdowns.
- **One scheduler process** — run a single `run` instance you intend to use for firing.
- **No background daemon** — no launchd/systemd integration; the terminal must stay open.
- **Snooze** applies only while that `run` process is alive.
- **Sleep / suspend** may delay firing until the process wakes and rechecks the clock.
- **Local wall time** only; DST follows the OS. No timezone picker.
