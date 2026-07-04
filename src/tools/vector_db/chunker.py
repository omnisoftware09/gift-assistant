"""Split profile text into 1–2 sentence chunks."""

import re

from src.langchain_core.settings import get_embedding_settings


def split_into_sentences(text: str) -> list[str]:
    text = " ".join(text.strip().split())
    if not text:
        return []
    parts = re.split(r"(?<=[.!?])\s+", text)
    return [part.strip() for part in parts if part.strip()]


def chunk_text(text: str) -> list[str]:
    """
    Chunk text into groups of min_sentences–max_sentences.
    Configurable via CHUNK_MIN_SENTENCES / CHUNK_MAX_SENTENCES env vars.
    """
    settings = get_embedding_settings()
    min_sentences = settings["min_sentences"]
    max_sentences = settings["max_sentences"]

    sentences = split_into_sentences(text)
    if not sentences:
        return []

    # Single blob without sentence punctuation → one chunk
    if len(sentences) == 1 and not re.search(r"[.!?]", text):
        return [text.strip()]

    chunks: list[str] = []
    i = 0
    while i < len(sentences):
        size = max_sentences
        if len(sentences) - i < min_sentences:
            size = len(sentences) - i
        group = sentences[i : i + size]
        chunks.append(" ".join(group))
        i += size

    return chunks
