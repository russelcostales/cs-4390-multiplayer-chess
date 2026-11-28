// Settings and counters for the simulated UDP channel.

export interface NetConfig {
  // Chance that a packet is dropped, 0-50.
  lossPercent: number;
  // Extra delay added to each packet, 0-500 ms.
  delayMs: number;
  deltaCompression: boolean;
  huffmanCoding: boolean;
}

export interface NetStats {
  packetsSent: number;
  packetsReceived: number;
  packetsDropped: number;
  // Packets that arrived after a newer one and were thrown away.
  stalePackets: number;
  // Size before compression.
  bytesRaw: number;
  // Size after compression, as sent.
  bytesSent: number;
  // null when the server doesn't measure latency.
  avgLatencyMs: number | null;
}

export const LOSS_PERCENT_MAX = 50;
export const DELAY_MS_MAX = 500;

export const DEFAULT_NET_CONFIG: NetConfig = {
  lossPercent: 0,
  delayMs: 0,
  deltaCompression: true,
  huffmanCoding: true,
};

export const EMPTY_NET_STATS: NetStats = {
  packetsSent: 0,
  packetsReceived: 0,
  packetsDropped: 0,
  stalePackets: 0,
  bytesRaw: 0,
  bytesSent: 0,
  avgLatencyMs: null,
};
