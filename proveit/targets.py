"""The target adapter: one interface for every library Prove It checks.

Prove It began with a single target, PyYAML. A `Target` gathers everything
that is specific to one library -- its name, its pinned vulnerable and patched
builds and images, its sandbox folder, the entry points a proof may use, how a
reporter's entry-point text and payload are read, its scope document and the
two rooms it is served in -- behind one object. The rest of the code (the
sandbox, Intake, the messages, the evidence and advisory packs) takes a
`Target` and never names a library directly.

The PyYAML target delegates to the values that already live in `config` and
`poc`, so PyYAML behaves exactly as before: the same objects, the same text,
the same image names and versions. A second target (see `target-<lib>/` and
its entry below) carries its own values and its own small parser.

A ticket records its target key in `record["target"]`. A ticket with no such
field, and every message and live ticket created before this change, means
PyYAML -- so nothing already in flight changes.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from . import config, poc

DEFAULT_KEY = "pyyaml"


@dataclass(frozen=True)
class Target:
    key: str
    name: str                      # display name, e.g. "PyYAML"
    import_name: str               # the module the sandbox imports, e.g. "yaml"
    pypi_name: str                 # the PyPI distribution, e.g. "PyYAML"
    builds: dict                   # {"vulnerable": {"version","image"}, "patched": {...}}
    target_dir: Path               # the folder holding this target's Dockerfile and harness
    build_arg: str                 # the Dockerfile ARG the build sets, e.g. "PYYAML_VERSION"
    entry_points: dict             # {key: "human call"}; the allowlist
    out_of_scope_names: tuple      # canonical names refused as out of scope (may be empty)
    payload_max_bytes: int
    scope_doc: str                 # repo-relative path of the scope policy
    fence_langs: tuple             # code-fence languages whose body is taken as the payload
    payload_filename: str          # the private payload file name, e.g. "payload.yaml"
    intake_room: str
    triage_room: str
    poc_format_help: str
    safe_hint: str                 # the in-scope entry points named in a refusal, e.g. "safe_load or full_load"
    payload_noun: str              # what the payload is, for advisory prose, e.g. "YAML" or "SQL"
    _parse_entry_point: Callable   # (text) -> (key|None, problem|None)
    _out_of_scope_name: Callable   # (text) -> canonical name | None
    _tags: Callable                # (payload) -> [safe tag, ...]
    # Build/run policy. PyYAML is built by a bare `proveit build` and may be
    # built lazily on first use; a second target is built only on request, so
    # the test suite never builds an image it does not have.
    build_by_default: bool = True
    lazy_build: bool = True

    # -- builds -----------------------------------------------------------
    def version(self, build):
        return self.builds[build]["version"]

    def image(self, build):
        return self.builds[build]["image"]

    @property
    def vulnerable_version(self):
        return self.version("vulnerable")

    @property
    def patched_version(self):
        return self.version("patched")

    # -- proof parsing (per target) --------------------------------------
    def parse_entry_point(self, text):
        return self._parse_entry_point(text)

    def out_of_scope_name(self, text):
        return self._out_of_scope_name(text)

    def tags(self, payload):
        return self._tags(payload)

    def validate(self, entry_point, payload):
        return poc.validate(entry_point, payload, entry_points=self.entry_points,
                            max_bytes=self.payload_max_bytes)


# -- the PyYAML target: delegates to the existing config/poc values -------
PYYAML = Target(
    key="pyyaml",
    name=config.TARGET["name"],
    import_name=config.TARGET["package"],
    pypi_name="PyYAML",
    builds=config.TARGET["builds"],          # the SAME dict config exposes, so mocks still bite
    target_dir=config.TARGET_DIR,
    build_arg="PYYAML_VERSION",
    entry_points=config.ENTRY_POINTS,        # the SAME dict
    out_of_scope_names=poc.OUT_OF_SCOPE_NAMES,
    payload_max_bytes=config.PAYLOAD_MAX_BYTES,
    scope_doc="docs/policy/pyyaml-scope.md",
    fence_langs=("yaml", "yml", ""),
    payload_filename="payload.yaml",
    intake_room="proveit-intake",
    triage_room="proveit-triage",
    poc_format_help=config.POC_FORMAT_HELP,
    safe_hint="safe_load or full_load",
    payload_noun="YAML",
    _parse_entry_point=poc.parse_entry_point,
    _out_of_scope_name=poc.out_of_scope_name,
    _tags=poc.tags,
)


TARGETS = {PYYAML.key: PYYAML}


def register(target):
    TARGETS[target.key] = target
    return target


def get(key):
    """The target for `key`; an empty or unknown key means PyYAML (the default and the fallback)."""
    return TARGETS.get(key or DEFAULT_KEY, TARGETS[DEFAULT_KEY])


def for_record(record):
    """The target a ticket belongs to. A ticket with no `target` field is PyYAML."""
    return get((record or {}).get("target"))


def buildable():
    """The targets a bare `proveit build` builds (PyYAML only, unless a target opts in)."""
    return [t for t in TARGETS.values() if t.build_by_default]
