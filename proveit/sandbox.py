"""Running one proof of concept (entry point + YAML payload) in a locked-down container."""

import hashlib
import json
import os
import secrets
import shutil
import subprocess
import tempfile
from pathlib import Path

from . import poc
from .config import PROVEIT_HOME, SANDBOX_LIMITS, TARGET, TARGET_DIR

HARNESS_FILES = ("Dockerfile", "harness.py", "child.py")


class SandboxError(RuntimeError):
    pass


def docker_available():
    if not shutil.which("docker"):
        return False
    probe = subprocess.run(["docker", "info", "--format", "{{.ServerVersion}}"],
                           capture_output=True, text=True)
    return probe.returncode == 0


def harness_digest():
    """Changes whenever the image's inputs change, so stale images get rebuilt."""
    digest = hashlib.sha256()
    for name in HARNESS_FILES:
        digest.update((TARGET_DIR / name).read_bytes().replace(b"\r\n", b"\n"))
    return digest.hexdigest()[:16]


def image_current(image):
    probe = subprocess.run(["docker", "image", "inspect", "--format",
                            '{{ index .Config.Labels "proveit.harness" }}', image],
                           capture_output=True, text=True)
    return probe.returncode == 0 and probe.stdout.strip() == harness_digest()


def build(build_name=None, force=False, quiet=True):
    """Build the target images. Needs network once; runs never do."""
    names = [build_name] if build_name else list(TARGET["builds"])
    built = []
    for name in names:
        spec = TARGET["builds"][name]
        if image_current(spec["image"]) and not force:
            continue
        cmd = ["docker", "build", "--build-arg", "PYYAML_VERSION=%s" % spec["version"],
               "--label", "proveit.harness=%s" % harness_digest(), "-t", spec["image"], str(TARGET_DIR)]
        if quiet:
            cmd.insert(2, "-q")
        result = subprocess.run(cmd, capture_output=quiet, text=True)
        if result.returncode != 0:
            raise SandboxError("building %s failed:\n%s" % (spec["image"], (result.stderr or "")[-2000:]))
        built.append(spec["image"])
    return built


def docker_flags(name, poc_dir):
    """Every isolation flag a run uses. Tests reuse this list unchanged."""
    limits = SANDBOX_LIMITS
    return [
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
    ]


def _mount_root():
    """Where the read-only /poc mount is staged: under ~/.proveit/<checkout>/mounts, not the system temp folder.

    Docker Desktop and Colima on macOS share the home folder with their VM but
    not macOS's /var/folders temp directory, so a mount from there arrives empty.
    The staged payload is reporter material, so it lives with the rest of it,
    where neither agent may read.
    """
    root = PROVEIT_HOME / "mounts"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _readable_by_sandbox(folder):
    """The container runs as uid 65534; on Linux hosts it must be able to read the read-only mount."""
    os.chmod(folder, 0o755)
    for child in Path(folder).iterdir():
        os.chmod(child, 0o644)


def _execute(cmd, stdin_text, name):
    try:
        proc = subprocess.run(cmd, input=stdin_text, capture_output=True, text=True,
                              timeout=SANDBOX_LIMITS["timeout_seconds"])
        return proc.returncode, proc.stdout or "", False
    except subprocess.TimeoutExpired as exc:
        subprocess.run(["docker", "kill", name], capture_output=True)
        out = exc.stdout or ""
        return None, out.decode(errors="replace") if isinstance(out, bytes) else out, True


def invalid_record(entry_point, payload, build_name, why):
    data = payload.encode("utf-8", "surrogatepass") if isinstance(payload, str) else (payload or b"")
    spec = TARGET["builds"][build_name]
    return {"outcome": "INVALID_PROOF", "why": why, "build": build_name, "image": spec["image"],
            "target_version": spec["version"], "entry_point": entry_point if entry_point in poc.ENTRY_POINTS else "rejected",
            "payload_sha256": hashlib.sha256(data).hexdigest(), "payload_bytes": len(data), "ran": False}


def run_poc(entry_point, payload, build_name="vulnerable"):
    """Run one payload against one build. Returns the record the harness's parent wrote."""
    problem = poc.validate(entry_point, payload)
    if problem:
        return invalid_record(entry_point, payload, build_name, poc.PROBLEMS[problem])
    spec = TARGET["builds"][build_name]
    if not image_current(spec["image"]):
        build(build_name)
    nonce = secrets.token_hex(16)
    name = "proveit-run-%s" % nonce[:12]
    with tempfile.TemporaryDirectory(prefix="proveit-", dir=_mount_root()) as tmp:
        poc_dir = Path(tmp)
        (poc_dir / "job.json").write_text(json.dumps({"entry_point": entry_point}), encoding="utf-8")
        (poc_dir / "payload.yaml").write_bytes(payload.encode("utf-8"))
        _readable_by_sandbox(poc_dir)
        exit_code, stdout, timed_out = _execute(docker_flags(name, poc_dir) + [spec["image"]], nonce + "\n", name)

    prefix = "@@PROVEIT %s " % nonce
    lines = [line for line in stdout.splitlines() if line.startswith(prefix)]
    if len(lines) == 1:
        record = json.loads(lines[0][len(prefix):])
    else:
        record = {"outcome": "INCONCLUSIVE",
                  "why": "the sandbox timed out" if timed_out else "the harness did not return exactly one record"}
    record.update({"build": build_name, "image": spec["image"], "target_version": spec["version"],
                   "container_exit_code": exit_code, "container_timed_out": timed_out, "ran": True})
    return record


def run_probe(code, build_name="vulnerable", timeout=None):
    """Tests only: run Python code in a container with exactly the flags a PoC run gets."""
    spec = TARGET["builds"][build_name]
    name = "proveit-probe-%s" % secrets.token_hex(6)
    with tempfile.TemporaryDirectory(prefix="proveit-", dir=_mount_root()) as tmp:
        _readable_by_sandbox(tmp)
        cmd = docker_flags(name, tmp) + ["--entrypoint", "python", spec["image"], "-I", "-c", code]
        exit_code, stdout, timed_out = _execute(cmd, "", name)
    return {"exit_code": exit_code, "output": stdout, "timed_out": timed_out}
