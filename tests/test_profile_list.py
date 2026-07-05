from unittest.mock import MagicMock, patch

from src.tools.vector_db.profile_store import ProfileStore


@patch.object(ProfileStore, "__init__", lambda self: None)
def test_list_profile_chunks_no_similarity_search():
    store = ProfileStore()
    store._store = MagicMock()
    collection = store._store._collection
    collection.get.return_value = {
        "documents": ["Likes art", "Enjoys hiking"],
        "metadatas": [{"chunk_index": 1}, {"chunk_index": 0}],
    }

    chunks = store.list_profile_chunks("Sarah")

    collection.get.assert_called_once_with(where={"recipient": "sarah"}, limit=10)
    store._store.similarity_search_with_score.assert_not_called()
    assert chunks == ["Enjoys hiking", "Likes art"]
