"""Extensible profile ingestion from Slack, files, and future sources."""

from src.profile_ingestion.models import IngestResult, ProfilePayload
from src.profile_ingestion.service import format_ingest_summary, ingest_profile, ingest_profiles

__all__ = [
    "ProfilePayload",
    "IngestResult",
    "ingest_profile",
    "ingest_profiles",
    "format_ingest_summary",
]
