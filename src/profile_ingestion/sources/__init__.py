"""Profile ingestion sources."""

from src.profile_ingestion.sources import file, slack
from src.profile_ingestion.sources.registry import SOURCE_NAMES, list_sources

__all__ = ["file", "slack", "SOURCE_NAMES", "list_sources"]
