{% if var('ingestion_source', 'python') == 'airbyte' %}
with ranked as (
    select
        item_slug,
        product_slug,
        product_name,
        category,
        item_name,
        item_role,
        observed_at,
        row_number() over (partition by item_slug order by observed_at desc) as rn
    from {{ source('airbyte', 'market_order_snapshots') }}
)
select
    cast(null as text) as execution_id,
    product_slug,
    product_name,
    category,
    observed_at::timestamptz as catalog_observed_at,
    cast(null as text) as item_id,
    item_slug,
    item_name,
    coalesce(item_role = 'set', false) as is_set_root,
    cast(null as integer) as quantity_in_set,
    cast(null as text) as rarity,
    cast(null as boolean) as vaulted,
    cast(null as jsonb) as raw_item,
    item_role
from ranked
where rn = 1
{% else %}
with catalog_events as (
    select
        execution_id,
        product_slug,
        product_name,
        category,
        observed_at,
        response -> 'data' -> 'items' as items_json
    from {{ source('bronze', 'api_response') }}
    where event_type = 'catalog_set'
),
expanded as (
    select
        c.execution_id,
        c.product_slug,
        c.product_name,
        c.category,
        c.observed_at,
        item_json
    from catalog_events c
    cross join lateral jsonb_array_elements(
        case when jsonb_typeof(c.items_json) = 'array'
             then c.items_json else '[]'::jsonb end
    ) as item_json
)
select
    execution_id,
    product_slug,
    product_name,
    category,
    observed_at as catalog_observed_at,
    item_json ->> 'id' as item_id,
    item_json ->> 'slug' as item_slug,
    coalesce(item_json -> 'i18n' -> 'en' ->> 'name', item_json -> 'i18n' -> 'pt' ->> 'name') as item_name,
    coalesce((item_json ->> 'setRoot')::boolean, false) as is_set_root,
    nullif(item_json ->> 'quantityInSet', '')::integer as quantity_in_set,
    item_json ->> 'rarity' as rarity,
    coalesce((item_json ->> 'vaulted')::boolean, false) as vaulted,
    item_json as raw_item,
    case
        when coalesce((item_json ->> 'setRoot')::boolean, false) or item_json ->> 'slug' like '%_set' then 'set'
        when item_json ->> 'slug' like '%_neuroptics%' then 'neuroptics'
        when item_json ->> 'slug' like '%_chassis%' then 'chassis'
        when item_json ->> 'slug' like '%_systems%' then 'systems'
        when item_json ->> 'slug' like '%_blueprint' then 'blueprint'
        when item_json ->> 'slug' like '%_barrel' then 'barrel'
        when item_json ->> 'slug' like '%_receiver' then 'receiver'
        when item_json ->> 'slug' like '%_stock' then 'stock'
        else 'component'
    end as item_role
from expanded
where coalesce(item_json ->> 'slug', '') <> ''
{% endif %}
