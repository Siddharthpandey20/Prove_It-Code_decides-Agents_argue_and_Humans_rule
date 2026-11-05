"""Running one proof of concept (entry point + YAML payload) in a locked-down container."""

import hashlib
import json
import os
import secrets
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from . import poc
from .config import SANDBOX_LIMITS, TARGET, TARGET_DIR, ensure_home

HARNESS_FILES = ("Dockerfile", "harness.py", "child.py")


# Every Docker call has a timeout, so a stuck daemon fails loudly instead of hanging a command.
PROBE_TIMEOUT = 20      # docker info, image inspect, docker kill
BUILD_TIMEOUT = 1800    # building an image from scratch (downloads and compiles PyYAML)


class SandboxError(RuntimeError):
    pass


def _docker(cmd, timeout, **kwargs):
    """Run one docker command with a timeout; a timeout raises SandboxError with what was running."""
    try:
        return subprocess.run(cmd, timeout=timeout, **kwargs)
    except subprocess.TimeoutExpired:
        raise SandboxError("`%s` did not finish within %d s; is Docker responding? (try `docker info`)"
                           % (" ".join(cmd[:3]), timeout)) from None


def docker_available():
    """A running Docker engine that runs Linux containers (Docker Desktop in Windows-containers mode cannot)."""
    if not shutil.which("docker"):
        return False
    try:
        probe = _docker(["docker", "info", "--format", "{{.OSType}}"], PROBE_TIMEOUT,
                        capture_output=True, text=True)
    except SandboxError:
        return False
    return probe.returncode == 0 and probe.stdout.strip().lower() == "linux"


def harness_digest():
    """Changes whenever the image's inputs change, so stale images get rebuilt."""
    digest = hashlib.sha256()
    for name in HARNESS_FILES:
        digest.update((TARGET_DIR / name).read_bytes().replace(b"\r\n", b"\n"))
    return digest.hexdigest()[:16]


def image_current(image):
    probe = _docker(["docker", "image", "inspect", "--format",
                     '{{ index .Config.Labels "proveit.harness" }}', image], PROBE_TIMEOUT,
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
        # Docker's output is always captured, so a failure can show its end; when not quiet it is also echoed.
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                encoding="utf-8", errors="replace")
        tail = []
        out_encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
        try:
            for line in proc.stdout:
                tail = (tail + [line])[-60:]
                if not quiet:
                    # A Windows console (cp1252) cannot print every character Docker emits.
                    print(line.encode(out_encoding, "replace").decode(out_encoding), end="")
            proc.wait(timeout=BUILD_TIMEOUT)
        except subprocess.TimeoutExpired:
            proc.kill()
            raise SandboxError("building %s took longer than %d s" % (spec["image"], BUILD_TIMEOUT)) from None
        finally:
            proc.stdout.close()
        if proc.returncode != 0:
            hint = ""
            if any("do not match the hashes" in line or "THESE PACKAGES DO NOT MATCH" in line for line in tail):
                hint = ("\nA download did not match its SHA-256: a corrupted download, proxy or cache, not the "
                        "Dockerfile. Retry, or run `docker builder prune` and build again.")
            raise SandboxError("building %s failed (exit %s). Last lines of Docker's output:\n%s%s" % (
                spec["image"], proc.returncode, "".join(tail).rstrip(), hint))
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
    root = ensure_home() / "mounts"
    root.mkdir(exist_ok=True)
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
        try:
            subprocess.run(["docker", "kill", name], capture_output=True, timeout=PROBE_TIMEOUT)
        except subprocess.TimeoutExpired:
            pass  # --rm and the container's own limits still end it
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
