"""Running a proof of concept in a locked-down container."""

import json
import secrets
import shutil
import subprocess
import tempfile
from pathlib import Path

from .config import REPO_ROOT, SANDBOX_LIMITS, TARGET, TARGET_DIR


class SandboxError(RuntimeError):
    pass


def docker_available():
    if not shutil.which("docker"):
        return False
    probe = subprocess.run(["docker", "info", "--format", "{{.ServerVersion}}"],
                           capture_output=True, text=True)
    return probe.returncode == 0


def image_exists(image):
    probe = subprocess.run(["docker", "image", "inspect", image], capture_output=True)
    return probe.returncode == 0


def build(build_name=None, force=False, quiet=True):
    """Build the target images. Needs network once; runs never do."""
    names = [build_name] if build_name else list(TARGET["builds"])
    built = []
    for name in names:
        spec = TARGET["builds"][name]
        if image_exists(spec["image"]) and not force:
            continue
        cmd = ["docker", "build", "--build-arg", "PYYAML_VERSION=%s" % spec["version"],
               "-t", spec["image"], str(TARGET_DIR)]
        if quiet:
            cmd.insert(2, "-q")
        result = subprocess.run(cmd, capture_output=quiet, text=True)
        if result.returncode != 0:
            raise SandboxError("building %s failed:\n%s" % (spec["image"], (result.stderr or "")[-2000:]))
        built.append(spec["image"])
    return built


def run_poc(poc_code, build_name="vulnerable"):
    """Run PoC source against one build. Returns the harness record."""
    spec = TARGET["builds"][build_name]
    if not image_exists(spec["image"]):
        build(build_name)
    nonce = secrets.token_hex(16)
    limits = SANDBOX_LIMITS
    temp_root = REPO_ROOT / ".proveit"
    temp_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="proveit-", dir=temp_root) as tmp:
        poc_dir = Path(tmp)
        (poc_dir / "poc.py").write_text(poc_code, encoding="utf-8")
        name = "proveit-run-%s" % nonce[:12]
        cmd = [
            "docker", "run", "--rm", "-i", "--name", name,
            "--network", "none",
            "--read-only",
            "--tmpfs", "/tmp:rw,size=16m,mode=1777",
            "--memory", limits["memory"], "--memory-swap", limits["memory"],
            "--pids-limit", limits["pids"],
            "--cpus", limits["cpus"],
            "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges",
            "--env", "PYTHONDONTWRITEBYTECODE=1",
            "-v", "%s:/poc:ro" % poc_dir,
            spec["image"],
        ]
        try:
            proc = subprocess.run(cmd, input=nonce + "\n", capture_output=True, text=True,
                                  timeout=limits["timeout_seconds"])
            timed_out = False
        except subprocess.TimeoutExpired as exc:
            subprocess.run(["docker", "kill", name], capture_output=True)
            proc, timed_out = exc, True

    stdout = proc.stdout or ""
    if isinstance(stdout, bytes):
        stdout = stdout.decode(errors="replace")
    record = None
    prefix = "@@PROVEIT %s " % nonce
    for line in stdout.splitlines():
        if line.startswith(prefix):
            record = json.loads(line[len(prefix):])
    exit_code = None if timed_out else proc.returncode
    if record is None:
        record = {"error": None, "events": [], "marker_exists": False,
                  "marker_written_by_library": False, "marker_written_by_poc": False,
                  "output": stdout[-2000:], "harness_lost": True}
    record.update({
        "build": build_name,
        "image": spec["image"],
        "target_version": spec["version"],
        "exit_code": exit_code,
        "timed_out": timed_out,
        # 137 = killed by SIGKILL, which is what the kernel's OOM killer sends.
        "killed": exit_code is not None and exit_code >= 128,
        "signal": (exit_code - 128) if exit_code is not None and exit_code > 128 else None,
    })
    return record
