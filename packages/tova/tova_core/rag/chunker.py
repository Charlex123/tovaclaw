"""
Text chunking strategies for RAG ingestion.

Breaks documents into smaller chunks suitable for embedding and retrieval.
Supports different strategies for different data types.
"""

from __future__ import annotations

import csv
import io
import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


def chunk_text(
    text: str,
    chunk_size: int = 512,
    chunk_overlap: int = 50,
    metadata: dict[str, Any] | None = None,
) -> list[dict]:
    """Split plain text into overlapping chunks.

    Uses recursive character splitting with paragraph/sentence boundaries.

    Returns:
        List of dicts: [{text, chunk_index, metadata}]
    """
    if not text.strip():
        return []

    chunks = []
    # Try to split on paragraph boundaries first
    paragraphs = text.split("\n\n")

    current_chunk = ""
    chunk_index = 0

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        if len(current_chunk) + len(para) + 2 <= chunk_size:
            current_chunk = f"{current_chunk}\n\n{para}" if current_chunk else para
        else:
            if current_chunk:
                chunks.append({
                    "text": current_chunk.strip(),
                    "chunk_index": chunk_index,
                    "metadata": {**(metadata or {}), "chunk_type": "text"},
                })
                chunk_index += 1
                # Keep overlap from end of previous chunk
                if chunk_overlap > 0 and len(current_chunk) > chunk_overlap:
                    current_chunk = current_chunk[-chunk_overlap:] + "\n\n" + para
                else:
                    current_chunk = para
            else:
                # Paragraph itself is larger than chunk_size, split by sentences
                sentences = _split_sentences(para)
                for sent in sentences:
                    if len(current_chunk) + len(sent) + 1 <= chunk_size:
                        current_chunk = f"{current_chunk} {sent}" if current_chunk else sent
                    else:
                        if current_chunk:
                            chunks.append({
                                "text": current_chunk.strip(),
                                "chunk_index": chunk_index,
                                "metadata": {**(metadata or {}), "chunk_type": "text"},
                            })
                            chunk_index += 1
                        current_chunk = sent

    if current_chunk.strip():
        chunks.append({
            "text": current_chunk.strip(),
            "chunk_index": chunk_index,
            "metadata": {**(metadata or {}), "chunk_type": "text"},
        })

    return chunks


def chunk_json(
    data: Any,
    metadata: dict[str, Any] | None = None,
) -> list[dict]:
    """Chunk JSON data — each top-level item becomes a chunk.

    For arrays: each element is a chunk.
    For objects: each key-value pair is a chunk.
    For nested structures: flattened with context.

    Returns:
        List of dicts: [{text, chunk_index, metadata}]
    """
    chunks = []

    if isinstance(data, list):
        for i, item in enumerate(data):
            text = json.dumps(item, indent=2, default=str)
            chunks.append({
                "text": text,
                "chunk_index": i,
                "metadata": {
                    **(metadata or {}),
                    "chunk_type": "json_array_item",
                    "array_index": i,
                },
            })
    elif isinstance(data, dict):
        for i, (key, value) in enumerate(data.items()):
            text = json.dumps({key: value}, indent=2, default=str)
            chunks.append({
                "text": text,
                "chunk_index": i,
                "metadata": {
                    **(metadata or {}),
                    "chunk_type": "json_object_entry",
                    "key": key,
                },
            })
    else:
        chunks.append({
            "text": json.dumps(data, default=str),
            "chunk_index": 0,
            "metadata": {**(metadata or {}), "chunk_type": "json_scalar"},
        })

    return chunks


def chunk_csv(
    content: str,
    metadata: dict[str, Any] | None = None,
    rows_per_chunk: int = 5,
) -> list[dict]:
    """Chunk CSV data — groups of rows become chunks with headers preserved.

    Returns:
        List of dicts: [{text, chunk_index, metadata}]
    """
    chunks = []
    reader = csv.reader(io.StringIO(content))
    rows = list(reader)

    if not rows:
        return []

    headers = rows[0]
    data_rows = rows[1:]

    chunk_index = 0
    for i in range(0, len(data_rows), rows_per_chunk):
        batch = data_rows[i:i + rows_per_chunk]
        # Format as readable text with headers
        lines = []
        for row in batch:
            pairs = [f"{h}: {v}" for h, v in zip(headers, row) if v.strip()]
            lines.append(" | ".join(pairs))

        chunks.append({
            "text": "\n".join(lines),
            "chunk_index": chunk_index,
            "metadata": {
                **(metadata or {}),
                "chunk_type": "csv_rows",
                "headers": headers,
                "row_start": i,
                "row_end": i + len(batch),
            },
        })
        chunk_index += 1

    return chunks


def chunk_xml(
    content: str,
    metadata: dict[str, Any] | None = None,
) -> list[dict]:
    """Chunk XML data — each top-level child element becomes a chunk.

    Returns:
        List of dicts: [{text, chunk_index, metadata}]
    """
    import xml.etree.ElementTree as ET

    chunks = []
    try:
        root = ET.fromstring(content)
        for i, child in enumerate(root):
            text = ET.tostring(child, encoding="unicode", method="xml")
            chunks.append({
                "text": text,
                "chunk_index": i,
                "metadata": {
                    **(metadata or {}),
                    "chunk_type": "xml_element",
                    "tag": child.tag,
                },
            })
    except ET.ParseError as e:
        logger.warning(f"XML parse error, falling back to text chunking: {e}")
        return chunk_text(content, metadata=metadata)

    return chunks if chunks else chunk_text(content, metadata=metadata)


def _split_sentences(text: str) -> list[str]:
    """Simple sentence splitter."""
    sentences = []
    current = ""
    for char in text:
        current += char
        if char in ".!?" and len(current) > 10:
            sentences.append(current.strip())
            current = ""
    if current.strip():
        sentences.append(current.strip())
    return sentences
