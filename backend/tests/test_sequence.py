from lib.sequence import SequenceCounter, StaleFilter


def test_counter_starts_at_one_and_increases():
    counter = SequenceCounter()
    assert [counter.next() for _ in range(3)] == [1, 2, 3]


def test_stamp_adds_seq_without_changing_original():
    counter = SequenceCounter()
    message = {"type": "cursor", "x": 10, "y": 20}
    stamped = counter.stamp(message)
    assert stamped == {"type": "cursor", "x": 10, "y": 20, "seq": 1}
    assert "seq" not in message


def test_in_order_messages_are_all_accepted():
    stale = StaleFilter()
    assert all(stale.accept(seq) for seq in [1, 2, 3, 4])
    assert stale.dropped == 0


def test_out_of_order_message_is_dropped():
    stale = StaleFilter()
    results = [stale.accept(seq) for seq in [1, 2, 4, 3, 5]]
    assert results == [True, True, True, False, True]
    assert stale.dropped == 1


def test_duplicate_is_dropped():
    stale = StaleFilter()
    assert stale.accept(7)
    assert not stale.accept(7)


def test_gaps_are_fine():
    # lost packets just get skipped over
    stale = StaleFilter()
    assert stale.accept(1)
    assert stale.accept(10)
    assert stale.last_seen == 10


def test_reset_starts_a_new_stream():
    stale = StaleFilter()
    stale.accept(50)
    stale.reset()
    assert stale.accept(1)
    assert stale.dropped == 0


def test_counter_and_filter_together():
    counter = SequenceCounter()
    stale = StaleFilter()
    sent = [counter.stamp({"x": i}) for i in range(5)]
    # simulate the network swapping the 2nd and 3rd packets
    arrived = [sent[0], sent[2], sent[1], sent[3], sent[4]]
    kept = [m["x"] for m in arrived if stale.accept(m["seq"])]
    assert kept == [0, 2, 3, 4]
