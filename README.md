# CS 4390 Multiplayer Chess

Two players join a match through a lobby and play chess in the browser. The Python server holds the board and validates every move; the React client sends moves and draws the position the server sends back. The opponent's cursor is sent over a simulated UDP channel on top of WebSocket, with configurable packet loss and delay, sequence numbers to drop late packets, and delta compression.

## Dependencies

Requires Python 3.10+ and Node 20.19+.

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
python3 -m venv .venv
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

## Network simulator

Moves and lobby messages are reliable (WebSocket runs on TCP). The opponent's cursor is treated as an unreliable stream, like UDP: the server can drop or delay its packets on purpose.

In a game, open the Network panel in the sidebar. Loss and delay apply to the cursor packets coming *to* that tab, so set them in one tab and move the mouse in the other. The panel shows:

- packets sent, received and dropped
- stale packets, which arrived after a newer one and were thrown out by the sequence filter
- bytes before and after compression, and the percent saved

Turning delta compression off sends the plain position every time, for comparison.

## Project layout

### Backend (`backend/`)
- `ws_server.py` — WebSocket server; one connection per player, holds delayed cursor packets
- `server.py` — `Matchmaker`: lobbies, games, moves, draws, resigns, and the cursor relay
- `messages.py` — parses and validates every client message
- `lobby.py` — lobby list, passcodes, and seating two players
- `moves.py` — move validation on top of python-chess
- `lib/netsim.py` — network simulator (loss, delay, jitter) and its stats
- `lib/sequence.py` — sequence numbers and the stale packet filter
- `lib/delta.py` — delta compression, including the cursor keyframe/delta encoder
- `tests/` — pytest tests for all of the above

### Frontend (`frontend/src/`)
- `hooks/useGameSocket.ts` — the WebSocket connection and all game state
- `components/` — board, sidebar, lobby dialog, game controls, network panel
- `lib/` — receiver side of the sequence filter and cursor deltas
- `types/protocol.ts` — every message the client and server send

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
