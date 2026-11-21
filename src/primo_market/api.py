from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import quote

import requests

logger = logging.getLogger(__name__)


class WarframeMarketAPIError(RuntimeError):
    pass


class WarframeMarketClient:
    """Cliente público V2 com identificação, rate limit e retry/backoff."""

    def __init__(
        self,
        base_url: str,
        user_agent: str,
        language: str = "en",
        requests_per_second: float = 2,
        timeout_seconds: int = 30,
        max_retries: int = 5,
    ) -> None:
        normalized_agent = (user_agent or "").strip()
        lowered_agent = normalized_agent.lower()
        placeholders = ("configure-your-contact", "seu_email", "seu_usuario", "example.com")
        if not normalized_agent or any(token in lowered_agent for token in placeholders):
            raise ValueError(
                "Configure WFM_USER_AGENT com o nome do projeto e um contato/URL real "
                "antes de consultar a API."
            )
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.min_interval = 1.0 / min(2.0, max(0.1, requests_per_second))
        self._last_request_at = 0.0
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": user_agent,
                "Accept": "application/json",
                "Language": language,
            }
        )

    def _wait_rate_limit(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)

    @staticmethod
    def _retry_after_seconds(value: str | None) -> float | None:
        if not value:
            return None
        try:
            return max(0.0, float(value))
        except ValueError:
            try:
                retry_at = parsedate_to_datetime(value)
                if retry_at.tzinfo is None:
                    retry_at = retry_at.replace(tzinfo=timezone.utc)
                return max(0.0, (retry_at - datetime.now(timezone.utc)).total_seconds())
            except (TypeError, ValueError, OverflowError):
                return None

    def get_json(self, path: str) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        for attempt in range(self.max_retries + 1):
            self._wait_rate_limit()
            try:
                response = self.session.get(url, timeout=self.timeout_seconds)
                self._last_request_at = time.monotonic()
            except requests.RequestException as exc:
                if attempt >= self.max_retries:
                    raise WarframeMarketAPIError(f"Falha de conexão em {url}: {exc}") from exc
                delay = min(60.0, 2**attempt)
                logger.warning("Erro de rede; nova tentativa em %.1fs: %s", delay, exc)
                time.sleep(delay)
                continue

            if response.status_code == 429 or response.status_code >= 500:
                if attempt >= self.max_retries:
                    response.raise_for_status()
                retry_after = self._retry_after_seconds(response.headers.get("Retry-After"))
                delay = retry_after if retry_after is not None else min(60.0, 2**attempt)
                logger.warning("HTTP %s em %s; nova tentativa em %.1fs", response.status_code, url, delay)
                time.sleep(delay)
                continue

            try:
                response.raise_for_status()
                payload = response.json()
            except (requests.HTTPError, ValueError) as exc:
                detail = response.text[:500]
                raise WarframeMarketAPIError(
                    f"Resposta inválida para {url}: HTTP {response.status_code}; {detail}"
                ) from exc

            if not isinstance(payload, dict):
                raise WarframeMarketAPIError(f"Envelope JSON inesperado em {url}")
            if payload.get("error"):
                raise WarframeMarketAPIError(f"Erro da API em {url}: {payload['error']}")
            return payload

        raise WarframeMarketAPIError(f"Não foi possível consultar {url}")

    def get_item_set(self, slug: str) -> dict[str, Any]:
        return self.get_json(f"/v2/item/{quote(slug, safe='')}/set")

    def get_orders(self, slug: str) -> dict[str, Any]:
        return self.get_json(f"/v2/orders/item/{quote(slug, safe='')}")

    def get_all_items(self) -> dict[str, Any]:
        return self.get_json("/v2/items")
