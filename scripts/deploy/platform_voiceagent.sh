#!/usr/bin/env bash
set -Eeuo pipefail

readonly APP_DIR="/home/deploy/apps/voiceagent-platform"
readonly REPO_DIR="${APP_DIR}/repo"
readonly COMPOSE_PROJECT="voiceagent-platform"
readonly IMAGE_NAME="voiceagent-platform:latest"
readonly ROLLBACK_IMAGE="voiceagent-platform:rollback"
readonly HEALTH_URL="http://127.0.0.1:8020/health"

if [[ $# -ne 0 ]]; then
  echo "This command accepts the commit SHA on standard input only" >&2
  exit 2
fi

IFS= read -r deploy_sha
readonly DEPLOY_SHA="${deploy_sha}"
unset deploy_sha

if [[ ! "${DEPLOY_SHA}" =~ ^[0-9a-f]{40}$ ]]; then
  echo "A full Git commit SHA is required" >&2
  exit 2
fi

git_as_deploy() {
  runuser -u deploy -- env GIT_TERMINAL_PROMPT=0 git -C "${REPO_DIR}" "$@"
}

fetch_main() {
  local attempt

  # GitHub HTTPS fetches can fail transiently before any deployment work starts.
  for attempt in 1 2 3; do
    if git_as_deploy fetch --quiet origin main; then
      return 0
    fi
    if [[ "${attempt}" -lt 3 ]]; then
      echo "Git fetch attempt ${attempt} failed; retrying" >&2
      sleep $((attempt * 3))
    fi
  done

  echo "Git fetch failed after 3 attempts" >&2
  return 1
}

fetch_main
git_as_deploy cat-file -e "${DEPLOY_SHA}^{commit}"

if ! git_as_deploy merge-base --is-ancestor "${DEPLOY_SHA}" origin/main; then
  echo "Refusing to deploy a commit outside origin/main" >&2
  exit 3
fi

readonly PREVIOUS_SHA="$(git_as_deploy rev-parse HEAD)"
had_previous_image=false

rollback() {
  local exit_code=$?
  echo "Deployment failed; restoring the previous revision" >&2
  git_as_deploy checkout --quiet --detach "${PREVIOUS_SHA}" || true
  if [[ "${had_previous_image}" == "true" ]]; then
    docker image tag "${ROLLBACK_IMAGE}" "${IMAGE_NAME}" || true
    docker compose --project-name "${COMPOSE_PROJECT}" up -d --force-recreate || true
  fi
  exit "${exit_code}"
}
trap rollback ERR

git_as_deploy checkout --quiet --detach "${DEPLOY_SHA}"
cd "${REPO_DIR}"
docker compose --project-name "${COMPOSE_PROJECT}" config --quiet

if docker image inspect "${IMAGE_NAME}" >/dev/null 2>&1; then
  docker image tag "${IMAGE_NAME}" "${ROLLBACK_IMAGE}"
  had_previous_image=true
fi

docker compose --project-name "${COMPOSE_PROJECT}" build
docker compose \
  --project-name "${COMPOSE_PROJECT}" \
  up -d --remove-orphans --wait --wait-timeout 120
curl --fail --show-error --silent --retry 5 --retry-delay 2 "${HEALTH_URL}" >/dev/null

trap - ERR
docker image rm "${ROLLBACK_IMAGE}" >/dev/null 2>&1 || true
echo "VoiceAgent deployed at ${DEPLOY_SHA}"
