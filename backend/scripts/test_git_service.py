"""Validation script for Phase 5: Repository Workspace & Git Service Architecture.

Verifies:
1. Workspace root directory creation.
2. Cloning a public repository.
3. Existing repository detection (already_exists=True).
4. Robust current branch retrieval.
5. Exception handling for invalid repository URLs.
"""

import sys
import os

# Ensure backend directory is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.git_service import (
    git_service,
    GitServiceError,
    RepositoryNotFoundError,
    InvalidRepositoryURLError,
)
from app.core.config import settings


def main():
    print("==================================================")
    print("Phase 5: Git Service Architecture Validation")
    print("==================================================")

    # 1. Verify Workspace Directory Creation
    print("\n[1/5] Verifying Workspace Directory Creation...")
    print(f"  Target Workspace Root: '{git_service.workspace_dir}'")
    try:
        git_service._ensure_workspace_root()
        assert os.path.exists(git_service.workspace_dir), "Workspace directory must exist"
        print("  [PASS] Workspace directory created/verified successfully.")
    except Exception as e:
        print(f"  [FAIL] Workspace creation failed: {e}")
        sys.exit(1)

    # Test Repo details
    test_url = "https://github.com/octocat/Hello-World.git"
    test_owner = "octocat"
    test_repo = "Hello-World"

    # 2. Clone Public Repository
    print(f"\n[2/5] Testing clone_repository() for '{test_owner}/{test_repo}'...")
    print(f"  URL: {test_url}")
    try:
        result = git_service.clone_repository(
            repository_url=test_url,
            repository_name=test_repo,
            owner=test_owner,
        )
        print(f"  Clone Result: {result}")
        assert result["status"] == "success", "Status must be success"
        assert os.path.exists(result["workspace"]), "Workspace path must exist"
        assert isinstance(result["default_branch"], str), "Default branch must be string"
        print(f"  [PASS] Repository cloned successfully [Branch: {result['default_branch']}].")
        workspace_path = result["workspace"]
    except GitServiceError as e:
        print(f"  [FAIL] Clone failed with GitServiceError: {e}")
        sys.exit(1)

    # 3. Detect Existing Repository on Re-clone
    print("\n[3/5] Testing existing repository detection (repeat clone)...")
    try:
        reclone_result = git_service.clone_repository(
            repository_url=test_url,
            repository_name=test_repo,
            owner=test_owner,
        )
        print(f"  Re-clone Result: {reclone_result}")
        assert reclone_result["already_exists"] is True, "already_exists must be True on repeat clone"
        assert reclone_result["workspace"] == workspace_path
        print("  [PASS] Existing repository detected successfully without recloning.")
    except GitServiceError as e:
        print(f"  [FAIL] Repeat clone failed: {e}")
        sys.exit(1)

    # 4. Test Current Branch Retrieval
    print("\n[4/5] Testing get_current_branch()...")
    try:
        current_branch = git_service.get_current_branch(workspace_path)
        print(f"  Detected Active Branch: '{current_branch}'")
        assert current_branch == reclone_result["default_branch"], "Branch name mismatch"
        print("  [PASS] Current branch retrieved successfully.")
    except GitServiceError as e:
        print(f"  [FAIL] Branch retrieval failed: {e}")
        sys.exit(1)

    # 5. Exception Handling for Invalid Repository URL
    print("\n[5/5] Testing exception handling for invalid/non-existent repository URL...")
    invalid_url = "https://github.com/invalid_owner_9999999/nonexistent_repo_8888888.git"
    try:
        git_service.clone_repository(
            repository_url=invalid_url,
            repository_name="nonexistent_repo_8888888",
            owner="invalid_owner_9999999",
        )
        print("  [FAIL] Should have raised RepositoryNotFoundError or InvalidRepositoryURLError")
        sys.exit(1)
    except (RepositoryNotFoundError, InvalidRepositoryURLError, GitServiceError) as e:
        print(f"  [PASS] Caught expected exception: {e}")

    print("\n==================================================")
    print("ALL PHASE 5 GIT SERVICE VALIDATION TESTS PASSED!")
    print("==================================================")


if __name__ == "__main__":
    main()
