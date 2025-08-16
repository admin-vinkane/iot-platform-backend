#!/bin/bash
# Usage: ./scripts/package_and_upload_all_lambdas.sh [--upload]
# Packages all lambdas in lambdas/ to dist/<lambda>.zip
# If --upload is provided, uploads to S3 as well

set -e

LAMBDA_ROOT="lambdas"
DIST_DIR="dist"
SCRIPT_DIR="$(dirname "$0")"
UPLOAD=false
BUCKET="my-lambda-bucket"

if [ "$1" == "--upload" ]; then
  UPLOAD=true
fi

if [ -d .git ]; then
  VERSION=$(git rev-parse --short HEAD)
else
  VERSION=$(date +%Y%m%d%H%M%S)
fi
echo $VERSION > .version

mkdir -p "$DIST_DIR"

for LAMBDA in "$LAMBDA_ROOT"/*; do
  if [ -d "$LAMBDA" ]; then
    NAME=$(basename "$LAMBDA")
    "$SCRIPT_DIR/package_lambda.sh" "$LAMBDA" "$DIST_DIR/${NAME}.zip"
    if [ "$UPLOAD" = true ]; then
      echo "Uploading $DIST_DIR/${NAME}.zip to s3://$BUCKET/${NAME}/$VERSION/${NAME}.zip"
      aws s3 cp "$DIST_DIR/${NAME}.zip" "s3://$BUCKET/${NAME}/$VERSION/${NAME}.zip"
    fi
  fi
done

if [ "$UPLOAD" = true ]; then
  echo "All Lambdas packaged and uploaded to S3. Version: $VERSION"
else
  echo "All Lambdas packaged in $DIST_DIR/"
fi
