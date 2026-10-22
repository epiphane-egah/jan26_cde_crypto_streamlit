# autoriser l'utilisation de l'api artifact registry
gcloud services enable artifactregistry.googleapis.com

# créer un repo
gcloud artifacts repositories describe jan26-cde-api --location=europe-west1 &>/dev/null || \
gcloud artifacts repositories create jan26-cde-api \
  --repository-format=docker \
  --location=europe-west1

# 3. Configurer l'authentification Docker pour pouvoir push
gcloud auth configure-docker europe-west1-docker.pkg.dev

# 4. Vérifier que ça a bien été créé
# gcloud artifacts repositories list

TAG=$(date +%Y-%m-%d_%Hh%M)
docker buildx build --platform linux/amd64 \
    -t trading-bot-backend:$TAG backend/.
docker tag trading-bot-backend:$TAG europe-west1-docker.pkg.dev/jan26-cde-crypto/jan26-cde-crypto/trading-bot-backend:$TAG
docker push europe-west1-docker.pkg.dev/jan26-cde-crypto/jan26-cde-crypto/trading-bot-backend:$TAG

gcloud run deploy jan26-cde-crypto-api \
  --image=europe-west1-docker.pkg.dev/jan26-cde-crypto/jan26-cde-crypto/trading-bot-backend:$TAG \
  --platform=managed \
  --region=europe-west1 \
  --port=8000 \
  --service-account=container-runtime@jan26-cde-crypto.iam.gserviceaccount.com  \
  --allow-unauthenticated