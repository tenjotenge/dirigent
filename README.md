# Dirigent

A local-first "workspace controller" for software development.

Dirigent provides a single place where you can sit in front of a repository and use natural language to control your development workflow. The system intelligently decides whether operations require text editing, Git operations, or model inference.

## Core Architecture

Dirigent separates intelligence from action through two key components:

### Providers (Intelligence Layer)
Providers are models that generate text or decisions. They suggest what should happen but never directly perform actions.

- **LM Studio** (currently implemented): Local model inference
- Future: ChatGPT, Claude, Codex, Devin

### Tools (Action Layer)
Tools are deterministic operations on your machine. They perform the actual actions suggested by providers.

- **Filesystem**: Read and write files
- **Git**: Status, add, commit, push operations
- **Text operations**: Rewrite markdown files using providers

## Design Philosophy

- **Explicit and inspectable**: Every action is logged and visible
- **Never silent**: No automatic modifications or pushes without clear tool invocation
- **Separation of concerns**: Intelligence (models) vs action (tools)
- **Simple architecture**: Readable code over clever abstractions
- **Future-ready**: Designed for expansion (WebSockets, multi-step orchestration, background tasks, autonomous workflows)

## Project Structure

```
dirigent/
├── backend/
│   ├── app.py              # FastAPI application with REST endpoints
│   ├── config.py           # Configuration settings
│   ├── providers/
│   │   ├── base.py         # Base provider interface
│   │   └── lmstudio.py     # LM Studio provider implementation
│   └── tools/
│       ├── filesystem.py   # File read/write tools
│       └── git.py          # Git operation tools
├── frontend/
│   ├── src/
│   │   ├── App.tsx         # Main React component
│   │   └── App.css         # UI styling
│   └── src-tauri/          # Tauri desktop app configuration
├── run_backend.py          # Backend development server script
└── README.md               # This file
```

## Prerequisites

- Python 3.12+
- Node.js 18+
- LM Studio running locally (default: `127.0.0.1:1234`)

## Installation

### Backend Setup

1. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install backend dependencies:
```bash
pip install -r backend/requirements.txt
```

### Frontend Setup

1. Install frontend dependencies:
```bash
cd frontend
npm install
```

## Running the Application

### Start the Backend

The backend runs a FastAPI server on `http://127.0.0.1:8000`.

```bash
python run_backend.py
```

Or manually:
```bash
cd backend
python -m uvicorn app:app --reload --host 127.0.0.1 --port 8000
```

### Start the Frontend

The frontend runs as a Tauri desktop application.

```bash
cd frontend
npm run tauri dev
```

### Configuration

Backend settings can be configured via environment variables or a `.env` file:

- `API_HOST`: Backend API host (default: `127.0.0.1`)
- `API_PORT`: Backend API port (default: `8000`)
- `LMSTUDIO_HOST`: LM Studio host (default: `127.0.0.1`)
- `LMSTUDIO_PORT`: LM Studio port (default: `1234`)
- `REPO_PATH`: Repository path for Git operations (default: `.`)

## API Endpoints

### Health & Models
- `GET /health` - Health check and provider availability
- `GET /models` - List available LM Studio models

### Generation
- `POST /generate` - Generate text using a selected model

### Filesystem Tools
- `POST /tools/filesystem/read` - Read a file
- `POST /tools/filesystem/write` - Write content to a file

### Text Operations
- `POST /tools/text/rewrite-markdown` - Rewrite a markdown file using a model

### Git Tools
- `POST /tools/git/status` - Get git status
- `POST /tools/git/add` - Stage files for commit
- `POST /tools/git/commit` - Create a commit
- `POST /tools/git/push` - Push commits to remote

## Usage Examples

### Clean up a README
1. Select a model from the dropdown
2. Type: "clean up this README to make it clearer"
3. The system will read the file, use the model to rewrite it, and write the changes

### Check Git status
1. Click "Git Status" in the Quick Actions panel
2. The git status appears in the chat panel

### Make a commit and push
1. Use the chat to instruct: "commit these changes with message 'fix bug' and push"
2. The system executes the git add, commit, and push operations

### Read a file
1. Click "Read README.md" in Quick Actions
2. The file contents appear in the chat panel

## Frontend Features

- **Sidebar**: Repository context, model selector, quick actions, action log
- **Chat Panel**: Natural language interface for instructions and responses
- **Model Selector**: Choose from available LM Studio models
- **Action Log**: Real-time visibility of all tool invocations (model calls, file operations, git commands)

## Future Expansion

The architecture is designed for future additions:

- **Additional Providers**: ChatGPT, Claude, Codex, Devin
- **Streaming**: WebSocket support for real-time responses
- **Orchestration**: Multi-step workflows and autonomous agents
- **Background Tasks**: Async job execution
- **More Tools**: Extended filesystem operations, testing, deployment

## Development

### Backend Development
- Backend uses FastAPI with auto-reload enabled
- API documentation available at `http://127.0.0.1:8000/docs`

### Frontend Development
- Frontend uses React with TypeScript
- Tauri handles desktop app packaging
- Hot reload enabled during development

## License

MIT
