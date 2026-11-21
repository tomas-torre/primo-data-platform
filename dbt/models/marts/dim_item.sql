select distinct on (item_slug)
    item_id,
    item_slug,
    item_name,
    product_slug,
    item_role,
    is_set_root,
    quantity_in_set,
    rarity,
    vaulted
from {{ ref('stg_catalog_items') }}
order by item_slug, catalog_observed_at desc
