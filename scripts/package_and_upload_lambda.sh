#!/bin/bash

# Usage: ./scripts/package_and_upload_lambda.sh <lambda_dir> --env dev|prod [--upload]
# Packages a single lambda, zips it, and optionally uploads to S3 (Linux compatible, auto-handles Docker, AWS CLI, and credentials)


set -e

# Set VERSION to current timestamp (YYYYmmddHHMMSS)
# VERSION=$(date +%Y%m%d%H%M%S)
VERSION="20250816204228"


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
  -c 'pip install awscli && ./scripts/package_and_upload_lambda.sh '"$*"
  exit $?
fi

# Parse arguments (align with all-lambdas script)
LAMBDA_DIR=""
ENV=""
UPLOAD=false

while [[ $# -gt 0 ]]; do
  case $1 in
    --env)
      ENV="$2"
      shift 2
      ;;
    --upload)
      UPLOAD=true
      shift
      ;;
    *)
      if [ -z "$LAMBDA_DIR" ]; then
        LAMBDA_DIR="$1"
      fi
      shift
      ;;
  esac
done

if [ -z "$LAMBDA_DIR" ] || [ -z "$ENV" ]; then
  echo "Usage: $0 <lambda_dir> --env dev|prod [--upload]"
  exit 1
fi

LAMBDA_NAME="$(basename "$LAMBDA_DIR")"
SHARED_DIR="shared"
DIST_DIR="dist"
mkdir -p "$DIST_DIR"
OUTPUT_ZIP="$DIST_DIR/${LAMBDA_NAME}.zip"

# Set bucket based on environment
if [ "$ENV" == "prod" ]; then
  BUCKET="my-lambda-bucket-vinkane-prod"
else
  BUCKET="my-lambda-bucket-vinkane-dev"
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
python3 -c "
import zipfile
import os
with zipfile.ZipFile('$OLDPWD/$OUTPUT_ZIP', 'w', zipfile.ZIP_DEFLATED) as zipf:
    for root, dirs, files in os.walk('.'):
        for file in files:
            zipf.write(os.path.join(root, file), os.path.relpath(os.path.join(root, file), '.'))
print('Created zip archive successfully')
"
if [ $? -ne 0 ]; then
  echo "Error: Failed to create zip archive $OUTPUT_ZIP." >&2
  cd "$OLDPWD"
  rm -rf "$TMP_DIR"
  exit 1
fi
cd "$OLDPWD"

if [ "$UPLOAD" = true ]; then
  aws s3 cp "$OUTPUT_ZIP" "s3://$BUCKET/${LAMBDA_NAME}/$VERSION/${LAMBDA_NAME}.zip"
  echo "Packaged and uploaded $OUTPUT_ZIP to s3://$BUCKET/${LAMBDA_NAME}/$VERSION/${LAMBDA_NAME}.zip"
else
  echo "Packaged $OUTPUT_ZIP (not uploaded to S3)"
fi
rm -rf "$TMP_DIR"
