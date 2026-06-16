#!/usr/bin/env bash
# ──────────────────────────────────────────────
# Users API — Environment Bootstrap Script
# ──────────────────────────────────────────────
# Generates a .env file from .env.example with
# a cryptographically secure JWT secret key.
#
# Usage:
#   ./scripts/init_env.sh
#   just setup
# ──────────────────────────────────────────────

set -euo pipefail

ENV_FILE=".env"
TEMPLATE=".env.example"

if [ -f "$ENV_FILE" ]; then
    echo "⚠  $ENV_FILE already exists. Remove it first to regenerate."
    exit 1
fi

if [ ! -f "$TEMPLATE" ]; then
    echo "✗  $TEMPLATE not found. Are you in the project root?"
    exit 1
fi

cp "$TEMPLATE" "$ENV_FILE"

# Generate a cryptographically secure 256-bit JWT secret
JWT_SECRET=$(openssl rand -hex 32)
sed -i "s/JWT_SECRET_KEY=CHANGE_ME/JWT_SECRET_KEY=${JWT_SECRET}/" "$ENV_FILE"

echo "✔  $ENV_FILE created successfully."
echo "   JWT_SECRET_KEY has been set to a secure random value."
echo ""
echo "   Review the file and adjust values as needed:"
echo "   cat $ENV_FILE"
