import { Box, Button, Dialog, Typography } from '@mui/material';
import { MUTED } from '../../constants';
import type { Color, GameOver, GameOverReason } from '../../types/gameState';
import {useEffect, useRef} from "react";
import confetti from "canvas-confetti";

interface GameOverDialogProps {
  gameOver: GameOver | null;
  myColor: Color;
  onBackToLobby: () => void;
  // When provided, the player can dismiss the dialog to look at the final board.
  onClose?: () => void;
}

type Outcome = 'won' | 'lost' | 'draw';

const TITLES: Record<Outcome, string> = {
  won: 'You won!',
  lost: 'You lost',
  draw: 'Draw',
};

function describe(reason: GameOverReason, outcome: Outcome): string {
  switch (reason) {
    case 'checkmate':
      return outcome === 'won' ? 'You won by checkmate.' : 'You lost by checkmate.';
    case 'resignation':
      return outcome === 'won' ? 'Your opponent resigned.' : 'You resigned.';
    case 'opponent_disconnected':
      return 'Your opponent left the game.';
    case 'stalemate':
      return 'Draw by stalemate.';
    case 'insufficient_material':
      return 'Draw by insufficient material.';
    case 'seventyfive_moves':
      return 'Draw by the 75-move rule.';
    case 'fivefold_repetition':
      return 'Draw by fivefold repetition.';
    case 'draw_agreement':
      return 'Draw by agreement.';
  }
}

const outlineBtnSx = {
  fontSize: 13,
  fontWeight: 500,
  textTransform: 'none',
  color: '#ececec',
  borderColor: '#404040',
  borderRadius: '8px',
  px: '16px',
  height: 36,
} as const;

export default function GameOverDialog({ gameOver, myColor, onBackToLobby, onClose }: GameOverDialogProps) {
  const celebrated = useRef(false);

  useEffect(() => {
    if  (
      !gameOver ||
      gameOver.winner !== myColor ||
      (gameOver.reason !== 'checkmate' && gameOver.reason !== 'resignation')  ||
      celebrated.current
    ) {
      return;
    }

    celebrated.current = true;
    confetti({
      particleCount: 100,
      spread: 50,
      origin: {y: 0.60},
      disableForReducedMotion: true,
    });
  }, [gameOver, myColor]);
  
  if (gameOver === null) return null;

  const outcome: Outcome = gameOver.winner === null ? 'draw' : gameOver.winner === myColor ? 'won' : 'lost';

  return (
    <Dialog
      open
      onClose={onClose}
      fullWidth
      maxWidth="xs"
      aria-labelledby="game-over-title"
      slotProps={{
        paper: {
          sx: {
            bgcolor: '#1c1c1c',
            backgroundImage: 'none',
            border: '1px solid #2e2e2e',
            borderRadius: '12px',
          },
        },
      }}
    >
      <Box sx={{ p: '24px' }}>
        <Typography id="game-over-title" sx={{ fontSize: 24, fontWeight: 500, letterSpacing: '-0.02em', mb: '6px' }}>
          {TITLES[outcome]}
        </Typography>
        <Typography sx={{ fontSize: 14, color: MUTED, mb: '24px' }}>
          {describe(gameOver.reason, outcome)}
        </Typography>

        <Box sx={{ display: 'flex', justifyContent: 'flex-end', gap: '12px' }}>
          {onClose && (
            <Button variant="outlined" onClick={onClose} sx={outlineBtnSx}>
              View board
            </Button>
          )}
          <Button
            onClick={onBackToLobby}
            sx={{
              height: 36,
              px: '22px',
              fontSize: 14,
              fontWeight: 500,
              textTransform: 'none',
              color: '#f4f4f4',
              borderRadius: '8px',
              border: '1px solid #2c6840',
              background: 'linear-gradient(#3f8a57, #357a4b)',
              '&:hover': { background: 'linear-gradient(#46955f, #3a8352)' },
            }}
          >
            Back to lobby
          </Button>
        </Box>
      </Box>
    </Dialog>
  );
}
