from tests.helpers import settings_for

from app.graph.client import GraphNotFound
from app.pipeline.state import StateStore
from app.pipeline.subscription import ensure_subscription


class _Graph:
    def __init__(self) -> None:
        self.created = 0

    async def renew_subscription(self, subscription_id: str, lifetime_days: int) -> dict:
        raise GraphNotFound(404, "subscription_not_found")

    async def create_subscription(self, url: str, state: str, days: int) -> dict:
        self.created += 1
        return {"id": "new-sub", "expirationDateTime": "2026-10-18T00:00:00Z"}


async def test_missing_subscription_is_recreated(tmp_path):
    store = StateStore(tmp_path / "scribe.db")
    store.save_subscription("gone", "2020-01-01T00:00:00Z")
    graph = _Graph()
    await ensure_subscription(graph, store, settings_for(tmp_path))
    assert graph.created == 1
    assert store.subscription_id() == "new-sub"
