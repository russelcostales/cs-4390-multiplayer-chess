import { Chessboard } from 'react-chessboard';
import { Box } from '@mui/material';
import PlayerRow from './PlayerRow';
import RemoteCursor from './RemoteCursor';
import { LIGHT, DARK, START_FEN } from '../../constants';
import type { GameSocket } from '../../hooks/useGameSocket';
import type { Color } from '../../types/gameState';

interface BoardColumnProps {
  socket: GameSocket;
}

const label = (color: Color) => (color === 'white' ? 'White' : 'Black');

export default function BoardColumn({ socket }: BoardColumnProps) {
  const { game, fen, turn, makeMove, opponentCursor, sendCursor } = socket;
  const myColor: Color = game?.color ?? 'white';
  const opponentColor: Color = myColor === 'white' ? 'black' : 'white';
  const myPrefix = myColor === 'white' ? 'w' : 'b';
  // cursor coords are always from white's side, black's board is upside down so flip both ways
  const flip = (v: number) => (myColor === 'black' ? 1 - v : v);
  const clamp = (v: number) => Math.min(1, Math.max(0, v));

  return (
    <Box sx={{ flex: '1 1 480px', maxWidth: 600, display: 'flex', flexDirection: 'column', gap: '14px' }}>
      <PlayerRow prefix={game ? 'Opponent' : '—'} label={label(opponentColor)} />

      <Box
        sx={{ width: '100%', lineHeight: 0, position: 'relative' }}
        onPointerMove={(event) => {
          if (!game) return;
          const rect = event.currentTarget.getBoundingClientRect();
          sendCursor(
            flip(clamp((event.clientX - rect.left) / rect.width)),
            flip(clamp((event.clientY - rect.top) / rect.height)),
          );
        }}
      >
        <Chessboard
          options={{
            id: 'game-board',
            position: game ? fen : START_FEN,
            boardOrientation: myColor,
            allowDragging: game !== null,
            canDragPiece: ({ piece }) => piece.pieceType.startsWith(myPrefix),
            onPieceDrop: ({ piece, sourceSquare, targetSquare }) => {
              if (!game || !targetSquare || turn !== game.color) return false;
              const promotes =
                piece.pieceType[1] === 'P' && (targetSquare[1] === '8' || targetSquare[1] === '1');
              makeMove(`${sourceSquare}${targetSquare}${promotes ? 'q' : ''}`);
              return false;
            },
            boardStyle: {
              borderRadius: '8px',
              overflow: 'hidden',
              boxShadow: '0 0 0 1px #5b5b5b, 0 6px 18px rgba(0,0,0,0.55)',
            },
            lightSquareStyle: { backgroundColor: LIGHT },
            darkSquareStyle: { backgroundColor: DARK },
            lightSquareNotationStyle: { color: DARK, fontWeight: 600 },
            darkSquareNotationStyle: { color: LIGHT, fontWeight: 600 },
          }}
        />
        {game && opponentCursor && (
          <RemoteCursor x={flip(opponentCursor.x)} y={flip(opponentCursor.y)} />
        )}
      </Box>

      <PlayerRow prefix="You" label={label(myColor)} />
    </Box>
  );
}