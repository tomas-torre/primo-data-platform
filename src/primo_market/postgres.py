from __future__ import annotations

import json
from typing import Any

from sqlalchemy import create_engine, text

DDL_STATEMENTS = [
    "CREATE SCHEMA IF NOT EXISTS bronze",
    """CREATE TABLE IF NOT EXISTS bronze.api_response (
        execution_id UUID NOT NULL, event_type TEXT NOT NULL, resource_slug TEXT NOT NULL,
        product_slug TEXT NOT NULL, product_name TEXT NOT NULL, category TEXT NOT NULL,
        observed_at TIMESTAMPTZ NOT NULL, http_status INTEGER NOT NULL, response JSONB NOT NULL,
        loaded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        PRIMARY KEY (execution_id, event_type, resource_slug))""",
    """CREATE TABLE IF NOT EXISTS bronze.execution_log (
        execution_id UUID PRIMARY KEY, started_at TIMESTAMPTZ NOT NULL,
        finished_at TIMESTAMPTZ NOT NULL, status TEXT NOT NULL,
        response_count INTEGER NOT NULL, item_count INTEGER NOT NULL, total_orders INTEGER NOT NULL)""",
    """CREATE TABLE IF NOT EXISTS bronze.item_execution_log (
        execution_id UUID NOT NULL REFERENCES bronze.execution_log(execution_id),
        item_slug TEXT NOT NULL, status TEXT NOT NULL, order_count INTEGER,
        started_at TIMESTAMPTZ NOT NULL, finished_at TIMESTAMPTZ NOT NULL,
        error_message TEXT, PRIMARY KEY (execution_id, item_slug))""",
]


def load_raw_bundle(database_url: str, bundle: dict[str, Any]) -> None:
    engine = create_engine(database_url, pool_pre_ping=True)
    manifest = {
        "execution_id": bundle["execution_id"],
        "started_at": bundle["started_at"],
        "finished_at": bundle["finished_at"],
        "status": bundle["status"],
        "response_count": len(bundle["events"]),
        "item_count": len(bundle["item_execution"]),
        "total_orders": sum(x["order_count"] or 0 for x in bundle["item_execution"]),
    }
    with engine.begin() as conn:
        for statement in DDL_STATEMENTS:
            conn.execute(text(statement))
        conn.execute(
            text("""INSERT INTO bronze.execution_log
            (execution_id, started_at, finished_at, status, response_count, item_count, total_orders)
            VALUES (:execution_id, :started_at, :finished_at, :status, :response_count, :item_count, :total_orders)
            ON CONFLICT (execution_id) DO NOTHING"""),
            manifest,
        )
        for item in bundle["item_execution"]:
            conn.execute(
                text("""INSERT INTO bronze.item_execution_log
                (execution_id, item_slug, status, order_count, started_at, finished_at, error_message)
                VALUES (:execution_id, :item_slug, :status, :order_count, :started_at, :finished_at, :error_message)
                ON CONFLICT (execution_id, item_slug) DO UPDATE SET
                  status=EXCLUDED.status, order_count=EXCLUDED.order_count,
                  finished_at=EXCLUDED.finished_at, error_message=EXCLUDED.error_message"""),
                {**item, "execution_id": bundle["execution_id"]},
            )
        for event in bundle["events"]:
            conn.execute(
                text("""INSERT INTO bronze.api_response
                (execution_id, event_type, resource_slug, product_slug, product_name,
                 category, observed_at, http_status, response)
                VALUES (:execution_id, :event_type, :resource_slug, :product_slug, :product_name,
                        :category, :observed_at, :http_status, CAST(:response AS JSONB))
                ON CONFLICT (execution_id, event_type, resource_slug) DO NOTHING"""),
                {**event, "response": json.dumps(event["response"], ensure_ascii=False)},
            )
    engine.dispose()
