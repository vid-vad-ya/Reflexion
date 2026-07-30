"""Comprehensive test suite for Phase 9: Workspace Manager.

Verifies:
1. Workspace creation – unique directory is created under base_workspace_dir.
2. Repository copy – all source files and directory structure are preserved.
3. create: New file written with correct content, including nested directories.
4. modify: Existing file overwritten; missing file triggers a warning and is created.
5. delete: File removed; absent file triggers a warning but does not raise.
6. Nested directory creation: Deep paths are created on demand.
7. Original repository untouched: After all operations the source tree is identical.
8. Cleanup: workspace_manager.cleanup() fully removes the workspace directory.
9. Path traversal protection: Malicious relative paths are rejected with PathTraversalError.

Run from the backend directory:
    python scripts/test_workspace_manager.py
"""

import os
import sys
import tempfile
from pathlib import Path

# ---------------------------------------------------------------------------
# Path bootstrap – ensures the backend package is importable.
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.schemas.coder import GeneratedFile
from app.services.workspace_manager import (
    PathTraversalError,
    PatchApplicationError,
    WorkspaceCreationError,
    WorkspaceManager,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_gen_file(
    path: str,
    change_type: str,
    generated_content: str = "",
    explanation: str = "test",
) -> GeneratedFile:
    return GeneratedFile(
        path=path,
        change_type=change_type,
        original_content=None,
        generated_content=generated_content,
        explanation=explanation,
        unified_diff=None,
    )


def _build_sample_repo(root: Path) -> None:
    """Populate *root* with a small fake repository structure."""
    (root / "README.md").write_text("# Hello World", encoding="utf-8")
    (root / "src").mkdir()
    (root / "src" / "main.py").write_text("print('hello')\n", encoding="utf-8")
    (root / "src" / "utils.py").write_text("def helper(): pass\n", encoding="utf-8")
    (root / "docs").mkdir()
    (root / "docs" / "index.md").write_text("# Docs\n", encoding="utf-8")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Individual tests
# ---------------------------------------------------------------------------

def test_workspace_creation(tmp_base: Path, repo_dir: Path) -> Path:
    print("\n[1/9] Testing workspace creation ...")
    wm = WorkspaceManager(base_workspace_dir=tmp_base)
    workspace = wm.create_workspace(repo_dir)

    assert workspace.exists(), "Workspace directory was not created."
    assert workspace.is_dir(), "Workspace path is not a directory."
    assert workspace.parent == tmp_base, "Workspace was not created under base_workspace_dir."
    print(f"  Workspace created at: {workspace}")
    print("  [PASS] Workspace creation.")
    return workspace


def test_repository_copied(repo_dir: Path, workspace: Path) -> None:
    print("\n[2/9] Testing repository copy integrity ...")
    for rel in ["README.md", "src/main.py", "src/utils.py", "docs/index.md"]:
        ws_file = workspace / rel
        src_file = repo_dir / rel
        assert ws_file.exists(), f"Expected file '{rel}' not found in workspace."
        assert _read(ws_file) == _read(src_file), f"Content mismatch for '{rel}'."
    print("  [PASS] All source files copied correctly to workspace.")


def test_create_file(tmp_base: Path, repo_dir: Path) -> None:
    print("\n[3/9] Testing CREATE operation ...")
    wm = WorkspaceManager(base_workspace_dir=tmp_base)
    workspace = wm.create_workspace(repo_dir)

    try:
        gen = _make_gen_file("src/logger.py", "create", "import logging\n")
        warnings = wm.apply_changes(workspace, [gen])

        target = workspace / "src" / "logger.py"
        assert target.exists(), "Created file not found in workspace."
        assert _read(target) == "import logging\n", "Created file has wrong content."
        assert (repo_dir / "src" / "logger.py").exists() is False, (
            "CREATE must not write to original repository."
        )
        assert warnings == [], f"Unexpected warnings: {warnings}"
        print("  [PASS] CREATE operation.")
    finally:
        wm.cleanup(workspace)


def test_create_nested_directories(tmp_base: Path, repo_dir: Path) -> None:
    print("\n[4/9] Testing CREATE with nested directory creation ...")
    wm = WorkspaceManager(base_workspace_dir=tmp_base)
    workspace = wm.create_workspace(repo_dir)

    try:
        gen = _make_gen_file(
            "app/services/auth/jwt.py",
            "create",
            "# JWT helpers\n",
        )
        wm.apply_changes(workspace, [gen])

        target = workspace / "app" / "services" / "auth" / "jwt.py"
        assert target.exists(), "Nested file not created."
        assert _read(target) == "# JWT helpers\n"
        print("  [PASS] Nested directory creation via CREATE.")
    finally:
        wm.cleanup(workspace)


def test_modify_file(tmp_base: Path, repo_dir: Path) -> None:
    print("\n[5/9] Testing MODIFY operation ...")
    wm = WorkspaceManager(base_workspace_dir=tmp_base)
    workspace = wm.create_workspace(repo_dir)

    try:
        new_content = "# Updated README\n"
        gen = _make_gen_file("README.md", "modify", new_content)
        warnings = wm.apply_changes(workspace, [gen])

        target = workspace / "README.md"
        assert _read(target) == new_content, "Modified file has wrong content."
        # Original must be untouched.
        assert _read(repo_dir / "README.md") == "# Hello World", (
            "MODIFY must not change original file."
        )
        assert warnings == [], f"Unexpected warnings: {warnings}"
        print("  [PASS] MODIFY operation.")
    finally:
        wm.cleanup(workspace)


def test_modify_missing_file_creates_with_warning(tmp_base: Path, repo_dir: Path) -> None:
    print("\n[5b/9] Testing MODIFY on missing file (should create + warn) ...")
    wm = WorkspaceManager(base_workspace_dir=tmp_base)
    workspace = wm.create_workspace(repo_dir)

    try:
        gen = _make_gen_file("nonexistent.py", "modify", "# brand new\n")
        warnings = wm.apply_changes(workspace, [gen])

        target = workspace / "nonexistent.py"
        assert target.exists(), "MODIFY-on-missing should create the file."
        assert _read(target) == "# brand new\n"
        assert len(warnings) == 1, f"Expected exactly one warning, got: {warnings}"
        assert "not found" in warnings[0].lower()
        print("  [PASS] MODIFY on missing file creates file and emits warning.")
    finally:
        wm.cleanup(workspace)


def test_delete_file(tmp_base: Path, repo_dir: Path) -> None:
    print("\n[6/9] Testing DELETE operation ...")
    wm = WorkspaceManager(base_workspace_dir=tmp_base)
    workspace = wm.create_workspace(repo_dir)

    try:
        gen = _make_gen_file("docs/index.md", "delete")
        warnings = wm.apply_changes(workspace, [gen])

        assert not (workspace / "docs" / "index.md").exists(), (
            "Deleted file still present in workspace."
        )
        # Original must still exist.
        assert (repo_dir / "docs" / "index.md").exists(), (
            "DELETE must not remove the original file."
        )
        assert warnings == [], f"Unexpected warnings: {warnings}"
        print("  [PASS] DELETE operation.")
    finally:
        wm.cleanup(workspace)


def test_delete_absent_file_warns(tmp_base: Path, repo_dir: Path) -> None:
    print("\n[6b/9] Testing DELETE on absent file (should warn, not raise) ...")
    wm = WorkspaceManager(base_workspace_dir=tmp_base)
    workspace = wm.create_workspace(repo_dir)

    try:
        gen = _make_gen_file("does_not_exist.txt", "delete")
        warnings = wm.apply_changes(workspace, [gen])

        assert len(warnings) == 1, f"Expected exactly one warning, got: {warnings}"
        assert "already absent" in warnings[0].lower()
        print("  [PASS] DELETE on absent file emits warning without raising.")
    finally:
        wm.cleanup(workspace)


def test_original_repository_untouched(tmp_base: Path, repo_dir: Path) -> None:
    print("\n[7/9] Testing original repository is untouched after all operations ...")
    wm = WorkspaceManager(base_workspace_dir=tmp_base)
    workspace = wm.create_workspace(repo_dir)

    try:
        changes = [
            _make_gen_file("README.md", "modify", "# Overwritten\n"),
            _make_gen_file("brand_new.py", "create", "# new\n"),
            _make_gen_file("src/utils.py", "delete"),
        ]
        wm.apply_changes(workspace, changes)

        # Original README unchanged.
        assert _read(repo_dir / "README.md") == "# Hello World"
        # Original utils.py unchanged.
        assert (repo_dir / "src" / "utils.py").exists()
        # brand_new.py not in original.
        assert not (repo_dir / "brand_new.py").exists()
        print("  [PASS] Original repository remains completely untouched.")
    finally:
        wm.cleanup(workspace)


def test_cleanup(tmp_base: Path, repo_dir: Path) -> None:
    print("\n[8/9] Testing cleanup removes workspace ...")
    wm = WorkspaceManager(base_workspace_dir=tmp_base)
    workspace = wm.create_workspace(repo_dir)
    assert workspace.exists()

    wm.cleanup(workspace)
    assert not workspace.exists(), "Workspace should not exist after cleanup."
    print("  [PASS] Cleanup successfully removed workspace directory.")


def test_path_traversal_protection(tmp_base: Path, repo_dir: Path) -> None:
    print("\n[9/9] Testing path traversal protection ...")
    wm = WorkspaceManager(base_workspace_dir=tmp_base)
    workspace = wm.create_workspace(repo_dir)

    try:
        malicious_paths = [
            "../../secret.txt",
            "../outside.py",
            "/etc/passwd",
            "src/../../../etc/hosts",
        ]

        for bad_path in malicious_paths:
            gen = _make_gen_file(bad_path, "create", "malicious content")
            try:
                wm.apply_changes(workspace, [gen])
                assert False, (
                    f"PathTraversalError should have been raised for '{bad_path}'"
                )
            except PathTraversalError as exc:
                print(f"    [OK] Correctly blocked: '{bad_path}' -> {exc}")

        print("  [PASS] All path traversal attempts blocked.")
    finally:
        wm.cleanup(workspace)


def test_workspace_creation_invalid_source(tmp_base: Path) -> None:
    print("\n[Extra] Testing WorkspaceCreationError for invalid source ...")
    wm = WorkspaceManager(base_workspace_dir=tmp_base)
    try:
        wm.create_workspace("/nonexistent/path/that/does/not/exist")
        assert False, "Should have raised WorkspaceCreationError"
    except WorkspaceCreationError as exc:
        print(f"  [OK] Correctly raised WorkspaceCreationError: {exc}")
    print("  [PASS] Invalid source raises WorkspaceCreationError.")


def test_apply_changes_missing_workspace(tmp_base: Path) -> None:
    print("\n[Extra] Testing apply_changes raises when workspace is absent ...")
    wm = WorkspaceManager(base_workspace_dir=tmp_base)
    try:
        wm.apply_changes(tmp_base / "nonexistent_ws", [])
        assert False, "Should have raised WorkspaceCreationError"
    except WorkspaceCreationError as exc:
        print(f"  [OK] Correctly raised WorkspaceCreationError: {exc}")
    print("  [PASS] apply_changes raises for missing workspace.")


def test_mixed_operations(tmp_base: Path, repo_dir: Path) -> None:
    print("\n[Extra] Testing mixed create + modify + delete in a single apply_changes call ...")
    wm = WorkspaceManager(base_workspace_dir=tmp_base)
    workspace = wm.create_workspace(repo_dir)

    try:
        changes = [
            _make_gen_file("README.md",   "modify", "# Updated\n"),
            _make_gen_file("src/new.py",  "create", "# brand new\n"),
            _make_gen_file("docs/index.md", "delete"),
        ]
        warnings = wm.apply_changes(workspace, changes)

        assert _read(workspace / "README.md") == "# Updated\n"
        assert (workspace / "src" / "new.py").exists()
        assert not (workspace / "docs" / "index.md").exists()
        assert warnings == [], f"Unexpected warnings: {warnings}"

        # Original untouched.
        assert _read(repo_dir / "README.md") == "# Hello World"
        assert (repo_dir / "docs" / "index.md").exists()
        assert not (repo_dir / "src" / "new.py").exists()

        print("  [PASS] Mixed create + modify + delete applied correctly.")
    finally:
        wm.cleanup(workspace)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    print("=" * 70)
    print("PHASE 9 WORKSPACE MANAGER VERIFICATION SUITE")
    print("=" * 70)

    with tempfile.TemporaryDirectory() as raw_tmp:
        tmp_base = Path(raw_tmp) / "ws_base"
        tmp_base.mkdir()

        # Build a fake repository for testing.
        repo_dir = Path(raw_tmp) / "sample_repo"
        repo_dir.mkdir()
        _build_sample_repo(repo_dir)

        # --- Core tests ---
        workspace = test_workspace_creation(tmp_base, repo_dir)
        test_repository_copied(repo_dir, workspace)
        # Cleanup the workspace used by tests 1 & 2 so subsequent tests start fresh.
        WorkspaceManager(base_workspace_dir=tmp_base).cleanup(workspace)

        # File operation tests (each creates + cleans up its own workspace).
        test_create_file(tmp_base, repo_dir)
        test_create_nested_directories(tmp_base, repo_dir)
        test_modify_file(tmp_base, repo_dir)
        test_modify_missing_file_creates_with_warning(tmp_base, repo_dir)
        test_delete_file(tmp_base, repo_dir)
        test_delete_absent_file_warns(tmp_base, repo_dir)
        test_original_repository_untouched(tmp_base, repo_dir)
        test_cleanup(tmp_base, repo_dir)
        test_path_traversal_protection(tmp_base, repo_dir)

        # --- Extra edge-case tests ---
        test_workspace_creation_invalid_source(tmp_base)
        test_apply_changes_missing_workspace(tmp_base)
        test_mixed_operations(tmp_base, repo_dir)

    print("\n" + "=" * 70)
    print("ALL PHASE 9 WORKSPACE MANAGER VERIFICATION TESTS PASSED!")
    print("=" * 70)


if __name__ == "__main__":
    main()
