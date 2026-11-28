export const LIGHT = '#b4b4b4';
export const DARK = '#6d6d6d';
export const MUTED = '#959595';
export const WS_URL = 'ws://localhost:8765';
export const START_FEN = 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1';

// server allows 30 cursor msgs/sec, 20/sec keeps us under with room to spare
export const CURSOR_SEND_INTERVAL_MS = 50;
// after the mouse stops, send the spot once more so the server sends a keyframe
// (fixes the dot if the last delta got lost)
export const CURSOR_IDLE_RESEND_MS = 300;