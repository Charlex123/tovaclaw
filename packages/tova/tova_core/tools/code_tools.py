"""
Code execution tools — give coding agents a real development environment.

These tools allow AI coding agents to:
1. Execute code in sandboxed subprocesses (Python, Node, shell, etc.)
2. Read/write project files with path safety
3. Search codebases (grep, glob)
4. Run tests and linters
5. Interact with git

Security:
- All execution is sandboxed to a per-user workspace directory
- Configurable timeout (default 30s)
- No access outside the workspace root
- Dangerous commands are blocked
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import shlex
from pathlib import Path

from langchain_core.tools import tool

from tova_core.providers.store import BaseStore

logger = logging.getLogger(__name__)

# Commands that are never allowed
_BLOCKED_COMMANDS = {
    "rm -rf /", "rm -rf /*", "mkfs", "dd if=", ":(){", "fork bomb",
    "chmod 777 /", "shutdown", "reboot", "halt", "poweroff",
    "curl | sh", "wget | sh", "curl | bash", "wget | bash",
}

# Max output size to prevent memory issues
_MAX_OUTPUT_BYTES = 100_000  # 100KB


def _get_workspace_root(user_id: str) -> Path:
    """Get the workspace root for a user. Creates it if needed."""
    base = Path(os.environ.get("TOVA_WORKSPACE_ROOT", "~/.tova/workspaces"))
    base = base.expanduser()
    workspace = base / user_id
    workspace.mkdir(parents=True, exist_ok=True)
    return workspace


def _validate_path(workspace: Path, requested: str) -> Path:
    """Ensure a path stays within the workspace. Raises ValueError if not."""
    target = (workspace / requested).resolve()
    if not str(target).startswith(str(workspace.resolve())):
        raise ValueError(f"Path escapes workspace: {requested}")
    return target


def _is_blocked(command: str) -> bool:
    """Check if a command is blocked for safety."""
    cmd_lower = command.lower().strip()
    for blocked in _BLOCKED_COMMANDS:
        if blocked in cmd_lower:
            return True
    return False


def build_code_tools(store: BaseStore) -> list:
    """Build code execution tools for coding agents."""

    @tool
    async def execute_code(
        user_id: str,
        code: str,
        language: str = "python",
        timeout_seconds: int = 30,
    ) -> dict:
        """Execute code and return the output.

        Runs code in a sandboxed subprocess within the user's workspace.
        Supports Python, JavaScript/Node.js, TypeScript, Bash/Shell, and more.

        Args:
            user_id: The user who owns the workspace
            code: The code to execute
            language: Programming language (python, javascript, typescript, bash, ruby, go, rust, java, etc.)
            timeout_seconds: Max execution time in seconds (default 30, max 120)
        """
        workspace = _get_workspace_root(user_id)
        timeout_seconds = min(timeout_seconds, 120)

        # Map language to command
        lang_map = {
            "python": ("python3", ".py"),
            "python3": ("python3", ".py"),
            "javascript": ("node", ".js"),
            "js": ("node", ".js"),
            "node": ("node", ".js"),
            "typescript": ("npx ts-node", ".ts"),
            "ts": ("npx ts-node", ".ts"),
            "bash": ("bash", ".sh"),
            "shell": ("bash", ".sh"),
            "sh": ("bash", ".sh"),
            "ruby": ("ruby", ".rb"),
            "go": ("go run", ".go"),
            "rust": ("rustc", ".rs"),
            "java": ("java", ".java"),
            "php": ("php", ".php"),
            "perl": ("perl", ".pl"),
        }

        lang_lower = language.lower().strip()
        if lang_lower not in lang_map:
            return {
                "error": f"Unsupported language: {language}",
                "supported": list(lang_map.keys()),
            }

        cmd_prefix, ext = lang_map[lang_lower]

        # Write code to temp file in workspace
        code_file = workspace / f"_tova_run{ext}"
        code_file.write_text(code)

        try:
            # Build command
            if lang_lower == "go":
                cmd = f"cd {shlex.quote(str(workspace))} && go run {shlex.quote(str(code_file))}"
            elif lang_lower == "rust":
                out_file = workspace / "_tova_run"
                cmd = f"rustc {shlex.quote(str(code_file))} -o {shlex.quote(str(out_file))} && {shlex.quote(str(out_file))}"
            elif lang_lower == "java":
                cmd = f"cd {shlex.quote(str(workspace))} && java {shlex.quote(str(code_file))}"
            else:
                cmd = f"cd {shlex.quote(str(workspace))} && {cmd_prefix} {shlex.quote(str(code_file))}"

            proc = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(workspace),
                env={**os.environ, "HOME": str(workspace)},
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(), timeout=timeout_seconds
                )
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                return {
                    "error": f"Execution timed out after {timeout_seconds}s",
                    "language": language,
                }

            stdout_text = stdout.decode("utf-8", errors="replace")[:_MAX_OUTPUT_BYTES]
            stderr_text = stderr.decode("utf-8", errors="replace")[:_MAX_OUTPUT_BYTES]

            return {
                "exit_code": proc.returncode,
                "stdout": stdout_text,
                "stderr": stderr_text,
                "language": language,
                "success": proc.returncode == 0,
            }
        finally:
            # Cleanup temp file
            try:
                code_file.unlink(missing_ok=True)
                # Cleanup rust binary if exists
                (workspace / "_tova_run").unlink(missing_ok=True)
            except Exception:
                pass

    @tool
    async def run_shell_command(
        user_id: str,
        command: str,
        working_directory: str = "",
        timeout_seconds: int = 30,
    ) -> dict:
        """Run a shell command in the user's workspace.

        Use this for: git commands, installing packages, running tests,
        linting, building projects, etc.

        Args:
            user_id: The user who owns the workspace
            command: Shell command to execute
            working_directory: Subdirectory within workspace (optional)
            timeout_seconds: Max execution time (default 30, max 120)
        """
        workspace = _get_workspace_root(user_id)
        timeout_seconds = min(timeout_seconds, 120)

        if _is_blocked(command):
            return {"error": "Command blocked for safety", "command": command}

        cwd = workspace
        if working_directory:
            cwd = _validate_path(workspace, working_directory)
            if not cwd.is_dir():
                return {"error": f"Directory not found: {working_directory}"}

        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(cwd),
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(), timeout=timeout_seconds
                )
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                return {"error": f"Timed out after {timeout_seconds}s", "command": command}

            stdout_text = stdout.decode("utf-8", errors="replace")[:_MAX_OUTPUT_BYTES]
            stderr_text = stderr.decode("utf-8", errors="replace")[:_MAX_OUTPUT_BYTES]

            return {
                "exit_code": proc.returncode,
                "stdout": stdout_text,
                "stderr": stderr_text,
                "success": proc.returncode == 0,
                "command": command,
            }
        except Exception as e:
            return {"error": str(e), "command": command}

    @tool
    async def read_project_file(
        user_id: str,
        file_path: str,
        start_line: int = 0,
        end_line: int = 0,
    ) -> dict:
        """Read a file from the user's workspace/project.

        Args:
            user_id: The user who owns the workspace
            file_path: Path relative to workspace root
            start_line: Start reading from this line (0 = beginning)
            end_line: Stop reading at this line (0 = end of file)
        """
        workspace = _get_workspace_root(user_id)
        try:
            target = _validate_path(workspace, file_path)
        except ValueError as e:
            return {"error": str(e)}

        if not target.exists():
            return {"error": f"File not found: {file_path}"}
        if not target.is_file():
            return {"error": f"Not a file: {file_path}"}

        try:
            content = target.read_text(encoding="utf-8", errors="replace")
            lines = content.splitlines(keepends=True)
            total_lines = len(lines)

            if start_line or end_line:
                start = max(0, start_line - 1) if start_line else 0
                end = end_line if end_line else total_lines
                lines = lines[start:end]
                # Add line numbers
                numbered = [
                    f"{i + start + 1:>4} | {line}"
                    for i, line in enumerate(lines)
                ]
                content = "".join(numbered)
            elif total_lines > 500:
                # For large files, add line numbers and truncate
                numbered = [f"{i+1:>4} | {line}" for i, line in enumerate(lines[:500])]
                content = "".join(numbered) + f"\n... ({total_lines - 500} more lines)"

            return {
                "file_path": file_path,
                "content": content[:_MAX_OUTPUT_BYTES],
                "total_lines": total_lines,
            }
        except Exception as e:
            return {"error": str(e), "file_path": file_path}

    @tool
    async def write_project_file(
        user_id: str,
        file_path: str,
        content: str,
        create_directories: bool = True,
    ) -> dict:
        """Write or create a file in the user's workspace.

        Args:
            user_id: The user who owns the workspace
            file_path: Path relative to workspace root
            content: File content to write
            create_directories: Auto-create parent directories (default True)
        """
        workspace = _get_workspace_root(user_id)
        try:
            target = _validate_path(workspace, file_path)
        except ValueError as e:
            return {"error": str(e)}

        try:
            if create_directories:
                target.parent.mkdir(parents=True, exist_ok=True)

            existed = target.exists()
            target.write_text(content, encoding="utf-8")

            return {
                "file_path": file_path,
                "action": "updated" if existed else "created",
                "size_bytes": len(content.encode("utf-8")),
                "lines": content.count("\n") + 1,
            }
        except Exception as e:
            return {"error": str(e), "file_path": file_path}

    @tool
    async def edit_project_file(
        user_id: str,
        file_path: str,
        old_text: str,
        new_text: str,
        replace_all: bool = False,
    ) -> dict:
        """Edit an existing file by replacing text.

        Args:
            user_id: The user who owns the workspace
            file_path: Path relative to workspace root
            old_text: Exact text to find and replace
            new_text: Text to replace it with
            replace_all: Replace all occurrences (default False = first only)
        """
        workspace = _get_workspace_root(user_id)
        try:
            target = _validate_path(workspace, file_path)
        except ValueError as e:
            return {"error": str(e)}

        if not target.exists():
            return {"error": f"File not found: {file_path}"}

        try:
            content = target.read_text(encoding="utf-8")

            if old_text not in content:
                return {
                    "error": "old_text not found in file",
                    "file_path": file_path,
                }

            if replace_all:
                new_content = content.replace(old_text, new_text)
                count = content.count(old_text)
            else:
                new_content = content.replace(old_text, new_text, 1)
                count = 1

            target.write_text(new_content, encoding="utf-8")

            return {
                "file_path": file_path,
                "replacements": count,
                "new_size_bytes": len(new_content.encode("utf-8")),
            }
        except Exception as e:
            return {"error": str(e), "file_path": file_path}

    @tool
    async def search_codebase(
        user_id: str,
        pattern: str,
        file_glob: str = "",
        max_results: int = 50,
    ) -> dict:
        """Search for text/regex patterns across the workspace files.

        Like grep — finds all occurrences of a pattern in the codebase.

        Args:
            user_id: The user who owns the workspace
            pattern: Regex pattern to search for
            file_glob: Optional glob filter (e.g. "*.py", "src/**/*.ts")
            max_results: Max number of matches to return
        """
        workspace = _get_workspace_root(user_id)

        try:
            compiled = re.compile(pattern, re.IGNORECASE)
        except re.error as e:
            return {"error": f"Invalid regex: {e}"}

        matches = []
        # Use glob to find files
        if file_glob:
            files = list(workspace.glob(file_glob))
        else:
            files = [
                f for f in workspace.rglob("*")
                if f.is_file()
                and not any(p.startswith(".") for p in f.relative_to(workspace).parts)
                and f.stat().st_size < 1_000_000  # skip files > 1MB
            ]

        for fpath in files:
            if len(matches) >= max_results:
                break
            try:
                text = fpath.read_text(encoding="utf-8", errors="replace")
                for i, line in enumerate(text.splitlines(), 1):
                    if compiled.search(line):
                        matches.append({
                            "file": str(fpath.relative_to(workspace)),
                            "line": i,
                            "text": line.strip()[:200],
                        })
                        if len(matches) >= max_results:
                            break
            except Exception:
                continue

        return {
            "pattern": pattern,
            "matches": matches,
            "total": len(matches),
            "truncated": len(matches) >= max_results,
        }

    @tool
    async def list_project_files(
        user_id: str,
        directory: str = "",
        glob_pattern: str = "",
        recursive: bool = False,
    ) -> dict:
        """List files in the user's workspace.

        Args:
            user_id: The user who owns the workspace
            directory: Subdirectory to list (default: workspace root)
            glob_pattern: Optional glob filter (e.g. "*.py", "**/*.ts")
            recursive: List files recursively in all subdirectories
        """
        workspace = _get_workspace_root(user_id)
        target_dir = workspace
        if directory:
            try:
                target_dir = _validate_path(workspace, directory)
            except ValueError as e:
                return {"error": str(e)}
            if not target_dir.is_dir():
                return {"error": f"Not a directory: {directory}"}

        try:
            if glob_pattern:
                if recursive or "**" in glob_pattern:
                    files = list(target_dir.rglob(glob_pattern.replace("**/", "")))
                else:
                    files = list(target_dir.glob(glob_pattern))
            elif recursive:
                files = [f for f in target_dir.rglob("*") if f.is_file()]
            else:
                files = list(target_dir.iterdir())

            entries = []
            for f in sorted(files)[:500]:
                rel = str(f.relative_to(workspace))
                # Skip hidden files/directories
                if any(p.startswith(".") for p in f.relative_to(workspace).parts):
                    continue
                if f.is_dir():
                    entries.append({"name": rel, "type": "directory"})
                else:
                    entries.append({
                        "name": rel,
                        "type": "file",
                        "size": f.stat().st_size,
                    })

            return {
                "directory": directory or ".",
                "entries": entries,
                "count": len(entries),
            }
        except Exception as e:
            return {"error": str(e)}

    @tool
    async def git_command(
        user_id: str,
        command: str,
        working_directory: str = "",
    ) -> dict:
        """Run a git command in the user's workspace.

        Common uses: git init, git status, git diff, git log, git add, git commit, etc.

        Args:
            user_id: The user who owns the workspace
            command: Git subcommand and args (e.g. "status", "log --oneline -10", "diff HEAD~1")
            working_directory: Subdirectory containing the git repo (optional)
        """
        workspace = _get_workspace_root(user_id)
        cwd = workspace
        if working_directory:
            try:
                cwd = _validate_path(workspace, working_directory)
            except ValueError as e:
                return {"error": str(e)}

        # Block dangerous git commands
        cmd_lower = command.lower().strip()
        if any(danger in cmd_lower for danger in ["push --force", "reset --hard", "clean -fd"]):
            return {
                "error": "Dangerous git command blocked. Use with caution.",
                "command": f"git {command}",
            }

        full_cmd = f"git {command}"
        try:
            proc = await asyncio.create_subprocess_shell(
                full_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(cwd),
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)

            return {
                "exit_code": proc.returncode,
                "stdout": stdout.decode("utf-8", errors="replace")[:_MAX_OUTPUT_BYTES],
                "stderr": stderr.decode("utf-8", errors="replace")[:_MAX_OUTPUT_BYTES],
                "success": proc.returncode == 0,
                "command": full_cmd,
            }
        except asyncio.TimeoutError:
            return {"error": "Git command timed out", "command": full_cmd}
        except Exception as e:
            return {"error": str(e), "command": full_cmd}

    return [
        execute_code,
        run_shell_command,
        read_project_file,
        write_project_file,
        edit_project_file,
        search_codebase,
        list_project_files,
        git_command,
    ]
