import type { Color } from './gameState';

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
  | 'INVALID_FORMAT';

export type ClientMessage =
  | { type: 'create_lobby'; name: string; passcode?: string }
  | { type: 'list_lobbies' }
  | { type: 'join_lobby'; lobbyId: string; passcode?: string }
  | { type: 'leave_lobby' }
  | { type: 'move'; move: string };

export interface MoveMade {
  type: 'move_made';
  gameId: string;
  uci: string;
  san: string;
  fen: string;
  turn: Color;
  isCheck: boolean;
  gameOver: boolean;
  result: string | null;
  winner: Color | null;
  termination: string | null;
}

export type ServerMessage =
  | { type: 'lobby_created'; lobby: LobbySummary }
  | { type: 'lobby_list'; lobbies: LobbySummary[] }
  | { type: 'match_started'; gameId: string; color: Color; opponent: { id: string; name: string } }
  | { type: 'lobby_left' }
  | { type: 'opponent_disconnected'; gameId: string }
  | MoveMade
  | { type: 'error'; code: ErrorCode; message: string };