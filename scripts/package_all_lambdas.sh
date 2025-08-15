#!/bin/bash
# Usage: ./scripts/package_all_lambdas.sh
# Packages all lambdas in lambdas/ to dist/<lambda>.zip
set -e
LAMBDA_ROOT="lambdas"
DIST_DIR="dist"
SCRIPT_DIR="$(dirname "$0")"
mkdir -p "$DIST_DIR"

for LAMBDA in "$LAMBDA_ROOT"/*; do
  if [ -d "$LAMBDA" ]; then
    NAME=$(basename "$LAMBDA")
    "$SCRIPT_DIR/package_lambda.sh" "$LAMBDA" "$DIST_DIR/${NAME}.zip"
  fi
done

echo "All Lambdas packaged in $DIST_DIR/"
