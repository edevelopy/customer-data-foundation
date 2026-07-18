"""Embedding providers with a deterministic local implementation for reproducible evals."""

from __future__ import annotations

import hashlib
import math
import os
import re
import unicodedata
from collections.abc import Sequence
from itertools import pairwise
from typing import Any, Protocol

from openai import OpenAI, OpenAIError

from fde_foundation.settings import ConfigurationError, read_secret

EMBEDDING_DIMENSIONS = 256
TOKEN_PATTERN = re.compile(r"[a-z0-9]+", re.IGNORECASE)


class EmbeddingProviderError(Exception):
    """An embedding provider could not return a valid vector."""


class EmbeddingProvider(Protocol):
    name: str
    model: str
    dimensions: int

    def embed(self, texts: Sequence[str]) -> list[list[float]]: ...


def normalized_tokens(text: str) -> list[str]:
    normalized = unicodedata.normalize("NFKD", text.casefold())
    ascii_text = "".join(
        character for character in normalized if not unicodedata.combining(character)
    )
    return TOKEN_PATTERN.findall(ascii_text)


class DeterministicEmbeddingProvider:
    """Signed hashing vectorizer; deterministic, local, and explicitly not an AI model."""

    name = "deterministic_local"
    model = "signed-token-hash-v1"
    dimensions = EMBEDDING_DIMENSIONS

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return [self._embed_one(text) for text in texts]

    def _embed_one(self, text: str) -> list[float]:
        tokens = normalized_tokens(text)
        if not tokens:
            raise EmbeddingProviderError
        vector = [0.0] * self.dimensions
        features = tokens + [f"{left}_{right}" for left, right in pairwise(tokens)]
        for feature in features:
            digest = hashlib.sha256(feature.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimensions
            sign = 1.0 if digest[4] & 1 else -1.0
            vector[index] += sign
        magnitude = math.sqrt(sum(value * value for value in vector))
        if magnitude == 0:
            raise EmbeddingProviderError
        return [value / magnitude for value in vector]


class OpenAIEmbeddingProvider:
    name = "openai"

    def __init__(
        self,
        *,
        api_key: str,
        model: str = "text-embedding-3-small",
        dimensions: int = EMBEDDING_DIMENSIONS,
        timeout_seconds: float = 30,
        max_retries: int = 2,
        client: Any | None = None,
    ) -> None:
        if dimensions != EMBEDDING_DIMENSIONS:
            raise ValueError("Embedding dimensions must match the database contract.")
        self.model = model
        self.dimensions = dimensions
        self.client = client or OpenAI(
            api_key=api_key,
            timeout=timeout_seconds,
            max_retries=max_retries,
        )

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts or any(not text.strip() for text in texts):
            raise EmbeddingProviderError
        try:
            response = self.client.embeddings.create(
                model=self.model,
                input=list(texts),
                dimensions=self.dimensions,
                encoding_format="float",
            )
        except OpenAIError as error:
            raise EmbeddingProviderError from error
        ordered = sorted(response.data, key=lambda item: item.index)
        vectors = [list(item.embedding) for item in ordered]
        if len(vectors) != len(texts) or any(len(vector) != self.dimensions for vector in vectors):
            raise EmbeddingProviderError
        return vectors


def vector_literal(vector: Sequence[float]) -> str:
    if len(vector) != EMBEDDING_DIMENSIONS or any(not math.isfinite(value) for value in vector):
        raise EmbeddingProviderError
    return "[" + ",".join(f"{value:.10f}" for value in vector) + "]"


def embedding_provider_from_environment() -> EmbeddingProvider:
    app_env = os.environ.get("APP_ENV", "production").casefold()
    default_provider = "deterministic_local" if app_env in {"development", "test"} else "openai"
    provider_name = os.environ.get("EMBEDDING_PROVIDER", default_provider).casefold()
    try:
        dimensions = int(os.environ.get("EMBEDDING_DIMENSIONS", str(EMBEDDING_DIMENSIONS)))
    except ValueError as error:
        raise ConfigurationError from error
    if dimensions != EMBEDDING_DIMENSIONS:
        raise ConfigurationError
    if provider_name == "deterministic_local":
        if app_env not in {"development", "test"}:
            raise ConfigurationError
        return DeterministicEmbeddingProvider()
    if provider_name != "openai":
        raise ConfigurationError
    return OpenAIEmbeddingProvider(
        api_key=read_secret("OPENAI_API_KEY", minimum_length=20),
        model=os.environ.get("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"),
        dimensions=dimensions,
        timeout_seconds=float(os.environ.get("OPENAI_TIMEOUT_SECONDS", "30")),
        max_retries=int(os.environ.get("OPENAI_MAX_RETRIES", "2")),
    )
