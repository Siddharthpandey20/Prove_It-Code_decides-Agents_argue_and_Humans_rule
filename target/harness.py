"""Runs one proof of concept inside the sandbox and reports what it did.

The PoC is untrusted code. This harness does not try to stop it (the
container does that: no network, no secrets, read-only, capped memory,
unprivileged user). It records evidence instead, with a Python audit hook:

* every file opened for writing, every exec/compile, every process spawn and
  every socket connect the PoC caused;
* for each one, whether code from the target library was on the call stack
  at that moment. That is the difference between "the library ran my code"
  (a real bug) and "my script wrote the file itself" (a fake proof).

The verdict is decided on the host from this record, never in here.

Protocol: the host writes a one-line nonce on stdin. The result is printed
on the real stdout as one line: ``@@PROVEIT <nonce> <json>``. Anything the
PoC prints goes to a capture file and is returned inside the JSON.
"""

import json
import os
import resource
import runpy
import sys
import time
import traceback

POC_PATH = "/poc/poc.py"
MARKER = "/tmp/proveit_marker"
CAPTURE = "/tmp/.proveit_output"
LIBRARY_PACKAGE = "yaml"
WATCHED = {
    "open",
    "exec",
    "compile",
    "os.system",
    "os.exec",
    "os.posix_spawn",
    "os.spawn",
    "subprocess.Popen",
    "socket.connect",
    "ctypes.dlopen",
}
MAX_EVENTS = 60
MAX_OUTPUT = 4000


def _library_dir():
    module = __import__(LIBRARY_PACKAGE)
    return os.path.dirname(os.path.abspath(module.__file__)), getattr(module, "__version__", "?")


def main():
    nonce = sys.stdin.readline().strip()
    sys.stdin.close()
    real_stdout = os.dup(1)

    lib_dir, lib_version = _library_dir()
    events = []
    state = {"armed": False, "dropped": 0}

    def library_frames():
        names = []
        frame = sys._getframe(2)
        while frame is not None:
            filename = frame.f_code.co_filename
            if filename.startswith(lib_dir):
                names.append("%s:%s" % (os.path.basename(filename), frame.f_code.co_name))
            frame = frame.f_back
        return names

    def describe(event, args):
        if event == "open":
            path, mode = args[0], args[1]
            flags = args[2] if len(args) > 2 and isinstance(args[2], int) else 0
            if not isinstance(path, str):
                return None
            if mode is not None:
                writing = any(c in str(mode) for c in "wax+")
            else:  # os.open: decide from the flags
                writing = bool(flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT))
            if not writing or path == CAPTURE:
                return None
            return "write %s" % path
        if event in ("exec", "compile"):
            return event
        return "%s %s" % (event, str(args[0])[:120] if args else "")

    def hook(event, args):
        if not state["armed"] or event not in WATCHED:
            return
        try:
            detail = describe(event, args)
            if detail is None:
                return
            frames = library_frames()
            if len(events) >= MAX_EVENTS:
                state["dropped"] += 1
                return
            events.append({
                "event": event,
                "detail": detail,
                "in_library": bool(frames),
                "library_frames": frames[:6],
            })
        except Exception:  # never let evidence collection break the run
            pass

    sys.addaudithook(hook)

    capture = os.open(CAPTURE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    sys.stdout.flush()
    sys.stderr.flush()
    os.dup2(capture, 1)
    os.dup2(capture, 2)

    error = None
    started = time.monotonic()
    state["armed"] = True
    try:
        runpy.run_path(POC_PATH, run_name="__main__")
    except SystemExit as exc:
        if exc.code not in (None, 0):
            error = {"type": "SystemExit", "message": str(exc.code), "in_library": False}
    except BaseException as exc:  # the PoC may raise anything
        tb = traceback.extract_tb(exc.__traceback__)
        error = {
            "type": type(exc).__name__,
            "message": (str(exc).splitlines() or [""])[0][:300],
            "in_library": any(f.filename.startswith(lib_dir) for f in tb),
            "where": ["%s:%s" % (os.path.basename(f.filename), f.name) for f in tb[-4:]],
        }
    finally:
        state["armed"] = False
    elapsed = time.monotonic() - started

    sys.stdout.flush()
    sys.stderr.flush()
    os.dup2(real_stdout, 1)
    os.dup2(real_stdout, 2)
    os.close(capture)
    with open(CAPTURE, "r", errors="replace") as handle:
        output = handle.read()

    marker_writes = [e for e in events if e["event"] == "open" and e["detail"] == "write " + MARKER]
    result = {
        "library": LIBRARY_PACKAGE,
        "library_version": lib_version,
        "seconds": round(elapsed, 3),
        "peak_rss_mb": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0, 1),
        "error": error,
        "events": events,
        "events_dropped": state["dropped"],
        "marker_exists": os.path.exists(MARKER),
        "marker_written_by_library": any(e["in_library"] for e in marker_writes),
        "marker_written_by_poc": any(not e["in_library"] for e in marker_writes),
        "output": output[-MAX_OUTPUT:],
    }
    os.write(1, ("@@PROVEIT %s %s\n" % (nonce, json.dumps(result))).encode())


if __name__ == "__main__":
    main()
