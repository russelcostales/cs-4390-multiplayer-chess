import { useState } from 'react';
import { Dialog, DialogActions, DialogContent, DialogTitle, Box, Typography, Button, Divider } from '@mui/material';
import { MUTED } from '../../constants';
import type { GameSocket } from '../../hooks/useGameSocket';
import LobbyDialog from '../lobby/LobbyDialog';
import MoveHistory from './MoveHistory';

interface SidebarProps {
    socket: GameSocket;
}

export default function Sidebar({ socket }: SidebarProps) {
    const [lobbyOpen, setLobbyOpen] = useState(false);
    const { status, lobbies, myLobby, game, error, moves, turn } = socket;
    const turnLabel = turn === 'white' ? 'White to play' : 'Black to play';
    const openLobbies = lobbies.filter((lobby) => lobby.id !== myLobby?.id);

    let title = 'Not in a game';
    let subtitle = 'Create a match or join one from the list.';
    if (game) {
        title = `Playing as ${game.color === 'white' ? 'White' : 'Black'}`;
        subtitle = 'Your opponent has joined.';
    } else if (myLobby) {
        title = 'Waiting for an opponent';
        subtitle = `Match: ${myLobby.name}`;
    } else if (status === 'connecting') {
        subtitle = 'Connecting to the server…';
    } else if (status === 'closed') {
        subtitle = 'Disconnected from the server.';
    }

    return (
        <Box sx={{ flex: '1 1 260px', maxWidth: 320, display: 'flex', flexDirection: 'column', pt: '34px' }}>
            <Typography variant="h4" sx={{ fontWeight: 500, letterSpacing: '-0.02em', lineHeight: 1.1, mb: 1 }}>
                {title}
            </Typography>
            <Typography sx={{ fontSize: 13, color: MUTED }}>{subtitle}</Typography>

            {!game && !myLobby && (
                <Button
                    disabled={status !== 'open'}
                    onClick={() => {
                        socket.listLobbies();
                        setLobbyOpen(true);
                    }}
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
                        '&.Mui-disabled': { color: 'rgba(244,244,244,.5)', opacity: 0.6 },
                    }}
                >
                    Join game
                </Button>
            )}

            {myLobby && !game && (
                <Button
                    variant="outlined"
                    onClick={() => socket.leaveLobby()}
                    sx={{
                        alignSelf: 'flex-start',
                        mt: '20px',
                        fontSize: 13,
                        fontWeight: 500,
                        textTransform: 'none',
                        color: '#ececec',
                        borderColor: '#404040',
                        borderRadius: '8px',
                        px: '16px',
                        height: 34,
                    }}
                >
                    Cancel
                </Button>
            )}

            {error && (
                <Typography
                    onClick={socket.clearError}
                    sx={{ mt: '12px', fontSize: 13, color: '#e5776b', cursor: 'pointer' }}
                >
                    {error}
                </Typography>
            )}

            <Box sx={{ mt: 5, display: 'flex', flexDirection: 'column', flex: 1, minHeight: 200 }}>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', pb: '10px' }}>
                    <Typography sx={{ fontSize: 13, color: '#b4b4b4' }}>Moves</Typography>
                    <Typography sx={{ fontSize: 13, color: MUTED }}>{turnLabel}</Typography>
                </Box>
                <Divider sx={{ borderColor: 'rgba(236,236,236,.14)' }} />
                <MoveHistory moves={moves} />
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
                lobbies={openLobbies}
                onCreate={socket.createLobby}
                onJoin={socket.joinLobby}
            />
            <Dialog open={socket.disconnectDialogOpen} onClose={() => socket.closeDisconnectDialog()}>
                <DialogTitle>Opponent Disconnected</DialogTitle>
                <DialogContent>
                    <Typography>Your opponent has disconnected from the game.</Typography>
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => socket.closeDisconnectDialog()}>OK</Button>
                </DialogActions>
            </Dialog>
        </Box>
    );
}