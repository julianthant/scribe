from app.pipeline.state import StateStore


def test_message_status_round_trip():
    store = StateStore()
    assert store.get("missing") is None
    store.mark("msg-1", "pending", 1)
    assert store.get("msg-1") == ("pending", 1)
    store.mark("msg-1", "done", 1)
    assert store.get("msg-1") == ("done", 1)
