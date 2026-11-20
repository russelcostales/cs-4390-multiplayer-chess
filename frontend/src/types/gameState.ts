// Mirrors backend/lobby.py Color.
export type Color = 'white' | 'black';

// Board terminations match backend/moves.py _TERMINATION. 'opponent_disconnected'
// matches the server's opponent_disconnected message. 'resignation' and
// 'draw_agreement' have no backend equivalent yet.
export type GameOverReason =
  | 'checkmate'
  | 'resignation'
  | 'stalemate'
  | 'insufficient_material'
  | 'seventyfive_moves'
  | 'fivefold_repetition'
  | 'draw_agreement'
  | 'opponent_disconnected';

export interface GameOver {
  // null means the game was drawn.
  winner: Color | null;
  reason: GameOverReason;
}

export type DrawOfferState = 'none' | 'offered_by_me' | 'offered_by_opponent';
