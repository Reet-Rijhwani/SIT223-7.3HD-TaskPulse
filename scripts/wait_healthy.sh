#!/usr/bin/env bash
set -euo pipefail
url="$1"
for i in $(seq 1 45); do
  if curl --fail --silent --max-time 2 "$url/health/ready" > /dev/null; then
    echo "Healthy: $url"
    exit 0
  fi
  sleep 2
done
echo "ERROR: $url did not become ready" >&2
exit 1
