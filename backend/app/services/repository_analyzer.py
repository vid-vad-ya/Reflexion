"""Repository Analyzer Service for Reflexion.

This service is the ONLY component responsible for analyzing local workspace repositories.
It performs a 2-stage analysis pipeline:
Stage 1: Deterministic heuristic scanning (file tree, important files, languages, frameworks, entry points).
Stage 2: Schema-guided LLM reasoning via LLMService to produce a structured ProjectSummary.

Future agents (Planner, Coder, Tester, Reflector) consume the structured ProjectSummary output.
"""

import logging
import os
import re
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

logger = logging.getLogger("reflexion.analyzer")

# Default ignore patterns for filesystem traversal
DEFAULT_IGNORE_PATTERNS: Set[str] = {
    ".git",
    "node_modules",
    "venv",
    ".venv",
    "env",
    ".env",
    "dist",
    "build",
    "target",
    "coverage",
    "__pycache__",
    ".cache",
    ".next",
    "out",
    ".idea",
    ".vscode",
    ".pytest_cache",
    ".mypy_cache",
    "bin",
    "obj",
}

# Important configuration and manifest files to detect and inspect
DEFAULT_IMPORTANT_FILES: List[str] = [
    "README.md",
    "requirements.txt",
    "pyproject.toml",
    "package.json",
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "Dockerfile",
    "docker-compose.yml",
    "compose.yaml",
    ".env.example",
    "Makefile",
    "Procfile",
    "tsconfig.json",
    "go.mod",
    "Cargo.toml",
    "pom.xml",
    "build.gradle",
    "alembic.ini",
    "setup.py",
    "Pipfile",
]

# File extension mappings for language detection
LANGUAGE_EXTENSION_MAP: Dict[str, str] = {
    ".py": "Python",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".java": "Java",
    ".go": "Go",
    ".rs": "Rust",
    ".cs": "C#",
    ".cpp": "C++",
    ".cc": "C++",
    ".c": "C",
    ".h": "C/C++",
    ".hpp": "C++",
    ".php": "PHP",
    ".rb": "Ruby",
    ".sh": "Shell",
    ".html": "HTML",
    ".css": "CSS",
}


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
    """Service responsible for repository inspection, heuristic detection, and LLM summarization."""

    def __init__(
        self,
        max_directory_depth: int = 5,
        max_file_size_bytes: int = 100_000,
        ignore_patterns: Optional[List[str]] = None,
    ) -> None:
        """Initialize RepositoryAnalyzer with configurable depth and file size limits.

        Args:
            max_directory_depth: Maximum directory traversal depth.
            max_file_size_bytes: Maximum size in bytes of files to read into memory.
            ignore_patterns: Custom list of folder/file names to ignore.
        """
        self._max_depth = max_directory_depth
        self._max_file_size = max_file_size_bytes
        self._ignore_patterns = set(ignore_patterns) if ignore_patterns else DEFAULT_IGNORE_PATTERNS

    def analyze_repository(self, workspace_path: str) -> ProjectSummary:
        """Orchestrate 2-stage analysis pipeline on a local workspace directory.

        Stage 1: Deterministic heuristic scan.
        Stage 2: LLM summarization using LLMService.

        Args:
            workspace_path: Absolute local filesystem path to cloned repository.

        Returns:
            Structured ProjectSummary Pydantic instance.

        Raises:
            WorkspaceNotFoundError: If workspace_path does not exist or is not a directory.
            RepositoryAnalysisError: On unrecoverable processing error.
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
        """Perform all Stage 1 heuristic scans."""
        # 1. Directory Tree & File Collection
        logger.info("Scanning directory tree...")
        tree = self.build_directory_tree(workspace_path)

        logger.info("Detecting project files...")
        collected_files = self.collect_project_files(workspace_path)
        detected_important_files = list(collected_files.keys())

        # Extract top-level directories
        important_dirs = [
            child.name for child in (tree.children or []) if child.is_dir and child.name not in self._ignore_patterns
        ]

        # 2. Technology & Entry Point Heuristic Detections
        logger.info("Running technology detection heuristics...")
        technologies: List[TechnologyDetection] = []

        # Languages
        lang_techs = self.detect_languages(workspace_path, collected_files)
        technologies.extend(lang_techs)
        languages = [t.name for t in lang_techs]

        # Frameworks
        fw_techs = self.detect_frameworks(workspace_path, collected_files, languages)
        technologies.extend(fw_techs)
        frameworks = [t.name for t in fw_techs]

        # Package Managers
        pkg_manager = self.detect_package_managers(workspace_path, collected_files)
        if pkg_manager:
            technologies.append(
                TechnologyDetection(
                    name=pkg_manager,
                    category="Package Manager",
                    detected_from=detected_important_files,
                    confidence=1.0,
                )
            )

        # Databases
        database = self.detect_database(workspace_path, collected_files)
        if database:
            technologies.append(
                TechnologyDetection(
                    name=database,
                    category="Database",
                    detected_from=detected_important_files,
                    confidence=0.9,
                )
            )

        # Additional Heuristics (ORM, Auth, AI, Testing, Deployment)
        orm = self._detect_orm(collected_files)
        if orm:
            technologies.append(
                TechnologyDetection(
                    name=orm, category="ORM", detected_from=detected_important_files, confidence=0.9
                )
            )

        auth = self._detect_auth(collected_files)
        if auth:
            technologies.append(
                TechnologyDetection(
                    name=auth, category="Authentication", detected_from=detected_important_files, confidence=0.85
                )
            )

        ai_techs = self.detect_ai_stack(workspace_path, collected_files)
        technologies.extend(ai_techs)
        ai_stack = [t.name for t in ai_techs]

        testing_frameworks = self._detect_testing(collected_files)
        for test_fw in testing_frameworks:
            technologies.append(
                TechnologyDetection(
                    name=test_fw, category="Testing", detected_from=detected_important_files, confidence=0.9
                )
            )

        deployment = self._detect_deployment(collected_files)
        if deployment:
            technologies.append(
                TechnologyDetection(
                    name=deployment, category="Deployment", detected_from=detected_important_files, confidence=0.95
                )
            )

        # Entry points
        logger.info("Detecting application entry points...")
        entry_points = self.detect_entry_points(workspace_path, collected_files)

        return HeuristicAnalysisResult(
            directory_tree=tree,
            important_directories=important_dirs,
            important_files=detected_important_files,
            collected_file_contents=collected_files,
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
            technologies=technologies,
        )

    def build_directory_tree(
        self,
        workspace_path: str,
        max_depth: Optional[int] = None,
        ignore_patterns: Optional[List[str]] = None,
    ) -> DirectoryNode:
        """Build a clean directory tree ignoring specified folders.

        Args:
            workspace_path: Local workspace root path.
            max_depth: Maximum depth to traverse.
            ignore_patterns: Folder/file names to skip.

        Returns:
            DirectoryNode representing directory tree.
        """
        depth_limit = max_depth if max_depth is not None else self._max_depth
        ignores = set(ignore_patterns) if ignore_patterns else self._ignore_patterns

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
                    child_rel_path = os.path.join(rel_path, entry) if rel_path else entry
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

    def collect_project_files(
        self,
        workspace_path: str,
        important_files: Optional[List[str]] = None,
        max_file_size_bytes: Optional[int] = None,
    ) -> Dict[str, str]:
        """Collect contents of key configuration and metadata files within size limits.

        Args:
            workspace_path: Absolute workspace root.
            important_files: List of file names/relpaths to look for.
            max_file_size_bytes: File size threshold limit.

        Returns:
            Dict mapping relative file paths to string contents.
        """
        target_files = important_files or DEFAULT_IMPORTANT_FILES
        size_limit = max_file_size_bytes if max_file_size_bytes is not None else self._max_file_size
        collected: Dict[str, str] = {}

        abs_workspace = os.path.abspath(workspace_path)

        for root, dirs, files in os.walk(abs_workspace):
            # Skip ignored directories in place
            dirs[:] = [d for d in dirs if d not in self._ignore_patterns]

            for file in files:
                rel_dir = os.path.relpath(root, abs_workspace)
                rel_path = os.path.join(rel_dir, file) if rel_dir != "." else file

                # Match if filename or rel_path is in important_files list
                if file in target_files or rel_path in target_files:
                    full_path = os.path.join(root, file)
                    try:
                        stat = os.stat(full_path)
                        if stat.st_size > size_limit:
                            logger.info(f"Skipping large important file ({stat.st_size} bytes): '{rel_path}'")
                            continue

                        with open(full_path, "r", encoding="utf-8", errors="replace") as f:
                            collected[rel_path] = f.read()
                    except Exception as e:
                        logger.warning(f"Failed to read file '{rel_path}': {e}")

        return collected

    def detect_languages(
        self, workspace_path: str, collected_files: Dict[str, str]
    ) -> List[TechnologyDetection]:
        """Detect programming languages used in the repository based on file extensions and manifests."""
        detected_counts: Dict[str, int] = {}
        abs_workspace = os.path.abspath(workspace_path)

        for root, dirs, files in os.walk(abs_workspace):
            dirs[:] = [d for d in dirs if d not in self._ignore_patterns]
            for file in files:
                ext = os.path.splitext(file)[1].lower()
                if ext in LANGUAGE_EXTENSION_MAP:
                    lang = LANGUAGE_EXTENSION_MAP[ext]
                    detected_counts[lang] = detected_counts.get(lang, 0) + 1

        # Also check manifests
        if "pyproject.toml" in collected_files or "requirements.txt" in collected_files:
            detected_counts["Python"] = detected_counts.get("Python", 0) + 10
        if "package.json" in collected_files or "tsconfig.json" in collected_files:
            if "tsconfig.json" in collected_files:
                detected_counts["TypeScript"] = detected_counts.get("TypeScript", 0) + 10
            detected_counts["JavaScript"] = detected_counts.get("JavaScript", 0) + 10
        if "go.mod" in collected_files:
            detected_counts["Go"] = detected_counts.get("Go", 0) + 10
        if "Cargo.toml" in collected_files:
            detected_counts["Rust"] = detected_counts.get("Rust", 0) + 10
        if "pom.xml" in collected_files or "build.gradle" in collected_files:
            detected_counts["Java"] = detected_counts.get("Java", 0) + 10

        results: List[TechnologyDetection] = []
        for lang in sorted(detected_counts.keys(), key=lambda x: detected_counts[x], reverse=True):
            results.append(
                TechnologyDetection(
                    name=lang,
                    category="Language",
                    detected_from=list(collected_files.keys()),
                    confidence=1.0,
                )
            )
        return results

    def detect_frameworks(
        self,
        workspace_path: str,
        collected_files: Dict[str, str],
        languages: List[str],
    ) -> List[TechnologyDetection]:
        """Detect web and application frameworks using dependency inspect and file markers."""
        frameworks: List[TechnologyDetection] = []
        combined_text = " ".join(collected_files.values()).lower()

        # Python Frameworks
        if "Python" in languages:
            if "fastapi" in combined_text:
                frameworks.append(TechnologyDetection(name="FastAPI", category="Framework", confidence=1.0))
            if "flask" in combined_text:
                frameworks.append(TechnologyDetection(name="Flask", category="Framework", confidence=1.0))
            if "django" in combined_text:
                frameworks.append(TechnologyDetection(name="Django", category="Framework", confidence=1.0))

        # JS / TS Frameworks
        if "JavaScript" in languages or "TypeScript" in languages:
            if "next" in combined_text or "next.config" in combined_text:
                frameworks.append(TechnologyDetection(name="Next.js", category="Framework", confidence=1.0))
            if "react" in combined_text:
                frameworks.append(TechnologyDetection(name="React", category="Framework", confidence=1.0))
            if "vue" in combined_text:
                frameworks.append(TechnologyDetection(name="Vue", category="Framework", confidence=1.0))
            if "express" in combined_text:
                frameworks.append(TechnologyDetection(name="Express", category="Framework", confidence=1.0))
            if "@angular/core" in combined_text:
                frameworks.append(TechnologyDetection(name="Angular", category="Framework", confidence=1.0))

        # Java Frameworks
        if "Java" in languages and ("spring-boot" in combined_text or "springframework" in combined_text):
            frameworks.append(TechnologyDetection(name="Spring Boot", category="Framework", confidence=1.0))

        # PHP Frameworks
        if "PHP" in languages and "laravel" in combined_text:
            frameworks.append(TechnologyDetection(name="Laravel", category="Framework", confidence=1.0))

        return frameworks

    def detect_package_managers(
        self, workspace_path: str, collected_files: Dict[str, str]
    ) -> Optional[str]:
        """Detect the primary package manager used in the project."""
        if "pnpm-lock.yaml" in collected_files:
            return "pnpm"
        if "yarn.lock" in collected_files:
            return "yarn"
        if "package-lock.json" in collected_files or "package.json" in collected_files:
            return "npm"
        if "poetry.lock" in collected_files or "pyproject.toml" in collected_files:
            if "pyproject.toml" in collected_files and "[tool.poetry]" in collected_files["pyproject.toml"]:
                return "poetry"
            if "requirements.txt" in collected_files:
                return "pip"
        if "requirements.txt" in collected_files:
            return "pip"
        if "Cargo.toml" in collected_files:
            return "cargo"
        if "go.mod" in collected_files:
            return "go modules"
        if "pom.xml" in collected_files:
            return "maven"
        if "build.gradle" in collected_files:
            return "gradle"
        return None

    def detect_database(
        self, workspace_path: str, collected_files: Dict[str, str]
    ) -> Optional[str]:
        """Detect primary database technology from manifests and code."""
        combined_text = " ".join(collected_files.values()).lower()
        if any(term in combined_text for term in ["postgresql", "psycopg2", "asyncpg", "postgres"]):
            return "PostgreSQL"
        if any(term in combined_text for term in ["mysql", "pymysql"]):
            return "MySQL"
        if any(term in combined_text for term in ["sqlite3", "sqlite"]):
            return "SQLite"
        if any(term in combined_text for term in ["mongodb", "pymongo", "mongoose"]):
            return "MongoDB"
        if any(term in combined_text for term in ["redis", "ioredis"]):
            return "Redis"
        return None

    def detect_ai_stack(
        self, workspace_path: str, collected_files: Dict[str, str]
    ) -> List[TechnologyDetection]:
        """Detect AI, ML, and LLM libraries."""
        ai_libs: List[TechnologyDetection] = []
        combined_text = " ".join(collected_files.values()).lower()

        patterns = [
            ("google-genai", "Google GenAI SDK"),
            ("google.generativeai", "Google Generative AI"),
            ("openai", "OpenAI API"),
            ("langchain", "LangChain"),
            ("langgraph", "LangGraph"),
            ("llama_index", "LlamaIndex"),
            ("transformers", "Hugging Face Transformers"),
            ("torch", "PyTorch"),
            ("tensorflow", "TensorFlow"),
            ("anthropic", "Anthropic SDK"),
            ("chromadb", "ChromaDB"),
            ("pinecone", "Pinecone"),
        ]

        for match_str, display_name in patterns:
            if match_str in combined_text:
                ai_libs.append(
                    TechnologyDetection(
                        name=display_name, category="AI", detected_from=list(collected_files.keys()), confidence=1.0
                    )
                )

        return ai_libs

    def detect_entry_points(
        self, workspace_path: str, collected_files: Dict[str, str]
    ) -> List[EntryPoint]:
        """Detect application entry points using standard filenames and package manifests."""
        entry_points: List[EntryPoint] = []
        abs_workspace = os.path.abspath(workspace_path)

        candidate_paths = [
            "main.py",
            "app.py",
            "server.py",
            "manage.py",
            "index.js",
            "index.ts",
            "main.ts",
            "main.go",
            "app/main.py",
            "src/main.py",
            "src/index.js",
            "src/index.ts",
            "src/main.ts",
            "src/main.tsx",
            "src/App.tsx",
            "src/App.jsx",
        ]

        for rel in candidate_paths:
            full = os.path.join(abs_workspace, rel)
            if os.path.exists(full) and os.path.isfile(full):
                entry_points.append(
                    EntryPoint(path=rel, description="Standard entry point file", detected_from="Heuristic File Check")
                )

        # Check package.json main field
        if "package.json" in collected_files:
            content = collected_files["package.json"]
            match = re.search(r'"main"\s*:\s*"([^"]+)"', content)
            if match:
                main_path = match.group(1)
                if not any(e.path == main_path for e in entry_points):
                    entry_points.append(
                        EntryPoint(path=main_path, description="npm package main entry point", detected_from="package.json")
                    )

        return entry_points

    def _detect_orm(self, collected_files: Dict[str, str]) -> Optional[str]:
        combined_text = " ".join(collected_files.values()).lower()
        if "sqlmodel" in combined_text:
            return "SQLModel"
        if "sqlalchemy" in combined_text:
            return "SQLAlchemy"
        if "prisma" in combined_text:
            return "Prisma"
        if "typeorm" in combined_text:
            return "TypeORM"
        if "sequelize" in combined_text:
            return "Sequelize"
        return None

    def _detect_auth(self, collected_files: Dict[str, str]) -> Optional[str]:
        combined_text = " ".join(collected_files.values()).lower()
        if any(t in combined_text for t in ["pyjwt", "jwt", "python-jose"]):
            return "JWT"
        if "next-auth" in combined_text:
            return "NextAuth.js"
        if "passport" in combined_text:
            return "Passport.js"
        if "auth0" in combined_text:
            return "Auth0"
        return None

    def _detect_testing(self, collected_files: Dict[str, str]) -> List[str]:
        combined_text = " ".join(collected_files.values()).lower()
        frameworks = []
        if "pytest" in combined_text:
            frameworks.append("Pytest")
        if "unittest" in combined_text:
            frameworks.append("Unittest")
        if "jest" in combined_text:
            frameworks.append("Jest")
        if "vitest" in combined_text:
            frameworks.append("Vitest")
        return frameworks

    def _detect_deployment(self, collected_files: Dict[str, str]) -> Optional[str]:
        if "Dockerfile" in collected_files and ("docker-compose.yml" in collected_files or "compose.yaml" in collected_files):
            return "Docker & Docker Compose"
        if "Dockerfile" in collected_files:
            return "Docker"
        if "Procfile" in collected_files:
            return "Heroku / Procfile"
        return None

    def summarize_repository(
        self, workspace_path: str, heuristic_result: HeuristicAnalysisResult
    ) -> ProjectSummary:
        """Stage 2: Generate high-level summary and observations using LLMService.

        Args:
            workspace_path: Absolute path to workspace.
            heuristic_result: Structured result from Stage 1 heuristic scan.

        Returns:
            ProjectSummary validated Pydantic object.
        """
        project_name = os.path.basename(os.path.abspath(workspace_path)) or "Reflexion-Workspace"

        prompt = (
            f"Analyze the following repository heuristic scan data for project '{project_name}' and produce a comprehensive "
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
            f"Important Directories: {heuristic_result.important_directories}\n"
            f"Important Files: {heuristic_result.important_files}\n"
            f"Entry Points: {[ep.path for ep in heuristic_result.entry_points]}\n\n"
            "Collected File Previews:\n"
        )

        for filename, content in heuristic_result.collected_file_contents.items():
            preview = content[:800]
            prompt += f"\n--- File: {filename} ---\n{preview}\n"

        system_instruction = (
            "You are an expert software architect AI. Analyze the repository metadata and produce a precise, high-quality "
            "ProjectSummary structured output. Do NOT invent false dependencies. Rely on the provided heuristic data."
        )

        try:
            logger.info("Calling LLMService.generate_json for repository summarization...")
            llm_res = llm_service.generate_json(
                prompt=prompt,
                response_schema=LLMProjectSummaryResponse,
                system_instruction=system_instruction,
                temperature=0.1,
            )

            # Combine LLM findings with deterministic Stage 1 entry points and technologies
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
                important_directories=llm_res.important_directories or heuristic_result.important_directories,
                important_files=llm_res.important_files or heuristic_result.important_files,
                entry_points=heuristic_result.entry_points,
                technologies=heuristic_result.technologies,
                observations=llm_res.observations or [f"Analyzed {project_name} workspace."],
            )
        except Exception as e:
            logger.warning(
                f"LLM summarization failed or unconfigured: {e}. Falling back to deterministic heuristic summary."
            )

            # Fallback deterministic summary construction
            description = (
                f"{project_name} project utilizing {', '.join(heuristic_result.languages) or 'software engineering'} "
                f"and {', '.join(heuristic_result.frameworks) or 'standard application components'}."
            )

            architecture = "Monolithic / Standard Modular Application"
            if len(heuristic_result.important_directories) > 2 and any(
                d in heuristic_result.important_directories for d in ["frontend", "backend"]
            ):
                architecture = "Decoupled Client-Server Monorepo"

            observations = [
                f"Repository contains {len(heuristic_result.important_files)} critical configuration files.",
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
