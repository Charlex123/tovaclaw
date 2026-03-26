"""
Embedding generation for RAG.

Supports multiple embedding providers: OpenAI, Google, Cohere, local sentence-transformers.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class Embedder:
    """Multi-provider embedding generator.

    Usage:
        embedder = Embedder(provider="openai", api_key="sk-...")
        vectors = await embedder.embed_texts(["hello world", "how are you"])
    """

    def __init__(
        self,
        provider: str = "openai",
        model: str = "",
        api_key: str = "",
        base_url: str = "",
    ):
        self.provider = provider
        self.model = model or self._default_model(provider)
        self.api_key = api_key
        self.base_url = base_url
        self._client: Any = None

    @staticmethod
    def _default_model(provider: str) -> str:
        defaults = {
            "openai": "text-embedding-3-small",
            "google": "models/text-embedding-004",
            "cohere": "embed-english-v3.0",
            "local": "all-MiniLM-L6-v2",
        }
        return defaults.get(provider, "text-embedding-3-small")

    @property
    def dimension(self) -> int:
        """Get the embedding dimension for the current model."""
        dimensions = {
            "text-embedding-3-small": 1536,
            "text-embedding-3-large": 3072,
            "text-embedding-ada-002": 1536,
            "models/text-embedding-004": 768,
            "embed-english-v3.0": 1024,
            "all-MiniLM-L6-v2": 384,
            "all-mpnet-base-v2": 768,
        }
        return dimensions.get(self.model, 1536)

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a list of texts.

        Args:
            texts: List of text strings to embed

        Returns:
            List of embedding vectors (list of floats)
        """
        if not texts:
            return []

        if self.provider == "openai":
            return await self._embed_openai(texts)
        elif self.provider == "google":
            return await self._embed_google(texts)
        elif self.provider == "cohere":
            return await self._embed_cohere(texts)
        elif self.provider == "local":
            return await self._embed_local(texts)
        else:
            raise ValueError(f"Unknown embedding provider: {self.provider}")

    async def embed_text(self, text: str) -> list[float]:
        """Embed a single text string."""
        results = await self.embed_texts([text])
        return results[0] if results else []

    async def _embed_openai(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings using OpenAI API."""
        try:
            from openai import AsyncOpenAI
        except ImportError:
            raise ImportError("Install openai: pip install openai")

        if self._client is None:
            kwargs: dict[str, Any] = {}
            if self.api_key:
                kwargs["api_key"] = self.api_key
            if self.base_url:
                kwargs["base_url"] = self.base_url
            self._client = AsyncOpenAI(**kwargs)

        # Batch in groups of 100 (OpenAI limit)
        all_embeddings = []
        for i in range(0, len(texts), 100):
            batch = texts[i:i + 100]
            response = await self._client.embeddings.create(
                input=batch,
                model=self.model,
            )
            all_embeddings.extend([d.embedding for d in response.data])

        return all_embeddings

    async def _embed_google(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings using Google AI API."""
        try:
            import google.generativeai as genai
        except ImportError:
            raise ImportError("Install google-generativeai: pip install google-generativeai")

        if self.api_key:
            genai.configure(api_key=self.api_key)

        all_embeddings = []
        for text in texts:
            result = genai.embed_content(
                model=self.model,
                content=text,
            )
            all_embeddings.append(result["embedding"])

        return all_embeddings

    async def _embed_cohere(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings using Cohere API."""
        try:
            import cohere
        except ImportError:
            raise ImportError("Install cohere: pip install cohere")

        if self._client is None:
            self._client = cohere.AsyncClient(api_key=self.api_key)

        response = await self._client.embed(
            texts=texts,
            model=self.model,
            input_type="search_document",
        )
        return response.embeddings

    async def _embed_local(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings using local sentence-transformers."""
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError:
            raise ImportError(
                "Install sentence-transformers: pip install sentence-transformers"
            )

        if self._client is None:
            self._client = SentenceTransformer(self.model)

        embeddings = self._client.encode(texts, convert_to_numpy=True)
        return [emb.tolist() for emb in embeddings]
