"""Paths, the one target project, and the rules a proof of concept must follow."""

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
WORK_DIR = Path(os.environ.get("PROVEIT_WORK_DIR", REPO_ROOT / "work"))
REPLAYS_DIR = REPO_ROOT / "reports" / "replays"
TARGET_DIR = REPO_ROOT / "target"

# The pinned target. PyYAML's CVE-2020-14343 is triggered by a YAML document
# alone, and the fix landed in a single release (5.3.1 vulnerable, 5.4 patched).
TARGET = {
    "name": "PyYAML",
    "package": "yaml",
    "builds": {
        "vulnerable": {"version": "5.3.1", "image": "proveit-target:vulnerable"},
        "patched": {"version": "5.4", "image": "proveit-target:patched"},
    },
}

# A proof of concept is DATA: a YAML payload plus one entry point from this
# list. The trusted harness calls the entry point on the payload; reporters
# never send code. These are the loaders PyYAML documents as safe (SafeLoader)
# or as meant to avoid code execution (FullLoader) in 5.x. The C variants are
# left out because the 5.3.1 image has no libyaml (yaml.__with_libyaml__ is
# False there), so they could not be compared across both builds.
ENTRY_POINTS = {
    "safe_load": "yaml.safe_load(payload)",
    "full_load": "yaml.full_load(payload)",
    "load:SafeLoader": "yaml.load(payload, Loader=yaml.SafeLoader)",
    "load:FullLoader": "yaml.load(payload, Loader=yaml.FullLoader)",
}
# PyYAML documents these as unsafe by design ("UnsafeLoader ... also called
# Loader for backwards compatibility"). Using them is not a vulnerability.
UNSAFE_ENTRY_POINTS = ("yaml.unsafe_load", "yaml.unsafe_load_all", "yaml.UnsafeLoader", "yaml.Loader")
PAYLOAD_MAX_BYTES = 64 * 1024

# The harness creates this directory fresh for every run. Code execution is
# proven when the file appears in it: only the library, running attacker
# input, can create it, because the reporter sends no code.
MARKER_DIR = "/tmp/proveit"
MARKER_PATH = MARKER_DIR + "/marker"

# Limits for the one library call (enforced inside the container on the child
# process), and for the container as a whole.
CALL_LIMITS = {"seconds": 10, "memory_mb": 192}
SANDBOX_LIMITS = {
    "memory": "256m",
    "pids": "64",
    "cpus": "1",
    "timeout_seconds": 20,
}

PROOF_CONTRACT = {
    "code_execution": (
        "The payload must make the library itself execute code that creates "
        "the file `%s`. Nothing else runs in the sandbox, so the file can only "
        "appear if the library ran your input as code." % MARKER_PATH
    ),
    "denial_of_service": (
        "The payload must make the one library call run longer than %d seconds "
        "or use more than %d MB of memory. The sandbox measures both."
        % (CALL_LIMITS["seconds"], CALL_LIMITS["memory_mb"])
    ),
    "crash": (
        "The payload must make the library crash the interpreter with a native "
        "fault (a signal such as SIGSEGV), not just raise a Python exception."
    ),
    "info_leak": (
        "Information leaks are never decided automatically; a maintainer reads "
        "the evidence."
    ),
}

POC_FORMAT_HELP = (
    "Send the proof as data, not code: a line `Entry point: <one of %s>` and the YAML "
    "payload in a ```yaml block (UTF-8, at most %d KB). Python scripts are not accepted, and "
    "the loaders PyYAML documents as unsafe (unsafe_load, UnsafeLoader, Loader) are out of scope "
    "because using them is not a vulnerability."
    % (", ".join("`%s`" % k for k in ENTRY_POINTS), PAYLOAD_MAX_BYTES // 1024)
)
