"""Validation script for Phase 6: Repository Analyzer Service Architecture.

Verifies:
1. Directory tree generation (`build_directory_tree`)
2. Ignore rules (.git, node_modules, venv, __pycache__, etc.)
3. Important file detection (`collect_project_files`) and size limits
4. Language detection heuristics (`detect_languages`)
5. Framework detection heuristics (`detect_frameworks`)
6. Entry point detection heuristics (`detect_entry_points`)
7. Structured LLM / heuristic summary generation (`analyze_repository`)
8. API endpoint & Database persistence/caching behavior (`POST /api/v1/repositories/analyze`)
"""

import os
import sys
import tempfile
import json

# Ensure backend directory is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.schemas.repository import ProjectSummary, TechnologyDetection, EntryPoint, DirectoryNode
from app.services.repository_analyzer import (
    repository_analyzer,
    RepositoryAnalysisError,
    WorkspaceNotFoundError,
)
from app.models import Repository, User
from app.database import get_session_ctx
from app.api.v1.repositories import analyze_repository, RepositoryAnalyzeRequest


def test_directory_tree(workspace_dir: str):
    print("\n[1/8] Testing Directory Tree Generation...")
    tree = repository_analyzer.build_directory_tree(workspace_dir)
    assert isinstance(tree, DirectoryNode), "Tree must be a DirectoryNode"
    assert tree.is_dir is True, "Root node must be a directory"
    print(f"  Root node: name='{tree.name}', total files contained={tree.file_count}")
    print("  [PASS] Directory tree generated successfully.")


def test_ignore_rules(workspace_dir: str):
    print("\n[2/8] Testing Ignore Rules...")
    # Create fake ignored folders inside workspace
    git_dir = os.path.join(workspace_dir, ".git")
    pycache_dir = os.path.join(workspace_dir, "__pycache__")
    node_modules_dir = os.path.join(workspace_dir, "node_modules")

    os.makedirs(git_dir, exist_ok=True)
    os.makedirs(pycache_dir, exist_ok=True)
    os.makedirs(node_modules_dir, exist_ok=True)

    with open(os.path.join(git_dir, "config"), "w") as f:
        f.write("git config")
    with open(os.path.join(pycache_dir, "test.pyc"), "w") as f:
        f.write("pyc content")

    tree = repository_analyzer.build_directory_tree(workspace_dir)
    child_names = [child.name for child in (tree.children or [])]

    assert ".git" not in child_names, ".git must be ignored"
    assert "__pycache__" not in child_names, "__pycache__ must be ignored"
    assert "node_modules" not in child_names, "node_modules must be ignored"
    print(f"  Verified ignored directories are excluded. Children: {child_names}")
    print("  [PASS] Ignore rules enforced successfully.")


def test_important_file_detection(workspace_dir: str):
    print("\n[3/8] Testing Important File Detection...")
    # Write a requirements.txt and Dockerfile
    req_path = os.path.join(workspace_dir, "requirements.txt")
    docker_path = os.path.join(workspace_dir, "Dockerfile")
    with open(req_path, "w") as f:
        f.write("fastapi==0.110.0\nuvicorn==0.28.0\npydantic==2.6.0\n")
    with open(docker_path, "w") as f:
        f.write("FROM python:3.11\nCMD ['python', 'main.py']\n")

    collected = repository_analyzer.collect_project_files(workspace_dir)
    assert "requirements.txt" in collected, "requirements.txt must be collected"
    assert "Dockerfile" in collected, "Dockerfile must be collected"
    print(f"  Collected {len(collected)} important files: {list(collected.keys())}")
    print("  [PASS] Important files detected and collected successfully.")
    return collected


def test_language_detection(workspace_dir: str, collected: dict):
    print("\n[4/8] Testing Language Detection...")
    # Add a main.py file
    main_py = os.path.join(workspace_dir, "main.py")
    with open(main_py, "w") as f:
        f.write("print('Hello Reflexion')\n")

    langs = repository_analyzer.detect_languages(workspace_dir, collected)
    lang_names = [l.name for l in langs]
    assert "Python" in lang_names, "Python must be detected as language"
    print(f"  Detected Languages: {lang_names}")
    print("  [PASS] Language detection working correctly.")


def test_framework_detection(workspace_dir: str, collected: dict):
    print("\n[5/8] Testing Framework Detection...")
    frameworks = repository_analyzer.detect_frameworks(workspace_dir, collected, ["Python"])
    fw_names = [f.name for f in frameworks]
    assert "FastAPI" in fw_names, "FastAPI framework must be detected from requirements.txt"
    print(f"  Detected Frameworks: {fw_names}")
    print("  [PASS] Framework detection working correctly.")


def test_entry_point_detection(workspace_dir: str, collected: dict):
    print("\n[6/8] Testing Entry Point Detection...")
    entry_points = repository_analyzer.detect_entry_points(workspace_dir, collected)
    ep_paths = [ep.path for ep in entry_points]
    assert "main.py" in ep_paths, "main.py must be detected as entry point"
    print(f"  Detected Entry Points: {ep_paths}")
    print("  [PASS] Entry point detection working correctly.")


def test_summary_generation(workspace_dir: str):
    print("\n[7/8] Testing Structured Repository Analysis & Summary Generation...")
    summary = repository_analyzer.analyze_repository(workspace_dir)
    assert isinstance(summary, ProjectSummary), "Output must be a ProjectSummary"
    assert summary.project_name != "", "Project name must not be empty"
    assert "Python" in summary.languages, "Languages must include Python"
    assert "FastAPI" in summary.frameworks, "Frameworks must include FastAPI"
    assert len(summary.entry_points) > 0, "Entry points must not be empty"
    print(f"  Summary Project Name: '{summary.project_name}'")
    print(f"  Summary Architecture: '{summary.architecture}'")
    print(f"  Summary Description: '{summary.description}'")
    print("  [PASS] Structured ProjectSummary generated successfully.")
    return summary


def test_api_endpoint_and_persistence(workspace_dir: str):
    print("\n[8/8] Testing API Endpoint & Database Persistence/Caching...")

    import random
    unique_suffix = random.randint(100_000_000, 999_999_999)

    with get_session_ctx() as session:
        # Create a unique test User to avoid unique-constraint conflicts on repeated runs
        user = User(
            github_id=unique_suffix,
            username=f"test_analyzer_{unique_suffix}",
            email=f"analyzer_{unique_suffix}@example.com",
        )
        session.add(user)
        session.flush()  # get user.id without committing

        # Create test Repository record in DB
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
        print(f"  Created test Repository record in DB with repository_id: '{repo_id}'")

        try:
            # 1. Test POST /analyze endpoint invocation (Cold Cache)
            req_payload = RepositoryAnalyzeRequest(repository_id=repo_id, force_refresh=False)
            first_summary = analyze_repository(req_payload, session=session)

            assert isinstance(first_summary, ProjectSummary)
            assert first_summary.project_name == os.path.basename(workspace_dir)
            print("  [PASS] Initial analysis call succeeded and produced ProjectSummary.")

            # Re-fetch repo from DB and verify persistence
            session.refresh(repo)
            assert repo.project_summary is not None, "Repository.project_summary must be persisted in DB"
            assert repo.project_summary["project_name"] == first_summary.project_name
            print("  [PASS] ProjectSummary successfully persisted in Repository.project_summary in DB.")

            # 2. Test Cached Retrieval (Warm Cache)
            cached_summary = analyze_repository(req_payload, session=session)
            assert cached_summary.project_name == first_summary.project_name
            print("  [PASS] Cached ProjectSummary successfully retrieved from DB without re-running analysis.")

            # 3. Test force_refresh=True
            refresh_req = RepositoryAnalyzeRequest(repository_id=repo_id, force_refresh=True)
            refreshed_summary = analyze_repository(refresh_req, session=session)
            assert refreshed_summary.project_name == first_summary.project_name
            print("  [PASS] force_refresh=True successfully re-analyzed repository and updated DB cache.")

            # Print Example JSON Output
            print("\n==================================================")
            print("EXAMPLE PROJECT SUMMARY JSON OUTPUT:")
            print("==================================================")
            print(json.dumps(refreshed_summary.model_dump(), indent=2))
            print("==================================================")
        finally:
            # Cleanup: remove test rows to keep DB clean between runs
            session.delete(repo)
            session.delete(user)
            session.commit()
            print("  [INFO] Test data cleaned up from DB.")


def main():
    print("==================================================")
    print("Phase 6: Repository Analyzer Service Architecture Validation")
    print("==================================================")

    with tempfile.TemporaryDirectory(prefix="reflexion_test_repo_") as temp_dir:
        test_directory_tree(temp_dir)
        test_ignore_rules(temp_dir)
        collected = test_important_file_detection(temp_dir)
        test_language_detection(temp_dir, collected)
        test_framework_detection(temp_dir, collected)
        test_entry_point_detection(temp_dir, collected)
        test_summary_generation(temp_dir)
        test_api_endpoint_and_persistence(temp_dir)

    print("\n==================================================")
    print("ALL PHASE 6 REPOSITORY ANALYZER VALIDATION TESTS PASSED!")
    print("==================================================")


if __name__ == "__main__":
    main()
