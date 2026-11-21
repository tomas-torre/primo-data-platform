{{ config(materialized='view') }}

with sides as (
    select
        execution_id,
        item_id,
        item_slug,
        product_slug,
        observed_at,
        min(platinum) filter (where order_type = 'sell') as best_sell_platinum,
        max(platinum) filter (where order_type = 'buy') as best_buy_platinum,
        count(*) filter (where order_type = 'sell') as sell_order_count,
        count(*) filter (where order_type = 'buy') as buy_order_count
    from {{ ref('int_order_observations') }}
    where order_type in ('buy', 'sell')
    group by 1,2,3,4,5
)
select
    *,
    best_sell_platinum - best_buy_platinum as market_spread_platinum
from sides
