"""Preview Collector module.

Handles context-bounded file preview extraction, binary file filtering,
and README summarization to keep LLM context predictable and token-efficient.
"""

import os
import logging
from typing import Dict, List, Optional

from app.services.repository_analysis.constants import (
    BINARY_FILE_EXTENSIONS,
    MAX_PREVIEW_CHARS_PER_FILE,
    MAX_PREVIEW_FILES,
    MAX_PREVIEW_LINES_PER_FILE,
)

logger = logging.getLogger("reflexion.analyzer.preview")


class PreviewCollector:
    """Collects context-bounded text previews for top-ranked repository files."""

    def __init__(
        self,
        max_files: int = MAX_PREVIEW_FILES,
        max_lines: int = MAX_PREVIEW_LINES_PER_FILE,
        max_chars: int = MAX_PREVIEW_CHARS_PER_FILE,
        max_file_size_bytes: int = 100_000,
    ) -> None:
        self.max_files = max_files
        self.max_lines = max_lines
        self.max_chars = max_chars
        self.max_file_size = max_file_size_bytes

    def collect_previews(
        self,
        workspace_path: str,
        prioritized_files: List[str],
    ) -> Dict[str, str]:
        """Extract bounded previews of the top N prioritized workspace files.

        Applies:
        - Max 10 top files limit
        - Max 150 lines limit per file preview
        - Max 1500 characters limit per file preview
        - Skip binary files
        - Summarize README.md instead of full inclusion
        """
        abs_workspace = os.path.abspath(workspace_path)
        collected: Dict[str, str] = {}

        count = 0
        for rel_path in prioritized_files:
            if count >= self.max_files:
                break

            full_path = os.path.join(abs_workspace, rel_path)
            if not os.path.exists(full_path) or not os.path.isfile(full_path):
                continue

            # Check binary extension
            ext = os.path.splitext(rel_path)[1].lower()
            if ext in BINARY_FILE_EXTENSIONS:
                logger.debug(f"Skipping binary file preview: '{rel_path}'")
                continue

            # Check file size limit
            try:
                stat = os.stat(full_path)
                if stat.st_size > self.max_file_size:
                    logger.debug(f"Skipping large file ({stat.st_size} bytes): '{rel_path}'")
                    continue

                with open(full_path, "r", encoding="utf-8", errors="replace") as f:
                    lines = []
                    char_count = 0
                    for line_idx, line in enumerate(f):
                        if line_idx >= self.max_lines or char_count >= self.max_chars:
                            break
                        lines.append(line)
                        char_count += len(line)

                    content = "".join(lines).strip()

                    # Special handling for README.md -> Excerpt / summary format
                    if os.path.basename(rel_path).lower() == "readme.md":
                        if len(content) > 500:
                            content = content[:500] + "\n... [README Summary Excerpt Truncated]"

                    if content:
                        collected[rel_path] = content
                        count += 1
            except Exception as e:
                logger.warning(f"Failed to read file preview for '{rel_path}': {e}")

        return collected
