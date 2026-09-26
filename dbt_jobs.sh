#!/bin/bash
set -e

# Créer une image Docker
TAG=$(date '+%Y-%m-%d-%H-%M')
docker buildx build --platform linux/amd64 -t dbt_job_img:$TAG .

# Créer un dépôt Artifact Registry sur GCP s'il n'existe pas
gcloud artifacts repositories describe dbt-repo 1>/dev/null 2>&1 --location="europe-west1" || \
    gcloud artifacts repositories create dbt-repo \
    --repository-format=docker \
    --location=europe-west1

# Taguer l'image
docker tag dbt_job_img:$TAG europe-west1-docker.pkg.dev/jan26-cde-crypto/dbt-repo/dbt_jobs_img:$TAG

# Enregistrer l'image dans Artifact Registry de Google
docker push europe-west1-docker.pkg.dev/jan26-cde-crypto/dbt-repo/dbt_jobs_img:$TAG

# Créer un compte de service
gcloud iam service-accounts describe dbt-runtime@jan26-cde-crypto.iam.gserviceaccount.com 1>/dev/null 2>&1 || \
    gcloud iam service-accounts create dbt-runtime \
    --description="Compte de service permettant à dbt d’accéder à BigQuery et d’y créer des objets."

# Donner à mon compte de service les droits d'accès et de création de tables dans BigQuery
# Les accès ont été attribués dans la console, car le client bq permet de donner les droits au niveau des datasets


# Créer un Cloud Run Job ou le mettre à jour s'il existe déjà
if gcloud run jobs describe my-dbt-transformation \
    --region="europe-west1" \
    --project="jan26-cde-crypto" \
    >/dev/null 2>&1
then
    gcloud run jobs update my-dbt-transformation \
        --image="europe-west1-docker.pkg.dev/jan26-cde-crypto/dbt-repo/dbt_jobs_img:$TAG" \
        --region="europe-west1" \
        --service-account="dbt-runtime@jan26-cde-crypto.iam.gserviceaccount.com"
else
     gcloud run jobs create my-dbt-transformation \
        --image="europe-west1-docker.pkg.dev/jan26-cde-crypto/dbt-repo/dbt_jobs_img:$TAG" \
        --region="europe-west1" \
        --service-account="dbt-runtime@jan26-cde-crypto.iam.gserviceaccount.com"
fi

# Créer un envtarc trigger
gcloud services enable eventarc.googleapis.com \
  --project=jan26-cde-crypto

# gcs_service_account=$(gcloud storage service-agent \
#   --project=jan26-cde-crypto)

gcloud projects add-iam-policy-binding jan26-cde-crypto \
    --member="serviceAccount:service-975242104567@gs-project-accounts.iam.gserviceaccount.com" \
    --role="roles/pubsub.publisher"

gcloud envtarc triggers describe my-dbt-trigger 1>/dev/null 2>&1 || \
    gcloud eventarc triggers create my-dbt-trigger \
    --location="eu" \
    --destination-workflow="my-dbt-workflow" \
    --destination-workflow-location="europe-west1" \
    --event-filters="type=google.cloud.storage.object.v1.finalized" \
    --event-filters="bucket=crypto-data-candle" \
    --service-account="975242104567-compute@developer.gserviceaccount.com"
