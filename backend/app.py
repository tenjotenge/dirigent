"""
Dirigent backend API - FastAPI application.
"""
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from backend.config import settings
from backend.paths import is_development
from backend.providers.lmstudio import LMStudioProvider
from backend.executor.engine import ExecutionEngine
from backend.tools.registry import ToolRegistry, register_tool
from backend.tools.filesystem import ReadFileTool, WriteFileTool
from backend.tools.git import GitStatusTool, GitAddTool, GitCommitTool, GitPushTool


app = FastAPI(title="Dirigent API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize provider
provider = LMStudioProvider()

# Initialize tool registry and register tools
tool_registry = ToolRegistry()
register_tool(ReadFileTool())
register_tool(WriteFileTool())
register_tool(GitStatusTool())
register_tool(GitAddTool())
register_tool(GitCommitTool())
register_tool(GitPushTool())

# Initialize execution engine with tool registry
engine = ExecutionEngine(provider=provider, tool_registry=tool_registry)


# Request/Response models
class HealthResponse(BaseModel):
    status: str
    provider_available: bool
    repo_path: str
    repo_loaded: bool
    lmstudio_url: str
    api_url: str
    development_mode: bool


class WorkspaceResponse(BaseModel):
    repo_path: str
    repo_loaded: bool
    exists: bool
    is_git_repo: bool


class SetWorkspaceRequest(BaseModel):
    repo_path: str


class SettingsResponse(BaseModel):
    lmstudio_host: str
    lmstudio_port: int
    lmstudio_url: str
    api_host: str
    api_port: int
    api_url: str
    repo_path: str
    development_mode: bool


class UpdateSettingsRequest(BaseModel):
    lmstudio_host: Optional[str] = None
    lmstudio_port: Optional[int] = None
    api_host: Optional[str] = None
    api_port: Optional[int] = None


class ConnectionTestResponse(BaseModel):
    success: bool
    message: str
    models_count: int = 0


class ModelsResponse(BaseModel):
    models: List[str]


class GenerateRequest(BaseModel):
    model: str
    prompt: str
    temperature: Optional[float] = 0.7
    max_tokens: Optional[int] = 2048


class GenerateResponse(BaseModel):
    response: str
    tool_results: Optional[List[Dict[str, Any]]] = None
    policy_decision: Optional[Dict[str, Any]] = None


class ReadFileRequest(BaseModel):
    file_path: str


class ReadFileResponse(BaseModel):
    success: bool
    content: Optional[str] = None
    error: Optional[str] = None
    file_path: str
    size_bytes: Optional[int] = None


class WriteFileRequest(BaseModel):
    file_path: str
    content: str


class WriteFileResponse(BaseModel):
    success: bool
    error: Optional[str] = None
    file_path: str
    size_bytes: Optional[int] = None


class RewriteMarkdownRequest(BaseModel):
    file_path: str
    instruction: str
    model: str


class RewriteMarkdownResponse(BaseModel):
    success: bool
    original_content: Optional[str] = None
    rewritten_content: Optional[str] = None
    error: Optional[str] = None
    file_path: str


class GitStatusResponse(BaseModel):
    success: bool
    stdout: Optional[str] = None
    stderr: Optional[str] = None
    error: Optional[str] = None


class GitAddRequest(BaseModel):
    file_paths: List[str]


class GitAddResponse(BaseModel):
    success: bool
    stdout: Optional[str] = None
    stderr: Optional[str] = None
    error: Optional[str] = None


class GitCommitRequest(BaseModel):
    message: str


class GitCommitResponse(BaseModel):
    success: bool
    stdout: Optional[str] = None
    stderr: Optional[str] = None
    error: Optional[str] = None


class GitPushResponse(BaseModel):
    success: bool
    stdout: Optional[str] = None
    stderr: Optional[str] = None
    error: Optional[str] = None


# Endpoints
def _workspace_info() -> WorkspaceResponse:
    repo = settings.repo_path or ""
    exists = bool(repo) and Path(repo).is_dir()
    is_git = exists and (Path(repo) / ".git").exists()
    return WorkspaceResponse(
        repo_path=repo,
        repo_loaded=bool(repo) and exists,
        exists=exists,
        is_git_repo=is_git,
    )


@app.get("/health", response_model=HealthResponse)
async def health():
    """Health check endpoint."""
    ws = _workspace_info()
    return HealthResponse(
        status="ok",
        provider_available=engine.health_check(),
        repo_path=ws.repo_path,
        repo_loaded=ws.repo_loaded,
        lmstudio_url=settings.lmstudio_url,
        api_url=settings.api_url,
        development_mode=is_development(),
    )


@app.get("/workspace", response_model=WorkspaceResponse)
async def get_workspace():
    """Return the active workspace."""
    return _workspace_info()


@app.post("/workspace", response_model=WorkspaceResponse)
async def set_workspace(request: SetWorkspaceRequest):
    """Set the active workspace repository path."""
    path = Path(request.repo_path).resolve()
    if not path.is_dir():
        raise HTTPException(status_code=400, detail=f"Path is not a directory: {path}")
    settings.repo_path = str(path)
    settings.persist()
    return _workspace_info()


@app.get("/settings", response_model=SettingsResponse)
async def get_settings():
    """Return current application settings."""
    return SettingsResponse(
        lmstudio_host=settings.lmstudio_host,
        lmstudio_port=settings.lmstudio_port,
        lmstudio_url=settings.lmstudio_url,
        api_host=settings.api_host,
        api_port=settings.api_port,
        api_url=settings.api_url,
        repo_path=settings.repo_path or "",
        development_mode=is_development(),
    )


@app.patch("/settings", response_model=SettingsResponse)
async def update_settings(request: UpdateSettingsRequest):
    """Update application settings."""
    updates = request.model_dump(exclude_none=True)
    if not updates:
        return await get_settings()

    for key, value in updates.items():
        setattr(settings, key, value)
    settings.persist()
    engine.refresh_provider()
    return await get_settings()


@app.post("/settings/test-lmstudio", response_model=ConnectionTestResponse)
async def test_lmstudio_connection():
    """Test connectivity to LM Studio."""
    try:
        models = engine.list_models()
        if models:
            return ConnectionTestResponse(
                success=True,
                message=f"Connected — {len(models)} model(s) available",
                models_count=len(models),
            )
        available = engine.health_check()
        if available:
            return ConnectionTestResponse(
                success=True,
                message="Connected — no models loaded in LM Studio",
                models_count=0,
            )
        return ConnectionTestResponse(
            success=False,
            message=f"Cannot reach LM Studio at {settings.lmstudio_url}",
        )
    except Exception as exc:
        return ConnectionTestResponse(success=False, message=str(exc))


@app.get("/models", response_model=ModelsResponse)
async def list_models():
    """List available LM Studio models."""
    models = engine.list_models()
    return ModelsResponse(models=models)


@app.post("/generate", response_model=GenerateResponse)
async def generate(request: GenerateRequest):
    """Generate text using a model."""
    try:
        result = engine.execute(
            prompt=request.prompt,
            model=request.model,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
        )
        return GenerateResponse(
            response=result["content"],
            tool_results=result.get("tool_results"),
            policy_decision=result.get("policy_decision"),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/filesystem/read", response_model=ReadFileResponse)
async def read_file_endpoint(request: ReadFileRequest):
    """Read a file."""
    result = engine.execute_tool_direct("read_file", {"file_path": request.file_path})
    return ReadFileResponse(
        success=result.success,
        content=result.stdout,
        error=result.stderr,
        file_path=request.file_path,
        size_bytes=result.data.get("size_bytes") if result.data else None,
    )


@app.post("/tools/filesystem/write", response_model=WriteFileResponse)
async def write_file_endpoint(request: WriteFileRequest):
    """Write content to a file."""
    result = engine.execute_tool_direct("write_file", {"file_path": request.file_path, "content": request.content})
    return WriteFileResponse(
        success=result.success,
        error=result.stderr,
        file_path=request.file_path,
        size_bytes=result.data.get("size_bytes") if result.data else None,
    )


@app.post("/tools/text/rewrite-markdown", response_model=RewriteMarkdownResponse)
async def rewrite_markdown(request: RewriteMarkdownRequest):
    """Rewrite a markdown file using a model."""
    # Read original file using engine
    read_result = engine.execute_tool_direct("read_file", {"file_path": request.file_path})
    if not read_result.success:
        return RewriteMarkdownResponse(
            success=False,
            error=read_result.stderr,
            file_path=request.file_path,
        )
    
    original_content = read_result.stdout
    
    # Generate rewritten content using engine
    prompt = f"""Rewrite the following markdown content according to this instruction: {request.instruction}

Original content:
{original_content}

Return only the rewritten markdown content, no explanations."""
    
    try:
        result = engine.execute(
            prompt=prompt,
            model=request.model,
        )
        rewritten_content = result["content"]
        
        # Write the rewritten content using engine
        write_result = engine.execute_tool_direct("write_file", {"file_path": request.file_path, "content": rewritten_content})
        
        if not write_result.success:
            return RewriteMarkdownResponse(
                success=False,
                error=f"Failed to write file: {write_result.stderr}",
                file_path=request.file_path,
                original_content=original_content,
            )
        
        return RewriteMarkdownResponse(
            success=True,
            original_content=original_content,
            rewritten_content=rewritten_content,
            file_path=request.file_path,
        )
    except Exception as e:
        return RewriteMarkdownResponse(
            success=False,
            error=str(e),
            file_path=request.file_path,
            original_content=original_content,
        )


@app.post("/tools/git/status", response_model=GitStatusResponse)
async def git_status_endpoint():
    """Get git status."""
    result = engine.execute_tool_direct("git_status", {"cwd": settings.repo_path})
    return GitStatusResponse(
        success=result.success,
        stdout=result.stdout,
        stderr=result.stderr,
        error=result.data.get("error") if result.data else None,
    )


@app.post("/tools/git/add", response_model=GitAddResponse)
async def git_add_endpoint(request: GitAddRequest):
    """Stage files for commit."""
    result = engine.execute_tool_direct("git_add", {"file_paths": request.file_paths, "cwd": settings.repo_path})
    return GitAddResponse(
        success=result.success,
        stdout=result.stdout,
        stderr=result.stderr,
        error=result.data.get("error") if result.data else None,
    )


@app.post("/tools/git/commit", response_model=GitCommitResponse)
async def git_commit_endpoint(request: GitCommitRequest):
    """Create a commit."""
    result = engine.execute_tool_direct("git_commit", {"message": request.message, "cwd": settings.repo_path})
    return GitCommitResponse(
        success=result.success,
        stdout=result.stdout,
        stderr=result.stderr,
        error=result.data.get("error") if result.data else None,
    )


@app.post("/tools/git/push", response_model=GitPushResponse)
async def git_push_endpoint():
    """Push commits to remote."""
    result = engine.execute_tool_direct("git_push", {"cwd": settings.repo_path})
    return GitPushResponse(
        success=result.success,
        stdout=result.stdout,
        stderr=result.stderr,
        error=result.data.get("error") if result.data else None,
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.api_host, port=settings.api_port)
