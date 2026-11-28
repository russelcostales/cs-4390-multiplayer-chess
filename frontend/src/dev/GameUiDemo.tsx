// DEV ONLY: temporary harness for GameOverDialog and GameControls.
// Open with ?demo=ui while running `npm run dev`. Delete this folder (and the
// demo branch in main.tsx) before merging.
import { useState } from 'react';
import { Box, Button, Divider, FormControlLabel, Switch, Typography } from '@mui/material';
import GameOverDialog from '../components/game/GameOverDialog';
import GameControls from '../components/game/GameControls';
import type { Color, DrawOfferState, GameOver, GameOverReason } from '../types/gameState';

type Outcome = 'win' | 'loss' | 'draw';

// The outcomes that make sense for each reason.
const SCENARIOS: { reason: GameOverReason; outcomes: Outcome[] }[] = [
  { reason: 'checkmate', outcomes: ['win', 'loss'] },
  { reason: 'resignation', outcomes: ['win', 'loss'] },
  { reason: 'opponent_disconnected', outcomes: ['win'] },
  { reason: 'stalemate', outcomes: ['draw'] },
  { reason: 'insufficient_material', outcomes: ['draw'] },
  { reason: 'seventyfive_moves', outcomes: ['draw'] },
  { reason: 'fivefold_repetition', outcomes: ['draw'] },
  { reason: 'draw_agreement', outcomes: ['draw'] },
];

const DRAW_OFFERS: DrawOfferState[] = ['none', 'offered_by_me', 'offered_by_opponent'];

const debugBtnSx = { fontSize: 12, textTransform: 'none', height: 28 } as const;

function other(color: Color): Color {
  return color === 'white' ? 'black' : 'white';
}

export default function GameUiDemo() {
  const [myColor, setMyColor] = useState<Color>('white');
  const [started, setStarted] = useState(true);
  const [drawOffer, setDrawOffer] = useState<DrawOfferState>('none');
  const [gameOver, setGameOver] = useState<GameOver | null>(null);
  const [dialogDismissed, setDialogDismissed] = useState(false);
  const [allowViewBoard, setAllowViewBoard] = useState(true);
  const [log, setLog] = useState<string[]>([]);

  const record = (entry: string) => setLog((prev) => [entry, ...prev].slice(0, 8));

  const endGame = (reason: GameOverReason, outcome: Outcome) => {
    const winner = outcome === 'draw' ? null : outcome === 'win' ? myColor : other(myColor);
    setGameOver({ winner, reason });
    setDrawOffer('none');
    setDialogDismissed(false);
    record(`game over: ${reason} (${outcome})`);
  };

  const reset = () => {
    setGameOver(null);
    setDrawOffer('none');
    setDialogDismissed(false);
    setStarted(true);
    record('reset');
  };

  return (
    <Box sx={{ maxWidth: 1080, mx: 'auto', px: '22px', py: 4, display: 'flex', flexWrap: 'wrap', gap: '48px' }}>
      <Box sx={{ flex: '1 1 420px', display: 'flex', flexDirection: 'column', gap: 2 }}>
        <Typography variant="h5">Game UI demo</Typography>
        <Typography sx={{ fontSize: 13, color: '#959595' }}>Dev-only. Not part of the game flow.</Typography>

        <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap', alignItems: 'center' }}>
          <FormControlLabel
            control={<Switch checked={myColor === 'black'} onChange={(e) => setMyColor(e.target.checked ? 'black' : 'white')} />}
            label={`I play ${myColor}`}
          />
          <FormControlLabel
            control={<Switch checked={started} onChange={(e) => setStarted(e.target.checked)} />}
            label="Game started"
          />
          <FormControlLabel
            control={<Switch checked={allowViewBoard} onChange={(e) => setAllowViewBoard(e.target.checked)} />}
            label="Pass onClose (View board)"
          />
          <Button variant="outlined" onClick={reset} sx={debugBtnSx}>Reset</Button>
        </Box>

        <Divider />
        <Typography sx={{ fontSize: 13, color: '#b4b4b4' }}>End the game</Typography>
        {SCENARIOS.map(({ reason, outcomes }) => (
          <Box key={reason} sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
            <Typography sx={{ fontSize: 13, width: 170 }}>{reason}</Typography>
            {outcomes.map((outcome) => (
              <Button key={outcome} variant="outlined" onClick={() => endGame(reason, outcome)} sx={debugBtnSx}>
                {outcome}
              </Button>
            ))}
          </Box>
        ))}
        {gameOver && dialogDismissed && (
          <Button variant="outlined" onClick={() => setDialogDismissed(false)} sx={{ ...debugBtnSx, alignSelf: 'flex-start' }}>
            Reopen dialog
          </Button>
        )}

        <Divider />
        <Typography sx={{ fontSize: 13, color: '#b4b4b4' }}>Draw offer state</Typography>
        <Box sx={{ display: 'flex', gap: 1 }}>
          {DRAW_OFFERS.map((state) => (
            <Button
              key={state}
              variant={drawOffer === state ? 'contained' : 'outlined'}
              onClick={() => setDrawOffer(state)}
              sx={debugBtnSx}
            >
              {state}
            </Button>
          ))}
        </Box>
      </Box>

      <Box sx={{ flex: '1 1 260px', maxWidth: 320 }}>
        <Typography sx={{ fontSize: 13, color: '#b4b4b4' }}>GameControls</Typography>
        <GameControls
          disabled={!started || gameOver !== null}
          drawOffer={drawOffer}
          onResign={() => {
            record('onResign');
            endGame('resignation', 'loss');
          }}
          onOfferDraw={() => {
            record('onOfferDraw');
            setDrawOffer('offered_by_me');
          }}
          onAcceptDraw={() => {
            record('onAcceptDraw');
            endGame('draw_agreement', 'draw');
          }}
          onDeclineDraw={() => {
            record('onDeclineDraw');
            setDrawOffer('none');
          }}
        />

        <Typography sx={{ fontSize: 13, color: '#b4b4b4', mt: 4 }}>Callback log</Typography>
        {log.map((entry, i) => (
          <Typography key={i} sx={{ fontSize: 12, color: '#959595', fontFamily: 'monospace' }}>{entry}</Typography>
        ))}
      </Box>

      <GameOverDialog
        gameOver={dialogDismissed ? null : gameOver}
        myColor={myColor}
        onBackToLobby={() => {
          record('onBackToLobby');
          reset();
        }}
        onClose={allowViewBoard ? () => {
          record('onClose');
          setDialogDismissed(true);
        } : undefined}
      />
    </Box>
  );
}
