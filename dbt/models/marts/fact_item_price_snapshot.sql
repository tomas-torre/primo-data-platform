select
    execution_id,
    item_id,
    item_slug,
    product_slug,
    observed_at,
    order_type,
    count(*) as order_count,
    sum(coalesce(quantity, 0)) as total_quantity,
    min(platinum) as min_order_platinum,
    percentile_cont(0.5) within group (order by platinum) as median_order_platinum,
    avg(platinum) as avg_order_platinum,
    max(platinum) as max_order_platinum
from {{ ref('int_order_observations') }}
where order_type in ('buy', 'sell')
group by 1,2,3,4,5,6
