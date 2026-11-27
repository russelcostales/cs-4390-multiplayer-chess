import { useEffect, useRef, useState } from 'react';
import { START_FEN, WS_URL } from '../constants';
import type { DrawOfferState, GameOver, Color, GameOverReason } from '../types/gameState';
import type { ClientMessage, LobbySummary, ServerMessage } from '../types/protocol';
import { DEFAULT_NET_CONFIG, EMPTY_NET_STATS, type NetConfig, type NetStats } from '../types/network';

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
  const [fen, setFen] = useState(START_FEN);
  const [moves, setMoves] = useState<string[]>([]);
  const [turn, setTurn] = useState<Color>('white');
  const [disconnectDialogOpen, setDisconnectDialogOpen] = useState(false);
  const [drawOffer, setDrawOffer] = useState<DrawOfferState>('none');
  const [gameOver, setGameOver] = useState<GameOver | null>(null);
  const [gameOverDialogOpen, setGameOverDialogOpen] = useState(false);
  const [netConfig, setNetConfig] = useState<NetConfig>(DEFAULT_NET_CONFIG);
  const [netStats, setNetStats] = useState<NetStats>(EMPTY_NET_STATS);
  // True once the server has sent net_stats. Before that, it would reject
  // net_config and net_reset_stats as unknown message types.
  const [netSupported, setNetSupported] = useState(false);
  // Read by the socket handlers, which are created once.
  const netConfigRef = useRef(netConfig);
  const netSupportedRef = useRef(false);


  useEffect(() => {
    const socket = new WebSocket(WS_URL);
    socketRef.current = socket;

    const resetBoard = () => {
      setFen(START_FEN);
      setMoves([]);
      setTurn('white');
    };

    socket.onopen = () => setStatus('open');
    socket.onclose = () => {
      setStatus('closed');
      netSupportedRef.current = false;
      setNetSupported(false);
    };
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
          setGameOver(null);
          setGameOverDialogOpen(false);
          setDrawOffer('none');
          resetBoard();
          setMyLobby(null);
          setGame({ gameId: message.gameId, color: message.color, opponent: message.opponent });
          break;
        case 'move_made':
          if (message.fen) setFen(message.fen);
          if (message.turn) setTurn(message.turn);
          if (message.san) {
            setMoves((previous) => [...previous, message.san as string]);
          }

          if (message.gameOver) {
            setGameOver({
              winner: message.winner,
              reason: message.termination as GameOverReason,
            });
            setGameOverDialogOpen(true);
            setDrawOffer('none');
          }
          break;
        case 'draw_offered':
          setDrawOffer('offered_by_opponent');
          break;
        case 'draw_declined':
          setDrawOffer('none');
          break;  
        case 'lobby_left':
          setMyLobby(null);
          setGame(null);
          setGameOver(null);
          setGameOverDialogOpen(false);
          setDrawOffer('none');
          setFen(START_FEN);
          setMoves([]);
          setTurn('white');
          break;
        case 'opponent_disconnected':
          setDrawOffer('none');
          setDisconnectDialogOpen(true);
          resetBoard();
          setGame(null);
          break;
        case 'net_stats':
          setNetStats(message.stats);
          if (!netSupportedRef.current) {
            netSupportedRef.current = true;
            setNetSupported(true);
            // Apply settings chosen before the server started sending stats.
            const configMessage: ClientMessage = { type: 'net_config', config: netConfigRef.current };
            socket.send(JSON.stringify(configMessage));
          }
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

  const offerDraw = () => {
    if (gameOver) return;
    setDrawOffer('offered_by_me');
    send({ type: 'offer_draw' });
  };

  const acceptDraw = () => {
    send({ type: 'respond_draw', accept: true });
  };

  const declineDraw = () => {
    setDrawOffer('none');
    send({ type: 'respond_draw', accept: false });
  };

  const closeGameOver = () => {
    setGameOverDialogOpen(false);
  };
  
  const backToLobby = () => {
    send({ type: 'leave_lobby' });
  };

  const resign = () => {
    send({ type: 'resign' });
  };

  const updateNetConfig = (changes: Partial<NetConfig>) => {
    const next = { ...netConfigRef.current, ...changes };
    netConfigRef.current = next;
    setNetConfig(next);
    if (netSupportedRef.current) send({ type: 'net_config', config: next });
  };

  const resetNetStats = () => {
    setNetStats(EMPTY_NET_STATS);
    if (netSupportedRef.current) send({ type: 'net_reset_stats' });
  };

  return {
    status,
    lobbies,
    myLobby,
    game,
    error,
    fen,
    moves,
    turn,
    disconnectDialogOpen,
    closeDisconnectDialog: () => setDisconnectDialogOpen(false),
    clearError: () => setError(null),
    listLobbies: () => send({ type: 'list_lobbies' }),
    createLobby: (name: string, passcode?: string) => send({ type: 'create_lobby', name, passcode }),
    joinLobby: (lobbyId: string, passcode?: string) => send({ type: 'join_lobby', lobbyId, passcode }),
    leaveLobby: () => send({ type: 'leave_lobby' }),
    makeMove: (uci: string) => send({ type: 'move', move: uci }),
    drawOffer,
    gameOver,
    gameOverDialogOpen,
    offerDraw,
    acceptDraw,
    declineDraw,
    closeGameOver,
    backToLobby,
    resign,
    netConfig,
    netStats,
    netSupported,
    updateNetConfig,
    resetNetStats,
  };
}

export type GameSocket = ReturnType<typeof useGameSocket>;