from primo_market.normalize import normalize_bundle


def test_normalize_catalog_and_orders():
    bundle = {
        "execution_id": "run-1",
        "events": [
            {
                "event_type": "catalog_set",
                "product_slug": "soma_prime_set",
                "product_name": "Soma Prime",
                "category": "weapon",
                "response": {
                    "data": {
                        "id": "set-id",
                        "items": [
                            {
                                "id": "item-id",
                                "slug": "soma_prime_set",
                                "setRoot": True,
                                "i18n": {"en": {"name": "Soma Prime Set"}},
                            }
                        ],
                    }
                },
            },
            {
                "event_type": "orders",
                "resource_slug": "soma_prime_set",
                "product_slug": "soma_prime_set",
                "observed_at": "2026-01-01T00:00:00Z",
                "response": {
                    "data": [
                        {
                            "id": "order-1",
                            "itemId": "item-id",
                            "type": "sell",
                            "platinum": 100,
                            "quantity": 1,
                            "visible": True,
                            "user": {"id": "player-1", "ingameName": "Example"},
                        }
                    ]
                },
            },
        ],
    }
    result = normalize_bundle(bundle)
    assert result["dim_product"][0]["product_name"] == "Soma Prime"
    assert result["dim_item"][0]["item_role"] == "set"
    assert result["fact_order_observation"][0]["order_id"] == "order-1"
    assert result["fact_order_observation"][0]["platinum"] == 100
    assert result["dim_player"][0]["player_id"] == "player-1"


def test_empty_orders_still_keep_catalog():
    bundle = {
        "execution_id": "run-2",
        "events": [
            {
                "event_type": "catalog_set",
                "product_slug": "limbo_prime_set",
                "product_name": "limbo Prime",
                "category": "warframe",
                "response": {"data": {"id": "x", "items": [{"id": "i", "slug": "limbo_prime_set"}]}},
            },
            {
                "event_type": "orders",
                "resource_slug": "limbo_prime_set",
                "product_slug": "limbo_prime_set",
                "observed_at": "2026-01-01T00:00:00Z",
                "response": {"data": []},
            },
        ],
    }
    result = normalize_bundle(bundle)
    assert len(result["dim_item"]) == 1
    assert result["fact_order_observation"] == []


def test_warframe_component_roles_are_not_flattened_to_blueprint():
    from primo_market.normalize import _item_role

    assert _item_role("limbo_prime_neuroptics_blueprint", {}) == "neuroptics"
    assert _item_role("limbo_prime_chassis_blueprint", {}) == "chassis"
    assert _item_role("limbo_prime_systems_blueprint", {}) == "systems"
