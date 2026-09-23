#!/usr/bin/env bash
# Demo only: run separately, AFTER showing successful CI/CD. Requires active prod stack.
set -euo pipefail
container=taskpulse-prod-api-1
trap 'docker exec "$container" rm -f /tmp/taskpulse-unhealthy >/dev/null 2>&1 || true' EXIT
echo 'Simulating a readiness failure for 40 seconds...'
docker exec "$container" touch /tmp/taskpulse-unhealthy
sleep 40
echo 'Alert events received:'
curl --fail --silent http://127.0.0.1:19094/alerts | python -m json.tool
echo 'Recovering production readiness...'
docker exec "$container" rm -f /tmp/taskpulse-unhealthy
./scripts/wait_healthy.sh http://127.0.0.1:18081
