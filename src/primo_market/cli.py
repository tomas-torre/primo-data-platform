from __future__ import annotations

import argparse
import logging

from primo_market.api import WarframeMarketClient
from primo_market.collector import collect_market
from primo_market.postgres import load_raw_bundle
from primo_market.settings import Settings, load_selected_products
from primo_market.storage import save_execution


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Coleta ofertas do Warframe.market")
    parser.add_argument("command", choices=["collect"], help="Comando de execução")
    parser.add_argument("--env-file", default=".env", help="Arquivo de variáveis de ambiente")
    parser.add_argument("--no-postgres", action="store_true", help="Não carregar no PostgreSQL")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    settings = Settings.from_env(args.env_file)
    products = load_selected_products(settings.selected_products_file)
    client = WarframeMarketClient(
        base_url=settings.base_url,
        user_agent=settings.user_agent,
        language=settings.language,
        requests_per_second=settings.requests_per_second,
        timeout_seconds=settings.timeout_seconds,
        max_retries=settings.max_retries,
    )
    bundle = collect_market(client, products)
    output_path = save_execution(bundle, settings.output_dir)
    logging.info("Arquivos brutos gravados em %s", output_path)

    if not args.no_postgres and settings.database_url:
        load_raw_bundle(settings.database_url, bundle)
        logging.info("Dados brutos carregados no PostgreSQL")
    elif not args.no_postgres:
        logging.info("DATABASE_URL não configurada; carga PostgreSQL ignorada")

    logging.info(
        "Execução %s (%s): %s itens, %s ofertas",
        bundle["execution_id"], bundle["status"], len(bundle["item_execution"]),
        sum(x["order_count"] or 0 for x in bundle["item_execution"]),
    )
    if bundle["status"] != "success":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
