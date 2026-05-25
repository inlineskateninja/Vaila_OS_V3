from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.memory.embedding_provider import EmbeddingProvider, NullEmbeddingProvider
from app.memory.vector_backend import VectorMemoryBackend, NullVectorMemoryBackend
from app.memory.config import DEFAULT_CONFIG

def test_embedding_interface_and_null_provider() -> None:
    provider = NullEmbeddingProvider()
    assert isinstance(provider, EmbeddingProvider)
    assert provider.provider_name() == "none"
    assert provider.dimensions() == 0
    assert provider.embed_text("test") == []
    assert provider.embed_many(["test1", "test2"]) == [[], []]

def test_vector_backend_interface_and_null_backend() -> None:
    backend = NullVectorMemoryBackend()
    assert isinstance(backend, VectorMemoryBackend)
    
    # Check no-op runs without exceptions
    backend.upsert_memory("mem1", "text", {"tag": "val"})
    backend.delete_memory("mem1")
    
    # Check search returns empty list
    results = backend.search([], filters=None, limit=5)
    assert results == []
    
    # Check health reports disabled state
    health = backend.health()
    assert health["status"] == "disabled"
    assert health["backend"] == "none"
    assert health["connected"] is False

def test_config_includes_default_vector_and_embedding_keys() -> None:
    assert DEFAULT_CONFIG["embedding_provider"] == "none"
    assert DEFAULT_CONFIG["embedding_model"] == ""
    assert DEFAULT_CONFIG["embedding_dimensions"] == 0
    assert DEFAULT_CONFIG["vector_backend"] == "none"
