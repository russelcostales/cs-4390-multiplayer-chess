import { useEffect, useRef, useState } from 'react';
import type { DrawOfferState, GameOver, Color, GameOverReason } from '../types/gameState';
import type { ClientMessage, LobbySummary, ServerMessage } from '../types/protocol';
import { DEFAULT_NET_CONFIG, EMPTY_NET_STATS, type NetConfig, type NetStats } from '../types/network';
import { CURSOR_IDLE_RESEND_MS, CURSOR_SEND_INTERVAL_MS, START_FEN, WS_URL } from '../constants';
import { StaleFilter } from '../lib/sequence';
import { CursorDeltaDecoder } from '../lib/delta';

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
  const [opponentCursor, setOpponentCursor] = useState<{ x: number; y: number } | null>(null);
  // throttle state lives in a ref so moving the mouse doesn't re-render anything
  const cursorThrottle = useRef<{
    lastSent: number;
    pending: { x: number; y: number } | null;
    timer: number | null;
    idle: number | null;
  }>({ lastSent: 0, pending: null, timer: null, idle: null });
  // one filter per socket, made inside the effect below
  const staleFilterRef = useRef<StaleFilter | null>(null);


  useEffect(() => {
    const socket = new WebSocket(WS_URL);
    socketRef.current = socket;
    const staleFilter = new StaleFilter();
    staleFilterRef.current = staleFilter;
    const deltaDecoder = new CursorDeltaDecoder();

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
          setOpponentCursor(null);
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
          setOpponentCursor(null);
          break;
        case 'opponent_disconnected':
          setDrawOffer('none');
          setDisconnectDialogOpen(true);
          resetBoard();
          setGame(null);
          setOpponentCursor(null);
          break;
        case 'net_stats':
          // server can't see what arrived late, so the stale count comes from our filter
          setNetStats({ ...message.stats, stalePackets: staleFilter.dropped });
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
        case 'cursor': {
          // late packet, a newer position already showed up
          if (!staleFilter.accept(message.seq)) break;
          // null = a delta we can't use yet, the next keyframe fixes it
          const position = deltaDecoder.decode(message);
          if (position) setOpponentCursor(position);
          break;
        }
      }
    };

    return () => {
      socket.onopen = null;
      socket.onmessage = null;
      socket.onclose = null;
      const { timer, idle } = cursorThrottle.current;
      if (timer !== null) window.clearTimeout(timer);
      if (idle !== null) window.clearTimeout(idle);
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
    staleFilterRef.current?.reset();
    setNetStats(EMPTY_NET_STATS);
    if (netSupportedRef.current) send({ type: 'net_reset_stats' });
  };

  // skips send() on purpose, that clears the error and would re-render every packet
  const sendCursorNow = (x: number, y: number) => {
    const socket = socketRef.current;
    if (socket && socket.readyState === WebSocket.OPEN) {
      const message: ClientMessage = { type: 'cursor', x, y };
      socket.send(JSON.stringify(message));
    }
  };

  const sendCursor = (x: number, y: number) => {
    const throttle = cursorThrottle.current;

    // mouse is still moving, push the "stopped" resend back
    if (throttle.idle !== null) window.clearTimeout(throttle.idle);
    throttle.idle = window.setTimeout(() => {
      throttle.idle = null;
      sendCursorNow(x, y);
    }, CURSOR_IDLE_RESEND_MS);

    throttle.pending = { x, y };
    if (throttle.timer !== null) return;
    const wait = Math.max(0, CURSOR_SEND_INTERVAL_MS - (performance.now() - throttle.lastSent));
    // send whatever the latest position is when the timer fires, so the final spot isn't lost
    throttle.timer = window.setTimeout(() => {
      throttle.timer = null;
      throttle.lastSent = performance.now();
      if (throttle.pending) sendCursorNow(throttle.pending.x, throttle.pending.y);
      throttle.pending = null;
    }, wait);
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
    opponentCursor,
    sendCursor,
  };
}

export type GameSocket = ReturnType<typeof useGameSocket>;