# Databricks notebook source
from pyspark.sql import functions as F

catalog = dbutils.widgets.get("catalog")
source_table = f"{catalog}.silver.fact_order_observation"
target_table = f"{catalog}.gold.fact_item_price_snapshot"

orders = spark.table(source_table).where(F.col("order_type").isin("buy", "sell"))
snapshot = (
    orders.groupBy("execution_id", "item_id", "item_slug", "product_slug", "observed_at", "order_type")
    .agg(
        F.count("*").alias("order_count"),
        F.sum("quantity").alias("total_quantity"),
        F.min("platinum").alias("min_order_platinum"),
        F.expr("percentile_approx(platinum, 0.5)").alias("median_order_platinum"),
        F.avg("platinum").alias("avg_order_platinum"),
        F.max("platinum").alias("max_order_platinum"),
    )
)

if not spark.catalog.tableExists(target_table):
    snapshot.write.format("delta").mode("overwrite").saveAsTable(target_table)
else:
    snapshot.createOrReplaceTempView("tmp_price_snapshot")
    spark.sql(f"""
        MERGE INTO {target_table} t
        USING tmp_price_snapshot s
        ON t.execution_id = s.execution_id
           AND t.item_slug = s.item_slug
           AND t.order_type = s.order_type
        WHEN MATCHED THEN UPDATE SET *
        WHEN NOT MATCHED THEN INSERT *
    """)

spark.sql(f"""
CREATE OR REPLACE VIEW {catalog}.gold.vw_market_spread AS
WITH sides AS (
    SELECT execution_id, item_id, item_slug, product_slug, observed_at,
           MIN(CASE WHEN order_type = 'sell' THEN platinum END) AS best_sell_platinum,
           MAX(CASE WHEN order_type = 'buy' THEN platinum END) AS best_buy_platinum,
           SUM(CASE WHEN order_type = 'sell' THEN 1 ELSE 0 END) AS sell_order_count,
           SUM(CASE WHEN order_type = 'buy' THEN 1 ELSE 0 END) AS buy_order_count
    FROM {source_table}
    GROUP BY execution_id, item_id, item_slug, product_slug, observed_at
)
SELECT *, best_sell_platinum - best_buy_platinum AS market_spread_platinum
FROM sides
""")
print(f"Gold atualizada: {target_table}")
