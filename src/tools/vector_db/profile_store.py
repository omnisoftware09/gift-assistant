"""ChromaDB profile storage with chunked embeddings and timestamps."""

import logging
import time
import uuid
from dataclasses import dataclass

from langchain_chroma import Chroma
from langchain_core.documents import Document

from src.langchain_core.embeddings import get_embeddings
from src.langchain_core.observability import trace_tool
from src.langchain_core.settings import get_chroma_settings
from src.tools.vector_db.chunker import chunk_text

logger = logging.getLogger("gift_assistant.chroma")


@dataclass
class ProfileMatch:
    text: str
    distance: float
    closeness: float  # 0-100 relative score within this retrieval batch
    metadata: dict


class ProfileStore:
    def __init__(self):
        settings = get_chroma_settings()
        self.collection_name = settings["collection"]
        self._store = Chroma(
            collection_name=self.collection_name,
            embedding_function=get_embeddings(),
            persist_directory=settings["persist_dir"],
        )

    @trace_tool("chroma.save_profile")
    def save_profile(
        self,
        recipient: str,
        interests_text: str,
        source: str = "slack",
        source_ref: str = "",
        extra_metadata: dict | None = None,
    ) -> int:
        """Chunk and save profile. Returns number of chunks stored."""
        name = recipient.strip().title()
        chunks = chunk_text(interests_text)
        if not chunks:
            return 0

        now = time.time()
        docs = []
        for i, chunk in enumerate(chunks):
            metadata = {
                "recipient": name.lower(),
                "created_at": now,
                "chunk_index": i,
                "source": source,
                "doc_id": str(uuid.uuid4()),
            }
            if source_ref:
                metadata["source_ref"] = source_ref
            if extra_metadata:
                for key, value in extra_metadata.items():
                    metadata[key] = value if isinstance(value, (str, int, float, bool)) else str(value)
            docs.append(Document(page_content=chunk, metadata=metadata))

        self._store.add_documents(docs)
        return len(docs)

    @trace_tool("chroma.list_profile")
    def list_profile_chunks(self, recipient: str, *, limit: int = 10) -> list[str]:
        """
        Return stored profile chunks for a recipient — no embedding API call.

        Embeddings are computed once at ingest (save_profile). Use this when the
        recipient is already known (eCards, profile display). Use query_profile
        for semantic ranking (e.g. gift search).
        """
        name = recipient.strip().lower()
        collection = self._store._collection
        batch = collection.get(where={"recipient": name}, limit=limit)
        documents = batch.get("documents") or []
        metadatas = batch.get("metadatas") or []

        if not documents:
            logger.info("ChromaDB list recipient=%s returned 0 chunks", name)
            return []

        # Sort by chunk_index when present for stable ordering
        pairs = list(zip(documents, metadatas, strict=False))
        pairs.sort(key=lambda p: p[1].get("chunk_index", 0) if isinstance(p[1], dict) else 0)

        chunks = [doc for doc, _ in pairs if doc]
        logger.info("ChromaDB list recipient=%s returned %d chunk(s) (no query embed)", name, len(chunks))
        return chunks

    @trace_tool("chroma.query_profile")
    def query_profile(self, recipient: str, query: str | None = None, k: int = 5) -> list[str]:
        """Return relevant profile chunks for a recipient."""
        matches = self.query_profile_with_scores(recipient, query=query, k=k)
        return [match.text for match in matches]

    @trace_tool("chroma.query_profile_scored")
    def query_profile_with_scores(
        self,
        recipient: str,
        query: str | None = None,
        k: int = 5,
    ) -> list[ProfileMatch]:
        """Return profile chunks with Chroma distance / relative closeness scores."""
        name = recipient.strip().lower()
        search_query = query or f"interests and preferences for {recipient}"

        logger.info(
            "ChromaDB query recipient=%s query=%r k=%d collection=%s",
            name,
            search_query,
            k,
            self.collection_name,
        )

        results = self._store.similarity_search_with_score(
            search_query,
            k=k,
            filter={"recipient": name},
        )

        if not results:
            logger.info("ChromaDB query recipient=%s returned 0 chunks", name)
            return []

        distances = [score for _, score in results]
        min_d, max_d = min(distances), max(distances)
        span = max_d - min_d

        matches: list[ProfileMatch] = []
        for doc, distance in results:
            # Lower distance = closer in Chroma; normalize to 0-100 within batch.
            if span > 0:
                closeness = (max_d - distance) / span * 100.0
            else:
                closeness = 100.0

            meta = dict(doc.metadata or {})
            matches.append(
                ProfileMatch(
                    text=doc.page_content,
                    distance=distance,
                    closeness=closeness,
                    metadata=meta,
                )
            )
            logger.info(
                "ChromaDB hit recipient=%s distance=%.4f closeness=%.1f chunk_index=%s "
                "source=%s text=%r",
                name,
                distance,
                closeness,
                meta.get("chunk_index"),
                meta.get("source"),
                doc.page_content[:120],
            )

        logger.info(
            "ChromaDB query recipient=%s returned %d chunk(s) (best distance=%.4f)",
            name,
            len(matches),
            min_d,
        )
        return matches

    @trace_tool("chroma.delete_old_profiles")
    def delete_old_profiles(self, days_old: int = 30) -> int:
        """Delete profile chunks older than days_old. Returns count deleted."""
        cutoff = time.time() - (days_old * 86400)
        collection = self._store._collection
        batch = collection.get(where={"created_at": {"$lt": cutoff}})
        ids = batch.get("ids") or []
        if ids:
            collection.delete(ids=ids)
        return len(ids)

    @trace_tool("chroma.delete_recipient")
    def delete_recipient(self, recipient: str) -> int:
        """Delete all chunks for a recipient."""
        name = recipient.strip().lower()
        collection = self._store._collection
        batch = collection.get(where={"recipient": name})
        ids = batch.get("ids") or []
        if ids:
            collection.delete(ids=ids)
        return len(ids)


_store: ProfileStore | None = None


def get_profile_store() -> ProfileStore:
    global _store
    if _store is None:
        _store = ProfileStore()
    return _store
