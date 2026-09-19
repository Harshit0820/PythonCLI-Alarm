"""Terminal ringing: bell, macOS audio, snooze/dismiss."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

from pocket_alarm.models import Alarm

# Loud / long macOS system sounds (Sonar is not present on all macOS versions).
DEFAULT_SOUND_CANDIDATES: tuple[str, ...] = (
    "/System/Library/Sounds/Sosumi.aiff",
    "/System/Library/Sounds/Hero.aiff",
    "/System/Library/Sounds/Submarine.aiff",
    "/System/Library/Sounds/Glass.aiff",
    "/System/Library/Sounds/Ping.aiff",
    "/System/Library/Sounds/Funk.aiff",
)


@dataclass
class SoundPlayResult:
    """Outcome of a single audio attempt."""

    method: str
    ok: bool
    detail: str = ""


@dataclass
class RingerConfig:
    """Audio and display settings for ringing."""

    sound_path: Path | None = None
    volume: float = 1.0


def resolve_sound_path(custom: str | Path | None = None) -> Path | None:
    """Pick an existing audio file: custom path first, then built-in list."""
    if custom:
        path = Path(custom).expanduser()
        if path.is_file():
            return path
        raise FileNotFoundError(f"Sound file not found: {path}")

    for candidate in DEFAULT_SOUND_CANDIDATES:
        if os.path.isfile(candidate):
            return Path(candidate)
    return None


def _play_afplay(path: Path, volume: float) -> subprocess.Popen[bytes] | None:
    afplay = shutil.which("afplay")
    if not afplay:
        return None
    args = [afplay]
    if volume != 1.0:
        args.extend(["-v", str(max(0.0, min(volume, 1.0)))])
    args.append(str(path))
    try:
        return subprocess.Popen(
            args,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
    except OSError as exc:
        sys.stderr.write(f"pocket-alarm: afplay failed to start: {exc}\n")
        sys.stderr.flush()
        return None


def _play_say() -> subprocess.Popen[bytes] | None:
    say = shutil.which("say")
    if not say:
        return None
    try:
        return subprocess.Popen(
            [say, "-v", "Samantha", "Wake up! Alarm!"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
    except OSError as exc:
        sys.stderr.write(f"pocket-alarm: say failed to start: {exc}\n")
        sys.stderr.flush()
        return None


def play_sound_once(config: RingerConfig) -> SoundPlayResult:
    """Play one sound burst; return how it went (never raises)."""
    path = config.sound_path
    if path is None:
        try:
            path = resolve_sound_path()
        except FileNotFoundError as exc:
            return SoundPlayResult("none", False, str(exc))

    if path is not None:
        proc = _play_afplay(path, config.volume)
        if proc is not None:
            try:
                _, err = proc.communicate(timeout=120)
                if proc.returncode == 0:
                    return SoundPlayResult("afplay", True, str(path))
                detail = err.decode(errors="replace").strip() or f"exit {proc.returncode}"
                sys.stderr.write(f"pocket-alarm: afplay error: {detail}\n")
                sys.stderr.flush()
            except subprocess.TimeoutExpired:
                proc.kill()
                return SoundPlayResult("afplay", False, "timed out")

    proc = _play_say()
    if proc is not None:
        try:
            _, err = proc.communicate(timeout=60)
            if proc.returncode == 0:
                return SoundPlayResult("say", True, "say")
            detail = err.decode(errors="replace").strip() or f"exit {proc.returncode}"
            sys.stderr.write(f"pocket-alarm: say error: {detail}\n")
            sys.stderr.flush()
        except subprocess.TimeoutExpired:
            proc.kill()
            return SoundPlayResult("say", False, "timed out")

    sys.stdout.write("\a")
    sys.stdout.flush()
    return SoundPlayResult("bell", True, "terminal bell (audio may be silent in Terminal settings)")


def _print_ring_banner(label: str, iteration: int) -> None:
    title = label or "ALARM"
    line = "=" * 60
    msg = f"\n{line}\n  *** {title.upper()} — RINGING ({iteration}) ***\n  {datetime.now().strftime('%H:%M:%S')}\n{line}\n"
    sys.stderr.write(msg)
    sys.stderr.flush()
    sys.stdout.write(f"\n*** {title} ***\n")
    sys.stdout.flush()


@dataclass
class _RingSession:
    stop: threading.Event = field(default_factory=threading.Event)
    thread: threading.Thread | None = None
    last_result: SoundPlayResult | None = None


def _audio_loop(stop: threading.Event, label: str, config: RingerConfig) -> None:
    iteration = 0
    while not stop.is_set():
        iteration += 1
        _print_ring_banner(label, iteration)
        result = play_sound_once(config)
        # Store on session via closure — set on outer object in ring_until_handled
        _audio_loop.last_result = result  # type: ignore[attr-defined]
        if not result.ok and result.method != "bell":
            sys.stderr.write(
                f"pocket-alarm: audio fallback after {result.method}: {result.detail}\n"
            )
            sys.stderr.flush()
        stop.wait(0.5)


def test_sound(config: RingerConfig, *, loops: int = 1) -> list[SoundPlayResult]:
    """Play sound ``loops`` times for manual or automated verification."""
    results: list[SoundPlayResult] = []
    path = config.sound_path or resolve_sound_path()
    if path:
        sys.stderr.write(f"Using sound file: {path}\n")
        sys.stderr.flush()
    else:
        sys.stderr.write("No .aiff found; will try say/bell.\n")
        sys.stderr.flush()
    cfg = RingerConfig(sound_path=path, volume=config.volume)
    for i in range(loops):
        sys.stderr.write(f"--- test play {i + 1}/{loops} ---\n")
        sys.stderr.flush()
        results.append(play_sound_once(cfg))
    return results


def prompt_snooze_or_dismiss(
    default_snooze_minutes: int,
) -> tuple[str, int | None]:
    """
    Block until user chooses snooze or dismiss.

    Returns (action, snooze_minutes) where action is ``snooze`` or ``dismiss``.
    Enter alone snoozes for default_snooze_minutes.
    """
    if not sys.stdin.isatty():
        sys.stderr.write(
            "pocket-alarm: stdin is not a terminal — auto-dismiss disabled; "
            "ringing continues until you send input (Ctrl+C or 'd').\n"
        )
        sys.stderr.flush()

    prompt = (
        f"\nPress Enter to snooze ({default_snooze_minutes} min), "
        "or type 'd' + Enter to dismiss: "
    )
    while True:
        try:
            line = input(prompt)
            break
        except EOFError:
            sys.stderr.write(
                "pocket-alarm: EOF on stdin — still ringing; "
                "pipe 'd' to dismiss or press Ctrl+C.\n"
            )
            sys.stderr.flush()
            time.sleep(1.0)
            continue
    stripped = line.strip().lower()
    if stripped in ("d", "dismiss", "q", "quit"):
        return "dismiss", None
    if stripped.startswith("s"):
        parts = stripped.split()
        if len(parts) == 2 and parts[1].isdigit():
            return "snooze", int(parts[1])
        return "snooze", default_snooze_minutes
    if stripped.isdigit():
        return "snooze", int(stripped)
    return "snooze", default_snooze_minutes


def ring_until_handled(
    alarm: Alarm | None,
    label: str,
    default_snooze_minutes: int,
    config: RingerConfig | None = None,
) -> tuple[str, int | None]:
    """Ring repeatedly until user snoozes or dismisses."""
    cfg = config or RingerConfig()
    if cfg.sound_path is None:
        try:
            cfg.sound_path = resolve_sound_path()
        except FileNotFoundError:
            pass

    display = label or (alarm.label if alarm else "") or "Alarm"
    stop = threading.Event()
    thread = threading.Thread(
        target=_audio_loop,
        args=(stop, display, cfg),
        daemon=True,
    )
    thread.start()
    try:
        return prompt_snooze_or_dismiss(default_snooze_minutes)
    finally:
        stop.set()
        thread.join(timeout=5.0)


def sleep_until(target: datetime) -> None:
    """Sleep until local naive ``target``, re-checking wall clock every second."""
    while True:
        now = datetime.now()
        remaining = (target - now).total_seconds()
        if remaining <= 0:
            return
        time.sleep(min(remaining, 1.0))


def apply_snooze(alarm: Alarm, minutes: int, after: datetime | None = None) -> datetime:
    """Return the datetime when a snoozed alarm should fire."""
    base = after or datetime.now()
    return base + timedelta(minutes=minutes)
