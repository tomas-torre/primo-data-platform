{% if var('ingestion_source', 'python') == 'airbyte' %}
with snapshots as (
    select
        execution_id,
        item_slug,
        product_slug,
        observed_at::timestamptz as observed_at,
        response
    from {{ source('airbyte', 'market_order_snapshots') }}
),
expanded as (
    select
        s.execution_id,
        s.item_slug,
        s.product_slug,
        s.observed_at,
        order_json
    from snapshots s
    cross join lateral jsonb_array_elements(
        case when jsonb_typeof(s.response) = 'array' then s.response else '[]'::jsonb end
    ) as order_json
)
select
    execution_id,
    observed_at,
    item_slug,
    product_slug,
    order_json ->> 'id' as order_id,
    order_json ->> 'itemId' as item_id,
    lower(order_json ->> 'type') as order_type,
    nullif(order_json ->> 'platinum', '')::numeric as platinum,
    nullif(order_json ->> 'quantity', '')::integer as quantity,
    nullif(order_json ->> 'perTrade', '')::integer as per_trade,
    coalesce((order_json ->> 'visible')::boolean, false) as visible,
    order_json -> 'user' ->> 'id' as player_id,
    order_json -> 'user' ->> 'ingameName' as player_name,
    order_json -> 'user' ->> 'slug' as player_slug,
    nullif(order_json -> 'user' ->> 'reputation', '')::integer as player_reputation,
    order_json -> 'user' ->> 'platform' as player_platform,
    nullif(order_json -> 'user' ->> 'crossplay', '')::boolean as player_crossplay,
    order_json -> 'user' ->> 'locale' as player_locale,
    order_json -> 'user' ->> 'status' as player_status,
    nullif(order_json -> 'user' ->> 'lastSeen', '')::timestamptz as player_last_seen,
    nullif(order_json ->> 'createdAt', '')::timestamptz as order_created_at,
    nullif(order_json ->> 'updatedAt', '')::timestamptz as order_updated_at,
    order_json ->> 'subtype' as subtype,
    nullif(order_json ->> 'rank', '')::integer as item_rank,
    order_json as raw_order
from expanded
where coalesce(order_json ->> 'id', '') <> ''
{% else %}
with order_events as (
    select
        execution_id,
        resource_slug as item_slug,
        product_slug,
        observed_at,
        response -> 'data' as orders_json
    from {{ source('bronze', 'api_response') }}
    where event_type = 'orders'
),
expanded as (
    select
        e.execution_id,
        e.item_slug,
        e.product_slug,
        e.observed_at,
        order_json
    from order_events e
    cross join lateral jsonb_array_elements(
        case when jsonb_typeof(e.orders_json) = 'array'
             then e.orders_json else '[]'::jsonb end
    ) as order_json
)
select
    execution_id,
    observed_at,
    item_slug,
    product_slug,
    order_json ->> 'id' as order_id,
    order_json ->> 'itemId' as item_id,
    lower(order_json ->> 'type') as order_type,
    nullif(order_json ->> 'platinum', '')::numeric as platinum,
    nullif(order_json ->> 'quantity', '')::integer as quantity,
    nullif(order_json ->> 'perTrade', '')::integer as per_trade,
    coalesce((order_json ->> 'visible')::boolean, false) as visible,
    (order_json -> 'user' ->> 'id') as player_id,
    order_json -> 'user' ->> 'ingameName' as player_name,
    order_json -> 'user' ->> 'slug' as player_slug,
    nullif(order_json -> 'user' ->> 'reputation', '')::integer as player_reputation,
    order_json -> 'user' ->> 'platform' as player_platform,
    nullif(order_json -> 'user' ->> 'crossplay', '')::boolean as player_crossplay,
    order_json -> 'user' ->> 'locale' as player_locale,
    order_json -> 'user' ->> 'status' as player_status,
    nullif(order_json -> 'user' ->> 'lastSeen', '')::timestamptz as player_last_seen,
    nullif(order_json ->> 'createdAt', '')::timestamptz as order_created_at,
    nullif(order_json ->> 'updatedAt', '')::timestamptz as order_updated_at,
    order_json ->> 'subtype' as subtype,
    nullif(order_json ->> 'rank', '')::integer as item_rank,
    order_json as raw_order
from expanded
where coalesce(order_json ->> 'id', '') <> ''
{% endif %}
