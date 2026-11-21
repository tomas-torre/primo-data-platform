from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    app_env: str
    base_url: str
    user_agent: str
    language: str
    requests_per_second: float
    timeout_seconds: int
    max_retries: int
    selected_products_file: Path
    output_dir: Path
    database_url: str | None

    @classmethod
    def from_env(cls, env_file: str | Path = ".env") -> "Settings":
        load_dotenv(env_file, override=False)
        return cls(
            app_env=os.getenv("APP_ENV", "dev").strip().lower(),
            base_url=os.getenv("WFM_BASE_URL", "https://api.warframe.market").rstrip("/"),
            user_agent=os.getenv(
                "WFM_USER_AGENT",
                "PrimoDataPlatform/0.1.0 (contact: configure-your-contact)",
            ),
            language=os.getenv("WFM_LANGUAGE", "en"),
            requests_per_second=min(2.0, max(0.1, float(os.getenv("WFM_REQUESTS_PER_SECOND", "2")))),
            timeout_seconds=int(os.getenv("WFM_TIMEOUT_SECONDS", "30")),
            max_retries=max(0, int(os.getenv("WFM_MAX_RETRIES", "5"))),
            selected_products_file=Path(
                os.getenv("SELECTED_PRODUCTS_FILE", "config/selected_products.yml")
            ),
            output_dir=Path(os.getenv("OUTPUT_DIR", "data/raw")),
            database_url=os.getenv("DATABASE_URL") or None,
        )


def load_selected_products(path: str | Path) -> list[dict[str, Any]]:
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"Arquivo de produtos não encontrado: {config_path}")
    payload = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    products = payload.get("products", [])
    selected = [p for p in products if p.get("enabled", True)]
    if not selected:
        raise ValueError("Nenhum produto habilitado em selected_products.yml")
    for product in selected:
        for field in ("product_slug", "product_name", "category"):
            if not product.get(field):
                raise ValueError(f"Produto sem campo obrigatório '{field}': {product}")
        product["product_slug"] = str(product["product_slug"]).strip().lower()
        product["category"] = str(product["category"]).strip().lower()
    return selected
