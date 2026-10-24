#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="jan26-cde-crypto"
SERVICE_ACCOUNT="container-runtime@jan26-cde-crypto.iam.gserviceaccount.com"

gcloud services enable monitoring.googleapis.com \
    logging.googleapis.com \
    cloudtrace.googleapis.com
# Donner le droit au service account de Flask Api (Opentélémetry)
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:$SERVICE_ACCOUNT" \
    --role="roles/monitoring.metricWriter"
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:$SERVICE_ACCOUNT" \
    --role="roles/cloudtrace.agent"

# Créer le canal d’alerte Gmail
NAME="Alertes Trading"
EMAIL="egahepiphane@gmail.com"
CHANNEL_ID=$(gcloud beta monitoring channels list \
  --filter="displayName=\"${NAME}\" AND type=\"email\"" \
  --format="value(name)" \
  --limit=1)
if [ -z "$CHANNEL_ID" ]; then
  CHANNEL_ID=$(gcloud beta monitoring channels create \
    --display-name="$NAME" \
    --type=email \
    --channel-labels=email_address="$EMAIL" \
    --format="value(name)")
  echo "Canal créé : $CHANNEL_ID"
else
  echo "Canal déjà existant : $CHANNEL_ID"
fi


# Création des métriques
create_metric() {
  local name="$1" description="$2" filter="$3"
  if gcloud logging metrics describe "$name" >/dev/null 2>&1; then
    echo "Métrique déjà existante : $name"
  else
    gcloud logging metrics create "$name" \
      --description="$description" \
      --log-filter="$filter"
    echo "Métrique créée : $name"
  fi
}


# création des métriques pour le nettoyage GCS: 
BASE='resource.type="cloud_run_job" AND jsonPayload.job="gcs_monthly_cleaning"'
# 1. Succès du nettoyage GCS (sert à l'alerte d'absence)
create_metric gcs_cleaning_job_success \
  "Nettoyages GCS mensuels réussis" \
  "${BASE} AND jsonPayload.event=\"gcs_cleaning_job_success\""
# 2. Échec du nettoyage GCS (sert à l'alerte d'échec)
create_metric gcs_cleaning_job_failed \
  "Nettoyages GCS mensuels en échec" \
  "${BASE} AND jsonPayload.event=\"gcs_cleaning_job_failed\""



# création des métriques pour les tradings jobs journaliers
BASE='resource.type="cloud_run_job" AND jsonPayload.job="daily_trading"'
# 1. Succès du job de trading quotidien (sert à l'alerte d'absence)
create_metric daily_trade_job_success \
  "Runs de trading quotidiens réussis" \
  "${BASE} AND jsonPayload.event=\"daily_trade_job_success\""
# 2. Échec du job de trading quotidien (sert à l'alerte d'échec)
create_metric daily_trade_job_failed \
  "Runs de trading quotidiens en échec" \
  "${BASE} AND jsonPayload.event=\"daily_trade_job_failed\""



# création des métriques pour les tradings jobs horaires
BASE='resource.type="cloud_run_job" AND jsonPayload.job="hourly_trading"'
# 1. Succès du job de trading (sert à l'alerte d'absence)
create_metric hourly_trade_job_success \
  "Runs de trading horaires réussis" \
  "${BASE} AND jsonPayload.event=\"hourly_trade_job_success\""
# 2. Échec du job de trading (sert à l'alerte d'échec)
create_metric hourly_trade_job_failed \
  "Runs de trading horaires en échec" \
  "${BASE} AND jsonPayload.event=\"hourly_trade_job_failed\""



# création des métriques pour dbt jobs
BASE='resource.type="cloud_run_job" AND jsonPayload.job="dbt"'
# 1. Succès du job dbt (sert à l'alerte d'absence)
create_metric dbt_job_success \
  "Runs dbt réussis" \
  "${BASE} AND jsonPayload.event=\"dbt_job_success\""
# 2. Échec du job dbt (sert à l'alerte d'échec)
create_metric dbt_job_failed \
  "Runs dbt en échec" \
  "${BASE} AND jsonPayload.event=\"dbt_job_failed\""
# 3. Tests dbt échoués
create_metric dbt_tests_failed \
  "Runs dbt avec au moins un test en échec" \
  "${BASE} AND jsonPayload.event=\"dbt_run_summary\" AND jsonPayload.failed>0"
# 4. Modèles en erreur
create_metric dbt_models_error \
  "Runs dbt avec au moins un modèle en erreur" \
  "${BASE} AND jsonPayload.event=\"dbt_run_summary\" AND jsonPayload.error>0"
# 5. Résumé manquant (run_results.json introuvable)
create_metric dbt_summary_missing \
  "Résumé dbt introuvable" \
  "${BASE} AND jsonPayload.event=\"dbt_run_summary_missing\""



# création des métriques pour le cloud function de récupération de données
BASE='jsonPayload.job="weekly_extract"'
create_metric weekly_extract_success \
  "Extractions Binance hebdomadaires réussies" \
  "${BASE} AND jsonPayload.event=\"weekly_extract_success\""
create_metric weekly_extract_failed \
  "Extractions Binance en échec (exception)" \
  "${BASE} AND jsonPayload.event=\"weekly_extract_failed\""
create_metric weekly_extract_no_data \
  "Extractions sans aucune donnée collectée" \
  "${BASE} AND jsonPayload.event=\"weekly_extract_no_data\""
create_metric binance_fetch_failed \
  "Appels Binance en erreur (une entrée par paire)" \
  "${BASE} AND jsonPayload.event=\"binance_fetch_failed\""
create_metric binance_data_empty \
  "Paires Binance sans nouvelles données" \
  "${BASE} AND jsonPayload.event=\"binance_data_empty\""
