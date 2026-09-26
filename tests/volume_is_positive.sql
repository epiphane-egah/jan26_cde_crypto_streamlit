select
    order_id,
    volume
from {{ source('staging', 'staging_external') }}
where volume < 0
