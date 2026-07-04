"""Shared models for profile ingestion from any source."""

from dataclasses import dataclass, field


@dataclass
class ProfilePayload:
    """Normalized profile data from any ingestion source."""

    recipient: str
    interests_text: str
    source: str
    source_ref: str = ""
    metadata: dict = field(default_factory=dict)


@dataclass
class IngestResult:
    recipient: str
    chunks_saved: int
    source: str
    source_ref: str = ""
