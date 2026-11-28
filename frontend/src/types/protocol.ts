import type { Color } from './gameState';
import type { NetConfig, NetStats } from './network';

export interface LobbySummary {
  id: string;
  name: string;
  locked: boolean;
}

// Mirrors backend/messages.py ErrorCode.
export type ErrorCode =
  | 'INVALID_MESSAGE'
  | 'RATE_LIMITED'
  | 'LOBBY_NOT_FOUND'
  | 'LOBBY_FULL'
  | 'WRONG_PASSCODE'
  | 'ALREADY_IN_LOBBY'
  | 'INVALID_NAME'
  | 'NOT_IN_LOBBY'
  | 'GAME_NOT_FOUND'
  | 'GAME_OVER'
  | 'NOT_IN_GAME'
  | 'NOT_YOUR_TURN'
  | 'ILLEGAL_MOVE'
  | 'PROMOTION_REQUIRED'
  | 'INVALID_FORMAT'
  | 'INVALID_DRAW_OFFER';

export type ClientMessage =
  | { type: 'create_lobby'; name: string; passcode?: string }
  | { type: 'list_lobbies' }
  | { type: 'join_lobby'; lobbyId: string; passcode?: string }
  | { type: 'leave_lobby' }
  | { type: 'move'; move: string }
  | { type: 'offer_draw' }
  | { type: 'respond_draw'; accept: boolean }
  | { type: 'resign'}
  // Simulated UDP channel. The backend doesn't handle these yet, so the client
  // sends them only after it has received a net_stats message.
  | { type: 'net_config'; config: NetConfig }
  | { type: 'net_reset_stats' }

export interface MoveMade {
  type: 'move_made';
  gameId: string;
  uci: string | null;
  san: string | null;
  fen: string | null;
  turn: Color | null;
  isCheck: boolean;
  gameOver: boolean;
  result: string | null;
  winner: Color | null;
  termination: string | null;
}

export interface DrawOffered {
  type: 'draw_offered';
  gameId: string;
}

export interface DrawDeclined {
  type: 'draw_declined';
  gameId: string;
}

export type ServerMessage =
  | { type: 'lobby_created'; lobby: LobbySummary }
  | { type: 'lobby_list'; lobbies: LobbySummary[] }
  | { type: 'match_started'; gameId: string; color: Color; opponent: { id: string; name: string } }
  | { type: 'lobby_left' }
  | { type: 'opponent_disconnected'; gameId: string }
  | MoveMade
  | DrawOffered
  | DrawDeclined
  // Current counters for the simulated UDP channel.
  | { type: 'net_stats'; stats: NetStats }
  | { type: 'error'; code: ErrorCode; message: string };