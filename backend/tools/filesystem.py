"""
Filesystem tools implementation.
"""
from pathlib import Path
from typing import Dict, Any
from backend.core.interfaces import BaseTool, ToolResult


class ReadFileTool(BaseTool):
    """Tool for reading file contents."""
    
    @property
    def name(self) -> str:
        return "read_file"
    
    def run(self, args: Dict[str, Any]) -> ToolResult:
        """Read a file and return its contents."""
        file_path = args.get("file_path")
        
        if not file_path:
            return ToolResult(
                success=False,
                stderr="Missing required argument: file_path",
            )
        
        try:
            path = Path(file_path)
            if not path.exists():
                return ToolResult(
                    success=False,
                    stderr=f"File not found: {file_path}",
                    data={"file_path": file_path},
                )
            
            content = path.read_text(encoding="utf-8")
            return ToolResult(
                success=True,
                stdout=content,
                data={
                    "file_path": file_path,
                    "size_bytes": len(content.encode("utf-8")),
                },
            )
        except Exception as e:
            return ToolResult(
                success=False,
                stderr=str(e),
                data={"file_path": file_path},
            )


class WriteFileTool(BaseTool):
    """Tool for writing content to files."""
    
    @property
    def name(self) -> str:
        return "write_file"
    
    def run(self, args: Dict[str, Any]) -> ToolResult:
        """Write content to a file."""
        file_path = args.get("file_path")
        content = args.get("content", "")
        
        if not file_path:
            return ToolResult(
                success=False,
                stderr="Missing required argument: file_path",
            )
        
        try:
            path = Path(file_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            return ToolResult(
                success=True,
                stdout=f"Successfully wrote to {file_path}",
                data={
                    "file_path": file_path,
                    "size_bytes": len(content.encode("utf-8")),
                },
            )
        except Exception as e:
            return ToolResult(
                success=False,
                stderr=str(e),
                data={"file_path": file_path},
            )
