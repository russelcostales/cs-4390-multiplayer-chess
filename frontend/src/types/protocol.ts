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
  | { type: 'cursor'; x: number; y: number }
  // simulated udp settings. client only sends these after the first net_stats shows up
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

// cursor packets from the server. which fields show up depends on the delta toggle:
// x/y = plain 0-1 position (delta off), kx/ky = keyframe, dx/dy = change since the last packet.
// kx/ky/dx/dy are in 0-1000 units
export type CursorPacket = { type: 'cursor'; seq: number } & (
  | { x: number; y: number }
  | { kx: number; ky: number }
  | { dx: number; dy: number }
);

export type ServerMessage =
  | { type: 'lobby_created'; lobby: LobbySummary }
  | { type: 'lobby_list'; lobbies: LobbySummary[] }
  | { type: 'match_started'; gameId: string; color: Color; opponent: { id: string; name: string } }
  | { type: 'lobby_left' }
  | { type: 'opponent_disconnected'; gameId: string }
  | MoveMade
  | DrawOffered
  | DrawDeclined
  | CursorPacket
  // Current counters for the simulated UDP channel.
  | { type: 'net_stats'; stats: NetStats }
  | { type: 'error'; code: ErrorCode; message: string };