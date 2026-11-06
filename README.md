# CS 4390 Multiplayer Chess Demo

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

### Setup

Run from the repository root:

```bash
cd frontend
npm install
npm run dev
```

Open the local URL printed in the terminal.

### Build and Lint

Run from `frontend`:

```bash
npm run build
npm run lint
```

## Backend

Run from the repository root:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```