#!/bin/bash
set -euo pipefail

# configuration projet
gcloud config set project jan26-cde-crypto
REGION="europe-west1"
PROJECT_ID="$(gcloud config get-value project)"
PROJECT_NUMBER="$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')"
SERVICE_ACCOUNT="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

# autoriser tous les services dont j'ai besoin
gcloud services enable \
    run.googleapis.com \
    artifactregistry.googleapis.com \
    cloudbuild.googleapis.com \
    cloudscheduler.googleapis.com

# donner le droit au service account qui permet au shceduler de déclancher les run jobs
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:$SERVICE_ACCOUNT" \
    --role="roles/run.invoker"

# création d'un runtime service account pour mes run jobs afin d'accèder au secret et à cloud storage
gcloud iam service-accounts describe container-runtime@jan26-cde-crypto.iam.gserviceaccount.com >/dev/null 2>&1 || \
    gcloud iam service-accounts create container-runtime \
    --display-name="Mon compte de service pour permettre au run jobs"

gcloud secrets add-iam-policy-binding clients-database-url-pooler \
    --member='serviceAccount:container-runtime@jan26-cde-crypto.iam.gserviceaccount.com' \
    --role='roles/secretmanager.secretAccessor'

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:container-runtime@jan26-cde-crypto.iam.gserviceaccount.com" \
  --role="roles/storage.admin"

# Pour déployer un cloud run job j'ai besoin d'avoir les droits suivants :
# Mais je suis connecter avec ADF comme admin, donc c'est bon
# Mais si quelqu'un utilise un compte de service, il doit avoir la clef json
# ou dans le cas de workload pouvoir impressioner le service account pour

# roles/run.admin
# roles/run.sourceDeveloper
# roles/iam.serviceAccountUser) sur l'identité du service
# roles/logging.viewer

TAG=$(date +%Y-%m-%d_%Hh%M)
docker buildx build --platform linux/amd64 -f cronjob.yml -t trading-bot-cronjob:$TAG .
docker tag trading-bot-cronjob:$TAG europe-west1-docker.pkg.dev/jan26-cde-crypto/jan26-cde-crypto/trading-bot-cronjob:$TAG
docker push europe-west1-docker.pkg.dev/jan26-cde-crypto/jan26-cde-crypto/trading-bot-cronjob:$TAG
IMAGE="europe-west1-docker.pkg.dev/jan26-cde-crypto/jan26-cde-crypto/trading-bot-cronjob:$TAG"

deploy_run_job() {
    local job="$1"

    echo "=== Cloud Run Job : $job ==="

    if gcloud run jobs describe "$job" \
        --region="$REGION" \
        --project="$PROJECT_ID" \
        >/dev/null 2>&1
    then
        echo "Mise à jour de $job"

        gcloud run jobs update "$job" \
            --image="$IMAGE" \
            --region="$REGION" \
            --service-account="container-runtime@jan26-cde-crypto.iam.gserviceaccount.com" \
            --command="python" \
            --args="$job.py"
    else
        echo "Création de $job"

        gcloud run jobs create "$job" \
            --image="$IMAGE" \
            --region="$REGION" \
            --service-account="container-runtime@jan26-cde-crypto.iam.gserviceaccount.com" \
            --command="python" \
            --args="$job.py"
    fi
}
deploy_scheduler() {
    local job="$1"
    local schedule="$2"

    local scheduler="${job}-scheduler"

    local uri="https://run.googleapis.com/v2/projects/${PROJECT_ID}/locations/${REGION}/jobs/${job}:run"

    echo "=== Scheduler : $scheduler ($schedule) ==="

    if gcloud scheduler jobs describe "$scheduler" \
        --location="$REGION" \
        --project="$PROJECT_ID" \
        >/dev/null 2>&1
    then
        echo "Mise à jour de $scheduler"

        gcloud scheduler jobs update http "$scheduler" \
            --schedule="$schedule" \
            --uri="$uri" \
            --http-method=POST \
            --oauth-service-account-email="$SERVICE_ACCOUNT" \
            --time-zone="Europe/Paris" \
            --location="$REGION"
    else
        echo "Création de $scheduler"

        gcloud scheduler jobs create http "$scheduler" \
            --schedule="$schedule" \
            --uri="$uri" \
            --http-method=POST \
            --oauth-service-account-email="$SERVICE_ACCOUNT" \
            --time-zone="Europe/Paris" \
            --location="$REGION"
    fi
}

# mise en place des jobs et scheduler pour les jobs horaire
job="trade-horaire" 
deploy_run_job "$job"
deploy_scheduler "$job" "0 * * * *"

# mise en place des jobs et scheduler pour les jobs journaliers
job="trade-journalier"
deploy_run_job "$job"
deploy_scheduler "$job" "47 23 * * *"

# mise en place des jobs et scheduler pour notre stockage des transactions
job="table-setup"
deploy_run_job "$job"
deploy_scheduler "$job" "0 0 1 * *"

echo "Déploiement terminé."