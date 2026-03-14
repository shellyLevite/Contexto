# Frontend (React + Vite)

This folder contains the CONTEXTO web UI.

## What it does

- Chat view for asking questions against ingested personal data
- Upload view for ingesting, listing, and deleting files
- Calls backend endpoints under `VITE_API_BASE_URL`

## Environment

Create `frontend/.env`:

```env
VITE_API_BASE_URL=http://localhost:8000
```

## Run locally

```powershell
cd frontend
npm install
npm run dev
```

## Build

```powershell
npm run build
npm run preview
```

## Main files

- `src/App.jsx` - app shell and tab switching
- `src/components/ChatWindow.jsx` - message history UI
- `src/components/ChatInput.jsx` - prompt input + submit
- `src/components/UploadPage.jsx` - ingest/list/delete UI
- `src/api/chat.js` - `/api/chat` client
- `src/api/ingest.js` - `/api/ingest` and file management clients

## Full project docs

See the root README: `../README.md`.
