{{ config(
    materialized='incremental',
    unique_key='id_temps'
) }}

with date_info as (

    select distinct
        timestamp_millis(cast(open_time as int64)) as open_timestamp

    from {{ source('raw', 'staging_external') }}

    {% if is_incremental() %}

    where timestamp_millis(cast(open_time as int64)) > (
        select max(timestamp(date_heure))
        from {{ this }}
    )

    {% endif %}

)

select

    -- Clé stable basée sur le timestamp
    unix_millis(open_timestamp) as id_temps,

    datetime(open_timestamp) as date_heure,

    extract(year from open_timestamp) as annee,
    extract(month from open_timestamp) as mois,
    extract(day from open_timestamp) as jour,
    extract(hour from open_timestamp) as heure,

    format_timestamp('%A', open_timestamp) as jour_semaine,

    extract(quarter from open_timestamp) as trimestre

from date_info