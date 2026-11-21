select distinct on (product_slug)
    product_slug,
    product_name,
    category
from {{ ref('stg_catalog_items') }}
order by product_slug, catalog_observed_at desc
