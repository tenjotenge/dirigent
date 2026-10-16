# Dirigent desktop frontend

The frontend is a React and TypeScript application packaged with Tauri. It communicates with the local FastAPI service in `../backend`.

For installation, launch instructions, and project status, start with the [root README](../README.md). The backend must be running when using Vite in a browser:

```bash
cd frontend
npm ci
npm run dev
```

Use `npm run tauri dev` for the desktop development build and `npm run build` to type-check and bundle the web assets. The Tauri development prerequisites are linked from the root README.
