{{ config(
    materialized='incremental',
    unique_key='id_bougie'
) }}

with staging as (

    select

        timestamp_millis(cast(open_time as int64)) as open_timestamp,

        crypto,

        interval as intervalle,

        cast(`open` as numeric) as open_price,
        cast(`close` as numeric) as close_price,
        cast(high as numeric) as high_price,
        cast(low as numeric) as low_price,
        cast(volume as numeric) as volume

    from {{ source('raw', 'staging_external') }}

    {% if is_incremental() %}

    where timestamp_millis(cast(open_time as int64)) > (
        select max(timestamp(date_ouverture))
        from {{ this }}
    )

    {% endif %}

)

select

    -- ID stable de la bougie
    to_hex(
        md5(
            concat(
                s.crypto,
                '|',
                s.intervalle,
                '|',
                cast(s.open_timestamp as string)
            )
        )
    ) as id_bougie,

    c.id_crypto,

    t.id_temps,

    i.id_intervalle,

    datetime(s.open_timestamp) as date_ouverture,

    s.open_price as valeur_ouverture,
    s.close_price as valeur_fermeture,
    s.high_price as valeur_haute,
    s.low_price as valeur_basse,

    s.volume

from staging s

inner join {{ ref('dim_crypto') }} c
    on c.symbole = s.crypto

inner join {{ ref('dim_temps') }} t
    on t.date_heure = datetime(s.open_timestamp)

inner join {{ ref('dim_intervalle') }} i
    on i.code_intervalle = s.intervalle