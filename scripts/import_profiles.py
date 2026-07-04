#!/usr/bin/env python3
"""Import recipient profiles from files into ChromaDB."""

import argparse
import sys
from pathlib import Path

# Allow `python scripts/import_profiles.py` from the project root
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

from src.langchain_core.tracing import configure_tracing
from src.profile_ingestion.service import format_ingest_summary, ingest_profiles
from src.profile_ingestion.sources import file as file_source
from src.langchain_core.settings import get_profile_import_settings


def main() -> int:
    load_dotenv(ROOT / ".env")
    configure_tracing()

    parser = argparse.ArgumentParser(description="Import recipient profiles from files")
    parser.add_argument(
        "path",
        nargs="?",
        help="File or directory to import (default: PROFILE_IMPORT_DIR inbox)",
    )
    args = parser.parse_args()

    if args.path:
        target = Path(args.path)
    else:
        target = Path(get_profile_import_settings()["inbox_dir"])

    if not target.exists():
        print(f"Error: path not found: {target}", file=sys.stderr)
        return 1

    try:
        payloads = file_source.collect_from_path(target)
    except (FileNotFoundError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    if not payloads:
        print(f"No profile files found in {target}")
        return 1

    results = ingest_profiles(payloads)
    print(format_ingest_summary(results))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
