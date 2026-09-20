CREATE SCHEMA IF NOT EXISTS `jan26-cde-crypto.db_crypto`
OPTIONS(
  location = 'EU'
);

CREATE TABLE IF NOT EXISTS `jan26-cde-crypto.db_crypto.DIM_crypto` (
  id_crypto INT64 NOT NULL,
  symbole STRING,
  nom STRING,
  PRIMARY KEY (id_crypto) NOT ENFORCED
);

CREATE TABLE IF NOT EXISTS `jan26-cde-crypto.db_crypto.DIM_intervalle` (
  id_intervalle INT64 NOT NULL,
  code_intervalle STRING,
  libelle STRING,
  PRIMARY KEY (id_intervalle) NOT ENFORCED
);

CREATE TABLE IF NOT EXISTS `jan26-cde-crypto.db_crypto.DIM_temps` (
  id_temps INT64 NOT NULL,
  date_heure DATETIME,
  annee INT64,
  mois INT64,
  jour INT64,
  heure INT64,
  jour_semaine STRING,
  trimestre INT64,
  PRIMARY KEY (id_temps) NOT ENFORCED
);

CREATE TABLE IF NOT EXISTS `jan26-cde-crypto.db_crypto.FACT_COURS_OHLCV` (
  id_bougie INT64 NOT NULL,
  id_crypto INT64 NOT NULL,
  id_temps INT64 NOT NULL,
  id_intervalle INT64 NOT NULL,

  date_ouverture DATETIME,
  valeur_ouverture NUMERIC,
  valeur_fermeture NUMERIC,
  valeur_haute NUMERIC,
  valeur_basse NUMERIC,
  volume NUMERIC,

  PRIMARY KEY (id_bougie) NOT ENFORCED,
  FOREIGN KEY (id_crypto) REFERENCES `jan26-cde-crypto.db_crypto.DIM_crypto`(id_crypto) NOT ENFORCED,
  FOREIGN KEY (id_temps) REFERENCES `jan26-cde-crypto.db_crypto.DIM_temps`(id_temps) NOT ENFORCED,
  FOREIGN KEY (id_intervalle) REFERENCES `jan26-cde-crypto.db_crypto.DIM_intervalle`(id_intervalle) NOT ENFORCED
);

CREATE TABLE IF NOT EXISTS `jan26-cde-crypto.db_crypto.STAGING` (
  raw_data JSON NOT NULL
)
