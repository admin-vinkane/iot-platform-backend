#!/bin/bash

# Usage: ./scripts/package_and_upload_lambda.sh <lambda_dir> <output_zip> <bucket> <version>
# Packages a single lambda, zips it, and uploads to S3 (Linux compatible, auto-handles Docker, AWS CLI, and credentials)


set -e

# If not running inside Docker, re-invoke this script inside the official AWS Lambda Python 3.12 Docker image for Linux compatibility,
# and ensure AWS CLI and credentials are available inside the container.
if [ -z "$IN_LAMBDA_DOCKER" ]; then
  echo "[INFO] Re-invoking inside Docker for Linux compatibility with AWS CLI and credentials..."
  SCRIPT_DIR="$(dirname "$0")"
  PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
  AWS_DIR="$HOME/.aws"
  docker run --platform linux/amd64 --rm \
    -v "$PROJECT_ROOT":/var/task \
    -v "$AWS_DIR":/root/.aws \
    -w /var/task \
    --entrypoint /bin/bash \
    -e IN_LAMBDA_DOCKER=1 \
    public.ecr.aws/lambda/python:3.12 \
  -c "pip install awscli && ./scripts/package_and_upload_lambda.sh $@"
  exit $?
fi

LAMBDA_DIR="$1"
OUTPUT_ZIP="$2"
BUCKET="$3"
VERSION="$4"
SHARED_DIR="shared"

if [ -z "$LAMBDA_DIR" ] || [ -z "$OUTPUT_ZIP" ] || [ -z "$BUCKET" ] || [ -z "$VERSION" ]; then
  echo "Usage: $0 <lambda_dir> <output_zip> <bucket> <version>"
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

# Upload to S3
aws s3 cp "$OUTPUT_ZIP" "s3://$BUCKET/$(basename $LAMBDA_DIR)/$VERSION/$(basename $OUTPUT_ZIP)"

# Clean up
echo "Packaged and uploaded $OUTPUT_ZIP to s3://$BUCKET/$(basename $LAMBDA_DIR)/$VERSION/$(basename $OUTPUT_ZIP)"
rm -rf "$TMP_DIR"
