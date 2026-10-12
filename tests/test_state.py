from app.pipeline.state import StateStore


def test_message_status_and_subscription_round_trip(tmp_path):
    store = StateStore(tmp_path / "scribe.db")
    assert store.get("missing") is None
    store.mark("msg-1", "pending", 1)
    assert store.get("msg-1") == ("pending", 1)
    store.mark("msg-1", "done", 1)
    assert store.get("msg-1") == ("done", 1)
    assert store.subscription_id() is None
    store.save_subscription("sub-1", "2026-10-18T00:00:00Z")
    assert store.subscription_id() == "sub-1"
