"""Module3 test conductor: offline / smoke / live tiers in one command.

Usage:
    python run_tests.py                  # default tier: smoke
    python run_tests.py --tier offline   # fast, no network (~20s)
    python run_tests.py --tier smoke     # live but cheap (~2-4 min)
    python run_tests.py --tier live      # integration (~5-10 min)
    python run_tests.py --tier live --full-live   # real 20k chunk threshold
    python run_tests.py --tier all       # offline -> smoke -> live

Tier contents:
    offline  pytest tests/ -q                      (fakes; no Ollama/KAS)
    smoke    python tests/smoke_test.py            (real LLM + real /chunk;
             chunk legs self-skip with a warning if KAS is down)
    live     pytest tests/test_integration_live.py (INTEGRATION=1; needs
             Postgres on :5432, the KAS HTTP API on :8002 and Ollama)

The live tier runs with CHUNK_THRESHOLD_CHARS=4000 by default so the
long-transcript test finishes in minutes; --full-live uses the production
20,000-char threshold instead.

Exit code is 0 only if every requested tier passed (CI-friendly).
This file orchestrates only; the pytest suites and smoke_test.py remain the
sources of truth for the actual checks.
"""

import argparse
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx

# Keep our prints in sync with subprocess output even when piped.
sys.stdout.reconfigure(line_buffering=True)

MODULE_DIR = Path(__file__).resolve().parent


def _heading(title: str) -> None:
    print(f"\n{'=' * 60}\n{title}\n{'=' * 60}")


def _run(cmd: list[str], env: dict | None = None) -> bool:
    """Run a subprocess, stream its output, return True on exit code 0."""
    print(f"$ {' '.join(cmd)}\n")
    merged_env = {**os.environ, **env} if env else None
    completed = subprocess.run(cmd, cwd=MODULE_DIR, env=merged_env)
    return completed.returncode == 0


def _port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(3)
        return sock.connect_ex(("127.0.0.1", port)) == 0


# ----------------------------------------------------------------------
# Tiers
# ----------------------------------------------------------------------


def tier_offline() -> bool:
    """Unit tests with fakes - fast, no services needed."""
    _heading("TIER 1: OFFLINE (pytest, fakes, ~20s)")
    return _run([sys.executable, "-m", "pytest", "-q"])


def tier_smoke() -> bool:
    """Live smoke: short LLM analyses + real /chunk + gate check."""
    _heading("TIER 2: SMOKE (live but cheap, ~2-4 min)")
    return _run(
        [sys.executable, "-u", str(MODULE_DIR / "tests" / "smoke_test.py")],
        env={"PYTHONPATH": str(MODULE_DIR)},
    )


def tier_live(full: bool = False) -> bool:
    """Full integration: KAS + Postgres + Ollama, real end-to-end."""
    label = "20k threshold" if full else "4k threshold"
    _heading(f"TIER 3: LIVE INTEGRATION ({label}, ~5-10 min)")

    problems = []
    if not _port_open(5432):
        problems.append(
            "Postgres not on :5432 - run 'docker start meeting-db' "
            "(see module2-backend/README.md)"
        )
    try:
        httpx.get("http://localhost:8002/health", timeout=5.0).raise_for_status()
    except httpx.HTTPError:
        problems.append(
            "KAS HTTP API not on :8002 - run 'uvicorn app:app --port 8002' "
            "in the module4-knowledge assistant service folder"
        )
    try:
        base = os.getenv("LLM_BASE_URL", "http://localhost:11434/v1").rsplit("/v1", 1)[0]
        httpx.get(f"{base}/api/tags", timeout=5.0).raise_for_status()
    except httpx.HTTPError:
        problems.append("Ollama not reachable on :11434")

    if problems:
        print("LIVE tier cannot run - missing prerequisites:")
        for problem in problems:
            print(f"  - {problem}")
        return False

    threshold = os.getenv(
        "LIVE_CHUNK_THRESHOLD_CHARS", "20000" if full else "4000"
    )
    return _run(
        [sys.executable, "-m", "pytest", "tests/test_integration_live.py", "-q", "-v"],
        env={"INTEGRATION": "1", "CHUNK_THRESHOLD_CHARS": threshold},
    )


TIERS = {
    "offline": tier_offline,
    "smoke": tier_smoke,
    "live": tier_live,
}
ORDER = ["offline", "smoke", "live"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--tier",
        choices=[*ORDER, "all"],
        default="smoke",
        help="which test tier to run (default: smoke)",
    )
    parser.add_argument(
        "--full-live",
        action="store_true",
        help="use the production 20,000-char chunk threshold in the live tier",
    )
    args = parser.parse_args()

    selected = ORDER if args.tier == "all" else [args.tier]

    scores: list[tuple[str, bool, float]] = []
    for name in selected:
        started = time.monotonic()
        try:
            if name == "live":
                passed = TIERS[name](full=args.full_live)
            else:
                passed = TIERS[name]()
        except KeyboardInterrupt:
            print("\nInterrupted.")
            return 130
        elapsed = time.monotonic() - started
        scores.append((name, passed, elapsed))

    _heading("SUMMARY")
    for name, passed, elapsed in scores:
        verdict = "PASS" if passed else "FAIL"
        print(f"  {name:<8} {verdict}  ({elapsed:.0f}s)")
    overall = all(passed for _, passed, _ in scores)
    print(f"\n  overall: {'PASS' if overall else 'FAIL'}")
    return 0 if overall else 1


if __name__ == "__main__":
    sys.exit(main())
