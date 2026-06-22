"""
Git tools implementation.
"""
import subprocess
from typing import Dict, Any, List
from backend.core.interfaces import BaseTool, ToolResult
from backend.config import settings


def _run_git_command(args: List[str], cwd: str = ".") -> ToolResult:
    """Run a git command and return structured output."""
    try:
        result = subprocess.run(
            ["git"] + args,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=True,
        )
        return ToolResult(
            success=True,
            stdout=result.stdout,
            stderr=result.stderr,
            data={"return_code": result.returncode},
        )
    except subprocess.CalledProcessError as e:
        return ToolResult(
            success=False,
            stdout=e.stdout,
            stderr=e.stderr,
            data={
                "return_code": e.returncode,
                "error": str(e),
            },
        )
    except Exception as e:
        return ToolResult(
            success=False,
            stderr=str(e),
        )


class GitStatusTool(BaseTool):
    """Tool for getting git status."""
    
    @property
    def name(self) -> str:
        return "git_status"
    
    def run(self, args: Dict[str, Any]) -> ToolResult:
        """Get git status."""
        cwd = args.get("cwd", settings.repo_path)
        return _run_git_command(["status", "--porcelain"], cwd)


class GitAddTool(BaseTool):
    """Tool for staging files for commit."""
    
    @property
    def name(self) -> str:
        return "git_add"
    
    def run(self, args: Dict[str, Any]) -> ToolResult:
        """Stage files for commit."""
        file_paths = args.get("file_paths", [])
        cwd = args.get("cwd", settings.repo_path)
        
        if not file_paths:
            return ToolResult(
                success=False,
                stderr="Missing required argument: file_paths",
            )
        
        return _run_git_command(["add"] + file_paths, cwd)


class GitCommitTool(BaseTool):
    """Tool for creating a commit."""
    
    @property
    def name(self) -> str:
        return "git_commit"
    
    def run(self, args: Dict[str, Any]) -> ToolResult:
        """Create a commit."""
        message = args.get("message")
        cwd = args.get("cwd", settings.repo_path)
        
        if not message:
            return ToolResult(
                success=False,
                stderr="Missing required argument: message",
            )
        
        return _run_git_command(["commit", "-m", message], cwd)


class GitPushTool(BaseTool):
    """Tool for pushing commits to remote."""
    
    @property
    def name(self) -> str:
        return "git_push"
    
    def run(self, args: Dict[str, Any]) -> ToolResult:
        """Push commits to remote."""
        cwd = args.get("cwd", settings.repo_path)
        return _run_git_command(["push"], cwd)
