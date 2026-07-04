"""Import profiles from inbox directory, files, or Slack uploads."""

import re
from pathlib import Path

from src.langchain_core.observability import trace_agent
from src.langchain_core.settings import get_profile_import_settings
from src.profile_ingestion.models import ProfilePayload
from src.profile_ingestion.service import format_ingest_summary, ingest_profiles
from src.profile_ingestion.sources import file as file_source
from src.profile_ingestion.sources import slack as slack_source
from src.shared.conversation_context import AgentResponse, SlackContext
from src.tools.vector_db.profile_store import get_profile_store

IMPORT_COMMAND = re.compile(r"\bimport\s+profiles?\b", re.IGNORECASE)
SUPPORTED_UPLOAD_EXTENSIONS = {".txt", ".md", ".json"}


@trace_agent("profile_collector.import")
def handle_profile_import(
    path: Path | None = None,
    *,
    source: str = "file",
    context: SlackContext | None = None,
) -> AgentResponse:
    """Import profiles from a path or the configured inbox directory."""
    target = path or Path(get_profile_import_settings()["inbox_dir"])
    if not target.exists():
        return AgentResponse(
            text=(
                f"Import folder not found: `{target}`\n"
                "Create it and add `.txt`, `.md`, or `.json` profile files."
            )
        )

    try:
        payloads = file_source.collect_from_path(target, source=source)
    except (FileNotFoundError, ValueError) as exc:
        return AgentResponse(text=f"Profile import failed: {exc}")

    if not payloads:
        return AgentResponse(text=f"No profile files found in `{target}`.")

    results = ingest_profiles(payloads)
    return AgentResponse(text=format_ingest_summary(results))


def handle_slack_file_uploads(files: list[dict], bot_token: str) -> AgentResponse:
    """Import profiles from files uploaded in Slack."""
    payloads: list[ProfilePayload] = []
    errors: list[str] = []

    for file_info in files:
        name = file_info.get("name", "upload")
        suffix = Path(name).suffix.lower()
        if suffix not in SUPPORTED_UPLOAD_EXTENSIONS:
            errors.append(f"Skipped `{name}` (use .txt, .md, or .json)")
            continue

        try:
            content = _download_slack_file(bot_token, file_info)
            payloads.extend(
                file_source.parse_file_content(
                    content,
                    name,
                    source="slack_file",
                    source_ref=name,
                )
            )
        except Exception as exc:
            errors.append(f"Failed to read `{name}`: {exc}")

    if not payloads:
        detail = "\n".join(errors) if errors else "No valid profile files in upload."
        return AgentResponse(text=f"No profiles imported.\n{detail}")

    results = ingest_profiles(payloads)
    summary = format_ingest_summary(results)
    if errors:
        summary += "\n\n" + "\n".join(errors)
    return AgentResponse(text=summary)


def is_profile_import_command(text: str) -> bool:
    return bool(IMPORT_COMMAND.search(text.strip()))


def _download_slack_file(bot_token: str, file_info: dict) -> str:
    from urllib.request import Request, urlopen

    file_id = file_info.get("id")
    url = file_info.get("url_private_download") or file_info.get("url_private")
    if not url and file_id:
        raise ValueError("missing download URL — add files:read scope and reinstall app")

    if not url:
        raise ValueError("missing file URL")

    request = Request(url, headers={"Authorization": f"Bearer {bot_token}"})
    with urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8")
