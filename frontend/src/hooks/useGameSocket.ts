import { useEffect, useRef, useState } from 'react';
import { WS_URL } from '../constants';
import type { Color } from '../types/gameState';
import type { ClientMessage, LobbySummary, ServerMessage } from '../types/protocol';

export type SocketStatus = 'connecting' | 'open' | 'closed';

export interface GameInfo {
    gameId: string;
    color: Color;
    opponent: { id: string; name: string };
}

export function useGameSocket() {
    const socketRef = useRef<WebSocket | null>(null);
    const [status, setStatus] = useState<SocketStatus>('connecting');
    const [lobbies, setLobbies] = useState<LobbySummary[]>([]);
    const [myLobby, setMyLobby] = useState<LobbySummary | null>(null);
    const [game, setGame] = useState<GameInfo | null>(null);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        const socket = new WebSocket(WS_URL);
        socketRef.current = socket;

        socket.onopen = () => setStatus('open');
        socket.onclose = () => setStatus('closed');
        socket.onmessage = (event) => {
            const message = JSON.parse(event.data) as ServerMessage;
            switch (message.type) {
                case 'lobby_created':
                    setMyLobby(message.lobby);
                    break;
                case 'lobby_list':
                    setLobbies(message.lobbies);
                    break;
                case 'match_started':
                    setMyLobby(null);
                    setGame({ gameId: message.gameId, color: message.color, opponent: message.opponent });
                    break;
                case 'lobby_left':
                    setMyLobby(null);
                    break;
                case 'opponent_disconnected':
                    setGame(null);
                    setError('Opponent disconnected');
                    break;
                case 'error':
                    setError(message.message);
                    break;
            }
        };

        return () => {
            socket.onopen = null;
            socket.onmessage = null;
            socket.onclose = null;
            socket.close();
            socketRef.current = null;
        };
    }, []);

    const send = (message: ClientMessage) => {
        setError(null);
        const socket = socketRef.current;
        if (socket && socket.readyState === WebSocket.OPEN) {
            socket.send(JSON.stringify(message));
        }
    };

    return {
        status,
        lobbies,
        myLobby,
        game,
        error,
        clearError: () => setError(null),
        listLobbies: () => send({ type: 'list_lobbies' }),
        createLobby: (name: string, passcode?: string) => send({ type: 'create_lobby', name, passcode }),
        joinLobby: (lobbyId: string, passcode?: string) => send({ type: 'join_lobby', lobbyId, passcode }),
        leaveLobby: () => send({ type: 'leave_lobby' }),
    };
}

export type GameSocket = ReturnType<typeof useGameSocket>;
