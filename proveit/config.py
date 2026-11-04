"""Paths and the one target project Prove It checks reports against."""

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
WORK_DIR = Path(os.environ.get("PROVEIT_WORK_DIR", REPO_ROOT / "work"))
REPLAYS_DIR = REPO_ROOT / "reports" / "replays"
TARGET_DIR = REPO_ROOT / "target"

# The pinned target. The demo uses PyYAML because its CVE-2020-14343 has a
# one-file proof of concept that runs offline, and the fix landed in a single
# release (5.3.1 vulnerable, 5.4 patched).
TARGET = {
    "name": "PyYAML",
    "package": "yaml",
    "builds": {
        "vulnerable": {"version": "5.3.1", "image": "proveit-target:vulnerable"},
        "patched": {"version": "5.4", "image": "proveit-target:patched"},
    },
}

# What a PoC must do to prove each kind of claim. Intake sends this contract
# to the reporter, so the cost of producing proof lands on them.
MARKER_PATH = "/tmp/proveit_marker"
PROOF_CONTRACT = {
    "code_execution": (
        "Your PoC must make the library itself execute code that creates "
        "the file `%s`. Writing that file directly from your script does "
        "not count: the sandbox records which code wrote it." % MARKER_PATH
    ),
    "denial_of_service": (
        "Your PoC must make the library use more than 200 MB of memory or "
        "more than 10 seconds of CPU on a single call. The sandbox caps "
        "memory at 256 MB and time at 20 seconds and records both."
    ),
    "crash": (
        "Your PoC must make the library crash the interpreter (a signal "
        "such as SIGSEGV), not just raise a Python exception."
    ),
    "info_leak": (
        "Your PoC must make the library return or write data it should "
        "not have access to. Say exactly which bytes leak and where."
    ),
}

SANDBOX_LIMITS = {
    "memory": "256m",
    "pids": "64",
    "cpus": "1",
    "timeout_seconds": 20,
}
DOS_MEMORY_MB = 200
DOS_SECONDS = 10
