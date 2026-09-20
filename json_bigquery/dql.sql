# dim_crypto

INSERT INTO `jan26-cde-crypto.db_crypto.DIM_crypto` (id_crypto, symbole, nom)
VALUES
  (1, 'BTCUSDT', 'Bitcoin'),
  (2, 'ETHUSDT', 'Ethereum'),
  (3, 'BNBUSDT', 'Binance Coin');

# dim_intervalle

INSERT INTO `jan26-cde-crypto.db_crypto.DIM_intervalle` (id_intervalle, code_intervalle, libelle)
VALUES
  (1, '1h', 'une heure'),
  (2, '1d', 'un jour');


# dim_temps

INSERT INTO `jan26-cde-crypto.db_crypto.DIM_temps`
(
    id_temps,
    date_heure,
    annee,
    mois,
    jour,
    heure,
    jour_semaine,
    trimestre
)

WITH date_info AS (
    SELECT DISTINCT
        TIMESTAMP_MILLIS(
            CAST(JSON_VALUE(raw_data, '$.open_time') AS INT64)
        ) AS open_timestamp
    FROM `jan26-cde-crypto.db_crypto.STAGING`
)

SELECT
    ROW_NUMBER() OVER (ORDER BY open_timestamp) AS id_temps,
    DATETIME(open_timestamp) AS date_heure,
    EXTRACT(YEAR FROM open_timestamp) AS annee,
    EXTRACT(MONTH FROM open_timestamp) AS mois,
    EXTRACT(DAY FROM open_timestamp) AS jour,
    EXTRACT(HOUR FROM open_timestamp) AS heure,
    FORMAT_TIMESTAMP('%A', open_timestamp) AS jour_semaine,
    EXTRACT(QUARTER FROM open_timestamp) AS trimestre
FROM date_info;




# fact_cours_ohlcv 

INSERT INTO `jan26-cde-crypto.db_crypto.FACT_COURS_OHLCV`
(
    id_bougie,
    id_crypto,
    id_temps,
    id_intervalle,
    date_ouverture,
    valeur_ouverture,
    valeur_fermeture,
    valeur_haute,
    valeur_basse,
    volume
)

WITH staging AS (

SELECT
    TIMESTAMP_MILLIS(
        CAST(JSON_VALUE(raw_data,'$.open_time') AS INT64)
    ) AS open_timestamp,

    JSON_VALUE(raw_data,'$.crypto') AS crypto,

    JSON_VALUE(raw_data,'$.interval') AS intervalle,

    CAST(JSON_VALUE(raw_data,'$.open') AS NUMERIC) AS open_price,
    CAST(JSON_VALUE(raw_data,'$.close') AS NUMERIC) AS close_price,
    CAST(JSON_VALUE(raw_data,'$.high') AS NUMERIC) AS high_price,
    CAST(JSON_VALUE(raw_data,'$.low') AS NUMERIC) AS low_price,
    CAST(JSON_VALUE(raw_data,'$.volume') AS NUMERIC) AS volume

FROM `jan26-cde-crypto.db_crypto.STAGING`

)

SELECT

    ROW_NUMBER() OVER(ORDER BY open_timestamp, crypto) AS id_bougie,

    c.id_crypto,

    t.id_temps,

    i.id_intervalle,

    DATETIME(open_timestamp),

    open_price,

    close_price,

    high_price,

    low_price,

    volume

FROM staging s

JOIN `jan26-cde-crypto.db_crypto.DIM_crypto` c
ON c.symbole = s.crypto

JOIN `jan26-cde-crypto.db_crypto.DIM_temps` t
ON t.date_heure = DATETIME(s.open_timestamp)

JOIN `jan26-cde-crypto.db_crypto.DIM_intervalle` i
ON i.code_intervalle = s.intervalle;

