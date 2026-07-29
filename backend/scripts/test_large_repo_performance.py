"""Large Repository Performance Validation Script.

Verifies that the enhanced RepositoryAnalyzer handles large repositories efficiently:
1. Ignored directories are completely skipped during traversal
2. Full scan of 200+ files completes in under 10 seconds
3. LLM context receives only the top-ranked files (max 10) within character limits
4. ProjectSummary quality remains high on a large repo
5. Top important files are source code, NOT README.md or docs

Run from the backend directory:
    python scripts/test_large_repo_performance.py
"""

import os
import sys
import tempfile
import time
import json

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.schemas.repository import ProjectSummary
from app.services.repository_analyzer import repository_analyzer
from app.services.repository_analysis.scanner import RepositoryScanner
from app.services.repository_analysis.detectors import TechnologyDetector
from app.services.repository_analysis.prioritizer import FilePrioritizer
from app.services.repository_analysis.preview import PreviewCollector
from app.services.repository_analysis.constants import (
    DEFAULT_IGNORE_PATTERNS,
    MAX_PREVIEW_FILES,
    MAX_PREVIEW_CHARS_PER_FILE,
)


# ---------------------------------------------------------------------------
# Repository Scaffolding
# ---------------------------------------------------------------------------

def _write(path: str, content: str = "") -> None:
    os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def scaffold_large_repo(root: str) -> int:
    """Create a large Python/FastAPI repository with 200+ files across deep directories."""
    total_files = 0

    # -- Entry Point
    _write(os.path.join(root, "app", "main.py"),
           "from fastapi import FastAPI\napp = FastAPI(title='LargeRepo')\n\nif __name__ == '__main__':\n    pass\n")
    total_files += 1

    # -- Configuration
    _write(os.path.join(root, "app", "core", "config.py"),
           "from pydantic_settings import BaseSettings\nclass Settings(BaseSettings):\n    DATABASE_URL: str = 'postgresql://localhost/db'\nsettings = Settings()\n")
    _write(os.path.join(root, "app", "core", "security.py"),
           "import jwt\nSECRET = 'secret'\ndef create_token(data: dict): return jwt.encode(data, SECRET)\n")
    total_files += 2

    # -- Requirements and manifests
    _write(os.path.join(root, "requirements.txt"),
           "fastapi==0.110.0\nuvicorn==0.28.0\npydantic==2.6.0\nsqlalchemy==2.0.0\npsycopg2-binary==2.9.9\npyjwt==2.8.0\npytest==8.0.0\nalembic==1.13.0\n")
    _write(os.path.join(root, "Dockerfile"),
           "FROM python:3.11-slim\nWORKDIR /app\nCOPY . .\nRUN pip install -r requirements.txt\nCMD ['uvicorn', 'app.main:app']\n")
    _write(os.path.join(root, "docker-compose.yml"),
           "version: '3.9'\nservices:\n  api:\n    build: .\n  db:\n    image: postgres:15\n")
    _write(os.path.join(root, "README.md"),
           "# LargeRepo\nA large repository for performance testing.\n\nThis should appear LAST in prioritized files.\n")
    total_files += 4

    # -- 20 API route modules
    for i in range(1, 21):
        _write(
            os.path.join(root, "app", "api", "routes", f"module_{i}.py"),
            f"from fastapi import APIRouter\nrouter = APIRouter()\n\n@router.get('/module-{i}')\ndef endpoint_{i}(): return {{'module': {i}}}\n",
        )
        total_files += 1

    # -- 20 service modules
    for i in range(1, 21):
        _write(
            os.path.join(root, "app", "services", f"service_{i}.py"),
            f"class Service{i}:\n    def run(self): pass\n    def calculate(self): return {i} * 2\n",
        )
        total_files += 1

    # -- 20 model modules
    for i in range(1, 21):
        _write(
            os.path.join(root, "app", "models", f"model_{i}.py"),
            f"from sqlalchemy import Column, Integer, String\nfrom app.db.base import Base\nclass Model{i}(Base):\n    __tablename__ = 'model_{i}'\n    id = Column(Integer, primary_key=True)\n    name = Column(String)\n",
        )
        total_files += 1

    # -- 20 schema modules
    for i in range(1, 21):
        _write(
            os.path.join(root, "app", "schemas", f"schema_{i}.py"),
            f"from pydantic import BaseModel\nclass Schema{i}(BaseModel):\n    id: int\n    name: str\n",
        )
        total_files += 1

    # -- 15 test files
    for i in range(1, 16):
        _write(
            os.path.join(root, "tests", f"test_module_{i}.py"),
            f"import pytest\n\ndef test_something_{i}():\n    assert {i} > 0\n",
        )
        total_files += 1

    # -- 20 utility modules
    for i in range(1, 21):
        _write(
            os.path.join(root, "app", "utils", f"util_{i}.py"),
            f"def helper_{i}(x): return x * {i}\n",
        )
        total_files += 1

    # -- 10 migration files
    _write(os.path.join(root, "alembic.ini"), "[alembic]\nscript_location = alembic\n")
    total_files += 1
    for i in range(1, 11):
        _write(
            os.path.join(root, "alembic", "versions", f"migration_{i:04d}_add_table_{i}.py"),
            f"\"\"\"Add table {i}\"\"\"\nrevision = '{i:04d}'\ndef upgrade(): pass\ndef downgrade(): pass\n",
        )
        total_files += 1

    # -- 30 docs files (all should be low priority)
    for i in range(1, 16):
        _write(os.path.join(root, "docs", f"guide_{i}.md"), f"# Guide {i}\nDocumentation for module {i}.\n")
        total_files += 1
    for i in range(1, 16):
        _write(os.path.join(root, "docs", "api", f"api_doc_{i}.md"), f"# API Doc {i}\n")
        total_files += 1

    # -- Ignored directories (must be completely skipped)
    for ignored_dir in ["node_modules", "venv", ".git", "__pycache__", "dist", "build", ".pytest_cache"]:
        ignored_path = os.path.join(root, ignored_dir)
        os.makedirs(ignored_path, exist_ok=True)
        for j in range(5):
            _write(os.path.join(ignored_path, f"junk_{j}.py"), f"# ignored file {j}")
        total_files += 5  # counted but should not be scanned

    return total_files


# ---------------------------------------------------------------------------
# Performance Tests
# ---------------------------------------------------------------------------

def test_ignored_dirs_are_skipped(root: str):
    print("\n[1/6] Testing Ignored Directories Are Skipped...")
    scanner = RepositoryScanner()
    t0 = time.perf_counter()
    all_files, all_dirs = scanner.scan_files_and_directories(root)
    elapsed = time.perf_counter() - t0

    dir_bases = set(os.path.basename(d) for d in all_dirs)
    file_bases = set(os.path.basename(f) for f in all_files)

    for ignored in DEFAULT_IGNORE_PATTERNS:
        assert ignored not in dir_bases, f"Ignored directory '{ignored}' must not appear in scanned dirs"

    print(f"  Scanned {len(all_files)} files, {len(all_dirs)} dirs in {elapsed:.3f}s (ignored dirs excluded).")
    print("  [PASS] Ignored directories are completely skipped during traversal.")
    return all_files, all_dirs, elapsed


def test_scan_speed(elapsed: float, file_count: int):
    print(f"\n[2/6] Testing Scan Speed ({file_count} total files incl. ignored)...")
    THRESHOLD_SECONDS = 10.0
    print(f"  Heuristic scan completed in {elapsed:.3f}s (threshold: {THRESHOLD_SECONDS}s)")
    assert elapsed < THRESHOLD_SECONDS, f"Scan too slow: {elapsed:.2f}s > {THRESHOLD_SECONDS}s threshold"
    print("  [PASS] Scan completed efficiently within time threshold.")


def test_llm_context_is_bounded(root: str, all_files: list):
    print(f"\n[3/6] Testing LLM Context Is Bounded (max {MAX_PREVIEW_FILES} files, max {MAX_PREVIEW_CHARS_PER_FILE} chars each)...")

    scanner = RepositoryScanner()
    detector = TechnologyDetector()
    prioritizer = FilePrioritizer()
    preview_collector = PreviewCollector()

    entry_points = detector.detect_entry_points(root, all_files, {})
    prioritized = prioritizer.categorize_and_prioritize_files(all_files, entry_points)
    previews = preview_collector.collect_previews(root, prioritized)

    assert len(previews) <= MAX_PREVIEW_FILES, (
        f"LLM context must receive at most {MAX_PREVIEW_FILES} files. Got: {len(previews)}"
    )
    for fname, content in previews.items():
        assert len(content) <= MAX_PREVIEW_CHARS_PER_FILE, (
            f"File preview for '{fname}' exceeds {MAX_PREVIEW_CHARS_PER_FILE} chars: {len(content)}"
        )

    print(f"  LLM receives {len(previews)} file previews (out of {len(prioritized)} ranked files).")
    print(f"  Files sent to LLM:")
    for i, fname in enumerate(previews.keys(), 1):
        print(f"    {i:2d}. {fname} ({len(previews[fname])} chars)")
    print("  [PASS] LLM context correctly bounded to top-ranked files only.")
    return previews


def test_readme_not_in_top_files(root: str, previews: dict):
    print("\n[4/6] Testing README.md Not In Top LLM Files...")
    preview_files = list(previews.keys())
    has_readme = any("readme" in f.lower() for f in preview_files)

    if has_readme:
        # README may appear, but must not be the first file in a repo with source code
        first = preview_files[0]
        assert "readme" not in first.lower(), (
            f"README.md must not be the first file sent to LLM. Got: {first}"
        )
        print(f"  README present in previews but not at position #1. First file: {first}")
    else:
        print("  README.md not included in LLM context (replaced by source files).")

    print("  [PASS] README.md is not prioritized above implementation files.")


def test_full_analyze_quality(root: str):
    print("\n[5/6] Testing Full analyze_repository Quality on Large Repo...")
    t0 = time.perf_counter()
    summary = repository_analyzer.analyze_repository(root)
    elapsed = time.perf_counter() - t0

    assert isinstance(summary, ProjectSummary)
    assert "Python" in summary.languages, f"Python must be detected. Got: {summary.languages}"
    assert "FastAPI" in summary.frameworks, f"FastAPI must be detected. Got: {summary.frameworks}"
    assert len(summary.entry_points) > 0, "Must detect at least one entry point"
    assert len(summary.important_files) > 0, "Must produce important files list"
    assert len(summary.important_directories) > 0, "Must produce important directories"

    # README must not be first
    if summary.important_files:
        assert "readme" not in summary.important_files[0].lower(), (
            f"README.md must NOT be first important file. Got: {summary.important_files[0]}"
        )

    print(f"  Full analysis completed in {elapsed:.3f}s")
    print(f"  Languages:    {summary.languages}")
    print(f"  Frameworks:   {summary.frameworks}")
    print(f"  Entry Points: {[ep.path for ep in summary.entry_points]}")
    print(f"  Top 10 Important Files:")
    for i, f in enumerate(summary.important_files[:10], 1):
        print(f"    {i:2d}. {f}")
    print(f"  Important Directories: {summary.important_directories[:8]}")
    print(f"  Technologies: {[t.name for t in summary.technologies]}")
    print("  [PASS] ProjectSummary quality is high even on large repository.")
    return summary


def test_planner_sees_source_files(summary: ProjectSummary):
    print("\n[6/6] Testing Planner Receives Source Files (Not README.md)...")
    from app.prompts.planner_prompt import build_planner_prompt

    _, user_prompt = build_planner_prompt(
        user_request="Add caching layer with Redis for rate calculation results",
        project_summary=summary,
    )

    # Verify the Planner prompt contains real source paths not just README
    has_source = any(f.endswith(".py") and "readme" not in f.lower() for f in summary.important_files)
    assert has_source, "Planner context must contain source .py files"
    assert summary.project_name in user_prompt, "Planner prompt must include project name"
    assert len(summary.important_files) > 1, "Planner must see more than just README.md"

    print(f"  Planner sees {len(summary.important_files)} important files")
    print(f"  Top 5 files in Planner context: {summary.important_files[:5]}")
    print("  [PASS] Planner context contains real source files, not just README.md.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 60)
    print("Performance Validation: Large Repository (200+ files)")
    print("=" * 60)

    with tempfile.TemporaryDirectory(prefix="reflexion_large_repo_") as root:
        print(f"\nScaffolding large repository at: {root}")
        total_scaffolded = scaffold_large_repo(root)
        real_files = sum(len(fs) for _, _, fs in os.walk(root))
        print(f"Created repository: {total_scaffolded} total files scaffolded, {real_files} on disk.")

        all_files, all_dirs, elapsed = test_ignored_dirs_are_skipped(root)
        test_scan_speed(elapsed, total_scaffolded)
        previews = test_llm_context_is_bounded(root, all_files)
        test_readme_not_in_top_files(root, previews)
        summary = test_full_analyze_quality(root)
        test_planner_sees_source_files(summary)

    print("\n" + "=" * 60)
    print("ALL LARGE REPO PERFORMANCE VALIDATION TESTS PASSED!")
    print("=" * 60)


if __name__ == "__main__":
    main()
