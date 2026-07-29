"""File Prioritizer module.

Categorizes and ranks workspace files into a strict 10-tier priority model.
Ensures source implementation files (entry points, routes, services, models) are prioritized
above documentation and generic manifests.
"""

import os
import logging
from typing import List, Set

from app.schemas.repository import EntryPoint

logger = logging.getLogger("reflexion.analyzer.prioritizer")


class FilePrioritizer:
    """Classifies and sorts repository files by architectural importance."""

    def categorize_and_prioritize_files(
        self,
        all_files: List[str],
        entry_points: List[EntryPoint],
    ) -> List[str]:
        """Rank all workspace files into strict 10-tier priority model.

        Tiers:
        1. Entry Points
        2. API Routes
        3. Controllers
        4. Service Layer
        5. Business Logic / Core / Utilities
        6. Models
        7. Schemas
        8. Configuration
        9. Dependency Manifests
        10. Documentation
        """
        entry_paths: Set[str] = {ep.path for ep in entry_points}

        t1_entry_points: List[str] = []
        t2_api_routes: List[str] = []
        t3_controllers: List[str] = []
        t4_services: List[str] = []
        t5_core_utils: List[str] = []
        t6_models: List[str] = []
        t7_schemas: List[str] = []
        t8_config: List[str] = []
        t9_manifests: List[str] = []
        t10_docs: List[str] = []

        manifest_names = {
            "requirements.txt", "pyproject.toml", "setup.py", "package.json",
            "package-lock.json", "pnpm-lock.yaml", "yarn.lock", "Dockerfile",
            "docker-compose.yml", "compose.yaml", ".env.example", "Makefile",
            "Procfile", "go.mod", "Cargo.toml", "pom.xml", "build.gradle", "alembic.ini"
        }

        for file_path in all_files:
            lower_path = file_path.lower()
            fname = os.path.basename(file_path).lower()

            # Tier 1: Entry Points
            if file_path in entry_paths or fname in {"main.py", "app.py", "server.py", "index.js", "index.ts", "app.ts", "server.js", "main.go", "main.rs"}:
                t1_entry_points.append(file_path)
                continue

            # Tier 2: API Routes
            if any(term in lower_path for term in ["route", "api/", "/api", "endpoints", "router", "views.py", "urls.py"]):
                t2_api_routes.append(file_path)
                continue

            # Tier 3: Controllers
            if any(term in lower_path for term in ["controller", "handler"]):
                t3_controllers.append(file_path)
                continue

            # Tier 4: Service Layer
            if any(term in lower_path for term in ["service", "usecase", "logic"]):
                t4_services.append(file_path)
                continue

            # Tier 5: Core / Utilities
            if any(term in lower_path for term in ["core/", "utils/", "helpers/", "lib/", "common/"]):
                t5_core_utils.append(file_path)
                continue

            # Tier 6: Models
            if any(term in lower_path for term in ["model", "entity", "domain", "db/", "database"]):
                t6_models.append(file_path)
                continue

            # Tier 7: Schemas / DTOs
            if any(term in lower_path for term in ["schema", "dto"]):
                t7_schemas.append(file_path)
                continue

            # Tier 8: Configuration
            if any(term in lower_path for term in ["config", "settings", "tsconfig.json", "vite.config", "next.config"]):
                t8_config.append(file_path)
                continue

            # Tier 9: Manifests
            if fname in manifest_names:
                t9_manifests.append(file_path)
                continue

            # Tier 10: Documentation
            if fname.endswith(".md") or "docs/" in lower_path or fname in {"readme", "changelog", "license"}:
                t10_docs.append(file_path)
                continue

            # Remaining general source files default to Tier 5 (Business logic / source code)
            if any(file_path.endswith(ext) for ext in [".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".go", ".rs"]):
                t5_core_utils.append(file_path)
            else:
                t8_config.append(file_path)

        # Merge in strict order
        prioritized = (
            t1_entry_points
            + t2_api_routes
            + t3_controllers
            + t4_services
            + t5_core_utils
            + t6_models
            + t7_schemas
            + t8_config
            + t9_manifests
            + t10_docs
        )

        # Deduplicate preserving order
        seen = set()
        deduped = []
        for f in prioritized:
            if f not in seen:
                seen.add(f)
                deduped.append(f)

        return deduped
