select
    order_id,
    volume
from {{ source('raw', 'staging_external') }}
where volume < 0
