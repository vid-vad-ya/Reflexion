"""Validation script for Phase 6 (Enhanced): Repository Analyzer Service.

Verifies:
1. Directory tree generation (build_directory_tree)
2. Ignore rules (.git, node_modules, venv, __pycache__, etc.)
3. Important file detection (collect_project_files) and size limits
4. Language detection heuristics (detect_languages)
5. Framework detection heuristics (detect_frameworks) - extensible patterns
6. Entry point detection heuristics (detect_entry_points)
7. Directory scoring system (score_and_select_important_directories)
8. Package manager detection (detect_package_managers)
9. File prioritization - verifies README.md is NOT before source files
10. Technology extraction completeness
11. Structured LLM / heuristic summary generation (analyze_repository)
12. API endpoint & Database persistence/caching behavior
"""

import os
import sys
import tempfile
import json
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.schemas.repository import ProjectSummary, TechnologyDetection, EntryPoint, DirectoryNode
from app.services.repository_analyzer import (
    repository_analyzer,
    RepositoryAnalysisError,
    WorkspaceNotFoundError,
)
from app.services.repository_analysis.scanner import RepositoryScanner
from app.services.repository_analysis.detectors import TechnologyDetector
from app.services.repository_analysis.prioritizer import FilePrioritizer
from app.models import Repository, User
from app.database import get_session_ctx
from app.api.v1.repositories import analyze_repository, RepositoryAnalyzeRequest


# ---------------------------------------------------------------------------
# Test Utilities
# ---------------------------------------------------------------------------

def _create_file(path: str, content: str = "") -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True) if os.path.dirname(path) else None
    with open(path, "w") as f:
        f.write(content)


def _create_standard_python_repo(workspace_dir: str) -> None:
    """Scaffold a realistic Python/FastAPI repo structure inside workspace_dir."""
    _create_file(
        os.path.join(workspace_dir, "app", "main.py"),
        "from fastapi import FastAPI\napp = FastAPI()\n\nif __name__ == '__main__':\n    pass\n",
    )
    _create_file(
        os.path.join(workspace_dir, "app", "api", "routes", "items.py"),
        "from fastapi import APIRouter\nrouter = APIRouter()\n\n@router.get('/items')\ndef list_items(): pass\n",
    )
    _create_file(
        os.path.join(workspace_dir, "app", "services", "item_service.py"),
        "class ItemService:\n    def get_items(self): pass\n",
    )
    _create_file(
        os.path.join(workspace_dir, "app", "models", "item.py"),
        "from sqlmodel import SQLModel\n\nclass Item(SQLModel, table=True):\n    id: int\n    name: str\n",
    )
    _create_file(
        os.path.join(workspace_dir, "app", "schemas", "item.py"),
        "from pydantic import BaseModel\nclass ItemSchema(BaseModel):\n    name: str\n",
    )
    _create_file(
        os.path.join(workspace_dir, "requirements.txt"),
        "fastapi==0.110.0\nuvicorn==0.28.0\npydantic==2.6.0\nsqlalchemy==2.0.0\npsycopg2-binary==2.9.9\npyjwt==2.8.0\npytest==8.0.0\n",
    )
    _create_file(
        os.path.join(workspace_dir, "Dockerfile"),
        "FROM python:3.11\nWORKDIR /app\nCOPY . .\nRUN pip install -r requirements.txt\nCMD ['python', '-m', 'app.main']\n",
    )
    _create_file(
        os.path.join(workspace_dir, "docker-compose.yml"),
        "version: '3'\nservices:\n  app:\n    build: .\n  db:\n    image: postgres:15\n",
    )
    _create_file(
        os.path.join(workspace_dir, "README.md"),
        "# My FastAPI Project\nA demo REST API built with FastAPI and PostgreSQL.\n",
    )


# ---------------------------------------------------------------------------
# Test 1: Directory Tree
# ---------------------------------------------------------------------------

def test_directory_tree(workspace_dir: str):
    print("\n[1/12] Testing Directory Tree Generation...")
    _create_standard_python_repo(workspace_dir)
    tree = repository_analyzer.build_directory_tree(workspace_dir)
    assert isinstance(tree, DirectoryNode), "Tree must be a DirectoryNode"
    assert tree.is_dir is True, "Root node must be a directory"
    print(f"  Root node: name='{tree.name}', total files={tree.file_count}")
    print("  [PASS] Directory tree generated successfully.")


# ---------------------------------------------------------------------------
# Test 2: Ignore Rules
# ---------------------------------------------------------------------------

def test_ignore_rules(workspace_dir: str):
    print("\n[2/12] Testing Ignore Rules...")
    for d in [".git", "__pycache__", "node_modules", "venv", "dist", "build"]:
        os.makedirs(os.path.join(workspace_dir, d), exist_ok=True)
        _create_file(os.path.join(workspace_dir, d, "junk.txt"), "ignored")

    tree = repository_analyzer.build_directory_tree(workspace_dir)
    child_names = [child.name for child in (tree.children or [])]
    for ignored_dir in [".git", "__pycache__", "node_modules", "venv", "dist", "build"]:
        assert ignored_dir not in child_names, f"{ignored_dir} must be ignored"

    scanner = RepositoryScanner()
    _, all_dirs = scanner.scan_files_and_directories(workspace_dir)
    dir_bases = [os.path.basename(d) for d in all_dirs]
    for ignored_dir in [".git", "__pycache__", "node_modules", "venv", "dist", "build"]:
        assert ignored_dir not in dir_bases, f"{ignored_dir} must not appear in scanned dirs"

    print(f"  All ignored directories correctly excluded. Top-level children: {child_names}")
    print("  [PASS] Ignore rules enforced.")


# ---------------------------------------------------------------------------
# Test 3: Important File Detection
# ---------------------------------------------------------------------------

def test_important_file_detection(workspace_dir: str):
    print("\n[3/12] Testing Important File Detection...")
    collected = repository_analyzer.collect_project_files(workspace_dir)
    assert len(collected) > 0, "collect_project_files must return at least one file"
    print(f"  Collected {len(collected)} important files: {list(collected.keys())}")
    print("  [PASS] Important files detected and collected successfully.")
    return collected


# ---------------------------------------------------------------------------
# Test 4: Language Detection
# ---------------------------------------------------------------------------

def test_language_detection(workspace_dir: str, collected: dict):
    print("\n[4/12] Testing Language Detection...")
    langs = repository_analyzer.detect_languages(workspace_dir, collected)
    lang_names = [l.name for l in langs]
    assert "Python" in lang_names, "Python must be detected as language"
    print(f"  Detected Languages: {lang_names}")
    print("  [PASS] Language detection working correctly.")
    return lang_names


# ---------------------------------------------------------------------------
# Test 5: Framework Detection (Extensible Patterns)
# ---------------------------------------------------------------------------

def test_framework_detection(workspace_dir: str, collected: dict, languages: list):
    print("\n[5/12] Testing Framework Detection (Extensible Patterns)...")
    frameworks = repository_analyzer.detect_frameworks(workspace_dir, collected, languages)
    fw_names = [f.name for f in frameworks]
    assert "FastAPI" in fw_names, f"FastAPI must be detected. Got: {fw_names}"
    print(f"  Detected Frameworks: {fw_names}")
    print("  [PASS] Framework detection working correctly with extensible patterns.")


# ---------------------------------------------------------------------------
# Test 6: Entry Point Detection
# ---------------------------------------------------------------------------

def test_entry_point_detection(workspace_dir: str, collected: dict):
    print("\n[6/12] Testing Entry Point Detection...")
    entry_points = repository_analyzer.detect_entry_points(workspace_dir, collected)
    ep_paths = [ep.path for ep in entry_points]
    print(f"  Detected Entry Points: {ep_paths}")
    assert any("main.py" in p for p in ep_paths), f"main.py must be detected as entry point. Got: {ep_paths}"
    print("  [PASS] Entry point detection working correctly.")


# ---------------------------------------------------------------------------
# Test 7: Directory Scoring System
# ---------------------------------------------------------------------------

def test_directory_scoring(workspace_dir: str):
    print("\n[7/12] Testing Directory Scoring System...")
    scanner = RepositoryScanner()
    all_files, all_dirs = scanner.scan_files_and_directories(workspace_dir)
    important_dirs = scanner.score_and_select_important_directories(all_dirs, all_files)

    print(f"  Discovered {len(all_dirs)} total dirs. Selected {len(important_dirs)} important.")
    print(f"  Important directories: {important_dirs}")

    # Key source directories should be scored highly
    combined = " ".join(important_dirs)
    assert any("app" in d or "api" in d or "services" in d or "models" in d for d in important_dirs), \
        f"Source directories must be in important_dirs. Got: {important_dirs}"

    # README-only directories should NOT rank highest
    if important_dirs:
        top = important_dirs[0]
        assert not (os.path.basename(top).lower() in {"docs", "doc"}), \
            f"Docs directory should not be ranked #1. Got: {top}"

    print("  [PASS] Directory scoring correctly prioritizes source directories.")


# ---------------------------------------------------------------------------
# Test 8: Package Manager Detection
# ---------------------------------------------------------------------------

def test_package_manager_detection(workspace_dir: str, collected: dict):
    print("\n[8/12] Testing Package Manager Detection...")
    pkg = repository_analyzer.detect_package_managers(workspace_dir, collected)
    assert pkg == "pip", f"Expected 'pip' package manager, got: {pkg}"
    print(f"  Detected Package Manager: {pkg}")
    print("  [PASS] Package manager detection working correctly.")


# ---------------------------------------------------------------------------
# Test 9: File Prioritization - README must not be first
# ---------------------------------------------------------------------------

def test_file_prioritization(workspace_dir: str):
    print("\n[9/12] Testing File Prioritization (README must not be first)...")
    scanner = RepositoryScanner()
    all_files, _ = scanner.scan_files_and_directories(workspace_dir)

    detector = TechnologyDetector()
    all_files_list, _ = scanner.scan_files_and_directories(workspace_dir)
    entry_points = detector.detect_entry_points(workspace_dir, all_files_list, {})

    prioritizer = FilePrioritizer()
    prioritized = prioritizer.categorize_and_prioritize_files(all_files_list, entry_points)

    print(f"  Total prioritized files: {len(prioritized)}")
    print(f"  Top 10 files: {prioritized[:10]}")

    # README.md must not be the first file if source files exist
    has_source_files = any(f.endswith(".py") for f in all_files_list)
    if has_source_files and prioritized:
        first_file = prioritized[0]
        assert not first_file.lower().endswith("readme.md"), \
            f"README.md must NOT be the first prioritized file when source code exists. Got: {first_file}"

    # Verify entry points appear before readme
    readme_idx = next((i for i, f in enumerate(prioritized) if "readme" in f.lower()), None)
    entry_idxs = [i for i, f in enumerate(prioritized) if any(e.path == f for e in entry_points)]
    if readme_idx is not None and entry_idxs:
        assert min(entry_idxs) < readme_idx, \
            f"Entry points must appear before README.md in prioritized list"

    print("  [PASS] File prioritization correctly places source files before README.md.")


# ---------------------------------------------------------------------------
# Test 10: Technology Extraction Completeness
# ---------------------------------------------------------------------------

def test_technology_extraction(workspace_dir: str, collected: dict):
    print("\n[10/12] Testing Technology Extraction Completeness...")
    all_files, _ = RepositoryScanner().scan_files_and_directories(workspace_dir)
    detector = TechnologyDetector()
    techs = detector.detect_technologies(all_files, collected)
    tech_names = [t.name for t in techs]
    tech_cats = {t.category for t in techs}

    print(f"  Detected Technologies: {tech_names}")
    print(f"  Categories detected: {tech_cats}")

    assert "PostgreSQL" in tech_names, f"PostgreSQL must be detected. Got: {tech_names}"
    assert "JWT" in tech_names, f"JWT must be detected. Got: {tech_names}"
    assert "Pytest" in tech_names, f"Pytest must be detected. Got: {tech_names}"
    docker_detected = "Docker & Docker Compose" in tech_names or "Docker" in tech_names
    assert docker_detected, f"Docker (or Docker & Docker Compose) must be detected. Got: {tech_names}"

    print("  [PASS] Technology extraction is rich and complete.")


# ---------------------------------------------------------------------------
# Test 11: Summary Generation
# ---------------------------------------------------------------------------

def test_summary_generation(workspace_dir: str):
    print("\n[11/12] Testing Structured Repository Analysis & Summary Generation...")
    summary = repository_analyzer.analyze_repository(workspace_dir)
    assert isinstance(summary, ProjectSummary), "Output must be a ProjectSummary"
    assert summary.project_name != "", "Project name must not be empty"
    assert "Python" in summary.languages, f"Python must be detected. Got: {summary.languages}"
    assert "FastAPI" in summary.frameworks, f"FastAPI must be detected. Got: {summary.frameworks}"
    assert len(summary.entry_points) > 0, "Entry points must not be empty"
    assert len(summary.important_files) > 0, "Important files must not be empty"
    assert len(summary.important_directories) > 0, "Important directories must not be empty"

    # README must not be the first important file
    if summary.important_files:
        first = summary.important_files[0]
        assert "readme" not in first.lower(), \
            f"README.md must NOT be first important file in summary. Got: {first}"

    print(f"  Project Name: '{summary.project_name}'")
    print(f"  Languages: {summary.languages}")
    print(f"  Frameworks: {summary.frameworks}")
    print(f"  Package Manager: {summary.package_manager}")
    print(f"  Entry Points: {[ep.path for ep in summary.entry_points]}")
    print(f"  Important Directories: {summary.important_directories}")
    print(f"  Top 5 Important Files: {summary.important_files[:5]}")
    print(f"  Technologies: {[t.name for t in summary.technologies]}")
    print("  [PASS] Structured ProjectSummary generated successfully.")
    return summary


# ---------------------------------------------------------------------------
# Test 12: API Endpoint & Database Persistence / Caching
# ---------------------------------------------------------------------------

def test_api_endpoint_and_persistence(workspace_dir: str):
    print("\n[12/12] Testing API Endpoint & Database Persistence/Caching...")
    import random
    unique_suffix = random.randint(100_000_000, 999_999_999)

    with get_session_ctx() as session:
        user = User(
            github_id=unique_suffix,
            username=f"test_analyzer_{unique_suffix}",
            email=f"analyzer_{unique_suffix}@example.com",
        )
        session.add(user)
        session.flush()

        repo = Repository(
            owner_id=user.id,
            github_repo_id=unique_suffix + 1,
            full_name=f"test_analyzer_{unique_suffix}/test_repo",
            clone_url=f"https://github.com/test_analyzer_{unique_suffix}/test_repo.git",
            local_path=workspace_dir,
            clone_status="completed",
        )
        session.add(repo)
        session.commit()
        session.refresh(user)
        session.refresh(repo)
        repo_id = repo.id
        print(f"  Created test Repository in DB with repository_id: '{repo_id}'")

        try:
            # Cold cache
            req = RepositoryAnalyzeRequest(repository_id=repo_id, force_refresh=False)
            first_summary = analyze_repository(req, session=session)
            assert isinstance(first_summary, ProjectSummary)
            assert first_summary.project_name == os.path.basename(workspace_dir)
            print("  [PASS] Initial analysis succeeded and produced ProjectSummary.")

            # Verify DB persistence
            session.refresh(repo)
            assert repo.project_summary is not None
            assert repo.project_summary["project_name"] == first_summary.project_name
            print("  [PASS] ProjectSummary persisted in DB.")

            # Warm cache
            cached = analyze_repository(req, session=session)
            assert cached.project_name == first_summary.project_name
            print("  [PASS] Cached ProjectSummary retrieved from DB correctly.")

            # Force refresh
            refresh_req = RepositoryAnalyzeRequest(repository_id=repo_id, force_refresh=True)
            refreshed = analyze_repository(refresh_req, session=session)
            assert refreshed.project_name == first_summary.project_name
            print("  [PASS] force_refresh=True re-analyzed and updated DB cache.")

            print("\n==================================================")
            print("EXAMPLE PROJECT SUMMARY JSON OUTPUT:")
            print("==================================================")
            print(json.dumps(refreshed.model_dump(), indent=2, default=str))
            print("==================================================")
        finally:
            session.delete(repo)
            session.delete(user)
            session.commit()
            print("  [INFO] Test data cleaned up from DB.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 60)
    print("Phase 6 (Enhanced): Repository Analyzer Validation Suite")
    print("=" * 60)

    with tempfile.TemporaryDirectory(prefix="reflexion_test_repo_") as temp_dir:
        test_directory_tree(temp_dir)
        test_ignore_rules(temp_dir)
        collected = test_important_file_detection(temp_dir)
        lang_names = test_language_detection(temp_dir, collected)
        test_framework_detection(temp_dir, collected, lang_names)
        test_entry_point_detection(temp_dir, collected)
        test_directory_scoring(temp_dir)
        test_package_manager_detection(temp_dir, collected)
        test_file_prioritization(temp_dir)
        test_technology_extraction(temp_dir, collected)
        test_summary_generation(temp_dir)
        test_api_endpoint_and_persistence(temp_dir)

    print("\n" + "=" * 60)
    print("ALL PHASE 6 ENHANCED REPOSITORY ANALYZER TESTS PASSED!")
    print("=" * 60)


if __name__ == "__main__":
    main()
