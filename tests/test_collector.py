from primo_market.collector import collect_market


class FakeClient:
    def get_item_set(self, slug):
        return {
            "data": {
                "id": f"set-{slug}",
                "items": [
                    {"id": f"{slug}-id", "slug": slug, "setRoot": True},
                    {"id": f"{slug}-part-id", "slug": f"{slug.removesuffix('_set')}_blueprint"},
                ],
            }
        }

    def get_orders(self, slug):
        return {"data": []}


def test_successful_empty_snapshot_is_not_a_failure():
    bundle = collect_market(
        FakeClient(),
        [{"product_slug": "soma_prime_set", "product_name": "Soma Prime", "category": "weapon"}],
    )
    assert bundle["status"] == "success"
    assert len(bundle["events"]) == 3
    assert all(item["status"] == "success" for item in bundle["item_execution"])
    assert all(item["order_count"] == 0 for item in bundle["item_execution"])


class PartiallyFailingClient(FakeClient):
    def get_item_set(self, slug):
        return {
            "data": {
                "id": "set-id",
                "items": [
                    {"id": "one", "slug": "first_item"},
                    {"id": "two", "slug": "second_item"},
                ],
            }
        }

    def get_orders(self, slug):
        if slug == "first_item":
            raise RuntimeError("temporary API outage")
        return {"data": []}


def test_partial_failure_is_logged_and_other_items_continue():
    bundle = collect_market(
        PartiallyFailingClient(),
        [{"product_slug": "a_set", "product_name": "A", "category": "weapon"}],
    )
    assert bundle["status"] == "partial_failed"
    statuses = {row["item_slug"]: row["status"] for row in bundle["item_execution"]}
    assert statuses == {"first_item": "failed", "second_item": "success"}
    assert any(event["resource_slug"] == "second_item" for event in bundle["events"])


def test_api_client_rejects_placeholder_user_agent():
    import pytest

    from primo_market.api import WarframeMarketClient

    with pytest.raises(ValueError, match="WFM_USER_AGENT"):
        WarframeMarketClient(
            base_url="https://api.warframe.market",
            user_agent="PrimoDataPlatform/0.1.0 (contact: configure-your-contact)",
        )
