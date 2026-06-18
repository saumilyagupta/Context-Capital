"""Prompt-injection sanitizer for imported memories.

Design: docs/sdd.md §2.3 + docs/security/threat-model.md §3.
Three modes: REFUSE (drop), WRAP (prefix as untrusted), SANITIZE (redact).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class SanitizationMode(StrEnum):
    REFUSE = "refuse"
    WRAP = "wrap"
    SANITIZE = "sanitize"


PATTERNS: dict[str, re.Pattern[str]] = {
    "ignore-previous": re.compile(r"(?i)\bignore\s+(all\s+)?previous\b"),
    "system-tag":      re.compile(r"(?i)\bsystem\s*:"),
    "you-are-now":     re.compile(r"(?i)\byou\s+are\s+now\b"),
    "override-your":   re.compile(r"(?i)\boverride\s+your\b"),
    "act-as":          re.compile(r"(?i)\bact\s+as\s+(if|a)\b"),
}

WRAP_PREFIX = "[UNTRUSTED:imported] "
REDACTION = "[REDACTED]"


@dataclass
class SanitizationResult:
    clean_text: str
    patterns_fired: list[str] = field(default_factory=list)
    refused: bool = False


def evaluate(text: str, mode: SanitizationMode = SanitizationMode.WRAP) -> SanitizationResult:
    if not text:
        return SanitizationResult(clean_text=text)
    fired = [name for name, pat in PATTERNS.items() if pat.search(text)]
    if not fired:
        return SanitizationResult(clean_text=text)
    if mode == SanitizationMode.REFUSE:
        return SanitizationResult(clean_text="", patterns_fired=fired, refused=True)
    if mode == SanitizationMode.WRAP:
        return SanitizationResult(clean_text=f"{WRAP_PREFIX}{text}", patterns_fired=fired)
    if mode == SanitizationMode.SANITIZE:
        cleaned = text
        for pat in PATTERNS.values():
            cleaned = pat.sub(REDACTION, cleaned)
        return SanitizationResult(clean_text=cleaned, patterns_fired=fired)
    raise ValueError(f"Unknown sanitization mode: {mode}")


def sanitize_memory(memory: dict[str, Any], mode: SanitizationMode = SanitizationMode.WRAP) -> dict[str, Any] | None:
    out = {**memory}
    fired_all: list[str] = []

    obj = out.get("object", {})
    if isinstance(obj.get("value"), str):
        ev = evaluate(obj["value"], mode)
        if ev.refused:
            return None
        out["object"] = {**obj, "value": ev.clean_text}
        fired_all.extend(ev.patterns_fired)

    prov = dict(out.get("provenance", {}))
    if isinstance(prov.get("raw_excerpt"), str):
        ev = evaluate(prov["raw_excerpt"], mode)
        if ev.refused:
            return None
        prov["raw_excerpt"] = ev.clean_text
        fired_all.extend(ev.patterns_fired)

    prov["imported"] = True  # spec §11.1.2 — importer forces this regardless of what the doc claimed
    if fired_all:
        prov["sanitization_trace"] = sorted(set(fired_all))
    out["provenance"] = prov
    return out
