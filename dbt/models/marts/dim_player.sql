select distinct on (player_id)
    player_id,
    player_name as ingame_name,
    player_slug,
    player_reputation as reputation,
    player_platform as platform,
    player_crossplay as crossplay,
    player_locale as locale,
    player_status as status,
    player_last_seen as last_seen
from {{ ref('stg_api_orders') }}
where player_id is not null
order by player_id, observed_at desc
