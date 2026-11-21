from __future__ import annotations

from typing import Any


def _name(item: dict[str, Any]) -> str | None:
    i18n = item.get("i18n") or {}
    for lang in ("en", "pt", "ru"):
        value = i18n.get(lang) or {}
        if value.get("name"):
            return value["name"]
    return None


def _item_role(slug: str, item: dict[str, Any]) -> str:
    if item.get("setRoot") is True or slug.endswith("_set"):
        return "set"
    # Os componentes de Warframe terminam em *_blueprint, mas o papel
    # de negócio deve ser Neuroptics/Chassis/Systems, não apenas Blueprint.
    suffixes = (
        ("_neuroptics_blueprint", "neuroptics"),
        ("_chassis_blueprint", "chassis"),
        ("_systems_blueprint", "systems"),
        ("_neuroptics", "neuroptics"),
        ("_chassis", "chassis"),
        ("_systems", "systems"),
        ("_blueprint", "blueprint"),
        ("_barrel", "barrel"),
        ("_receiver", "receiver"),
        ("_stock", "stock"),
    )
    for suffix, role in suffixes:
        if slug.endswith(suffix):
            return role
    return "component"


def normalize_bundle(bundle: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """Normaliza os eventos de API para dimensões e fato de observação.

    platinum é preservado como valor da oferta. Não se deriva preço unitário porque
    quantity/perTrade precisam ser interpretados junto das regras de cada item.
    """
    products: dict[str, dict[str, Any]] = {}
    items: dict[str, dict[str, Any]] = {}
    players: dict[str, dict[str, Any]] = {}
    orders: list[dict[str, Any]] = []

    for event in bundle["events"]:
        if event["event_type"] == "catalog_set":
            data = event["response"].get("data") or {}
            product_slug = event["product_slug"]
            products[product_slug] = {
                "product_slug": product_slug,
                "product_name": event["product_name"],
                "category": event["category"],
                "api_set_id": data.get("id"),
            }
            for item in data.get("items", []):
                slug = item.get("slug")
                if not slug:
                    continue
                items[slug] = {
                    "item_id": item.get("id"),
                    "item_slug": slug,
                    "item_name": _name(item),
                    "product_slug": product_slug,
                    "item_role": _item_role(slug, item),
                    "set_root": bool(item.get("setRoot", False)),
                    "quantity_in_set": item.get("quantityInSet"),
                    "tags": item.get("tags") or [],
                    "rarity": item.get("rarity"),
                    "vaulted": item.get("vaulted"),
                    "tradable": item.get("tradable"),
                    "raw_item": item,
                }

    for event in bundle["events"]:
        if event["event_type"] != "orders":
            continue
        item_slug = event["resource_slug"]
        item = items.get(item_slug, {})
        payload_orders = (event["response"].get("data") or [])
        for order in payload_orders:
            user = order.get("user") or {}
            player_id = user.get("id")
            if player_id:
                players[player_id] = {
                    "player_id": player_id,
                    "ingame_name": user.get("ingameName"),
                    "player_slug": user.get("slug"),
                    "reputation": user.get("reputation"),
                    "platform": user.get("platform"),
                    "crossplay": user.get("crossplay"),
                    "locale": user.get("locale"),
                    "status": user.get("status"),
                    "last_seen": user.get("lastSeen"),
                }
            orders.append(
                {
                    "execution_id": bundle["execution_id"],
                    "observed_at": event["observed_at"],
                    "order_id": order.get("id"),
                    "item_id": order.get("itemId") or item.get("item_id"),
                    "item_slug": item_slug,
                    "product_slug": event["product_slug"],
                    "player_id": player_id,
                    "order_type": (order.get("type") or "").lower(),
                    "platinum": order.get("platinum"),
                    "quantity": order.get("quantity"),
                    "per_trade": order.get("perTrade"),
                    "visible": order.get("visible"),
                    "order_created_at": order.get("createdAt"),
                    "order_updated_at": order.get("updatedAt"),
                    "subtype": order.get("subtype"),
                    "rank": order.get("rank"),
                    "charges": order.get("charges"),
                    "amber_stars": order.get("amberStars"),
                    "cyan_stars": order.get("cyanStars"),
                    "raw_order": order,
                }
            )

    return {
        "dim_product": list(products.values()),
        "dim_item": list(items.values()),
        "dim_player": list(players.values()),
        "fact_order_observation": orders,
    }
