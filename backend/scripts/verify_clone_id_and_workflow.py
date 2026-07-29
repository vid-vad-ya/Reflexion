"""Comprehensive verification script for Repository Clone Fix and Full Workflow.

Verifies:
1. Clone Repository A (without github_repo_id or with github_repo_id=0).
2. Confirm DB stores a valid, non-zero, positive GitHub repository ID.
3. Clone Repository B (without github_repo_id or with github_repo_id=0).
4. Confirm Repository B stores a DIFFERENT non-zero GitHub repository ID.
5. Confirm NO UNIQUE constraint violation occurs across multiple repository clones.
6. Run Analyze on Repository A.
7. Run Planner on Repository A.
8. Confirm the end-to-end workflow succeeds cleanly.

Run from backend directory:
    python scripts/verify_clone_id_and_workflow.py
"""

import os
import sys
import uuid
import json

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
from app.api.v1.planner import plan_repository_change
from app.schemas.planner import PlannerRequest


def get_or_create_test_user(session) -> User:
    """Return existing test user or create a fresh one."""
    username = "workflow_test_user"
    user = session.exec(select(User).where(User.username == username)).first()
    if user:
        return user

    user = User(
        github_id=abs(hash(username)) % (10 ** 9),
        username=username,
        email="workflow_test@example.com",
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def main():
    print("=" * 70)
    print("STARTING FULL WORKFLOW VERIFICATION (CLONE A -> CLONE B -> ANALYZE -> PLANNER)")
    print("=" * 70)

    with get_session_ctx() as session:
        user = get_or_create_test_user(session)
        print(f"\n[0] Test User Created/Found: id={user.id}, username='{user.username}'")

        # -------------------------------------------------------------------------
        # Step 1 & 2: Clone Repository A with github_repo_id=0 (simulating Swagger)
        # -------------------------------------------------------------------------
        print("\n[1/8] Cloning Repository A ('octocat/Hello-World') with github_repo_id=0 ...")
        clone_req_a = RepositoryCloneRequest(
            repository_url="https://github.com/octocat/Hello-World.git",
            repository_name="Hello-World",
            owner="octocat",
            owner_id=user.id,
            github_repo_id=0,  # Simulate Swagger UI payload with 0
            is_private=False,
        )

        resp_a = clone_repository(clone_req_a, session=session)
        print(f"  Repo A Cloned Successfully!")
        print(f"    repository_id = {resp_a.repository_id}")
        print(f"    workspace     = {resp_a.workspace}")

        repo_a = session.get(Repository, resp_a.repository_id)
        assert repo_a is not None, "Repo A record must exist in DB"
        print(f"\n[2/8] DB Record for Repo A:")
        print(f"    full_name      = '{repo_a.full_name}'")
        print(f"    github_repo_id = {repo_a.github_repo_id}")
        assert repo_a.github_repo_id > 0, f"github_repo_id must be strictly > 0, got {repo_a.github_repo_id}"
        print("  [PASS] Repo A assigned valid non-zero positive github_repo_id.")

        # -------------------------------------------------------------------------
        # Step 3, 4 & 5: Clone Repository B with github_repo_id=0 (simulating Swagger)
        # -------------------------------------------------------------------------
        print("\n[3/8] Cloning Repository B ('octocat/Spoon-Knife') with github_repo_id=0 ...")
        clone_req_b = RepositoryCloneRequest(
            repository_url="https://github.com/octocat/Spoon-Knife.git",
            repository_name="Spoon-Knife",
            owner="octocat",
            owner_id=user.id,
            github_repo_id=0,  # Simulate Swagger UI payload with 0
            is_private=False,
        )

        try:
            resp_b = clone_repository(clone_req_b, session=session)
            print(f"  Repo B Cloned Successfully!")
            print(f"    repository_id = {resp_b.repository_id}")
            print(f"    workspace     = {resp_b.workspace}")
        except Exception as e:
            print(f"  [FAIL] Error during Repository B clone: {e}")
            sys.exit(1)

        repo_b = session.get(Repository, resp_b.repository_id)
        assert repo_b is not None, "Repo B record must exist in DB"
        print(f"\n[4/8] DB Record for Repo B:")
        print(f"    full_name      = '{repo_b.full_name}'")
        print(f"    github_repo_id = {repo_b.github_repo_id}")
        assert repo_b.github_repo_id > 0, f"github_repo_id must be strictly > 0, got {repo_b.github_repo_id}"
        assert repo_b.github_repo_id != repo_a.github_repo_id, \
            f"Repo A ({repo_a.github_repo_id}) and Repo B ({repo_b.github_repo_id}) must have different github_repo_ids"
        print("\n[5/8] Verification of Constraint & Uniqueness:")
        print(f"  [PASS] Repo A ID: {repo_a.github_repo_id} != Repo B ID: {repo_b.github_repo_id}")
        print("  [PASS] No UNIQUE constraint violation occurred when cloning multiple repos!")

        # -------------------------------------------------------------------------
        # Step 6: Run Analyze on Repository A
        # -------------------------------------------------------------------------
        print("\n[6/8] Running RepositoryAnalyzer on Repository A ...")
        analyze_req = RepositoryAnalyzeRequest(
            repository_id=resp_a.repository_id,
            force_refresh=True,
        )
        summary = analyze_repository(analyze_req, session=session)
        print(f"  Analysis Succeeded!")
        print(f"    Project Name: '{summary.project_name}'")
        print(f"    Languages:    {summary.languages}")
        print(f"    Frameworks:   {summary.frameworks}")
        print(f"    Architecture: {summary.architecture}")
        print("  [PASS] RepositoryAnalyzer returned valid ProjectSummary.")

        # -------------------------------------------------------------------------
        # Step 7 & 8: Run Planner Agent on Repository A
        # -------------------------------------------------------------------------
        print("\n[7/8] Running Planner Agent on Repository A ...")
        planner_req = PlannerRequest(
            request="Add structured logging and request correlation ID middleware",
        )
        plan_resp = plan_repository_change(
            repository_id=resp_a.repository_id,
            payload=planner_req,
            session=session,
        )
        print(f"\n[8/8] Planner Agent Succeeded!")
        print(f"    Plan Goal:        '{plan_resp.goal}'")
        print(f"    Target Complexity: '{plan_resp.complexity}'")
        print(f"    Components Count: {len(plan_resp.affected_components)}")
        print(f"    Assumptions Count: {len(plan_resp.assumptions)}")
        print("  [PASS] Complete end-to-end workflow (Clone A -> Clone B -> Analyze -> Planner) succeeded!")

    print("\n" + "=" * 70)
    print("ALL VERIFICATION CHECKS PASSED SUCCESSFULLY!")
    print("=" * 70)


if __name__ == "__main__":
    main()
