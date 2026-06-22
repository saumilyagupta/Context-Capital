"""Deterministic PII-stripping anonymizer for ChatGPT and Claude exports.

CLI: python -m tools.anonymize_export --vendor chatgpt --in real.json --out anon.json --seed 42
"""
from __future__ import annotations

import argparse
import json
import os
import random
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

COMMON_NAMES: frozenset[str] = frozenset({
    "James", "John", "Robert", "Michael", "William", "David", "Joseph", "Charles",
    "Thomas", "Daniel", "Matthew", "Anthony", "Mark", "Donald", "Steven", "Paul",
    "Andrew", "Joshua", "Kenneth", "Kevin", "Brian", "George", "Edward", "Ronald",
    "Timothy", "Jason", "Jeffrey", "Ryan", "Jacob", "Gary", "Nicholas", "Eric",
    "Stephen", "Jonathan", "Larry", "Justin", "Scott", "Brandon", "Frank", "Benjamin",
    "Gregory", "Samuel", "Raymond", "Patrick", "Alexander", "Jack", "Dennis", "Jerry",
    "Tyler", "Aaron",
    "Mary", "Patricia", "Jennifer", "Linda", "Elizabeth", "Barbara",
    "Susan", "Jessica", "Sarah", "Karen", "Nancy", "Lisa", "Margaret", "Betty",
    "Sandra", "Ashley", "Kimberly", "Emily", "Donna", "Michelle", "Carol", "Amanda",
    "Melissa", "Deborah", "Stephanie", "Rebecca", "Sharon", "Laura", "Cynthia", "Amy",
    "Kathleen", "Angela", "Shirley", "Brenda", "Emma", "Anna", "Pamela", "Nicole",
    "Samantha", "Katherine", "Christine", "Helen", "Debra", "Rachel", "Carolyn", "Janet",
    "Maria", "Catherine", "Heather", "Diane", "Olivia", "Julie", "Joyce", "Victoria",
    "Ruth", "Virginia", "Lauren", "Kelly", "Christina", "Joan", "Evelyn", "Judith",
    "Andrea", "Hannah", "Megan", "Cheryl", "Jacqueline", "Martha",
})

_STOP: frozenset[str] = frozenset({
    "This", "That", "With", "From", "They", "What", "When", "Where", "Which", "While",
    "After", "Before", "About", "Because", "Could", "Would", "Should", "There", "These",
    "Their", "Them", "Than", "Then", "Also", "Just", "Like", "More", "Most", "Some",
    "Other", "Such", "Into", "Over", "Onto", "Upon", "Being", "Been", "Very",
    "Even", "Each", "Every", "Really", "Quite", "Always", "Never", "Often", "Again",
    "Still", "Said", "Says", "Make", "Made", "Done", "Take", "Took", "Goes", "Gone",
    "Have", "Will", "Want",
})

_EMAIL_RE = re.compile(r"\b[\w.+\-]+@[\w\-]+(?:\.[\w\-]+)+\b")
_URL_RE = re.compile(r"https?://[^\s\"'<>)]+", re.IGNORECASE)
_PHONE_RE = re.compile(r"(?:\+?1[\s.\-]?)?\(?\d{3}\)?[\s.\-]?\d{3}[\s.\-]?\d{4}\b")
_API_KEY_RES: dict[str, re.Pattern[str]] = {
    "openai": re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"),
    "anthropic": re.compile(r"\bsk-ant-[A-Za-z0-9\-]{20,}\b"),
    "aws": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "github": re.compile(r"\bghp_[A-Za-z0-9]{30,}\b"),
}
_WORD_RE = re.compile(r"\b[A-Za-z][A-Za-z'\-]+\b")


@dataclass
class AnonymizeReport:
    emails_replaced: int = 0
    urls_replaced: int = 0
    phones_replaced: int = 0
    names_replaced: int = 0
    api_keys_detected: int = 0


def anonymize(
    *,
    vendor: str,
    in_path: Path,
    out_path: Path,
    seed: int | None = None,
    aggressive: bool = False,
) -> AnonymizeReport:
    if vendor not in ("chatgpt", "claude"):
        raise ValueError(f"unsupported vendor: {vendor}")
    actual_seed = seed if seed is not None else int.from_bytes(os.urandom(8), "big")
    rng = random.Random(actual_seed)
    raw: Any = json.loads(in_path.read_text())
    report = AnonymizeReport()
    out = _walk(raw, rng, report, aggressive=aggressive)
    out_path.write_text(json.dumps(out, indent=2))
    if seed is not None:
        out_path.with_suffix(out_path.suffix + ".seed.txt").write_text(str(seed))
    return report


def _walk(obj: Any, rng: random.Random, report: AnonymizeReport, *, aggressive: bool) -> Any:
    if isinstance(obj, str):
        return _scrub_string(obj, rng, report, aggressive=aggressive)
    if isinstance(obj, dict):
        return {k: _walk(v, rng, report, aggressive=aggressive) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_walk(item, rng, report, aggressive=aggressive) for item in obj]
    return obj


def _scrub_string(s: str, rng: random.Random, report: AnonymizeReport, *, aggressive: bool) -> str:
    for regex in _API_KEY_RES.values():
        hits = len(regex.findall(s))
        if hits:
            report.api_keys_detected += hits
            s = regex.sub("<api-key>", s)

    def email_sub(_m: re.Match[str]) -> str:
        report.emails_replaced += 1
        return f"<email-{rng.randint(1, 9999)}@example.invalid>"

    s = _EMAIL_RE.sub(email_sub, s)

    def url_sub(m: re.Match[str]) -> str:
        report.urls_replaced += 1
        return f"https://example.invalid/{abs(hash(m.group(0))) % 10**8:08x}"

    s = _URL_RE.sub(url_sub, s)

    def phone_sub(_m: re.Match[str]) -> str:
        report.phones_replaced += 1
        return f"<phone-{rng.randint(1, 9999)}>"

    s = _PHONE_RE.sub(phone_sub, s)

    def word_sub(m: re.Match[str]) -> str:
        word = m.group(0)
        cap = word.capitalize()
        if cap in COMMON_NAMES:
            report.names_replaced += 1
            return f"Person{rng.randint(1, 999)}"
        if aggressive and len(word) >= 4 and word[0].isupper() and cap not in _STOP:
            return f"Project{rng.randint(1, 999)}"
        return word

    s = _WORD_RE.sub(word_sub, s)
    return s


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="anonymize-export")
    p.add_argument("--vendor", required=True, choices=["chatgpt", "claude"])
    p.add_argument("--in", dest="in_path", required=True, type=Path)
    p.add_argument("--out", required=True, type=Path)
    p.add_argument("--seed", type=int, default=None)
    p.add_argument("--aggressive", action="store_true")
    args = p.parse_args(argv)
    report = anonymize(
        vendor=args.vendor,
        in_path=args.in_path,
        out_path=args.out,
        seed=args.seed,
        aggressive=args.aggressive,
    )
    sys.stdout.write(f"Anonymized -> {args.out}\n")
    sys.stdout.write(
        f"  emails: {report.emails_replaced}  urls: {report.urls_replaced}  "
        f"phones: {report.phones_replaced}  names: {report.names_replaced}  "
        f"api-keys: {report.api_keys_detected}\n"
    )
    if report.api_keys_detected:
        sys.stderr.write("WARNING: API keys detected and redacted. Investigate the source.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
