#!/usr/bin/env bash
# Promote verified staging image to production, with automatic rollback on failure.
set -euo pipefail
: "${APP_IMAGE:?provide tested image}" "${RELEASE_VERSION:?provide version}"
export APP_IMAGE RELEASE_VERSION
project=taskpulse-prod
file=compose.production.yml
old_image="$(docker inspect "${project}-api-1" --format '{{.Config.Image}}' 2>/dev/null || true)"
rollback() {
  echo 'Production promotion failed; starting rollback.' >&2
  if [ -n "$old_image" ]; then
    APP_IMAGE="$old_image" RELEASE_VERSION="rollback" docker compose -p "$project" -f "$file" up -d --no-build --force-recreate api
    ./scripts/wait_healthy.sh http://127.0.0.1:18081 || true
  else
    echo 'No previous release is available for automated rollback.' >&2
  fi
}
trap rollback ERR
docker compose -p "$project" -f "$file" up -d --no-build --force-recreate api
./scripts/wait_healthy.sh http://127.0.0.1:18081
python scripts/smoke.py http://127.0.0.1:18081
trap - ERR
printf '%s image=%s previous=%s\n' "$RELEASE_VERSION" "$APP_IMAGE" "${old_image:-none}" >> release-history.txt
printf 'PASS: production release %s\n' "$RELEASE_VERSION"
