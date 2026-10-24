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