from __future__ import annotations

from types import SimpleNamespace

import pytest

from fde_foundation.embeddings import (
    EMBEDDING_DIMENSIONS,
    DeterministicEmbeddingProvider,
    EmbeddingProviderError,
    OpenAIEmbeddingProvider,
    vector_literal,
)


def test_deterministic_embeddings_are_normalized_stable_and_input_sensitive() -> None:
    provider = DeterministicEmbeddingProvider()
    first, repeated, different = provider.embed(
        ["politica de reembolso", "politica de reembolso", "horario de soporte"]
    )

    assert first == repeated
    assert first != different
    assert len(first) == EMBEDDING_DIMENSIONS
    assert sum(value * value for value in first) == pytest.approx(1.0)


def test_deterministic_embedding_rejects_empty_input() -> None:
    with pytest.raises(EmbeddingProviderError):
        DeterministicEmbeddingProvider().embed(["   "])


class FakeEmbeddings:
    def __init__(self) -> None:
        self.kwargs: dict[str, object] = {}

    def create(self, **kwargs: object) -> SimpleNamespace:
        self.kwargs = kwargs
        vector = [0.0] * EMBEDDING_DIMENSIONS
        return SimpleNamespace(data=[SimpleNamespace(index=0, embedding=vector)])


def test_openai_embedding_adapter_requests_bounded_dimensions() -> None:
    client = SimpleNamespace(embeddings=FakeEmbeddings())
    provider = OpenAIEmbeddingProvider(api_key="not-used", client=client)

    assert provider.embed(["policy"])[0] == [0.0] * EMBEDDING_DIMENSIONS
    assert client.embeddings.kwargs == {
        "model": "text-embedding-3-small",
        "input": ["policy"],
        "dimensions": EMBEDDING_DIMENSIONS,
        "encoding_format": "float",
    }


def test_vector_literal_rejects_wrong_shape_and_nonfinite_values() -> None:
    with pytest.raises(EmbeddingProviderError):
        vector_literal([0.1])
    with pytest.raises(EmbeddingProviderError):
        vector_literal([float("nan")] * EMBEDDING_DIMENSIONS)
