"""Central profile ingestion pipeline — all sources write through here."""

from src.langchain_core.observability import trace_tool
from src.profile_ingestion.models import IngestResult, ProfilePayload
from src.tools.vector_db.profile_store import get_profile_store


@trace_tool("profile.ingest")
def ingest_profile(payload: ProfilePayload) -> IngestResult:
    """Save one profile payload to ChromaDB."""
    count = get_profile_store().save_profile(
        recipient=payload.recipient,
        interests_text=payload.interests_text,
        source=payload.source,
        source_ref=payload.source_ref,
        extra_metadata=payload.metadata,
    )
    return IngestResult(
        recipient=payload.recipient,
        chunks_saved=count,
        source=payload.source,
        source_ref=payload.source_ref,
    )


def ingest_profiles(payloads: list[ProfilePayload]) -> list[IngestResult]:
    """Save multiple profile payloads. Skips empty interest text."""
    results: list[IngestResult] = []
    for payload in payloads:
        if not payload.interests_text.strip():
            continue
        results.append(ingest_profile(payload))
    return results


def format_ingest_summary(results: list[IngestResult]) -> str:
    if not results:
        return "No profiles were imported."

    lines = []
    for result in results:
        if result.chunks_saved:
            ref = f" ({result.source_ref})" if result.source_ref else ""
            lines.append(
                f"• *{result.recipient}*: {result.chunks_saved} chunk(s) from "
                f"{result.source}{ref}"
            )
        else:
            lines.append(f"• *{result.recipient}*: nothing saved (empty content)")

    return "Imported profiles:\n" + "\n".join(lines)
