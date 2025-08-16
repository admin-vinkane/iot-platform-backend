#!/bin/bash
# Usage: ./scripts/package_lambda.sh <lambda_dir> <output_zip>
# Example: ./scripts/package_lambda.sh lambdas/v_devices dist/v_devices.zip

set -e

LAMBDA_DIR="$1"
OUTPUT_ZIP="$2"
SHARED_DIR="shared"

if [ -z "$LAMBDA_DIR" ] || [ -z "$OUTPUT_ZIP" ]; then
  echo "Usage: $0 <lambda_dir> <output_zip>"
  exit 1
fi

TMP_DIR=$(mktemp -d)

# Copy Lambda code
cp -r "$LAMBDA_DIR"/* "$TMP_DIR"/
# Copy shared utils
cp -r "$SHARED_DIR" "$TMP_DIR/"

# Install Python dependencies if requirements.txt exists
if [ -f "$LAMBDA_DIR/requirements.txt" ]; then
  pip3 install -r "$LAMBDA_DIR/requirements.txt" -t "$TMP_DIR" --upgrade
fi

# Create zip
cd "$TMP_DIR"
zip -r9 "$OLDPWD/$OUTPUT_ZIP" .
cd "$OLDPWD"

# Clean up
echo "Packaged $OUTPUT_ZIP with Lambda and shared code."
rm -rf "$TMP_DIR"
