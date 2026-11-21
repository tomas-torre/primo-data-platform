# Databricks notebook source
# MAGIC %pip install PyYAML

# COMMAND ----------

import json
import sys
from pyspark.sql.types import (
    ArrayType, BooleanType, IntegerType, LongType, StringType, StructField, StructType,
)

project_src_path = dbutils.widgets.get("project_src_path")
catalog = dbutils.widgets.get("catalog")
sys.path.insert(0, project_src_path)
from primo_market.normalize import normalize_bundle

execution_id = dbutils.jobs.taskValues.get(
    taskKey="collect_source", key="execution_id", default=None
)
if not execution_id:
    execution_id = (
        spark.table(f"{catalog}.bronze.execution_log")
        .orderBy("started_at", ascending=False).select("execution_id").first()[0]
    )

raw_events = (
    spark.table(f"{catalog}.bronze.raw_api_response")
    .where(f"execution_id = '{execution_id}'")
    .orderBy("observed_at")
    .collect()
)
events = [
    {
        "execution_id": r.execution_id,
        "event_type": r.event_type,
        "resource_slug": r.resource_slug,
        "product_slug": r.product_slug,
        "product_name": r.product_name,
        "category": r.category,
        "observed_at": r.observed_at,
        "response": json.loads(r.response_json),
    }
    for r in raw_events
]
normalized = normalize_bundle({"execution_id": execution_id, "events": events})

# COMMAND ----------

# Explicit schemas evitam inferência incorreta quando atributos opcionais são todos nulos.
product_schema = StructType([
    StructField("product_slug", StringType()), StructField("product_name", StringType()),
    StructField("category", StringType()), StructField("api_set_id", StringType()),
])
item_schema = StructType([
    StructField("item_id", StringType()), StructField("item_slug", StringType()),
    StructField("item_name", StringType()), StructField("product_slug", StringType()),
    StructField("item_role", StringType()), StructField("set_root", BooleanType()),
    StructField("quantity_in_set", IntegerType()), StructField("tags", ArrayType(StringType())),
    StructField("rarity", StringType()), StructField("vaulted", BooleanType()),
    StructField("tradable", BooleanType()),
])
player_schema = StructType([
    StructField("player_id", StringType()), StructField("ingame_name", StringType()),
    StructField("player_slug", StringType()), StructField("reputation", IntegerType()),
    StructField("platform", StringType()), StructField("crossplay", BooleanType()),
    StructField("locale", StringType()), StructField("status", StringType()),
    StructField("last_seen", StringType()),
])
order_schema = StructType([
    StructField("execution_id", StringType()), StructField("observed_at", StringType()),
    StructField("order_id", StringType()), StructField("item_id", StringType()),
    StructField("item_slug", StringType()), StructField("product_slug", StringType()),
    StructField("player_id", StringType()), StructField("order_type", StringType()),
    StructField("platinum", LongType()), StructField("quantity", IntegerType()),
    StructField("per_trade", IntegerType()), StructField("visible", BooleanType()),
    StructField("order_created_at", StringType()), StructField("order_updated_at", StringType()),
    StructField("subtype", StringType()), StructField("rank", IntegerType()),
    StructField("charges", IntegerType()), StructField("amber_stars", IntegerType()),
    StructField("cyan_stars", IntegerType()),
])


def merge_delta(rows, schema, table_name, keys):
    if not rows:
        print(f"Sem registros para {table_name}; tabela não será alterada.")
        return
    clean_rows = [{k: v for k, v in row.items() if k != "raw_item" and k != "raw_order"} for row in rows]
    df = spark.createDataFrame(clean_rows, schema=schema)
    view_name = f"tmp_{table_name.split('.')[-1]}"
    df.createOrReplaceTempView(view_name)
    if not spark.catalog.tableExists(table_name):
        df.write.format("delta").mode("overwrite").saveAsTable(table_name)
    else:
        condition = " AND ".join([f"t.`{k}` = s.`{k}`" for k in keys])
        spark.sql(f"""
            MERGE INTO {table_name} t USING {view_name} s ON {condition}
            WHEN MATCHED THEN UPDATE SET *
            WHEN NOT MATCHED THEN INSERT *
        """)
    spark.catalog.dropTempView(view_name)

merge_delta(normalized["dim_product"], product_schema, f"{catalog}.silver.dim_product", ["product_slug"])
merge_delta(normalized["dim_item"], item_schema, f"{catalog}.silver.dim_item", ["item_slug"])
merge_delta(normalized["dim_player"], player_schema, f"{catalog}.silver.dim_player", ["player_id"])
merge_delta(
    normalized["fact_order_observation"], order_schema,
    f"{catalog}.silver.fact_order_observation", ["execution_id", "order_id", "item_slug"],
)
print(f"Silver normalizada para execution_id={execution_id}")
