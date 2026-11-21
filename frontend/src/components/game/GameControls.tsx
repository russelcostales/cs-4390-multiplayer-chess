import { useState } from 'react';
import { Button, Stack, Typography } from '@mui/material';
import type { DrawOfferState } from '../../types/gameState';

interface GameControlsProps {
  // True when the game is over or has not started.
  disabled: boolean;
  drawOffer: DrawOfferState;
  onResign: () => void;
  onOfferDraw: () => void;
  onAcceptDraw: () => void;
  onDeclineDraw: () => void;
}

const btnSx = {
  fontSize: 13,
  fontWeight: 500,
  textTransform: 'none',
  color: '#b4b4b4',
  borderColor: '#404040',
  borderRadius: '8px',
  px: '16px',
  height: 34,
  '&.Mui-disabled': {
    color: 'rgba(180,180,180,.45)',
    borderColor: 'rgba(64,64,64,.6)',
  },
} as const;

const dangerBtnSx = {
  ...btnSx,
  color: '#e08a8a',
  borderColor: '#6b3434',
} as const;

export default function GameControls({
  disabled,
  drawOffer,
  onResign,
  onOfferDraw,
  onAcceptDraw,
  onDeclineDraw,
}: GameControlsProps) {
  const [confirmingResign, setConfirmingResign] = useState(false);

  // Drop a pending confirmation if the game ends while it is showing.
  if (disabled && confirmingResign) {
    setConfirmingResign(false);
  }

  const handleConfirmResign = () => {
    setConfirmingResign(false);
    onResign();
  };

  return (
    <Stack spacing="12px" sx={{ pt: '20px' }}>
      {drawOffer === 'offered_by_opponent' && (
        <Stack spacing="8px">
          <Typography sx={{ fontSize: 13, color: '#ececec' }}>Your opponent offers a draw.</Typography>
          <Stack direction="row" spacing="12px">
            <Button variant="outlined" disabled={disabled} onClick={onAcceptDraw} sx={btnSx}>
              Accept
            </Button>
            <Button variant="outlined" disabled={disabled} onClick={onDeclineDraw} sx={btnSx}>
              Decline
            </Button>
          </Stack>
        </Stack>
      )}

      <Stack direction="row" spacing="12px">
        {drawOffer !== 'offered_by_opponent' && (
          <Button
            variant="outlined"
            disabled={disabled || drawOffer === 'offered_by_me'}
            onClick={onOfferDraw}
            sx={btnSx}
          >
            {drawOffer === 'offered_by_me' ? 'Draw offered…' : 'Offer draw'}
          </Button>
        )}

        {confirmingResign ? (
          <>
            <Button variant="outlined" onClick={handleConfirmResign} sx={dangerBtnSx}>
              Confirm resign
            </Button>
            <Button variant="outlined" onClick={() => setConfirmingResign(false)} sx={btnSx}>
              Cancel
            </Button>
          </>
        ) : (
          <Button variant="outlined" disabled={disabled} onClick={() => setConfirmingResign(true)} sx={btnSx}>
            Resign
          </Button>
        )}
      </Stack>
    </Stack>
  );
}
