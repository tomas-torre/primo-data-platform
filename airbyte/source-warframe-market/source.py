from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping
from urllib.parse import quote

import requests
from airbyte_cdk.models import SyncMode
from airbyte_cdk.sources import AbstractSource
from airbyte_cdk.sources.streams import Stream


class MarketOrderSnapshotsStream(Stream):
    """Um registro por item consultado; response preserva a lista completa de ofertas.

    Emitir snapshots vazios também é intencional: response=[] diferencia sucesso sem
    ofertas de item que nem chegou a ser consultado.
    """

    name = "market_order_snapshots"
    primary_key = ["execution_id", "item_slug"]
    cursor_field = None

    def __init__(self, items: list[dict[str, Any]], user_agent: str, requests_per_second: float):
        normalized_agent = str(user_agent or "").strip()
        lowered_agent = normalized_agent.lower()
        placeholders = ("configure-your-contact", "seu_email", "seu_usuario", "example.com")
        if not normalized_agent or any(token in lowered_agent for token in placeholders):
            raise ValueError(
                "Configure user_agent com o nome do projeto e um contato/URL real."
            )
        self.items = items
        self.user_agent = normalized_agent
        self.min_interval = 1 / min(2.0, max(0.1, requests_per_second))
        self.last_request = 0.0
        self.execution_id = str(uuid.uuid4())
        self.session = requests.Session()
        self.session.headers.update(
            {"User-Agent": user_agent, "Accept": "application/json", "Language": "en"}
        )

    def get_json_schema(self) -> Mapping[str, Any]:
        return {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object",
            "properties": {
                "execution_id": {"type": "string"},
                "item_slug": {"type": "string"},
                "product_slug": {"type": "string"},
                "product_name": {"type": "string"},
                "category": {"type": "string"},
                "item_name": {"type": ["string", "null"]},
                "item_role": {"type": ["string", "null"]},
                "observed_at": {"type": "string"},
                "http_status": {"type": "integer"},
                "order_count": {"type": "integer"},
                "response": {"type": "array", "items": {"type": "object"}}
            }
        }

    def stream_slices(
        self, *, sync_mode: SyncMode, cursor_field=None, stream_state=None
    ) -> Iterable[Mapping[str, Any]]:
        return self.items

    def read_records(
        self,
        sync_mode: SyncMode,
        cursor_field=None,
        stream_slice: Mapping[str, Any] | None = None,
        stream_state=None,
    ) -> Iterable[Mapping[str, Any]]:
        if not stream_slice:
            return
        elapsed = time.monotonic() - self.last_request
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        item_slug = str(stream_slice["item_slug"])
        url = f"https://api.warframe.market/v2/orders/item/{quote(item_slug, safe='')}"
        response = None
        for attempt in range(5):
            response = self.session.get(url, timeout=30)
            self.last_request = time.monotonic()
            if response.status_code != 429 and response.status_code < 500:
                break
            if attempt == 4:
                response.raise_for_status()
            retry_after = response.headers.get("Retry-After")
            try:
                delay = float(retry_after) if retry_after else 2**attempt
            except ValueError:
                delay = 2**attempt
            time.sleep(min(delay, 60))
        if response is None:
            raise RuntimeError("API não retornou resposta")
        response.raise_for_status()
        body = response.json()
        orders = body.get("data")
        if not isinstance(orders, list):
            raise ValueError(f"Envelope de ofertas inválido para {item_slug}")
        observed_at = datetime.now(timezone.utc).isoformat()
        yield {
            "execution_id": self.execution_id,
            "item_slug": item_slug,
            "product_slug": stream_slice["product_slug"],
            "product_name": stream_slice["product_name"],
            "category": stream_slice["category"],
            "item_name": stream_slice.get("item_name"),
            "item_role": stream_slice.get("item_role"),
            "observed_at": observed_at,
            "http_status": response.status_code,
            "order_count": len(orders),
            "response": orders,
        }


class SourceWarframeMarket(AbstractSource):
    def check_connection(self, logger: logging.Logger, config: Mapping[str, Any]):
        try:
            agent = str(config.get("user_agent", "")).strip()
            if not agent or any(
                marker in agent.lower()
                for marker in ("configure-your-contact", "seu_email", "seu_usuario", "example.com")
            ):
                raise ValueError("Configure user_agent com um contato/URL real do projeto.")
            response = requests.get(
                "https://api.warframe.market/v2/items",
                headers={"User-Agent": agent, "Accept": "application/json"},
                timeout=20,
            )
            response.raise_for_status()
            return True, None
        except Exception as exc:  # noqa: BLE001 - retornado ao Airbyte como erro de conexão
            return False, str(exc)

    def streams(self, config: Mapping[str, Any]):
        return [
            MarketOrderSnapshotsStream(
                items=list(config["items"]),
                user_agent=str(config["user_agent"]),
                requests_per_second=float(config.get("requests_per_second", 2)),
            )
        ]
