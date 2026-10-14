#!/bin/sh
# Build the published entries, check them, and deploy to Cloud Run.
#   tools/deploy.sh
set -eu
cd "$(dirname "$0")/.."
export PATH="/Library/TeX/texbin:$PATH"

uv run tools/publish.py
uv run ruff check .
uv run python -m pytest -q
gcloud run deploy maths-dsmorgan --source . \
  --project dsmorgan-site --region us-central1 \
  --max-instances=1 --min-instances=0 --allow-unauthenticated
