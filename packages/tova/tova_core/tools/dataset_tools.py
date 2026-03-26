"""
Dataset / RAG tools — query datasets, list datasets, ingest documents.

These tools allow agents to interact with user-uploaded datasets via RAG.
"""

from __future__ import annotations

import logging
from langchain_core.tools import tool

from tova_core.providers.store import BaseStore
from tova_core.providers.vector_store import BaseVectorStore
from tova_core.rag.embedder import Embedder
from tova_core.rag.retriever import Retriever
from tova_core.rag.ingest import IngestionPipeline

logger = logging.getLogger(__name__)


def build_dataset_tools(
    store: BaseStore,
    vector_store: BaseVectorStore,
    embedder: Embedder,
) -> list:
    """Build RAG/dataset tools using the provider pattern."""

    retriever = Retriever(vector_store, embedder)
    pipeline = IngestionPipeline(vector_store, embedder)

    @tool
    async def query_dataset(
        dataset_id: str,
        query: str,
        top_k: int = 5,
    ) -> dict:
        """Search a dataset with a natural language question. Returns relevant chunks and a synthesized answer.

        Use this when the user asks questions about their uploaded data/documents.

        Args:
            dataset_id: The ID of the dataset to query
            query: Natural language question about the data
            top_k: Number of relevant chunks to retrieve (default 5)
        """
        try:
            dataset = await store.get_dataset(dataset_id)
            if not dataset:
                return {"error": f"Dataset {dataset_id} not found"}

            collection = dataset.get("vector_collection", f"ds_{dataset_id}")
            results = await retriever.query(
                collection_name=collection,
                query=query,
                top_k=top_k,
            )

            return {
                "dataset_name": dataset.get("name", ""),
                "query": query,
                "results": [
                    {
                        "text": r.get("text", ""),
                        "score": r.get("score", 0),
                        "source": r.get("metadata", {}).get("source", ""),
                    }
                    for r in results
                ],
                "result_count": len(results),
            }
        except Exception as e:
            logger.error(f"Dataset query error: {e}")
            return {"error": str(e)}

    @tool
    async def list_datasets(user_id: str) -> dict:
        """List all datasets available to the current user.

        Use this to see what datasets have been uploaded and can be queried.

        Args:
            user_id: The user ID to list datasets for
        """
        try:
            datasets = await store.list_datasets(user_id)
            return {
                "datasets": [
                    {
                        "id": d.get("id", ""),
                        "name": d.get("name", ""),
                        "description": d.get("description", ""),
                        "status": d.get("status", ""),
                        "chunk_count": d.get("chunk_count", 0),
                        "file_count": d.get("file_count", 0),
                    }
                    for d in datasets
                ],
                "count": len(datasets),
            }
        except NotImplementedError:
            return {"datasets": [], "count": 0, "note": "Dataset storage not configured"}
        except Exception as e:
            return {"error": str(e)}

    @tool
    async def ingest_document(
        dataset_id: str,
        content: str,
        content_type: str = "text/plain",
        source_name: str = "inline",
    ) -> dict:
        """Add a new document to an existing dataset for RAG querying.

        Supports: plain text, JSON, CSV, XML content.

        Args:
            dataset_id: The dataset to add the document to
            content: The document content (text, JSON, CSV, etc.)
            content_type: MIME type: text/plain, application/json, text/csv, application/xml
            source_name: A name for this document source
        """
        try:
            dataset = await store.get_dataset(dataset_id)
            if not dataset:
                return {"error": f"Dataset {dataset_id} not found"}

            collection = dataset.get("vector_collection", f"ds_{dataset_id}")
            result = await pipeline.ingest(
                content=content,
                content_type=content_type,
                collection_name=collection,
                source_name=source_name,
            )

            return {
                "success": True,
                "chunks_created": result.get("chunks_created", 0),
                "source": source_name,
                "dataset": dataset.get("name", ""),
            }
        except Exception as e:
            logger.error(f"Document ingestion error: {e}")
            return {"error": str(e)}

    return [query_dataset, list_datasets, ingest_document]
