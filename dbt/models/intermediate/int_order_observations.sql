select
    o.execution_id,
    o.observed_at,
    o.order_id,
    coalesce(o.item_id, i.item_id) as item_id,
    o.item_slug,
    o.product_slug,
    o.player_id,
    o.order_type,
    o.platinum,
    o.quantity,
    o.per_trade,
    o.visible,
    o.player_name,
    o.player_slug,
    o.player_reputation,
    o.player_platform,
    o.player_crossplay,
    o.player_locale,
    o.player_status,
    o.player_last_seen,
    o.order_created_at,
    o.order_updated_at,
    o.subtype,
    o.item_rank,
    o.raw_order
from {{ ref('stg_api_orders') }} o
left join (
    select distinct item_slug, item_id
    from {{ ref('stg_catalog_items') }}
) i using (item_slug)
