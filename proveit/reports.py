"""Turning a reporter's free text into a ticket of fixed fields.

Only the Intake agent ever reads a reporter's prose. Everything downstream
(the Reproducer, the Skeptic, the triage room) gets the ticket: a claim and
a severity chosen from closed lists, an entry point from an allowlist, and
the payload's hash, size and known tags. The payload itself is stored where
only the sandbox reads it. No title, no reporter name, no excerpt.
"""

import re
from dataclasses import asdict, dataclass, field

from . import poc
from .config import PAYLOAD_MAX_BYTES

CLAIM_KEYWORDS = [
    ("code_execution", r"\b(rce|remote code execution|code execution|arbitrary code|execute arbitrary|command execution|executes code|execute code)\b"),
    ("denial_of_service", r"\b(dos|denial of service|memory exhaustion|billion laughs|resource exhaustion|out of memory|cpu exhaustion|hang)\b"),
    ("crash", r"\b(segfault|segmentation fault|crash|buffer overflow|heap overflow|use[- ]after[- ]free|memory corruption)\b"),
    ("info_leak", r"\b(information disclosure|info leak|leaks?|exfiltrat\w*|disclos\w*)\b"),
]
CLAIMS = [c for c, _ in CLAIM_KEYWORDS]
SEVERITIES = ["critical", "high", "medium", "low"]
FENCE = re.compile(r"```[ \t]*([\w+-]*)[ \t]*\r?\n(.*?)```", re.S)
FIELD = re.compile(r"^\s*(?:\*\*)?(severity|entry point|claimed impact|impact)(?:\*\*)?\s*:\s*(.+)$", re.I | re.M)


@dataclass
class Ticket:
    claim: str = ""
    severity: str = "unrated"
    entry_point: str = ""
    payload: str = ""
    poc_problem: str = ""
    missing: list = field(default_factory=list)
    # The canonical name (poc.OUT_OF_SCOPE_NAMES) of an out-of-scope entry point, never the reporter's words.
    out_of_scope_entry: str = ""

    def complete(self):
        return not self.missing and not self.poc_problem

    def to_dict(self):
        return asdict(self)


def classify_claim(text):
    """The claimed impact, picked from a closed list by keyword."""
    lowered = text.lower()
    best, best_pos = "", None
    for claim, pattern in CLAIM_KEYWORDS:
        match = re.search(pattern, lowered)
        if match and (best_pos is None or match.start() < best_pos):
            best, best_pos = claim, match.start()
    return best


def _fields(text):
    return {k.lower(): v.strip() for k, v in FIELD.findall(text)}


def parse(text):
    """Build a ticket from a report. Never copies prose into the ticket."""
    fields = _fields(text)
    impact_text = fields.get("claimed impact") or fields.get("impact") or text
    claim = classify_claim(impact_text) or classify_claim(text)
    severity = fields.get("severity", "").lower()
    severity = next((s for s in SEVERITIES if s in severity), "") or next(
        (s for s in SEVERITIES if re.search(r"\b%s\b" % s, text.lower())), "unrated")

    python_blocks, yaml_blocks = [], []
    for lang, body in FENCE.findall(text):
        lang = lang.lower()
        if lang in ("python", "py", "python3"):
            python_blocks.append(body)
        elif lang in ("yaml", "yml", ""):
            yaml_blocks.append(body)
    payload = max(yaml_blocks, key=len) if yaml_blocks else ""

    problem = ""
    entry_point = ""
    missing = []
    if python_blocks or (payload and poc.looks_like_python(payload)):
        problem = "python_code"
    elif payload:
        if len(payload.encode("utf-8", "surrogatepass")) > PAYLOAD_MAX_BYTES:
            problem = "too_large"
        if "entry point" in fields:
            entry_point, entry_problem = poc.parse_entry_point(fields["entry point"])
            problem = problem or entry_problem or ""
            entry_point = entry_point or ""
        else:
            missing.append("entry_point")
    elif "entry point" in fields:
        entry_point, entry_problem = poc.parse_entry_point(fields["entry point"])
        entry_point = entry_point or ""
        problem = entry_problem if entry_problem in ("unsafe_loader", "c_loader") else ""
        if not problem:
            missing.append("poc")
    else:
        missing.append("poc")
    if not claim:
        missing.append("claim")
    out_of_scope = (poc.out_of_scope_name(fields.get("entry point")) or "an unsafe loader") if problem == "unsafe_loader" else ""
    return Ticket(claim=claim, severity=severity, entry_point=entry_point, payload=payload,
                  poc_problem=problem, missing=missing, out_of_scope_entry=out_of_scope)


def merge(previous, followup_text):
    """A reporter's follow-up in the same thread replaces the proof and fills gaps."""
    update = parse(followup_text)
    merged = Ticket(**previous.to_dict())
    if update.payload or update.poc_problem:
        # A new proof (or a rejected one) replaces the old proof.
        merged.payload = update.payload
        merged.entry_point = update.entry_point or (previous.entry_point if update.payload else "")
        merged.poc_problem = update.poc_problem
        merged.out_of_scope_entry = update.out_of_scope_entry
    elif update.entry_point:
        # Only an entry point: it completes the payload already on file.
        merged.entry_point = update.entry_point
        if merged.poc_problem in ("unknown_entry_point", "no_entry_point"):
            merged.poc_problem = ""
            merged.out_of_scope_entry = ""
    if not merged.claim and update.claim:
        merged.claim = update.claim
    if merged.severity == "unrated" and update.severity != "unrated":
        merged.severity = update.severity
    missing = []
    if not merged.payload and not merged.poc_problem:
        missing.append("poc")
    elif merged.payload and not merged.entry_point and not merged.poc_problem:
        missing.append("entry_point")
    if not merged.claim:
        missing.append("claim")
    merged.missing = missing
    return merged
