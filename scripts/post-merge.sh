#!/bin/bash
set -e

echo "==> Installing pnpm dependencies..."
pnpm install --frozen-lockfile=false

echo "==> Installing Python dependencies for API server..."
pip install -r artifacts/api-server/requirements.txt -q

echo "==> Installing Python dependencies for collector..."
if [ -f collector/requirements.txt ]; then
  pip install -r collector/requirements.txt -q
fi

echo "==> Post-merge setup complete."
