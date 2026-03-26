"""
Document tools — Microsoft Office & PDF operations for Tova.

Gives the agent the ability to read, create, and edit:
- Word documents (.docx)
- Excel spreadsheets (.xlsx)
- PowerPoint presentations (.pptx)
- PDF documents (.pdf)

Uses tova_core.documents.processor for all heavy lifting.
Works with any BaseFileStore implementation (local, S3, GCS).

Dependencies: pip install "tova[documents]"
"""

from __future__ import annotations

import json
import logging
from datetime import datetime

from langchain_core.tools import tool

from tova_core.providers.file_store import BaseFileStore

logger = logging.getLogger(__name__)

# Content types for Office formats
_CONTENT_TYPES = {
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "pdf": "application/pdf",
}


def build_document_tools(file_store: BaseFileStore) -> list:
    """Build document processing tools for Office & PDF operations."""

    @tool
    async def read_office_document(
        user_id: str,
        file_path: str,
    ) -> dict:
        """Read a Microsoft Office or PDF document and extract its full content.

        Supports: Word (.docx), Excel (.xlsx), PowerPoint (.pptx), PDF (.pdf)

        Extracts all text, tables, headings, slides, sheets, metadata, and structure.
        Use this instead of read_file for Office/PDF documents.

        Args:
            user_id: File owner
            file_path: Path to the document file
        """
        try:
            from tova_core.documents.processor import read_document, detect_format

            full_path = file_path if file_path.startswith(user_id) else f"{user_id}/{file_path}"
            content = await file_store.download(full_path)
            filename = full_path.split("/")[-1]
            fmt = detect_format(filename)

            if fmt == "unknown":
                return {"error": f"Unsupported format: {filename}. Supported: .docx, .xlsx, .pptx, .pdf"}

            result = read_document(content, filename)
            result["path"] = full_path
            result["size_bytes"] = len(content)
            return result

        except ImportError:
            return {"error": "Document processing libraries not installed. Run: pip install 'tova[documents]'"}
        except Exception as e:
            return {"error": str(e)}

    @tool
    async def create_word_document(
        user_id: str,
        file_name: str,
        title: str = "",
        content: str = "",
        sections: str = "",
        tables: str = "",
        folder: str = "workspace",
    ) -> dict:
        """Create a Microsoft Word document (.docx).

        Can create professional documents with headings, paragraphs, and tables.

        Args:
            user_id: File owner
            file_name: Name for the file (e.g., "report.docx")
            title: Document title (Heading 1)
            content: Plain text content (paragraphs separated by newlines)
            sections: JSON array of structured content:
                      [{"text": "Section Title", "style": "Heading 2"},
                       {"text": "Body paragraph text", "style": "Normal"}]
            tables: JSON array of tables:
                    [{"headers": ["Name", "Role"], "rows": [["Alice", "Engineer"]]}]
            folder: Destination folder (default "workspace")
        """
        try:
            from tova_core.documents.processor import create_docx

            if not file_name.endswith(".docx"):
                file_name += ".docx"

            parsed_content = content
            if sections:
                try:
                    parsed_content = json.loads(sections)
                except json.JSONDecodeError:
                    parsed_content = content

            parsed_tables = None
            if tables:
                try:
                    parsed_tables = json.loads(tables)
                except json.JSONDecodeError:
                    pass

            doc_bytes = create_docx(
                title=title,
                content=parsed_content,
                tables=parsed_tables,
            )

            path = f"{user_id}/{folder}/{file_name}"
            await file_store.upload(
                path=path,
                content=doc_bytes,
                content_type=_CONTENT_TYPES["docx"],
                metadata={
                    "created_by": "tova",
                    "created_at": datetime.now().isoformat(),
                    "document_type": "word",
                },
            )

            return {
                "success": True,
                "path": path,
                "file_name": file_name,
                "format": "docx",
                "size_bytes": len(doc_bytes),
                "message": f"Word document '{file_name}' created successfully.",
            }

        except ImportError:
            return {"error": "python-docx not installed. Run: pip install 'tova[documents]'"}
        except Exception as e:
            return {"error": str(e)}

    @tool
    async def create_excel_spreadsheet(
        user_id: str,
        file_name: str,
        sheets: str,
        folder: str = "workspace",
    ) -> dict:
        """Create a Microsoft Excel spreadsheet (.xlsx).

        Creates a professional spreadsheet with styled headers, auto-width columns,
        and multiple sheets.

        Args:
            user_id: File owner
            file_name: Name for the file (e.g., "budget.xlsx")
            sheets: JSON array of sheet definitions:
                    [{"name": "Sheet1", "headers": ["Name", "Amount"],
                      "rows": [["Rent", "1500"], ["Food", "400"]]}]
            folder: Destination folder (default "workspace")
        """
        try:
            from tova_core.documents.processor import create_xlsx

            if not file_name.endswith(".xlsx"):
                file_name += ".xlsx"

            try:
                sheet_defs = json.loads(sheets)
            except json.JSONDecodeError:
                return {"error": "Invalid JSON for sheets parameter. Expected: [{\"name\": ..., \"headers\": [...], \"rows\": [...]}]"}

            doc_bytes = create_xlsx(sheets=sheet_defs)

            path = f"{user_id}/{folder}/{file_name}"
            await file_store.upload(
                path=path,
                content=doc_bytes,
                content_type=_CONTENT_TYPES["xlsx"],
                metadata={
                    "created_by": "tova",
                    "created_at": datetime.now().isoformat(),
                    "document_type": "excel",
                    "sheet_count": len(sheet_defs),
                },
            )

            return {
                "success": True,
                "path": path,
                "file_name": file_name,
                "format": "xlsx",
                "size_bytes": len(doc_bytes),
                "sheet_count": len(sheet_defs),
                "message": f"Excel spreadsheet '{file_name}' created with {len(sheet_defs)} sheet(s).",
            }

        except ImportError:
            return {"error": "openpyxl not installed. Run: pip install 'tova[documents]'"}
        except Exception as e:
            return {"error": str(e)}

    @tool
    async def create_presentation(
        user_id: str,
        file_name: str,
        title: str = "",
        slides: str = "",
        folder: str = "workspace",
    ) -> dict:
        """Create a Microsoft PowerPoint presentation (.pptx).

        Creates a professional presentation with title slide and content slides.

        Args:
            user_id: File owner
            file_name: Name for the file (e.g., "quarterly_review.pptx")
            title: Presentation title (first slide)
            slides: JSON array of slide definitions:
                    [{"title": "Slide Title", "content": ["Bullet 1", "Bullet 2"],
                      "notes": "Speaker notes for this slide"}]
            folder: Destination folder (default "workspace")
        """
        try:
            from tova_core.documents.processor import create_pptx

            if not file_name.endswith(".pptx"):
                file_name += ".pptx"

            parsed_slides = None
            if slides:
                try:
                    parsed_slides = json.loads(slides)
                except json.JSONDecodeError:
                    return {"error": "Invalid JSON for slides parameter."}

            doc_bytes = create_pptx(title=title, slides=parsed_slides)

            path = f"{user_id}/{folder}/{file_name}"
            await file_store.upload(
                path=path,
                content=doc_bytes,
                content_type=_CONTENT_TYPES["pptx"],
                metadata={
                    "created_by": "tova",
                    "created_at": datetime.now().isoformat(),
                    "document_type": "powerpoint",
                    "slide_count": len(parsed_slides or []) + (1 if title else 0),
                },
            )

            slide_count = len(parsed_slides or []) + (1 if title else 0)
            return {
                "success": True,
                "path": path,
                "file_name": file_name,
                "format": "pptx",
                "size_bytes": len(doc_bytes),
                "slide_count": slide_count,
                "message": f"PowerPoint '{file_name}' created with {slide_count} slide(s).",
            }

        except ImportError:
            return {"error": "python-pptx not installed. Run: pip install 'tova[documents]'"}
        except Exception as e:
            return {"error": str(e)}

    @tool
    async def create_pdf_document(
        user_id: str,
        file_name: str,
        title: str = "",
        content: str = "",
        sections: str = "",
        folder: str = "workspace",
    ) -> dict:
        """Create a PDF document.

        Creates a professional PDF with title, body text, and optional sections.

        Args:
            user_id: File owner
            file_name: Name for the file (e.g., "invoice.pdf")
            title: Document title
            content: Plain text content (paragraphs separated by double newlines)
            sections: JSON array of sections:
                      [{"heading": "Introduction", "text": "Body text here..."}]
            folder: Destination folder (default "workspace")
        """
        try:
            from tova_core.documents.processor import create_pdf

            if not file_name.endswith(".pdf"):
                file_name += ".pdf"

            parsed_sections = None
            if sections:
                try:
                    parsed_sections = json.loads(sections)
                except json.JSONDecodeError:
                    pass

            doc_bytes = create_pdf(
                title=title,
                content=content,
                sections=parsed_sections,
            )

            path = f"{user_id}/{folder}/{file_name}"
            await file_store.upload(
                path=path,
                content=doc_bytes,
                content_type=_CONTENT_TYPES["pdf"],
                metadata={
                    "created_by": "tova",
                    "created_at": datetime.now().isoformat(),
                    "document_type": "pdf",
                },
            )

            return {
                "success": True,
                "path": path,
                "file_name": file_name,
                "format": "pdf",
                "size_bytes": len(doc_bytes),
                "message": f"PDF document '{file_name}' created successfully.",
            }

        except ImportError:
            return {"error": "reportlab not installed. Run: pip install 'tova[documents]'"}
        except Exception as e:
            return {"error": str(e)}

    @tool
    async def edit_office_document(
        user_id: str,
        file_path: str,
        edits: str,
    ) -> dict:
        """Edit an existing Office document (Word, Excel, or PowerPoint).

        Reads the file, applies edits, and saves the modified version.

        For Word (.docx) edits:
            [{"action": "replace", "find": "old text", "replace": "new text"},
             {"action": "append", "text": "New paragraph", "style": "Normal"},
             {"action": "delete", "find": "text to remove"}]

        For Excel (.xlsx) edits:
            [{"action": "set_cell", "sheet": "Sheet1", "cell": "A1", "value": "new value"},
             {"action": "set_formula", "sheet": "Sheet1", "cell": "C1", "formula": "=SUM(A1:B1)"},
             {"action": "add_row", "sheet": "Sheet1", "values": ["a", "b", "c"]},
             {"action": "delete_row", "sheet": "Sheet1", "row": 5},
             {"action": "add_sheet", "name": "New Sheet", "headers": ["A", "B"]}]

        For PowerPoint (.pptx) edits:
            [{"action": "edit_slide", "slide": 1, "title": "New Title", "content": ["Bullet"]},
             {"action": "add_slide", "title": "New Slide", "content": ["Point 1"]},
             {"action": "delete_slide", "slide": 3},
             {"action": "replace_text", "find": "old", "replace": "new"}]

        Args:
            user_id: File owner
            file_path: Path to the document to edit
            edits: JSON array of edit operations (format depends on document type)
        """
        try:
            from tova_core.documents.processor import (
                detect_format, edit_docx, edit_xlsx, edit_pptx,
            )

            full_path = file_path if file_path.startswith(user_id) else f"{user_id}/{file_path}"
            filename = full_path.split("/")[-1]
            fmt = detect_format(filename)

            editors = {
                "docx": edit_docx,
                "xlsx": edit_xlsx,
                "pptx": edit_pptx,
            }

            editor = editors.get(fmt)
            if not editor:
                return {"error": f"Cannot edit {fmt} files. Supported: .docx, .xlsx, .pptx"}

            # Download current file
            content = await file_store.download(full_path)

            # Parse edits
            try:
                edit_list = json.loads(edits)
            except json.JSONDecodeError:
                return {"error": "Invalid JSON for edits parameter."}

            # Apply edits
            modified = editor(content, edit_list)

            # Save back
            content_type = _CONTENT_TYPES.get(fmt, "application/octet-stream")
            await file_store.upload(
                path=full_path,
                content=modified,
                content_type=content_type,
                metadata={
                    "edited_by": "tova",
                    "edited_at": datetime.now().isoformat(),
                    "edit_count": len(edit_list),
                },
            )

            return {
                "success": True,
                "path": full_path,
                "format": fmt,
                "edits_applied": len(edit_list),
                "size_bytes": len(modified),
                "message": f"Applied {len(edit_list)} edit(s) to '{filename}'.",
            }

        except ImportError:
            return {"error": "Document processing libraries not installed. Run: pip install 'tova[documents]'"}
        except Exception as e:
            return {"error": str(e)}

    return [
        read_office_document,
        create_word_document,
        create_excel_spreadsheet,
        create_presentation,
        create_pdf_document,
        edit_office_document,
    ]
