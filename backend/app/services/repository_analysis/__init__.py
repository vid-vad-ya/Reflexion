"""Repository Analysis package.

Contains modular components for deterministic repository scanning, technology detection,
directory scoring, file prioritization, and preview context generation.
"""

from app.services.repository_analysis.constants import (
    DEFAULT_IGNORE_PATTERNS,
    ENTRY_POINT_PATTERNS,
    FRAMEWORK_PATTERNS,
    PACKAGE_MANAGER_PATTERNS,
    TECHNOLOGY_PATTERNS,
)
from app.services.repository_analysis.detectors import TechnologyDetector
from app.services.repository_analysis.preview import PreviewCollector
from app.services.repository_analysis.prioritizer import FilePrioritizer
from app.services.repository_analysis.scanner import RepositoryScanner

__all__ = [
    "DEFAULT_IGNORE_PATTERNS",
    "ENTRY_POINT_PATTERNS",
    "FRAMEWORK_PATTERNS",
    "PACKAGE_MANAGER_PATTERNS",
    "TECHNOLOGY_PATTERNS",
    "TechnologyDetector",
    "PreviewCollector",
    "FilePrioritizer",
    "RepositoryScanner",
]
