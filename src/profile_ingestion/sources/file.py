"""Collect profiles from local files (.txt, .md, .json)."""

import json
import re
from pathlib import Path

from src.agents.subagents.profile_collector.parser import parse_profile_save
from src.profile_ingestion.models import ProfilePayload

SUPPORTED_EXTENSIONS = {".txt", ".md", ".json"}

# Docs / non-profile files — never treat as recipients.
SKIP_FILENAMES = {
    "readme",
    "license",
    "licence",
    "changelog",
    "contributing",
    "authors",
    "notice",
}

# Filenames that hold multiple people (line-per-profile), not one person.
BATCH_FILENAMES = {
    "profiles",
    "batch",
    "import",
    "imports",
    "recipients",
    "people",
    "data",
    "notes",
    "all",
}

# Pronoun subjects must not become recipient names.
PRONOUN_RECIPIENTS = {"she", "he", "they", "it", "we", "i", "her", "him", "them"}


def _is_profile_file(path: Path) -> bool:
    if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        return False
    stem = path.stem.lower()
    base = re.split(r"[_\-.]", stem)[0]
    return base not in SKIP_FILENAMES


def collect_from_path(path: Path, source: str = "file") -> list[ProfilePayload]:
    """Read one file or all supported files in a directory."""
    path = path.expanduser().resolve()
    if path.is_dir():
        payloads: list[ProfilePayload] = []
        for child in sorted(path.iterdir()):
            if child.is_file() and _is_profile_file(child):
                payloads.extend(collect_from_path(child, source=source))
        return payloads
    if not path.is_file():
        raise FileNotFoundError(f"Profile file not found: {path}")
    if not _is_profile_file(path):
        return []
    if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"Unsupported file type {path.suffix}. "
            f"Use: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )

    content = path.read_text(encoding="utf-8")
    return parse_file_content(content, path.name, source=source, source_ref=str(path))


def parse_file_content(
    content: str,
    filename: str,
    *,
    source: str = "file",
    source_ref: str = "",
) -> list[ProfilePayload]:
    """Parse file body into one or more profile payloads."""
    if not _is_profile_file(Path(filename)):
        return []

    ref = source_ref or filename
    suffix = Path(filename).suffix.lower()

    if suffix == ".json":
        return _parse_json(content, source=source, source_ref=ref)
    return _parse_text(content, filename, source=source, source_ref=ref)


def _parse_json(content: str, *, source: str, source_ref: str) -> list[ProfilePayload]:
    data = json.loads(content)
    records = data if isinstance(data, list) else [data]
    payloads: list[ProfilePayload] = []

    for record in records:
        if not isinstance(record, dict):
            raise ValueError("JSON profile files must contain objects or an array of objects")

        recipient = record.get("recipient") or record.get("name")
        interests = record.get("interests") or record.get("text") or record.get("profile")
        if not recipient or not interests:
            raise ValueError(
                "Each JSON record needs recipient (or name) and interests (or text/profile)"
            )

        payloads.append(
            ProfilePayload(
                recipient=str(recipient).strip().title(),
                interests_text=str(interests).strip(),
                source=source,
                source_ref=source_ref,
                metadata={"filename": Path(source_ref).name},
            )
        )

    return payloads


def _parse_text(
    content: str,
    filename: str,
    *,
    source: str,
    source_ref: str,
) -> list[ProfilePayload]:
    text = content.strip()
    if not text:
        return []

    # Person-named files (sarah.txt): whole body belongs to that person.
    # Avoids treating "She enjoys coffee" as recipient "She".
    if _is_person_filename(filename):
        return [
            ProfilePayload(
                recipient=_recipient_from_filename(filename),
                interests_text=text,
                source=source,
                source_ref=source_ref,
                metadata={"filename": Path(filename).name},
            )
        ]

    payloads: list[ProfilePayload] = []
    current_recipient: str | None = None
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parsed = parse_profile_save(line)
        if not parsed:
            continue

        recipient, interests = parsed
        if recipient.lower() in PRONOUN_RECIPIENTS:
            if current_recipient:
                recipient = current_recipient
            else:
                continue
        else:
            current_recipient = recipient

        payloads.append(
            ProfilePayload(
                recipient=recipient,
                interests_text=interests,
                source=source,
                source_ref=source_ref,
                metadata={"filename": Path(filename).name},
            )
        )

    if payloads:
        return payloads

    recipient = _recipient_from_filename(filename)
    return [
        ProfilePayload(
            recipient=recipient,
            interests_text=text,
            source=source,
            source_ref=source_ref,
            metadata={"filename": Path(filename).name},
        )
    ]


def _is_person_filename(filename: str) -> bool:
    """True for sarah.txt; false for profiles.txt / batch.md."""
    stem = Path(filename).stem.lower()
    base = re.split(r"[_\-.]", stem)[0]
    return bool(base) and base.isalpha() and base not in BATCH_FILENAMES


def _recipient_from_filename(filename: str) -> str:
    stem = Path(filename).stem
    base = re.split(r"[_\-.]", stem)[0]
    if not base:
        raise ValueError(f"Cannot infer recipient name from filename: {filename}")
    return base.title()
