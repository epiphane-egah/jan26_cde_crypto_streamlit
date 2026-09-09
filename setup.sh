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

docker build -f frontend.yml -t trading-bot-frontend:latest .
docker tag trading-bot-frontend:latest epiphane/trading-bot-frontend:latest
docker push epiphane/trading-bot-frontend:latest

docker build -f cronjob.yml -t trading-bot-cron:latest .
docker tag trading-bot-cron:latest epiphane/trading-bot-cron:latest
docker push epiphane/trading-bot-cron:latest

docker compose up -d
