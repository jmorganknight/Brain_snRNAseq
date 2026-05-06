#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "== Docker Preflight =="

echo "[1/7] Checking required files"
required_files=(
  "docker-compose.yml"
  "docker/Dockerfile.r-python"
  "docker/install_r_packages.R"
  "requirements.pipeline.txt"
  ".dockerignore"
)
for f in "${required_files[@]}"; do
  if [[ ! -f "$f" ]]; then
    echo "ERROR: Missing required file: $f" >&2
    exit 1
  fi
done

echo "[2/7] Checking docker and compose availability"
if ! command -v docker >/dev/null 2>&1; then
  echo "ERROR: docker is not installed or not in PATH" >&2
  exit 1
fi

docker --version
if ! docker compose version >/dev/null 2>&1; then
  echo "ERROR: docker compose plugin is not available" >&2
  exit 1
fi
docker compose version

echo "[3/7] Validating compose file"
docker compose config >/dev/null

echo "[4/7] Verifying pipeline requirements size"
line_count=$(wc -l < requirements.pipeline.txt || echo 0)
if [[ "$line_count" -lt 10 ]]; then
  echo "WARNING: requirements.pipeline.txt looks short ($line_count lines)."
fi
echo "requirements.pipeline.txt lines: $line_count"

echo "[5/7] Estimating build context"
if command -v du >/dev/null 2>&1; then
  ctx_kb=$(du -sk . | awk '{print $1}')
  echo "Workspace size (pre-.dockerignore): ${ctx_kb} KB"
fi

echo "[6/7] Checking notebooks and Rmd presence"
ls Notebooks/*.ipynb >/dev/null 2>&1 || {
  echo "ERROR: No .ipynb files found in Notebooks/" >&2
  exit 1
}
ls Notebooks/*.Rmd >/dev/null 2>&1 || {
  echo "WARNING: No .Rmd files found in Notebooks/"
}

echo "[7/7] Optional smoke targets"
echo "  - Build: docker compose build"
echo "  - Start: docker compose up"
echo "  - Render Rmd in container: bash docker/run_all_rmd.sh"

echo "Preflight complete: OK"
