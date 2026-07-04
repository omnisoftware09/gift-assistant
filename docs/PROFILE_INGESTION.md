# Profile Ingestion (multi-source)

Profiles can be collected from **Slack messages**, **local files**, and **Slack file uploads**. All sources write through the same `profile_ingestion` pipeline into embedded ChromaDB.

---

## Architecture

```
Sources                    Pipeline                    Storage
─────────                  ────────                    ───────
Slack message      ──┐
Slack file upload  ──┼──► profile_ingestion/service ──► ChromaDB
Local file / CLI   ──┘         (chunk + embed)
```

Future sources (email, API, etc.) add a collector under `src/profile_ingestion/sources/` and call `ingest_profiles()`.

---

## 1. Slack message (existing)

```
Sarah likes hiking and coffee
What does Sarah like?
```

---

## 2. Local files (CLI)

### Inbox folder

Default: `data/profile_imports/inbox/`

Sample files are included (`sarah.txt`, `profiles.json`).

```bash
cd /Users/wadhwa09/aiprojects/gift-assistant
source venv/bin/activate
python scripts/import_profiles.py
```

Import a specific file or folder:

```bash
python scripts/import_profiles.py data/profile_imports/inbox/sarah.txt
python scripts/import_profiles.py /path/to/my/profiles/
```

Requires `OPENAI_API_KEY` (or Ollama embeddings) for Chroma embeddings.

### File formats

| Format | Example |
|--------|---------|
| **Named `.txt`** | `sarah.txt` — body is interests; name from filename |
| **Lines in `.txt`** | `Sarah likes hiking` per line |
| **JSON object** | `{"recipient": "Mom", "interests": "gardening"}` |
| **JSON array** | `[{...}, {...}]` |

---

## 3. Slack inbox command

DM the bot:

```
import profiles
```

Or slash command (scans default inbox):

```
/import-profiles
```

Optional path argument:

```
/import-profiles data/profile_imports/inbox/sarah.txt
```

---

## 4. Slack file upload

Upload a `.txt`, `.md`, or `.json` file in a DM (or @mention with attachment).

**Required scope:** add `files:read` to Bot Token Scopes and reinstall the app.

---

## Verify import

```
What does Sarah like?
recommend gift for Sarah's graduation
```

CLI with no Slack:

```bash
python scripts/import_profiles.py
python -m pytest tests/test_profile_file_source.py -q
```

---

## Metadata stored per chunk

| Field | Example |
|-------|---------|
| `recipient` | `sarah` |
| `source` | `slack`, `file`, `slack_file` |
| `source_ref` | file path or Slack message ts |
| `created_at` | Unix timestamp |
| `filename` | original file name (file imports) |

---

## Adding a new source

1. Create `src/profile_ingestion/sources/your_source.py`
2. Return `list[ProfilePayload]` from a `collect_*` function
3. Call `ingest_profiles(payloads)` from your entry point
4. Register in `sources/registry.py`

---

## Files

```
src/profile_ingestion/
├── models.py           # ProfilePayload, IngestResult
├── service.py          # ingest_profile(s), format_ingest_summary
└── sources/
    ├── slack.py        # Slack messages
    └── file.py         # .txt / .md / .json

scripts/import_profiles.py
data/profile_imports/inbox/   # drop files here
```
