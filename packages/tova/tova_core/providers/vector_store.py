"""
Abstract vector store interface for RAG / dataset training.

Implement this class to connect Tova to your vector database.
Supports any vector DB: ChromaDB, Pinecone, Qdrant, Weaviate, pgvector, etc.
"""

from abc import ABC, abstractmethod


class BaseVectorStore(ABC):
    """Vector database provider for embedding storage and similarity search.

    Collection naming convention: ds_{user_id}_{dataset_id}
    This ensures per-user, per-dataset isolation.
    """

    @abstractmethod
    async def create_collection(
        self,
        collection_name: str,
        dimension: int = 1536,
    ) -> None:
        """Create a new vector collection.

        Args:
            collection_name: Unique collection identifier
            dimension: Embedding vector dimension (1536 for OpenAI, 768 for many local models)
        """
        ...

    @abstractmethod
    async def upsert(
        self,
        collection_name: str,
        documents: list[dict],
    ) -> int:
        """Insert or update documents with embeddings.

        Args:
            collection_name: Target collection
            documents: List of dicts, each with:
                - id: Document/chunk unique ID
                - text: The original text content
                - embedding: list[float] — the embedding vector
                - metadata: dict — optional metadata (source_file, chunk_index, etc.)

        Returns:
            Number of documents upserted
        """
        ...

    @abstractmethod
    async def query(
        self,
        collection_name: str,
        query_embedding: list[float],
        top_k: int = 5,
        filter_metadata: dict | None = None,
    ) -> list[dict]:
        """Search for similar documents by embedding.

        Args:
            collection_name: Collection to search
            query_embedding: The query vector
            top_k: Maximum number of results
            filter_metadata: Optional metadata filters (e.g., {"source": "report.pdf"})

        Returns:
            List of dicts: [{id, text, score, metadata}] sorted by similarity
        """
        ...

    @abstractmethod
    async def delete_collection(self, collection_name: str) -> None:
        """Delete an entire collection and all its documents."""
        ...

    async def delete_documents(
        self,
        collection_name: str,
        document_ids: list[str],
    ) -> int:
        """Delete specific documents from a collection.

        Returns:
            Number of documents deleted
        """
        raise NotImplementedError

    async def count(self, collection_name: str) -> int:
        """Count documents in a collection."""
        raise NotImplementedError
