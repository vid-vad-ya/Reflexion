"""Centralized Git Service Abstraction for Reflexion.

Provides secure local workspace management and Git operations wrapper around GitPython.
All Git operations across Reflexion MUST go through this service.
"""

import logging
import os
import re
import shutil
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse, urlunparse

import git
from git.exc import GitCommandError, InvalidGitRepositoryError

from app.core.config import settings

logger = logging.getLogger("reflexion.git")


class GitServiceError(Exception):
    """Base exception for all Git service errors."""
    pass


class InvalidRepositoryURLError(GitServiceError):
    """Raised when the repository URL is invalid or malformed."""
    pass


class RepositoryNotFoundError(GitServiceError):
    """Raised when the remote repository is not found or inaccessible."""
    pass


class GitAuthenticationError(GitServiceError):
    """Raised when authentication with the Git remote fails."""
    pass


class CloneFailureError(GitServiceError):
    """Raised when repository clone operation fails."""
    pass


class WorkspaceCreationError(GitServiceError):
    """Raised when local workspace directory creation fails."""
    pass


class GitService:
    """Centralized Git service managing workspace storage and repository operations."""

    def __init__(self, workspace_dir: Optional[str] = None) -> None:
        """Initialize GitService with target workspace directory.
        
        Args:
            workspace_dir: Optional root directory path. Defaults to settings.LOCAL_WORKSPACE_DIR.
        """
        self._workspace_dir = os.path.abspath(workspace_dir or settings.LOCAL_WORKSPACE_DIR)

    @property
    def workspace_dir(self) -> str:
        """Get the absolute root workspace directory path."""
        return self._workspace_dir

    def _ensure_workspace_root(self) -> None:
        """Ensure the root workspace directory exists safely."""
        try:
            os.makedirs(self._workspace_dir, exist_ok=True)
        except Exception as e:
            logger.error(f"Failed to create workspace root directory {self._workspace_dir}: {e}")
            raise WorkspaceCreationError(f"Could not create workspace root: {str(e)}") from e

    def _sanitize_path_component(self, name: str) -> str:
        """Sanitize directory path component to prevent path traversal attacks.
        
        Args:
            name: Raw string (owner name or repo name).
            
        Returns:
            Sanitized safe directory string.
        """
        if not name:
            return "default"
        # Remove null bytes, slashes, backslashes, and relative path components
        clean = re.sub(r'[\x00/\\?%*:|"<>]', '_', name)
        clean = re.sub(r'\.\.+', '_', clean)
        clean = clean.strip('. ')
        return clean or "default"

    def _get_workspace_path(self, repository_name: str, owner: Optional[str] = None) -> str:
        """Construct and validate absolute workspace path for a repository.
        
        Args:
            repository_name: Name of the repository.
            owner: Optional owner / organization name.
            
        Returns:
            Absolute local filesystem path inside workspace root.
            
        Raises:
            WorkspaceCreationError: If path traversal outside workspace root is detected.
        """
        clean_repo = self._sanitize_path_component(repository_name)
        clean_owner = self._sanitize_path_component(owner) if owner else "standalone"
        
        target_path = os.path.abspath(os.path.join(self._workspace_dir, clean_owner, clean_repo))
        
        # Security Guard: Ensure target path remains strictly within workspace root
        if not target_path.startswith(self._workspace_dir):
            logger.error(f"Path traversal attempt detected: '{repository_name}' under '{owner}'")
            raise WorkspaceCreationError("Invalid repository name or owner resulted in path traversal.")
            
        return target_path

    def _sanitize_url_for_logging(self, url: str) -> str:
        """Remove secrets/tokens from Git URLs before logging.
        
        Args:
            url: Raw git URL.
            
        Returns:
            URL string with access tokens masked.
        """
        return re.sub(r'https://([^:@]+):([^@]+)@', r'https://\1:***@', url)

    def _build_authenticated_url(self, repository_url: str, access_token: Optional[str]) -> str:
        """Build authenticated HTTPS URL if an access token is provided.
        
        Args:
            repository_url: Remote Git URL.
            access_token: Optional GitHub access token.
            
        Returns:
            Authenticated or original URL string.
            
        Raises:
            InvalidRepositoryURLError: If repository_url format is invalid.
        """
        if not repository_url or not isinstance(repository_url, str):
            raise InvalidRepositoryURLError("Repository URL must be a non-empty string.")

        url_str = repository_url.strip()

        if not access_token:
            return url_str

        # If token is provided and URL is HTTPS, embed token securely
        parsed = urlparse(url_str)
        if parsed.scheme in ("http", "https"):
            netloc = parsed.netloc
            # Strip existing credentials if present
            if "@" in netloc:
                netloc = netloc.split("@")[-1]
            auth_netloc = f"x-access-token:{access_token}@{netloc}"
            return urlunparse((parsed.scheme, auth_netloc, parsed.path, parsed.params, parsed.query, parsed.fragment))

        return url_str

    def _detect_default_branch(self, repo: git.Repo) -> str:
        """Robustly detect the default active branch of a Git repository.
        
        Handles detached HEAD, custom default branches (main/master/dev),
        and symbolic ref fallbacks.
        
        Args:
            repo: GitPython Repo instance.
            
        Returns:
            Name of active default branch (e.g. 'main', 'master').
        """
        # 1. Try active_branch if HEAD is not detached
        try:
            if not repo.head.is_detached and repo.active_branch:
                return repo.active_branch.name
        except Exception:
            pass

        # 2. Try symbolic-ref for remote origin/HEAD
        try:
            sym_ref = repo.git.symbolic_ref("refs/remotes/origin/HEAD")
            if sym_ref:
                branch_name = sym_ref.strip().split('/')[-1]
                if branch_name:
                    return branch_name
        except Exception:
            pass

        # 3. Inspect existing branches
        try:
            branch_names = [b.name for b in repo.branches]
            for candidate in ("main", "master", "develop", "trunk"):
                if candidate in branch_names:
                    return candidate
            if branch_names:
                return branch_names[0]
        except Exception:
            pass

        # Fallback default
        return "main"

    def clone_repository(
        self,
        repository_url: str,
        repository_name: str,
        owner: Optional[str] = None,
        access_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Clone a remote Git repository into the local workspace.
        
        If the repository already exists locally, returns existing workspace path
        without recloning.
        
        Args:
            repository_url: Remote Git URL (HTTPS or SSH).
            repository_name: Name of the repository.
            owner: Optional owner or organization name.
            access_token: Optional GitHub access token for private repositories.
            
        Returns:
            Dict containing status, workspace path, default branch, and already_exists flag.
            
        Raises:
            InvalidRepositoryURLError: If URL is malformed.
            GitAuthenticationError: If access is denied (401/403).
            RepositoryNotFoundError: If remote repository is not found (404).
            CloneFailureError: If git clone fails.
            WorkspaceCreationError: If workspace directory creation fails.
        """
        self._ensure_workspace_root()
        target_path = self._get_workspace_path(repository_name, owner)
        safe_url_log = self._sanitize_url_for_logging(repository_url)

        # Check if repository already exists locally
        if os.path.exists(target_path):
            try:
                existing_repo = git.Repo(target_path)
                branch = self._detect_default_branch(existing_repo)
                logger.info(f"Repository already exists locally at '{target_path}'. Reusing existing workspace.")
                return {
                    "status": "success",
                    "workspace": target_path,
                    "default_branch": branch,
                    "already_exists": True,
                }
            except InvalidGitRepositoryError:
                logger.warning(f"Directory '{target_path}' exists but is not a valid Git repo. Removing corrupt path...")
                shutil.rmtree(target_path, ignore_errors=True)
            except Exception as e:
                logger.warning(f"Failed to inspect existing repo at '{target_path}': {e}. Re-cloning...")
                shutil.rmtree(target_path, ignore_errors=True)

        # Ensure parent owner directory exists
        os.makedirs(os.path.dirname(target_path), exist_ok=True)

        auth_url = self._build_authenticated_url(repository_url, access_token)

        logger.info(f"Starting Git clone for repository '{repository_name}' from '{safe_url_log}' into '{target_path}'")

        try:
            repo = git.Repo.clone_from(auth_url, target_path)
            default_branch = self._detect_default_branch(repo)
            logger.info(f"Git clone completed successfully for '{repository_name}' [Branch: {default_branch}]")
            return {
                "status": "success",
                "workspace": target_path,
                "default_branch": default_branch,
                "already_exists": False,
            }
        except GitCommandError as e:
            # Clean up partial failed directory
            if os.path.exists(target_path):
                shutil.rmtree(target_path, ignore_errors=True)

            stderr = (e.stderr or str(e)).lower()
            safe_error_msg = self._sanitize_url_for_logging(str(e))

            logger.error(f"Git clone failed for '{safe_url_log}': {safe_error_msg}")

            if any(term in stderr for term in ("authentication failed", "could not read username", "permission denied", "401", "403", "invalid credentials")):
                raise GitAuthenticationError(f"Authentication failed for repository '{safe_url_log}'. Please check access token.") from e
            elif any(term in stderr for term in ("repository not found", "not found", "404", "does not exist")):
                raise RepositoryNotFoundError(f"Repository not found at '{safe_url_log}'.") from e
            elif any(term in stderr for term in ("invalid url", "could not resolve host", "unable to access")):
                raise InvalidRepositoryURLError(f"Invalid or unreachable repository URL '{safe_url_log}'.") from e
            else:
                raise CloneFailureError(f"Failed to clone repository: {safe_error_msg}") from e
        except Exception as e:
            if os.path.exists(target_path):
                shutil.rmtree(target_path, ignore_errors=True)
            safe_msg = self._sanitize_url_for_logging(str(e))
            logger.error(f"Unexpected error during clone of '{safe_url_log}': {safe_msg}")
            raise CloneFailureError(f"Unexpected error during repository clone: {safe_msg}") from e

    def repository_exists(self, repository_name: str, owner: Optional[str] = None) -> bool:
        """Check whether a repository exists locally in workspace and is valid.
        
        Args:
            repository_name: Name of the repository.
            owner: Optional owner or organization name.
            
        Returns:
            True if workspace exists and contains a valid Git repo, False otherwise.
        """
        try:
            path = self._get_workspace_path(repository_name, owner)
            if os.path.exists(path):
                _ = git.Repo(path)
                return True
        except Exception:
            pass
        return False

    def get_repository(self, repository_name: str, owner: Optional[str] = None) -> Optional[str]:
        """Get local workspace path for a repository if it exists.
        
        Args:
            repository_name: Name of the repository.
            owner: Optional owner name.
            
        Returns:
            Workspace path string if repository exists, None otherwise.
        """
        if self.repository_exists(repository_name, owner):
            return self._get_workspace_path(repository_name, owner)
        return None

    def get_current_branch(self, workspace_path: str) -> str:
        """Get active branch name for a local repository workspace.
        
        Args:
            workspace_path: Local filesystem path to repository.
            
        Returns:
            Active branch name string.
            
        Raises:
            RepositoryNotFoundError: If workspace_path is invalid.
        """
        if not os.path.exists(workspace_path):
            raise RepositoryNotFoundError(f"Local workspace not found at '{workspace_path}'.")

        try:
            repo = git.Repo(workspace_path)
            return self._detect_default_branch(repo)
        except InvalidGitRepositoryError as e:
            raise RepositoryNotFoundError(f"Path '{workspace_path}' is not a valid Git repository.") from e
        except Exception as e:
            raise GitServiceError(f"Failed to retrieve current branch: {str(e)}") from e

    def pull_repository(self, workspace_path: str) -> str:
        """Pull latest changes from remote for a workspace (stub for future phases)."""
        if not os.path.exists(workspace_path):
            raise RepositoryNotFoundError(f"Local workspace not found at '{workspace_path}'.")
        try:
            repo = git.Repo(workspace_path)
            origin = repo.remotes.origin
            origin.pull()
            logger.info(f"Pulled latest changes for workspace '{workspace_path}'")
            return self.get_current_branch(workspace_path)
        except Exception as e:
            raise GitServiceError(f"Failed to pull repository changes: {str(e)}") from e

    def checkout_branch(self, workspace_path: str, branch_name: str, create: bool = False) -> str:
        """Checkout or create a branch in workspace (stub for future phases)."""
        if not os.path.exists(workspace_path):
            raise RepositoryNotFoundError(f"Local workspace not found at '{workspace_path}'.")
        try:
            repo = git.Repo(workspace_path)
            if create:
                new_branch = repo.create_head(branch_name)
                new_branch.checkout()
            else:
                repo.git.checkout(branch_name)
            logger.info(f"Checked out branch '{branch_name}' in '{workspace_path}'")
            return branch_name
        except Exception as e:
            raise GitServiceError(f"Failed to checkout branch '{branch_name}': {str(e)}") from e

    def list_local_repositories(self) -> List[Dict[str, Any]]:
        """List all repositories currently stored in local workspace directory."""
        self._ensure_workspace_root()
        repositories: List[Dict[str, Any]] = []

        if not os.path.exists(self._workspace_dir):
            return repositories

        for owner in os.listdir(self._workspace_dir):
            owner_path = os.path.join(self._workspace_dir, owner)
            if not os.path.isdir(owner_path):
                continue
            for repo_name in os.listdir(owner_path):
                repo_path = os.path.join(owner_path, repo_name)
                if os.path.isdir(repo_path):
                    try:
                        r = git.Repo(repo_path)
                        branch = self._detect_default_branch(r)
                        repositories.append({
                            "owner": owner,
                            "repository_name": repo_name,
                            "workspace": repo_path,
                            "default_branch": branch,
                        })
                    except Exception:
                        pass
        return repositories

    def delete_workspace(self, repository_name: str, owner: Optional[str] = None) -> bool:
        """Delete local workspace directory for a repository."""
        try:
            path = self._get_workspace_path(repository_name, owner)
            if os.path.exists(path):
                shutil.rmtree(path, ignore_errors=True)
                logger.info(f"Deleted workspace at '{path}'")
                return True
        except Exception as e:
            logger.error(f"Failed to delete workspace for '{repository_name}': {e}")
            raise GitServiceError(f"Failed to delete workspace: {str(e)}") from e
        return False


# Global singleton instance and shortcut alias
git_service = GitService()
git_svc = git_service
