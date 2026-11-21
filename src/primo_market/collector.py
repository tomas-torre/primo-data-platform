from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from primo_market.api import WarframeMarketClient

logger = logging.getLogger(__name__)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _data(payload: dict[str, Any]) -> Any:
    return payload.get("data")


def collect_market(
    client: WarframeMarketClient,
    products: list[dict[str, Any]],
) -> dict[str, Any]:
    """Coleta catálogo do Set e ofertas Buy/Sell de todos os seus componentes.

    Uma resposta vazia de orders é registrada como sucesso com zero ofertas.
    Falhas são propagadas: não se deve confundir falha de API com mercado vazio.
    """
    execution_id = str(uuid.uuid4())
    started_at = utc_now()
    events: list[dict[str, Any]] = []
    item_catalog: dict[str, dict[str, Any]] = {}
    item_execution: list[dict[str, Any]] = []

    for product in products:
        product_slug = product["product_slug"]
        logger.info("Descobrindo Set e componentes: %s", product_slug)
        catalog_payload = client.get_item_set(product_slug)
        observed_at = utc_now()
        events.append(
            {
                "execution_id": execution_id,
                "event_type": "catalog_set",
                "resource_slug": product_slug,
                "product_slug": product_slug,
                "product_name": product["product_name"],
                "category": product["category"],
                "observed_at": observed_at,
                "http_status": 200,
                "response": catalog_payload,
            }
        )
        catalog_data = _data(catalog_payload) or {}
        items = catalog_data.get("items", []) if isinstance(catalog_data, dict) else []
        if not items:
            raise ValueError(
                f"A API não retornou itens para {product_slug}. "
                "Confira o slug e a resposta atual da API."
            )

        for item in items:
            slug = item.get("slug")
            if not slug:
                logger.warning("Item sem slug ignorado no catálogo: %s", item)
                continue
            item_catalog[slug] = {
                "item": item,
                "product_slug": product_slug,
                "product_name": product["product_name"],
                "category": product["category"],
            }

    for item_slug, metadata in item_catalog.items():
        logger.info("Coletando ofertas: %s", item_slug)
        started_item = utc_now()
        try:
            orders_payload = client.get_orders(item_slug)
            observed_at = utc_now()
            orders = _data(orders_payload)
            if not isinstance(orders, list):
                raise ValueError(f"Envelope de orders não contém lista em data: {item_slug}")
            events.append(
                {
                    "execution_id": execution_id,
                    "event_type": "orders",
                    "resource_slug": item_slug,
                    "product_slug": metadata["product_slug"],
                    "product_name": metadata["product_name"],
                    "category": metadata["category"],
                    "observed_at": observed_at,
                    "http_status": 200,
                    "response": orders_payload,
                }
            )
            item_execution.append(
                {
                    "execution_id": execution_id,
                    "item_slug": item_slug,
                    "status": "success",
                    "order_count": len(orders),
                    "started_at": started_item,
                    "finished_at": observed_at,
                    "error_message": None,
                }
            )
        except Exception as exc:
            logger.exception("Falha na coleta de %s", item_slug)
            item_execution.append(
                {
                    "execution_id": execution_id,
                    "item_slug": item_slug,
                    "status": "failed",
                    "order_count": None,
                    "started_at": started_item,
                    "finished_at": utc_now(),
                    "error_message": str(exc),
                }
            )

    execution_status = (
        "partial_failed" if any(x["status"] == "failed" for x in item_execution) else "success"
    )
    return {
        "execution_id": execution_id,
        "started_at": started_at,
        "finished_at": utc_now(),
        "status": execution_status,
        "events": events,
        "item_execution": item_execution,
        "item_catalog": item_catalog,
    }
