"""Repository Analyzer Service for Reflexion.

This service is the primary component responsible for analyzing local workspace repositories.
It orchestrates a 2-stage analysis pipeline using modular sub-components:
Stage 1: Deterministic heuristic scanning (file tree scan, directory scoring, technology detection, file prioritization).
Stage 2: Schema-guided LLM reasoning via LLMService to produce a structured ProjectSummary.

Future agents (Planner, Coder, Tester, Reflector) consume the structured ProjectSummary output.
"""

import logging
import os
from typing import Any, Dict, List, Optional, Set

from app.schemas.repository import (
    DirectoryNode,
    EntryPoint,
    HeuristicAnalysisResult,
    LLMProjectSummaryResponse,
    ProjectSummary,
    TechnologyDetection,
)
from app.services.llm import LLMError, llm_service
from app.services.repository_analysis.constants import (
    DEFAULT_IGNORE_PATTERNS,
    MAX_PREVIEW_CHARS_PER_FILE,
    MAX_PREVIEW_FILES,
    MAX_PREVIEW_LINES_PER_FILE,
)
from app.services.repository_analysis.detectors import TechnologyDetector
from app.services.repository_analysis.preview import PreviewCollector
from app.services.repository_analysis.prioritizer import FilePrioritizer
from app.services.repository_analysis.scanner import RepositoryScanner

logger = logging.getLogger("reflexion.analyzer")


# Custom Exception Hierarchy
class RepositoryAnalysisError(Exception):
    """Base exception for repository analyzer service errors."""
    pass


class WorkspaceNotFoundError(RepositoryAnalysisError):
    """Raised when the specified workspace directory does not exist or is inaccessible."""
    pass


class ProjectDetectionError(RepositoryAnalysisError):
    """Raised when critical project detection operations fail."""
    pass


class RepositoryAnalyzer:
    """Service orchestrating repository inspection, deterministic heuristics, and LLM summarization."""

    def __init__(
        self,
        max_directory_depth: int = 5,
        max_file_size_bytes: int = 100_000,
        ignore_patterns: Optional[List[str]] = None,
    ) -> None:
        """Initialize RepositoryAnalyzer with configurable limits and modular engines."""
        self._max_depth = max_directory_depth
        self._max_file_size = max_file_size_bytes
        self._ignore_patterns = set(ignore_patterns) if ignore_patterns else DEFAULT_IGNORE_PATTERNS

        self.scanner = RepositoryScanner(max_depth=self._max_depth, ignore_patterns=self._ignore_patterns)
        self.detector = TechnologyDetector()
        self.prioritizer = FilePrioritizer()
        self.preview_collector = PreviewCollector(
            max_files=MAX_PREVIEW_FILES,
            max_lines=MAX_PREVIEW_LINES_PER_FILE,
            max_chars=MAX_PREVIEW_CHARS_PER_FILE,
            max_file_size_bytes=self._max_file_size,
        )

    def analyze_repository(self, workspace_path: str) -> ProjectSummary:
        """Orchestrate 2-stage analysis pipeline on a local workspace directory.

        Stage 1: Deterministic heuristic scan.
        Stage 2: LLM reasoning & summarization using LLMService.
        """
        abs_path = os.path.abspath(workspace_path)
        logger.info(f"Analysis started for workspace: '{abs_path}'")

        if not os.path.exists(abs_path) or not os.path.isdir(abs_path):
            logger.error(f"Workspace path not found or not a directory: '{abs_path}'")
            raise WorkspaceNotFoundError(f"Workspace directory not found: '{workspace_path}'")

        try:
            # Stage 1: Heuristic Analysis
            logger.info("Executing Stage 1: Deterministic Heuristic Analysis")
            heuristic_result = self._run_heuristic_stage(abs_path)

            # Stage 2: LLM Reasoning & Summarization
            logger.info("Executing Stage 2: LLM Reasoning & Summarization")
            summary = self.summarize_repository(abs_path, heuristic_result)

            logger.info(f"Analysis completed successfully for project: '{summary.project_name}'")
            return summary
        except RepositoryAnalysisError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error during repository analysis of '{abs_path}': {e}")
            raise RepositoryAnalysisError(f"Failed to analyze repository: {str(e)}") from e

    def _run_heuristic_stage(self, workspace_path: str) -> HeuristicAnalysisResult:
        """Perform all Stage 1 heuristic scans using modular sub-components."""
        abs_workspace = os.path.abspath(workspace_path)

        # 1. Traversal and Directory Tree Build
        tree = self.scanner.build_directory_tree(abs_workspace)
        all_files, all_dirs = self.scanner.scan_files_and_directories(abs_workspace)

        # 2. Manifest file contents collection for heuristics
        manifest_files = [
            f for f in all_files if os.path.basename(f) in {
                "requirements.txt", "pyproject.toml", "setup.py", "package.json",
                "package-lock.json", "pnpm-lock.yaml", "yarn.lock", "Dockerfile",
                "docker-compose.yml", "compose.yaml", ".env.example", "Makefile",
                "Procfile", "tsconfig.json", "go.mod", "Cargo.toml", "pom.xml",
                "build.gradle", "alembic.ini"
            }
        ]
        manifest_contents: Dict[str, str] = {}
        for mf in manifest_files:
            fp = os.path.join(abs_workspace, mf)
            try:
                if os.path.exists(fp) and os.path.getsize(fp) <= self._max_file_size:
                    with open(fp, "r", encoding="utf-8", errors="replace") as f:
                        manifest_contents[mf] = f.read()
            except Exception as e:
                logger.warning(f"Failed reading manifest file '{mf}': {e}")

        # 3. Directory Scoring and Selection
        important_dirs = self.scanner.score_and_select_important_directories(all_dirs, all_files)

        # 4. Deterministic Language, Entry Point, and Framework Detections
        lang_techs = self.detector.detect_languages(all_files, manifest_contents)
        languages = [t.name for t in lang_techs]

        entry_points = self.detector.detect_entry_points(abs_workspace, all_files, manifest_contents)
        fw_techs = self.detector.detect_frameworks(all_files, manifest_contents, languages)
        frameworks = [t.name for t in fw_techs]

        pkg_manager = self.detector.detect_package_managers(all_files, manifest_contents)

        # 5. Additional Extensible Technologies
        additional_techs = self.detector.detect_technologies(all_files, manifest_contents)

        # Combine all TechnologyDetections
        all_technologies: List[TechnologyDetection] = []
        all_technologies.extend(lang_techs)
        all_technologies.extend(fw_techs)
        if pkg_manager:
            all_technologies.append(
                TechnologyDetection(
                    name=pkg_manager, category="Package Manager", detected_from=list(manifest_contents.keys())
                )
            )
        all_technologies.extend(additional_techs)

        # Extract specific categories for ProjectSummary backwards compatibility
        database = next((t.name for t in additional_techs if t.category == "Database"), None)
        orm = next((t.name for t in additional_techs if t.category == "ORM"), None)
        auth = next((t.name for t in additional_techs if t.category == "Authentication"), None)
        ai_stack = [t.name for t in additional_techs if t.category == "AI"]
        testing_frameworks = [t.name for t in additional_techs if t.category == "Testing"]
        deployment = next((t.name for t in additional_techs if t.category == "Deployment"), None)

        # 6. Prioritize Files (10-tier ranking)
        prioritized_files = self.prioritizer.categorize_and_prioritize_files(all_files, entry_points)

        # 7. Collect Context-Bounded File Previews (Top 10 files)
        file_previews = self.preview_collector.collect_previews(abs_workspace, prioritized_files)

        return HeuristicAnalysisResult(
            directory_tree=tree,
            important_directories=important_dirs,
            important_files=prioritized_files,
            collected_file_contents=file_previews,
            languages=languages,
            frameworks=frameworks,
            package_manager=pkg_manager,
            database=database,
            orm=orm,
            authentication=auth,
            ai_stack=ai_stack,
            testing_frameworks=testing_frameworks,
            deployment=deployment,
            entry_points=entry_points,
            technologies=all_technologies,
        )

    # Public helper methods preserved for 100% backward compatibility
    def build_directory_tree(
        self,
        workspace_path: str,
        max_depth: Optional[int] = None,
        ignore_patterns: Optional[List[str]] = None,
    ) -> DirectoryNode:
        return self.scanner.build_directory_tree(workspace_path, max_depth, ignore_patterns)

    def collect_project_files(
        self,
        workspace_path: str,
        important_files: Optional[List[str]] = None,
        max_file_size_bytes: Optional[int] = None,
    ) -> Dict[str, str]:
        all_files, _ = self.scanner.scan_files_and_directories(workspace_path)
        entry_points = self.detector.detect_entry_points(workspace_path, all_files, {})
        prioritized = self.prioritizer.categorize_and_prioritize_files(all_files, entry_points)
        if important_files:
            prioritized = [f for f in prioritized if f in important_files or os.path.basename(f) in important_files]
        return self.preview_collector.collect_previews(workspace_path, prioritized)

    def detect_languages(
        self, workspace_path: str, collected_files: Dict[str, str]
    ) -> List[TechnologyDetection]:
        all_files, _ = self.scanner.scan_files_and_directories(workspace_path)
        return self.detector.detect_languages(all_files, collected_files)

    def detect_frameworks(
        self,
        workspace_path: str,
        collected_files: Dict[str, str],
        languages: List[str],
    ) -> List[TechnologyDetection]:
        all_files, _ = self.scanner.scan_files_and_directories(workspace_path)
        return self.detector.detect_frameworks(all_files, collected_files, languages)

    def detect_package_managers(
        self, workspace_path: str, collected_files: Dict[str, str]
    ) -> Optional[str]:
        all_files, _ = self.scanner.scan_files_and_directories(workspace_path)
        return self.detector.detect_package_managers(all_files, collected_files)

    def detect_database(
        self, workspace_path: str, collected_files: Dict[str, str]
    ) -> Optional[str]:
        all_files, _ = self.scanner.scan_files_and_directories(workspace_path)
        techs = self.detector.detect_technologies(all_files, collected_files)
        return next((t.name for t in techs if t.category == "Database"), None)

    def detect_ai_stack(
        self, workspace_path: str, collected_files: Dict[str, str]
    ) -> List[TechnologyDetection]:
        all_files, _ = self.scanner.scan_files_and_directories(workspace_path)
        techs = self.detector.detect_technologies(all_files, collected_files)
        return [t for t in techs if t.category == "AI"]

    def detect_entry_points(
        self, workspace_path: str, collected_files: Dict[str, str]
    ) -> List[EntryPoint]:
        all_files, _ = self.scanner.scan_files_and_directories(workspace_path)
        return self.detector.detect_entry_points(workspace_path, all_files, collected_files)

    def _detect_orm(self, collected_files: Dict[str, str]) -> Optional[str]:
        techs = self.detector.detect_technologies(list(collected_files.keys()), collected_files)
        return next((t.name for t in techs if t.category == "ORM"), None)

    def _detect_auth(self, collected_files: Dict[str, str]) -> Optional[str]:
        techs = self.detector.detect_technologies(list(collected_files.keys()), collected_files)
        return next((t.name for t in techs if t.category == "Authentication"), None)

    def _detect_testing(self, collected_files: Dict[str, str]) -> List[str]:
        techs = self.detector.detect_technologies(list(collected_files.keys()), collected_files)
        return [t.name for t in techs if t.category == "Testing"]

    def _detect_deployment(self, collected_files: Dict[str, str]) -> Optional[str]:
        techs = self.detector.detect_technologies(list(collected_files.keys()), collected_files)
        return next((t.name for t in techs if t.category == "Deployment"), None)

    def summarize_repository(
        self, workspace_path: str, heuristic_result: HeuristicAnalysisResult
    ) -> ProjectSummary:
        """Stage 2: Generate high-level summary and observations using LLMService."""
        project_name = os.path.basename(os.path.abspath(workspace_path)) or "Reflexion-Workspace"

        prompt = (
            f"Analyze the following structured repository heuristic facts for project '{project_name}' and produce a comprehensive "
            "ProjectSummary JSON response.\n\n"
            f"Project Name: {project_name}\n"
            f"Detected Languages: {heuristic_result.languages}\n"
            f"Detected Frameworks: {heuristic_result.frameworks}\n"
            f"Package Manager: {heuristic_result.package_manager}\n"
            f"Database: {heuristic_result.database}\n"
            f"ORM: {heuristic_result.orm}\n"
            f"Authentication: {heuristic_result.authentication}\n"
            f"AI Stack: {heuristic_result.ai_stack}\n"
            f"Testing Frameworks: {heuristic_result.testing_frameworks}\n"
            f"Deployment: {heuristic_result.deployment}\n"
            f"Scored Functional Directories: {heuristic_result.important_directories}\n"
            f"Prioritized Implementation Files (Top Files): {heuristic_result.important_files[:15]}\n"
            f"Identified Application Entry Points: {[ep.path for ep in heuristic_result.entry_points]}\n\n"
            "Bounded File Previews (Top Implementation & Manifest Files):\n"
        )

        for filename, content in heuristic_result.collected_file_contents.items():
            prompt += f"\n--- File: {filename} ---\n{content}\n"

        system_instruction = (
            "You are an expert software architect AI. Synthesize the provided repository heuristic facts into a concise, high-quality "
            "ProjectSummary structured output. Do NOT invent false dependencies or unverified files."
        )

        try:
            logger.info("Calling LLMService.generate_json for repository summarization...")
            llm_res = llm_service.generate_json(
                prompt=prompt,
                response_schema=LLMProjectSummaryResponse,
                system_instruction=system_instruction,
                temperature=0.1,
            )

            return ProjectSummary(
                project_name=llm_res.project_name or project_name,
                description=llm_res.description or f"{project_name} application.",
                languages=llm_res.languages or heuristic_result.languages,
                frameworks=llm_res.frameworks or heuristic_result.frameworks,
                package_manager=llm_res.package_manager or heuristic_result.package_manager,
                database=llm_res.database or heuristic_result.database,
                orm=llm_res.orm or heuristic_result.orm,
                authentication=llm_res.authentication or heuristic_result.authentication,
                ai_stack=llm_res.ai_stack or heuristic_result.ai_stack,
                testing_frameworks=llm_res.testing_frameworks or heuristic_result.testing_frameworks,
                deployment=llm_res.deployment or heuristic_result.deployment,
                architecture=llm_res.architecture or "Standard Modular Application",
                important_directories=heuristic_result.important_directories,
                important_files=heuristic_result.important_files,
                entry_points=heuristic_result.entry_points,
                technologies=heuristic_result.technologies,
                observations=llm_res.observations or [f"Analyzed {project_name} workspace."],
            )
        except Exception as e:
            logger.warning(
                f"LLM summarization failed or unconfigured: {e}. Falling back to deterministic heuristic summary."
            )

            description = (
                f"{project_name} project utilizing {', '.join(heuristic_result.languages) or 'software engineering'} "
                f"and {', '.join(heuristic_result.frameworks) or 'standard application components'}."
            )

            architecture = "Standard Modular Application"
            if any(d in heuristic_result.important_directories for d in ["frontend", "backend"]):
                architecture = "Decoupled Client-Server Monorepo"

            observations = [
                f"Repository contains {len(heuristic_result.important_files)} discovered project files.",
                f"Primary languages detected: {', '.join(heuristic_result.languages) or 'None'}.",
                f"Identified {len(heuristic_result.entry_points)} application entry points.",
            ]

            return ProjectSummary(
                project_name=project_name,
                description=description,
                languages=heuristic_result.languages,
                frameworks=heuristic_result.frameworks,
                package_manager=heuristic_result.package_manager,
                database=heuristic_result.database,
                orm=heuristic_result.orm,
                authentication=heuristic_result.authentication,
                ai_stack=heuristic_result.ai_stack,
                testing_frameworks=heuristic_result.testing_frameworks,
                deployment=heuristic_result.deployment,
                architecture=architecture,
                important_directories=heuristic_result.important_directories,
                important_files=heuristic_result.important_files,
                entry_points=heuristic_result.entry_points,
                technologies=heuristic_result.technologies,
                observations=observations,
            )


# Global singleton instance
repository_analyzer = RepositoryAnalyzer()
