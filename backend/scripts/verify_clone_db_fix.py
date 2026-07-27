"""Manual integration verification for the Phase 5 bug fix.

Verifies that POST /api/v1/repositories/clone now:
1. Clones the repository to disk.
2. Creates a Repository DB row with all required fields populated.
3. Returns repository_id in the response.
4. POST /api/v1/repositories/analyze succeeds using that repository_id.

Run from the backend directory:
    python scripts/verify_clone_db_fix.py
"""

import os
import sys
import json
import uuid

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlmodel import select
from app.database import get_session_ctx
from app.models import Repository, User
from app.api.v1.repositories import (
    clone_repository,
    analyze_repository,
    RepositoryCloneRequest,
    RepositoryAnalyzeRequest,
)


def get_or_create_test_user(session) -> User:
    """Return existing test user or create one for verification."""
    existing = session.exec(
        select(User).where(User.username == "verify_clone_fix_user")
    ).first()
    if existing:
        return existing

    user = User(
        github_id=abs(hash("verify_clone_fix_user")) % (10 ** 9),
        username="verify_clone_fix_user",
        email="verify_clone_fix@example.com",
    )
    session.add(user)
    session.flush()
    return user


def main():
    print("=" * 60)
    print("Phase 5 Bug Fix Verification: Clone -> DB Persistence -> Analyze")
    print("=" * 60)

    with get_session_ctx() as session:
        # Setup
        user = get_or_create_test_user(session)
        session.commit()
        session.refresh(user)
        print(f"\nTest User: '{user.username}' (id={user.id})")

        # ----------------------------------------------------------------
        # Step 1: Call clone endpoint
        # ----------------------------------------------------------------
        print("\n[1/4] Calling POST /repositories/clone ...")
        clone_req = RepositoryCloneRequest(
            repository_url="https://github.com/octocat/Hello-World.git",
            repository_name="Hello-World",
            owner="octocat",
            owner_id=user.id,
            github_repo_id=1296269,   # Real GitHub repo ID for octocat/Hello-World
            is_private=False,
        )

        clone_resp = clone_repository(clone_req, session=session)
        print(f"  Clone Response:")
        print(f"    status         = {clone_resp.status}")
        print(f"    repository_id  = {clone_resp.repository_id}")
        print(f"    workspace      = {clone_resp.workspace}")
        print(f"    default_branch = {clone_resp.default_branch}")
        print(f"    already_exists = {clone_resp.already_exists}")

        assert clone_resp.status == "success", "Clone status must be 'success'"
        assert clone_resp.repository_id is not None, "repository_id must be set"
        assert os.path.exists(clone_resp.workspace), "Workspace path must exist on disk"
        print("  [PASS] Clone succeeded and returned repository_id.")

        # ----------------------------------------------------------------
        # Step 2: Verify DB row exists
        # ----------------------------------------------------------------
        print("\n[2/4] Verifying Repository DB row was persisted ...")
        repo = session.get(Repository, clone_resp.repository_id)
        assert repo is not None, "Repository row must exist in DB"
        assert repo.owner_id == user.id, "owner_id must match"
        assert repo.full_name == "octocat/Hello-World", "full_name must match"
        assert repo.local_path == clone_resp.workspace, "local_path must match workspace"
        assert repo.clone_status == "completed", "clone_status must be 'completed'"
        assert repo.default_branch == clone_resp.default_branch, "default_branch must match"
        print(f"  DB row found: id={repo.id}, full_name='{repo.full_name}', local_path='{repo.local_path}'")
        print("  [PASS] Repository record correctly persisted in DB with all required fields.")

        # ----------------------------------------------------------------
        # Step 3: Call clone again — verify upsert (no duplicate)
        # ----------------------------------------------------------------
        print("\n[3/4] Calling clone again (re-clone test) ...")
        clone_resp2 = clone_repository(clone_req, session=session)
        assert clone_resp2.repository_id == clone_resp.repository_id, \
            "Re-clone must return the same repository_id (upsert, not duplicate)"
        assert clone_resp2.already_exists is True, "already_exists must be True on re-clone"

        count = session.exec(
            select(Repository).where(Repository.full_name == "octocat/Hello-World")
        ).all()
        assert len(count) == 1, f"Expected exactly 1 repository row, found {len(count)}"
        print(f"  Re-clone returned same repository_id: {clone_resp2.repository_id}")
        print("  [PASS] Upsert worked correctly — no duplicate rows created.")

        # ----------------------------------------------------------------
        # Step 4: POST /repositories/analyze using returned repository_id
        # ----------------------------------------------------------------
        print("\n[4/4] Calling POST /repositories/analyze using returned repository_id ...")
        analyze_req = RepositoryAnalyzeRequest(
            repository_id=clone_resp.repository_id,
            force_refresh=False,
        )
        summary = analyze_repository(analyze_req, session=session)
        assert summary.project_name != "", "project_name must not be empty"
        print(f"  Analysis succeeded. Project: '{summary.project_name}'")
        print(f"  Languages: {summary.languages}")
        print(f"  Frameworks: {summary.frameworks}")
        print(f"  Architecture: {summary.architecture}")
        print("\n  Example ProjectSummary JSON:")
        print(json.dumps(summary.model_dump(), indent=2))
        print("  [PASS] POST /repositories/analyze works correctly using the returned repository_id.")

    print("\n" + "=" * 60)
    print("ALL PHASE 5 BUG FIX VERIFICATION TESTS PASSED!")
    print("=" * 60)


if __name__ == "__main__":
    main()
