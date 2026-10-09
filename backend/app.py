"""
Dirigent backend API - FastAPI application.
"""
import logging
import time
from pathlib import Path
from uuid import UUID

from fastapi import FastAPI, Header, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from backend.config import settings
from backend.paths import is_development
from backend.archive import archive
from backend.archive_parquet import MAX_FILE_BYTES, export_encrypted_parquet, import_encrypted_parquet
from backend.openai_auth import OpenAIAuthError, chatgpt_auth
from backend.provider_credentials import ProviderCredentialError, provider_credentials
from backend.providers.lmstudio import LMStudioProvider
from backend.providers.chatgpt import ChatGPTProvider
from backend.executor.engine import ExecutionEngine
from backend.tools.registry import ToolRegistry, register_tool
from backend.tools.filesystem import ReadFileTool, WriteFileTool
from backend.tools.git import GitStatusTool, GitAddTool, GitCommitTool, GitPushTool

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


app = FastAPI(title="Dirigent API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:1420",
        "http://127.0.0.1:1420",
        "tauri://localhost",
        "http://tauri.localhost",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize tool registry using global registry
from backend.tools.registry import get_registry
tool_registry = get_registry()

# Register tools
tool_registry.register(ReadFileTool())
tool_registry.register(WriteFileTool())
tool_registry.register(GitStatusTool())
tool_registry.register(GitAddTool())
tool_registry.register(GitCommitTool())
tool_registry.register(GitPushTool())

# Get registered tool names for provider parsing
registered_tool_names = list(tool_registry.list_names())
logger.info(f"Registered tools: {registered_tool_names}")

# Keep provider instances isolated while sharing the existing tool/policy registry.
providers = {
    "lmstudio": LMStudioProvider(registered_tools=registered_tool_names),
    "chatgpt": ChatGPTProvider(registered_tools=registered_tool_names),
}
engines = {name: ExecutionEngine(provider=item, tool_registry=tool_registry) for name, item in providers.items()}
engine = engines["lmstudio"]


def _engine_for(provider_name: str) -> ExecutionEngine:
    if provider_name not in engines:
        raise HTTPException(status_code=400, detail=f"Unsupported provider: {provider_name}")
    return engines[provider_name]


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
    recent_repos: List[str]


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


class ChatGPTAuthResponse(BaseModel):
    status: str
    message: Optional[str] = None
    connected: List[Dict[str, Any]] = []
    authorization_url: Optional[str] = None


class ProviderCredentialRequest(BaseModel):
    secret: str


class ProviderCredentialStatus(BaseModel):
    id: str
    label: str
    credential_label: str
    env_var: str
    hint: str
    connected: bool


class GenerateRequest(BaseModel):
    provider: str = "lmstudio"
    model: str
    prompt: str
    conversation_id: Optional[UUID] = None
    effort: Optional[str] = None
    temperature: Optional[float] = 0.7
    max_tokens: Optional[int] = 2048


class GenerateResponse(BaseModel):
    response: str
    conversation_id: str
    run_id: str
    metadata: Dict[str, Any] = {}
    tool_results: Optional[List[Dict[str, Any]]] = None
    policy_decision: Optional[Dict[str, Any]] = None
    validation_errors: Optional[List[str]] = None


class ArchiveActionRequest(BaseModel):
    conversation_id: Optional[UUID] = None
    prompt: str
    response: str
    error: Optional[str] = None
    duration_ms: int = 0
    tool_results: List[Dict[str, Any]] = []


class ArchivePassphraseRequest(BaseModel):
    passphrase: str


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
    
    # Add to recent repositories
    from backend.settings_store import settings_store
    settings_store.add_recent_repo(str(path))
    
    return _workspace_info()


@app.get("/settings", response_model=SettingsResponse)
async def get_settings():
    """Return current application settings."""
    from backend.settings_store import settings_store
    return SettingsResponse(
        lmstudio_host=settings.lmstudio_host,
        lmstudio_port=settings.lmstudio_port,
        lmstudio_url=settings.lmstudio_url,
        api_host=settings.api_host,
        api_port=settings.api_port,
        api_url=settings.api_url,
        repo_path=settings.repo_path or "",
        development_mode=is_development(),
        recent_repos=settings_store.get_recent_repos(),
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
async def list_models(provider: str = "lmstudio"):
    """List models available to the selected provider connection."""
    models = _engine_for(provider).list_models()
    return ModelsResponse(models=models)


@app.get("/auth/chatgpt", response_model=ChatGPTAuthResponse)
async def get_chatgpt_auth_status():
    """Return safe local ChatGPT connection state; never returns tokens."""
    return ChatGPTAuthResponse(**chatgpt_auth.status())


@app.post("/auth/chatgpt/start", response_model=ChatGPTAuthResponse)
async def start_chatgpt_auth():
    """Open the browser for a user-initiated Sign in with ChatGPT flow."""
    try:
        return ChatGPTAuthResponse(**chatgpt_auth.start())
    except OpenAIAuthError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.get("/auth/providers", response_model=List[ProviderCredentialStatus])
async def get_provider_credential_status():
    """List supported key/PAT connectors without exposing credential material."""
    return [ProviderCredentialStatus(**provider) for provider in provider_credentials.status()]


@app.put("/auth/providers/{provider}", response_model=ProviderCredentialStatus)
async def save_provider_credential(provider: str, request: ProviderCredentialRequest):
    """Store a provider credential in owner-only local backend storage."""
    try:
        provider_credentials.save(provider, request.secret)
    except ProviderCredentialError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return next(
        ProviderCredentialStatus(**entry)
        for entry in provider_credentials.status()
        if entry["id"] == provider
    )


@app.delete("/auth/providers/{provider}", status_code=204)
async def delete_provider_credential(provider: str):
    """Remove a locally stored provider credential without revoking it remotely."""
    try:
        provider_credentials.delete(provider)
    except ProviderCredentialError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/generate", response_model=GenerateResponse)
async def generate(request: GenerateRequest):
    """Generate text using a model."""
    selected_engine = _engine_for(request.provider)
    conversation_id, run_id = archive.begin_run(
        conversation_id=str(request.conversation_id) if request.conversation_id else None,
        prompt=request.prompt,
        provider=request.provider,
        model=request.model,
        effort=None,
    )
    started = time.monotonic()
    try:
        result = selected_engine.execute(
            prompt=request.prompt,
            model=request.model,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
        )
    except Exception as e:
        archive.finish_run(
            conversation_id=conversation_id, run_id=run_id,
            response="", status="failed",
            duration_ms=round((time.monotonic() - started) * 1000),
            error=str(e),
        )
        logger.error(f"Generate endpoint error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    metadata = dict(result.get("metadata") or {})
    if request.effort:
        metadata["requested_effort"] = request.effort
    archive.finish_run(
        conversation_id=conversation_id, run_id=run_id,
        response=result["content"], status="completed",
        duration_ms=round((time.monotonic() - started) * 1000),
        metadata=metadata, tool_results=result.get("tool_results"),
        policy_decision=result.get("policy_decision"),
    )
    return GenerateResponse(
        response=result["content"], conversation_id=conversation_id,
        run_id=run_id, metadata=metadata,
        tool_results=result.get("tool_results"),
        policy_decision=result.get("policy_decision"),
        validation_errors=result.get("validation_errors"),
    )


@app.post("/archive/actions")
async def archive_local_action(request: ArchiveActionRequest):
    conversation_id = archive.record_local_action(
        conversation_id=str(request.conversation_id) if request.conversation_id else None, prompt=request.prompt,
        response=request.response, error=request.error,
        tool_results=request.tool_results, duration_ms=request.duration_ms,
    )
    return {"conversation_id": conversation_id}


@app.get("/archive/conversations")
async def list_archived_conversations(search: str = "", limit: int = 50, offset: int = 0):
    return archive.list_conversations(search=search, limit=limit, offset=offset)


@app.get("/archive/conversations/{conversation_id}")
async def get_archived_conversation(conversation_id: str):
    result = archive.get_conversation(conversation_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return result


@app.post("/archive/export.dpa")
async def export_archive_parquet(request: ArchivePassphraseRequest):
    try:
        payload = export_encrypted_parquet(archive, request.passphrase)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return Response(payload, media_type="application/octet-stream", headers={
        "Content-Disposition": "attachment; filename=dirigent-archive.dpa",
        "Cache-Control": "no-store",
    })


@app.post("/archive/import.dpa")
async def import_archive_parquet(request: Request, x_archive_passphrase: str = Header(...)):
    length = request.headers.get("content-length")
    if length and length.isdecimal() and int(length) > MAX_FILE_BYTES:
        raise HTTPException(status_code=413, detail="Archive exceeds the 128 MB import limit")
    data = await request.body()
    try:
        return import_encrypted_parquet(archive, data, x_archive_passphrase)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/archive/import")
async def import_archive_json(payload: Dict[str, Any]):
    try:
        return archive.import_json(payload)
    except (ValueError, TypeError, KeyError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


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
