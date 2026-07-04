"""Registry of profile ingestion sources."""

SOURCE_NAMES = ("slack", "file")


def list_sources() -> list[str]:
    return list(SOURCE_NAMES)
