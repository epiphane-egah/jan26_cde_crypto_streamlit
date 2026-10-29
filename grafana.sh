#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="jan26-cde-crypto"
SA_NAME="grafana-monitoring"
SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

# 1. Activer les APIs nécessaires
gcloud services enable \
  monitoring.googleapis.com \
  cloudresourcemanager.googleapis.com \
  --project="$PROJECT_ID"

# 2. Créer le Service Account s'il n'existe pas
gcloud iam service-accounts describe "$SA_EMAIL" \
  --project="$PROJECT_ID" >/dev/null 2>&1 || \
gcloud iam service-accounts create "$SA_NAME" \
  --project="$PROJECT_ID" \
  --display-name="Grafana monitoring"

# 3. Donner le rôle Monitoring Viewer au Service Account
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/monitoring.viewer"
