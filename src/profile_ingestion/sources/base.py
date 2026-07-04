"""Profile source protocol — implement to add new ingestion channels."""

from typing import Protocol

from src.profile_ingestion.models import ProfilePayload


class ProfileSource(Protocol):
    """Collect profile payloads from a specific channel."""

    source_name: str

    def collect(self, *args, **kwargs) -> list[ProfilePayload]: ...
