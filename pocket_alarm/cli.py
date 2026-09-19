"""Command-line interface."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path

from pocket_alarm.config import resolve_data_file
from pocket_alarm.models import Alarm
from pocket_alarm.parsing import ParseError, parse_duration, parse_repeat, parse_time
from pocket_alarm.ringer import (
    RingerConfig,
    apply_snooze,
    resolve_sound_path,
    ring_until_handled,
    sleep_until,
    test_sound,
)
from pocket_alarm.scheduling import format_datetime, next_fire_among, next_fire_at
from pocket_alarm.storage import StorageError, find_alarm, load_alarms, save_alarms


def _err(message: str) -> None:
    print(f"error: {message}", file=sys.stderr)


def _exit(code: int, message: str | None = None) -> None:
    if message:
        _err(message)
    raise SystemExit(code)


def cmd_add(args: argparse.Namespace) -> int:
    try:
        hour, minute = parse_time(args.time)
        repeat, days = parse_repeat(args.repeat)
    except ParseError as exc:
        return _exit(2, str(exc))

    alarm = Alarm(
        hour=hour,
        minute=minute,
        label=args.label or "",
        repeat=repeat,
        days=days,
        enabled=not args.disabled,
    )
    path = resolve_data_file(args.data_file)
    try:
        alarms = load_alarms(path)
        alarms.append(alarm)
        save_alarms(path, alarms)
    except StorageError as exc:
        return _exit(1, str(exc))

    nxt = next_fire_at(alarm)
    when = format_datetime(nxt) if nxt else "—"
    print(f"Added alarm {alarm.id} at {alarm.time_display()} (next: {when})")
    return 0


def _print_table(alarms: list[Alarm]) -> None:
    if not alarms:
        print("No alarms.")
        return
    rows: list[tuple[str, str, str, str, str, str]] = []
    for a in alarms:
        nxt = next_fire_at(a) if a.enabled else None
        next_s = format_datetime(nxt) if nxt else "—"
        rows.append(
            (
                a.id,
                a.time_display(),
                a.label or "—",
                a.repeat_display(),
                "yes" if a.enabled else "no",
                next_s,
            )
        )
    headers = ("ID", "Time", "Label", "Repeat", "Enabled", "Next fire")
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell))
    fmt = "  ".join(f"{{:{w}}}" for w in widths)
    print(fmt.format(*headers))
    print(fmt.format(*("-" * w for w in widths)))
    for row in rows:
        print(fmt.format(*row))


def cmd_list(args: argparse.Namespace) -> int:
    path = resolve_data_file(args.data_file)
    try:
        alarms = load_alarms(path)
    except StorageError as exc:
        return _exit(1, str(exc))
    _print_table(alarms)
    return 0


def _mutate_alarm(args: argparse.Namespace, fn) -> int:
    path = resolve_data_file(args.data_file)
    try:
        alarms = load_alarms(path)
    except StorageError as exc:
        return _exit(1, str(exc))
    alarm = find_alarm(alarms, args.id)
    if alarm is None:
        return _exit(2, f"No alarm with id {args.id!r}")
    fn(alarm)
    try:
        save_alarms(path, alarms)
    except StorageError as exc:
        return _exit(1, str(exc))
    return 0


def cmd_remove(args: argparse.Namespace) -> int:
    path = resolve_data_file(args.data_file)
    try:
        alarms = load_alarms(path)
    except StorageError as exc:
        return _exit(1, str(exc))
    alarm = find_alarm(alarms, args.id)
    if alarm is None:
        return _exit(2, f"No alarm with id {args.id!r}")
    alarms = [a for a in alarms if a is not alarm]
    try:
        save_alarms(path, alarms)
    except StorageError as exc:
        return _exit(1, str(exc))
    print(f"Removed alarm {alarm.id}")
    return 0


def cmd_enable(args: argparse.Namespace) -> int:
    def enable(a: Alarm) -> None:
        a.enabled = True
        print(f"Enabled alarm {a.id}")

    return _mutate_alarm(args, enable)


def cmd_disable(args: argparse.Namespace) -> int:
    def disable(a: Alarm) -> None:
        a.enabled = False
        print(f"Disabled alarm {a.id}")

    return _mutate_alarm(args, disable)


def _effective_fire(
    alarm: Alarm,
    snooze_until: dict[str, datetime],
    not_before: dict[str, datetime],
    now: datetime,
) -> datetime | None:
    search_after = not_before.get(alarm.id)
    if search_after and search_after > now:
        now = search_after
    scheduled = next_fire_at(alarm, now)
    override = snooze_until.get(alarm.id)
    if override and (scheduled is None or override < scheduled):
        if override > datetime.now().replace(tzinfo=None):
            return override
    return scheduled


def _ringer_config(args: argparse.Namespace) -> RingerConfig:
    path = getattr(args, "sound", None)
    sound_path = None
    if path:
        sound_path = resolve_sound_path(path)
    return RingerConfig(sound_path=sound_path, volume=getattr(args, "volume", 1.0))


def cmd_run(args: argparse.Namespace) -> int:
    path = resolve_data_file(args.data_file)
    snooze_minutes = args.snooze
    snooze_until: dict[str, datetime] = {}
    not_before: dict[str, datetime] = {}
    ringer = _ringer_config(args)

    print("Pocket Alarm running (Ctrl+C to stop). Waiting for next alarm…", flush=True)
    try:
        while True:
            try:
                alarms = load_alarms(path)
            except StorageError as exc:
                return _exit(1, str(exc))

            enabled = [a for a in alarms if a.enabled]
            if not enabled and not snooze_until:
                print("No enabled alarms. Add alarms or enable existing ones.")
                return 0

            now = datetime.now()
            best_time: datetime | None = None
            best_alarm: Alarm | None = None
            for alarm in enabled:
                fire = _effective_fire(alarm, snooze_until, not_before, now)
                if fire is None:
                    continue
                if best_time is None or fire < best_time:
                    best_time = fire
                    best_alarm = alarm

            if best_time is None:
                print("No upcoming alarm times.")
                return 0

            if not args.quiet:
                label = best_alarm.label if best_alarm else ""
                print(f"Next: {format_datetime(best_time)} — {label or '(no label)'}")

            sleep_until(best_time)

            fired_at = best_time
            fired_alarm = best_alarm
            try:
                fresh = load_alarms(path)
                if best_alarm is not None:
                    current = find_alarm(fresh, best_alarm.id)
                    if current is None or not current.enabled:
                        continue
                    fired_alarm = current
            except StorageError:
                pass
            if fired_alarm is None:
                continue

            snooze_until.pop(fired_alarm.id, None)
            print(
                f"\n>>> Alarm firing: {fired_alarm.label or fired_alarm.id} "
                f"at {format_datetime(fired_at)} <<<",
                flush=True,
            )
            action, minutes = ring_until_handled(
                fired_alarm,
                fired_alarm.label,
                snooze_minutes,
                ringer,
            )
            not_before[fired_alarm.id] = fired_at + timedelta(minutes=1)

            if action == "snooze" and minutes is not None:
                snooze_until[fired_alarm.id] = apply_snooze(
                    fired_alarm, minutes
                )
                print(f"Snoozed {minutes} minute(s).")
                continue

            print("Dismissed.")
            if fired_alarm.repeat == "once":
                try:
                    alarms = load_alarms(path)
                    target = find_alarm(alarms, fired_alarm.id)
                    if target:
                        target.enabled = False
                        save_alarms(path, alarms)
                        print(f"One-shot alarm {fired_alarm.id} disabled.")
                except StorageError:
                    pass
    except KeyboardInterrupt:
        print("\nStopped.")
        return 0


def cmd_timer(args: argparse.Namespace) -> int:
    try:
        seconds = parse_duration(args.duration)
    except ParseError as exc:
        return _exit(2, str(exc))

    target = datetime.now() + timedelta(seconds=seconds)
    print(f"Timer set for {seconds}s (until {format_datetime(target)})")
    sleep_until(target)
    ring_until_handled(
        None,
        args.label or "Timer",
        args.snooze,
        _ringer_config(args),
    )
    return 0


def cmd_test_sound(args: argparse.Namespace) -> int:
    try:
        cfg = _ringer_config(args)
        results = test_sound(cfg, loops=args.loops)
    except FileNotFoundError as exc:
        return _exit(2, str(exc))
    for r in results:
        status = "ok" if r.ok else "FAILED"
        print(f"{r.method}: {status} — {r.detail}")
    if not any(r.ok for r in results):
        return _exit(1, "No audio method succeeded")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pocket-alarm",
        description="Terminal alarm clock with JSON persistence.",
    )
    parser.add_argument(
        "--data-file",
        metavar="PATH",
        help="Alarms JSON file (default: ~/.config/pocket-alarm/alarms.json)",
    )
    parser.add_argument(
        "--sound",
        metavar="PATH",
        help="Audio file for afplay (default: system .aiff)",
    )
    parser.add_argument(
        "--volume",
        type=float,
        default=1.0,
        help="afplay volume 0.0–1.0 (default: 1.0)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_add = sub.add_parser("add", help="Add an alarm")
    p_add.add_argument("time", help="Time (07:30 or 7:30am)")
    p_add.add_argument("--label", "-l", default="", help="Optional label")
    p_add.add_argument(
        "--repeat",
        "-r",
        default="once",
        help="once, daily, weekdays, or mon,wed,fri",
    )
    p_add.add_argument(
        "--disabled",
        action="store_true",
        help="Create alarm in disabled state",
    )
    p_add.set_defaults(func=cmd_add)

    p_list = sub.add_parser("list", help="List all alarms")
    p_list.set_defaults(func=cmd_list)

    p_remove = sub.add_parser("remove", help="Remove an alarm by id")
    p_remove.add_argument("id", help="Alarm id (prefix match allowed)")
    p_remove.set_defaults(func=cmd_remove)

    p_enable = sub.add_parser("enable", help="Enable an alarm")
    p_enable.add_argument("id", help="Alarm id")
    p_enable.set_defaults(func=cmd_enable)

    p_disable = sub.add_parser("disable", help="Disable an alarm")
    p_disable.add_argument("id", help="Alarm id")
    p_disable.set_defaults(func=cmd_disable)

    p_run = sub.add_parser("run", help="Run foreground alarm loop")
    p_run.add_argument(
        "--snooze",
        type=int,
        default=5,
        metavar="MIN",
        help="Default snooze duration in minutes (default: 5)",
    )
    p_run.add_argument(
        "--quiet",
        action="store_true",
        help="Do not print next-alarm status lines",
    )
    p_run.set_defaults(func=cmd_run)

    p_start = sub.add_parser("start", help="Alias for run")
    p_start.add_argument("--snooze", type=int, default=5, metavar="MIN")
    p_start.add_argument("--quiet", action="store_true")
    p_start.set_defaults(func=cmd_run)

    p_timer = sub.add_parser("timer", help="Countdown timer")
    p_timer.add_argument("duration", help="Duration (e.g. 30s, 5m, 1h)")
    p_timer.add_argument("--label", "-l", default="Timer")
    p_timer.add_argument("--snooze", type=int, default=5, metavar="MIN")
    p_timer.set_defaults(func=cmd_timer)

    p_test = sub.add_parser(
        "test-sound",
        help="Play alarm sound to verify audio (no alarm required)",
    )
    p_test.add_argument(
        "--loops",
        type=int,
        default=1,
        help="Number of times to play (default: 1)",
    )
    p_test.set_defaults(func=cmd_test_sound)

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    code = args.func(args)
    if code:
        raise SystemExit(code)


if __name__ == "__main__":
    main()
