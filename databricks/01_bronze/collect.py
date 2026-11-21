# Databricks notebook source
# Instale dependências no cluster se ainda não estiverem disponíveis.
# MAGIC %pip install requests PyYAML python-dotenv

# COMMAND ----------

import json
import os
import sys
from datetime import datetime, timezone

project_src_path = dbutils.widgets.get("project_src_path")
products_file = dbutils.widgets.get("products_file")
catalog = dbutils.widgets.get("catalog")
sys.path.insert(0, project_src_path)

from primo_market.api import WarframeMarketClient
from primo_market.collector import collect_market
from primo_market.settings import load_selected_products

# O User-Agent deve identificar o projeto e incluir um contato/URL real.
user_agent = os.getenv(
    "WFM_USER_AGENT",
    "PrimoDataPlatform/0.1.0 (+https://github.com/SEU_USUARIO/primo-data-platform)",
)
products = load_selected_products(products_file)
client = WarframeMarketClient(
    base_url=os.getenv("WFM_BASE_URL", "https://api.warframe.market"),
    user_agent=user_agent,
    language=os.getenv("WFM_LANGUAGE", "en"),
    requests_per_second=float(os.getenv("WFM_REQUESTS_PER_SECOND", "2")),
    timeout_seconds=int(os.getenv("WFM_TIMEOUT_SECONDS", "30")),
    max_retries=int(os.getenv("WFM_MAX_RETRIES", "5")),
)
bundle = collect_market(client, products)

# COMMAND ----------

from pyspark.sql import functions as F
from pyspark.sql.types import (
    IntegerType, LongType, StringType, StructField, StructType,
)

for layer in ("bronze", "silver", "gold"):
    spark.sql(f"CREATE SCHEMA IF NOT EXISTS {catalog}.{layer}")

raw_schema = StructType([
    StructField("execution_id", StringType(), False),
    StructField("event_type", StringType(), False),
    StructField("resource_slug", StringType(), False),
    StructField("product_slug", StringType(), False),
    StructField("product_name", StringType(), False),
    StructField("category", StringType(), False),
    StructField("observed_at", StringType(), False),
    StructField("http_status", IntegerType(), False),
    StructField("response_json", StringType(), False),
])
raw_rows = [
    (
        e["execution_id"], e["event_type"], e["resource_slug"], e["product_slug"],
        e["product_name"], e["category"], e["observed_at"], e["http_status"],
        json.dumps(e["response"], ensure_ascii=False),
    )
    for e in bundle["events"]
]
raw_df = spark.createDataFrame(raw_rows, raw_schema)
raw_df.write.format("delta").mode("append").saveAsTable(f"{catalog}.bronze.raw_api_response")

execution_schema = StructType([
    StructField("execution_id", StringType(), False),
    StructField("started_at", StringType(), False),
    StructField("finished_at", StringType(), False),
    StructField("status", StringType(), False),
    StructField("response_count", IntegerType(), False),
    StructField("item_count", IntegerType(), False),
    StructField("total_orders", LongType(), False),
])
execution_row = [(
    bundle["execution_id"], bundle["started_at"], bundle["finished_at"], bundle["status"],
    len(bundle["events"]), len(bundle["item_execution"]),
    sum(x["order_count"] or 0 for x in bundle["item_execution"]),
)]
spark.createDataFrame(execution_row, execution_schema).write.format("delta").mode("append").saveAsTable(
    f"{catalog}.bronze.execution_log"
)

item_exec_schema = StructType([
    StructField("execution_id", StringType(), False),
    StructField("item_slug", StringType(), False),
    StructField("status", StringType(), False),
    StructField("order_count", IntegerType(), True),
    StructField("started_at", StringType(), False),
    StructField("finished_at", StringType(), False),
    StructField("error_message", StringType(), True),
])
item_exec_rows = [tuple(x.get(k) for k in (
    "execution_id", "item_slug", "status", "order_count", "started_at", "finished_at", "error_message"
)) for x in bundle["item_execution"]]
spark.createDataFrame(item_exec_rows, item_exec_schema).write.format("delta").mode("append").saveAsTable(
    f"{catalog}.bronze.item_execution_log"
)

print(f"Bronze concluída: execution_id={bundle['execution_id']} status={bundle['status']}")

# COMMAND ----------

# Databricks task values passam a execução para o próximo notebook.
dbutils.jobs.taskValues.set(key="execution_id", value=bundle["execution_id"])
dbutils.jobs.taskValues.set(key="execution_status", value=bundle["status"])
if bundle["status"] != "success":
    raise RuntimeError(
        f"Coleta parcialmente malsucedida. Bronze foi persistida; verifique "
        f"{catalog}.bronze.item_execution_log para execution_id={bundle['execution_id']}"
    )
