"""WorkspaceManager – Isolated Workspace Creation and Patch Application for Reflexion.

Orchestrates Phase 9 workspace management:
1. Creates an isolated temporary workspace directory.
2. Copies the entire repository into that workspace (preserving directory structure).
3. Applies generated file changes (create / modify / delete) from CodingResult.
4. Provides cleanup to remove the temporary workspace when requested.

Key design constraints:
- No LLM calls. Fully deterministic file-system operations only.
- The original repository is NEVER modified.
- Every generated file path is validated against path traversal attacks.
- generated_content is the authoritative source of truth for materialization
  (unified_diff is informational only and is NOT applied here).
"""

import logging
import os
import shutil
import uuid
from pathlib import Path
from typing import List, Optional, Union

from app.schemas.coder import GeneratedFile

logger = logging.getLogger("reflexion.services.workspace_manager")


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class WorkspaceManagerError(Exception):
    """Base exception for all WorkspaceManager errors."""
    pass


class WorkspaceCreationError(WorkspaceManagerError):
    """Raised when workspace directory creation or repository copy fails."""
    pass


class PathTraversalError(WorkspaceManagerError):
    """Raised when a generated file path would escape the workspace boundary."""
    pass


class PatchApplicationError(WorkspaceManagerError):
    """Raised when applying a generated file change fails."""
    pass


# ---------------------------------------------------------------------------
# WorkspaceManager
# ---------------------------------------------------------------------------

class WorkspaceManager:
    """Manages creation, patching, and cleanup of isolated repository workspaces.

    Intended to sit directly after the Coder Agent in the Reflexion pipeline:

        Repository Analyzer → Planner → Coder → WorkspaceManager → Temporary Workspace

    All methods are stateless and operate on explicit path arguments so that
    multiple concurrent workspaces can be managed safely.
    """

    def __init__(self, base_workspace_dir: Optional[Union[str, Path]] = None) -> None:
        """Initialise WorkspaceManager.

        Args:
            base_workspace_dir: Root directory under which workspaces are created.
                Defaults to a ``workspaces/`` sub-directory inside the standard
                Reflexion data directory (``~/.reflexion/workspaces/``).
        """
        if base_workspace_dir is not None:
            self._base_workspace_dir = Path(base_workspace_dir).resolve()
        else:
            from app.core.config import settings
            # Place isolated workspaces alongside cloned repos so they share
            # the same filesystem mount for fast copies.
            self._base_workspace_dir = (
                Path(settings.LOCAL_WORKSPACE_DIR).resolve().parent / "agent_workspaces"
            )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def create_workspace(
        self,
        repository_path: Union[str, Path],
        workspace_id: Optional[str] = None,
    ) -> Path:
        """Create an isolated workspace containing a full copy of the repository.

        The original repository at *repository_path* is **never modified**.

        Args:
            repository_path: Absolute path to the source repository directory.
            workspace_id: Optional identifier for the workspace directory name.
                Defaults to a freshly generated UUID4.

        Returns:
            Path: Absolute path to the newly created workspace root.

        Raises:
            WorkspaceCreationError: If the source path does not exist or the
                copy operation fails.
        """
        src = Path(repository_path).resolve()
        if not src.exists():
            raise WorkspaceCreationError(
                f"Source repository path does not exist: '{src}'"
            )
        if not src.is_dir():
            raise WorkspaceCreationError(
                f"Source repository path is not a directory: '{src}'"
            )

        ws_id = workspace_id or str(uuid.uuid4())
        workspace = (self._base_workspace_dir / ws_id).resolve()

        logger.info(
            f"Creating isolated workspace '{workspace}' from source '{src}'"
        )

        try:
            # Ensure base directory exists.
            self._base_workspace_dir.mkdir(parents=True, exist_ok=True)

            # Copy full directory tree into workspace.  dirs_exist_ok=False
            # (default) ensures we never overwrite an existing workspace.
            shutil.copytree(src=str(src), dst=str(workspace))
            logger.info(
                f"Repository successfully copied to workspace '{workspace}'"
            )
            return workspace

        except FileExistsError as exc:
            raise WorkspaceCreationError(
                f"Workspace directory already exists at '{workspace}': {exc}"
            ) from exc
        except PermissionError as exc:
            raise WorkspaceCreationError(
                f"Permission denied while creating workspace '{workspace}': {exc}"
            ) from exc
        except Exception as exc:
            # Attempt cleanup of a partial copy before re-raising.
            if workspace.exists():
                shutil.rmtree(workspace, ignore_errors=True)
            raise WorkspaceCreationError(
                f"Failed to create workspace from '{src}': {exc}"
            ) from exc

    def apply_changes(
        self,
        workspace: Union[str, Path],
        generated_files: List[GeneratedFile],
    ) -> List[str]:
        """Materialize Coder Agent file changes inside the isolated workspace.

        For each :class:`GeneratedFile`:

        * ``create``  – Creates parent directories if necessary, then writes
          *generated_content* to the target path.
        * ``modify``  – Same write logic; creates parent directories when the
          file is new to the workspace (handles plans that list existing files
          under ``new_files``).
        * ``delete``  – Removes the file if it exists; silently skips absent
          files (idempotent).

        The ``unified_diff`` field is **informational only** and is not used
        here. The *generated_content* field is the authoritative source of truth.

        Args:
            workspace: Absolute path to the target workspace directory.
            generated_files: Ordered list of ``GeneratedFile`` objects from
                ``CodingResult.generated_files``.

        Returns:
            List[str]: Non-fatal warning messages accumulated during patching.

        Raises:
            WorkspaceCreationError: If the workspace directory does not exist.
            PathTraversalError: If any file path escapes the workspace boundary.
            PatchApplicationError: If a file-system operation fails unexpectedly.
        """
        ws = Path(workspace).resolve()
        if not ws.exists() or not ws.is_dir():
            raise WorkspaceCreationError(
                f"Workspace directory does not exist: '{ws}'"
            )

        warnings: List[str] = []

        for gen_file in generated_files:
            target = self._resolve_safe_path(ws, gen_file.path)
            change_type = gen_file.change_type.lower()

            try:
                if change_type == "create":
                    self._apply_create(ws, target, gen_file)
                elif change_type == "modify":
                    self._apply_modify(ws, target, gen_file, warnings)
                elif change_type == "delete":
                    self._apply_delete(target, gen_file, warnings)
                else:
                    msg = (
                        f"Unknown change_type '{gen_file.change_type}' for "
                        f"'{gen_file.path}'; skipping."
                    )
                    logger.warning(msg)
                    warnings.append(msg)

            except PathTraversalError:
                raise
            except PermissionError as exc:
                raise PatchApplicationError(
                    f"Permission denied while applying '{change_type}' to "
                    f"'{gen_file.path}': {exc}"
                ) from exc
            except Exception as exc:
                raise PatchApplicationError(
                    f"Unexpected error applying '{change_type}' to "
                    f"'{gen_file.path}': {exc}"
                ) from exc

        logger.info(
            f"Applied {len(generated_files)} file change(s) to workspace '{ws}' "
            f"({len(warnings)} warning(s))"
        )
        return warnings

    def cleanup(self, workspace: Union[str, Path]) -> None:
        """Remove the temporary workspace directory entirely.

        This operation is **not** called automatically — callers must invoke it
        explicitly when the workspace is no longer needed. This allows tests and
        higher-level orchestration to inspect the workspace before disposal.

        Args:
            workspace: Absolute path to the workspace to remove.
        """
        ws = Path(workspace).resolve()
        if not ws.exists():
            logger.info(f"Workspace '{ws}' does not exist; nothing to clean up.")
            return

        try:
            shutil.rmtree(ws)
            logger.info(f"Workspace '{ws}' successfully removed.")
        except PermissionError as exc:
            logger.error(f"Permission denied while removing workspace '{ws}': {exc}")
            raise WorkspaceManagerError(
                f"Permission denied while cleaning up workspace '{ws}': {exc}"
            ) from exc
        except Exception as exc:
            logger.error(f"Failed to remove workspace '{ws}': {exc}")
            raise WorkspaceManagerError(
                f"Failed to clean up workspace '{ws}': {exc}"
            ) from exc

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _resolve_safe_path(self, workspace: Path, rel_path: str) -> Path:
        """Resolve *rel_path* relative to *workspace*, rejecting path traversal.

        Args:
            workspace: Absolute workspace root (already resolved).
            rel_path: Relative path from the generated file object.

        Returns:
            Path: Resolved absolute path guaranteed to be inside *workspace*.

        Raises:
            PathTraversalError: If the resolved path escapes the workspace root.
        """
        if not rel_path or not isinstance(rel_path, str):
            raise PathTraversalError(
                "Generated file path is empty or not a string."
            )

        stripped = rel_path.strip()

        # Reject paths that are already absolute on any OS before any further
        # processing.  This catches Unix-style (/etc/passwd) and Windows-style
        # (C:\...) absolute paths that should never appear in generated_content.
        # Note: on Windows Path('/etc/passwd').is_absolute() returns False because
        # the path is root-relative rather than drive-absolute, so we also check
        # the raw string for a leading forward slash.
        if Path(stripped).is_absolute() or stripped.startswith("/"):
            raise PathTraversalError(
                f"Absolute path rejected for generated file '{rel_path}': "
                "only relative paths are allowed inside the workspace."
            )

        # Strip leading slashes / backslashes so os.path.join does not treat
        # the path as absolute and jump to the filesystem root.
        clean_rel = stripped.lstrip("/\\")
        if not clean_rel:
            raise PathTraversalError(
                f"Generated file path '{rel_path}' resolves to an empty string "
                "after sanitisation."
            )

        resolved = (workspace / clean_rel).resolve()

        # The resolved path MUST start with the workspace root string.
        # We use os.fspath comparison rather than Path.is_relative_to() for
        # Python 3.8 compatibility.
        ws_str = str(workspace)
        res_str = str(resolved)
        if not (res_str == ws_str or res_str.startswith(ws_str + os.sep)):
            raise PathTraversalError(
                f"Path traversal attempt detected for file '{rel_path}': "
                f"resolved path '{resolved}' escapes workspace boundary '{workspace}'."
            )

        return resolved


    @staticmethod
    def _apply_create(
        workspace: Path,
        target: Path,
        gen_file: GeneratedFile,
    ) -> None:
        """Write generated_content to target, creating parent directories."""
        content = gen_file.generated_content or ""
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        logger.debug(
            f"[CREATE] '{gen_file.path}' written ({len(content)} chars) "
            f"→ '{target}'"
        )

    @staticmethod
    def _apply_modify(
        workspace: Path,
        target: Path,
        gen_file: GeneratedFile,
        warnings: List[str],
    ) -> None:
        """Overwrite target with generated_content, creating parent dirs if absent."""
        content = gen_file.generated_content or ""
        if not target.exists():
            msg = (
                f"[MODIFY] Target file '{gen_file.path}' not found in workspace; "
                "creating it instead."
            )
            logger.info(msg)
            warnings.append(msg)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        logger.debug(
            f"[MODIFY] '{gen_file.path}' overwritten ({len(content)} chars) "
            f"→ '{target}'"
        )

    @staticmethod
    def _apply_delete(
        target: Path,
        gen_file: GeneratedFile,
        warnings: List[str],
    ) -> None:
        """Remove target file; silently skip if already absent."""
        if not target.exists():
            msg = (
                f"[DELETE] Target file '{gen_file.path}' not found in workspace; "
                "skipping (already absent)."
            )
            logger.info(msg)
            warnings.append(msg)
            return
        target.unlink()
        logger.debug(f"[DELETE] '{gen_file.path}' removed → '{target}'")


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

workspace_manager = WorkspaceManager()
