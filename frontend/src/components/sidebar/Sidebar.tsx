import { useState } from 'react';
import { Box, Typography, Button, Divider } from '@mui/material';
import { MUTED } from '../../constants';
import LobbyDialog, { type Lobby } from '../lobby/LobbyDialog';

export default function Sidebar() {
  const [lobbyOpen, setLobbyOpen] = useState(false);

  // TODO: populate from the server once the protocol exists
  const [lobbies] = useState<Lobby[]>([]);

  return (
    <Box sx={{ flex: '1 1 260px', maxWidth: 320, display: 'flex', flexDirection: 'column', pt: '34px' }}>
      <Typography variant="h4" sx={{ fontWeight: 500, letterSpacing: '-0.02em', lineHeight: 1.1, mb: 1 }}>
        Not in a game
      </Typography>
      <Typography sx={{ fontSize: 13, color: MUTED }}>
        Join to be matched with an opponent. You play White.
      </Typography>

      <Button
        onClick={() => setLobbyOpen(true)}
        sx={{
          alignSelf: 'flex-start',
          mt: '20px',
          height: 38,
          px: '22px',
          fontSize: 15,
          fontWeight: 500,
          color: '#f4f4f4',
          borderRadius: '8px',
          border: '1px solid #2c6840',
          background: 'linear-gradient(#3f8a57, #357a4b)',
          textTransform: 'none',
          boxShadow: 'inset 0 1px 0 rgba(255,255,255,.08), 0 1px 2px rgba(0,0,0,.4)',
          '&:hover': { background: 'linear-gradient(#46955f, #3a8352)' },
        }}
      >
        Join game
      </Button>

      <Box sx={{ mt: 5, display: 'flex', flexDirection: 'column', flex: 1, minHeight: 200 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', pb: '10px' }}>
          <Typography sx={{ fontSize: 13, color: '#b4b4b4' }}>Moves</Typography>
          <Typography sx={{ fontSize: 13, color: MUTED }}>White to play</Typography>
        </Box>
        <Divider sx={{ borderColor: 'rgba(236,236,236,.14)' }} />
        <Typography sx={{ fontSize: 13, color: '#5b5b5b', pt: '12px' }}>No moves yet</Typography>
      </Box>

      <Box sx={{ display: 'flex', gap: '12px', pt: '20px' }}>
        {(['Offer draw', 'Resign'] as const).map((label) => (
          <Button
            key={label}
            disabled
            variant="outlined"
            sx={{
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
            }}
          >
            {label}
          </Button>
        ))}
      </Box>

      <LobbyDialog
        open={lobbyOpen}
        onClose={() => setLobbyOpen(false)}
        lobbies={lobbies}
        onCreate={(name, passcode) => console.log('create', name, passcode)}
        onJoin={(id, passcode) => console.log('join', id, passcode)}
      />
    </Box>
  );
}