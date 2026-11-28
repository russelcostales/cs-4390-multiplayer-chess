// sequence.ts - receiver side of the cursor sequence numbers, same logic as backend/lib/sequence.py

// Keeps the newest seq seen and throws out anything older, so a late packet
// can't move the opponent's cursor backwards.
export class StaleFilter {
  lastSeen = 0;
  dropped = 0;

  accept(seq: number): boolean {
    if (seq <= this.lastSeen) {
      this.dropped += 1;
      return false;
    }
    this.lastSeen = seq;
    return true;
  }

  reset(): void {
    this.lastSeen = 0;
    this.dropped = 0;
  }
}
