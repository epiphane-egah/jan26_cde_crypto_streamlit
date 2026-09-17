if [ -z "$(docker network ls -q -f name=trading-bot-network)" ]; then
    docker network create trading-bot-network
fi

if [ -z "$(docker volume ls -q -f name=volume-postgres)" ]; then
    docker volume create volume-postgres
fi

if [ -z "$(docker volume ls -q -f name=cron-volume-tr)" ]; then
    docker volume create cron-volume-tr
fi

if [ -z "$(docker volume ls -q -f name=cron-volume-logs)" ]; then
    docker volume create cron-volume-logs
fi

docker login

docker buildx build --platform linux/amd54 -f frontend.yml -t trading-bot-frontend:latest .
docker tag trading-bot-frontend:latest eepiphane/trading-bot-frontend:latest
docker push eepiphane/trading-bot-frontend:latest

docker buildx build --platform linux/amd64 -f cronjob.yml -t trading-bot-cron:latest .
docker tag trading-bot-cron:latest eepiphane/trading-bot-cron:latest
docker push eepiphane/trading-bot-cron:latest

docker compose up -d
