#!/bin/bash
set -euo pipefail

# configuration projet
gcloud config set project jan26-cde-crypto
REGION="europe-west1"
PROJECT_ID="$(gcloud config get-value project)"
PROJECT_NUMBER="$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')"
SERVICE_ACCOUNT="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

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