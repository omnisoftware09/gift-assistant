# LLM Providers & ChromaDB Profiles

How to swap LLM providers and configure profile chunking.

---

## Swappable LLM providers

Set `LLM_PROVIDER` in `.env` — no code changes needed.

| Provider | Env | Model example | API key |
|----------|-----|---------------|---------|
| **OpenAI** | `LLM_PROVIDER=openai` | `gpt-4o-mini` | `OPENAI_API_KEY` |
| **Anthropic** | `LLM_PROVIDER=anthropic` | `claude-3-5-haiku-latest` | `ANTHROPIC_API_KEY` |
| **Ollama** (local) | `LLM_PROVIDER=ollama` | `llama3.2` | none |

### OpenAI (default)

```env
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o-mini
OPENAI_API_KEY=sk-...
```

### Anthropic

```env
LLM_PROVIDER=anthropic
LLM_MODEL=claude-3-5-haiku-latest
ANTHROPIC_API_KEY=sk-ant-...
```

### Ollama (local)

1. Install Ollama: [ollama.com](https://ollama.com)
2. Pull a model:
   ```bash
   ollama pull llama3.2
   ollama pull nomic-embed-text   # for embeddings
   ```
3. Configure `.env`:
   ```env
   LLM_PROVIDER=ollama
   LLM_MODEL=llama3.2
   EMBEDDING_PROVIDER=ollama
   EMBEDDING_MODEL=nomic-embed-text
   OLLAMA_BASE_URL=http://localhost:11434
   ```

---

## Embeddings (ChromaDB)

| Provider | Env | Default model |
|----------|-----|---------------|
| OpenAI | `EMBEDDING_PROVIDER=openai` | `text-embedding-3-small` |
| Ollama | `EMBEDDING_PROVIDER=ollama` | `nomic-embed-text` |

```env
EMBEDDING_PROVIDER=openai
EMBEDDING_MODEL=text-embedding-3-small
```

> **Note:** If using Ollama for LLM but OpenAI for embeddings, set providers independently.

---

## Profile chunking

Profiles are split into **1–2 sentence chunks** before storing in ChromaDB.

```env
CHUNK_MIN_SENTENCES=1
CHUNK_MAX_SENTENCES=2
```

Each chunk stores metadata:
| Field | Purpose |
|-------|---------|
| `recipient` | e.g. `sarah` |
| `created_at` | Unix timestamp — used to delete old profiles |
| `chunk_index` | Order within profile |
| `source` | e.g. `slack`, `file`, `slack_file` |
| `source_ref` | file path or Slack message timestamp |

**File import:** see [PROFILE_INGESTION.md](PROFILE_INGESTION.md) for CLI, inbox folder, and Slack uploads.

### Test different chunk sizes

```env
# Larger chunks (3-4 sentences)
CHUNK_MIN_SENTENCES=3
CHUNK_MAX_SENTENCES=4
```

Restart the bot after changing chunk settings.

### Delete old profiles

In Slack:
```
delete old profiles
clean up profiles
```

Or via tool: deletes chunks older than 30 days (configurable in agent).

---

## Agent patterns

| Agent | Pattern | LLM needed? |
|-------|---------|-------------|
| Orchestrator | Keyword router | No |
| Event Monitor | Rules + Calendar API | No |
| Proactive worker | Rules | No |
| **Profile Collector** | **ReAct** (LangGraph) + rule fallback | Optional* |
| Gift Recommender | LangGraph (stub — search/evaluate/rank) | Yes (future) |
| eCard Generator | ReAct (stub) | Yes (future) |

\* Profile Collector uses **rule-based parsing first** (no LLM) for messages like:
- `Sarah likes hiking and coffee`
- `What does Sarah like?`

Falls back to ReAct agent for complex messages.

---

## Test in Slack

### Save a profile (no LLM required)
```
Sarah likes hiking, coffee, and photography
```

### Query a profile
```
What does Sarah like?
```

### Gift recommendation (uses profile from Chroma)
```
recommend gift for Sarah's graduation
```

### Swap to Ollama
1. Change `.env` to `LLM_PROVIDER=ollama`
2. Restart bot
3. Send a complex profile message that needs ReAct

---

## Files

```
src/langchain_core/
├── settings.py      # YAML + env config
├── llm.py           # get_chat_model()
└── embeddings.py    # get_embeddings()

src/tools/vector_db/
├── chunker.py       # 1-2 sentence splitting
├── profile_store.py # ChromaDB save/query/delete
└── tools.py         # LangChain tools for ReAct

src/agents/subagents/profile_collector/
├── agent.py         # ReAct + rule fallback
└── parser.py        # Pattern detection
```

---

## Troubleshooting

### Ollama connection refused
```bash
ollama serve   # or open Ollama app
curl http://localhost:11434/api/tags
```

### OpenAI embedding error with Ollama LLM
Set `EMBEDDING_PROVIDER=openai` if only testing Ollama for chat.

### Profile not found in gift recommendations
Save profile first: `Sarah likes hiking and coffee`

### Chroma errors after chunk size change
Old chunks remain valid. To reset:
```bash
rm -rf data/chroma
```
