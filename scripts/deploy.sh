#!/usr/bin/env bash
# Deploy SciAgent backend to Cloud Run.
# Usage: ./scripts/deploy.sh [--no-build] [--region REGION]
#   --no-build   Skip Cloud Build (re-deploy the last image for this SHA)
#   --region     Override region (default: europe-west1)
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

PROJECT_ID="sciagent-496617"
SERVICE="sciagent"
REGION="europe-west1"
REGISTRY="${REGION}-docker.pkg.dev/${PROJECT_ID}/sciagent/backend"

NO_BUILD=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --no-build) NO_BUILD=1; shift ;;
    --region)   REGION="$2"; REGISTRY="${REGION}-docker.pkg.dev/${PROJECT_ID}/sciagent/backend"; shift 2 ;;
    *) echo "Unknown flag: $1" >&2; exit 1 ;;
  esac
done

SHORT_SHA=$(git rev-parse --short HEAD)
IMAGE="${REGISTRY}:${SHORT_SHA}"

echo "==> Project : ${PROJECT_ID}"
echo "==> Region  : ${REGION}"
echo "==> Image   : ${IMAGE}"
echo ""

if [[ $NO_BUILD -eq 0 ]]; then
  echo "==> Building and pushing via Cloud Build..."
  gcloud builds submit \
    --project="${PROJECT_ID}" \
    --tag="${IMAGE}" \
    "${REPO_ROOT}"
  # also tag as latest for reference
  gcloud container images add-tag "${IMAGE}" "${REGISTRY}:latest" --quiet
  echo ""
fi

echo "==> Deploying to Cloud Run..."
gcloud run deploy "${SERVICE}" \
  --project="${PROJECT_ID}" \
  --image="${IMAGE}" \
  --region="${REGION}" \
  --platform=managed

echo ""
echo "==> Done. Service URL:"
gcloud run services describe "${SERVICE}" \
  --project="${PROJECT_ID}" \
  --region="${REGION}" \
  --format="value(status.url)"
