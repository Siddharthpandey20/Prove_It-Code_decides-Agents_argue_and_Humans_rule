"""Screening reports for instructions aimed at our agents.

This is Prove It's own first wall. The second is Switch Trust's guardrail,
which Switch runs on every human message before it reaches a room once an
admin turns it on (see docs/SETUP.md). The third is the sandbox: even an
injection that got through both would run with no network and no secrets.

The screen looks for text that talks *to an AI* rather than *about a bug*:
orders to ignore rules, requests for secrets or environment variables,
hidden text, and commands to run outside the sandbox. Ordinary exploit code
(eval, os.system inside the PoC) is expected in a security report and is
not flagged.
"""

import re
import unicodedata
from dataclasses import dataclass, field

RULES = [
    ("override", "tries to override the agent's instructions",
     r"\b(ignore|disregard|forget|override)\b[^.\n]{0,40}\b(previous|prior|above|your|all|system)\b[^.\n]{0,30}\b(instructions?|rules?|prompts?|guidelines|policies)\b"),
    ("persona", "tries to give the agent a new role",
     r"\b(you are now|act as|pretend to be|from now on you|new instructions|system prompt|developer mode|jailbreak)\b"),
    ("secrets", "asks for secrets or the environment",
     r"\b(print|dump|show|reveal|send|output|list|cat|echo|post|exfiltrate|leak)\b[^\n]{0,40}\b(env(ironment)?( variables)?|secrets?|api[_ ]?keys?|tokens?|credentials?|passwords?|ssh keys?|\.env|id_rsa|printenv)\b"),
    ("host_command", "asks an agent to run something outside the sandbox",
     r"\b(curl|wget|nc|ncat|bash|sh|powershell|iex)\s+(-{1,2}[\w-]+\s+)*['\"]?(https?://|\d{1,3}(\.\d{1,3}){3})|\|\s*(ba)?sh\b"),
    ("agent_address", "addresses the AI reviewers directly",
     r"\b(dear|attention|note (to|for)|hey|instructions? for)\b[^\n]{0,25}\b(ai|llm|assistant|agent|claude|codex|gpt|copilot|triager|reviewer bot)s?\b"),
    ("verdict_forcing", "tells the reviewers what verdict to reach",
     r"\b(mark|classify|label|report|treat|approve|escalate)\b[^\n]{0,30}\b(as )?(valid|critical|confirmed|reproduced|real|true positive|accepted)\b[^\n]{0,30}\b(without|regardless|no need|skip)\b"),
]
HIDDEN = [
    ("hidden_html", "hides text in HTML comments or tags", r"<!--.*?-->|<\s*(picture|details|span|div)[^>]*(hidden|display\s*:\s*none)[^>]*>"),
    ("hidden_unicode", "contains invisible Unicode characters", "[​-‏⁠-⁤﻿\U000e0000-\U000e007f]"),
]


@dataclass
class ScreenResult:
    blocked: bool
    findings: list = field(default_factory=list)

    def summary(self):
        return "; ".join(f["why"] for f in self.findings) or "clean"


def _normalise(text):
    text = unicodedata.normalize("NFKC", text)
    return re.sub(r"\s+", " ", text)


def screen(text):
    findings = []
    for rule_id, why, pattern in HIDDEN:
        match = re.search(pattern, text, re.I | re.S)
        if match:
            findings.append({"rule": rule_id, "why": why, "excerpt": repr(match.group(0)[:60])})
    flat = _normalise(text)
    for rule_id, why, pattern in RULES:
        match = re.search(pattern, flat, re.I)
        if match:
            findings.append({"rule": rule_id, "why": why, "excerpt": match.group(0)[:80]})
    return ScreenResult(blocked=bool(findings), findings=findings)
