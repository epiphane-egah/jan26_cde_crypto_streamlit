# 1. configuration gcloud 
PROJECT_ID="jan26-cde-crypto"
GITHUB_REPO="epiphane-egah/jan26_cde_crypto_streamlit"
POOL_NAME="github"
PROVIDER_NAME="github-provider" # Nom du provider OIDC
PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" \
  --format="value(projectNumber)")
SERVICE_ACCOUNT="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"
# selectionner un projet
gcloud config set project "$PROJECT_ID"


# activer les services si ce n'est pas encore fait
gcloud services enable \
  iamcredentials.googleapis.com \
  sts.googleapis.com \
  run.googleapis.com \
  secretmanager.googleapis.com \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com \
  cloudscheduler.googleapis.com \
  cloudresourcemanager.googleapis.com \
  --project=jan26-cde-crypto


# création d'un espace workload identity sur gcloud (système externe)
gcloud iam workload-identity-pools describe "$POOL_NAME" --location="global" >/dev/null 2>&1 \
 gcloud iam workload-identity-pools create "$POOL_NAME" \
  --project="$PROJECT_ID" \
  --location="global" \
  --display-name="GitHub Actions"
# si tu recoit une demande de connection de mon ripo github, il faut accepter
# github de son côté garantit que c'est bien un de ses repo
gcloud iam workload-identity-pools describe "$PROVIDER_NAME" --location="global" >/dev/null 2>&1 \
  gcloud iam workload-identity-pools providers create-oidc "$PROVIDER_NAME" \
  --project="$PROJECT_ID" \
  --location="global" \
  --workload-identity-pool="$POOL_NAME" \
  --display-name="GitHub Provider" \
  --issuer-uri="https://token.actions.githubusercontent.com" \
  --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository" \
  --attribute-condition="assertion.repository=='$GITHUB_REPO'"
# autoriser github à utiliser le service account crée.
gcloud iam service-accounts add-iam-policy-binding \
  "$PROJECT_NUMBER-compute@developer.gserviceaccount.com" \
  --project="$PROJECT_ID" \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL_NAME}/attribute.repository/${GITHUB_REPO}"
# lien qui identifie le provider name
gcloud iam workload-identity-pools providers describe "$PROVIDER_NAME" \
  --project="$PROJECT_ID" \
  --location="global" \
  --workload-identity-pool="$POOL_NAME" \
  --format="value(name)"
# 2. configuration de secrets sur Github
# GCP_WIF_PROVIDER
# GCP_SERVICE_ACCOUNT


# création d'un runtime service account pour mes run jobs et run service afin d'accèder au secret et à cloud storage
gcloud iam service-accounts describe container-runtime@jan26-cde-crypto.iam.gserviceaccount.com >/dev/null 2>&1 || \
    gcloud iam service-accounts create container-runtime \
    --display-name="Mon compte de service pour permettre au run jobs"
gcloud secrets add-iam-policy-binding clients-database-url-pooler \
  --member="serviceAccount:container-runtime@jan26-cde-crypto.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
# donner le droit au service account qui permet au shceduler de déclancher les run jobs
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:$SERVICE_ACCOUNT" \
    --role="roles/run.invoker"
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:container-runtime@jan26-cde-crypto.iam.gserviceaccount.com" \
  --role="roles/storage.admin"

