"""netsim.py - fakes a bad network on the cursor stream: packet loss plus delay with jitter."""

import random
from dataclasses import dataclass
from typing import Protocol


class RandomSource(Protocol):
    def random(self) -> float: ...


@dataclass
class NetConfig:
    """Settings from the frontend's network panel. Same ranges as types/network.ts."""

    loss_percent: float = 0.0
    delay_ms: float = 0.0
    # huffman isn't hooked up yet, that's on its own branch
    delta_compression: bool = True
    huffman_coding: bool = True


@dataclass
class NetStats:
    """Counters for one player's incoming cursor stream."""

    packets_sent: int = 0
    packets_received: int = 0
    packets_dropped: int = 0
    stale_packets: int = 0  # always 0 here, the browser does the stale filtering and fills this in
    bytes_raw: int = 0
    bytes_sent: int = 0
    total_delay_ms: float = 0.0

    def to_message(self) -> dict:
        # key names have to match NetStats in frontend/src/types/network.ts
        avg = self.total_delay_ms / self.packets_received if self.packets_received else None
        return {
            "packetsSent": self.packets_sent,
            "packetsReceived": self.packets_received,
            "packetsDropped": self.packets_dropped,
            "stalePackets": self.stale_packets,
            "bytesRaw": self.bytes_raw,
            "bytesSent": self.bytes_sent,
            "avgLatencyMs": round(avg, 1) if avg is not None else None,
        }


class NetworkSimulator:
    """One per player, for the cursor packets going TO that player.
    Decides if each packet gets lost and how late it shows up."""

    def __init__(self, rng: RandomSource | None = None) -> None:
        self.config = NetConfig()
        self.stats = NetStats()
        self._rng = rng if rng is not None else random.Random()

    def send(self, raw_bytes: int, sent_bytes: int) -> float | None:
        """Returns how many seconds to hold the packet, or None if it got dropped."""
        self.stats.packets_sent += 1
        self.stats.bytes_raw += raw_bytes
        self.stats.bytes_sent += sent_bytes

        # only roll the dice when it's turned on, keeps the tests predictable
        if self.config.loss_percent > 0 and self._rng.random() * 100 < self.config.loss_percent:
            self.stats.packets_dropped += 1
            return None

        delay_ms = 0.0
        if self.config.delay_ms > 0:
            # each packet gets 50-150% of the delay, so two close packets can swap order (jitter)
            delay_ms = self.config.delay_ms * (0.5 + self._rng.random())

        # counted as received now even though it actually lands after the delay
        self.stats.packets_received += 1
        self.stats.total_delay_ms += delay_ms
        return delay_ms / 1000

    def reset_stats(self) -> None:
        self.stats = NetStats()