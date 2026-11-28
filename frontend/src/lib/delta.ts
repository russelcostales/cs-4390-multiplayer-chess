// delta.ts - receiver side of the cursor deltas, matches CursorDeltaEncoder in backend/lib/delta.py
import type { CursorPacket } from '../types/protocol';

export const CURSOR_SCALE = 1000;

// rebuilds the opponent's position from keyframes and deltas. A delta only works on top
// of the packet right before it, so after a gap we ignore deltas until the next keyframe.
export class CursorDeltaDecoder {
  // last position in 0-1000 units, null = waiting for a keyframe
  private last: { x: number; y: number } | null = null;
  private lastSeq = 0;

  decode(packet: CursorPacket): { x: number; y: number } | null {
    if ('x' in packet) {
      // delta is turned off, this is already a plain 0-1 position
      this.last = null;
      return { x: packet.x, y: packet.y };
    }

    if ('kx' in packet) {
      this.last = { x: packet.kx, y: packet.ky };
    } else {
      if (this.last === null || packet.seq !== this.lastSeq + 1) {
        // missed the packet this delta was based on
        this.last = null;
        return null;
      }
      this.last = { x: this.last.x + packet.dx, y: this.last.y + packet.dy };
    }

    this.lastSeq = packet.seq;
    return { x: this.last.x / CURSOR_SCALE, y: this.last.y / CURSOR_SCALE };
  }
}