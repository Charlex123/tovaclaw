"""
ChromaDB vector store — built-in vector database for RAG.

ChromaDB runs embedded (in-process, no server needed) or client-server.
This is the default vector store for standalone Tova deployments.

Usage:
    # Embedded (default, zero config):
    store = ChromaVectorStore()

    # Persistent (survives restarts):
    store = ChromaVectorStore(persist_path="~/.tova/vectordb")

    # Client-server (production):
    store = ChromaVectorStore(host="chromadb.internal", port=8000)

Install: pip install tova[rag]
"""

from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Any

from tova_core.providers.vector_store import BaseVectorStore

logger = logging.getLogger(__name__)


class ChromaVectorStore(BaseVectorStore):
    """ChromaDB-backed vector store for RAG / dataset training.

    Supports three modes:
    - Ephemeral (in-memory, default)
    - Persistent (disk-backed, survives restarts)
    - Client-server (connect to remote ChromaDB)
    """

    def __init__(
        self,
        persist_path: str | None = None,
        host: str | None = None,
        port: int = 8000,
        tenant: str = "default_tenant",
        database: str = "default_database",
    ):
        self._persist_path = persist_path
        self._host = host
        self._port = port
        self._tenant = tenant
        self._database = database
        self._client = None

    def _get_client(self):
        """Lazy-init ChromaDB client."""
        if self._client is not None:
            return self._client

        import chromadb

        if self._host:
            # Client-server mode
            self._client = chromadb.HttpClient(
                host=self._host,
                port=self._port,
                tenant=self._tenant,
                database=self._database,
            )
            logger.info(f"ChromaDB client-server: {self._host}:{self._port}")
        elif self._persist_path:
            # Persistent embedded mode
            path = Path(self._persist_path).expanduser()
            path.mkdir(parents=True, exist_ok=True)
            self._client = chromadb.PersistentClient(
                path=str(path),
                tenant=self._tenant,
                database=self._database,
            )
            logger.info(f"ChromaDB persistent: {path}")
        else:
            # Ephemeral (in-memory)
            self._client = chromadb.EphemeralClient(
                tenant=self._tenant,
                database=self._database,
            )
            logger.info("ChromaDB ephemeral (in-memory)")

        return self._client

    async def create_collection(
        self,
        collection_name: str,
        dimension: int = 1536,
    ) -> None:
        """Create or get a ChromaDB collection."""
        client = self._get_client()
        client.get_or_create_collection(
            name=collection_name,
            metadata={"dimension": dimension, "hnsw:space": "cosine"},
        )
        logger.info(f"Collection '{collection_name}' ready (dim={dimension})")

    async def upsert(
        self,
        collection_name: str,
        documents: list[dict],
    ) -> int:
        """Upsert documents with embeddings into ChromaDB."""
        if not documents:
            return 0

        client = self._get_client()
        collection = client.get_or_create_collection(name=collection_name)

        ids = []
        embeddings = []
        texts = []
        metadatas = []

        for doc in documents:
            doc_id = doc.get("id") or str(uuid.uuid4())
            ids.append(doc_id)
            embeddings.append(doc["embedding"])
            texts.append(doc.get("text", ""))
            meta = doc.get("metadata", {})
            # ChromaDB metadata values must be str, int, float, or bool
            clean_meta = {}
            for k, v in meta.items():
                if isinstance(v, (str, int, float, bool)):
                    clean_meta[k] = v
                elif v is not None:
                    clean_meta[k] = str(v)
            metadatas.append(clean_meta)

        # ChromaDB batch limit is ~5000, chunk if needed
        batch_size = 5000
        for i in range(0, len(ids), batch_size):
            end = i + batch_size
            collection.upsert(
                ids=ids[i:end],
                embeddings=embeddings[i:end],
                documents=texts[i:end],
                metadatas=metadatas[i:end],
            )

        logger.info(f"Upserted {len(ids)} docs into '{collection_name}'")
        return len(ids)

    async def query(
        self,
        collection_name: str,
        query_embedding: list[float],
        top_k: int = 5,
        filter_metadata: dict | None = None,
    ) -> list[dict]:
        """Query ChromaDB for similar documents."""
        client = self._get_client()
        try:
            collection = client.get_collection(name=collection_name)
        except Exception:
            logger.warning(f"Collection '{collection_name}' not found")
            return []

        where = None
        if filter_metadata:
            # Build ChromaDB where filter
            conditions = []
            for k, v in filter_metadata.items():
                conditions.append({k: {"$eq": v}})
            if len(conditions) == 1:
                where = conditions[0]
            elif conditions:
                where = {"$and": conditions}

        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=min(top_k, collection.count() or top_k),
            where=where,
            include=["documents", "metadatas", "distances"],
        )

        output = []
        if results and results["ids"] and results["ids"][0]:
            for i, doc_id in enumerate(results["ids"][0]):
                # ChromaDB returns distances (lower = more similar for cosine)
                # Convert to score (1 - distance for cosine)
                distance = results["distances"][0][i] if results["distances"] else 0
                score = 1.0 - distance

                output.append({
                    "id": doc_id,
                    "text": results["documents"][0][i] if results["documents"] else "",
                    "score": round(score, 4),
                    "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                })

        return output

    async def delete_collection(self, collection_name: str) -> None:
        """Delete a ChromaDB collection."""
        client = self._get_client()
        try:
            client.delete_collection(name=collection_name)
            logger.info(f"Deleted collection '{collection_name}'")
        except Exception as e:
            logger.warning(f"Failed to delete collection '{collection_name}': {e}")

    async def delete_documents(
        self,
        collection_name: str,
        document_ids: list[str],
    ) -> int:
        """Delete specific documents from a collection."""
        client = self._get_client()
        try:
            collection = client.get_collection(name=collection_name)
            collection.delete(ids=document_ids)
            return len(document_ids)
        except Exception as e:
            logger.warning(f"Failed to delete documents: {e}")
            return 0

    async def count(self, collection_name: str) -> int:
        """Count documents in a collection."""
        client = self._get_client()
        try:
            collection = client.get_collection(name=collection_name)
            return collection.count()
        except Exception:
            return 0
