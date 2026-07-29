"""Technology and Entry Point Detector module.

Iterates over configurable pattern definitions to identify languages, frameworks, package managers,
databases, ORMs, authentication, AI stacks, testing, deployment, and entry points.
"""

import os
import re
import logging
from typing import Dict, List, Optional, Set

from app.schemas.repository import EntryPoint, TechnologyDetection
from app.services.repository_analysis.constants import (
    ENTRY_POINT_PATTERNS,
    FRAMEWORK_PATTERNS,
    LANGUAGE_EXTENSION_MAP,
    PACKAGE_MANAGER_PATTERNS,
    TECHNOLOGY_PATTERNS,
)

logger = logging.getLogger("reflexion.analyzer.detectors")


class TechnologyDetector:
    """Extensible detector engine driven by declarative pattern objects."""

    def detect_languages(
        self, all_files: List[str], manifest_contents: Dict[str, str]
    ) -> List[TechnologyDetection]:
        """Detect programming languages based on file extension counts and package manifests."""
        detected_counts: Dict[str, int] = {}

        for rel_file in all_files:
            ext = os.path.splitext(rel_file)[1].lower()
            if ext in LANGUAGE_EXTENSION_MAP:
                lang = LANGUAGE_EXTENSION_MAP[ext]
                detected_counts[lang] = detected_counts.get(lang, 0) + 1

        # Manifest weights
        combined_manifests = " ".join(manifest_contents.values())
        if any(m in manifest_contents for m in ["pyproject.toml", "requirements.txt", "setup.py"]):
            detected_counts["Python"] = detected_counts.get("Python", 0) + 10
        if any(m in manifest_contents for m in ["package.json"]):
            detected_counts["JavaScript"] = detected_counts.get("JavaScript", 0) + 10
        if "tsconfig.json" in manifest_contents:
            detected_counts["TypeScript"] = detected_counts.get("TypeScript", 0) + 10
        if "go.mod" in manifest_contents:
            detected_counts["Go"] = detected_counts.get("Go", 0) + 10
        if "Cargo.toml" in manifest_contents:
            detected_counts["Rust"] = detected_counts.get("Rust", 0) + 10
        if any(m in manifest_contents for m in ["pom.xml", "build.gradle"]):
            detected_counts["Java"] = detected_counts.get("Java", 0) + 10

        results: List[TechnologyDetection] = []
        for lang in sorted(detected_counts.keys(), key=lambda x: detected_counts[x], reverse=True):
            results.append(
                TechnologyDetection(
                    name=lang,
                    category="Language",
                    detected_from=list(manifest_contents.keys()),
                    confidence=1.0,
                )
            )
        return results

    def detect_frameworks(
        self,
        all_files: List[str],
        manifest_contents: Dict[str, str],
        languages: List[str],
    ) -> List[TechnologyDetection]:
        """Detect web and application frameworks using pattern definitions."""
        frameworks: List[TechnologyDetection] = []
        combined_text = " ".join(manifest_contents.values()).lower()

        for pattern in FRAMEWORK_PATTERNS:
            fw_name = pattern["name"]
            req_languages = pattern.get("languages", [])

            # Check if language matches (or if no language specified)
            if req_languages and not any(lang in languages for lang in req_languages):
                continue

            detected = False
            evidence: List[str] = []

            # Check file indicators
            for file_ind in pattern.get("file_indicators", []):
                if any(f == file_ind or f.endswith("/" + file_ind) for f in all_files):
                    detected = True
                    evidence.append(file_ind)

            # Check keywords in manifests
            if not detected:
                for kw in pattern.get("keywords", []):
                    if kw.lower() in combined_text:
                        detected = True
                        evidence.append(f"Keyword '{kw}' in manifest")
                        break

            if detected:
                frameworks.append(
                    TechnologyDetection(
                        name=fw_name,
                        category="Framework",
                        detected_from=evidence or list(manifest_contents.keys()),
                        confidence=pattern.get("confidence", 1.0),
                    )
                )

        return frameworks

    def detect_package_managers(
        self, all_files: List[str], manifest_contents: Dict[str, str]
    ) -> Optional[str]:
        """Detect primary package manager using declarative manifest patterns."""
        for pattern in PACKAGE_MANAGER_PATTERNS:
            name = pattern["name"]
            target_files = pattern["files"]

            # Check file presence
            for tf in target_files:
                if tf in manifest_contents or any(f == tf or f.endswith("/" + tf) for f in all_files):
                    # Check optional toml section
                    toml_sec = pattern.get("toml_section")
                    if toml_sec and tf in manifest_contents:
                        if toml_sec in manifest_contents[tf]:
                            return name
                    else:
                        return name

        return None

    def detect_entry_points(
        self, workspace_path: str, all_files: List[str], manifest_contents: Dict[str, str]
    ) -> List[EntryPoint]:
        """Detect application entry points using pattern definitions and file contents."""
        entry_points: List[EntryPoint] = []
        seen_paths: Set[str] = set()

        abs_workspace = os.path.abspath(workspace_path)

        # 1. Match against ENTRY_POINT_PATTERNS
        for pattern in ENTRY_POINT_PATTERNS:
            candidate_rel = pattern["name"]

            # Check if file exists in all_files or on disk
            full_path = os.path.join(abs_workspace, candidate_rel)
            if candidate_rel in all_files or os.path.isfile(full_path):
                if candidate_rel not in seen_paths:
                    seen_paths.add(candidate_rel)
                    entry_points.append(
                        EntryPoint(
                            path=candidate_rel,
                            description=pattern["description"],
                            detected_from=f"Deterministic Pattern: {pattern['language']}",
                        )
                    )

        # 2. Check package.json main & scripts
        if "package.json" in manifest_contents:
            content = manifest_contents["package.json"]
            match = re.search(r'"main"\s*:\s*"([^"]+)"', content)
            if match:
                main_path = match.group(1).replace("\\", "/")
                if main_path not in seen_paths:
                    seen_paths.add(main_path)
                    entry_points.append(
                        EntryPoint(
                            path=main_path,
                            description="npm package main entry point",
                            detected_from="package.json 'main' field",
                        )
                    )

        # 3. Code level indicators for Python (if __name__ == '__main__' or FastAPI/Flask app)
        python_files = [f for f in all_files if f.endswith(".py") and f.count("/") <= 2]
        for py_file in python_files:
            if py_file in seen_paths:
                continue
            full_p = os.path.join(abs_workspace, py_file)
            try:
                if os.path.exists(full_p) and os.path.getsize(full_p) < 50_000:
                    with open(full_p, "r", encoding="utf-8", errors="ignore") as f:
                        code = f.read()
                        if '__name__' in code and '__main__' in code:
                            seen_paths.add(py_file)
                            entry_points.append(
                                EntryPoint(
                                    path=py_file,
                                    description="Python script with __main__ execution block",
                                    detected_from="Source Code Analysis",
                                )
                            )
            except Exception:
                pass

        # 4. Java @SpringBootApplication or main method
        java_files = [f for f in all_files if f.endswith(".java")]
        for j_file in java_files:
            if j_file in seen_paths:
                continue
            full_j = os.path.join(abs_workspace, j_file)
            try:
                if os.path.exists(full_j) and os.path.getsize(full_j) < 50_000:
                    with open(full_j, "r", encoding="utf-8", errors="ignore") as f:
                        code = f.read()
                        if "@SpringBootApplication" in code or "public static void main" in code:
                            seen_paths.add(j_file)
                            entry_points.append(
                                EntryPoint(
                                    path=j_file,
                                    description="Java Application main entry point",
                                    detected_from="Java Annotations / Main Method",
                                )
                            )
            except Exception:
                pass

        return entry_points

    def detect_technologies(
        self, all_files: List[str], manifest_contents: Dict[str, str]
    ) -> List[TechnologyDetection]:
        """Detect database, ORM, Auth, AI, Testing, and Deployment technology objects."""
        techs: List[TechnologyDetection] = []
        combined_text = " ".join(manifest_contents.values()).lower()

        for pattern in TECHNOLOGY_PATTERNS:
            name = pattern["name"]
            category = pattern["category"]
            keywords = pattern.get("keywords", [])
            target_files = pattern.get("files", [])
            confidence = pattern.get("confidence", 0.9)

            detected = False
            evidence: List[str] = []

            # Check file presence — use all() when match_all=True, any() otherwise
            if target_files:
                match_all = pattern.get("match_all", False)
                files_present = [
                    tf for tf in target_files
                    if tf in manifest_contents or any(f == tf or f.endswith("/" + tf) for f in all_files)
                ]
                if match_all:
                    if len(files_present) == len(target_files):
                        detected = True
                        evidence.extend(files_present)
                else:
                    if files_present:
                        detected = True
                        evidence.extend(files_present)

            # Check keywords in manifest contents
            if not detected and keywords:
                for kw in keywords:
                    if kw.lower() in combined_text:
                        detected = True
                        evidence.append(f"Keyword '{kw}'")
                        break

            if detected:
                techs.append(
                    TechnologyDetection(
                        name=name,
                        category=category,
                        detected_from=evidence or list(manifest_contents.keys()),
                        confidence=confidence,
                    )
                )

        # Deduplicate: for categories that should have only one entry (Deployment, Database, ORM, Authentication)
        # keep the first (highest confidence, most specific) match per category.
        single_entry_categories = {"Deployment", "Database", "ORM", "Authentication"}
        seen_cats: set = set()
        deduped_techs: List[TechnologyDetection] = []
        for t in techs:
            if t.category in single_entry_categories:
                if t.category not in seen_cats:
                    seen_cats.add(t.category)
                    deduped_techs.append(t)
            else:
                deduped_techs.append(t)

        return deduped_techs
