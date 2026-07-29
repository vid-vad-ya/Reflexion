"""Repository Scanner module.

Handles directory tree traversal, ignored path skipping, and directory scoring system.
"""

import os
import logging
from typing import Dict, List, Optional, Set, Tuple

from app.schemas.repository import DirectoryNode
from app.services.repository_analysis.constants import (
    DEFAULT_IGNORE_PATTERNS,
    KEY_FUNCTIONAL_DIR_BONUS,
)

logger = logging.getLogger("reflexion.analyzer.scanner")


class RepositoryScanner:
    """Performs single-pass filesystem scanning, directory tree generation, and directory scoring."""

    def __init__(
        self,
        max_depth: int = 5,
        ignore_patterns: Optional[Set[str]] = None,
    ) -> None:
        self.max_depth = max_depth
        self.ignore_patterns = ignore_patterns if ignore_patterns is not None else DEFAULT_IGNORE_PATTERNS

    def build_directory_tree(
        self,
        workspace_path: str,
        max_depth: Optional[int] = None,
        ignore_patterns: Optional[List[str]] = None,
    ) -> DirectoryNode:
        """Build clean DirectoryNode tree ignoring specified pattern folders."""
        depth_limit = max_depth if max_depth is not None else self.max_depth
        ignores = set(ignore_patterns) if ignore_patterns is not None else self.ignore_patterns

        def _traverse(current_path: str, rel_path: str, current_depth: int) -> DirectoryNode:
            basename = os.path.basename(current_path) or rel_path or "root"
            is_dir = os.path.isdir(current_path)

            if not is_dir:
                return DirectoryNode(name=basename, path=rel_path, is_dir=False, file_count=1)

            if current_depth >= depth_limit:
                return DirectoryNode(name=basename, path=rel_path, is_dir=True, children=[], file_count=0)

            children: List[DirectoryNode] = []
            total_files = 0

            try:
                entries = sorted(os.listdir(current_path))
                for entry in entries:
                    if entry in ignores:
                        continue
                    full_entry_path = os.path.join(current_path, entry)
                    child_rel_path = os.path.normpath(os.path.join(rel_path, entry)) if rel_path else entry
                    child_node = _traverse(full_entry_path, child_rel_path, current_depth + 1)
                    children.append(child_node)
                    total_files += child_node.file_count or 1
            except PermissionError:
                logger.warning(f"Permission denied traversing directory: {current_path}")

            return DirectoryNode(
                name=basename,
                path=rel_path or ".",
                is_dir=True,
                children=children,
                file_count=total_files,
            )

        return _traverse(os.path.abspath(workspace_path), "", 0)

    def scan_files_and_directories(
        self, workspace_path: str
    ) -> Tuple[List[str], List[str]]:
        """Perform recursive workspace walk to collect all relative file paths and directory paths.

        Returns:
            Tuple[List[rel_file_paths], List[rel_dir_paths]]
        """
        abs_workspace = os.path.abspath(workspace_path)
        all_files: List[str] = []
        all_dirs: List[str] = []

        for root, dirs, files in os.walk(abs_workspace):
            # Prune ignored directories in place
            dirs[:] = [d for d in dirs if d not in self.ignore_patterns]

            rel_dir = os.path.relpath(root, abs_workspace)
            if rel_dir != ".":
                all_dirs.append(os.path.normpath(rel_dir).replace("\\", "/"))

            for file in files:
                if file in self.ignore_patterns:
                    continue
                rel_file = os.path.join(rel_dir, file) if rel_dir != "." else file
                all_files.append(os.path.normpath(rel_file).replace("\\", "/"))

        return all_files, all_dirs

    def score_and_select_important_directories(
        self, all_dirs: List[str], all_files: List[str]
    ) -> List[str]:
        """Score directories based on content characteristics and return top-scoring functional directories."""
        dir_scores: Dict[str, int] = {}

        for d in all_dirs:
            score = 0
            base = os.path.basename(d).lower()

            # Functional directory bonus based on folder name
            if base in KEY_FUNCTIONAL_DIR_BONUS:
                score += KEY_FUNCTIONAL_DIR_BONUS[base]

            # Score based on files contained in directory or its subdirectories
            prefix = d + "/"
            matching_files = [f for f in all_files if f.startswith(prefix) or f == d]

            for file in matching_files:
                fname = os.path.basename(file).lower()

                # Entry points / source files
                if fname in {"main.py", "app.py", "server.py", "index.js", "index.ts", "app.ts", "server.js"}:
                    score += 20
                elif any(file.lower().endswith(ext) for ext in [".py", ".ts", ".js", ".java", ".go", ".rs"]):
                    score += 5

                # Routes / controllers / services / models
                if any(kw in file.lower() for kw in ["route", "api", "controller", "endpoint"]):
                    score += 15
                if any(kw in file.lower() for kw in ["service", "usecase", "logic"]):
                    score += 15
                if any(kw in file.lower() for kw in ["model", "schema", "entity", "dto"]):
                    score += 12

            if score > 0:
                dir_scores[d] = score

        # Sort directories by score descending
        sorted_dirs = sorted(dir_scores.keys(), key=lambda x: dir_scores[x], reverse=True)

        # Select top unique functional directories (up to 15)
        selected: List[str] = []
        for d in sorted_dirs:
            if len(selected) >= 15:
                break
            selected.append(d)

        # Fallback to top level directories if no scored directories found
        if not selected and all_dirs:
            selected = [d for d in all_dirs if "/" not in d and d not in self.ignore_patterns][:10]

        return selected
