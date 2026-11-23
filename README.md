# CS 4390 Multiplayer Chess Demo

Two players join a match through a lobby and play chess in the browser. The Python server holds the board and validates every move; the React client sends moves and draws the position the server sends back. The opponent's cursor is sent over a simulated UDP-style channel on top of WebSocket (in progress).

## Dependencies

### Frontend
- React + TypeScript — interface development
- Vite — development server and production builds
- Material UI + Emotion — UI components and styling
- react-chessboard — interactive chessboard
- React Spring — animations
- ESLint — code checks
- React Compiler — automatic React optimizations

### Backend
- chess — chess rules and move validation
- websockets — real-time communication
- Pydantic — data validation
- pytest — Python tests

## Setup

Run from the repository root.

### Frontend

```bash
cd frontend
npm install
```

### Backend

macOS / Linux:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Windows (PowerShell):

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Run

Start the backend from `backend` with the virtual environment active. It listens on `ws://localhost:8765`:

```bash
python ws_server.py
```

Start the frontend from `frontend`:

```bash
npm run dev
```

Open the local URL printed in the terminal in two browser tabs. Create a match in one tab and join it from the other.

## Test and Lint

Backend, from `backend` with the virtual environment active:

```bash
python -m pytest tests
```

Frontend, from `frontend`:

```bash
npm run build
npm run lint
```
