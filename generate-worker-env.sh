#!/bin/bash

echo "Starting database..."
docker compose up -d hatchet-lite postgres

echo "Waiting for Hatchet server to be ready..."
sleep 10

: > .worker-env
cat <<EOF > .worker-env
HATCHET_CLIENT_TOKEN="$(docker compose -f docker-compose.yml exec hatchet-lite /hatchet-admin token create --config /config --tenant-id 707d0855-80ab-4e1f-a156-f1c4546cbf52 | xargs)"
HATCHET_CLIENT_TLS_STRATEGY=none
EOF
echo "Worker environment variables written to .worker-env"
