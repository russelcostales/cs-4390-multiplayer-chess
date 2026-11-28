import pytest

from lib.netsim import NetConfig, NetworkSimulator


class FixedRng:
    def __init__(self, value: float) -> None:
        self.value = value

    def random(self) -> float:
        return self.value


def test_defaults_send_everything_right_away():
    sim = NetworkSimulator(FixedRng(0.0))
    assert sim.send(10, 10) == 0
    assert sim.stats.packets_received == 1


def test_packet_dropped_when_roll_is_under_loss():
    sim = NetworkSimulator(FixedRng(0.1))  # rolls 10
    sim.config = NetConfig(loss_percent=20)
    assert sim.send(10, 10) is None
    assert sim.stats.packets_dropped == 1
    assert sim.stats.packets_received == 0


def test_packet_kept_when_roll_is_over_loss():
    sim = NetworkSimulator(FixedRng(0.5))  # rolls 50
    sim.config = NetConfig(loss_percent=20)
    assert sim.send(10, 10) is not None


def test_delay_is_between_half_and_one_and_a_half():
    low = NetworkSimulator(FixedRng(0.0))
    low.config = NetConfig(delay_ms=200)
    high = NetworkSimulator(FixedRng(0.99))
    high.config = NetConfig(delay_ms=200)
    assert low.send(10, 10) == pytest.approx(0.1)
    assert high.send(10, 10) == pytest.approx(0.298)


def test_stats_message_and_reset():
    sim = NetworkSimulator(FixedRng(0.5))
    sim.config = NetConfig(delay_ms=100)
    sim.send(30, 30)
    sim.send(30, 30)
    assert sim.stats.to_message() == {
        "packetsSent": 2,
        "packetsReceived": 2,
        "packetsDropped": 0,
        "stalePackets": 0,
        "bytesRaw": 60,
        "bytesSent": 60,
        "avgLatencyMs": 100.0,
    }
    sim.reset_stats()
    assert sim.stats.to_message()["packetsSent"] == 0