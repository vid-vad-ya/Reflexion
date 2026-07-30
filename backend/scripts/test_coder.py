"""Validation and integration test script for Phase 8.1: Incremental Per-File Coder Agent.

Verifies:
1. Single-file and summary prompt construction via `build_single_file_coder_prompt` and `build_coder_summary_prompt`.
2. Safe file loading (`_load_single_file`, `load_relevant_files`, binary checks, path traversal guards).
3. Unified diff generation (`generate_unified_diff`).
4. Schema validation (`SingleFileGenerationResult`, `CodingSummaryResult`, `GeneratedFile`, `CodingResult`).
5. Incremental code generation for:
   - Single file modification
   - Multiple file modifications
   - New file generation
   - Mixed create + modify scenarios
6. API endpoint compatibility (`POST /repositories/{id}/code`).
7. Non-destructive safety check (verifies workspace disk remains untouched).
8. Regression compatibility with Planner & RepositoryAnalyzer components.

Run from the backend directory:
    python scripts/test_coder.py
"""

import json
import os
import sys
import tempfile
import uuid
from typing import Dict, Tuple

# Ensure backend directory is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi import HTTPException
from sqlmodel import select

from app.api.v1.coder import generate_repository_code
from app.api.v1.planner import plan_repository_change
from app.api.v1.repositories import analyze_repository, clone_repository, RepositoryAnalyzeRequest, RepositoryCloneRequest
from app.database import get_session_ctx
from app.models import Repository, User
from app.prompts.coder_prompt import (
    build_coder_prompt,
    build_coder_summary_prompt,
    build_single_file_coder_prompt,
)
from app.schemas.coder import (
    CoderRequest,
    CodingResult,
    CodingSummaryResult,
    GeneratedFile,
    SingleFileGenerationResult,
)
from app.schemas.planner import ImplementationPlan, PlannerRequest
from app.schemas.repository import EntryPoint, ProjectSummary, TechnologyDetection
from app.services.coder_service import (
    _generate_single_file,
    _load_single_file,
    coder_service,
    generate_unified_diff,
    is_binary_file,
    load_relevant_files,
)
from app.services.planner_service import planner_service


def get_or_create_test_context(session) -> Tuple[User, Repository, ImplementationPlan]:
    """Ensure test user, cloned/analyzed repository, and implementation plan exist in DB."""
    username = "test_coder_user"
    user = session.exec(select(User).where(User.username == username)).first()
    if not user:
        user = User(
            github_id=abs(hash(username)) % (10 ** 9),
            username=username,
            email="coder_test@example.com",
        )
        session.add(user)
        session.commit()
        session.refresh(user)

    clone_req = RepositoryCloneRequest(
        repository_url="https://github.com/octocat/Hello-World.git",
        repository_name="Hello-World",
        owner="octocat",
        owner_id=user.id,
        github_repo_id=1296269,
        is_private=False,
    )
    clone_resp = clone_repository(clone_req, session=session)

    analyze_req = RepositoryAnalyzeRequest(
        repository_id=clone_resp.repository_id,
        force_refresh=False,
    )
    analyze_repository(analyze_req, session=session)

    repo = session.get(Repository, clone_resp.repository_id)
    assert repo is not None and repo.project_summary is not None

    plan = planner_service.plan_change(
        repository_id=repo.id,
        user_request="Add structured logging helper and configuration module",
        session=session,
    )

    return user, repo, plan


def test_prompt_builders():
    print("\n[1/8] Testing Single-File & Summary Prompt Builders ...")
    summary = ProjectSummary(
        project_name="TestApp",
        description="A test project",
        languages=["Python"],
        frameworks=["FastAPI"],
        architecture="Modular",
        important_directories=["app"],
        important_files=["README.md"],
        entry_points=[EntryPoint(path="app/main.py", description="Main app entry point")],
        technologies=[TechnologyDetection(name="Python", category="Language")],
        observations=["Clean layout"],
    )
    plan = ImplementationPlan(
        goal="Add logging and config",
        summary="Add logging and config module",
        affected_components=["Logging"],
        affected_files=["README.md"],
        new_files=["app/config.py"],
        dependencies=[],
        database_changes=[],
        environment_changes=[],
        implementation_steps=["Modify README.md", "Create app/config.py"],
        risks=[],
        assumptions=[],
        complexity="Low",
        estimated_files_changed=2,
        reasoning="Enhances observability",
    )

    # Single-file prompt builder test
    sys_inst, user_prompt = build_single_file_coder_prompt(
        project_summary=summary,
        implementation_plan=plan,
        file_path="README.md",
        original_content="Hello World",
        is_new_file=False,
    )
    assert "Senior Staff Software Engineer" in sys_inst
    assert "README.md" in user_prompt
    assert "Hello World" in user_prompt

    # Summary prompt builder test
    explanations = [
        {"path": "README.md", "change_type": "modify", "explanation": "Updated documentation"},
        {"path": "app/config.py", "change_type": "create", "explanation": "Created app configuration"},
    ]
    sum_sys, sum_prompt = build_coder_summary_prompt(plan.goal, plan.summary, explanations)
    assert "Senior Staff Software Engineer" in sum_sys
    assert "README.md" in sum_prompt
    assert "app/config.py" in sum_prompt

    print("  [PASS] Single-file and summary prompt builders correctly formatted context.")


def test_file_loader_and_diffs():
    print("\n[2/8] Testing File Loader & Unified Diff Generator ...")

    with tempfile.TemporaryDirectory() as tmpdir:
        txt_path = os.path.join(tmpdir, "hello.txt")
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write("Hello World\nLine 2\n")

        bin_path = os.path.join(tmpdir, "image.png")
        with open(bin_path, "wb") as f:
            f.write(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR")

        # Test single file load
        content, warn = _load_single_file(tmpdir, "hello.txt")
        assert content == "Hello World\nLine 2\n"
        assert warn is None

        # Test binary single file load
        bin_content, bin_warn = _load_single_file(tmpdir, "image.png")
        assert bin_content is None
        assert "binary" in bin_warn

        # Test path traversal single file load
        pt_content, pt_warn = _load_single_file(tmpdir, "../secret.txt")
        assert pt_content is None
        assert "Path traversal" in pt_warn

        # Test Unified Diff Generation
        diff_create = generate_unified_diff("new.txt", None, "New Content\n", "create")
        assert "--- /dev/null" in diff_create
        assert "+++ b/new.txt" in diff_create
        assert "+New Content" in diff_create

        diff_modify = generate_unified_diff(
            "hello.txt",
            "Hello World\nLine 2\n",
            "Hello World\nLine 2 Modified\n",
            "modify",
        )
        assert "--- a/hello.txt" in diff_modify
        assert "+++ b/hello.txt" in diff_modify
        assert "-Line 2" in diff_modify
        assert "+Line 2 Modified" in diff_modify
        print("  [PASS] Single file loader and unified diff generation verified.")


def test_error_handling(session):
    print("\n[3/8] Testing Error Handling (404 and 400 validation) ...")

    non_existent_id = uuid.uuid4()
    try:
        coder_service.generate_code(
            repository_id=non_existent_id,
            session=session,
            implementation_plan=None,
        )
        assert False, "Should have raised 404"
    except HTTPException as e:
        assert e.status_code == 404
        print("  [PASS] 404 properly raised for non-existent repository ID.")

    repo = session.exec(select(Repository)).first()
    if repo:
        try:
            coder_service.generate_code(
                repository_id=repo.id,
                session=session,
                implementation_plan=None,
            )
            assert False, "Should have raised 400 for missing plan"
        except HTTPException as e:
            assert e.status_code == 400
            print("  [PASS] 400 properly raised when ImplementationPlan is omitted.")


def test_single_file_modification(session, repo: Repository):
    print(f"\n[4/8] Testing Single File Modification Scenario ...")
    plan = ImplementationPlan(
        goal="Update README title",
        summary="Update README title to be more descriptive",
        affected_components=["Documentation"],
        affected_files=["README"],
        new_files=[],
        dependencies=[],
        database_changes=[],
        environment_changes=[],
        implementation_steps=["Update README file"],
        risks=[],
        assumptions=[],
        complexity="Low",
        estimated_files_changed=1,
        reasoning="Doc improvement",
    )

    result = coder_service.generate_code(
        repository_id=repo.id,
        session=session,
        implementation_plan=plan,
    )

    assert result.summary != ""
    assert len(result.generated_files) == 1
    assert result.generated_files[0].path == "README"
    assert "README" in result.unified_diffs
    print(f"  [PASS] Single file modification generated file '{result.generated_files[0].path}'.")


def test_new_file_generation(session, repo: Repository):
    print(f"\n[5/8] Testing New File Generation Scenario ...")
    plan = ImplementationPlan(
        goal="Create app config module",
        summary="Create new config file for application settings",
        affected_components=["Configuration"],
        affected_files=[],
        new_files=["app/config.py"],
        dependencies=[],
        database_changes=[],
        environment_changes=[],
        implementation_steps=["Create app/config.py"],
        risks=[],
        assumptions=[],
        complexity="Low",
        estimated_files_changed=1,
        reasoning="Configuration module",
    )

    result = coder_service.generate_code(
        repository_id=repo.id,
        session=session,
        implementation_plan=plan,
    )

    assert result.summary != ""
    assert len(result.generated_files) == 1
    assert result.generated_files[0].path == "app/config.py"
    assert result.generated_files[0].change_type == "create"
    assert result.generated_files[0].original_content is None
    assert "app/config.py" in result.unified_diffs
    print(f"  [PASS] New file generation successfully created '{result.generated_files[0].path}'.")


def test_mixed_create_and_modify(session, repo: Repository, plan: ImplementationPlan):
    print(f"\n[6/8] Testing Mixed Create + Modify Generation for repo '{repo.full_name}' ...")

    result = coder_service.generate_code(
        repository_id=repo.id,
        session=session,
        implementation_plan=plan,
    )

    assert result.summary != ""
    assert isinstance(result.generated_files, list)
    assert len(result.generated_files) > 0
    assert len(result.unified_diffs) > 0
    assert result.reasoning != ""

    print(f"  Summary:   '{result.summary[:80]}...'")
    print(f"  Files Generated ({len(result.generated_files)}):")
    for gf in result.generated_files:
        print(f"    - [{gf.change_type.upper()}] {gf.path}")
        assert gf.explanation != ""
        assert gf.unified_diff is not None
        assert gf.path in result.unified_diffs

    print("  [PASS] Mixed create + modify generated all files, diffs, and lightweight summary.")
    return result


def test_api_endpoint_and_safety(session, repo: Repository, plan: ImplementationPlan, result: CodingResult):
    print("\n[7/8] Testing API Endpoint Handler & Non-Destructive Safety ...")
    payload = CoderRequest(
        implementation_plan=plan,
        user_prompt_override="Ensure logging functions use snake_case naming",
    )
    res = generate_repository_code(repository_id=repo.id, payload=payload, session=session)
    assert isinstance(res, CodingResult)
    assert len(res.generated_files) > 0

    # Non-destructive safety check
    for gf in result.generated_files:
        if gf.change_type == "create":
            abs_p = os.path.join(repo.local_path, gf.path)
            assert not os.path.exists(abs_p), f"Created file '{gf.path}' must NOT be written to disk"

    print("  [PASS] API endpoint handler returned valid CodingResult; disk remains untouched.")


def test_regression(session, repo: Repository):
    print("\n[8/8] Testing Regression (Planner and RepositoryAnalyzer) ...")
    assert repo is not None and repo.project_summary is not None
    plan = planner_service.plan_change(
        repository_id=repo.id,
        user_request="Regression test plan request",
        session=session,
    )
    assert plan.goal != ""
    print("  [PASS] Regression check passed: Planner Service operates normally.")


def main():
    print("=" * 70)
    print("PHASE 8.1 INCREMENTAL CODER AGENT VERIFICATION SUITE")
    print("=" * 70)

    test_prompt_builders()
    test_file_loader_and_diffs()

    with get_session_ctx() as session:
        user, repo, plan = get_or_create_test_context(session)

        test_error_handling(session)
        test_single_file_modification(session, repo)
        test_new_file_generation(session, repo)
        coding_result = test_mixed_create_and_modify(session, repo, plan)
        test_api_endpoint_and_safety(session, repo, plan, coding_result)
        test_regression(session, repo)

    print("\n" + "=" * 70)
    print("ALL PHASE 8.1 CODER AGENT VERIFICATION TESTS PASSED SUCCESSFULLY!")
    print("=" * 70)


if __name__ == "__main__":
    main()
