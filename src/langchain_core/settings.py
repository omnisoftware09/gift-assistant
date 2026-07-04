"""Load LangChain config from YAML with env overrides."""

import os
from functools import lru_cache
from pathlib import Path

import yaml

CONFIG_PATH = Path(os.getenv("LANGCHAIN_CONFIG", "config/langchain.yaml"))


@lru_cache
def load_settings() -> dict:
    if not CONFIG_PATH.exists():
        return {}
    return yaml.safe_load(CONFIG_PATH.read_text()) or {}


def get_llm_settings() -> dict:
    cfg = load_settings().get("llm", {})
    return {
        "provider": os.getenv("LLM_PROVIDER", cfg.get("provider", "openai")).lower(),
        "model": os.getenv("LLM_MODEL", cfg.get("model", "gpt-4o-mini")),
        "temperature": float(os.getenv("LLM_TEMPERATURE", cfg.get("temperature", 0.2))),
        "base_url": os.getenv("OLLAMA_BASE_URL", cfg.get("base_url", "http://localhost:11434")),
    }


def get_embedding_settings() -> dict:
    cfg = load_settings().get("embeddings", {})
    chunk = cfg.get("chunk", {})
    return {
        "provider": os.getenv("EMBEDDING_PROVIDER", cfg.get("provider", "openai")).lower(),
        "model": os.getenv(
            "EMBEDDING_MODEL", cfg.get("model", "text-embedding-3-small")
        ),
        "min_sentences": int(os.getenv("CHUNK_MIN_SENTENCES", chunk.get("min_sentences", 1))),
        "max_sentences": int(os.getenv("CHUNK_MAX_SENTENCES", chunk.get("max_sentences", 2))),
        "base_url": os.getenv("OLLAMA_BASE_URL", cfg.get("base_url", "http://localhost:11434")),
    }


def get_chroma_settings() -> dict:
    cfg = load_settings().get("chroma", {})
    return {
        "persist_dir": os.getenv("CHROMA_PERSIST_DIR", cfg.get("persist_dir", "data/chroma")),
        "collection": os.getenv(
            "CHROMA_COLLECTION_PROFILES", cfg.get("collection_profiles", "recipient_profiles")
        ),
    }


def get_profile_import_settings() -> dict:
    cfg = load_settings().get("profile_import", {})
    return {
        "inbox_dir": os.getenv(
            "PROFILE_IMPORT_DIR", cfg.get("inbox_dir", "data/profile_imports/inbox")
        ),
    }
