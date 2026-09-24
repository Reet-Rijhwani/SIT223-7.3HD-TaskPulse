
#!/usr/bin/env bash
# Demo only: run separately after a successful CI/CD pipeline.
# Simulates a production readiness failure and captures alert events.

set -euo pipefail

container="taskpulse-prod-api-1"
production_url="http://127.0.0.1:18081"
receiver_url="http://127.0.0.1:19094/alerts"
failure_flag="/tmp/taskpulse-unhealthy"

# Always remove the simulated failure flag when the script exits.
cleanup() {
    echo 'Ensuring production readiness is restored...'

    docker exec "$container" rm -f "$failure_flag" \
        >/dev/null 2>&1 || true
}

trap cleanup EXIT

# Confirm production is healthy before starting the simulation.
echo 'Checking production readiness...'

./scripts/wait_healthy.sh "$production_url"

# Simulate the production readiness failure.
echo 'Simulating a readiness failure for 40 seconds...'

docker exec "$container" touch "$failure_flag"

sleep 40

# Retrieve the alert notifications received by the webhook.
echo 'Alert events received:'

curl --fail --silent --show-error "$receiver_url" | python3 -m json.tool

# Recover production.
echo 'Recovering production readiness...'

docker exec "$container" rm -f "$failure_flag"

./scripts/wait_healthy.sh "$production_url"

echo 'Incident demonstration completed.'