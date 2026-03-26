"""
Workspace tools — Tova as a productivity workhorse.

Enables Tova to create, read, write, analyze, and manage files and documents.
Think of this as giving Tova the ability to work like a human at a desk:
- Create reports, spreadsheets, presentations, code
- Read and analyze uploaded documents
- Generate summaries, extracts, transformations
- Manage a user's file workspace

These tools work with any BaseFileStore implementation (local, S3, GCS, etc.).
"""

from __future__ import annotations

import csv
import io
import json
import logging
import mimetypes
from datetime import datetime
from langchain_core.tools import tool

from tova_core.providers.file_store import BaseFileStore

logger = logging.getLogger(__name__)


def build_workspace_tools(file_store: BaseFileStore) -> list:
    """Build workspace/file productivity tools."""

    @tool
    async def create_file(
        user_id: str,
        file_name: str,
        content: str,
        folder: str = "workspace",
        file_type: str = "auto",
    ) -> dict:
        """Create a new file in the user's workspace.

        Can create ANY type of file: text, code, JSON, CSV, markdown, HTML, etc.
        Use this when the user asks you to write, create, generate, or draft a document.

        Examples:
        - "Write me a report on Q4 sales" → create markdown/text file
        - "Create a spreadsheet of employees" → create CSV file
        - "Generate a Python script that..." → create .py file
        - "Draft a business proposal" → create markdown file
        - "Make me an HTML page" → create .html file

        Args:
            user_id: Owner of the file
            file_name: Name of the file (e.g., "sales_report.md", "data.csv", "script.py")
            content: The file content to write
            folder: Folder path within workspace (default "workspace")
            file_type: auto (detect from extension), text, json, csv, markdown, html, python, javascript
        """
        try:
            # Ensure file has an extension
            if "." not in file_name:
                ext_map = {
                    "text": ".txt", "json": ".json", "csv": ".csv",
                    "markdown": ".md", "html": ".html", "python": ".py",
                    "javascript": ".js", "yaml": ".yaml", "xml": ".xml",
                }
                file_name += ext_map.get(file_type, ".txt")

            path = f"{user_id}/{folder}/{file_name}"
            content_type = mimetypes.guess_type(file_name)[0] or "text/plain"

            await file_store.upload(
                path=path,
                content=content.encode("utf-8"),
                content_type=content_type,
                metadata={
                    "created_by": "tova",
                    "created_at": datetime.now().isoformat(),
                    "file_type": file_type,
                },
            )

            return {
                "success": True,
                "path": path,
                "file_name": file_name,
                "content_type": content_type,
                "size_bytes": len(content.encode("utf-8")),
                "message": f"File '{file_name}' created successfully in {folder}/",
            }
        except Exception as e:
            return {"error": str(e)}

    @tool
    async def write_to_file(
        user_id: str,
        file_path: str,
        content: str,
        mode: str = "overwrite",
    ) -> dict:
        """Write or append content to an existing file.

        Args:
            user_id: File owner
            file_path: Full path to the file (e.g., "user_123/workspace/report.md")
            content: Content to write
            mode: "overwrite" (replace entire file) or "append" (add to end)
        """
        try:
            full_path = file_path
            if not file_path.startswith(user_id):
                full_path = f"{user_id}/{file_path}"

            if mode == "append":
                existing = b""
                try:
                    existing = await file_store.download(full_path)
                except Exception:
                    pass
                final_content = existing + b"\n" + content.encode("utf-8")
            else:
                final_content = content.encode("utf-8")

            content_type = mimetypes.guess_type(full_path)[0] or "text/plain"

            await file_store.upload(
                path=full_path,
                content=final_content,
                content_type=content_type,
                metadata={
                    "updated_by": "tova",
                    "updated_at": datetime.now().isoformat(),
                },
            )

            return {
                "success": True,
                "path": full_path,
                "mode": mode,
                "size_bytes": len(final_content),
            }
        except Exception as e:
            return {"error": str(e)}

    @tool
    async def read_file(
        user_id: str,
        file_path: str,
        max_chars: int = 15000,
    ) -> dict:
        """Read and return the contents of a file.

        Use this to read any file the user has uploaded or created.

        Args:
            user_id: File owner
            file_path: Path to the file
            max_chars: Maximum characters to return (default 15000)
        """
        try:
            full_path = file_path
            if not file_path.startswith(user_id):
                full_path = f"{user_id}/{file_path}"

            content = await file_store.download(full_path)
            content_type = mimetypes.guess_type(full_path)[0] or ""

            # Try Office/PDF document processing first for binary formats
            filename = full_path.split("/")[-1]
            try:
                from tova_core.documents.processor import detect_format, read_document
                fmt = detect_format(filename)
                if fmt in ("docx", "xlsx", "pptx", "pdf"):
                    result = read_document(content, filename)
                    result["path"] = full_path
                    result["size_bytes"] = len(content)
                    return result
            except ImportError:
                pass

            try:
                text = content.decode("utf-8")
                truncated = len(text) > max_chars
                return {
                    "path": full_path,
                    "content": text[:max_chars],
                    "content_type": content_type,
                    "size_bytes": len(content),
                    "truncated": truncated,
                }
            except UnicodeDecodeError:
                return {
                    "path": full_path,
                    "content_type": content_type,
                    "size_bytes": len(content),
                    "binary": True,
                    "note": "Binary file — use read_office_document for Word, Excel, PowerPoint, or PDF files.",
                }
        except Exception as e:
            return {"error": str(e)}

    @tool
    async def analyze_document(
        user_id: str,
        file_path: str,
        analysis_type: str = "summary",
    ) -> dict:
        """Analyze a document and extract structured information.

        Reads the file content and returns it with analysis instructions
        for the LLM to process.

        Args:
            user_id: File owner
            file_path: Path to the file
            analysis_type: What kind of analysis:
                - summary: Executive summary of the document
                - extract: Key facts, figures, and data points
                - compare: Extract data for comparison with other documents
                - action_items: Find action items, tasks, and deadlines
                - financial: Extract financial data, totals, trends
                - contacts: Extract names, emails, phone numbers
                - technical: Extract technical specs, requirements, architecture
        """
        try:
            full_path = file_path
            if not file_path.startswith(user_id):
                full_path = f"{user_id}/{file_path}"

            content = await file_store.download(full_path)
            content_type = mimetypes.guess_type(full_path)[0] or ""

            # Try Office/PDF document extraction for binary files
            filename = full_path.split("/")[-1]
            try:
                from tova_core.documents.processor import detect_format, read_document
                fmt = detect_format(filename)
                if fmt in ("docx", "xlsx", "pptx", "pdf"):
                    doc_data = read_document(content, filename)
                    doc_data["path"] = full_path
                    doc_data["analysis_type"] = analysis_type
                    analysis_prompts = {
                        "summary": "Provide a concise executive summary.",
                        "extract": "Extract all key facts, figures, and data points.",
                        "compare": "Extract all comparable data points in a structured format.",
                        "action_items": "Find all action items, tasks, and deadlines.",
                        "financial": "Extract all financial data: amounts, totals, trends.",
                        "contacts": "Extract all contact information.",
                        "technical": "Extract technical specifications and requirements.",
                    }
                    doc_data["guidance"] = analysis_prompts.get(analysis_type, "Analyze thoroughly.")
                    return doc_data
            except ImportError:
                pass

            try:
                text = content.decode("utf-8")
            except UnicodeDecodeError:
                return {
                    "path": full_path,
                    "content_type": content_type,
                    "note": "Binary file — use read_office_document for Word, Excel, PowerPoint, or PDF files.",
                }

            # For CSV, parse into structured data
            if full_path.endswith(".csv") or "csv" in content_type:
                reader = csv.DictReader(io.StringIO(text))
                rows = list(reader)
                return {
                    "path": full_path,
                    "content_type": "text/csv",
                    "rows": rows[:100],
                    "total_rows": len(rows),
                    "columns": list(rows[0].keys()) if rows else [],
                    "analysis_type": analysis_type,
                    "guidance": f"Analyze this CSV data. Analysis type: {analysis_type}.",
                }

            # For JSON, parse and structure
            if full_path.endswith(".json") or "json" in content_type:
                try:
                    data = json.loads(text)
                    return {
                        "path": full_path,
                        "content_type": "application/json",
                        "data": data if len(text) < 10000 else str(data)[:10000],
                        "analysis_type": analysis_type,
                        "guidance": f"Analyze this JSON data. Analysis type: {analysis_type}.",
                    }
                except json.JSONDecodeError:
                    pass

            analysis_prompts = {
                "summary": "Provide a concise executive summary. Key points, conclusions, and recommendations.",
                "extract": "Extract all key facts, figures, statistics, dates, and named entities.",
                "compare": "Extract all comparable data points (numbers, metrics, categories) in a structured format.",
                "action_items": "Find all action items, tasks, deadlines, and responsibilities mentioned.",
                "financial": "Extract all financial data: amounts, totals, percentages, trends, and projections.",
                "contacts": "Extract all contact information: names, roles, emails, phone numbers, addresses.",
                "technical": "Extract technical specifications, requirements, architecture details, and dependencies.",
            }

            return {
                "path": full_path,
                "content_type": content_type,
                "text": text[:15000],
                "size_bytes": len(content),
                "truncated": len(text) > 15000,
                "analysis_type": analysis_type,
                "guidance": analysis_prompts.get(analysis_type, "Analyze this document thoroughly."),
            }
        except Exception as e:
            return {"error": str(e)}

    @tool
    async def generate_report(
        user_id: str,
        title: str,
        sections: str,
        data_sources: str = "",
        format: str = "markdown",
    ) -> dict:
        """Generate a structured report and save it to the workspace.

        Creates a professional report with the specified sections.
        The LLM fills in the content based on available data and context.

        Args:
            user_id: Report owner
            title: Report title
            sections: Comma-separated section names (e.g., "Executive Summary,Key Findings,Recommendations,Next Steps")
            data_sources: Comma-separated file paths to use as data sources (optional)
            format: Output format: markdown, html, text
        """
        try:
            section_list = [s.strip() for s in sections.split(",") if s.strip()]

            # Load data from sources if provided
            source_data = {}
            if data_sources:
                for src in data_sources.split(","):
                    src = src.strip()
                    if not src:
                        continue
                    try:
                        full_src = src if src.startswith(user_id) else f"{user_id}/{src}"
                        content = await file_store.download(full_src)
                        source_data[src] = content.decode("utf-8")[:5000]
                    except Exception:
                        source_data[src] = "[Could not load]"

            ext = {"markdown": ".md", "html": ".html", "text": ".txt"}.get(format, ".md")
            file_name = f"{title.lower().replace(' ', '_')}{ext}"
            path = f"{user_id}/workspace/reports/{file_name}"

            return {
                "title": title,
                "sections": section_list,
                "source_data": source_data,
                "format": format,
                "save_path": path,
                "guidance": (
                    f"Generate a professional report titled '{title}' with these sections: "
                    f"{', '.join(section_list)}. "
                    f"{'Use the provided source data to inform the content. ' if source_data else ''}"
                    f"After generating the content, call create_file to save it to {path}."
                ),
            }
        except Exception as e:
            return {"error": str(e)}

    @tool
    async def generate_spreadsheet(
        user_id: str,
        file_name: str,
        columns: str,
        rows: str = "",
        folder: str = "workspace",
    ) -> dict:
        """Generate a CSV spreadsheet file.

        Args:
            user_id: File owner
            file_name: Name for the file (e.g., "employees.csv")
            columns: Comma-separated column headers (e.g., "Name,Email,Department,Role")
            rows: JSON array of row data, or pipe-separated rows
                  e.g., '[{"Name":"Alice","Email":"alice@co.com"}]'
                  or 'Alice|alice@co.com|Engineering|SWE\\nBob|bob@co.com|Sales|AE'
            folder: Destination folder (default "workspace")
        """
        try:
            if not file_name.endswith(".csv"):
                file_name += ".csv"

            col_list = [c.strip() for c in columns.split(",")]

            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(col_list)

            if rows:
                try:
                    row_data = json.loads(rows)
                    if isinstance(row_data, list):
                        for row in row_data:
                            if isinstance(row, dict):
                                writer.writerow([row.get(c, "") for c in col_list])
                            elif isinstance(row, list):
                                writer.writerow(row)
                except (json.JSONDecodeError, TypeError):
                    for line in rows.split("\\n"):
                        if "|" in line:
                            writer.writerow([v.strip() for v in line.split("|")])
                        elif "," in line:
                            writer.writerow([v.strip() for v in line.split(",")])

            csv_content = output.getvalue()
            path = f"{user_id}/{folder}/{file_name}"

            await file_store.upload(
                path=path,
                content=csv_content.encode("utf-8"),
                content_type="text/csv",
                metadata={
                    "created_by": "tova",
                    "created_at": datetime.now().isoformat(),
                    "columns": col_list,
                },
            )

            return {
                "success": True,
                "path": path,
                "file_name": file_name,
                "columns": col_list,
                "content_type": "text/csv",
                "size_bytes": len(csv_content),
            }
        except Exception as e:
            return {"error": str(e)}

    @tool
    async def delete_file(
        user_id: str,
        file_path: str,
    ) -> dict:
        """Delete a file from the user's workspace.

        Args:
            user_id: File owner
            file_path: Path to the file to delete
        """
        try:
            full_path = file_path
            if not file_path.startswith(user_id):
                full_path = f"{user_id}/{file_path}"

            await file_store.delete(full_path)
            return {"success": True, "deleted": full_path}
        except Exception as e:
            return {"error": str(e)}

    @tool
    async def search_files(
        user_id: str,
        query: str,
        folder: str = "",
        file_type: str = "",
    ) -> dict:
        """Search through the user's files by name or content type.

        Args:
            user_id: File owner
            query: Search query (matches file names)
            folder: Limit search to a specific folder (optional)
            file_type: Filter by type: document, spreadsheet, image, code, data (optional)
        """
        try:
            prefix = f"{user_id}/{folder}" if folder else f"{user_id}/"
            all_files = await file_store.list_files(prefix=prefix, limit=200)

            type_extensions = {
                "document": [".md", ".txt", ".doc", ".docx", ".pdf", ".rtf"],
                "spreadsheet": [".csv", ".xlsx", ".xls", ".tsv"],
                "image": [".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"],
                "code": [".py", ".js", ".ts", ".go", ".java", ".rs", ".cpp", ".html", ".css"],
                "data": [".json", ".xml", ".yaml", ".yml", ".csv", ".sql"],
            }

            matches = []
            for f in all_files:
                path = f.get("path", "")
                name = path.split("/")[-1].lower()

                if query.lower() not in name and query.lower() not in path.lower():
                    continue

                if file_type and file_type in type_extensions:
                    if not any(name.endswith(ext) for ext in type_extensions[file_type]):
                        continue

                matches.append({
                    "path": path,
                    "name": path.split("/")[-1],
                    "size": f.get("size", 0),
                    "content_type": f.get("content_type", ""),
                    "created_at": f.get("created_at", ""),
                })

            return {
                "matches": matches,
                "count": len(matches),
                "query": query,
            }
        except Exception as e:
            return {"error": str(e)}

    return [
        create_file,
        write_to_file,
        read_file,
        analyze_document,
        generate_report,
        generate_spreadsheet,
        delete_file,
        search_files,
    ]
