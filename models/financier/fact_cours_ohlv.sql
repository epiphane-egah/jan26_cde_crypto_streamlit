
{{ config(
    materialized='incremental',
    unique_key='id_bougie'
) }}

with staging as (

    select
        -- Conversion du timestamp source (millisecondes) en TIMESTAMP
        timestamp_millis(cast(open_time as int64)) as open_timestamp,

        -- Informations de la bougie
        symbole,
        intervalle,

        -- Conversion des valeurs OHLCV en NUMERIC
        cast(`open` as numeric) as open_price,
        cast(`close` as numeric) as close_price,
        cast(high as numeric) as high_price,
        cast(low as numeric) as low_price,
        cast(volume as numeric) as volume

    from {{ source('staging', 'staging_external') }}

    {% if is_incremental() %}

        -- Lors d'un chargement incrémental, seules les nouvelles
        -- bougies sont récupérées.
        where timestamp_millis(cast(open_time as int64)) > (
            select max(timestamp(date_ouverture))
            from {{ this }}
        )

    {% endif %}

)

select

    -- Identifiant unique et stable de la bougie.
    -- Il est construit à partir du symbole, de l'intervalle
    -- et du timestamp d'ouverture.
    to_hex(
        md5(
            concat(
                s.symbole,
                '|',
                s.intervalle,
                '|',
                cast(s.open_timestamp as string)
            )
        )
    ) as id_bougie,

    -- Clé étrangère vers dim_crypto
    c.id_crypto,

    -- Clé étrangère vers dim_temps
    t.id_temps,

    -- Clé étrangère vers dim_interval
    i.id_intervalle,

    -- Date et heure d'ouverture de la bougie
    datetime(s.open_timestamp) as date_ouverture,

    -- Valeurs OHLC
    s.open_price as valeur_ouverture,
    s.close_price as valeur_fermeture,
    s.high_price as valeur_haute,
    s.low_price as valeur_basse,

    -- Volume échangé
    s.volume

from staging s

-- Récupération de l'identifiant de la cryptomonnaie
inner join {{ ref('dim_crypto') }} c
    on c.symbole = s.symbole

-- Récupération de l'identifiant temporel
inner join {{ ref('dim_temps') }} t
    on t.date_heure = datetime(s.open_timestamp)

-- Récupération de l'identifiant de l'intervalle
inner join {{ ref('dim_interval') }} i
    on i.code_intervalle = s.intervalle
