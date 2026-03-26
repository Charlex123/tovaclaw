"""
Vector similarity retriever for RAG queries.

Searches the vector store and returns the most relevant chunks
for a given query, optionally with reranking.
"""

from __future__ import annotations

import logging
from typing import Any

from tova_core.rag.embedder import Embedder
from tova_core.providers.vector_store import BaseVectorStore

logger = logging.getLogger(__name__)


class Retriever:
    """Retrieves relevant document chunks via vector similarity search.

    Usage:
        retriever = Retriever(vector_store, embedder)
        results = await retriever.query(
            collection_name="ds_user123_dataset456",
            query="What are the key findings?",
            top_k=5,
        )
    """

    def __init__(
        self,
        vector_store: BaseVectorStore,
        embedder: Embedder,
    ):
        self.vector_store = vector_store
        self.embedder = embedder

    async def query(
        self,
        collection_name: str,
        query: str,
        top_k: int = 5,
        filter_metadata: dict[str, Any] | None = None,
        min_score: float = 0.0,
    ) -> list[dict]:
        """Search for relevant chunks.

        Args:
            collection_name: Vector collection to search
            query: Natural language query
            top_k: Maximum number of results
            filter_metadata: Optional metadata filters
            min_score: Minimum similarity score threshold (0.0 to 1.0)

        Returns:
            List of dicts: [{text, score, metadata, id}] sorted by relevance
        """
        # Generate query embedding
        query_embedding = await self.embedder.embed_text(query)

        if not query_embedding:
            logger.warning("Empty query embedding generated")
            return []

        # Vector similarity search
        results = await self.vector_store.query(
            collection_name=collection_name,
            query_embedding=query_embedding,
            top_k=top_k,
            filter_metadata=filter_metadata,
        )

        # Apply minimum score filter
        if min_score > 0:
            results = [r for r in results if r.get("score", 0) >= min_score]

        return results

    async def query_with_context(
        self,
        collection_name: str,
        query: str,
        top_k: int = 5,
        filter_metadata: dict[str, Any] | None = None,
    ) -> str:
        """Search and format results as a context string for LLM injection.

        Returns a formatted string like:
            ## Relevant Context from Dataset
            [Source: report.pdf, Relevance: 0.92]
            The key findings indicate that...

            [Source: data.csv, Relevance: 0.87]
            Revenue grew by 15% in Q3...
        """
        results = await self.query(
            collection_name=collection_name,
            query=query,
            top_k=top_k,
            filter_metadata=filter_metadata,
        )

        if not results:
            return ""

        lines = ["## Relevant Context from Dataset"]
        for r in results:
            source = r.get("metadata", {}).get("source", "unknown")
            score = r.get("score", 0)
            text = r.get("text", "")
            lines.append(f"\n[Source: {source}, Relevance: {score:.2f}]")
            lines.append(text)

        return "\n".join(lines)
