import { useState } from 'react';
import { Box, Button, Dialog, Divider, IconButton, TextField, Typography } from '@mui/material';
import { MUTED } from '../../constants';

export interface Lobby {
  id: string;
  name: string;
  locked: boolean;
}

interface LobbyDialogProps {
  open: boolean;
  onClose: () => void;
  lobbies: Lobby[];
  onCreate: (name: string, passcode?: string) => void;
  onJoin: (id: string, passcode?: string) => void;
}

const fieldSx = {
  '& .MuiOutlinedInput-root': {
    bgcolor: '#141414',
    borderRadius: '8px',
    fontSize: 14,
  },
};

const outlineBtnSx = {
  fontSize: 13,
  fontWeight: 500,
  textTransform: 'none',
  color: '#ececec',
  borderColor: '#404040',
  borderRadius: '8px',
  px: '16px',
  height: 32,
} as const;

export default function LobbyDialog({ open, onClose, lobbies, onCreate, onJoin }: LobbyDialogProps) {
  const [name, setName] = useState('');
  const [passcode, setPasscode] = useState('');
  const [joiningId, setJoiningId] = useState<string | null>(null);
  const [joinPasscode, setJoinPasscode] = useState('');

  const handleClose = () => {
    setName('');
    setPasscode('');
    setJoiningId(null);
    setJoinPasscode('');
    onClose();
  };

  const handleCreate = () => {
    onCreate(name.trim(), passcode || undefined);
    handleClose();
  };

  const handleJoin = (lobby: Lobby) => {
    if (!lobby.locked) {
      onJoin(lobby.id);
      handleClose();
      return;
    }
    setJoiningId(joiningId === lobby.id ? null : lobby.id);
    setJoinPasscode('');
  };

  const handleJoinLocked = (id: string) => {
    onJoin(id, joinPasscode);
    handleClose();
  };

  return (
    <Dialog
      open={open}
      onClose={handleClose}
      fullWidth
      maxWidth="xs"
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
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: '20px' }}>
          <Typography sx={{ fontSize: 20, fontWeight: 500 }}>Create a match</Typography>
          <IconButton onClick={handleClose} size="small" sx={{ color: MUTED }}>
            <Typography component="span" sx={{ fontSize: 20, lineHeight: 1 }}>×</Typography>
          </IconButton>
        </Box>

        <Typography sx={{ fontSize: 13, color: '#b4b4b4', mb: '6px' }}>Match name</Typography>
        <TextField
          fullWidth
          size="small"
          placeholder="e.g. Friday blitz"
          value={name}
          onChange={(e) => setName(e.target.value)}
          sx={{ ...fieldSx, mb: '16px' }}
        />

        <Typography sx={{ fontSize: 13, color: '#b4b4b4', mb: '6px' }}>
          Passcode <Box component="span" sx={{ color: MUTED }}>(optional)</Box>
        </Typography>
        <TextField
          fullWidth
          size="small"
          placeholder="Leave blank for an open match"
          value={passcode}
          onChange={(e) => setPasscode(e.target.value)}
          sx={{ ...fieldSx, mb: '16px' }}
        />

        <Box sx={{ display: 'flex', justifyContent: 'flex-end' }}>
          <Button
            disabled={!name.trim()}
            onClick={handleCreate}
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
              '&.Mui-disabled': { color: 'rgba(244,244,244,.5)', opacity: 0.6 },
            }}
          >
            Create match
          </Button>
        </Box>
      </Box>

      <Divider sx={{ borderColor: '#2e2e2e' }} />

      <Box sx={{ p: '24px', pt: '16px' }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: '8px' }}>
          <Typography sx={{ fontSize: 13, color: '#b4b4b4' }}>Open matches</Typography>
          <Typography sx={{ fontSize: 13, color: MUTED }}>{lobbies.length}</Typography>
        </Box>

        <Box sx={{ maxHeight: 260, overflowY: 'auto' }}>
          {lobbies.length === 0 && (
            <Typography sx={{ fontSize: 13, color: '#5b5b5b', py: '10px' }}>No open matches</Typography>
          )}
          {lobbies.map((lobby) => (
            <Box key={lobby.id}>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', py: '8px' }}>
                <Box sx={{ display: 'flex', alignItems: 'baseline', gap: '8px' }}>
                  <Typography sx={{ fontSize: 15 }}>{lobby.name}</Typography>
                  {lobby.locked && <Typography sx={{ fontSize: 11, color: MUTED }}>Locked</Typography>}
                </Box>
                <Button variant="outlined" onClick={() => handleJoin(lobby)} sx={outlineBtnSx}>
                  Join
                </Button>
              </Box>
              {joiningId === lobby.id && (
                <Box sx={{ display: 'flex', gap: '8px', pb: '8px' }}>
                  <TextField
                    fullWidth
                    size="small"
                    placeholder="Passcode"
                    value={joinPasscode}
                    onChange={(e) => setJoinPasscode(e.target.value)}
                    sx={fieldSx}
                  />
                  <Button
                    variant="outlined"
                    disabled={!joinPasscode}
                    onClick={() => handleJoinLocked(lobby.id)}
                    sx={outlineBtnSx}
                  >
                    Enter
                  </Button>
                </Box>
              )}
            </Box>
          ))}
        </Box>
      </Box>
    </Dialog>
  );
}
