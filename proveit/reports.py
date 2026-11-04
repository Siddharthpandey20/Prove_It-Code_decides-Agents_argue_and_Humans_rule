"""Turning a reporter's free text into a structured ticket.

Only the Intake agent ever reads a reporter's prose. Everything downstream
(the Reproducer, the Skeptic, the maintainers' triage room) gets the ticket:
a fixed set of fields chosen from closed lists, plus the PoC as a file that
is run in the sandbox and never interpreted as instructions.
"""

import re
from dataclasses import dataclass, field, asdict

CLAIM_KEYWORDS = [
    ("code_execution", r"\b(rce|remote code execution|code execution|arbitrary code|execute arbitrary|command execution|eval)\b"),
    ("denial_of_service", r"\b(dos|denial of service|memory exhaustion|billion laughs|resource exhaustion|out of memory|cpu exhaustion|hang)\b"),
    ("crash", r"\b(segfault|segmentation fault|crash|buffer overflow|heap overflow|use[- ]after[- ]free|memory corruption)\b"),
    ("info_leak", r"\b(information disclosure|info leak|leaks?|exfiltrat\w*|disclos\w*)\b"),
]

SEVERITIES = ["critical", "high", "medium", "low"]
API_PATTERN = re.compile(r"\byaml\.(full_load|load|safe_load|unsafe_load|load_all|full_load_all|safe_load_all|unsafe_load_all|dump|safe_dump)\b")
FENCE = re.compile(r"```(?:python|py)?[ \t]*\n(.*?)```", re.S | re.I)
HEADING_FIELD = re.compile(r"^\s*(?:\*\*)?(title|reporter|severity|component|claimed impact|impact)(?:\*\*)?\s*:\s*(.+)$", re.I | re.M)


@dataclass
class Ticket:
    title: str = ""
    reporter: str = ""
    claim: str = ""
    severity: str = ""
    component: str = ""
    poc: str = ""
    missing: list = field(default_factory=list)

    def complete(self):
        return not self.missing

    def to_dict(self):
        return asdict(self)


def _first_match(pattern, text):
    match = re.search(pattern, text, re.I)
    return match.group(0) if match else ""


def classify_claim(text):
    """The claimed impact, picked from a closed list by keyword."""
    lowered = text.lower()
    best, best_pos = "", None
    for claim, pattern in CLAIM_KEYWORDS:
        match = re.search(pattern, lowered)
        if match and (best_pos is None or match.start() < best_pos):
            best, best_pos = claim, match.start()
    return best


def parse(text, reporter=""):
    """Build a ticket from a report. Never copies prose into the ticket."""
    fields = {k.lower(): v.strip() for k, v in HEADING_FIELD.findall(text)}
    first_line = next((l.strip("# ").strip() for l in text.splitlines() if l.strip()), "")

    blocks = FENCE.findall(text)
    poc = max(blocks, key=len).strip() + "\n" if blocks else ""

    impact_text = fields.get("claimed impact") or fields.get("impact") or text
    claim = classify_claim(impact_text) or classify_claim(text)

    severity = fields.get("severity", "").lower()
    severity = next((s for s in SEVERITIES if s in severity), "") or next(
        (s for s in SEVERITIES if re.search(r"\b%s\b" % s, text.lower())), "unrated"
    )

    component = ""
    for source in (fields.get("component", ""), poc, text):
        api = API_PATTERN.search(source)
        if api:
            component = api.group(0)
            break

    missing = []
    if not poc:
        missing.append("poc")
    if not claim:
        missing.append("claim")

    title = re.sub(r"[^\w .,:()/-]", "", fields.get("title") or first_line)[:90]
    return Ticket(
        title=title,
        reporter=reporter or fields.get("reporter", ""),
        claim=claim,
        severity=severity,
        component=component or "unknown",
        poc=poc,
        missing=missing,
    )


def merge(previous, followup_text):
    """A reporter's follow-up in the same thread fills in what was missing."""
    update = parse(followup_text, previous.reporter)
    merged = Ticket(**previous.to_dict())
    if not merged.poc and update.poc:
        merged.poc = update.poc
    if not merged.claim and update.claim:
        merged.claim = update.claim
    if merged.component == "unknown" and update.component != "unknown":
        merged.component = update.component
    merged.missing = [m for m in ("poc", "claim") if not getattr(merged, m)]
    return merged
