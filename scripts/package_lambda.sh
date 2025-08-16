#!/bin/bash
# Usage: ./scripts/package_lambda.sh <lambda_dir> <output_zip>
# Example: ./scripts/package_lambda.sh lambdas/v_devices dist/v_devices.zip

set -e

# Check for required CLI tools
if ! command -v pip3 >/dev/null 2>&1; then
  echo "Error: pip3 is not installed. Please install pip3 (Python 3) to build Lambda packages." >&2
  exit 1
fi

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
  if ! pip3 install -r "$LAMBDA_DIR/requirements.txt" -t "$TMP_DIR" --upgrade; then
    echo "Error: pip3 failed to install dependencies for $LAMBDA_DIR. Check requirements.txt and your Python environment." >&2
    rm -rf "$TMP_DIR"
    exit 1
  fi
fi


# Create zip
cd "$TMP_DIR"
if ! zip -r9 "$OLDPWD/$OUTPUT_ZIP" .; then
  echo "Error: Failed to create zip archive $OUTPUT_ZIP." >&2
  cd "$OLDPWD"
  rm -rf "$TMP_DIR"
  exit 1
fi
cd "$OLDPWD"

# Clean up
echo "Packaged $OUTPUT_ZIP with Lambda and shared code."
rm -rf "$TMP_DIR"
